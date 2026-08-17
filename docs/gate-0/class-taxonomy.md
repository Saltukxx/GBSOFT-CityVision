# AI Class Taxonomy (MVP v1)

Durum: taslak — Gate 0’da kilitleyin.

## Tasarım kuralı

AI önce **görsel sınıf** üretir. Belediye olayı (violation / work order) AI + GPS + GIS + business rules ile üretilir.

## Model A — General Object Detection

| Class | Açıklama | MVP |
| ----- | -------- | --- |
| `car` | Binek otomobil | Evet |
| `bus` | Belediye / yolcu otobüsü | Evet |
| `truck` | Kamyon / kamyonet (büyük ticari) | Evet |
| `motorcycle` | Motosiklet / scooter | Evet |
| `person` | Yaya | Trafik KPI opsiyonel |
| `trash_container` | Çöp konteyneri (normal doluluk) | Evet |
| `traffic_sign` | Trafik / yön tabelası | Phase II hazırlığı |
| `bus_stop` | Fiziksel durak yapısı (varsa) | Destekleyici |

## Model B — Infrastructure

| Class | Açıklama | Tip | MVP |
| ----- | -------- | --- | --- |
| `pothole` | Yol çukuru | bbox veya mask | Evet |
| `road_crack` | Belirgin asfalt çatlağı / kırık | bbox veya mask | Evet |
| `road_damage` | Genel yüzey deformasyonu (çukur değil) | mask tercih | Evet |
| `manhole` | Rögar kapağı (çukur değil; **iş emri değil**) | bbox | Görsel evet / event hayır |
| `overflowing_container` | Taşmış konteyner | bbox | Evet |
| `street_waste` | Yol/kaldırımda atık yığını | bbox | Evet |

## Sınıf tanımları (Gate 0 zorunlu)

### `pothole`

```text
Class: pothole
Positive: asfaltta çukur, malzeme kaybı, kenarı belirgin kavite
Negative: asfalt yaması, gölge, eriyen kar birikintisi, rögar kapağı (`manhole`), hız kesici
Minimum visible size: frame genişliğinin ~0.5%+ (pilot sonrası kalibre)
Occlusion: >50% kapalıysa label opsiyonel / low confidence
Severity:
  low    — sığ, tek tekerlek rahatsızlığı
  medium — belirgin kavite
  high   — geniş/derin, araç hasarı riski
Required confidence (event): >= 0.85 (ilk varsayılan)
```

### `manhole`

```text
Class: manhole
Positive: yol yüzeyindeki rögar / menhol kapağı (yuvarlak veya kare)
Negative: çukur (kavite), asfalt yaması, hız kesici
Note: çukur ile karışmasın diye ayrı sınıf; sağlam kapak iş emri değildir.
Pipeline: manhole kutusu annotated videoda durur; event_classes içinde yoktur.
Pothole ile IoU örtüşürse pothole düşer (rögar çukur yazmasın).
```

### `overflowing_container`

```text
Class: overflowing_container
Positive: konteyner ağzından taşan / kapak kapanmayan belirgin atık
Negative: yanındaki torba yokken dolu ama taşmamış konteyner → trash_container
```

### `street_waste`

```text
Class: street_waste
Positive: yol kenarı / kaldırımda birikmiş atık yığını
Negative: tek yaprak, küçük ambalaj (min size kalibre edilecek)
```

### Bus stop obstruction (event, class değil — MVP kapalı)

```text
AI üretir: car|bus|truck|motorcycle (+ track)
GIS üretir: vehicle_position ∈ BUS_STOP_zone
Event: potential_bus_stop_obstruction
Motor durur; geofence varsayılan kapalı. Drone durak işgali MVP değil.
İlk sürüm otomatik ceza DEĞİL.
```

## CVAT label listesi (kopyala-yapıştır)

```text
car
bus
truck
motorcycle
person
trash_container
overflowing_container
street_waste
pothole
road_crack
road_damage
manhole
bus_stop
traffic_sign
```

## Mapping notu

COCO pretrained modeller `car/bus/truck/motorcycle/person` ile bootstrap eder.
`pothole` / waste sınıfları **kendi dataset’imizle** fine-tune gerektirir.
