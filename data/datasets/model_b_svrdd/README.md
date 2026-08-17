# Model B SVRDD bootstrap (YOLO)

Kaynak: [ShuoZheLi/SVRDD_YOLO](https://huggingface.co/datasets/ShuoZheLi/SVRDD_YOLO)

| id | class |
| -- | ----- |
| 0 | pothole |
| 1 | road_crack |
| 2 | manhole |

Yama kutuları yazılmaz; görüntü hard-negative olarak kalır. Rögar (`manhole cover`) sınıf 2’dir.

```bash
python scripts/prepare_svrdd.py
python scripts/train_model_b.py --data configs/model_b_svrdd.data.yaml --epochs 40 --device mps --name train_svrdd --export-to models/infra-b-road-svrdd.pt --no-val
```
