/**
 * Seslendirmeye kilitli zamanlama.
 *
 * public/voiceover-tr.mp3 (58.67 sn) içindeki cümle sınırları sessizlik
 * analiziyle ölçüldü; sahneler bu sınırlara oturur. Ses değişirse
 * scripts/vo-boundaries.mjs yeniden çalıştırılıp buradaki değerler güncellenir.
 */

export const FPS = 30;
export const TRANSITION = 12;

/** Her cümlenin başlangıç karesi (mutlak). */
export const VO = {
  s01: 0, // Drone aynı şehir koridorunu planlı uçuşlarla tekrar tarıyor.
  s02: 112, // Her uçuş görünür belediye sorunlarını konumu ve kanıtıyla kayda dönüştürüyor.
  s03: 222, // City Vision yol hasarı, taşan konteyner ve kaçak döküm alanlarını tespit ediyor.
  s04: 413, // Sabit rota ve çekim standardı sonuçları karşılaştırılabilir kılıyor.
  s05: 566, // Uçuş görüntüsü merkezi yapay zekâ sisteminde analiz ediliyor.
  s06: 670, // Tespit edilen her sorun konumu ve görüntüsüyle birlikte sisteme kaydediliyor.
  s07: 809, // Aynı sorun tekrarlı uçuşlarda yeniden görüldüğünde kayıtlar tek olay altında birleştiriliyor.
  s08: 998, // Bu sayede aynı sorun için birden fazla iş emri oluşturulmuyor.
  s09: 1120, // Belediye ekipleri doğrudan doğru noktaya yönlendiriliyor.
  s10: 1232, // Bunun için yeni bir ekip kurulmasına gerek kalmıyor.
  s11: 1316, // Planlı drone uçuşları sürerken izinli koridor düzenli takip ediliyor.
  s12: 1434, // Sorunlar büyümeden tespit ediliyor ve ekipler daha hızlı harekete geçiyor.
  s13: 1567, // GBSoft City Vision şehir yönetimini daha hızlı, daha düzenli ve daha verimli hâle getiriyor.
  end: 1760,
} as const;

/** Sahnelerin mutlak başlangıç kareleri. */
export const SCENE_START = [VO.s01, VO.s03, VO.s04, VO.s05, VO.s07, VO.s09, VO.s11, VO.s13];

export const TOTAL = 1830; // 61 sn — anlatım bittikten sonra 2.3 sn kapanış payı

/**
 * TransitionSeries geçişleri örtüştüğü için her sahnenin süresi
 * "bir sonraki sahneye kalan mesafe + geçiş" olmalı ki mutlak
 * başlangıçlar seslendirmeyle birebir tutsun.
 */
export const SCENE_DURATIONS = SCENE_START.map((start, i) =>
  i === SCENE_START.length - 1 ? TOTAL - start : SCENE_START[i + 1] - start + TRANSITION,
);

/** Mutlak kareyi sahne içi yerel kareye çevirir (kopya metinleri hizalamak için). */
export const localOf = (sceneIndex: number, absolute: number) => absolute - SCENE_START[sceneIndex];

/**
 * Müzik yatağı — public/muzik-lightbeats.mp3
 *
 * Parça 138 sn ve seviyesi dalgalı. 70. saniyeden başlayan 61 saniyelik pencere
 * ölçümle en tutarlı bölüm (ortalama -11.7 dBFS, sapma 1.5 dB) ve sonunda
 * doğal olarak sönümleniyor — kapanışa yakışıyor.
 *
 * Seviye: seslendirmenin konuşma anlarındaki RMS'i -21.8 dBFS, müziğin bu
 * penceredeki RMS'i -11.7 dBFS. Anlatım altında müziği 16 dB aşağıda tutmak
 * için 0.05 kazanç gerekiyor. Anlatım bittikten sonra kapanışta yükseliyor.
 */
export const MUSIC = {
  /** Parçanın hangi karesinden başlanacağı (70 sn × 30 fps). */
  trimBefore: 2100,
  /** Anlatım altındaki kazanç. */
  bed: 0.043,
  /** Anlatım bittikten sonra kapanış kazancı. */
  tail: 0.12,
  /** Kapanış yükselişinin başladığı kare (son cümlenin bitişine yakın). */
  liftAt: 1742,
} as const;

/**
 * Seslendirme kazancı. Ham kayıt -1.5 dBFS tepe yapıyor; AAC kodlaması
 * bunu tam ölçeğe taşıyor. Instagram yeniden kodlarken kırpılma olmasın
 * diye ~1.3 dB tavan payı bırakıyoruz.
 */
export const VOICE_GAIN = 0.86;
