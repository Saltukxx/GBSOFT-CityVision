# GBSoft CityVision — SAM3 Teknik Fizibilite ve Maliyet Analizi

**İnceleme tarihi:** 26 Ağustos 2026  
**Kapsam:** Mevcut CityVision deposu, SAM3/SAM3.1, video/GPU mimarisi,
ölçeklenebilirlik, lisans, KVKK, depolama, ağ, operasyon ve insan inceleme
maliyeti.

> Bu çalışma mühendislik kararı içindir; hukuk veya lisans görüşü değildir.
> Üretim sözleşmesi öncesinde model, veri seti ve üçüncü taraf yazılım lisansları
> hukuk birimi tarafından ayrıca onaylanmalıdır.

## 1. Yönetici özeti

SAM3 tabanlı görsel arama **teknik olarak yapılabilir**, ancak SAM3'ü bütün drone
arşivinin her karesinde doğrudan çalıştırmak önerilmez. En uygun sistem dört
kademeli hibrit mimaridir:

1. Bilinen sorgular (`çöp`, `taşmış konteyner`, `çukur`) önce mevcut CityVision
   tespitleri ve indeksinden aranır.
2. Yeni sorgularda ucuz bir text-image ön arama veya açık kelime dağarcıklı
   detector aday kare/parçaları seçer.
3. SAM3 yalnızca adaylarda tespit ve piksel maskesi üretir.
4. SAM3.1 video tracker yalnızca adayın çevresindeki kısa klipte sonucu takip
   eder; bütün uçuş boyunca açık bırakılmaz.

Bu tasarım:

- Bilinen sorgularda sonucu saniyeler içinde getirebilir.
- SAM3 GPU kullanımını aday oranıyla sınırlar.
- Maske kalitesi gereken yerde SAM3'ün avantajını korur.
- Model değiştirilebilirliğini ve lisans alternatiflerini açık tutar.

### Üretime geçmeden önce zorunlu kapılar

1. SAM lisansı ve mevcut Ultralytics kullanımının lisans durumu yazılı olarak
   onaylanmalıdır.
2. SAM3 ayrı CUDA GPU servisine çıkarılmalıdır; mevcut API container'ına
   eklenmemelidir.
3. İş kuyruğuna heartbeat/lease, progress, cancel, retry ve GPU concurrency
   kontrolü eklenmelidir.
4. Video yükleme tüm dosyayı RAM'e alan FastAPI yolundan çıkarılıp doğrudan
   nesne deposuna resumable multipart yüklemeye dönüştürülmelidir.
5. Drone koordinatı ile hedef koordinatı birbirinden ayrılmalıdır.
6. Arama sonuçlarını ve maskeleri saklayacak kalıcı veri modeli eklenmelidir.
7. Belediye görüntüleri için saklama-imha, erişim, yüz/plaka gizleme ve denetim
   politikası tamamlanmalıdır.

## 2. Doğrulanmış SAM3 gerçekleri

### 2.1 Model yapısı

- Resmî depo SAM3'ün detector ve tracker paylaşan bir vision encoder kullandığını
  ve modelin 848 milyon parametre olduğunu belirtiyor.
- Detector metin, geometri ve görsel örneklerle koşullanan DETR tabanlıdır.
- Tracker SAM2'nin transformer encoder-decoder yaklaşımını devralır.
- Resmî Hugging Face işlemcisi varsayılan olarak 1008 × 1008 giriş kullanır;
  farklı çözünürlüğün kaliteyi düşürebileceğini açıkça belirtir.
- Çıktı kutu, skor, instance maskesi ve semantic maskeyi içerebilir.
- Aynı görüntüde birden fazla prompt için vision embedding, aynı prompt'la çok
  görüntü için text embedding tekrar kullanılabilir. CityVision adaptörü bunu
  zorunlu optimizasyon olarak uygulamalıdır.

Kaynaklar:

- [SAM3 resmî deposu](https://github.com/facebookresearch/sam3)
- [SAM3 makalesi](https://arxiv.org/abs/2511.16719)
- [Hugging Face SAM3 dokümantasyonu](https://huggingface.co/docs/transformers/model_doc/sam3)

### 2.2 SAM3.1

SAM3.1, Object Multiplex ile çok nesneli takibi ortak bellek kovalarında toplar.
Resmî sürüm notu 128 nesnede tek H100 üzerinde eski SAM3 video yoluna göre
yaklaşık 7 kat hızlanma bildiriyor. Bu iyileştirme çok nesneli kısa klip takibi
için değerlidir; tek görüntü aramasını 7 kat hızlandırdığı anlamına gelmez.

Kaynak: [SAM3.1 sürüm notu](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md)

### 2.3 Ortam ve dağıtım

Resmî depo şu üretim önkoşullarını listeliyor:

- Python 3.12+
- PyTorch 2.7+
- CUDA 12.6+ uyumlu GPU
- Hız için opsiyonel FlashAttention 3 ve derlenmiş connected-components uzantısı
- Hugging Face checkpoint erişim onayı ve kimlik doğrulaması

Mevcut CityVision container'ı Python 3.11-slim ve genel `torch>=2.2` kullanıyor;
NVIDIA CUDA runtime içermiyor. Aynı ortamı zorla birleştirmek bağımlılık ve
dağıtım riskini artırır. Öneri, sürümü sabitlenmiş ayrı bir `sam3-worker`
container'ıdır.

### 2.4 Lisans

SAM3 Apache/MIT değildir; özel **SAM License** kullanır. Lisans kullanım,
değişiklik ve dağıtım için sınırlı haklar tanır; yeniden dağıtım şartları,
yaptırım/ticaret kontrolleri, sorumluluk ve lisans değişikliği hükümleri içerir.
GBSoft'un belediye hizmeti, müşteri ortamı, model ağırlığı dağıtımı ve destek
sözleşmesi özelinde hukuk onayı bir go/no-go kapısıdır.

Kaynak: [SAM License](https://github.com/facebookresearch/sam3/blob/main/LICENSE)

## 3. Mevcut CityVision teknik denetimi

### 3.1 Güçlü mevcut parçalar

- PostgreSQL/PostGIS olay ve coğrafi sorgu altyapısı var.
- S3/MinIO uyumlu nesne deposu soyutlaması var.
- Şehir/tenant ve rol bazlı erişim kontrolü var.
- İmzalı medya URL'leri var.
- Redis destekli arka plan iş yapısı var.
- Drone video + GPS sidecar yükleme ve merkezi analiz akışı var.
- Olay birleştirme, güven bantları, insan inceleme ve iş emri yapısı var.
- Mevcut taxonomy içinde `overflowing_container` ve `street_waste` bulunuyor.
- `infra-b-waste.pt` modeli mevcut.

Bu nedenle SAM3 için sıfırdan ürün kurulmayacak; yeni arama ve GPU katmanı
mevcut CityVision çekirdeğine bağlanacaktır.

### 3.2 Kritik eksikler ve etkileri

| Bulgu | Mevcut durum | Üretim etkisi | Gereken geliştirme |
| --- | --- | --- | --- |
| Sonuç tipi | `Detection` yalnız `bbox_xyxy` saklıyor | Maskeler kaybolur | Ayrı `VisualSearchHit` ve RLE/polygon alanları |
| Detection DB | `detections` tablosu yalnız sınıf başına toplam sayı saklıyor | Geçmişte kutu/kare araması yapılamaz | Kare/hit düzeyinde indeks |
| İş heartbeat'i | `running` iş 30 dk sonra başlangıç zamanına göre stale sayılıyor | Uzun SAM işi iki kez çalışabilir | Lease + heartbeat + owner token |
| GPU concurrency | Tek genel Redis kuyruğu; thread fallback var | Aynı GPU'da OOM ve yarış | Ayrı GPU kuyruğu, GPU başına concurrency=1 |
| Progress/cancel | Yok | Dashboard bekleme ve operasyon zayıf | Progress, cancel_requested, attempt, timeout |
| Video upload | Dosya `await file.read()` ile tamamen RAM'e alınıyor | GB düzeyinde video RAM'i tüketir | Presigned multipart/resumable upload |
| Upload limiti | Varsayılan 200 MB | Mevcut 4K kliplerin çoğu yüklenemez | Parçalı doğrudan object-store yükleme |
| Video analiz | Video bütünü GPU worker yereline indiriliyor | Ağ ve disk tekrarları | Aynı bölgede depolama, cache/range/proxy |
| Decode | OpenCV ile tek kare seri decode/inference | GPU aç kalabilir | FFmpeg/NVDEC + batch decode + prefetch |
| Annotated video | Her koşuda tam `annotated.mp4` üretiliyor | Depolama yaklaşık iki katına çıkar | Tarayıcıda canvas overlay; yalnız kanıt crop/clip |
| GPS | Detection'a drone GPS'i kopyalanıyor | Drone konumu hedef konumu sanılır | `platform_geom` ve `target_geom` ayrımı |
| DJI SRT | Mevcut parser yalnız lat/lon okuyor | Yer projeksiyonu yapılamaz | İrtifa, yaw/pitch/roll, gimbal, kamera kalibrasyonu |
| Mahremiyet | Sunum metninde yüz/plaka maskeleme var; çalışan pipeline'da bulunmadı | KVKK/erişim riski | Gerçek redaction ve retention hattı |
| Gözlemlenebilirlik | GPU süresi, frame/s, OOM, maliyet metriği yok | Kapasite ve fatura yönetilemez | Prometheus/OpenTelemetry ve job accounting |

### 3.3 Depodaki veri ve disk bulguları

İnceleme anındaki yerel veri:

- `outputs`: yaklaşık 51 GB
- `data`: yaklaşık 12 GB
- `models`: yaklaşık 438 MB
- `runs`: yaklaşık 617 MB

Çıktı alanının ham veriden çok daha büyük olmasının ana nedeni çok sayıda tam
annotated video kopyasıdır. Bazı tekil annotated videolar 1–1,6 GB'tır. SAM3
maskeleri için ayrıca tam video render etmek bu büyümeyi hızlandırır. Overlay'in
istemci tarafında çizilmesi birinci derece maliyet optimizasyonudur.

Depodaki 4K drone örnekleri yaklaşık 5–46 GB/saat aralığındadır. Aynı süre için
bitrate farkı çok yüksek olduğundan kapasite planı tek bir ortalamaya
dayandırılmamalı; uçuş başına gerçek bitrate kaydedilmelidir.

### 3.4 Mevcut çöp modelinin durumu

`models/infra-b-waste.pt`:

- YOLO detect modelidir; segmentasyon modeli değildir.
- Yalnız `overflowing_container` sınıfına sahiptir.
- Eğitim seti yaklaşık 6,6 bin train ve 6,6 bin validation görüntüsü içerir.
- Kaynak örnekler sabit/sokak kamerası perspektifindedir; drone/aerial değildir.
- `street_waste` için yerel/aerial eğitim verisi yoktur.

Dolayısıyla mevcut model sorgu yönlendirme ve aday üretme için yararlıdır fakat
drone görüntüsünde “her türlü çöp” doğruluğu varmış gibi kabul edilemez. Aerial
waste test seti ayrı hazırlanmalıdır.

### 3.5 Mevcut SAM3 pilotunun durumu

Depoda `.venv-sam3-pilot`, 3,44 GB float32 checkpoint ve
`scripts/pilot_sam3_labeling.py` bulunuyor; ana pipeline'a bağlı değildir.
Mevcut ortamda CUDA yok ve sandbox içinde MPS görünmüyor, bu nedenle anlamlı hız
benchmark'ı henüz yapılmamıştır.

Pilot script üretim veya kalite kararı için şu haliyle kullanılamaz:

1. `PROMPTS` değerleri string olduğu halde ikinci döngü string karakterlerini
   tek tek prompt olarak çalıştırıyor.
2. Her prompt'ta görüntüyü yeniden encode ederek en pahalı işlemi tekrarlıyor.
3. Float32 kullanıyor; CUDA üretiminde BF16/AMP denemesi yapılmalı.
4. Yalnız kutu post-process yolunu çağırıyor; hedef olan instance maskeyi
   değerlendirmiyor.
5. Rastgele az sayıda, çoğu pozitif etiketli kare gerçek negatif precision ve
   flight-level false-positive ölçümü vermez.
6. Image ve video checkpoint/API uyumu açık bir model manifestiyle sabitlenmemiş.

Pilot yeniden yazılmalı; mevcut dosya benchmark kanıtı sayılmamalıdır.

## 4. Önerilen üretim mimarisi

### 4.1 Sorgu yönlendirici

Her kullanıcı sorgusu aynı pahalı yola gitmemelidir.

```text
Kullanıcı sorgusu
       |
       v
Normalize et + belediye taxonomy'sine eşle
       |
       +-- Bilinen sınıf? -------------------------------+
       |                                                 |
       |     Mevcut hit/event/frame indeksini sorgula    |
       |                    |                            |
       |                    v                            |
       |          SAM3 ile seçili aday maskesi           |
       |                                                 |
       +-- Yeni/açık sorgu? -----------------------------+
             |
             v
     Tile tabanlı text-image/open-vocab ön arama
             |
             v
       En iyi adaylarda SAM3
             |
             v
     Kısa klipte SAM3.1 takip + dedupe
```

### Yol A — Bilinen sorgu

Örnek: `çöp`, `taşmış konteyner`, `çukur`.

1. Sorgu taxonomy sınıfına eşlenir.
2. Önceden üretilmiş frame/hit indeksinden adaylar getirilir.
3. Kullanıcı yalnız kutu isterse sonuç anında gösterilir.
4. Maske isterse SAM3 yalnız seçilen aday crop/karelerinde çalışır.

Bu yol en düşük maliyetli ve en öngörülebilir yoldur.

### Yol B — Yeni sorgu

Örnek: `terk edilmiş kanepe`, `inşaat molozu`.

1. Kullanıcı sorgusu basit noun-phrase prompt paketine dönüştürülür.
2. Global kare yerine yüksek çözünürlüklü tile kataloğu aranır.
3. İlk K aday SAM3 ile doğrulanır.
4. Adayın çevresindeki kısa zaman penceresi SAM3.1 ile takip edilir.
5. Aynı fiziksel bulgu prompt, kare ve uçuşlar arasında birleştirilir.

### Yol C — Hiç aday bulunamadığında kontrollü geniş tarama

Kullanıcı “derin tarama” seçerse veya kalite denetimi gerekiyorsa sistem seçili
videoyu 0,5–1 FPS ve tile stratejisiyle tarar. İş başlamadan önce tahmini süre ve
maliyet gösterilir. Bu yol varsayılan değildir.

### 4.2 Model servisi

SAM3 ana FastAPI sürecine kütüphane olarak gömülmemelidir.

Önerilen `sam3-worker` özellikleri:

- Python/CUDA/PyTorch sürümleri tam pinli ayrı image
- Model başlangıçta bir kez yüklenir ve warm-up yapılır
- GPU başına varsayılan concurrency `1`
- Kontrollü frame micro-batching
- BF16/AMP; FP32 yalnız doğrulama karşılaştırması
- `torch.inference_mode()`
- Desteklenen donanımda `torch.compile`
- Aynı karede vision embedding cache
- Aynı prompt paketinde text embedding cache
- Prompt başına ayrı vision encode yapılmaz
- OOM durumunda batch azaltma; işi iki kez paralel başlatmama
- Model, processor, CUDA image ve prompt pack sürüm manifesti
- Health, readiness ve GPU memory metrikleri
- Checkpoint erişim token'ı secret manager'da; log/payload içinde değil

### 4.3 İş kuyruğu

Yeni GPU iş modeli:

- `queue`: `cityvision:gpu:sam3`
- `lease_owner`: worker UUID
- `lease_expires_at`: heartbeat ile uzatılır
- `heartbeat_at`
- `progress_current`, `progress_total`, `stage`
- `attempt`, `max_attempts`, `next_retry_at`
- `cancel_requested_at`
- `idempotency_key`
- `resource_seconds`, `gpu_type`, `peak_vram_mb`

İdempotency anahtarı en az şu bileşenlerden üretilir:

```text
video_sha256
model_manifest_version
prompt_pack_version
sampling_and_tile_config
threshold_profile
```

Aynı iş tekrar istenirse mevcut sonuç döndürülür. Kullanıcı prompt yazımını
değiştirip aynı normalize pakete ulaşıyorsa gereksiz tarama yapılmaz.

### 4.4 Video ingest ve proxy stratejisi

### Yükleme

- API dosya byte'larını RAM'e almamalı.
- Uploader object-store için presigned multipart URL almalı.
- 16–64 MB parçalar, checksum ve resumable state kullanılmalı.
- Tamamlanan multipart upload sonrası API yalnız metadata ve object key almalı.
- Aynı checksum yeniden yüklenmemeli.

### Video türevleri

Her uçuş için üç farklı varlık düşünülmelidir:

1. `original`: delil/yeniden işleme için, kısa veya mevzuata uygun retention
2. `analysis_proxy`: model için görsel kaliteyi koruyan, standart codec/bitrate
3. `dashboard_proxy`: hızlı seek ve kullanıcı oynatması için

Tek proxy'nin hem küçük nesne analizi hem düşük bant genişlikli dashboard için
uygun olacağı varsayılmamalıdır. Aerial küçük nesne benchmark'ı sonrası profile
karar verilmelidir.

### Decode

- FFmpeg ile zaman damgalı frame extraction
- GPU ortamında NVDEC denenmeli
- Decode, preprocess ve inference pipeline halinde örtüştürülmeli
- Sabit 1 FPS yerine hareket/sahne değişimine göre adaptive sampling denenmeli
- Aday çevresinde daha yüksek temporal density kullanılmalı

### 4.5 Çözünürlük ve tile tasarımı

SAM3 1008 kare giriş için tasarlanmıştır. 3840 × 2160 drone karesini tek seferde
1008'e küçültmek yaklaşık 3,8 kat lineer küçülme yaratır; küçük atıklar
kaybolabilir.

Önerilen üç profil:

| Profil | Kullanım | Yaklaşım |
| --- | --- | --- |
| `fast` | İlk keşif | 0,5 FPS, tam kare, 1008 |
| `balanced` | Varsayılan | 1 FPS tam kare + adaylarda tile |
| `deep` | Kontrollü denetim | 0,5–1 FPS, yaklaşık 15 örtüşen tile |

Tile sınırındaki tekrarlar mask IoU/NMS ile birleştirilir. Minimum görünür nesne
boyutu piksel cinsinden veri setinde raporlanmalı; recall bu boyut dilimlerine
göre ölçülmelidir.

### 4.6 Arama indeksi

İlk MVP'de ayrı vector DB şart değildir. PostgreSQL'de frame metadata ve object
key tutulup aday seçimi basit taxonomy üzerinden yapılabilir.

Arşiv ölçeğinde:

- Metinle görsel arama için CLIP/SigLIP türü language-aligned embedding gerekir.
- DINOv3 doğrudan text-image araması değildir; görsel örnekle benzerlik, clustering
  ve aktif öğrenme için kullanılabilir.
- Global frame embedding küçük çöpleri kaçırabilir; tile embedding gerekir.
- PostgreSQL + pgvector ilk tercih olabilir; operasyonel ihtiyaç aşarsa ayrı
  vector store değerlendirilir.
- Embedding model/sürümü indeks kaydında tutulmalıdır.

### 4.7 Sonuç ve maske saklama

Veritabanında:

- Bbox
- Düşük çözünürlüklü RLE veya polygon
- Score ve threshold profile
- Frame/timecode
- Prompt/prompt-pack/model sürümü
- Review state
- Platform ve hedef konumu
- Dedupe group

tutulur. Tam mask veya maskeli PNG object store'da tutulabilir. Her kare için
tam çözünürlüklü PNG maske saklamak gereksizdir.

Dashboard tam annotated video istemez. Orijinal/proxy video üzerinde bbox ve
RLE maske canvas/WebGL ile çizilir. Yalnız onaylı olay için kısa evidence clip
ve preview render edilir.

### 4.8 Drone hedef koordinatı

Yeni veri modeli iki ayrı geometri taşımalıdır:

- `platform_geom`: drone'un konumu
- `target_geom`: görüntüdeki hedefin tahmini yer konumu

Ek alanlar:

- Altitude türü: relative, AGL, MSL
- Aircraft yaw/pitch/roll
- Gimbal yaw/pitch/roll
- Kamera intrinsics ve distortion
- Timestamp synchronization error
- Projection method ve estimated error radius

İlk sürüm `target_geom=NULL`, `location_quality=platform_approximate` dönebilir.
Mevcut event fusion içinde drone koordinatının hedef koordinatı gibi kullanılması
engellenmelidir. Gerçek projeksiyon düz zemin ray intersection ile başlar;
oblique/engebeli arazi için DEM veya ortofoto gerekir.

### 4.9 Mahremiyet ve güvenlik

- Orijinal medya en dar role açılmalı.
- Dashboard proxy ve thumbnail üretiminden önce yüz/plaka redaction uygulanmalı.
- Redaction başarısızlığı için örneklem denetimi yapılmalı.
- Arama sorguları, medya görüntüleme ve export işlemleri audit log'a girmeli.
- Belediye/şehir verileri tenant bazında object-key prefix ve DB RLS ile ayrılmalı.
- Veri saklama ve periyodik imha politikası teknik job olarak uygulanmalı.
- Model üçüncü taraf inference API'sine belediye görüntüsü göndermemeli; aksi
  halde veri aktarımı ve sözleşme ayrıca değerlendirilmelidir.
- İnsan onayı olmadan kişi aleyhine otomatik idari sonuç üretilmemelidir.

KVKK Kurumu yapay zekâ sistemlerinde insan merkezli, şeffaf, denetlenebilir ve
mahremiyet odaklı yaklaşımı vurguluyor. Kaynaklar:

- [Yapay Zekâ Alanında Kişisel Verilerin Korunmasına Dair Tavsiyeler](https://www.kvkk.gov.tr/Icerik/7048/Yapay-Zeka-Alaninda-Kisisel-Verilerin-Korunmasina-Dair-Tavsiyeler)
- [Kişisel verilerin silinmesi/yok edilmesi/anonimleştirilmesi](https://www.kvkk.gov.tr/Icerik/2038/kisisel-verilerin-silinmesi-yok-edilmesi-veya-anonim-hale-getirilmesi)

## 5. Maliyet modeli

Tüm fiyatlar 26 Ağustos 2026 tarihindeki kamuya açık liste fiyatlarıdır; vergi,
kur, disk, ağ, destek, rezervasyon ve bölge farkları dahil değildir.

### 5.1 GPU liste fiyatı referansı

Runpod Secure Cloud sayfasındaki örnek saatlik fiyatlar:

| GPU | VRAM | USD/GPU-saat | 100 saat/ay | 730 saat açık |
| --- | ---: | ---: | ---: | ---: |
| L4 | 24 GB | 0,49 | 49 | 358 |
| L40S | 48 GB | 0,99 | 99 | 723 |
| H100 PCIe | 80 GB | 2,89 | 289 | 2.110 |
| H200 | 141 GB | 4,59 | 459 | 3.351 |

Kaynak: [Runpod GPU fiyatları](https://www.runpod.io/pricing)

Bu tablo yalnız kapasite referansıdır. SAM3'ün her GPU'da çalışacağı veya aynı
verimi vereceği varsayılmaz. Özellikle 24/48 GB kartlarda gerçek VRAM ve batch
benchmark'ı yapılmalıdır.

### 5.2 Teorik SAM3 tarama hesabı

Formül:

```text
encoder_passes = video_seconds × sample_fps × tiles_per_frame
gpu_hours = encoder_passes × measured_seconds_per_pass / 3600
compute_cost = gpu_hours × provider_hourly_price
```

SAM3 makalesi tek görüntü için H200 üzerinde 30 ms bildiriyor. Bu, veri decode,
tile üretimi, upload/download, job startup ve bizim aerial verimiz dahil olmayan
**teorik alt sınırdır**.

30 dakikalık 4K video için H200 alt sınırı:

| Profil | Encoder pass | Teorik GPU süresi | H200 teorik maliyet | 2–5× planlama bandı |
| --- | ---: | ---: | ---: | ---: |
| 1 FPS, tek tam kare | 1.800 | 0,9 dk | 0,07 USD | 0,14–0,34 USD |
| 0,5 FPS, 15 tile | 13.500 | 6,75 dk | 0,52 USD | 1,03–2,58 USD |
| 1 FPS, 15 tile | 27.000 | 13,5 dk | 1,03 USD | 2,07–5,16 USD |
| 30 FPS, 15 tile | 810.000 | 6,75 saat | 30,98 USD | 61,96–154,91 USD |

Son satır tam kare hızlı video tracker'ın gerçek uygulama şekli değildir; tüm
kareleri bağımsız, tüm tile'larda taramanın neden yasaklanması gerektiğini
gösteren üst maliyet senaryosudur.

### En büyük maliyet azaltıcılar

1. Bilinen sorguda mevcut hit indeksini kullanmak
2. SAM3'ü yalnız aday kare/crop'a uygulamak
3. Vision embedding'i promptlar arasında paylaşmak
4. Text embedding'i kareler arasında paylaşmak
5. Aday çevresinde kısa tracker penceresi kullanmak
6. Kullanılmayan GPU'yu kapatmak/serverless worker
7. Decode/preprocess ile GPU inference'ı pipeline etmek
8. Sonuç cache/idempotency

### 5.3 Depolama

Yerel örneklerde gözlenen video oranı yaklaşık 5–46 GB/uçuş-saatidir.

Cloudflare R2 Standard liste fiyatı 0,015 USD/GB-ay ve doğrudan R2 egress'i
ücretsizdir. Bu yalnız karşılaştırma referansıdır; belediye veri yerleşimi ve
sözleşmesi ayrıca değerlendirilmelidir.

| Arşiv | 5 GB/saat | 12 GB/saat | 46 GB/saat |
| --- | ---: | ---: | ---: |
| 100 uçuş-saati | 7,5 USD/ay | 18 USD/ay | 69 USD/ay |
| 1.000 uçuş-saati | 75 USD/ay | 180 USD/ay | 690 USD/ay |

Kaynak: [Cloudflare R2 fiyatlandırması](https://developers.cloudflare.com/r2/pricing/)

Tam annotated video üretmek bu tutarı yaklaşık ikiye katlayabilir. Proxy,
retention ve yalnız evidence clip üretimi depolama maliyetinde GPU
optimizasyonundan daha büyük tasarruf sağlayabilir.

### 5.4 Ağ ve upload

4K drone videosu yüksek bitrate'te 20–46 GB/saat olabilir. 20 Mbps gerçek uplink
ile 20 GB yüklemek ideal koşulda yaklaşık 2,2 saat sürer. Bu nedenle:

- Drone/dock ile merkez arasında resumable transfer şarttır.
- Analiz proxy'si edge'de üretilebilir, fakat küçük atık kalitesi benchmark ile
  doğrulanmalıdır.
- Object store ile GPU farklı bulutlarda ise egress maliyeti GPU maliyetini
  aşabilir.
- GPU worker ve sıcak video cache aynı bölge/provider'da tutulmalıdır.

### 5.5 İnsan inceleme maliyeti

Üretimde en pahalı kalem GPU değil, yanlış alarm incelemesi olabilir.

```text
review_hours = flight_hours × hits_per_flight_hour × seconds_per_hit / 3600
```

Örnek: 1.000 uçuş-saati, saat başına 50 sonuç ve sonuç başına 15 saniye inceleme
yaklaşık 208 personel-saatidir. Bu yüzden yalnız mAP değil:

- Flight-hour başına yanlış alarm
- İlk 20 sonuçta precision
- Aynı olay için mükerrer sonuç
- Sonuç başına ortalama inceleme süresi

ürün kabul metrikleri olmalıdır.

### 5.6 Mühendislik eforu

Aşağıdaki bant tek deneyimli CV/backend mühendisi eşdeğeri içindir; frontend,
DevOps, veri etiketleme ve hukuk paralel destekleri ayrıca planlanmalıdır.

| Paket | Tahmini efor |
| --- | ---: |
| Lisans + CUDA benchmark spike | 1–2 kişi-hafta |
| GPU job/lease/progress altyapısı | 2–3 kişi-hafta |
| Resumable upload + proxy/video katalog | 2–4 kişi-hafta |
| Offline SAM3 arama MVP | 3–5 kişi-hafta |
| Dashboard review ve olay bağlantısı | 2–4 kişi-hafta |
| Aerial kalite seti ve kalibrasyon | 2–4 kişi-hafta + etiketleme |
| Hedef GPS projeksiyonu | 4–8 kişi-hafta |
| Arşiv embedding ve ölçekleme | 4–8 kişi-hafta |
| Canlı uçuş modu | 6–12 kişi-hafta |

Offline, güvenli ve ölçülebilir MVP için gerçekçi toplam bant yaklaşık 8–14
kişi-haftadır. Doğrudan “SAM3 endpoint'i eklemek” daha kısa görünür ama GPU
yarışları, GB video yükleme, veri kaybı ve yanlış GPS nedeniyle üretim MVP'si
sayılmaz.

### 5.7 Bulut mu şirket içi GPU mu?

### Bulut/on-demand önerilir, eğer:

- Pilot ve kullanım düzensizse
- Aylık GPU süresi birkaç yüz saatin altındaysa
- Model/donanım benchmark'ı henüz sabit değilse
- Hızla L40S/H100/H200 karşılaştırması gerekiyorsa

### Şirket içi/dedicated değerlendirilebilir, eğer:

- Veri yerleşimi bulutu kısıtlıyorsa
- GPU sürekli yüksek dolulukla çalışacaksa
- Çok şehirli üretim hacmi tahmin edilebiliyorsa
- Elektrik, soğutma, yedek parça, sürücü ve nöbet operasyonu karşılanabiliyorsa

Satın alma kararı pilot benchmark'tan önce verilmemelidir. Basit eşik:

```text
cloud_monthly = measured_gpu_hours × hourly_price
on_prem_monthly = amortization + electricity + cooling + operations + downtime
```

## 6. Alternatif mimariler

| Seçenek | Açık sorgu | Maske | Hız/maliyet | Lisans/operasyon | Öneri |
| --- | --- | --- | --- | --- | --- |
| SAM3 doğrudan tüm arşiv | Güçlü | Var | En pahalı | Özel SAM lisansı, ağır CUDA | Kullanma |
| Örnekleme/tile + SAM3 | Güçlü | Var | Pilot için kabul edilebilir | GPU servisi gerekir | MVP benchmark |
| Mevcut YOLO/RF-DETR → SAM3 | Bilinen sınıflar | Var | En ucuz | Mevcut lisanslar gözden geçirilmeli | Varsayılan bilinen sorgu |
| Text-image tile retrieval → SAM3 | Yeni sorgular | Var | Arşivde dengeli | Ek embedding index | Hedef üretim mimarisi |
| Grounding DINO → SAM2 | Güçlü/modüler | Var | Benchmark gerekli | Kod/checkpoint lisansları ayrı doğrulanmalı | SAM3 fallback/karşılaştırma |
| Custom YOLO-Seg | Kapalı sınıf | Var | En hızlı üretim | Maske verisi ve lisans kararı | Yüksek hacimli sabit sınıflar |

Grounding DINO kodu ve SAM2 resmî modeli Apache-2.0 olarak yayımlanmıştır; yine
de her checkpoint ve dataset lisansı ayrıca doğrulanmalıdır.

Kaynaklar:

- [Grounding DINO lisansı](https://github.com/IDEA-Research/GroundingDINO/blob/main/LICENSE)
- [SAM2 resmî deposu ve lisansı](https://github.com/facebookresearch/sam2)

## 7. Lisans ve bağımlılık riski

Mevcut CityVision `ultralytics` paketine ve ondan üretilmiş ağırlıklara dayanıyor.
Ultralytics'in güncel lisans açıklaması kapalı kaynak ticari/internal kullanım,
SaaS ve embedded dağıtım için Enterprise lisans gerektiğini; aksi durumda
AGPL-3.0 yükümlülüklerini belirtiyor.

Kaynak: [Ultralytics lisans açıklaması](https://www.ultralytics.com/license)

Bu, SAM3 projesinden bağımsız mevcut bir ürün riskidir. Teknik planın `P0`
maddesi olmalıdır:

1. GBSoft ürününün dağıtım biçimini hukukla sınıflandır.
2. Ultralytics Enterprise teklifini al veya permissive runtime/model geçişini
   planla.
3. Her model ağırlığı ve her dataset için SBOM/model-card lisans kaydı tut.
4. SAM3, Grounding DINO, SAM2 ve embedding modelini aynı şekilde envantere al.

## 8. Kalite planı

### 8.1 Aerial waste gold set

Mevcut GarbageOverflow seti drone domainini temsil etmiyor. Yeni test seti:

- En az 10 farklı uçuş/gün/saat
- Nadir ve yoğun çöp alanları
- Nadir negatif uçuşlar
- Gölge, yaprak, taş, moloz, araç yükü, konteyner, yol yaması gibi hard negative
- Nadir/oblique açı, farklı yükseklik, 4K ve proxy kalite karşılaştırması
- Uçuş bazlı train/validation/test ayrımı
- Kutu + instance polygon + görünür minimum piksel boyutu

Başlangıç hedefi:

- 150–300 benzersiz pozitif waste instance
- 500+ hard-negative tile
- En az 3 tamamen negatif uçuş

Bu sayılar eğitim hedefi değil, fizibilite/eşik kalibrasyonu için başlangıçtır.

### 8.2 Geçici kabul hedefleri

Belediye ile pilot öncesi onaylanmak üzere:

- Event-level recall: görünür minimum boyut üstünde ≥ %70
- Review queue precision: ≥ %80
- Precision@20: ≥ %85
- Yanlış alarm: ≤ 3 / uçuş-saat
- Mükerrerlik: gerçek olay başına ≤ 1,2 hit
- Mask IoU: ≥ 0,60 veya sınır yerine alan ölçümü için onaylı Dice hedefi
- Offline balanced arama: hedef GPU'da video süresinden hızlı
- Job recovery: worker ölünce tekil ve idempotent devam
- Cross-city veri sızıntısı: 0
- Otomatik iş emri: MVP'de 0

Eşikler model genel benchmark'ından değil aerial gold set sonuçlarından seçilir.

### 8.3 Deney matrisi

Her model için aynı uçuş split'i ve prompt paketi:

- SAM3 image
- SAM3.1 short video
- Grounding DINO + SAM2
- Mevcut waste YOLO + SAM3 crop
- Gerekirse custom YOLO-Seg

Her biri şu profillerde ölçülür:

- Full frame 1008
- 0,5 FPS ve 1 FPS
- 4K tile
- Original ve analysis proxy
- FP32/BF16
- L40S/H100/H200 mümkün olan alt küme

Rapor yalnız kalite değil `USD/uçuş-saat`, `GPU-s/uçuş-saat`, peak VRAM ve
review-minute/uçuş-saat içermelidir.

## 9. Önceliklendirilmiş teknik backlog

### P0 — Go/no-go önkoşulları

- [ ] SAM ve Ultralytics lisans değerlendirmesi
- [ ] Aerial waste gold set oluşturma
- [ ] Pilot script'i doğru mask/embedding cache/BF16 ile yeniden yazma
- [ ] L40S, H100 ve varsa H200 benchmark'ı
- [ ] Original/proxy küçük nesne kalite testi
- [ ] Hedef GPS için mevcut telemetri alan envanteri
- [ ] KVKK saklama, erişim ve imha kararı

### P1 — Platform sağlamlaştırma

- [ ] GPU'ya özel Redis kuyruğu
- [ ] Lease/heartbeat/progress/cancel/retry/idempotency
- [ ] Ayrı CUDA `sam3-worker` image
- [ ] Presigned resumable multipart video upload
- [ ] Analysis/dashboard proxy üretimi
- [ ] Temp/cache cleanup ve disk quota
- [ ] GPU/job maliyet metrikleri

### P2 — Offline MVP

- [ ] `visual_searches`, `visual_search_hits`, `visual_query_templates`
- [ ] Bilinen sorgu router'ı
- [ ] `çöp` prompt paketi
- [ ] Balanced sampling + tile fallback
- [ ] SAM3 mask sonucu ve RLE/polygon
- [ ] Zamansal/prompt dedupe
- [ ] Sonuç galerisi, video seek ve review
- [ ] Onaylı hit → mevcut event akışı
- [ ] Canvas overlay; tam annotated video yok

### P3 — Arşiv ölçekleme

- [ ] Frame/tile kataloğu
- [ ] SigLIP/CLIP aday indeksi
- [ ] pgvector fizibilitesi
- [ ] Cache ve maliyet önizlemesi
- [ ] Tarih/şehir/uçuş kapsamlı arama
- [ ] Kota, priority ve adil GPU scheduling

### P4 — Coğrafi doğruluk

- [ ] DJI telemetri parser genişletme
- [ ] Kamera/gimbal kalibrasyon kaydı
- [ ] Ray-ground projection
- [ ] DEM/ortofoto seçeneği
- [ ] Hedef konumu hata yarıçapı
- [ ] Event fusion'ı target geometry'ye taşıma

### P5 — Canlı uçuş

- [ ] Segment tabanlı canlı ingest
- [ ] Aktif sorgu state'i
- [ ] Kademeli dashboard sonuçları
- [ ] Edge/cloud partition ve bağlantı toleransı
- [ ] Canlı kapasite/SLA ve alarm yönetimi

## 10. Nihai teknik karar

Önerilen ilk ürün:

> Yüklenmiş bir drone videosunda, bilinen `çöp` taxonomy'sini önce mevcut hızlı
> detector/indeks ile adaylayan; SAM3'ü yalnız adaylarda maskeyi doğrulamak için
> kullanan; sonuçları insan incelemesine sunan offline görsel arama.

Önerilmeyen ilk ürün:

> Kullanıcının her serbest sorgusunda bütün 4K arşivi her kare ve her tile için
> SAM3 ile baştan tarayan sistem.

SAM3'ün gerçek değeri “her şeyi sürekli çalıştırmak” değil; açık sorguda aday
bulma, maske üretme, etiketleme hızlandırma ve kısa klip takibidir. Sabit ve
yüksek hacimli belediye sınıfları zamanla daha küçük özel detector/segmenter'a
distill edilmeli; SAM3 keşif ve öğretmen modeli olarak kalmalıdır.
