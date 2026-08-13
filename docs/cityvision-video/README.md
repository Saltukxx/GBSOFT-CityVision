# GBSoft City Vision — tanıtım videoları (Remotion)

## Çıktılar

| Dosya | Kompozisyon | Süre |
| --- | --- | --- |
| `out/GBSoft-CityVision-Reels-60sn.mp4` | `CityVision-Reels-Vertical` | 61 sn · 1080×1920 · seslendirme + müzik |
| `out/GBSoft-CityVision-Reels-60sn-Sessiz.mp4` | `CityVision-Reels-Vertical-Sessiz` | 61 sn · 1080×1920 · tamamen sessiz master |
| `out/GBSoft-CityVision-Tanitim-90sn.mp4` | `CityVision-Tanitim-Yatay` | 90 sn · 1920×1080 · eski yatay sürüm |

## Komutlar

```bash
npm run dev                  # Remotion Studio (canlı önizleme)
npm run qa                   # sahne başına 3 kare basar -> qa/index.html kontak sayfası
npm run qa -- 256 402 1109   # istenen kareleri basar
npm run render:reel          # yayın sürümü (seslendirmeli)
npm run render:reel:sessiz   # sessiz sürüm
npm run render:reel:draft    # yarım çözünürlük, hızlı taslak
npm run lint                 # eslint + tsc
```

`npm run qa` düzen hatalarını (çakışma, taşma, boşluk) videoyu baştan sona
izlemeden yakalamak içindir. Her tasarım değişikliğinden sonra çalıştırın,
`qa/index.html`i tarayıcıda açın.

## Klasör yapısı

```
src/reel/
  theme.ts        renk, grid, tipografi ve hareket eğrisi — tek kaynak
  timing.ts       seslendirmeye kilitli sahne başlangıçları ve süreleri
  fonts.ts        Inter Tight + IBM Plex Mono (latin-ext, Türkçe)
  chrome.tsx      marka satırı, ilerleme rayı, başlık, panel, arka plan
  graphics.tsx    tespit anotasyonu, güzergâh haritası, kapsama grafiği
  scenes/S01..S08 sahneler
```

## Tasarım kuralları

- **Tek vurgu rengi.** `C.accent` ana renk; `alert / warn / ok` yalnızca anlam
  taşıdığında (hasar, eşik, onay). Rastgele renk kullanılmaz.
- **Sabit grid.** Kenar boşluğu 88 px, marka satırı 104, ilerleme rayı 166,
  başlık 296, içerik 1624'ün altına taşmaz, künye 1668. Tüm sahneler aynı.
- **Parıltı yok.** Neon glow, film grain ve tarama efekti kullanılmaz; çizgiler
  1–2 px, köşeler keskin. Bunlar "şablon video" hissi veren ilk işaretlerdir.
- **Veri mono tipografiyle.** Skor, koordinat, plaka, kimlik → IBM Plex Mono.
  Ürün arayüzü hissi verir ve sayıları hizalar.
- **Tek hareket eğrisi.** `theme.ease` dışında yumuşama kullanılmaz; kamera
  hareketi tek yönlü ve yavaş.

## Seslendirme senkronu

Sahneler `src/reel/timing.ts` içindeki cümle sınırlarına kilitlidir. Değerler
`public/voiceover-tr.mp3` üzerinde sessizlik analiziyle ölçüldü (bkz.
`voiceover.txt`). Sahne süreleri elle girilmez; `SCENE_DURATIONS` bu
sınırlardan ve geçiş süresinden hesaplanır.

Ses değişirse:

1. Yeni sesi `public/voiceover-tr.mp3` olarak koyun.
2. `npm run vo:boundaries` ile süreyi doğrulayın.
3. Cümle başlangıçlarını `timing.ts` içindeki `VO` nesnesinde güncelleyin.
4. `npm run qa` ile kontrol edip render alın.

## Ses karışımı

| Katman | Dosya | Seviye |
| --- | --- | --- |
| Seslendirme | `public/voiceover-tr.mp3` | ×0.86 (AAC kodlaması için ~1.3 dB tavan payı) |
| Müzik yatağı | `public/muzik-lightbeats.mp3` | anlatım altında 0.043, kapanışta 0.12 |

Müzik parçanın 70. saniyesinden başlar (`MUSIC.trimBefore`) — ölçümle en tutarlı
61 saniyelik pencere burası ve sonu doğal olarak sönümleniyor. Ölçülen sonuç:
konuşma −21 dBFS, cümle aralarında müzik −34 dBFS (yani 13 dB altta), kapanışta
−31 dBFS. Kırpılma yok.

Kaynak: Pixabay (lightbeatsmusic) — Pixabay Content License, ticari kullanım
serbest, atıf gerekmez.

Seviye değiştirmek için `src/reel/timing.ts` içindeki `MUSIC` ve `VOICE_GAIN`
sabitleri yeterli; kompozisyon dosyasına dokunmaya gerek yok.

## Görseller

Videodaki tüm fotoğraflar `public/gorseller/` altındadır ve
`docs/sunum/CityVision-Gorseller/` klasöründen gelir. Başka görsel kaynağı
kullanılmaz.
