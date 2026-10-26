# Product Requirements Document — MVP

**Ürün:** GBSoft City Vision  
**Sürüm:** MVP / Pilot  
**Süre hedefi:** 8 hafta
**Pilot:** 1 belediye · 1 izinli koridor · 1 Dock / drone · nadir grid + alçak doğrulama · 30 gün

## Problem

Belediyeler yol çukuru, çöp taşması ve yüzey hasarını çoğunlukla vatandaş bildirimi veya seyrek saha turu ile öğrenir. Tek seferlik drone uçuşu kayıt olur ama görüntü operasyonel olaya dönüşmez.

## Çözüm

DJI Dock veya DJI Fly ile tekrarlanabilir koridor taraması; merkezi hibrit yapay zekâ analizi; olay birleştirme; operatöre tekil, doğrulanabilir olay ve iş emri adayı.

## Değer cümlesi

> Drone ile tekrarlanabilir koridor taraması; olay = tespit + GPS + fusion + insan onayı.

## MVP kapsamı (In)

1. **Pothole AI** — çukur / büyük kırık / yüzey deformasyonu (rögar iş emri değil)  
2. **Waste AI** — taşmış konteyner, yol kenarı atık  
3. **Nadir + oblique profiller** — kuşbakışı tarama ve alçak inceleme  
4. **DJI GPS** — SRT sidecar → harita  

## Out of scope (MVP)

- Otomatik trafik cezası / EDS iddiası  
- Parking / ANPR production  
- Engelli rampası, tabela, sokak lambası (Phase II+)  
- DJI Cloud API / Dock MQTT (ayrı entegrasyon)  
- Tam ERP entegrasyonu  

## Kullanıcılar

| Rol | İhtiyaç |
| --- | ------- |
| Operatör | Haritada olayları incele, doğru/yanlış işaretle |
| Fen İşleri / Temizlik | İş emri adayı al |
| Ürün / Admin | Model versiyonu, uçuş profili, pilot KPI |

## İlk demo ekranları (zorunlu dört)

1. Live Route  
2. AI Detection (bbox overlay)  
3. City Event Map  
4. Event Detail (+ Create Work Order)

## Non-functional

- Privacy by design: mümkün olduğunca event crop + kısa kanıt kliniği  
- Her event’te `model_version`  
- Human-in-the-loop zorunlu (ilk üretim)  
- Merkezi veya görev bazlı bulut GPU

## Başarı (özet)

Detay: `success-metrics.md`  
Operasyonel ana KPI: **false events per corridor**.

## Bağımlılıklar

- İzinli koridor ve Dock/drone erişimi  
- CVAT + labeling ekibi / süresi (nadir + eğik kare, rögar hard-negative)  
- DJI SRT veya eşdeğer GPS  
- Model stack lisans kararı (MVP sonu gate)
