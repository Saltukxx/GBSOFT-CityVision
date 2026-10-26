# GBSoft CityVision — SAM3 Görsel Arama ve Segmentasyon Planı

**Teknik inceleme güncellemesi:** 26 Ağustos 2026  
**Ayrıntılı fizibilite:**
[SAM3 Teknik Fizibilite ve Maliyet Analizi](sam3-visual-search-technical-feasibility.md)

## 0. Teknik inceleme sonrası kararlar

İlk taslak, derin teknik/maliyet incelemesi sonrasında aşağıdaki bağlayıcı
kararlarla geliştirilmiştir:

1. SAM3 bütün arşivin varsayılan tarayıcısı olmayacaktır.
2. Bilinen sorgular önce mevcut YOLO/RF-DETR sonuç ve frame indeksinden aranacak;
   SAM3 yalnız adaylarda maske doğrulaması yapacaktır.
3. Yeni sorgular önce ucuz tile tabanlı text-image/open-vocabulary aday seçimine,
   sonra SAM3'e gidecektir.
4. SAM3.1 video tracker yalnız adayın çevresindeki kısa klipte çalışacaktır.
5. SAM3, mevcut API/container içine eklenmeyecek; ayrı CUDA GPU worker olacaktır.
6. Offline MVP'den önce iş kuyruğu lease/heartbeat/progress/idempotency ve
   resumable video upload ile sağlamlaştırılacaktır.
7. Drone GPS'i hedef GPS'i olarak kullanılmayacaktır; iki konum ayrı saklanacaktır.
8. Tam maskeli annotated video üretilmeyecek; dashboard overlay'i istemci
   tarafında çizecek ve yalnız evidence clip render edilecektir.
9. SAM ve mevcut Ultralytics lisansı hukuk onayı bir P0 go/no-go kapısıdır.
10. Kalite ve maliyet kararı genel benchmark'la değil kendi aerial waste gold
    setimizle verilecektir.

## 1. Amaç

Belediye personelinin CityVision dashboard'u üzerinden `çöp`, `kaçak döküm`,
`moloz` veya benzeri basit bir kavram yazarak seçili drone uçuşlarında görsel
arama yapabilmesini sağlamak.

Sistem, eşleşen nesne ve alanları SAM3 ile bulup segmente edecek; sonuçları
maske, güven skoru, video zamanı, uçuş bilgisi ve mümkün olduğunda tahmini
harita konumuyla gösterecek.

İlk sürüm geçmişte yüklenmiş videolarda, kullanıcı tarafından başlatılan bir
arama olarak çalışacaktır. Canlı uçuş analizi ilk sürümün kapsamında değildir.

## 2. Temel ürün kararı

CityVision'da iki model yolu birlikte kullanılacaktır:

1. Sürekli çalışan YOLO/RF-DETR hattı, bilinen belediye olaylarını hızlı ve
   ekonomik biçimde tespit etmeye devam eder.
2. SAM3 hattı, kullanıcının serbest metin sorgularında ve ayrıntılı piksel
   maskesi gereken adaylarda isteğe bağlı olarak çalışır.

SAM3 sonucu otomatik olarak belediye olayı veya iş emri oluşturmaz. Sonuç önce
CityVision güven katmanından ve gerekiyorsa insan onayından geçer.

## 3. Kullanıcı deneyimi

### 3.1 Arama oluşturma

Belediye personeli dashboard'da:

- Arama metnini girer: `çöp`
- Şehir seçer
- Tarih aralığı seçer
- Bir veya daha fazla uçuş/video seçer
- `Ara` düğmesine basar

Arama arka plan işi olarak kuyruğa alınır. Arayüzde `sırada`, `taranıyor`,
`tamamlandı` veya `başarısız` durumu ve ilerleme oranı gösterilir.

### 3.2 Sonuç ekranı

Her sonuçta aşağıdakiler gösterilir:

- Maskeli önizleme
- Normal görüntü
- Eşleşen kategori
- Güven skoru ve güven bandı
- Video adı, uçuş ve zaman kodu
- Harita konumu ve konum kalitesi
- Videoda ilgili ana gitme bağlantısı
- `Onayla`, `Reddet` ve `Olay oluştur` işlemleri

Sonuçlar galeri, video zaman çizgisi ve harita üzerinde incelenebilir.

## 4. Hedef sistem akışı

```text
Drone videosu + GPS/telemetri
             |
             v
CityVision nesne deposu ve video kataloğu
             |
             v
Dashboard sorgusu: "çöp"
             |
             v
Türkçe sorgu normalizasyonu ve prompt paketi
             |
             v
        Sorgu yönlendirici
        /                 \
       v                   v
Bilinen belediye       Yeni/serbest sorgu
sınıfı                 text-image tile indeksi
       |                   |
       v                   v
Mevcut detection/frame   En iyi K aday kare/crop
indeksi                  |
       \                 /
        v               v
        Seçili adaylarda SAM3 maske doğrulaması
             |
             v
Kısa SAM3.1 takip penceresi + mükerrer sonuç birleştirme
             |
             v
Platform/hedef konumu ayrımı + güven skoru
             |
             v
Sonuç galerisi -> insan onayı -> olay/iş emri
```

## 5. Sorgu yorumlama

Kullanıcının yazdığı tek Türkçe kelime doğrudan tek model prompt'u olarak
kullanılmayacaktır. CityVision sorguyu kontrollü bir prompt paketine çevirecek.

Örnek `çöp` paketi:

- `garbage bag`
- `pile of garbage`
- `street litter`
- `overflowing trash container`
- `dumped waste`
- `construction debris`
- `discarded furniture`

Türkçe eş anlamlılar aynı pakete bağlanır:

- çöp
- atık
- kaçak döküm
- moloz
- taşmış konteyner
- terk edilmiş eşya

İlk sürümde prompt paketleri yönetici tarafından tanımlanmış ve sürümlenmiş
olacaktır. Serbest ve sınırsız prompt üretimi sonraki aşamaya bırakılacaktır.

## 6. Görüntü işleme yaklaşımı

### 6.1 Uzun videolar

SAM3'e saatler süren video tek parça verilmez. Video kısa kliplere veya örnek
karelere bölünür. Çöp gibi sabit olayların ilk taramasında düşük kare sıklığıyla
başlanabilir; aday bulunduğunda çevresindeki kareler daha yoğun işlenir.

### 6.2 Küçük nesneler ve drone çözünürlüğü

Drone görüntüsünün tamamını düşük çözünürlüğe indirmek küçük çöp alanlarını yok
edebilir. Bu nedenle sistem:

1. Kareyi düşük maliyetle ön tarar.
2. Gerekli olduğunda yüksek çözünürlüklü, örtüşen parçalara böler.
3. SAM3'ü aday parçalarda çalıştırır.
4. Parça sınırlarındaki kutu ve maskeleri tekrar birleştirir.

### 6.3 Zamansal birleştirme

Aynı çöp alanının art arda gelen karelerde ürettiği sonuçlar tek bulgu altında
birleştirilir. Bir bulgu için ilk/son görülme zamanı, gözlem sayısı ve en iyi
kanıt karesi saklanır.

### 6.4 Maske formatı

Maskeler veritabanında büyük bitmap olarak tutulmaz. Polygon veya RLE biçiminde
sıkıştırılır. Maskeli önizleme görselleri nesne deposunda saklanır.

## 7. Konumlandırma

Drone GPS'i hedef nesnenin gerçek GPS'i değildir. İlk MVP iki konum kalitesi
sunacaktır:

- `drone_approximate`: Yalnızca drone konumu; yaklaşık sonuç
- `ground_projected`: Kamera ve telemetriyle yere projekte edilmiş hedef konumu

Gerçek hedef koordinatı için mümkün olduğunda şu veriler kullanılacaktır:

- Drone enlem ve boylamı
- Barometrik/AGL yükseklik
- Heading
- Gimbal yaw, pitch ve roll
- Kamera iç parametreleri ve görüntü çözünürlüğü
- Uygunsa sayısal yükseklik modeli

Konum kalitesi dashboard'da açıkça gösterilecek; yaklaşık konum kesin koordinat
gibi sunulmayacaktır.

## 8. Veri modeli

### 8.1 `visual_searches`

- Kimlik
- Şehir ve kullanıcı
- Kullanıcının sorgusu
- Normalize edilmiş sorgu ve prompt paketi sürümü
- Video/uçuş/tarih kapsamı
- Durum ve ilerleme
- Model/checkpoint sürümü
- Oluşturulma, başlama ve bitiş zamanı
- Hata ve özet alanları

### 8.2 `visual_search_hits`

- Arama kimliği
- Video yükleme ve uçuş kimliği
- Kare ve zaman kodu
- Eşleşen kavram
- Güven skoru ve güven bandı
- Kutu koordinatları
- Polygon/RLE maske
- Önizleme nesne anahtarı
- Drone GPS'i
- Tahmini hedef GPS'i ve konum kalitesi
- Mükerrer grup kimliği
- İnceleme durumu ve inceleyen kullanıcı
- Oluşturulan CityVision olay/iş emri bağlantısı

### 8.3 `visual_query_templates`

- Türkçe sorgu ve eş anlamlılar
- SAM3 prompt listesi
- Negatif kavramlar
- Eşikler
- Sürüm ve aktiflik durumu

## 9. Servis ve API taslağı

### Dashboard/API

- `POST /api/visual-searches` — yeni arama oluşturur
- `GET /api/visual-searches` — kullanıcının aramalarını listeler
- `GET /api/visual-searches/{id}` — durum ve özeti döndürür
- `GET /api/visual-searches/{id}/hits` — sayfalı sonuçları döndürür
- `PATCH /api/visual-search-hits/{id}` — onay/red işlemi yapar
- `POST /api/visual-search-hits/{id}/event` — onaylı bulgudan olay oluşturur

### Arka plan işi

Mevcut iş kuyruğuna `sam_visual_search` tipi eklenecektir. İşçi:

1. Kullanıcının şehir ve video erişimini doğrular.
2. Prompt paketini çözer.
3. Video ve telemetriyi nesne deposundan alır.
4. Kare/klipleri seçer.
5. SAM3 çıkarımını çalıştırır.
6. Maskeleri filtreler ve zamansal sonuçları birleştirir.
7. Konum ve güven skorlarını hesaplar.
8. Önizlemeleri yükler ve sonuçları veritabanına kaydeder.

## 10. Güvenlik ve belediye iş akışı

- Mevcut şehir bazlı tenant izolasyonu korunur.
- Kullanıcı yalnızca yetkili olduğu şehrin videolarını arayabilir.
- Medya mevcut imzalı URL yapısıyla sunulur.
- Arama, onay, red ve olay oluşturma işlemleri denetim kaydına yazılır.
- SAM3 bulguları varsayılan olarak `inceleme bekliyor` durumunda başlar.
- Yüksek güven bile tek başına otomatik iş emri oluşturmaz.

## 11. Kalite ve değerlendirme

Pilot veri setinde hem pozitif hem zor negatif örnekler bulunmalıdır.

Pozitif örnekler:

- Çöp poşeti
- Yol kenarı çöpü
- Taşmış konteyner
- Kaçak döküm
- Moloz
- Terk edilmiş mobilya

Zor negatif örnekler:

- Yaprak yığını
- Kaya ve toprak
- Gölge
- İnşaat malzemesi
- Asfalt yaması
- Dolu fakat taşmamış konteyner

Raporlanacak metrikler:

- Bulgu precision ve recall
- Maske IoU/Dice
- Video başına yanlış alarm
- Gerçek olay başına mükerrer sonuç
- Arama tamamlanma süresi
- İnsan onay/red oranı
- Konum hatası; ölçülebiliyorsa metre cinsinden

Kesin başarı eşikleri ilk donanım ve pilot veri ölçümünden sonra dondurulacaktır.
MVP kabulü için sistemin yalnızca teknik olarak çalışması değil, belediye
personelinin inceleyebileceği düzeyde yanlış alarm üretmesi şarttır.

## 12. Uygulama aşamaları

### Aşama 0 — Teknik fizibilite ve lisans kontrolü

- SAM3 checkpoint erişimini ve kullanım lisansını doğrula.
- Hedef GPU'da tek kare, yüksek çözünürlüklü parça ve kısa video benchmark'ı yap.
- 50–100 temsilî drone klibinde `çöp` prompt paketini dene.
- Küçük nesne, açı ve çözünürlük sınırlarını raporla.
- Devam/uyarlama/alternatif model kararını ver.

**Çıkış kriteri:** Maliyet, hız ve temel kalite açısından pilot yapılabilirliği
kanıtlanmış olmalıdır.

### Aşama 1 — Üretim temeli

- Büyük videoyu API belleğine almayan presigned resumable multipart upload kur.
- `original`, `analysis_proxy` ve `dashboard_proxy` varlıklarını ayır.
- Ayrı GPU kuyruğuna lease/heartbeat, progress, cancel, retry ve idempotency ekle.
- Sürümü sabitlenmiş ayrı CUDA `sam3-worker` oluştur; modeli bir kez yükleyip
  warm-up yap ve GPU başına eşzamanlılığı sınırla.
- Model, prompt, eşik ve veri sürümünü sonuç manifestine kaydet.
- Dashboard proxy'sinde gerçek yüz/plaka redaksiyonu ve erişim denetimi uygula.

**Çıkış kriteri:** Kesilmiş veya tekrar başlayan upload devam edebilmeli; uzun
GPU işi ikinci kez sahiplenilmemeli; worker çöküp yeniden başladığında sonuç
kaybı veya mükerrer hit üretmemelidir.

### Aşama 2 — Offline MVP

- SAM3 model adaptörünü oluştur.
- `sam_visual_search` iş tipini ayrı GPU kuyruğuna ekle.
- Tek seçili yüklenmiş videoda arama çalıştır.
- `çöp` için kontrollü prompt paketini ekle.
- Bilinen sorguyu mevcut detection/frame indeksine, yeni sorguyu doğrudan pilot
  taramasına yönlendiren ilk query router'ı ekle.
- Maske, kutu, güven ve zaman kodunu sakla.
- Basit sonuç galerisi ve video zamanına gitme özelliğini ekle.
- Tam annotated video yerine istemci tarafında maske/kutu overlay'i çiz.

**Çıkış kriteri:** Kullanıcı seçili videoda `çöp` aratıp maskeli sonuçları
görebilmeli; sonuçlar olay oluşturmadan önce onaylanabilmelidir.

### Aşama 3 — Kalite ve belediye olayı entegrasyonu

- Zamansal takip ve mükerrer sonuç birleştirme ekle.
- Güven bantlarını kalibre et.
- Hard-negative veri döngüsünü kur.
- Onaylı bulgudan CityVision olayı ve iş emri oluştur.
- Kullanıcı geri bildirimlerini veri setine aktar.

**Çıkış kriteri:** Aynı fiziksel çöp alanı tek bulguya indirgenmeli ve onaylı
bulgu mevcut olay/iş emri akışına kontrollü biçimde girmelidir.

### Aşama 4 — Harita ve hedef GPS'i

- Telemetri alanlarını standartlaştır.
- Kamera/gimbal geometrisiyle yer projeksiyonunu uygula.
- Konum kalitesi ve hata tahmini ekle.
- Bulguları sonuç haritasında göster.

**Çıkış kriteri:** Her harita sonucu yaklaşık veya projekte konum olarak açıkça
etiketlenmeli; projekte konum doğruluğu saha örnekleriyle ölçülmelidir.

### Aşama 5 — Arşiv ölçekleme

- Uçuşlardan aranabilir görsel embedding kataloğu oluştur.
- Önce hızlı aday seçimi, sonra SAM3 doğrulaması uygula.
- Prompt ve video sonuçlarını önbelleğe al.
- Birden fazla uçuş ve tarih aralığında arama ekle.
- Kullanıcı/şehir kotası ve ayrıntılı maliyet tahmini ekle.

**Çıkış kriteri:** Kullanıcı şehir ve tarih aralığında arama yapabilmeli; sistem
tüm arşivi her sorguda baştan SAM3 ile taramamalıdır.

### Aşama 6 — Canlı uçuş modu

- Drone akışını veya kısa video segmentlerini gerçek zamanlı al.
- Aktif sorguları yeni segmentlere uygula.
- Sonuçları dashboard'a kademeli gönder.
- Bağlantı kesintisi, tekrar deneme ve edge/cloud çalışma kararlarını uygula.

**Çıkış kriteri:** Kullanıcı aktif uçuş boyunca bir sorgu başlatıp gecikmeli de
olsa yeni bulguları dashboard'da görebilmelidir.

## 13. İlk pilot kapsamı

İlk pilot bilinçli olarak dar tutulacaktır:

- Yalnızca yüklenmiş drone videosu
- Tek şehir ve seçili uçuş
- Tek üst sorgu: `çöp`
- Yönetilen prompt paketi
- Arka planda asenkron analiz
- Maskeli sonuç galerisi
- Video zamanına gitme
- İnsan onayı/red işlemi
- Otomatik iş emri yok
- Hedef GPS'i ilk aşamada yaklaşık olabilir

Pilot başarılı olduktan sonra `moloz`, `kaçak döküm`, `hasarlı yol`, `işgal`,
`terk edilmiş araç` gibi yeni sorgu paketleri eklenebilir.

## 14. Başlıca riskler ve önlemler

| Risk | Önlem |
| --- | --- |
| Drone görüntüsünde nesnelerin çok küçük olması | Yüksek çözünürlüklü parça işleme ve aday büyütme |
| `çöp` kavramının belirsiz olması | Yönetilen alt prompt paketi ve negatif örnekler |
| Çok fazla yanlış alarm | Güven kalibrasyonu, zamansal tekrar ve insan onayı |
| Arşiv taramasının yavaş/pahalı olması | Embedding ön araması, önbellek ve GPU kuyruğu |
| Aynı olayın birçok kez çıkması | Zamansal ve coğrafi birleştirme |
| Drone GPS'inin hedef konumu sanılması | Konum kalitesi alanı ve kamera projeksiyonu |
| Model veya checkpoint değişiminde sonuçların değişmesi | Model/prompt sürümünü her aramada saklama |
| Şehirler arası veri erişimi | Mevcut tenant ve rol kontrolünü tüm yeni tablolara uygulama |

## 15. Önerilen başlangıç kararı

İlk geliştirme hedefi şu olmalıdır:

> Belediye personeli seçili, daha önce yüklenmiş bir drone videosunda `çöp`
> araması başlatır; CityVision arka planda SAM3 ile tarama yapar ve maskeli,
> güven skorlu, zaman kodlu sonuçları insan incelemesine sunar.

Bu hedef doğrulandıktan sonra sırasıyla olay entegrasyonu, hedef GPS'i, arşiv
ölçekleme ve canlı uçuş moduna geçilir.
