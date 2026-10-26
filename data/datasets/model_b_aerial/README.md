# Aerial DJI Model B — hand boxes

Label in the browser: `python scripts/label_aerial.py`
Guide: `docs/labeling-guide-aerial.md` · Collection: `docs/aerial-data-collection.md`

## Clips

| prefix | source video | flight | frames | extracted at |
| --- | --- | --- | --- | --- |
| `dji` | `data/samples/dji_fly_20260816*.mp4` | 16 Aug 2026 | 406 | 1920 |
| `clip1` | `1. video 4.5 dk .mp4` | 16 Aug 2026 | 291 | 3840 |
| `clip2` | `2. video 4.5 dk.MP4` | 16 Aug 2026 | 291 | 3840 |
| `clip3` | `3. video 1 küsür dk 3_3.mp4` | 16 Aug 2026 | 69 | 3840 |
| `clip4` | `17 AĞU PZT 14.00 1. VİDEO.MP4` | 17 Aug 2026 14:00 | 291 | 3840 |
| `clip5` | `17 AGU Pzt 15.00 2. video .mp4` | 17 Aug 2026 15:00 | 231 | 3840 |
| `clip6` | `17 AGU PZT 16.00 4. VİDEO .mp4` | 17 Aug 2026 16:00 | 87 | 3840 |
| `clip7` | `17 AGU PZT 21.00 5. VİDEO .MP4` | 17 Aug 2026 21:00 | 168 | 3840 |
| `clip8` | `17 AGU PZT 16.30 5. VİDEO .mp4` | 17 Aug 2026 16:30 | 130 | 3840 |
| `clip9` | `17 AGU. PZT 20.30 4. VİDEO .MP4` | 17 Aug 2026 20:30 | 48 | 3840 |
| `clip10` | `18 Ağustos Salı 2. video` | 18 Aug 2026 | 72 | 1920 |
| `clip11` | `18 AĞUSTOS SALI 4. video .mp4` | 18 Aug 2026 | 291 | 3840 |
| `clip22` | `25 Agu 5.MP4` | 25 Aug 2026 | 72 | 3840 |
| `clip23` | `25 Agu 2 .MP4` | 25 Aug 2026 | 292 | 3840 |
| `clip24` | `25 Agu 1.MP4` | 25 Aug 2026 | 291 | 3840 |

### 18 Ağu 2026 oturumu (clip8 / clip9)

El etiketleri + inceleme kopyası: [`docs/eval/clip8-clip9/`](../../../docs/eval/clip8-clip9/README.md).
clip8: 74 kutulu / 254 kutu (169 çatlak). clip9: 11 kutulu.
v4 eğitiminden önce clip9 tamir şeridi `pothole` → `road_damage`; `clip9_0046000ms` üçüncü kapak `manhole`, çevresi `road_damage`. clip8 `0067000`/`0068000` Telekom kapağı hâlâ eksik.

### 18 Ağu 2026 oturumu (clip10 / clip11)

El etiketleri: [`docs/eval/clip10-clip11/`](../../../docs/eval/clip10-clip11/README.md).
clip10: 40 kutulu / 210 kutu (167 çatlak). clip11: 57 kutulu / 134 kutu (41 çukur).
Kullanılabilir; birkaç etiketlenmiş karede rögar kutusu yok (`clip11_0092000` Telekom, `clip11_0152000`–`0154000`).

Sources are symlinked into `data/samples/clip<N>_*.mp4`; sampled at 1 fps. Most clips are
3840x2160 30 fps. `clip10` is native 1920x1080 (~60 fps). `clip1`-`clip3` were first extracted
at 1920 and re-extracted at 3840 on 17 Aug; hand labels survived untouched because YOLO
coordinates are normalized. Only the older `dji_*` frames and `clip10` are at 1920.

Split is clip-based: `clip3` = hold-out test; every other clip is cut on its timeline (last 20% to val, 1 frame(s) at the cut dropped).
Frames listed in `background.txt` export as empty labels (hard negatives).
Train frames holding pothole/road_crack are copied 5x.

export train=306 val=39 test=12 (bg train=0 val=0 test=0, rare copies=144, guard dropped=5) boxes={'pothole': 178, 'road_crack': 36, 'manhole': 200, 'road_damage': 226}

<!-- export stats below; edited by hand above -->

Split is clip-based: `clip3` = hold-out test; every other clip is cut on its timeline (last 20% to val, 1 frame(s) at the cut dropped).
Frames listed in `background.txt` export as empty labels (hard negatives), capped at 15% of the train split and spread across clips.
Train frames holding pothole/road_crack are copied 5x.

export train=2976 val=417 test=27 (bg train=446 val=157 test=27, bg over cap dropped=150, rare copies=1436, guard dropped=24, external train added=0) boxes={'pothole': 1549, 'road_crack': 2282, 'road_damage': 3320}
