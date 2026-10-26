# GBSoft CityVision — Drone Odaklı Ürün Planı

**Kanonik kapsam:** Drone / DJI Dock görüntülerinden belediye olaylarının bulunması, haritada birleştirilmesi ve insan onayıyla iş emri adayına dönüştürülmesi.

**Pilot hedefi:** 1 belediye · 1 izinli koridor · 1 drone veya Dock · 30–60 gün.

## 1. Ürün tezi

CityVision, tekrarlanabilir drone uçuşlarından gelen video, fotoğraf ve telemetriyi operasyonel belediye kayıtlarına dönüştürür.

```text
Drone / DJI Dock
  → video + uçuş telemetrisi
  → hızlı aday tespiti
  → gerektiğinde SAM3 segmentasyonu
  → hedef konumu tahmini
  → mekânsal ve zamansal birleştirme
  → harita + kanıt
  → personel onayı
  → iş emri adayı / entegrasyon
```

Sistem ilk sürümde otomatik karar veya otomatik ceza üretmez. Model aday üretir; yetkili personel onaylar veya reddeder.

## 2. MVP kullanım alanları

### Birincil: Atık ve kaçak döküm

- taşmış konteyner,
- yol veya arazi kenarında atık yığını,
- moloz ve kaçak döküm alanı,
- tekrarlayan atık noktalarının izlenmesi.

### İkincil: Yol yüzeyi hasarı

- büyük çukur,
- belirgin yüzey deformasyonu,
- kırık veya bozulmuş asfalt bölgesi,
- aynı koridordaki değişimin zaman içinde karşılaştırılması.

Küçük yol kusurları ancak saha verisi, irtifa ve görüntü çözünürlüğü yeterliyse ürün kapsamına alınır.

## 3. MVP dışında

- canlı uçuş sırasında zorunlu anlık analiz,
- otonom iş emri açma,
- yüz tanıma ve plaka tanıma,
- trafik cezası veya EDS,
- her serbest metin sorgusunda tüm video arşivini yeniden tarama,
- santimetre seviyesinde hedef koordinatı garantisi,
- tam ERP entegrasyonu,
- bütün belediye sorunlarını tek modelle çözme iddiası.

## 4. Yapay zekâ mimarisi

### 4.1 Hızlı aday bulma

Bilinen olay sınıfları uçuş sisteme girdiğinde bir kez taranır. Her sonuç için zaman damgası, sınıf, güven skoru, kutu, kanıt karesi, model sürümü ve konum bilgisi indekslenir.

### 4.2 SAM3'ün rolü

SAM3 ana tarayıcı değildir. Şunlar için kullanılır:

- aday nesnenin hassas maskesini çıkarmak,
- alan ve kapladığı yüzeyi ölçmek,
- operatöre daha anlaşılır görsel kanıt sunmak,
- etiketleme süresini azaltmak,
- yeni sorgularda ön elemeden geçen az sayıdaki kareyi doğrulamak.

Dashboard'da “çöp” gibi bilinen sorgular indeksli sonuçları anında döndürür. Yeni bir sorgu önce açık kelime / görsel benzerlik katmanıyla aday kareleri seçer; SAM3 yalnızca bu adaylarda çalışır.

### 4.3 Adaptif örnekleme

- genel tarama: saniyede yaklaşık 0,5–1 kare,
- aday görülen bölümde daha yoğun analiz,
- yüksek çözünürlüklü görüntüde gerektiğinde tile/crop,
- aynı nesnenin ardışık karelerdeki sonuçlarını tek gözleme indirme,
- tam işaretlenmiş video yerine kanıt karesi ve kısa klip.

## 5. Drone çekim standardı

Her pilot koridor için uçuş profili kilitlenir:

- rota ve waypoint'ler,
- irtifa aralığı,
- uçuş hızı,
- gimbal açısı,
- çözünürlük ve kare hızı,
- günün tercih edilen saati,
- görüntü bindirmesi,
- hava ve görüş kabul koşulları.

Geniş alan taraması için nadir, yol ayrıntısı ve hedef doğrulama için alçak eğik çekim profili kullanılır. Aynı rotanın aynı parametrelerle tekrarlanması model karşılaştırması ve olay birleştirme için zorunludur.

## 6. Konumlandırma

Drone konumu, görüntüdeki hedefin konumu değildir. Sistem ayrı ayrı saklar:

- platform konumu,
- kamera yönelimi ve gimbal açısı,
- irtifa,
- tahmini hedef konumu,
- konum doğruluğu,
- tahmin kaynağı ve algoritma sürümü.

İlk pilot yaklaşık hedef konumuyla çalışabilir. Daha yüksek doğruluk için kamera kalibrasyonu, arazi/yüzey modeli ve ışın–zemin kesişimi eklenir. Konumu belirsiz gözlemler otomatik olarak tek olaya birleştirilmez.

## 7. Veri ve değerlendirme

Model seçmeden önce drone perspektifinde bir gold set oluşturulur:

- 150–300 gerçek pozitif olay örneği,
- en az 500 zor negatif kare veya tile,
- en az 3 tamamen olaysız uçuş,
- farklı irtifa, ışık, zemin ve mevsim örnekleri,
- aynı bölgenin tekrarlı uçuşları.

Başlangıç pilot hedefleri:

| Ölçüt | Başlangıç eşiği |
| --- | ---: |
| Görülebilir olaylarda recall | ≥ %70 |
| Personel kuyruğunda precision | ≥ %80 |
| İlk 20 sonuçta precision | ≥ %85 |
| Yanlış alarm | ≤ 3 / uçuş saati |
| Gerçek olay başına sonuç | ≤ 1,2 |
| Şehirler arası veri sızıntısı | 0 |
| Otomatik iş emri | 0 |

Eşikler gölgeli, temiz ve tamamen negatif uçuşlar üzerinde ayrı raporlanır. Üretim hedefleri pilot sonuçlarından sonra yükseltilir.

## 8. Platform bileşenleri

1. **Flight ingestion:** DJI Dock / FlightHub senkronizasyonu ve kontrollü manuel yükleme.
2. **Object storage:** Ham uçuş medyası, proxy, kanıt ve crop için ayrı yaşam döngüsü.
3. **GPU job queue:** Lease, heartbeat, ilerleme, iptal, tekrar deneme ve idempotency.
4. **Detection index:** Kare ve aday bazlı aranabilir sonuç tablosu.
5. **Event engine:** Mekânsal/zamansal birleştirme ve güven skoru.
6. **Review dashboard:** Harita, kanıt, onay/ret ve geri bildirim.
7. **Work-order adapter:** Onaylanmış olayları CSV/API ile belediye sistemine aktarma.
8. **Audit and tenancy:** Şehir izolasyonu, rol bazlı erişim ve denetim kaydı.

## 9. Depolama ve maliyet kontrolü

- Tarayıcı yüklemesi uygulama belleğine alınmaz; doğrudan nesne depoya çok parçalı yükleme yapılır.
- Ham video için belediyeyle kararlaştırılmış kısa saklama süresi uygulanır.
- Onaylanmış kanıtlar ve audit kayıtları ayrı politikayla tutulur.
- Dashboard için düşük çözünürlüklü proxy kullanılır.
- Tam işaretlenmiş video varsayılan olarak üretilmez.
- GPU yalnızca görev varken çalıştırılır; pilot öncesinde donanım satın alınmaz.
- Bilinen sorgular için yeniden inference yapılmaz.

## 10. Güvenlik, KVKK ve operasyon

- Uçuş yalnızca izinli koridor ve görev kapsamında yapılır.
- Konut pencereleri, özel alanlar ve gereksiz kişi/plaka görüntüsü çekim planında azaltılır.
- Ham görüntü erişimi en az ayrıcalık ilkesiyle sınırlandırılır.
- Medya bağlantıları kısa ömürlü ve imzalıdır.
- Her erişim, dışa aktarma, onay ve silme işlemi audit kaydına girer.
- Saklama süresi sonunda otomatik silme uygulanır.
- Model sonucu karar değil, personel incelemesine sunulan adaydır.
- Pilot başlamadan önce veri sorumlusu, amaç, hukuki dayanak, aydınlatma yöntemi ve saklama planı belediyeyle yazılı olarak kilitlenir.

## 11. Teslim planı

### Hafta 1–2 — Veri ve gerçeklik testi

- pilot koridor ve sorumlu belediye birimi,
- uçuş profilleri,
- ilk gold set,
- mevcut modellerin tarafsız benchmark'ı,
- lisans, saklama ve erişim kararları.

### Hafta 3–4 — Güvenilir veri hattı

- büyük dosya yükleme,
- FlightHub senkronizasyonu,
- GPU görev kuyruğu,
- kare/aday indeksi,
- model manifesti ve tekrar üretilebilir çalışma.

### Hafta 5–6 — Hibrit yapay zekâ ve harita

- atık ve yol hasarı aday tespiti,
- adaylarda SAM3 maskesi,
- hedef konumu tahmini,
- olay birleştirme,
- dashboard araması ve kanıt ekranı.

### Hafta 7–8 — Kontrollü saha pilotu

- sabit rotada tekrarlı uçuşlar,
- personel onay/ret akışı,
- eşik kilitleme,
- yanlış alarm ve kaçırılan olay analizi,
- CSV/API iş emri adayı,
- haftalık KPI raporu.

## 12. Ürün kapıları

### Gate 0 — Pilot hazırlığı

İzinli koridor, veri sorumluluğu, uçuş standardı, saklama politikası, model lisansları ve belediye sahibi belli değilse geliştirme pilot sayılmaz.

### Gate 1 — Model uygunluğu

Gold set üzerinde temel recall ve review precision hedefleri sağlanmadan dashboard özellikleri genişletilmez.

### Gate 2 — Operasyonel güvenilirlik

Yükleme, görev kuyruğu, şehir izolasyonu, audit, kanıt erişimi ve silme politikası doğrulanır.

### Gate 3 — Ücretli pilot

Sabit rotada saha KPI'ları sağlanır, belediye personelinin inceleme süresi ölçülür ve gerçek iş akışına kontrollü aktarım başlar.

## 13. Başarı tanımı

MVP, çok sayıda özellik üretince değil; belediye personeline az sayıda, doğru, konumu ve kanıtı anlaşılır olay adayı sunduğunda başarılıdır. Ana optimizasyon hedefi GPU maliyeti değil, **doğru olay başına toplam inceleme maliyetidir**.
