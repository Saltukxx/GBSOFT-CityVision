# Event Taxonomy (MVP v1)

Detection ≠ Event. Event, tekrarlayan gözlemler ve kurallar sonrası oluşan operasyonel kayıttır.

## Event tipleri

| event_type | Kaynak | Birim | MVP |
| ---------- | ------ | ----- | --- |
| `pothole` | Model B + fusion | Fen İşleri | Evet |
| `road_damage` | Model B + fusion | Fen İşleri | Evet |
| `overflowing_container` | Model B + fusion | Temizlik | Evet |
| `street_waste` | Model B + fusion | Temizlik | Evet |
| `potential_bus_stop_obstruction` | Vehicle det + GIS geofence | Zabıta | Evet |
| `traffic_density` | Tracking KPI (segment) | Ulaşım | Evet (analytics) |

## Ortak event şeması

```json
{
  "event_id": "POT-18222",
  "type": "pothole",
  "lat": 39.91821,
  "lon": 41.27311,
  "severity": "medium",
  "confidence": 0.96,
  "first_seen": "2026-08-12T09:14:00Z",
  "last_seen": "2026-08-12T16:37:00Z",
  "observations": 4,
  "status": "open",
  "model_version": "pothole-0.1.0",
  "vehicle_ids": ["BUS-17"],
  "camera_ids": ["FRONT"]
}
```

## Severity

| Seviye | Kullanım |
| ------ | -------- |
| `low` | İzle / düşük öncelik |
| `medium` | Planlı müdahale |
| `high` | Acil / güvenlik riski |

## Confidence bantları (başlangıç)

| Bant | Aksiyon |
| ---- | ------- |
| `< 0.70` | discard / archive |
| `0.70–0.85` | manual review |
| `0.85–0.95` | probable |
| `> 0.95` | high confidence |

Composite confidence: AI score + GPS kalitesi + tekrar gözlem + farklı araç doğrulaması.

## Status lifecycle

```text
detected → under_review → confirmed → work_order_created → resolved
                 ↘ false_positive
```

## Fusion kuralı (MVP)

Aynı `type` için yaklaşık **15 m** yarıçap + **72 saat** penceresindeki observations tek event’e birleşir (pilot sonrası kalibre).
