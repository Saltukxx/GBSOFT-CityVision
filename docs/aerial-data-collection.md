# Drone veri seti toplama kılavuzu

Model B'nin yol sınıflarını yalnızca kendi drone karelerimizle eğitiyoruz. Sokak seviyesi açık
setler (SVRDD, RoadEye) kullanılmıyor — gerekçe: [training-model-b.md](training-model-b.md) §0e.

Bu sayfa, yeni bir uçuş yapılırken nelerin çekilmesi gerektiğini ve karelerin sete nasıl
alındığını anlatır. Kutu çizme kuralları ayrı: [labeling-guide-aerial.md](labeling-guide-aerial.md).

## Bugünkü durum

| Sınıf | Kutu | Kaç karede |
|---|---|---|
| `manhole` | 177 | 96 |
| `road_damage` | 184 | 122 |
| `pothole` | 39 | 36 |
| `road_crack` | 16 | 8 |

Toplam 218 el etiketli kare, arka plan (nesnesiz) karesi yok. `pothole` ve `road_crack` bu
sayılarla öğrenilemez; model onları `road_damage`/`manhole`'a yuvarlıyor. Sınıf başına **300 kutu**
kullanılabilir alt sınır, **1000+** rahat bölge.

Kaba ihtiyaç: `road_crack` için ~150, `pothole` için ~240 yeni içerikli kare. Kare sayısı değil,
**kutu sayısı** hedef — çatlağı olmayan 500 kare bu açığı kapatmaz.

## Uçuşta ne çekilmeli

Öncelik sırası, eksik olan sınıfa göre:

1. **Çatlaklı yollar.** Eski asfalt, yamalı yollar, kavşak yaklaşımları, ağır araç güzergâhları.
   Bu tek başına en kritik madde; mevcut sette 8 kare var.
2. **Çukurlar.** Yağmurdan sonra su tutan noktalar en kolay bulunur.
3. **Çeşitlilik.** Aynı yolu farklı koşullarda geçmek, yeni yol çekmek kadar değerli:
   - İrtifa: 20 m / 40 m / 60 m
   - Gimbal: dik bakış (90°) ve eğik (~45°)
   - Saat: sabah ve akşam (uzun gölge) + öğle (gölgesiz)
   - Zemin: yeni asfalt, yıpranmış asfalt, yamalı, beton, parke
   - Islak ve kuru
4. **Temiz yollar.** Kusursuz asfalt üzerinde geçiş kareleri lazım — bunlar arka plan olarak
   işaretlenip modele "burada hiçbir şey yok" öğretir. Setin ~%15-20'si böyle olmalı.

Gölge, ıslak leke, boya izi ve derz gibi yanlış alarm kaynakları çerçeveye **bilerek** girsin;
model ancak gördüğü şeyi ayırt etmeyi öğrenir.

## Kareleri sete alma

```bash
# yeni klip → raw_frames/  (prefix her klip için tekil olmalı: clip7, clip8, …)
python scripts/label_aerial.py --extract ~/Downloads/DJI_0042.MP4 \
  --prefix clip7 --every-sec 1.0 --max-width 3840
```

**Çözünürlük.** Şimdiye kadar `--max-width 1920` kullandık; kaynak 4K olduğu için kareler yarıya
indi, eğitim de 960'a indirdiği için toplam 4 kat küçülme oldu. Rögar ve çukur bunu kaldırıyor,
ince çatlak kaldırmıyor: 4K'da 12 px'lik bir çatlak eğitim girdisinde 3 px'e düşüyor. Yeni
klipleri **3840** ile çıkarın ve çatlak hedefliyorsanız eğitimi `--imgsz 1280` ile kurun.

Pratik kural: etiketleyicide %100 zoom'da çatlağı göremiyorsanız etiketlemeyin — o kutu modele
gürültü olarak gider. Bir sonraki uçuşta o noktanın üzerinden daha alçak geçin.

**Kare aralığı.** `--every-sec 1.0` normal seyir hızında iyi. Drone bir noktada asılı kaldıysa
kareler birbirinin kopyası olur; `scripts/queue_uncertain.py` bunları dhash ile ayıklıyor, yine de
asılı kalınan bölümü uzun tutmayın.

**Klip = split birimi.** Bir klip ya tamamen eğitimde ya tamamen testtedir; aynı yolun ardışık
kareleri iki tarafa dağılırsa test skoru şişer. `clip3` şu an test, `clip2` doğrulama. Yeni
kliplerin bir tanesini teste ayırın, gerisi eğitime gitsin.

## Etiketleme sırası

```bash
python scripts/queue_uncertain.py     # priority.txt + background_candidates.txt üretir
python scripts/label_aerial.py        # tarayıcı etiketleyici, mode: priority / bgcand / review
```

1. `priority` modu — modelin en çok tereddüt ettiği kareler, kare başına en yüksek kazanç.
2. `bgcand` modu — hiç tespit çıkmayan kareler; doğruysa `B` ile temiz kare işaretle.
3. `review` modu — eski etiketleri kılavuzdaki kurallarla tekrar geçir.

Bittiğinde:

```bash
python scripts/label_aerial.py --export     # klip bazlı split + oversampling
python scripts/train_model_b.py --data configs/model_b_aerial.data.yaml \
  --model yolov8s.pt --imgsz 1280 --epochs 120 --batch 4 --device mps \
  --degrees 180 --flipud 0.5 --close-mosaic 15 \
  --name train_aerial_v3 --export-to models/infra-b-road-aerial.pt
python scripts/eval_aerial.py --weights models/infra-b-road-aerial.pt \
  --split test --device mps --tag v3 \
  --baseline docs/eval/baseline-aerial-v1.test.json
```

## Sokak seviyesi ağırlıklardan çıkış

`configs/pipeline.yaml` şu an Model B olarak üç ağırlık çalıştırıyor: kendi aerial modelimiz +
iki sokak seviyesi model (RDD, SVRDD). Sokak modelleri kendi setimiz zayıfken emniyet ağı.
Aerial model `docs/eval/README.md` içindeki eşikleri tutar tutmaz o ikisi kaldırılıp tek modele
inilecek — böylece perspektif uyuşmazlığından gelen yanlış kutular da biter.
