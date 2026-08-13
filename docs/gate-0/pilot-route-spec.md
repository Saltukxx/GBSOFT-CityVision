# Pilot Route Specification

Durum: taslak — belediye ile doldurulacak.

## Seçim kriterleri

1. Tek güzergâh, tekrarlanabilir (günde ≥ 4 tur ideal)  
2. Karışık yüzey: iyi asfalt + yama + bilinen çukurlar  
3. En az 3–5 otobüs durağı (geofence için)  
4. Çöp konteyneri koridoru  
5. Farklı ışık/gölge dilimleri  

## Şablon

```text
City: __________________
Route name: __________________
Length (km): ______
Typical duration (min): ______
Bus IDs: BUS-__ , BUS-__
Cameras per bus: FRONT + RIGHT
Operating hours: __:__ – __:__
Known pothole count (manual survey): __
Known overflowing containers: __
Bus stop zone count (GIS): __
```

## Veri toplama planı (ilk 2 hafta)

| Koşul | Hedef süre |
| ----- | ---------: |
| Sabah | ≥ 4 saat |
| Öğle | ≥ 4 saat |
| Akşam | ≥ 4 saat |
| Gece | ≥ 3 saat |
| Yağmur / ıslak | fırsat oldukça |
| Kar / çamur (Erzurum) | fırsat oldukça |

Toplam MVP hedefi: **30–50 saat** şehir videosu.

## GIS hazırlık listesi

- [ ] `bus_stops` polygon  
- [ ] güzergâh line / corridor  
- [ ] bilinen konteyner noktaları (varsa)  
- [ ] manuel ground-truth çukur listesi (lat/lon)

## Pilot süresi

**30 gün** canlı araç + günlük KPI kaydı (`success-metrics.md`).
