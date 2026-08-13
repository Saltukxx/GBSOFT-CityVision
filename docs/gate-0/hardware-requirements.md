# Hardware Requirements — Pilot

## Edge bilgisayar

| Aşama | Öneri |
| ----- | ----- |
| AR-GE | Laptop (CUDA varsa avantaj) |
| Saha pilot | NVIDIA Jetson Orin NX (veya başlangıç için Orin Nano) |

## Kamera (araç başı 2 adet)

| Kamera | Yön | Use-case |
| ------ | --- | -------- |
| FRONT | Ön | pothole, road, traffic, crosswalk |
| RIGHT | Sağ | parking, bus stop, trash, sidewalk, signs |

### Minimum özellikler (pilot)

- 1080p@30fps veya üstü  
- Global / düşük rolling-shutter tercih  
- İyi dinamik aralık (gölge ↔ güneş)  
- Titreşim dayanımlı montaj  
- Bilinen FOV / lens (kalibrasyon için)

Production’da tüketici GoPro yerine endüstriyel / otomotiv kamera tercih edilir; pilot’da maliyet için daha esnek olunabilir.

## GPS

- 1 Hz veya daha sık NMEA / API  
- Kamera timestamp ile **zorunlu senkron**  
- Ideal: aynı edge saati (NTP veya PPS)

Her frame / event ile:

```text
timestamp, lat, lon, speed, heading, camera_id, vehicle_id
```

## Depolama & ağ

- Yerel SSD: ham buffer + evidence clip  
- 4G/5G: event paketi upload (tam video değil)  
- Evidence paketi hedefi: `event.jpg` + crop + ~15 sn clip + `event.json`

## Güç / çevre

- Araç aküsü regüle besleme  
- Geniş sıcaklık aralığı (Erzurum kışı)  
- Toz / nem koruması (IP rating hedefi saha sonrası netleşir)
