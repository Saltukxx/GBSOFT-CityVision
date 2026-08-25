# clip8 / clip9 — 18 Ağu 2026 etiket oturumu

Kaynak: Downloads’taki 17 Ağu 16:30 ve 20:30 uçuşları.
Kareler: `data/datasets/model_b_aerial/raw_frames/` (`clip8_*`, `clip9_*`, 3840, 1 fps).
Bu klasör, gitignore’daki canlı setten bağımsız bir kopyadır; eğitimden önce buradan veya `labels_hand/` içinden okunur.

## Durum (18 Ağu 16:26)

| | clip8 (16:30, 2.2 dk) | clip9 (20:30, 0.8 dk) |
|---|---|---|
| Kare | 130 | 48 |
| Kutulu | 74 | 11 |
| Temiz (B) | 10 | 11 |
| Atlanan | 46 | 26 |
| Kutu | 254 | 22 |
| pothole | 7 | 11 |
| road_crack | 169 | 3 |
| manhole | 17 | 8 |
| road_damage | 61 | 0 |

clip9 kullanılabilir hale getirildi (18 Ağu 17:20, v4 öncesi): tamir şeridi `road_damage`; `0046000ms` üçüncü kapak `manhole`, çevresi `road_damage`. clip8 Telekom kapakları hâlâ eksik.

## Eğitimden önce düzelt

### clip9 — yama ≠ çukur

`0021000`–`0026000` açık renkli tamir şeridi **pothole değil, road_damage**. Oyuk yok.

- `clip9_0021000ms`
- `clip9_0022000ms`
- `clip9_0023000ms`
- `clip9_0024000ms` (4 kutu, hepsi şerit)
- `clip9_0026000ms`

### clip9 — kapak çukur yazılmış

`clip9_0046000ms`: üç benzer kapaktan biri `pothole`; `manhole` olmalı. Diğer iki rögar doğru.

### clip9 — bırak

`clip9_0027000ms` iki büyük rögar kutusu doğru (yakın plan, kutu büyük çünkü drone alçalmış).

### clip8 — eksik rögar

`clip8_0067000ms` ve `clip8_0068000ms`: Türk Telekom kapağı görünüyor, kutu yok. Bu kareler zaten etiketli; kapağı da çiz.

`0068000` içindeki yama=`road_damage` / oyuk=`pothole` ayrımı doğru.

## Sonraki adım

Düzeltmeler etiketlenince:

```bash
python scripts/label_aerial.py --export
python scripts/train_model_b.py --data configs/model_b_aerial.data.yaml ...
```

clip8’in asıl katkısı **çatlak** (169 kutu). clip3 test hold-out olarak kalır.
