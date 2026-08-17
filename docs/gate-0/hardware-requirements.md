# Hardware Requirements — Pilot

## İşlem

| Aşama | Öneri |
| ----- | ----- |
| AR-GE | Laptop (MPS / CUDA) |
| Saha pilot | Merkezi GPU; Dock/Fly videosu ofiste veya bulutta işlenir |
| Sonraki faz | Jetson companion (onboard AI yok — MVP) |

## Drone / kamera

| Kaynak | Rol |
| ------ | --- |
| DJI Dock + Matrice (4D/4TD) | Tekrarlanabilir waypoint / nadir grid |
| DJI Fly (pilot) | Alçak eğik inceleme, lab klipleri |

Varsayılan kamera id: `AERIAL`.

### Minimum özellikler (pilot)

- 1080p@30fps veya üstü  
- Nadir harita + alçak eğik bakış (gimbal)  
- İyi dinamik aralık (gölge ↔ güneş)  
- DJI SRT veya eşdeğer kare zamanlı GPS  

## GPS

- DJI Fly/Dock **SRT** (videonun yanında `.SRT` / `.srt`)  
- Yoksa JSONL/CSV sidecar: `timestamp_ms, lat, lon`  
- Kamera timestamp ile senkron (SRT satır zamanı)

Her frame / event ile:

```text
timestamp, lat, lon, speed, heading, camera_id, vehicle_id
```

`vehicle_id` drone / dock asset id’sidir (`DJI-01`).

## Depolama & ağ

- Dock/laptop: ham MP4 + SRT  
- 4G/5G veya ofis ağı: event paketi upload (tam video değil)  
- Evidence paketi hedefi: `event.jpg` + crop + ~15 sn clip + `event.json`

## Güç / çevre

- Dock şarj + saha elektrik (Dock 3 yedek batarya değiştirmez)  
- Rüzgâr / yağmur / görüş: DJI kalkış limitleri  
- SHGM ticari izin; otomasyon yükümlülüğü kaldırmaz
