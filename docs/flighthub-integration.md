# FlightHub 2 entegrasyonu (Dock + Matrice 4TD)

Otonom sistemin iki ayrı katmanı var ve birbirinden bağımsız ilerliyorlar:

| Katman | Ne demek | Neye bağlı | Durum |
|---|---|---|---|
| **Uçuş otonomisi** | Dock planlı rotayı uçar, iner, şarj olur, medyayı yükler | Entegrasyon işi | FlightHub 2 + bu modül |
| **Karar otonomisi** | Tespit insan onayı olmadan iş emrine döner | Model doğruluğu | Henüz yok, bkz. `docs/eval/README.md` |

İlk sürümde uçuş tam otonom, karar operatör onaylı. Bu bir taviz değil: operatörün her
onayı/reddi bir etiket üretiyor (`src/cityvision/review/feedback.py`), yani karar
otonomisine giden veriyi asıl bu döngü topluyor. Eşikler tutunca onay adımı sınıf bazında
kaldırılır — önce `manhole`, sonra `road_damage`, en son `pothole` ve `road_crack`.

## Neden Cloud API değil de FlightHub 2

**Bir dock aynı anda tek bir bulut platformuna bağlanır.** DJI Enterprise uygulamasında tek
bir bulut hedefi seçiliyor; FlightHub 2 ile kendi Cloud API sunucumuzu aynı dock üzerinde
birlikte kullanmak desteklenmiyor (başka bir platforma geçmek için mevcut kimlik bilgisinin
üzerine yazmak gerekiyor). Yani "ikisi birlikte" bir mimari seçenek değil.

Desteklenen yol: dock FlightHub 2'ye bağlı kalır, CityVision biten uçuşları **OpenAPI** ile
çeker. Böylece rota planlama, uçuş takvimi, dock sağlığı, canlı görüntü ve hava durumu
kapıları DJI tarafında hazır gelir; tespit tamamen bizde kalır.

Kazanç: MQTT broker, görev planlayıcı, zamanlayıcı ve dock sağlık takibi yazmıyoruz.
Bedel: FlightHub 2 lisansı ve DJI'ın veri modeline bağımlılık.

KVKK/veri egemenliği gerekirse **FlightHub 2 On-Premises** var: aynı OpenAPI'yi kendi
sunucunuzda çalıştırıyor. Belediye ihalelerinde bu maddeyi sormaya değer.

## Veri akışı

```
Dock 3 + Matrice 4TD
  └─ FlightHub 2            rota, takvim, dock sağlığı, canlı görüntü
       ↓ OpenAPI (pull)
  scripts/flighthub_sync.py pull
       ├─ görev durumu      success mi?
       ├─ medya             original_url → MinIO/S3
       └─ rota (trajectory) → gps.jsonl yan dosyası
       ↓
  analyze_video işi (mevcut)
       └─ run_pipeline → olay füzyonu → PostGIS → operatör paneli → iş emri
```

Tespit tarafında tek satır değişmedi. Entegrasyon var olan `analyze_video` işine
bağlanıyor, yani `edge_video_uploads` tablosu, iş kuyruğu, mekânsal birleştirme ve iş emri
akışı aynen çalışıyor.

## Kimlik doğrulama

İki header yeterli:

- `X-User-Token` — FlightHub 2 → My Organization → Organization Settings → FlightHub Sync →
  Organization Key (bir JWT)
- `X-Project-Uuid` — proje listesindeki `data.list.uuid`

```bash
CITYVISION_FH2_BASE_URL=https://<flighthub-host>     # public cloud ve on-prem farklı
CITYVISION_FH2_USER_TOKEN=<organization key>
CITYVISION_FH2_PROJECT_UUID=<proje uuid>
```

`base_url` için varsayılan bilinçli olarak yok: yanlış hosta sessizce bağlanmak, açık hata
mesajından kötüdür.

## Doğrulanmamış endpoint'ler

DJI'ın referansında `/openapi/v0.1/project`, `/system_status` ve `/live-stream/start`
birebir yazılı. Buna karşılık görev/medya/rota çağrılarının **yolları** okuyabildiğimiz
public referansta sabitlenmiş değil; DJI yalnızca çağrıların varlığını ve sırasını
anlatıyor. Bu yüzden tahmin edilen yollar `PROVISIONAL_ENDPOINTS` içinde duruyor ve env ile
override edilebiliyor:

```bash
CITYVISION_FH2_EP_FLIGHT_TASK_MEDIA=/v2/task/{task_uuid}/files
```

**İlk gerçek uçuştan önce yapılacak:** FlightHub 2 kurulumunun kendi OpenAPI sayfasından bu
dört yolu teyit et ve gerekiyorsa `src/cityvision/flighthub/config.py` içinde düzelt.
Doğrulama komutu hangi yolların şüpheli olduğunu listeler:

```bash
python scripts/flighthub_sync.py status
```

Yol yanlışsa görüntü kaybedilmiyor: rota çağrısı başarısız olursa video yine işlenir,
sadece olaylar haritaya oturmaz ve sonuçta `trajectory_warning` döner.

## Donanımsız çalıştırma (mock)

Dock gelmeden tüm zincir çalışır. Taklit sunucu, gerçek bir video dosyasını görev medyası
olarak servis eder ve rotaları `config.py` ile aynı tablodan üretir; ikisi birbirinden
kayamaz.

```bash
# 1. terminal
python scripts/flighthub_sync.py mock --video data/samples/smoke.mp4

# 2. terminal
export CITYVISION_FH2_BASE_URL=http://127.0.0.1:8099
export CITYVISION_FH2_USER_TOKEN=mock-organization-key
python scripts/flighthub_sync.py status
python scripts/flighthub_sync.py tasks
python scripts/flighthub_sync.py pull 22222222-2222-4222-8222-222222222222
```

Kuyruğun işlenmesi için Redis worker'ı gerekir (`python scripts/job_worker.py`); Redis yoksa
iş aynı süreçte thread olarak çalışır.

Mock ile yapılan uçtan uca doğrulama (17 Ağu 2026): `clip2`'nin 40 gerçek 4K karesinden
üretilen video → 12 rota noktası → 39 tespit, **39'u da koordinatlı** → PostGIS'te 1 olay.

## Zaman ekseni tuzağı

Rota zaman damgaları duvar saati (epoch), ama `GpsFix.timestamp_ms` **video saati** —
`parse_dji_srt` altyazı offseti yazıyor, tespitler de kare indeksinden zamanlanıyor. Epoch
değerleri doğrudan yazılsa her fix `max_interp_gap_ms` sınırını aşar ve **GPS sessizce hiçbir
tespite işlenmez**. `parse_trajectory` bu yüzden uçuş başlangıcına göre yeniden tabanlıyor.

## Sonraki adımlar

1. FlightHub 2 hesabı açılınca `status` ile dört provisional yolu teyit et.
2. Çekme işini periyodik hale getir (cron veya Redis worker döngüsü).
3. FlightHub Sync webhook'u: medya yüklenince anında bildirim. Pull yeterli çalışıyorsa
   acele etmeye gerek yok; webhook'un kimlik doğrulama seçenekleri panelden görülmeli.
4. Onarım sonrası doğrulama uçuşu: kapatılan iş emri için aynı koridoru tekrar uçup
   kusurun gittiğini teyit etmek.
