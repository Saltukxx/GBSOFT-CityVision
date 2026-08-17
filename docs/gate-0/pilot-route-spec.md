# Pilot Route Specification

Durum: taslak — belediye ile doldurulacak.

## Seçim kriterleri

1. İzinli koridor, tekrarlanabilir (nadir grid + alçak doğrulama geçişi)  
2. Karışık yüzey: iyi asfalt + yama + bilinen çukurlar + rögar  
3. Çöp konteyneri / atık yığını görülebilir sokak  
4. Farklı ışık/gölge dilimleri  
5. Dock menzili ve dönüş yolu net  

## Şablon

```text
City: __________________
Corridor name: __________________
Length (km): ______
Typical duration (min): ______
Drone / Dock IDs: DJI-__
Profiles: nadir grid + oblique inspect
Operating hours: __:__ – __:__
Known pothole count (manual survey): __
Known overflowing containers: __
Manhole hard-negatives in corridor: __
```

## Veri toplama planı (ilk 2 hafta)

| Koşul | Hedef |
| ----- | ----- |
| Nadir grid | ≥ 4 tekrarlanabilir tarama |
| Alçak eğik inceleme | Bilinen çukur / rögar noktaları |
| Sabah / öğle / akşam | En az birer geçiş |
| Yağmur / ıslak | fırsat oldukça |

Toplam MVP hedefi: **tekrarlanabilir koridor** (saat hedefi yerine aynı grid’in tekrarları).

## GIS hazırlık listesi

- [ ] izinli koridor polygon / no-fly kenarı  
- [ ] nadir waypoint grid  
- [ ] bilinen konteyner noktaları (varsa)  
- [ ] manuel ground-truth çukur listesi (lat/lon)  
- [ ] rögar konumları (hard-negative)

## Pilot süresi

**30 gün** Dock/drone koridoru + günlük KPI kaydı (`success-metrics.md`).
