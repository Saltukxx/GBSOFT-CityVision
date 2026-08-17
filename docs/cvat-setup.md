# CVAT kurulumu (City Vision)

## Durum

Repo içinde: `tools/cvat` (gitignore’lı clone)  
UI: [http://localhost:8080](http://localhost:8080)

## Komutlar

```bash
# Başlat
bash scripts/cvat_up.sh

# Durdur
bash scripts/cvat_down.sh

# İlk kurulum / yeniden pull
bash scripts/cvat_install.sh
```

## Admin oluştur (bir kez)

```bash
docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'
```

Username / email / password soracak. Bunları sen seç.

## City Vision proje etiketleri (Model B)

Yeni project → Labels (sıra önemli — YOLO id ile aynı):

| # | Label |
| - | ----- |
| 0 | overflowing_container |
| 1 | street_waste |
| 2 | pothole |
| 3 | road_crack |
| 4 | road_damage |
| 5 | manhole |

Tip: **Rectangle** (bbox).

## İş akışı

1. Project + Task oluştur, video yükle  
2. Annotate → kaydet  
3. Menu → Export task dataset → **YOLO 1.1** / Ultralytics  
4. Export’u açıp şuraya koy:

```text
data/datasets/model_b/images/train|val
data/datasets/model_b/labels/train|val
```

5. Eğit:

```bash
python scripts/train_model_b.py --epochs 80
```

## Notlar

- `tools/cvat` git’e eklenmez (büyük upstream repo).  
- Docker Desktop açık olmalı.  
- Port **8080** kullanılır.
