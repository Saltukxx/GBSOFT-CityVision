# Aerial etiketleme kılavuzu (DJI drone kareleri)

Etiketleyici: `.venv/bin/python scripts/label_aerial.py` → http://127.0.0.1:8765

Sınıflar: `1 Çukur (pothole)` · `2 Çatlak (road_crack)` · `3 Rögar (manhole)` · `4 Hasar (road_damage)` · `B Temiz kare`

Zoom: `+` / `−` · `0` sığdır · `9` (veya `1:1`) bire bir piksel · ⌘/Ctrl+tekerlek imlecin
olduğu yerden yakınlaşır. İnce çatlağı sığdırılmış görüntüde çizmeye çalışma, `9` ile aç.

Bu kılavuzun tek amacı **aynı nesneye her seferinde aynı ismi vermek**. Tutarsız etiket, modelin
çukuru hasara, hasarı rögara yuvarlamasının birinci sebebi.

## Karar ağacı

Bir işaret görünce sırayla sor:

1. **Dökme demir/beton kapak mı?** (yuvarlak veya kare, kenarı düzgün, üstünde döküm deseni)
   → `3 Rögar`. Asfalt bozuk olsun olmasın rögar rögardır.
2. **Kenarı belirgin, içi karanlık, gerçek bir oyuk mu?** (asfalt kopmuş, derinlik hissi var)
   → `1 Çukur`.
3. **Yüzey bozulmuş ama oyuk yok mu?** (yama, timsah çatlağı, sökülmüş üst tabaka, bozuk alan)
   → `4 Hasar`.
4. **İnce çizgisel çatlak mı?** (tek hat, boyuna/enine, alan değil çizgi)
   → `2 Çatlak`.
5. Hiçbiri değil → kutu çizme.

## Kare başına karar: hepsi, temiz, ya da atla

Etiketli bir karede kutu çizilmemiş her bölge modele "burada nesne yok" örneği olarak gider.
Yani karedeki üç rögardan ikisini çizip üçüncüsünü atlarsan, modele o rögarı **rögar değil**
diye öğretirsin. Eksik etiket yanlış etiketten daha çok zarar verir.

Bu yüzden her kare için üç seçenekten **biri**:

| Durum | Ne yap |
| --- | --- |
| Karedeki nesnelerin hepsini tanıyorum | **Hepsini** çiz, tek tanesini bile atlama |
| Karede hiçbir kusur ve hiç rögar yok | `B` (temiz kare) |
| Bir nesneden emin değilim / kare bulanık | `→` ile **hiç dokunmadan** atla |

Kısmi etiket yok. Karede net nesneler ve emin olmadığın bir nesne birlikte varsa, kareyi
kısmen etiketlemek yerine tamamen atla.

Boyut alt sınırı: 1:1 zoom'da bakıp ne olduğunu anlamadığın şeye kutu çizme. Önemli olan bu
kararı her karede aynı şekilde vermen; bazı karelerde belirsiz lekeleri çizip bazılarında
çizmemek modelin sınırı hiç öğrenememesine yol açar.

## Hangi kareyi açmalı: seçici ol

Kare seçiminde seçici, kare içinde eksiksiz. Kareler 1 sn aralıklı olduğu için aynı çukur
6-8 karede görünüyor; hepsini etiketlemek emeğin çoğunu tek nesneye yatırmak olur.

Nadir sınıfa göre seç: `road_crack` (16 kutu) ve `pothole` (39 kutu) içeren kareler,
`manhole` (177 kutu) içeren kareden çok daha değerli. `öncelik` filtresi bu sıralamayı
otomatik yapar.

## Sınıf tanımları

### 3 Rögar (manhole)

Rögar, menhol, ızgara, vana kapağı, telekom kapağı. Kenarı geometrik ve düzgündür.

- Kapağın **üstündeki** leke, çatlak, pas veya çökme **ayrı kutu almaz**. Sadece rögar kutusu çizilir.
- Kapak asfalttan çökmüş/yükselmişse hâlâ sadece `Rögar`. (Çökme iş emri konusu ama sınıfı değişmez.)
- Kapağın **etrafındaki** halka çatlak, kapaktan taşıyorsa ve belirgin bir alansa `4 Hasar` olarak
  ayrı çizilebilir; kapağı içine alacak şekilde çizilmez.
- Kutuyu kapağın dış kenarına oturt, gölgeyi dahil etme.

### 1 Çukur (pothole)

Asfaltın koptuğu, derinliği olan oyuk.

- İçi karanlık, kenarı düzensiz ve keskin. Su birikmişse yansıma olabilir.
- Sadece **oyuğun kendisi** kutuya girer, çevresindeki çatlak halkası değil.
- Yan yana birden fazla oyuk varsa her biri **ayrı** kutu.

### 4 Hasar (road_damage)

Yüzey bozulmuş ama oyuk yok.

- Asfalt yaması, siyah tamir izi, timsah (blok) çatlak alanı, sökülmüş üst tabaka, tekerlek izi
  deformasyonu, kaba dokulu düzensiz yüzey.
- Bunlar **alan** nesnesidir; kutu bozuk bölgenin tamamını kapsar.
- Bir yamanın içinde ayrıca çukur varsa: yamayı `Hasar`, çukuru `Çukur` olarak iki kutu çiz.

### 2 Çatlak (road_crack)

Tek hatlı ince çatlak: boyuna, enine veya diyagonal.

- **Parçalama kuralı:** Kesintisiz çatlak, kare içinde tek kutu; 2 m'den uzun kesintiler ayrı kutu.
- Çizgi boyunca dar bir kutu; çevresindeki temiz asfaltı içine alma.
- Çatlak ağı hâline gelmişse (blok/timsah) artık `4 Hasar`.

## Etiketlenmeyecekler

- Islak leke, su birikintisi (oyuk yoksa), kuruyan su izi
- Yağ/mazot lekesi, fren izi, lastik izi
- Yol çizgileri, yazı, ok, yaya geçidi, sarı/beyaz boya
- Gölge (ağaç, bina, direk, drone gölgesi)
- Kişi, araç, motosiklet, konteyner, bordür, kaldırım deseni
- Kar/toprak/moloz yığını (bunlar atık sınıfı, bu modelin işi değil)

## B — Temiz kare (arka plan)

Karede hiçbir kusur **ve hiç rögar** yoksa `B` tuşuna bas. Bu kare modele "burada aranan
hiçbir şey yok" örneği olarak gider ve yanlış alarmı azaltır.

**Önemli:** `B` sadece gerçekten temiz kareler için. Kareyi "kopyası zaten var" veya
"emin değilim" diye geçiyorsan `B` **basma**, `→` ile atla. Yanlış `B`, içinde rögar olan bir
kareyi modele "rögar yok" diye öğretir ve doğru tespitleri bastırır.

İyi `B` adayları: sağlam düz asfalt, ıslak leke, gölge, yol çizgisi, kaldırım, araç yoğun kare.

## Kutu çizme kuralları

- Kutu nesneye sıkı otursun; 2-3 px boşluk sorun değil, %50 fazla alan sorun.
- Yarısı kadraj dışında kalan nesneyi etiketle (görünen kısmı), ancak %20'den azı görünüyorsa geç.
- Çok bulanık / hareket lekesi olan karede emin olamadığın nesneyi etiketleme, kareyi atla.
- Aynı nesne iki farklı sınıfa aday görünüyorsa karar ağacındaki **ilk** uyan sınıfı seç.

## Revizyon modu

Filtre menüsünde `revizyon` seçildiğinde yalnız etiketli kareler gelir. Amaç `Çukur` ile `Hasar`
sınırını bu kılavuza göre yeniden geçmek: oyuk yoksa `Hasar`, oyuk varsa `Çukur`, kapak varsa `Rögar`.

## Öncelik modu

`öncelik` filtresi `scripts/queue_uncertain.py` çıktısını kullanır: modelin kararsız kaldığı,
modellerin çeliştiği ve çatlak adayı olan kareler önce gelir. Rastgele kare etiketlemek yerine
buradan gitmek aynı emekle daha çok kazandırır.

Kuyruğu üretmek için:

```bash
.venv/bin/python scripts/queue_uncertain.py
```
