# Labeling Guideline v1

Annotator’lar için kısa kural seti. Şüphede **atlayın** veya `hard_negative` notu düşünün; yanlış pozitif dataset’i zehirler.

## Genel

1. Her nesne için sıkı bbox: nesneyi tam sar, fazla boşluk bırakma.  
2. Occlusion > %50 ise yalnızca net sınıf görünüyorsa işaretle.  
3. Gece / yağmur / kar: aynı kurallar; silüet yeterince net değilse işaretleme.  
4. Frame aralığı: video’da her frame değil; net görünen keyframeler + track tutarlılığı.  
5. Asfalt yaması, gölge, buz birikintisi **pothole değildir**. Rögar kapağı `manhole`.

## Nadir vs eğik kare

Aynı koridor iki bakış üretir; etiket kuralları değişmez, görünürlük değişir.

| Bakış | Ne beklenir | Dikkat |
| ----- | ----------- | ------ |
| **Nadir** (kuşbakışı, yüksek) | Sokak geometrisi, büyük yama / açık kavite | Küçük çukur kaybolur; rögar daire gibi görünür |
| **Eğik / alçak** | Çukur kenarı, çatlak dokusu, taşmış konteyner | Rögar RDD modellerinde `pothole` olur — **her zaman `manhole`** |

Rögar, her iki bakışta da **pothole hard-negative**: kapak görünüyorsa `manhole` kutula, çukur kutusu koyma (kayıp kapak + açık kavite hariç).

## Sınıf kuralları

### `pothole`

- Kavite / malzeme kaybı zorunlu.  
- Sadece renk farkı veya yama → **etiketleme**.  
- Rögar kapağı → `manhole`, `pothole` değil.
- Severity alanını ayrı attribute olarak işaretle (low/medium/high) — CVAT attribute.

### `manhole`

- Yuvarlak / kare kapak, menteşe, ızgara deseni.
- Kapak çukurun içinde olsa bile baskın nesne kapaksa `manhole`.
- Kayıp kapak + açık kavite → `pothole` (veya ikisini ayrı kutula).

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

## Kalite kontrol

- Her batch’te %10 dual-review  
- Anlaşmazlık → taxonomy’ye örnek ekle  
- Erzurum özel: kar / yama / çamur hard-negative örnekleri zorunlu

## Çıktı formatı

CVAT export: COCO veya YOLO txt. Proje varsayılanı: **YOLO** (class id = `configs/classes.yaml` sırası).
