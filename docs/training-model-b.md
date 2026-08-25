# Model B nasıl eğitilir? (çukur / çöp / yol hasarı)

Model A (araç) hazır COCO ağırlığıyla çalışır.  
**Çukur ve çöp için kendi Model B’ni eğitmen gerekir.**

## 0) Hazır yol bozukluğu ağırlığı (önerilen bootstrap)

Pipeline varsayılan road Model B:

- Dosya: `models/infra-b-road-rdd.pt`
- Kaynak: [vinothvikas1987/pothole-detection-yolov8](https://huggingface.co/vinothvikas1987/pothole-detection-yolov8) (Apache-2.0, YOLOv8s, RDD)
- Native sınıflar `Longitudinal Crack` / `Pothole` / … → City Vision taxonomy: `configs/classes.yaml` → `label_aliases`

İndirme (bir kez):

```bash
python - <<'PY'
from pathlib import Path
import shutil
from huggingface_hub import hf_hub_download
dest = Path("models/infra-b-road-rdd.pt")
src = hf_hub_download("vinothvikas1987/pothole-detection-yolov8", "best.pt")
shutil.copy2(src, dest)
print(dest, dest.stat().st_size)
PY
```

Eski tek-sınıf RoadEye bootstrap (`models/infra-b-road.pt`) hâlâ diskte kalabilir; `pipeline.yaml` artık RDD ağırlığını kullanır.

## 0b) Hızlı başlangıç — kendi pothole eğitimin (RoadEye)

RDD2022 S3 linkleri şu an 403 verebiliyor. Çalışan yol: Hugging Face **RoadEye** YOLO pothole seti.

```bash
# Dataset indir (varsayılan ~1500 train)
python scripts/prepare_public_pothole.py --train-limit 1500 --val-limit 300

# Model B (pothole) eğit — Mac'te MPS
python scripts/train_model_b.py \
  --data configs/model_b_road.data.yaml \
  --epochs 40 \
  --device mps \
  --name train_roadeye \
  --export-to models/infra-b-road.pt

# Pipeline'a bağla
python scripts/run_pipeline.py \
  --source data/samples/demo.mp4 \
  --output outputs/demo_b \
  --model-b models/infra-b-road.pt
```

RDD2022 denemek için (S3 açıksa):

```bash
python scripts/prepare_rdd2022.py --source rdd --country Czech
```

## 0c) SVRDD — çukur + çatlak + rögar

Street-view seti ([SVRDD](https://huggingface.co/datasets/ShuoZheLi/SVRDD_YOLO), CC BY 4.0). RoadEye’ı ezmez; çıktı `data/datasets/model_b_svrdd`.

Eşleme: `pothole` → `pothole`, üç çatlak → `road_crack`, rögar → `manhole`, yama kutuları silinir (görüntü kalır).

```bash
# Tam set (~8k görüntü, ilk indirme ~4 GB)
python scripts/prepare_svrdd.py

# Hızlı deneme
python scripts/prepare_svrdd.py --max-train 800 --max-val 200

python scripts/train_model_b.py \
  --data configs/model_b_svrdd.data.yaml \
  --epochs 40 \
  --device mps \
  --name train_svrdd \
  --export-to models/infra-b-road-svrdd.pt
```

Alttaki Baidu street-view görüntüleri Baidu Maps ToS’a tabidir; ticari ağırlık dağıtmadan önce kontrol edin.

Sonra yerel / CVAT verisiyle fine-tune ederek Türkiye şartlarına uyarlarsın.

## 0d) Aerial (DJI) — kendi el etiketlerimiz

Veri toplama: `docs/aerial-data-collection.md`. Etiketleme kuralları: `docs/labeling-guide-aerial.md`.
Ölçüm geçmişi: `docs/eval/README.md`.

```bash
# 1) Kareleri çıkar — kaynak 4K, ince çatlak için tam çözünürlük şart
python scripts/label_aerial.py --extract data/samples/clip4_1400.mp4 --prefix clip4 \
  --every-sec 1 --max-width 3840

# 2) Hangi kare etiketlenmeye değer? (düşük güven / model çelişkisi / çatlak adayı)
python scripts/queue_uncertain.py --device mps

# 3) Tarayıcıda etiketle — "öncelik" filtresi kuyruğu kullanır, B = temiz kare
python scripts/label_aerial.py
# doğrudan bir klipte açmak için: http://127.0.0.1:8765/?clip=clip4&mode=todo

# 4) YOLO train/val/test'e paketle (klip bazlı bölme)
python scripts/label_aerial.py --export

# 5) Eğit — drone yaw'ladığı için dönme ve dikey flip açık olmalı
python scripts/train_model_b.py \
  --data configs/model_b_aerial.data.yaml \
  --model yolov8s.pt --imgsz 1280 --epochs 100 --batch 4 --device mps \
  --degrees 180 --flipud 0.5 --close-mosaic 15 --patience 25 \
  --name train_aerial_v3 --export-to models/infra-b-road-aerial-v3.pt

# 6) Hold-out klipte ölç (eğitime hiç girmeyen clip3)
python scripts/eval_aerial.py --split test --device mps --tag aerial-v3
```

**MPS tuzağı:** `--device mps` verdiğin halde Ultralytics başlıkta `CPU (arm)` yazıyorsa,
komut kum havuzu (sandbox) içinde çalışıyor ve PyTorch GPU'yu görmüyor —
`torch.backends.mps.is_available()` orada `False` döner. Eğitim durmaz, sadece 2 kat yavaşlar.
Başlangıçta `MPS (Apple ...)` satırını ve ilk epoch'ta sıfırdan farklı bir `GPU_mem` değeri
gördüğünü doğrula; `0G` görüyorsan koşu CPU'dadır.

**MPS'in ikinci tuzağı — saatler sonra çöken eğitim:** PyTorch'un MPS arka ucu, `.expand()`
ile genişletilmiş bitişik olmayan tensörlerde boolean maske indekslemeyi yanlış sayıyor.
Ultralytics'in hedef atayıcısı (`TaskAlignedAssigner.get_box_metrics`) bunu kullandığı için
eğitim ortasında düşüyor:

```
RuntimeError: shape mismatch: value tensor of shape [6772]
cannot be broadcast to indexing result of shape [6480]
```

Hata belirsiz zamanlı — karedeki kutu sayısına bağlı, o yüzden v3 tam 25. epoch'ta düştü.
Ultralytics 8.4 bu noktada CPU'ya düşüyor ama **yalnız bellek yetmezliğinde**, şekil
uyuşmazlığında değil. `patch_tal_for_mps()` (`src/cityvision/pipeline/train_utils.py`)
atayıcıyı MPS'te CPU'ya yönlendiriyor; `train_model_b.py` bunu her koşuda kuruyor, CPU ve
CUDA'da etkisiz. Ölçtüğümüz kadarıyla yavaşlatmıyor (atama, adımın küçük bir parçası).

Çöktüyse sıfırdan başlamaya gerek yok, `last.pt` duruyor:

```bash
python scripts/train_model_b.py --resume runs/model_b/train_aerial_v3/weights/last.pt \
  --data configs/model_b_aerial.data.yaml \
  --name train_aerial_v3 --export-to models/infra-b-road-aerial-v3.pt
```

`--name` ve `--export-to` tekrar verilmeli: `--resume` veri setini ve hiperparametreleri
checkpoint'ten okur ama dışa aktarma hedefini okumaz.

`--imgsz 1280` seçimi 4K karelerden geliyor: 960'a indirince 4K'daki 12 px'lik çatlak 3 px'e
düşüyor. Bedeli hız — M5 Pro'da 847 görüntü için epoch ~4-5 dk (960'da ~1 dk).

Bölme kuralı `src/cityvision/pipeline/dataset_split.py` içinde: `clip3` tamamı hold-out test,
diğer her klip kendi zaman çizgisinde kesilir (son %20 val, kesim noktasındaki kare atılır).
Video karelerini rastgele bölmek val skorunu gerçek dışı yükseltir, çünkü komşu saniyeler
neredeyse aynı görüntüdür.

`background.txt`'teki kareler boş etiketle dışa aktarılır (hard negative) ve yanlış alarmı
düşürür. Bu liste `reviewed.txt`'ten ayrıdır: kutusuz gözden geçirilmiş bir kare "temiz" değil,
sadece "atlanmış" olabilir.

Temiz kareler eğitim bölmesinin en fazla %15'i olacak şekilde kırpılır (`BG_MAX_FRAC`) ve klipler
arasında sırayla seçilir. Sınır olmadan oran %35'e çıkıyordu; bu kadar boş görüntü kaybı
"hiçbir şey tahmin etme" yönüne kaydırıp nadir sınıflarda duyarlılığı düşürür. Kırpma yalnız
eğitimde: val ve test her temiz kareyi tutar, yanlış alarm ölçümü dürüst kalsın diye.

## 0e) Neden sokak seviyesi setlerle birleştirmiyoruz

SVRDD ve RoadEye araç yüksekliğinden, öne bakan perspektifle çekilmiş. Bizim kareler 20-60 m
irtifadan eğik bakış. Aynı nesne iki domainde farklı görünür: rögar kapağı sokak görüntüsünde
perspektiften dolayı elips, kuşbakışında daire; çatlak sokak görüntüsünde ekranın altında kalın,
havadan ince bir çizgi. Kutu sayısını büyütmek için bu setleri karıştırmak, modele yanlış şekil
ve ölçek önyargısı öğretme riski taşıyor (negatif transfer).

Karar: **aerial veri setini kendimiz büyütüyoruz.** Yeni drone çekimleri geldikçe kare ekliyoruz.
Sokak seviyesi ağırlıklar (`infra-b-road-rdd.pt`, `infra-b-road-svrdd.pt`) şimdilik pipeline'da
emniyet ağı olarak duruyor; kendi modelimiz sınıf başına yeterli kutuya ulaşınca çıkarılacak.

## 0b) Waste bootstrap — GarbageOverflow (Plan A)

```bash
# 1) HF token (bir kez)
# https://huggingface.co/settings/tokens → Read token oluştur
cp .env.example .env
# .env içine: HF_TOKEN=hf_...
set -a; source .env; set +a
# veya: huggingface-cli login

# 2) Dataset
python scripts/prepare_garbage_overflow.py

# 3) Train
python scripts/train_model_b.py \
  --data configs/model_b_waste.data.yaml \
  --epochs 40 --device mps --name train_waste_overflow \
  --export-to models/infra-b-waste.pt
```

Not: Bu set yalnızca `overflowing_container`. `street_waste` için sonra TACO/yerel veri.

## 1) Veri topla (yerel)

- Pilot güzergahta video çek (sabah/öğle/akşam/gece, yağmur/kar/yama).
- Frame’leri çıkar veya CVAT’e video yükle.

## 2) CVAT’te etiketle

Sınıflar (sıra sabit):

0. `overflowing_container`
1. `street_waste`
2. `pothole`
3. `road_crack`
4. `road_damage`

Kurallar: `docs/gate-0/labeling-guideline-v1.md`

Export: **YOLO / Ultralytics**

## 3) Dataset’i yerleştir

```text
data/datasets/model_b/
  images/train/ ...
  images/val/   ...
  labels/train/ ...
  labels/val/   ...
```

Detay: `data/datasets/model_b/README.md`  
Config: `configs/model_b.data.yaml`

İlk deneme için pratik minimum:

- 300+ pothole
- 200+ waste
- train/val ayrımı video-aware (~80/20)

## 4) Eğit

```bash
source .venv/bin/activate
python scripts/train_model_b.py \
  --model yolov8n.pt \
  --epochs 80 \
  --imgsz 640 \
  --batch 16
```

Mac’te GPU yoksa otomatik CPU olur (yavaş). CUDA’lı makinede `--device 0`.

Çıktı:

- `runs/model_b/train/weights/best.pt`
- kopya: `models/infra-b-v1.pt`

## 5) Pipeline’a bağla

`configs/pipeline.yaml`:

```yaml
detection:
  model_a: yolov8n.pt
  model_b: models/infra-b-v1.pt
```

Sonra:

```bash
python scripts/run_pipeline.py \
  --source data/samples/demo.mp4 \
  --output outputs/demo_with_b \
  --model-b models/infra-b-v1.pt
```

## 6) Kaliteyi ölç

Bakılacaklar:

- class bazlı Precision / Recall / mAP50
- operasyonel: **false events / km** (yalancı çukur)

Kötüyse:

1. hard-negative ekle (yama, gölge, kar)
2. daha fazla gece/yağmur örneği
3. `yolov8s.pt` ile yeniden dene
4. conf eşiğini `pipeline.yaml` içinde yükselt

## 7) Durak / 2. sıra park?

Bunlar Model B eğitimi **değil**:

- araç tespiti (Model A) + GPS + GeoJSON zone + dwell süresi
- zone örneği: `configs/zones.example.geojson`

## Lisans

Ultralytics ticari kullanım için Enterprise / AGPL durumunu MVP sonunda netleştir.
