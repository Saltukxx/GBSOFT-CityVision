# AI Class Taxonomy (MVP v1)

Durum: taslak — Gate 0’da kilitleyin.

## Tasarım kuralı

AI önce **görsel sınıf** üretir. Belediye olayı (violation / work order) AI + GPS + GIS + business rules ile üretilir.

## Model A — Drone Context Detection

| Class | Açıklama | MVP |
| ----- | -------- | --- |
| `person` | Yalnızca mahremiyet filtresi / hard-negative desteği | Yardımcı |
| `trash_container` | Çöp konteyneri (normal doluluk) | Evet |

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

## CVAT label listesi (kopyala-yapıştır)

```text
person
trash_container
overflowing_container
street_waste
pothole
road_crack
road_damage
manhole
```

## Mapping notu

COCO pretrained model `person` sınıfını mahremiyet ve hard-negative desteği için bootstrap eder.
`pothole` / waste sınıfları **kendi dataset’imizle** fine-tune gerektirir.
