# Success Metrics — Pilot

## Model metrikleri (her class)

- Precision  
- Recall  
- F1  
- mAP@0.5  

Bunlar gerekli ama belediyeye anlatılan ana metrik değil.

## Operasyonel ana KPI

### False events per route

```text
Örnek 20 km güzergâh
Gerçek pothole: 22
Tespit: 20
False detection: 3
→ false events / km = 0.15
```

## Pilot hedefleri (başlangıç)

| KPI | Hedef |
| --- | ----: |
| Pothole precision | > %90 |
| Pothole recall | > %85 |
| Waste precision | > %85 |
| Duplicate event rate | < %10 |
| GPS olay hatası | < 10 m |
| Dashboard availability | > %99 |
| Event upload latency | < 60 sn |
| Manuel inceleme | < 15 sn/olay |

## Günlük pilot telemetri

```text
km driven
hours recorded
AI events
verified events
false positives
false negatives
duplicate events
GPS errors
upload volume
edge CPU/GPU usage
temperature
```

## Kalibrasyon notu

İlk 30 gün eşikler sabittir; saha verisi sonrası confidence bantları ve fusion yarıçapı yeniden ayarlanır.
