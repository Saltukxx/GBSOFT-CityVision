# Sample videos

Put pilot / demo MP4 files here (gitignored).

Quick smoke video (synthetic, no detections expected):

```bash
python scripts/make_smoke_video.py --output data/samples/smoke.mp4
```

## Wikimedia CC0 road clip (lab)

Source: [Tonkin Highway (CC0)](https://commons.wikimedia.org/wiki/File:Tonkin_Highway,_Redcliffe_Bridge_to_Great_Eastern_Highway.ogv) by Evad37.

```bash
# original download (ogv) → trimmed mp4 + synthetic GPS already prepared as:
#   data/samples/tonkin_highway.ogv
#   data/samples/tonkin_highway_15s.mp4
#   data/samples/tonkin_highway_15s.gps.jsonl

python scripts/run_pipeline.py \
  --source data/samples/tonkin_highway_15s.mp4 \
  --output outputs/tonkin_memphis_smoke \
  --gps data/samples/tonkin_highway_15s.gps.jsonl \
  --drone-id DJI-LAB-01 \
  --camera-id AERIAL
```

GPS sidecar is **synthetic** (for sync testing only), not real Perth telemetry.
