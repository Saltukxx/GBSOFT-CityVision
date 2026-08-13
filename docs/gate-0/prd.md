# Product Requirements Document — MVP

**Ürün:** GBSoft City Vision  
**Sürüm:** MVP / Pilot  
**Süre hedefi:** 24 hafta  
**Pilot:** 1 belediye · 1 güzergâh · 1–2 otobüs · 2 kamera/araç · 30 gün

## Problem

Belediyeler yol çukuru, çöp taşması, durak işgali ve trafik yoğunluğunu çoğunlukla vatandaş bildirimi veya seyrek saha turu ile öğrenir. Mevcut araç filoları şehirde zaten dolaşır ama görüntü operasyonel olaya dönüşmez.

## Çözüm

Belediye araçlarındaki kamera + GPS + edge AI ile sürekli tarama; cloud’da event fusion; operatöre tekil, doğrulanabilir olay ve iş emri adayı.

## Değer cümlesi

> Mevcut belediye araçlarınızı şehrin tamamını sürekli tarayan yapay zekâ sensörlerine dönüştürüyoruz.

## MVP kapsamı (In)

1. **Pothole AI** — çukur / büyük kırık / yüzey deformasyonu  
2. **Waste AI** — taşmış konteyner, yol kenarı atık  
3. **Bus stop obstruction** — *potential* ihlal adayı (ceza değil)  
4. **Traffic analytics** — sınıf bazlı sayım / yoğunluk KPI  

## Out of scope (MVP)

- Otomatik trafik cezası / EDS iddiası  
- Parking / ANPR production  
- Engelli rampası, tabela, sokak lambası (Phase II+)  
- Tam ERP entegrasyonu  

## Kullanıcılar

| Rol | İhtiyaç |
| --- | ------- |
| Operatör | Haritada olayları incele, doğru/yanlış işaretle |
| Fen İşleri / Temizlik | İş emri adayı al |
| Zabıta | Durak işgali adayını incele |
| Ürün / Admin | Model versiyonu, pilot KPI |

## İlk demo ekranları (zorunlu dört)

1. Live Route  
2. AI Detection (bbox overlay)  
3. City Event Map  
4. Event Detail (+ Create Work Order)

## Non-functional

- Privacy by design: mümkün olduğunca event crop + kısa kanıt kliniği  
- Her event’te `model_version`  
- Human-in-the-loop zorunlu (ilk üretim)  
- Edge-first tercih (Jetson pilotu sonraki faz)

## Başarı (özet)

Detay: `success-metrics.md`  
Operasyonel ana KPI: **false events per route**.

## Bağımlılıklar

- Pilot güzergâh ve araç erişimi  
- CVAT + labeling ekibi / süresi  
- Kamera + GPS senkronu  
- Model stack lisans kararı (MVP sonu gate)
