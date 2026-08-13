# GBSoft City Vision

## Yapay Zekâ Destekli Mobil Belediye Görüntü Analiz Platformu

**Doküman tipi:** Ürün + Teknik Geliştirme Yol Haritası
**Planlanan MVP süresi:** 24 hafta
**İlk saha hedefi:** 1 belediye, 1 güzergâh, 1–2 belediye otobüsü
**İlk ticari ürün kapsamı:** Yol bozukluğu + çöp + durak/yol işgali + trafik analizi

---

# 1. Yönetici Özeti

GBSoft City Vision'ın amacı, belediye otobüsleri, zabıta araçları, çöp kamyonları ve diğer belediye araçlarına yerleştirilen kameraları **hareketli şehir sensörlerine** dönüştürmektir.

Sistem belediye aracının güzergâhı boyunca görüntüyü analiz ederek:

* yol çukuru,
* yol yüzeyi bozulması,
* taşmış çöp konteyneri,
* yol üzerindeki atık,
* otobüs durağı işgali,
* yanlış park adayı,
* ikinci sıra park,
* yaya geçidi işgali,
* engelli rampası işgali,
* trafik yoğunluğu,
* bozuk/deforme tabela,
* yol çizgisi bozulması,
* potansiyel sokak lambası arızası

gibi olayları otomatik olarak tespit eder.

Her olay:

**görüntü + olay tipi + zaman + GPS koordinatı + güven skoru + araç/kamera bilgisi**

ile merkezi sisteme gönderilir.

Backend aynı problemi farklı araçların tekrar görmesi durumunda bunları birleştirir ve belediye personeline:

> “Aynı çukur üç farklı belediye aracı tarafından son 24 saat içinde tespit edildi.”

şeklinde tek bir operasyonel olay sunar.

Amaç yalnızca görüntü tanıyan bir AI modeli geliştirmek değildir.

Amaç:

> **Şehrin fiziksel durumunu sürekli tarayan ve belediyenin operasyon sistemine otomatik iş emri üreten bir platform geliştirmektir.**

---

# 2. Ürün Vizyonu

Uzun vadeli ürün:

**City Vision Platform**

olmalıdır.

Temel mimari:

```text
BELEDİYE ARACI
        │
        ▼
KAMERA + GPS + IMU
        │
        ▼
EDGE AI
        │
        ├── Object Detection
        ├── Segmentation
        ├── Tracking
        ├── OCR / ANPR
        └── Scene Analysis
        │
        ▼
LOCAL EVENT ENGINE
        │
        ▼
4G / 5G
        │
        ▼
GBSOFT CITY VISION CLOUD
        │
        ├── Event Fusion
        ├── GIS Engine
        ├── Duplicate Detection
        ├── Evidence Management
        ├── AI Confidence Engine
        └── Historical Analysis
        │
        ▼
BELEDİYE OPERASYON PLATFORMU
        │
        ├── Zabıta
        ├── Fen İşleri
        ├── Temizlik
        ├── Ulaşım
        └── Beyaz Masa
```

---

# 3. En Önemli Ürün Prensibi

Sistemi:

> “Her şeyi tanıyan tek bir AI modeli”

şeklinde geliştirmemek gerekir.

Doğru yaklaşım:

```text
AI detection
+
tracking
+
GPS
+
GIS
+
business rules
+
historical observations
=
municipal event
```

olmalıdır.

Örneğin AI yalnızca:

> “otomobil”

tespit eder.

Ancak:

> “Bu otomobil otobüs durağını işgal ediyor.”

kararının verilebilmesi için:

* aracın konumu,
* otobüs durağının GIS alanı,
* aracın o alanla geometrik kesişimi,
* görüntü güven skoru,
* gerekiyorsa tekrar gözlem

birlikte değerlendirilmelidir.

---

# 4. İlk MVP Kapsamı

İlk sürümde **12 farklı problemi aynı anda çözmeye çalışılmamalıdır.**

MVP dört modülden oluşmalıdır.

### Modül 1 — Pothole AI

Tespit:

* çukur,
* büyük asfalt kırığı,
* yüzey deformasyonu.

Çıktı:

```text
POTHOLE-000187

Location:
39.xxxxx / 41.xxxxx

Severity:
Medium

Confidence:
94%

Observed:
3 times

First observation:
12.08.2026 09:14

Last observation:
12.08.2026 16:37
```

---

### Modül 2 — Waste AI

Tespit:

* taşmış konteyner,
* konteyner dışında çöp,
* yol kenarı atık yığını.

---

### Modül 3 — Bus Stop Obstruction

Tespit:

* durak alanındaki araçlar,
* durak önünü kapatan araçlar.

İlk sürümde sistem bunu:

**“Potential Bus Stop Violation”**

olarak üretmelidir.

Otomatik trafik cezası sistemi olarak tasarlanmamalıdır.

---

### Modül 4 — Traffic Analytics

Tespit:

* otomobil,
* otobüs,
* minibüs,
* kamyon,
* motosiklet.

Üretilecek KPI'lar:

* araç/dakika,
* araç/saat,
* araç sınıfı dağılımı,
* tahmini yoğunluk,
* trafik kuyruğu,
* güzergâh yoğunluk değişimi.

---

# 5. Faz 0 — Ürün Gereksinimleri

## Süre

**1 hafta**

## Yapılacaklar

İlk belediye pilotu için resmi ürün gereksinimleri oluşturulacaktır.

Her detection sınıfı için tanım hazırlanmalıdır.

Örneğin:

### Pothole

```text
Class:
pothole

Minimum visible size:
defined

Occlusion policy:
defined

Severity:
low / medium / high

Required confidence:
defined
```

### Overflowing Trash

```text
container
trash
overflowing_container
street_waste
```

gibi class taxonomy oluşturulmalıdır.

## Teslimatlar

* Product Requirement Document
* AI class taxonomy
* event taxonomy
* pilot route specification
* hardware requirements
* success metrics
* labeling guideline v1

## Gate 0

Kodlamaya başlamadan önce:

**“Model tam olarak neyi tespit edecek?”**

sorusunun bütün sınıflar için cevaplanmış olması gerekir.

---

# 6. Faz 1 — Computer Vision Prototype

## Süre

**Hafta 2–4**

## Amaç

Laptop üzerinde çalışan ilk görüntü analiz pipeline'ının oluşturulması.

## Teknoloji

* Python
* OpenCV
* PyTorch
* YOLO-compatible object detection
* Git
* Docker

OpenCV'nin güncel dokümantasyonunda görüntü işleme, video I/O, kalibrasyon ve tracking için temel modüller bulunuyor.

## İlk pipeline

```text
MP4
 │
 ▼
OpenCV
 │
 ▼
Frame
 │
 ▼
Object Detector
 │
 ▼
Bounding boxes
 │
 ▼
Tracker
 │
 ▼
Object IDs
 │
 ▼
JSON events
```

Örnek:

```json
{
  "frame": 4281,
  "timestamp": "14:22:31.120",
  "class": "car",
  "confidence": 0.94,
  "track_id": 182
}
```

## Acceptance Criteria

Sistem:

* MP4 video okuyabilmeli,
* araçları tespit edebilmeli,
* videoda takip edebilmeli,
* detection sonuçlarını JSON'a yazabilmeli,
* görüntü üzerine bbox çizebilmeli.

Ultralytics'in güncel tracking altyapısı BoT-SORT ve ByteTrack ile video boyunca nesne kimliği koruyabiliyor ve modeller TensorRT gibi deployment formatlarına aktarılabiliyor.

---

# 7. Faz 2 — Veri Toplama Altyapısı

## Süre

**Hafta 3–6**

AI projesinin en kritik varlığı model değil:

# Dataset

olacaktır.

İlk aşamada Erzurum veya pilot belediyede:

**minimum 30–50 saat şehir videosu**

toplanması hedeflenmelidir.

Farklı koşullar özellikle kaydedilmelidir:

* sabah,
* öğle,
* akşam,
* gece,
* güneş,
* yağmur,
* kar,
* gölge,
* trafik yoğunluğu,
* boş yol.

### Özellikle Erzurum gibi şehirlerde

Dataset'e mutlaka:

* karla kaplı yol,
* eriyen kar,
* buz,
* çamur,
* yol üzerindeki gölge,
* asfalt yamaları

eklenmelidir.

Aksi halde model asfalt yamasını çukur olarak algılayabilir.

---

# 8. Annotation Platformu

Önerilen başlangıç:

**CVAT**

CVAT görüntü ve video annotation'ı yanında detection, segmentation ve tracking tabanlı AI-assisted annotation mekanizmaları sunuyor.

Class yapısı:

```text
vehicle
car
bus
truck
motorcycle

pothole
road_crack

trash_container
overflowing_container
street_waste

bus_stop
traffic_sign
crosswalk
```

## İlk dataset hedefi

### MVP

Yaklaşık:

**10.000–20.000 kaliteli annotated frame**

hedeflenmelidir.

Ancak sayıdan daha önemli olan:

**dataset çeşitliliğidir.**

---

# 9. Faz 3 — Model Training

## Süre

**Hafta 5–9**

Tek model yerine iki temel model kullanılması önerilir.

### Model A — General Object Detection

```text
car
bus
truck
motorcycle
person
trash_container
traffic_sign
```

### Model B — Infrastructure Segmentation / Detection

```text
pothole
road_damage
trash
overflow
road_marking
```

Segmentation özellikle:

* çukur,
* çatlak,
* yol hasarı

gibi geometrisi önemli olan olaylarda kullanılmalıdır.

---

# 10. Model Evaluation

Sadece:

**accuracy**

raporlanmamalıdır.

Her class için:

* Precision
* Recall
* F1
* mAP
* false positives/km
* false negatives/km

ölçülmelidir.

Fakat belediye ürünü açısından en önemli KPI:

### False events per route

olmalıdır.

Örneğin:

```text
20 km route

Real potholes: 22

Detected:
20

False detections:
3
```

bu belediyenin anlayacağı performans ölçüsüdür.

---

# 11. Faz 4 — Tracking Engine

## Süre

**Hafta 8–10**

Object detection'dan sonra tracking eklenir.

Önerilen ilk seçenekler:

**ByteTrack**

veya

**BoT-SORT**

Ultralytics her iki tracker'ı da mevcut video/live-stream tracking modunda destekliyor.

Amaç:

```text
car detected
```

yerine:

```text
car #172
car #173
car #174
```

üretmektir.

Tracking sayesinde:

* araç sayımı,
* aynı aracın tekrar sayılmaması,
* zone duration,
* line crossing,
* durak işgali

hesaplanabilir.

---

# 12. Faz 5 — GPS ve Kamera Senkronizasyonu

## Süre

**Hafta 9–11**

Her frame aşağıdaki bilgilerle ilişkilendirilmelidir:

```text
timestamp
latitude
longitude
speed
heading
camera_id
vehicle_id
```

Örnek:

```json
{
  "timestamp": "2026-08-12T14:32:18.320",
  "bus_id": "BUS-17",
  "camera": "FRONT",
  "latitude": 39.92183,
  "longitude": 41.27192,
  "speed": 31.4,
  "heading": 182
}
```

Kamera saati ve GPS saatinin senkronizasyonu zorunlu kabul edilmelidir.

---

# 13. Faz 6 — GIS Engine

## Süre

**Hafta 10–13**

Önerilen altyapı:

**PostgreSQL + PostGIS**

GIS verileri:

```text
bus_stops
roads
crosswalks
parking_zones
disabled_ramps
containers
street_lights
traffic_signs
```

olarak tutulur.

---

# 14. Geofence Engine

Örneğin:

```text
BUS_STOP_187
```

için gerçek dünya polygonu tanımlanır.

AI araç tespit eder.

GIS Engine:

```text
vehicle_position ∈ BUS_STOP_187
```

kontrolü gerçekleştirir.

Sonuç:

```text
Potential Bus Stop Obstruction
```

oluşturulur.

Bu, saf computer vision yerine:

**AI + spatial intelligence**

yaklaşımıdır.

---

# 15. Faz 7 — Event Fusion Engine

## Süre

**Hafta 12–15**

Bence platformun en önemli fikri burasıdır.

Örneğin üç otobüs:

```text
BUS 4
Pothole
39.91814 / 41.27318

BUS 7
Pothole
39.91816 / 41.27313

BUS 11
Pothole
39.91811 / 41.27321
```

tespit ediyor.

Sistem bunları üç ayrı olay olarak göstermemelidir.

### Event Fusion

çıktısı:

```text
POTHOLE #881

Observations:
3

Confidence:
VERY HIGH

First seen:
07:14

Last seen:
17:21
```

olmalıdır.

PostGIS'teki `ST_ClusterDBSCAN` gibi spatial clustering fonksiyonları yakın geometrileri belirli mesafe kriterlerine göre gruplamaya imkan veriyor ve bu katmanda kullanılabilir.

---

# 16. Event Confidence Engine

Confidence yalnızca neural-network confidence olmamalıdır.

Örneğin:

```text
AI confidence        0.87
GPS confidence       0.95
Repeat observation   +0.10
Second bus detected  +0.10
```

birlikte değerlendirilmelidir.

Sonuç:

```text
EVENT CONFIDENCE
97%
```

olabilir.

Önerilen seviyeler:

```text
<70%       discard/archive
70–85%     manual review
85–95%     probable
>95%       high confidence
```

İlk pilot sonrası eşikler gerçek saha verisine göre kalibre edilmelidir.

---

# 17. Faz 8 — Evidence Engine

Her olay için bütün video saklanmamalıdır.

Önerilen olay paketi:

```text
event.jpg

object_crop.jpg

before.mp4
event.mp4
after.mp4

event.json
```

Örneğin:

**5 saniye önce + 5 saniye olay + 5 saniye sonra**

saklanabilir.

Bu hem:

* bandwidth,
* storage,
* KVKK,
* operatör inceleme

açısından daha yönetilebilir bir mimari oluşturur.

NVIDIA DeepStream, Jetson/dGPU tabanlı streaming analytics pipeline'ları, tracking ve edge inference için güncel NVIDIA platformlarından biridir.

---

# 18. Faz 9 — Edge Hardware Prototype

## Süre

**Hafta 12–16**

İlk AR-GE:

**Laptop üzerinde**

yapılmalıdır.

Saha aşamasında:

### Önerilen pilot

**NVIDIA Jetson Orin NX**

değerlendirilebilir.

NVIDIA'nın güncel ürün sayfasına göre Orin NX ailesi 8/16 GB seçeneklerinde ve konfigürasyona bağlı olarak **157 TOPS'a kadar AI performansı** sunuyor.

Başlangıç prototipi için:

**Jetson Orin Nano**

da yeterli olabilir.

NVIDIA'nın güncel Orin Nano platformu 67 TOPS'a kadar AI performansı sunuyor.

---

# 19. Araç Donanım Mimarisi

Pilot:

```text
                BUS

       FRONT CAMERA
             │
             │
       RIGHT CAMERA
             │
             ▼
       EDGE COMPUTER
             │
      ┌──────┼──────┐
      │      │      │
     GPS    SSD    4G/5G
      │
      ▼
   CLOUD
```

### Kamera 1

Ön yön:

* pothole,
* road,
* traffic,
* crosswalk.

### Kamera 2

Sağ yön:

* parking,
* bus stop,
* trash,
* sidewalk,
* signs.

---

# 20. Donanım Seçim Kriterleri

Production sisteminde tüketici tipi GoPro yerine otomotiv/endüstriyel kamera düşünülmelidir.

Aranacak özellikler:

* 1080p veya üstü,
* yüksek dynamic range,
* düşük ışık performansı,
* sağlam bağlantı,
* titreşim dayanımı,
* IP koruma,
* kontrollü exposure,
* bilinen lens karakteristiği.

Pilot aşamasında daha düşük maliyetli kamera kullanılabilir.

---

# 21. Faz 10 — Backend

## Süre

**Hafta 14–18**

Önerilen yapı:

```text
FastAPI / similar API
        │
PostgreSQL
        │
PostGIS
        │
Object Storage
        │
Redis
        │
Background workers
```

Temel tablolar:

```text
vehicles
cameras
routes
detections
observations
events
event_media
assets
zones
users
work_orders
model_versions
```

---

# 22. Event Data Model

```json
{
  "event_id": "POT-18222",
  "type": "pothole",
  "lat": 39.91821,
  "lon": 41.27311,
  "severity": "medium",
  "confidence": 0.96,
  "first_seen": "...",
  "last_seen": "...",
  "observations": 4,
  "model_version": "pothole-1.2.4"
}
```

Model versiyonunun olayla birlikte kaydedilmesi zorunlu tutulmalıdır.

---

# 23. Faz 11 — Belediye Dashboard

## Süre

**Hafta 16–20**

Ana ekran:

```text
TODAY

Potholes             137
Waste                 31
Bus stop violations   18
Traffic incidents      9
```

Harita:

🔴 kritik
🟠 yüksek
🟡 orta
🟢 çözüldü

---

# 24. Olay İnceleme Ekranı

Örnek:

## POTHOLE #18221

**Atatürk Caddesi**

Detection confidence:

**96%**

Detected by:

**BUS-17**

Observed:

**4 times**

### Actions

**[Doğru]**

**[Yanlış Tespit]**

**[İş Emri Oluştur]**

**[Fen İşlerine Gönder]**

**[Çözüldü]**

---

# 25. Human-in-the-Loop

İlk üretim sürümünde AI'nın kararları insan tarafından doğrulanmalıdır.

Her:

**Doğru**

ve

**Yanlış**

seçimi training datasına dönmelidir.

Bu:

# Active Learning Loop

oluşturur.

```text
AI
 ↓
Detection
 ↓
Municipal employee
 ↓
Correct / Wrong
 ↓
Dataset
 ↓
Retraining
 ↓
Better AI
```

Bu mekanizma zaman içerisinde City Vision'ın her şehir için adaptasyonunu sağlar.

---

# 26. Faz 12 — MLOps

## Süre

**Hafta 17–21**

Production AI sisteminde:

```text
model_final.pt
model_final2.pt
model_final_real.pt
```

gibi dosya yönetimi kesinlikle kullanılmamalıdır.

Model registry kurulmalıdır.

Örneğin:

**MLflow**

Model Registry; model lineage, versioning, aliases ve metadata yönetimi için merkezi model store sağlayabiliyor.

Örnek:

```text
pothole-model

v1.0
v1.1
v1.2

PRODUCTION → v1.1
STAGING    → v1.2
```

Her detection:

```text
model_version = 1.1
```

bilgisi içermelidir.

---

# 27. Model Deployment Pipeline

```text
Dataset
   │
   ▼
Training
   │
   ▼
Evaluation
   │
   ▼
Model Registry
   │
   ▼
Staging
   │
   ▼
Shadow Test
   │
   ▼
Production
   │
   ▼
Jetson Fleet
```

Rollback desteklenmelidir.

Örneğin:

```text
Model v1.4
false positive increased

ROLLBACK

Model v1.3
```

---

# 28. Faz 13 — İlk Saha Pilotu

## Süre

**Hafta 20–24**

İlk test:

### 1 belediye

### 1 güzergâh

### 1–2 otobüs

### 2 kamera/araç

### 30 gün

---

# 29. Pilot Ölçümleri

Her gün:

```text
km driven
hours recorded
AI events
verified events
false positives
false negatives
duplicate events
GPS errors
upload volume
edge CPU/GPU usage
temperature
```

ölçülmelidir.

---

# 30. Pilot KPI'ları

İlk ticari pilot için önerilen hedefler:

| KPI                    | Pilot hedefi |
| ---------------------- | -----------: |
| Pothole precision      |        > %90 |
| Pothole recall         |        > %85 |
| Waste precision        |        > %85 |
| Duplicate event rate   |        < %10 |
| GPS olay hatası        |       < 10 m |
| Dashboard availability |        > %99 |
| Event upload latency   |      < 60 sn |
| Manuel inceleme        | < 15 sn/olay |

Bunlar başlangıç ürün hedefleridir; saha verisi geldikçe yeniden kalibre edilmelidir.

---

# 31. Modelin Bilmediğini Bilmesi

AI'nın zorla karar vermesi engellenmelidir.

Örneğin:

```text
Confidence: 54%
```

ise:

```text
UNKNOWN
```

olarak sınıflandırılmalıdır.

**Yanlış belediye iş emri üretmek**, bazı olayları kaçırmaktan operasyonel olarak daha pahalı olabilir.

Bu nedenle precision ve confidence calibration özellikle önemlidir.

---

# 32. Parking Detection — Phase II

Park modülü ikinci aşamada geliştirilmelidir.

Pipeline:

```text
vehicle detection
        │
        ▼
tracking
        │
        ▼
ANPR
        │
        ▼
GPS
        │
        ▼
parking-zone intersection
        │
        ▼
repeat observation
        │
        ▼
candidate violation
```

Otobüs hareket halinde olduğu için ilk observation:

```text
Possible violation
```

olmalıdır.

---

# 33. Cross-Bus Confirmation

Örnek:

```text
14:01
BUS-7
25 ABC 123
BUS_STOP_42
```

↓

```text
14:08
BUS-18
25 ABC 123
BUS_STOP_42
```

↓

Backend:

```text
Same plate
Same zone
7 minutes difference
```

↓

```text
HIGH CONFIDENCE
PARKING EVENT
```

Bu, sabit kamera olmadan bile güçlü bir doğrulama mekanizması oluşturabilir.

---

# 34. EDS Ayrımı

City Vision'ın ilk ticari versiyonunda:

> “otomatik trafik cezası sistemi”

iddiası yapılmamalıdır.

2918 sayılı Kanun Ek-16 kapsamında EDS için Emniyet Genel Müdürlüğü tarafından ayrıca uygulama usul ve teknik gereklilik dokümanları yayımlanmaktadır.

Bu nedenle mimari:

```text
AI Detection
       ↓
Candidate Violation
       ↓
Authorized Review
```

olarak başlamalıdır.

EDS entegrasyonu ayrı bir ürün/regülasyon projesi olarak ele alınmalıdır.

---

# 35. KVKK Mimarisi

Privacy sonradan eklenen bir özellik olmamalıdır.

Başlangıçtan itibaren:

### Edge processing

tercih edilmelidir.

Mümkün olduğunca bütün görüntüyü sunucuya göndermek yerine:

```text
event crop
+
short evidence clip
+
metadata
```

gönderilmelidir.

KVKK'nın kamera kullanımına ilişkin güncel rehberinde amaç belirleme, veri minimizasyonu ve işlenen kişisel verinin amaçla sınırlı tutulması özellikle vurgulanmaktadır.

---

# 36. Privacy by Design

Sistemde:

* retention policy,
* role-based access,
* audit log,
* encryption,
* face masking,
* plate masking,
* event-only storage

özellikleri bulunmalıdır.

Örneğin:

### Normal dashboard

```text
25 *** ***
```

### Yetkili zabıta kullanıcısı

```text
25 ABC 123
```

şeklinde erişim tasarlanabilir.

---

# 37. Lisans Riski

Commercial product geliştirmeden önce AI framework lisansları incelenmelidir.

Ultralytics güncel lisans açıklamasında proprietary/closed-source ve ticari kullanımlar için Enterprise lisansını belirtirken, alternatif olarak AGPL-3.0 koşullarının uygulanabileceğini açıklıyor.

Dolayısıyla production başlamadan önce:

**Ultralytics lisansı satın alma**

veya

**daha uygun lisanslı model stack'i kullanma**

kararı verilmelidir.

Bu karar kod mimarisini değiştirebileceği için en geç MVP sonunda verilmelidir.

---

# 38. Takım Yapısı

İdeal ilk ekip:

### 1 × Computer Vision / ML Engineer

Sorumluluk:

* dataset,
* training,
* evaluation,
* deployment.

### 1 × Backend Engineer

Sorumluluk:

* API,
* PostGIS,
* Event Engine,
* event fusion.

### 1 × Frontend / Mobile Engineer

Sorumluluk:

* dashboard,
* map,
* review UI.

### 1 × Embedded / Edge Engineer

İlk aşamada part-time olabilir.

Sorumluluk:

* cameras,
* Jetson,
* networking,
* GPS,
* vehicle installation.

### 1 × Product Owner

Belediye süreçlerini ve AI ekibini bağlar.

---

# 39. Minimum Ekip

Eğer ekip küçükse:

```text
1 Full-stack developer
1 AI/Computer Vision engineer
```

ile MVP çıkarılabilir.

Ancak saha pilotunda:

**embedded + hardware**

konusunda dış destek alınmalıdır.

---

# 40. 24 Haftalık Master Roadmap

| Hafta | İş                      |
| ----- | ----------------------- |
| 1     | PRD + class definitions |
| 2     | OpenCV pipeline         |
| 3     | Base object detection   |
| 4     | Tracking prototype      |
| 3–6   | Dataset collection      |
| 4–7   | Annotation              |
| 5–9   | Model training          |
| 8–10  | Tracking engine         |
| 9–11  | GPS integration         |
| 10–13 | PostGIS / GIS           |
| 12–15 | Event Fusion            |
| 12–16 | Jetson prototype        |
| 14–18 | Backend                 |
| 16–20 | Dashboard               |
| 17–21 | MLOps                   |
| 18–21 | Vehicle installation    |
| 20–24 | Live municipal pilot    |

---

# 41. Development Milestones

## Milestone 1 — Week 4

### Video AI Demo

Video yüklenir.

Sistem araçları algılar.

---

## Milestone 2 — Week 8

### Pothole AI

Gerçek şehir videosundan çukur bulur.

---

## Milestone 3 — Week 12

### Geo AI

Her detection haritada görünür.

---

## Milestone 4 — Week 15

### City Event Engine

Duplicate olayları birleştirir.

---

## Milestone 5 — Week 18

### Edge AI

Jetson üzerinde çalışır.

---

## Milestone 6 — Week 20

### Belediye Dashboard

Operatör gerçek olayları görür.

---

## Milestone 7 — Week 24

# LIVE PILOT

Gerçek belediye otobüsü şehirde dolaşır.

AI:

```text
Potholes      48
Waste         11
Bus stop       6
Traffic        ...
```

oluşturur.

---

# 42. Pilot Sonrası Phase II

Pilot doğrulanınca:

### Parking AI

### Crosswalk AI

### Disabled Ramp AI

### Double Parking AI

eklenir.

---

# 43. Phase III

Sonraki modüller:

### Road Marking AI

Silinmiş:

* yaya geçidi,
* şerit,
* dur çizgisi.

### Sign AI

* kırılmış tabela,
* eğilmiş tabela,
* kapatılmış tabela.

### Streetlight AI

Gece belediye araçlarından:

* çalışan,
* çalışmayan

sokak lambalarının tespiti.

---

# 44. Phase IV — City Digital Twin

Uzun vadede ürün:

```text
CITY
 │
 ├── Roads
 ├── Waste
 ├── Traffic
 ├── Signs
 ├── Lights
 ├── Parking
 └── Infrastructure
```

üzerinden sürekli güncellenen bir:

# Urban Condition Map

oluşturmalıdır.

Her yolun:

```text
Road Health Score
```

değeri üretilebilir.

Örneğin:

**Atatürk Caddesi: 82/100**

**Cumhuriyet Caddesi: 54/100**

---

# 45. Prediction Katmanı

Yeterli tarihsel veri oluştuktan sonra sistem sadece:

> “çukur var”

demek yerine:

> “Bu yol segmentinin önümüzdeki 3 ay içinde bakım ihtiyacı yüksek.”

tahmini yapabilir.

Burada artık computer vision'dan:

# Predictive Municipal Maintenance

seviyesine geçilmiş olur.

---

# 46. City Vision'ın Rekabet Avantajı

GBSoft açısından moat yalnızca YOLO modeli değildir.

YOLO yerine yarın başka bir model kullanılabilir.

Asıl teknolojik değer:

### 1. Belediye dataset'i

### 2. GIS entegrasyonu

### 3. Event Fusion Engine

### 4. Municipal workflow entegrasyonu

### 5. Historical city data

### 6. Active learning feedback

### 7. Multi-camera / multi-vehicle observations

olacaktır.

Rakip aynı AI modelini indirebilir.

Fakat:

**3 yıllık şehir veri setini indiremez.**

---

# 47. Ürünün Satış Cümlesi

City Vision'ın belediyeye anlatımı:

> **“Mevcut belediye araçlarınızı şehrin tamamını sürekli tarayan yapay zekâ sensörlerine dönüştürüyoruz.”**

Ardından:

> “Yeni saha personeli çıkarmadan, zaten şehirde gezen otobüs, çöp kamyonu ve zabıta araçlarından şehrin sorunlarını otomatik tespit ediyoruz.”

Bu teknik özellik anlatmaktan daha güçlü bir değer önerisidir.

---

# 48. İlk Demo İçin Kesin Kapsam

İlk demo kesinlikle şu dört ekranla sınırlandırılmalıdır:

### 1 — Live Route

Otobüs güzergâhı.

### 2 — AI Detection

Kamera görüntüsü üzerinde detection.

### 3 — City Event Map

Bulunan problemler.

### 4 — Event Detail

```text
Problem:
Pothole

Confidence:
96%

Location:
...

Observed:
3 times

[Create Work Order]
```

Bu dört ekran çalışan halde olduğunda proje artık yalnızca AI deneyi değil:

# Belediye ürünü

haline gelir.

---

# 49. İlk 30 Günlük Uygulama Planı

## Hafta 1

* Python environment
* OpenCV
* Git repository
* Docker environment
* video processing
* YOLO prototype

## Hafta 2

* vehicle detection
* tracking
* traffic counting
* JSON event output

## Hafta 3

* saha videosu çekimi
* CVAT kurulumu
* pothole annotation
* waste annotation

## Hafta 4

* ilk pothole model training
* inference
* evaluation
* demo video

### 30. gün hedefi:

Bir Erzurum/belediye yol videosu sisteme verildiğinde:

```text
POTHOLE
CAR
BUS
TRASH
```

algılayıp ekranda göstermesi.

---

# 50. 60 Günlük Hedef

```text
Video
+
GPS
+
AI
```

birleştirilmiş olmalı.

Haritada:

```text
🔴 pothole
🟠 trash
🟡 obstruction
```

görülmeli.

---

# 51. 90 Günlük Hedef

Bir araç gerçek şehirde hareket ederken:

**kamera → edge AI → GPS → backend → dashboard**

zinciri çalışmalıdır.

---

# 52. 180 Günlük Hedef

Bir belediyede gerçek pilot:

```text
1–2 buses
2 cameras / bus
City Vision Edge
City Vision Cloud
City Vision Dashboard
```

çalışıyor olmalıdır.

Ve yönetim ekranında:

> **“Bu ay yapay zekâ tarafından 2.418 şehir problemi tespit edildi; 1.976'sı doğrulandı, 1.302'si çözüldü.”**

gibi gerçek operasyon KPI'ları gösterilebilmelidir.

---

# Sonuç

Bu projenin geliştirme stratejisi:

**AI model yapmak**

değil,

# AI + GIS + Edge + Belediye Operasyon Platformu

oluşturmak olmalıdır.

İlk altı ayın amacı kusursuz ve onlarca problemi tespit eden bir sistem geliştirmek değildir.

Amaç:

> **Tek bir belediye otobüsünü yapay zekâ destekli şehir tarama aracına dönüştürmek; araç şehirde dolaşırken yol çukuru, çöp, durak işgali ve trafik durumunu otomatik tespit ederek harita üzerinde gerçek belediye iş akışına dönüştürmek.**

Bu çalıştığı anda altyapı ikinci, üçüncü ve dördüncü use-case'leri eklemek için hazır olacaktır.
