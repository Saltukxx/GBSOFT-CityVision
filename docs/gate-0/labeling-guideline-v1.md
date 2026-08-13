# Labeling Guideline v1

Annotator’lar için kısa kural seti. Şüphede **atlayın** veya `hard_negative` notu düşünün; yanlış pozitif dataset’i zehirler.

## Genel

1. Her nesne için sıkı bbox: nesneyi tam sar, fazla boşluk bırakma.  
2. Occlusion > %50 ise yalnızca net sınıf görünüyorsa işaretle.  
3. Gece / yağmur / kar: aynı kurallar; silüet yeterince net değilse işaretleme.  
4. Frame aralığı: video’da her frame değil; net görünen keyframeler + track tutarlılığı.  
5. Asfalt yaması, gölge, rögar, buz birikintisi **pothole değildir**.

## Sınıf kuralları

### Vehicles (`car` / `bus` / `truck` / `motorcycle`)

- Araç büyük ölçüde görünür olmalı.  
- Park / hareket fark etmez.  
- Römorklu araçlarda ana gövdeyi etiketle.

### `pothole`

- Kavite / malzeme kaybı zorunlu.  
- Sadece renk farkı veya yama → **etiketleme**.  
- Severity alanını ayrı attribute olarak işaretle (low/medium/high) — CVAT attribute.

### `road_crack` / `road_damage`

- Çatlak: uzun lineer kırık.  
- Damage: çukur olmayan bozulma (çakıl dökülmesi, çökme).  
- İkisini aynı anda kullanma; baskın olanı seç.

### `trash_container` vs `overflowing_container`

- Kapalı / taşmamış → `trash_container`  
- Ağzından taşan belirgin atık → `overflowing_container`  
- İkisini aynı nesneye koyma.

### `street_waste`

- Yığın / torba grubu.  
- Tek küçük ambalajı yok say (min size sonra kalibre).

### `bus_stop`

- Fiziksel durak (işaret + sığınak).  
- “Durak alanı işgali” event’i annotation değildir; GIS sonra bağlanır.

## Kalite kontrol

- Her batch’te %10 dual-review  
- Anlaşmazlık → taxonomy’ye örnek ekle  
- Erzurum özel: kar / yama / çamur hard-negative örnekleri zorunlu

## Çıktı formatı

CVAT export: COCO veya YOLO txt. Proje varsayılanı: **YOLO** (class id = `configs/classes.yaml` sırası).
