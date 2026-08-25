# Aerial Model B ölçümleri

Her ölçüm `scripts/eval_aerial.py` ile alınır ve buraya JSON olarak yazılır:

```bash
.venv/bin/python scripts/eval_aerial.py --split test --device mps --tag <isim>
.venv/bin/python scripts/eval_aerial.py --split val  --device mps --tag <isim> \
    --baseline docs/eval/baseline-aerial-v1.val.json
```

## Bölmeler

| split | kaynak | not |
| --- | --- | --- |
| test | `clip3` (tamamı) | hold-out; eğitime hiç girmez |
| val | her klibin zaman kuyruğu (son %20) | klip bazlı, komşu kare sızıntısı yok |
| train | kalan kareler | nadir sınıf kareleri 5x kopyalanır |

## baseline-aerial-v1 (17 Ağu 2026)

`models/infra-b-road-aerial.pt` — 218 el etiketiyle, eski karışık bölmeyle eğitilen ilk ağırlık.

| split | mAP50 | manhole R | pothole mAP50 | road_crack mAP50 | road_damage mAP50 |
| --- | --- | --- | --- | --- | --- |
| test (clip3, 12 kare) | 0.993 | 0.959 | yok | yok | yok |
| val (39 kare) | 0.547 | 1.000 | 0.335 | 0.165 | 0.694 |

**Bu sayılar iyimser.** Ağırlık, bölme kuralları değişmeden önce eğitildiği için bugünün val ve
test karelerinin bir kısmını eğitimde görmüş durumda. Yani gerçek başlangıç noktası bundan
daha kötü; sonraki ağırlıklar temiz bir hold-out üzerinde ölçülecek ve karşılaştırma bu yönde
baseline'ın lehine kayacak.

İkinci sınırlama: `clip3` yalnız 19 rögar kutusu içeriyor, çukur ve çatlak örneği yok. Bu yüzden
hold-out şu an sadece rögar tarafını ölçebiliyor; `clip3`'ün 69 karesi tamamlanana kadar karar
`--split val` üzerinden verilir.

## aerial-v2 (17 Ağu 2026) — eşikleri tutmadı

`models/infra-b-road-aerial-v2.pt` — `yolov8s` @ 960, 180° rotasyon + flipud, klip bazlı temiz
bölme. 150 epoch istendi, patience 30 ile 71. epoch'ta durdu (en iyi ~41).

| split | mAP50 | manhole P/R | pothole mAP50 | road_crack mAP50 | road_damage mAP50 |
| --- | --- | --- | --- | --- | --- |
| val (39 kare, 99 kutu) | 0.185 | 0.51 / 0.44 | 0.003 | 0.000 | 0.290 |

Baseline'ın 0.547'siyle kıyaslanamaz: o sayı sızıntılı bölmede alınmıştı. Ama mutlak değerler
de kötü ve sebebi veri, yöntem değil — bu ağırlık **16 çatlak ve 39 çukur kutusuyla** eğitildi.
Model o iki sınıfı hiç öğrenemedi; doğrulama tarafında da yalnız 6 çatlak ve 3 çukur örneği var,
yani sayı istatistiksel olarak da anlamsız.

Çıkarım: mimari, augmentasyon ve bölme tarafında yapacak şey kalmadı; tek kaldıraç veri.
Bu ölçümden sonra el etiketleri 416 → 859 kutuya (çatlak 16 → 100, çukur 39 → 65) ve temiz kare
sayısı 1 → 141'e çıktı; üstelik 609 yeni 4K kare eklendi. Sonraki ağırlık bu veriyle ve
`--imgsz 1280` ile eğitilecek.

## aerial-v3 (17 Ağu 2026) — eşikleri tutmadı, ama v2'yi 3 kat geçti

`models/infra-b-road-aerial-v3.pt` — `yolov8s` @ 1280, 847 eğitim görüntüsü (1018 el kutusu),
180° rotasyon + flipud, klip bazlı bölme, temiz kareler %15 ile sınırlı. 100 epoch istendi,
`patience 25` ile **91. epoch'ta erken durdu** (en iyi epoch 66).

Eğitim 25. epoch'ta bir kez çöktü: PyTorch MPS'in boolean maske indeksleme hatası
(`docs/training-model-b.md`, MPS'in ikinci tuzağı). `last.pt`'den devam edildi, sonuç etkilenmedi.

### Üç ağırlık, aynı koşullar

Önceki karşılaştırmalar farklı bölme ve farklı çözünürlükte alındığı için kıyaslanamıyordu.
Bu tablo üçünü de **aynı** ayarla ölçüyor: `--split val --imgsz 1280 --conf 0.25 --iou 0.5`,
133 kare / 182 kutu.

| ağırlık | mAP50 | mAP50-95 | manhole P/R | pothole mAP50 | road_crack mAP50 | road_damage mAP50 |
| --- | --- | --- | --- | --- | --- | --- |
| v1 (`yolov8n`, sızıntılı bölme) | 0.284 | 0.127 | 0.57 / 0.78 | 0.330 | 0.000 | 0.180 |
| v2 (`yolov8s` @ 960) | 0.069 | 0.024 | 0.46 / 0.20 | 0.084 | 0.000 | 0.043 |
| **v3 (`yolov8s` @ 1280)** | **0.166** | **0.074** | **0.63 / 0.53** | 0.165 | 0.000 | 0.127 |

Okunuşu:

- **v2 → v3 gerçek bir kazanç:** her sınıfta 2-3 kat. Çözünürlük artışı, 2.5 kat veri ve temiz
  kare sınırı birlikte işe yaradı.
- **v1 hâlâ daha yüksek görünüyor ama bu sayı geçerli değil.** v1, klip bazlı bölme
  yazılmadan önce eğitildi, yani bugünün val karelerinin bir kısmı onun eğitim setinde. Bir
  modelin hold-out `clip3`'te 0.993 mAP50 alıp val'de 0.284'e düşmesi zaten bu sızıntının
  imzası. v1'i referans almak, kendi kopya çektiği sınavla karşılaştırmak olur.
- **`road_crack` üç modelde de tam 0.000.** 100 eğitim kutusu ve 17 val örneğiyle hiçbir
  yapılandırma bunu öğrenemez. Çatlak, sonraki etiketleme turunun birinci hedefi.
- v3 üçünün **en hassas** modeli (rögar P 0.63, hasar P 0.52) ama duyarlılığı düşük (0.21):
  konuştuğunda daha çok haklı, ama çok şey kaçırıyor.

Ultralytics `val()` P/R'yi max-F1 noktasında raporlar; `conf` yalnız PR eğrisinin kuyruğunu
keser. Düşük `conf`'ta mAP'in artması dağıtılan eşiği seçmez. Çalışma noktası, `conf=0.001`
val koşusunun PR eğrisinden, hedef recall'a karşılık gelen **km başına yanlış olay** ile
seçilir — `conf` taraması değil.

### v3 neden henüz pipeline'a bağlanmadı

`configs/pipeline.yaml` hâlâ v1'i kullanıyor. v3'ün gerçekten daha iyi olduğunu **ölçemiyoruz**:
tek temiz hold-out'umuz `clip3` ve orada yalnız 19 rögar kutusu var. v1'in val skoru sızıntılı,
v3'ün skoru temiz — yani iki sayı aynı ölçeğe ait değil ve düşük olanın kötü olduğu sonucu
çıkmıyor. Karar `clip3` tamamlanınca (ya da `clip5`/`clip6`'dan ikinci bir hold-out klip
ayrılınca) verilecek. Bu, sürüm atlamak değil, ölçemediğimiz bir değişikliği üretime
sokmamaktır.

## clip3 tamamlandı (18 Ağu 2026)

69 kare: 24'ü kutulu (44 rögar), 45'i temiz. `imgsz 1280`, `conf 0.10`, test bölmesi.

| model | P | R | mAP50 | mAP50-95 | temiz karede yanlış kutu |
| --- | --- | --- | --- | --- | --- |
| v1 (sızıntılı — `clip3` eğitimindeydi) | 0.754 | 0.906 | 0.719 | 0.288 | 54 (32/45 kare) |
| v2 | 0.656 | 0.523 | 0.601 | 0.243 | 131 (42/45 kare) |
| **v3** | 0.604 | **0.705** | 0.581 | 0.196 | **49 (29/45 kare)** |

Hâlâ yalnız rögar ölçülebiliyor: `clip3`'te tek bir çukur, çatlak veya hasar kutusu yok, yani
kabul eşiklerinin ikisi bu klipte prensip olarak ölçülemez. Karar için `clip5`/`clip6`'dan
çukur içeren ikinci bir hold-out klip ayırmak gerekiyor.

v1'in tablodaki üstünlüğü geçerli değil: bu klibin kareleri v1'in eğitim setindeydi, yani kendi
kopya çektiği sınavda yarışıyor. Aynı sebep yanlış alarm sütununu da v1 lehine büküyor — v1 bu
kareleri "kutusuz" olarak görmüş, sessiz kalması öğrenilmiş davranış. Tek adil karşılaştırma
v2 ile v3 arasında ve orada v3 net kazanıyor: recall 0.523 → 0.705, yanlış kutu 131 → 49.

Temiz karelerdeki rögar tespitlerinin sistematik bir etiket eksiği olup olmadığı kontrol edildi:
`conf 0.35`'te üç modelin birden rögar gördüğü 45 karenin yalnız 3'ü çıktı ve üçü de gerçek
rögardı (kareler yeniden kuyruğa alındı). Kalan tespitler düşük güvenli ve modeller arasında
uyumsuz — yani gerçek yanlış alarm, eksik etiket değil.

## Kabul eşikleri

`scripts/eval_aerial.py` içindeki `THRESHOLDS`:

- `manhole_recall >= 0.85`
- `pothole_map50 >= 0.50`
- `road_crack_map50 >= 0.30`

Bir sınıfın o bölmede **50'den az** kutusu varsa sonuç `n/a` (ölçülemedi) olarak raporlanır,
başarısız sayılmaz; ama karar da verilemez. `n=3` ile FAIL vermek anlamsız.

Eşikler tutmazsa çözüm **daha fazla drone verisi**, farklı veri kaynağı değil. Sokak seviyesi
setlerle birleştirme seçeneği eleniyor (gerekçe: `docs/training-model-b.md` §0e). Yeni uçuşlarda
neyin çekileceği: `docs/aerial-data-collection.md`.
