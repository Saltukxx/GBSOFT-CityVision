from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "GBSoft_DJI_Dock_CityVision_Raporu.pdf"

W, H = A4
M = 42

GREEN_D = HexColor("#0A3B27")
GREEN = HexColor("#12603F")
GREEN_T = HexColor("#E8F1EB")
TURQ = HexColor("#0E9C9C")
TURQ_T = HexColor("#E1F2F1")
INK = HexColor("#0F2019")
INK_2 = HexColor("#33463E")
MUT = HexColor("#6C7C74")
MUT_2 = HexColor("#93A19A")
LINE = HexColor("#DCE3DD")
PAPER = HexColor("#FFFFFF")
PAPER_2 = HexColor("#F5F7F4")
SAND = HexColor("#B8862B")
SAND_T = HexColor("#F7EFDD")
BRICK = HexColor("#A8442F")
BRICK_T = HexColor("#F7E9E5")


def register_fonts() -> None:
    regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    italic = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
    pdfmetrics.registerFont(TTFont("GBRegular", regular))
    pdfmetrics.registerFont(TTFont("GBBold", bold))
    pdfmetrics.registerFont(TTFont("GBItalic", italic))


def wrap(text: str, width: float, font: str, size: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdfmetrics.stringWidth(candidate, font, size) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def text_block(c, text, x, y, width, size=10, leading=None, color=INK_2,
               font="GBRegular", max_lines=None):
    leading = leading or size * 1.35
    lines = wrap(text, width, font, size)
    if max_lines:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    yy = y
    for line in lines:
        c.drawString(x, yy, line)
        yy -= leading
    return yy


def rounded(c, x, y, w, h, fill=PAPER_2, stroke=LINE, radius=10, sw=0.8):
    c.setLineWidth(sw)
    c.setStrokeColor(stroke)
    c.setFillColor(fill)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def pill(c, text, x, y, fill=GREEN_T, color=GREEN, width=None):
    c.setFont("GBBold", 7.5)
    width = width or pdfmetrics.stringWidth(text, "GBBold", 7.5) + 18
    c.setFillColor(fill)
    c.roundRect(x, y, width, 18, 9, fill=1, stroke=0)
    c.setFillColor(color)
    c.drawCentredString(x + width / 2, y + 5.6, text)
    return width


def section_header(c, eyebrow, title, subtitle=None):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(TURQ)
    c.rect(M, H - 54, 24, 3, fill=1, stroke=0)
    c.setFillColor(TURQ)
    c.setFont("GBBold", 8.5)
    c.drawString(M + 32, H - 57, eyebrow.upper())
    c.setFillColor(INK)
    c.setFont("GBBold", 22)
    c.drawString(M, H - 90, title)
    if subtitle:
        text_block(c, subtitle, M, H - 111, W - 2 * M, 9.2, 12.5, MUT)


def footer(c, page_no, source_hint=None):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(M, 30, W - M, 30)
    c.setFont("GBRegular", 7.2)
    c.setFillColor(MUT)
    c.drawString(M, 17, "GBSoft · City Vision · DJI Dock değerlendirmesi")
    if source_hint:
        c.drawCentredString(W / 2, 17, source_hint)
    c.setFont("GBBold", 7.2)
    c.setFillColor(GREEN)
    c.drawRightString(W - M, 17, f"{page_no:02d}")


def bullet(c, text, x, y, width, color=INK_2, accent=TURQ, size=9.2):
    c.setFillColor(accent)
    c.circle(x + 3, y - 2.2, 2.2, fill=1, stroke=0)
    return text_block(c, text, x + 14, y, width - 14, size, size * 1.35, color)


def card(c, x, y, w, h, title, body, tag=None, fill=PAPER_2, accent=GREEN):
    rounded(c, x, y, w, h, fill, LINE, 11)
    c.setFillColor(accent)
    c.rect(x, y + h - 5, w, 5, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("GBBold", 11)
    c.drawString(x + 14, y + h - 27, title)
    if tag:
        pill(c, tag, x + 14, y + 12, TURQ_T, TURQ)
        body_y = y + h - 47
        text_block(c, body, x + 14, body_y, w - 28, 8.4, 11.4, INK_2)
    else:
        text_block(c, body, x + 14, y + h - 47, w - 28, 8.4, 11.4, INK_2)


def cover(c):
    image_path = ROOT / "docs" / "sunum" / "img" / "cover.jpg"
    if image_path.exists():
        img = ImageReader(str(image_path))
        c.drawImage(img, 0, 0, W, H, preserveAspectRatio=False, mask="auto")
    else:
        c.setFillColor(GREEN_D)
        c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(Color(0.02, 0.14, 0.09, alpha=0.89))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setStrokeColor(Color(0.4, 0.83, 0.77, alpha=0.28))
    c.setLineWidth(0.8)
    for i in range(8):
        c.line(M, 150 + i * 45, W - M, 150 + i * 45)
    for i in range(7):
        c.line(M + i * 82, 130, M + i * 82, H - 90)

    c.setFont("GBBold", 10)
    c.setFillColor(HexColor("#67D3C4"))
    c.drawString(M, H - 58, "GBSOFT · CITY VISION")
    c.setFont("GBBold", 31)
    c.setFillColor(white)
    c.drawString(M, H - 150, "DJI Dock ile")
    c.drawString(M, H - 189, "Otonom Belediye Operasyonu")
    c.setFont("GBRegular", 13)
    c.setFillColor(HexColor("#CFE4DA"))
    text_block(c,
               "Dock 3 + Matrice 4D/4TD ile yapılabilecekler, GBSoft entegrasyon mimarisi, yapay zekâ akışı, sınırlar ve üç kalemli maliyet görünümü.",
               M, H - 230, W - 2 * M, 12.5, 17, HexColor("#DDEBE4"), "GBRegular")

    pill(c, "TEKNİK VE TİCARİ DEĞERLENDİRME", M, 92,
         Color(0.4, 0.83, 0.77, alpha=0.16), HexColor("#8FE0D2"), 190)
    c.setFont("GBRegular", 8.5)
    c.setFillColor(HexColor("#B9CEC4"))
    c.drawString(M, 61, "Hazırlanma tarihi: 15 Ağustos 2026")
    c.drawRightString(W - M, 61, "Kaynaklar: DJI Enterprise · DJI Developer · SHGM")
    c.showPage()


def page_summary(c, n):
    section_header(c, "01 · Yönetici özeti", "Dock alırsak tam olarak ne kazanırız?",
                   "Dock, drone’u yalnızca uzaktan uçurulan bir araç olmaktan çıkarıp tekrarlanabilir, ölçülebilir ve zamanlanabilir bir belediye sensörüne dönüştürür.")

    rounded(c, M, H - 255, W - 2 * M, 115, GREEN_D, GREEN_D, 14)
    c.setFillColor(HexColor("#67D3C4"))
    c.setFont("GBBold", 9)
    c.drawString(M + 18, H - 168, "NET SONUÇ")
    c.setFillColor(white)
    c.setFont("GBBold", 18)
    c.drawString(M + 18, H - 198, "City Vision için doğru ilk kurulum:")
    c.setFillColor(HexColor("#8FE0D2"))
    c.drawString(M + 18, H - 224, "Dock 3 + Matrice 4D + GBSoft Cloud API")
    c.setFont("GBRegular", 8.2)
    c.setFillColor(HexColor("#CFE4DA"))
    c.drawRightString(W - M - 18, H - 244, "4TD yalnızca termal/gece senaryosu varsa")

    gap = 12
    cw = (W - 2 * M - 2 * gap) / 3
    y = H - 405
    card(c, M, y, cw, 125, "Planlı görev", "Saat, bölge veya olay bazlı uçuşlar otomatik başlar; rota, kamera açıları ve çekim noktaları tekrarlanır.", "OTOMASYON", PAPER_2, TURQ)
    card(c, M + cw + gap, y, cw, 125, "Sürekli veri", "Aynı alan aynı parametrelerle yeniden çekilir; değişiklik analizi ve trend raporu güvenilir hâle gelir.", "ÖLÇÜLEBİLİR", PAPER_2, GREEN)
    card(c, M + 2 * (cw + gap), y, cw, 125, "Merkezi kontrol", "Görev, telemetri, medya, AI bulgusu ve belediye iş emri tek GBSoft akışında birleşir.", "ENTEGRASYON", PAPER_2, SAND)

    rounded(c, M, 90, W - 2 * M, 82, TURQ_T, TURQ, 12)
    c.setFont("GBBold", 10.5)
    c.setFillColor(TURQ)
    c.drawString(M + 16, 145, "Dock’un gerçek değeri")
    text_block(c, "Daha iyi kamera satın almak değil; sahaya personel göndermeden aynı işi tekrar tekrar yaptırabilmek, veriyi otomatik alabilmek ve sonucu belediye operasyonuna bağlayabilmektir.", M + 16, 125, W - 2 * M - 32, 9.4, 13, INK_2)
    footer(c, n, "Kaynak [1] [2] [3]")
    c.showPage()


def page_change(c, n):
    section_header(c, "02 · Operasyon modeli", "Dock olmadan / Dock ile",
                   "Aşağıdaki fark, otonom rota uçuşu ile gerçekten uzaktan ve tekrarlanabilir operasyon arasındaki farktır.")

    colw = (W - 2 * M - 14) / 2
    x1, x2 = M, M + colw + 14
    y, h = 165, 515
    rounded(c, x1, y, colw, h, PAPER_2, LINE, 13)
    rounded(c, x2, y, colw, h, GREEN_T, GREEN, 13)
    c.setFillColor(MUT)
    c.setFont("GBBold", 9)
    c.drawString(x1 + 18, y + h - 30, "SADECE DRONE")
    c.setFillColor(INK)
    c.setFont("GBBold", 16)
    c.drawString(x1 + 18, y + h - 57, "Operatör sahada")
    c.setFillColor(GREEN)
    c.setFont("GBBold", 9)
    c.drawString(x2 + 18, y + h - 30, "DOCK 3 + DRONE")
    c.setFillColor(INK)
    c.setFont("GBBold", 16)
    c.drawString(x2 + 18, y + h - 57, "Operatör merkezde")

    left = [
        "Drone taşınır ve sahaya yerleştirilir.",
        "Batarya elle takılır ve değiştirilir.",
        "Kalkış öncesi hazırlık sahada yapılır.",
        "Görev otomatik uçabilir; başlatma insandadır.",
        "İniş sonrası drone toplanır ve şarj edilir.",
        "Kötü hava kararı operatör gözlemine dayanır.",
        "Tekrarlı görevler personel takvimine bağlıdır.",
    ]
    right = [
        "Drone hava şartlarına dayanıklı istasyonda bekler.",
        "Görev zamanı geldiğinde otomatik hazırlanır.",
        "Kapak açılır, sistem kontrolü ve kalkış yapılır.",
        "Planlanan rota ve kamera aksiyonları uygulanır.",
        "Drone hassas şekilde Dock’a iner ve şarj olur.",
        "Rüzgâr, yağış ve sıcaklık sensörleri görevi korur.",
        "Telemetri ve medya GBSoft’a otomatik aktarılır.",
    ]
    yy = y + h - 95
    for item in left:
        yy = bullet(c, item, x1 + 16, yy, colw - 32, MUT, MUT_2, 8.8) - 11
    yy = y + h - 95
    for item in right:
        yy = bullet(c, item, x2 + 16, yy, colw - 32, INK_2, GREEN, 8.8) - 11

    c.setFont("GBBold", 9.2)
    c.setFillColor(BRICK)
    c.drawString(x1 + 18, y + 22, "Personel başına görev kapasitesi sınırlı")
    c.setFillColor(GREEN)
    c.drawString(x2 + 18, y + 22, "Tekrarlı görev ve veri standardı güçlü")
    footer(c, n, "Kaynak [2] [3]")
    c.showPage()


def page_capabilities(c, n):
    section_header(c, "03 · Yetenek haritası", "Dock 3 ile yapılabilecekler",
                   "Yetkinlikler dört katmanda toplanır: uçuş otomasyonu, veri toplama, uzaktan operasyon ve kurumsal entegrasyon.")
    gap = 11
    cw = (W - 2 * M - 2 * gap) / 3
    ch = 142
    y1 = H - 295
    y2 = y1 - ch - 13
    items = [
        ("Zamanlanmış uçuş", "Günlük, haftalık veya olay tetiklemeli görev; aynı rotayı ve çekim parametrelerini tekrarlar.", "ROTA", TURQ),
        ("Uzaktan kalkış/iniş", "Görev merkezden başlatılır; hassas RTK ve görsel işaretlerle Dock’a dönüş yapılır.", "UZAKTAN", GREEN),
        ("Otomatik şarj", "Matrice 4D serisi %15’ten %95’e ideal koşullarda yaklaşık 27 dakikada şarj edilir.", "27 DK", SAND),
        ("Canlı görüntü", "Drone ve Dock kameraları izlenir; operatör gerektiğinde görevi durdurur veya müdahale eder.", "CANLI", TURQ),
        ("Medya aktarımı", "Fotoğraf, video ve termal medya merkezi sisteme alınır; arşiv ve analiz kuyruğu oluşturulur.", "VERİ", GREEN),
        ("Çoklu Dock akışı", "Bir drone birden fazla Dock arasında görev yapabilir; her Dock aynı anda yalnızca bir drone barındırır.", "FİLO", SAND),
    ]
    for i, item in enumerate(items):
        row = i // 3
        col = i % 3
        card(c, M + col * (cw + gap), y1 - row * (ch + 13), cw, ch, item[0], item[1], item[2], PAPER_2, item[3])

    rounded(c, M, 76, W - 2 * M, 64, BRICK_T, BRICK, 10)
    c.setFillColor(BRICK)
    c.setFont("GBBold", 9.5)
    c.drawString(M + 14, 117, "Kritik sınır")
    text_block(c, "Dock bataryayı fiziksel olarak değiştirmez ve elektrik kesildiğinde yedek batarya drone’u şarj etmez. Bir Dock bir drone barındırır; sürekli kesintisiz görev için yedeklilik ayrıca tasarlanmalıdır.", M + 14, 99, W - 2 * M - 28, 8.5, 11.3, INK_2)
    footer(c, n, "Kaynak [1] [2]")
    c.showPage()


def page_use_cases(c, n):
    section_header(c, "04 · Belediye senaryoları", "City Vision için en güçlü kullanım alanları",
                   "4D görsel haritalama ve denetim için; 4TD ise termal, gece ve acil durum görevleri için seçilmelidir.")
    usecases = [
        ("Yol ve altyapı", "Çukur, çatlak, yüzey bozulması, kazı ve bakım sonrası kontrol.", "4D"),
        ("Atık ve hafriyat", "Kaçak döküm, taşmış konteyner alanı, moloz ve çevre kirliliği.", "4D"),
        ("İmar ve yapılaşma", "Yeni yapı, çatı/cephe değişimi, ruhsat dışı alan ve dönemsel fark.", "4D"),
        ("Şantiye ilerleme", "Belediye yatırımı, yol yapımı, metraj ve görsel ilerleme raporu.", "4D"),
        ("Park ve yeşil alan", "Ağaç/bitki alanı değişimi, sulama sorunu ve park envanteri.", "4D"),
        ("Afet ve yangın", "Sıcak nokta, duman/yangın çevresi, riskli alan ve gece desteği.", "4TD"),
        ("Arama-kurtarma", "Gece, düşük ışık, termal insan/araç tespiti ve anons desteği.", "4TD"),
        ("Enerji ve bina", "Güneş paneli, ısı kaybı, çatı ve uzak mesafe görsel inceleme.", "4TD"),
    ]
    gap = 10
    cw = (W - 2 * M - gap) / 2
    ch = 105
    top = H - 240
    for i, (title, body, model) in enumerate(usecases):
        row, col = divmod(i, 2)
        x = M + col * (cw + gap)
        y = top - row * (ch + 10)
        fill = PAPER_2 if model == "4D" else TURQ_T
        accent = GREEN if model == "4D" else TURQ
        rounded(c, x, y, cw, ch, fill, LINE, 10)
        pill(c, model, x + cw - 48, y + ch - 31, accent, white, 32)
        c.setFillColor(INK)
        c.setFont("GBBold", 10.5)
        c.drawString(x + 13, y + ch - 27, title)
        text_block(c, body, x + 13, y + ch - 51, cw - 26, 8.3, 11, INK_2)
    footer(c, n, "Kaynak [2] [4]")
    c.showPage()


def page_lifecycle(c, n):
    section_header(c, "05 · Görev akışı", "Uçtan uca otonom görev yaşam döngüsü",
                   "GBSoft yalnızca uçuş komutu vermez; bulguyu belediye operasyonuna bağlayan tüm döngüyü yönetir.")

    steps = [
        ("01", "Planla", "Bölge, irtifa, hız, kamera ve güvenli dönüş parametreleri."),
        ("02", "Kontrol", "Hava, batarya, Dock, GNSS, bağlantı ve izin penceresi."),
        ("03", "Uçur", "Kapak açılır; rota ve çekim aksiyonları otomatik uygulanır."),
        ("04", "Aktar", "Medya, telemetri, olay ve sağlık verileri GBSoft’a gelir."),
        ("05", "Analiz et", "AI tespit, segmentasyon, değişiklik ve risk skoru üretir."),
        ("06", "İş emri", "İnsan onayı sonrası birim, ekip ve SLA ile görev açılır."),
        ("07", "Doğrula", "Onarım sonrası tekrar uçuş; önce/sonra kanıtı ve kapanış."),
    ]
    start_y = H - 174
    x_line = M + 34
    c.setStrokeColor(LINE)
    c.setLineWidth(2)
    c.line(x_line, 113, x_line, start_y + 6)
    yy = start_y
    for num, title, body in steps:
        c.setFillColor(GREEN if num not in ("04", "05") else TURQ)
        c.circle(x_line, yy, 15, fill=1, stroke=0)
        c.setFont("GBBold", 7.5)
        c.setFillColor(white)
        c.drawCentredString(x_line, yy - 2.5, num)
        c.setFont("GBBold", 11)
        c.setFillColor(INK)
        c.drawString(x_line + 30, yy + 4, title)
        text_block(c, body, x_line + 120, yy + 4, W - M - (x_line + 120), 8.8, 11.5, INK_2)
        yy -= 70

    rounded(c, M + 320, 86, W - M - (M + 320), 70, GREEN_T, GREEN, 10)
    c.setFillColor(GREEN)
    c.setFont("GBBold", 9)
    c.drawString(M + 335, 132, "Öğrenme döngüsü")
    text_block(c, "Her doğrulama, model güvenini ve sonraki görev planını iyileştirir.", M + 335, 113, W - M - (M + 350), 8.2, 11, INK_2)
    footer(c, n, "Kaynak [3] [5]")
    c.showPage()


def page_architecture(c, n):
    section_header(c, "06 · Yazılım mimarisi", "GBSoft Dock entegrasyonu",
                   "DJI Cloud API; MQTT, HTTPS ve WebSocket üzerinden Dock’u üçüncü taraf bulut platformuna bağlar.")

    nodes = [
        (M, H - 250, 115, 96, "DOCK 3", "Drone, sensör, şarj ve saha kamerası", GREEN_D, white),
        (M + 145, H - 250, 115, 96, "CLOUD API", "MQTT · HTTPS · WebSocket", TURQ, white),
        (M + 290, H - 250, 115, 96, "GBSOFT CORE", "Görev, yetki, olay ve kayıt", GREEN, white),
        (M + 435, H - 250, 75, 96, "CITY VISION", "Harita ve iş emri", SAND, white),
    ]
    for x, y, w, h, title, body, fill, color in nodes:
        rounded(c, x, y, w, h, fill, fill, 12)
        c.setFillColor(color)
        c.setFont("GBBold", 9.5)
        c.drawCentredString(x + w / 2, y + h - 27, title)
        lines = wrap(body, w - 20, "GBRegular", 7.8)
        c.setFont("GBRegular", 7.8)
        yy = y + h - 49
        for line in lines:
            c.drawCentredString(x + w / 2, yy, line)
            yy -= 10.5
    c.setStrokeColor(MUT_2)
    c.setLineWidth(1.2)
    for x in (M + 115, M + 260, M + 405):
        c.line(x + 5, H - 202, x + 25, H - 202)
        c.setFillColor(MUT_2)
        c.setStrokeColor(MUT_2)
        p = c.beginPath()
        p.moveTo(x + 25, H - 202)
        p.lineTo(x + 18, H - 198)
        p.lineTo(x + 18, H - 206)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    subcards = [
        ("Görev yönetimi", "Rota sürümü, zamanlama, güvenlik kontrolü, durdurma ve tekrar uçuş."),
        ("Veri katmanı", "Nesne depolama, PostGIS, medya ilişkisi, değişiklik geçmişi ve denetim izi."),
        ("AI servisleri", "Çukur/atık/yapı tespiti, termal anomali, güven skoru ve insan doğrulaması."),
        ("Belediye akışı", "Birim yönlendirme, iş emri, SLA, ekip/araç atama ve kapanış kanıtı."),
    ]
    gap = 10
    cw = (W - 2 * M - gap) / 2
    for i, (title, body) in enumerate(subcards):
        row, col = divmod(i, 2)
        card(c, M + col * (cw + gap), 275 - row * 125, cw, 112, title, body, None, PAPER_2, TURQ if i == 2 else GREEN)

    rounded(c, M, 68, W - 2 * M, 57, SAND_T, SAND, 10)
    c.setFont("GBBold", 9)
    c.setFillColor(SAND)
    c.drawString(M + 14, 103, "Bağımlılık kararı")
    text_block(c, "Kendi yazılımınızı geliştirdiğiniz için FlightHub 2 Enterprise zorunlu değildir. Cloud API üretim omurgası, FlightHub 2 ise devreye alma veya yedek operasyon aracı olabilir.", M + 14, 85, W - 2 * M - 28, 8.3, 11, INK_2)
    footer(c, n, "Kaynak [3] [5] [6]")
    c.showPage()


def page_ai(c, n):
    section_header(c, "07 · Yapay zekâ", "AI nerede ve nasıl çalışmalı?",
                   "Başlangıçta güvenli ve ekonomik yaklaşım: görev sonrası sunucu analizi + operatör onayı.")

    tiers = [
        ("A", "Görev sonrası analiz", "Fotoğraflar inişten sonra aktarılır. Çukur, atık, yapı ve değişiklik analizi yapılır.", "ÖNERİLEN BAŞLANGIÇ", GREEN, GREEN_T),
        ("B", "Canlı yayın analizi", "Video akışı GPU’ya gelir. Yangın, kayıp kişi ve güvenlik olayında anlık alarm üretilir.", "ACİL DURUM", TURQ, TURQ_T),
        ("C", "Drone üzerinde AI", "Manifold 3 veya on-board yeteneklerle düşük gecikmeli özel algoritma çalıştırılır.", "İLERİ AŞAMA", SAND, SAND_T),
    ]
    yy = H - 250
    for letter, title, body, tag, accent, fill in tiers:
        rounded(c, M, yy, W - 2 * M, 122, fill, accent, 13)
        c.setFillColor(accent)
        c.circle(M + 34, yy + 61, 20, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("GBBold", 14)
        c.drawCentredString(M + 34, yy + 56, letter)
        c.setFillColor(INK)
        c.setFont("GBBold", 13)
        c.drawString(M + 70, yy + 82, title)
        pill(c, tag, W - M - 125, yy + 75, accent, white, 112)
        text_block(c, body, M + 70, yy + 56, W - 2 * M - 90, 8.8, 12, INK_2)
        yy -= 139

    rounded(c, M, 72, W - 2 * M, 76, BRICK_T, BRICK, 10)
    c.setFont("GBBold", 9.3)
    c.setFillColor(BRICK)
    c.drawString(M + 14, 124, "Güvenlik ilkesi")
    text_block(c, "İlk sürümde AI bulguyu üretmeli; uçuş rotasını tek başına değiştirmemelidir. AI tespit eder, operatör onaylar, gerekiyorsa yeni yakın inceleme görevi oluşturulur.", M + 14, 104, W - 2 * M - 28, 8.5, 11.4, INK_2)
    footer(c, n, "Kaynak [6] [7]")
    c.showPage()


def page_limits(c, n):
    section_header(c, "08 · Sınırlar ve güvenlik", "Otonom demek sınırsız demek değildir",
                   "Teknik kapasite; hava sahası izni, şehir engelleri, bağlantı, batarya ve insan gözetimiyle birlikte değerlendirilmelidir.")

    facts = [
        ("10 km", "DJI’ın ideal koşullardaki azami operasyon yarıçapı; şehir garantisi değildir."),
        ("54 dk", "Matrice 4D serisinin kontrollü koşullardaki azami ileri uçuş süresi."),
        ("12 m/s", "Dock 3 için azami izin verilen kalkış/iniş rüzgârı."),
        ("1 drone", "Her Dock aynı anda yalnızca bir drone barındırır."),
    ]
    gap = 9
    cw = (W - 2 * M - 3 * gap) / 4
    for i, (big, body) in enumerate(facts):
        x = M + i * (cw + gap)
        rounded(c, x, H - 260, cw, 125, PAPER_2, LINE, 10)
        c.setFillColor(GREEN if i != 0 else TURQ)
        c.setFont("GBBold", 20)
        c.drawCentredString(x + cw / 2, H - 180, big)
        lines = wrap(body, cw - 20, "GBRegular", 7.6)
        c.setFillColor(MUT)
        c.setFont("GBRegular", 7.6)
        yy = H - 204
        for line in lines:
            c.drawCentredString(x + cw / 2, yy, line)
            yy -= 10

    rounded(c, M, H - 465, W - 2 * M, 175, GREEN_T, GREEN, 12)
    c.setFillColor(GREEN)
    c.setFont("GBBold", 11)
    c.drawString(M + 16, H - 320, "Şehir içinde proje varsayımı")
    y = H - 346
    for item in [
        "Yoğun yapılaşmada ilk planlama yarıçapını 2-3 km kabul edin.",
        "Açık ilçede 3-5 km, saha keşfi ve izinle doğrulanabilir.",
        "10 km değerini satış vaadi değil teknik üst sınır olarak kullanın.",
        "Elektrik, internet ve güvenli iniş koridoru saha seçiminin temelidir.",
    ]:
        y = bullet(c, item, M + 16, y, W - 2 * M - 32, INK_2, GREEN, 8.7) - 8

    rounded(c, M, 84, W - 2 * M, 98, BRICK_T, BRICK, 11)
    c.setFillColor(BRICK)
    c.setFont("GBBold", 10)
    c.drawString(M + 16, 154, "Türkiye operasyonu")
    text_block(c, "Matrice 4D serisi 500 g üzerindedir. SHGM ticari operasyonlarda kayıt, yetkili pilot ve uçuş izni gerekliliklerini belirtir; meskûn ve kalabalık bölgelerde uçuş izni zorunludur. Dock otomasyonu bu yükümlülükleri kaldırmaz.", M + 16, 134, W - 2 * M - 32, 8.5, 11.5, INK_2)
    footer(c, n, "Kaynak [1] [8]")
    c.showPage()


def page_cost(c, n):
    section_header(c, "09 · Maliyet", "Yalnızca üç maliyet kalemi",
                   "Kullanıcı talebi doğrultusunda kurulum, enerji, internet, sunucu, personel, izin ve yazılım geliştirme maliyetleri bu tabloda yoktur.")

    rows = [
        ("1", "Matrice 4D", "Drone + RC Plus 2", "6.763-6.885 €", "365-372 bin TL", "Görsel haritalama ve belediye denetimi için önerilen drone."),
        ("2", "DJI Dock 3", "Sadece Dock", "12.860 €", "yaklaşık 694 bin TL", "Otomatik saklama, kalkış, iniş, şarj ve saha bağlantısı."),
        ("3", "FlightHub 2 Enterprise", "1 yıl · 1 cihaz", "3.280 $", "yaklaşık 155 bin TL", "Opsiyonel; GBSoft Cloud API kullanıyorsa zorunlu değil."),
    ]
    y = H - 275
    for i, (num, title, scope, foreign, tl, note) in enumerate(rows):
        accent = (GREEN, TURQ, SAND)[i]
        fill = (GREEN_T, TURQ_T, SAND_T)[i]
        rounded(c, M, y, W - 2 * M, 123, fill, accent, 13)
        c.setFillColor(accent)
        c.circle(M + 27, y + 62, 16, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("GBBold", 10)
        c.drawCentredString(M + 27, y + 58, num)
        c.setFillColor(INK)
        c.setFont("GBBold", 13)
        c.drawString(M + 57, y + 84, title)
        c.setFillColor(MUT)
        c.setFont("GBRegular", 8)
        c.drawString(M + 57, y + 67, scope)
        c.setFillColor(accent)
        c.setFont("GBBold", 12)
        c.drawRightString(W - M - 18, y + 83, foreign)
        c.setFillColor(INK)
        c.setFont("GBBold", 9.5)
        c.drawRightString(W - M - 18, y + 64, tl)
        text_block(c, note, M + 57, y + 40, W - 2 * M - 75, 8.1, 10.5, INK_2)
        y -= 140

    rounded(c, M, 92, W - 2 * M, 88, GREEN_D, GREEN_D, 12)
    c.setFillColor(HexColor("#67D3C4"))
    c.setFont("GBBold", 9)
    c.drawString(M + 16, 153, "ÜÇ KALEM REFERANS TOPLAMI")
    c.setFillColor(white)
    c.setFont("GBBold", 17)
    c.drawString(M + 16, 126, "Yaklaşık 1,21-1,22 milyon TL")
    c.setFont("GBRegular", 7.8)
    c.setFillColor(HexColor("#CFE4DA"))
    c.drawRightString(W - M - 16, 128, "Türkiye vergi/bayi/teslim farkları hariç")

    c.setFont("GBRegular", 7.2)
    c.setFillColor(MUT)
    c.drawString(M, 72, "Kur varsayımı: 1 € ≈ 54 TL; 1 $ ≈ 47,4 TL. Referans fiyatlar kamuya açık Ağustos 2026 listeleridir.")
    footer(c, n, "Kaynak [9] [10] [11] [12]")
    c.showPage()


def page_recommendation(c, n):
    section_header(c, "10 · Uygulama planı", "GBSoft için önerilen yol",
                   "Tek Dock ile önce ölçülebilir bir belediye koridoru kanıtlanmalı; genişleme gerçek görev verisiyle yapılmalıdır.")

    phases = [
        ("1", "Pilot alan", "Bir belediye binası/tesisi, tek Dock 3, Matrice 4D ve sınırlı izin koridoru."),
        ("2", "Üç kullanım", "Yol hasarı, atık/hafriyat ve imar/değişiklik analizi; termal yok."),
        ("3", "GBSoft entegrasyonu", "Cloud API, medya alımı, görev ekranı, AI kuyruğu, harita ve iş emri."),
        ("4", "Operasyon kanıtı", "Görev başarı oranı, tespit doğruluğu, kapanan iş emri ve süre kazancı."),
        ("5", "Genişleme", "İkinci Dock, 4TD veya gerçek zamanlı AI yalnızca kanıtlanan ihtiyaçla."),
    ]
    y = H - 205
    for num, title, body in phases:
        c.setFillColor(GREEN if num != "3" else TURQ)
        c.roundRect(M, y - 13, 38, 38, 10, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("GBBold", 12)
        c.drawCentredString(M + 19, y, num)
        c.setFillColor(INK)
        c.setFont("GBBold", 11)
        c.drawString(M + 55, y + 9, title)
        text_block(c, body, M + 55, y - 8, W - M - (M + 55), 8.7, 11.5, INK_2)
        y -= 82

    rounded(c, M, 88, W - 2 * M, 112, GREEN_D, GREEN_D, 13)
    c.setFillColor(HexColor("#67D3C4"))
    c.setFont("GBBold", 9)
    c.drawString(M + 16, 172, "SATIN ALMA KARARI")
    c.setFillColor(white)
    c.setFont("GBBold", 16)
    c.drawString(M + 16, 145, "Dock 3 + Matrice 4D alınabilir.")
    text_block(c, "FlightHub 2 Enterprise ise GBSoft’un Cloud API tabanlı kendi operasyon paneli hedefleniyorsa zorunlu değildir; yalnızca kurumsal yedek/standart DJI işlevleri için ayrıca değerlendirilmelidir.", M + 16, 122, W - 2 * M - 32, 8.7, 11.6, HexColor("#DDEBE4"))
    footer(c, n, "Kaynak [3] [5] [6]")
    c.showPage()


def page_sources(c, n):
    section_header(c, "11 · Kaynakça", "Resmî ve kamuya açık kaynaklar",
                   "Teknik iddialarda DJI Enterprise/DJI Developer; Türkiye operasyonunda SHGM; fiyatlarda kamuya açık bayi ve 2026 liste verileri kullanılmıştır.")

    sources = [
        ("[1] DJI Dock 3 teknik özellikleri", "https://enterprise.dji.com/dock-3/specs"),
        ("[2] DJI Dock 3 ürün ve kullanım alanları", "https://enterprise.dji.com/dock-3"),
        ("[3] DJI Dock 3 sık sorulan sorular", "https://enterprise.dji.com/dock-3/faq"),
        ("[4] Matrice 4D/4TD kamera ve haritalama farkları", "https://enterprise.dji.com/dock-3/faq"),
        ("[5] DJI Cloud API", "https://developer.dji.com/cloud-api/"),
        ("[6] Cloud API desteklenen ürünler", "https://developer.dji.com/doc/cloud-api-tutorial/en/overview/product-support.html"),
        ("[7] DJI Payload SDK - AI canlı görüntü", "https://developer.dji.com/doc/payload-sdk-tutorial/en/function-overview/advanced-function/liveview-ai.html"),
        ("[8] SHGM ticari İHA işlemleri ve uçuş izinleri", "https://iha.shgm.gov.tr/public/ticari-islemler"),
        ("[9] DJI Paris - Dock 3 ve Matrice 4D fiyat listesi", "https://boutique.dji-paris.com/dock-3-c3740.html"),
        ("[10] AprFlyTech - Matrice 4D RC Plus 2 combo", "https://www.aprflytech.it/en/prodotti/dji-enterprise/djidock3"),
        ("[11] DJI 2026 kamuya açık ürün/fiyat listesi", "https://www.myvendorlink.com/external/vfile?d=vrf&ft=b&i=187&s=193823&sv=0&v=107153"),
        ("[12] ECB euro/dolar/TL referans kurları", "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"),
        ("[13] FlightHub 2 Enterprise resmî ürün sayfası", "https://store.dji.com/fr/product/dji-flighthub-2-enterprise-version-1-year-1-device"),
    ]
    y = H - 150
    for title, url in sources:
        c.setFillColor(INK)
        c.setFont("GBBold", 8.4)
        c.drawString(M, y, title)
        y -= 12
        y = text_block(c, url, M, y, W - 2 * M, 6.7, 9, MUT) - 9

    rounded(c, M, 61, W - 2 * M, 52, PAPER_2, LINE, 9)
    c.setFillColor(MUT)
    c.setFont("GBItalic", 7.2)
    text_block(c, "Not: Fiyatlar satın alma teklifi değildir; yalnızca kamuya açık liste referanslarıdır. Türkiye nihai fiyatı için yetkili DJI Enterprise bayisinden aynı kapsamda yazılı teklif alınmalıdır.", M + 12, 94, W - 2 * M - 24, 7.2, 9.5, MUT, "GBItalic")
    footer(c, n, "Erişim tarihi: 15 Ağustos 2026")
    c.showPage()


def build() -> None:
    register_fonts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("GBSoft - DJI Dock ile Otonom Belediye Operasyonu")
    c.setAuthor("GBSoft")
    c.setSubject("DJI Dock 3, Matrice 4D/4TD, City Vision entegrasyonu ve maliyet")

    cover(c)
    page_summary(c, 2)
    page_change(c, 3)
    page_capabilities(c, 4)
    page_use_cases(c, 5)
    page_lifecycle(c, 6)
    page_architecture(c, 7)
    page_ai(c, 8)
    page_limits(c, 9)
    page_cost(c, 10)
    page_recommendation(c, 11)
    page_sources(c, 12)
    c.save()
    print(OUT)


if __name__ == "__main__":
    build()
