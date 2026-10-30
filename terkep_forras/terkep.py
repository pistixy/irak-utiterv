"""Iraki Kurdisztán útvonal-térkép generátor.

Futtatás:  python terkep.py
Kimenet:   ../Irak_utvonal_terkep.png (és .jpg)

Háttér: Esri World Topo Map csempék (© Esri és adatszolgáltatói)
Útvonal: OSRM (router.project-osrm.org) valós úthálózaton számolva.
"""
import io, json, math, os, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)
CACHE = os.path.join(os.environ.get("TEMP", HERE), "irak_tiles")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "personal-itinerary-map/1.0"}
TS = 256

# ---------------------------------------------------------------- pontok
P = {
    "SUL":     (35.5617, 45.3168),
    "SULI":    (35.5622, 45.4254),
    "GOYZHA":  (35.5606, 45.4942),
    "HALABJA": (35.1860, 45.9735),
    "AHMADAWA": (35.3172, 46.0903),
    "BYARA":   (35.2308, 46.1206),
    "TAWELA":  (35.1994, 46.1861),
    "DUKAN":   (35.9537, 44.9533),
    "ERBIL":   (36.1914, 44.0093),
    "JERWAN":  (36.6699, 43.3939),
    "KHINIS":  (36.7549, 43.4115),
    "LALISH":  (36.7715, 43.3030),
    "DUHOK":   (36.8667, 42.9885),
    "AMEDI":   (37.0920, 43.4874),
    "AKRE":    (36.7305, 43.8749),
    "BEKHME":  (36.7034, 44.2786),
    "GAB":     (36.6317, 44.4458),
    "BEKHAL":  (36.6145, 44.4960),
    "RAWANDUZ": (36.6146, 44.5265),
    "SHAQLAWA": (36.4000, 44.3368),
    "AINKAWA": (36.2274, 43.9923),
    "EBL":     (36.2376, 43.9632),
}

DAYS = [
    ("1", "Nov 8 (Sun)", "Arrival, Sulaymaniyah", ["SUL", "SULI", "GOYZHA", "SULI"]),
    ("2", "Nov 9 (Mon)", "Halabja + Hawraman loop", ["SULI", "HALABJA", "TAWELA", "BYARA", "AHMADAWA", "SULI"]),
    ("3", "Nov 10 (Tue)", "Sulaymaniyah → Lake Dukan → Erbil", ["SULI", "DUKAN", "ERBIL"]),
    ("4", "Nov 11 (Wed)", "Erbil → Jerwan → Khinis → LALISH → Duhok", ["ERBIL", "JERWAN", "KHINIS", "LALISH", "DUHOK"]),
    ("5", "Nov 12 (Thu)", "Duhok → Amedi + Sulav", ["DUHOK", "AMEDI"]),
    ("6", "Nov 13 (Fri)", "Amedi → Akre → Bekhme → Gali Ali Beg → Rawanduz", ["AMEDI", "AKRE", "BEKHME", "GAB", "RAWANDUZ"]),
    ("7", "Nov 14 (Sat)", "Rawanduz → Bekhal → Shaqlawa → Erbil → airport", ["RAWANDUZ", "BEKHAL", "SHAQLAWA", "ERBIL", "AINKAWA", "EBL"]),
]

# (kulcs, sorszám, felirat-sorok, irány dx,dy a címkéhez, kiemelt?)
SIGHTS = [
    ("SULI", "1", ["Sulaymaniyah", "Amna Suraka, Slemani Museum, bazaar"], (1, 1), False),
    ("GOYZHA", "2", ["Goyzha Mountain", "sunset viewpoint"], (1, -1), False),
    ("HALABJA", "3", ["Halabja", "1988 memorial"], (-1, 0), False),
    ("TAWELA", "4", ["Tawela", "Hawraman terraced village"], (-1, 1), False),
    ("BYARA", "5", ["Byara", "Naqshbandi takiya"], (-1, -1), False),
    ("AHMADAWA", "6", ["Ahmad Awa", "waterfall, gorge"], (1, -1), False),
    ("DUKAN", "7", ["Lake Dukan", "dam, viewpoint"], (1, 0), False),
    ("ERBIL", "8", ["Erbil", "Citadel (UNESCO), Qaysari Bazaar"], (1, 1), False),
    ("JERWAN", "9", ["Jerwan", "Assyrian aqueduct (690 BC)"], (-1, 1), False),
    ("KHINIS", "10", ["Khinis", "Sennacherib rock reliefs"], (1, 1), False),
    ("LALISH", "11", ["LALISH", "holy town of the Yazidis"], (1, -1), True),
    ("DUHOK", "12", ["Duhok", "bazaar, Duhok Dam"], (-1, -1), False),
    ("AMEDI", "13", ["Amedi + Sulav", "clifftop town, Bab Zebar gate"], (1, -1), False),
    ("AKRE", "14", ["Akre", "terraced old town"], (-1, 1), False),
    ("BEKHME", "15", ["Bekhme Gorge", "Great Zab river"], (0, -1), False),
    ("GAB", "16", ["Gali Ali Beg", "gorge + waterfall"], (-1, 1), False),
    ("RAWANDUZ", "17", ["Rawanduz", "canyon, old town, Bekhal waterfall"], (1, -1), False),
    ("SHAQLAWA", "18", ["Shaqlawa", "orchard town, fruit market"], (1, 1), False),
]

SLEEPS = [
    ("SULI", ["Stay: Sulaymaniyah", "3 nights (Nov 7/8, 8, 9)"], (30, 175)),
    ("ERBIL", ["Stay: Erbil", "1 night (Nov 10)"], (90, -70)),
    ("DUHOK", ["Stay: Duhok", "1 night (Nov 11)"], (-60, 120)),
    ("AMEDI", ["Stay: Amedi / Sulav", "1 night (Nov 12)"], (-110, -80)),
    ("RAWANDUZ", ["Stay: Rawanduz", "1 night (Nov 13)"], (120, 70)),
    ("EBL", ["Last night: Erbil airport", "Nov 14/15"], (-70, 110)),
]

AIRPORTS = [
    ("SUL", ["ARRIVAL – Sulaymaniyah (ISU)", "Nov 8, 02:30"], (-1, -1)),
    ("EBL", ["DEPARTURE – Erbil (EBL)", "Nov 15, 06:30"], (-1, -1)),
]

# ---------------------------------------------------------------- színek, fontok
BLUE = (21, 101, 192)
BLUE_DARK = (13, 60, 130)
ORANGE = (230, 110, 20)
GOLD = (212, 160, 0)
PURPLE = (106, 27, 154)
RED = (198, 40, 40)
INK = (30, 30, 30)
WHITE = (255, 255, 255)

FD = r"C:\Windows\Fonts"
def F(name, size):
    return ImageFont.truetype(os.path.join(FD, name), size)


# ---------------------------------------------------------------- vetület, csempék
def px(lat, lon, z):
    n = 2 ** z * TS
    x = (lon + 180) / 360 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def tile(z, x, y):
    fn = os.path.join(CACHE, f"esri_{z}_{x}_{y}.jpg")
    if not os.path.exists(fn):
        url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
                open(fn, "wb").write(data)
                break
            except Exception as e:
                print("retry", url, e); time.sleep(2)
        time.sleep(0.05)
    return Image.open(fn).convert("RGB")


def basemap(z, lat_s, lon_w, lat_n, lon_e):
    x0, y0 = px(lat_n, lon_w, z)
    x1, y1 = px(lat_s, lon_e, z)
    tx0, ty0, tx1, ty1 = int(x0 // TS), int(y0 // TS), int(x1 // TS), int(y1 // TS)
    big = Image.new("RGB", ((tx1 - tx0 + 1) * TS, (ty1 - ty0 + 1) * TS))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            big.paste(tile(z, tx, ty), ((tx - tx0) * TS, (ty - ty0) * TS))
    ox, oy = x0 - tx0 * TS, y0 - ty0 * TS
    img = big.crop((int(ox), int(oy), int(ox + x1 - x0), int(oy + y1 - y0)))
    proj = lambda lat, lon: (px(lat, lon, z)[0] - x0, px(lat, lon, z)[1] - y0)
    return img, proj


# ---------------------------------------------------------------- útvonal
def route(keys):
    fn = os.path.join(CACHE, "route_" + "_".join(keys) + ".json")
    if os.path.exists(fn):
        return json.load(open(fn))
    coords = ";".join(f"{P[k][1]},{P[k][0]}" for k in keys)
    url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
    r = d["routes"][0]
    res = {"coords": r["geometry"]["coordinates"], "km": r["distance"] / 1000, "h": r["duration"] / 3600}
    json.dump(res, open(fn, "w"))
    time.sleep(1)
    return res


# ---------------------------------------------------------------- rajzoló segédek
def halo_text(d, xy, text, font, fill=INK, anchor="la", sw=6):
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=sw, stroke_fill=WHITE)


def label_block(d, x, y, lines, fonts, direction, gap=34, fills=None):
    """Címke a ponthoz képest direction=(dx,dy) irányban (-1/0/1)."""
    dx, dy = direction
    sizes = [d.textbbox((0, 0), t, font=f, stroke_width=6) for t, f in zip(lines, fonts)]
    w = max(b[2] - b[0] for b in sizes)
    hs = [b[3] - b[1] + 6 for b in sizes]
    h = sum(hs)
    if dx > 0: lx = x + gap
    elif dx < 0: lx = x - gap - w
    else: lx = x - w / 2
    if dy > 0: ly = y + gap * 0.6
    elif dy < 0: ly = y - gap * 0.6 - h
    else: ly = y - h / 2
    cy = ly
    for i, (t, f) in enumerate(zip(lines, fonts)):
        tw = sizes[i][2] - sizes[i][0]
        tx = lx if dx > 0 else (lx + w - tw if dx < 0 else lx + (w - tw) / 2)
        halo_text(d, (tx, cy), t, f, fill=(fills[i] if fills else INK))
        cy += hs[i]


def num_marker(d, x, y, n, r, color, font):
    d.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), fill=WHITE)
    d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    d.text((x, y + 1), n, font=font, fill=WHITE, anchor="mm")


def star(d, x, y, r, color):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    d.polygon(pts, fill=color, outline=WHITE, width=5)


def sleep_marker(d, x, y, s, font_sym):
    d.rounded_rectangle((x - s - 4, y - s - 4, x + s + 4, y + s + 4), radius=12, fill=WHITE)
    d.rounded_rectangle((x - s, y - s, x + s, y + s), radius=9, fill=PURPLE)
    d.text((x, y + 2), "☾", font=font_sym, fill=WHITE, anchor="mm")


def plane_marker(d, x, y, r, font_sym):
    d.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), fill=WHITE)
    d.ellipse((x - r, y - r, x + r, y + r), fill=RED)
    d.text((x, y + 1), "✈", font=font_sym, fill=WHITE, anchor="mm")


def polyline(d, pts, width, color):
    d.line(pts, fill=color, width=width, joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


# ---------------------------------------------------------------- fő térkép
def main():
    Z = 11
    img, proj = basemap(Z, 35.02, 42.55, 37.30, 46.32)
    img = img.convert("RGBA")
    W, H = img.size
    print("map size", W, H)

    routes = [route(d[3]) for d in DAYS]

    # útvonal: fehér kontúr + kék
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for r in routes:
        pts = [proj(lat, lon) for lon, lat in r["coords"]]
        polyline(d, pts, 20, (255, 255, 255, 230))
    for r in routes:
        pts = [proj(lat, lon) for lon, lat in r["coords"]]
        polyline(d, pts, 11, BLUE + (255,))
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)

    f_num = F("segoeuib.ttf", 30)
    f_lab = F("segoeuib.ttf", 40)
    f_sub = F("segoeui.ttf", 32)
    f_big = F("segoeuib.ttf", 58)
    f_bigsub = F("segoeuib.ttf", 38)
    f_sym = F("seguisym.ttf", 40)
    f_day = F("segoeuib.ttf", 34)

    # nap-jelölők az útvonalon (az adott nap geometriájának közepén)
    day_pos_override = {"1": 0.0, "2": 0.15, "3": 0.62, "4": 0.2, "5": 0.5, "6": 0.3, "7": 0.62}
    day_px_offset = {"1": (-130, 60)}
    for (n, date, _, _), r in zip(DAYS, routes):
        c = r["coords"][int(len(r["coords"]) * day_pos_override[n])]
        x, y = proj(c[1], c[0])
        ox, oy = day_px_offset.get(n, (0, 0))
        x, y = x + ox, y + oy
        txt = f"Day {n}"
        b = d.textbbox((0, 0), txt, font=f_day)
        w, h = b[2] - b[0] + 34, b[3] - b[1] + 22
        d.rounded_rectangle((x - w / 2 - 4, y - h / 2 - 4, x + w / 2 + 4, y + h / 2 + 4), radius=h / 2 + 4, fill=WHITE)
        d.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), radius=h / 2, fill=BLUE_DARK)
        d.text((x, y), txt, font=f_day, fill=WHITE, anchor="mm")

    # szállások
    for k, lines, (ox, oy) in SLEEPS:
        x, y = proj(*P[k])
        sx, sy = x + ox, y + oy
        d.line((x, y, sx, sy), fill=PURPLE, width=4)
        sleep_marker(d, sx, sy, 26, f_sym)
        label_block(d, sx, sy, lines, [F("segoeuib.ttf", 30), F("segoeui.ttf", 28)],
                    (1 if ox >= 0 else -1, 0), gap=40, fills=[PURPLE, PURPLE])

    # repterek
    for k, lines, dirn in AIRPORTS:
        x, y = proj(*P[k])
        plane_marker(d, x, y, 28, F("seguisym.ttf", 34))
        label_block(d, x, y, lines, [F("segoeuib.ttf", 34), F("segoeuib.ttf", 32)], dirn, gap=42, fills=[RED, RED])

    # látnivalók
    for k, n, lines, dirn, hl in SIGHTS:
        x, y = proj(*P[k])
        if hl:
            star(d, x, y, 58, GOLD)
            d.text((x, y + 6), n, font=f_num, fill=INK, anchor="mm")
            label_block(d, x, y, lines, [f_big, f_bigsub], dirn, gap=60, fills=[(150, 90, 0), (150, 90, 0)])
        else:
            num_marker(d, x, y, n, 24, ORANGE, f_num)
            label_block(d, x, y, lines, [f_lab, f_sub], dirn, gap=36)

    # forrásmegjelölés
    halo_text(d, (20, H - 50), "Basemap: © Esri, HERE, Garmin, OpenStreetMap contributors · Routing: OSRM / OpenStreetMap",
              F("segoeui.ttf", 28), fill=(80, 80, 80))

    # ----------------------------------------------------------- jobb oldali panel
    PW = 2100
    canvas = Image.new("RGB", (W + PW, H), (250, 248, 244))
    canvas.paste(img.convert("RGB"), (0, 0))
    c = ImageDraw.Draw(canvas)
    X = W + 80
    y = 70
    c.text((X, y), "IRAQI KURDISTAN", font=F("segoeuib.ttf", 96), fill=INK); y += 120
    c.text((X, y), "Backpacking loop · 8–15 November 2026", font=F("segoeui.ttf", 56), fill=(70, 70, 70)); y += 100
    c.line((X, y, W + PW - 80, y), fill=(200, 195, 185), width=4); y += 40

    # jelmagyarázat
    c.text((X, y), "Legend", font=F("segoeuib.ttf", 52), fill=INK); y += 85
    c.line((X, y + 18, X + 120, y + 18), fill=WHITE, width=22)
    c.line((X, y + 18, X + 120, y + 18), fill=BLUE, width=12)
    c.text((X + 160, y - 6), "Route (on the real road network)", font=F("segoeui.ttf", 44), fill=INK); y += 80
    num_marker(c, X + 60, y + 22, "5", 24, ORANGE, f_num)
    c.text((X + 160, y - 4), "Sight (number = visiting order)", font=F("segoeui.ttf", 44), fill=INK); y += 80
    star(c, X + 60, y + 22, 40, GOLD)
    c.text((X + 160, y - 4), "Lalish – the main goal", font=F("segoeui.ttf", 44), fill=INK); y += 85
    sleep_marker(c, X + 60, y + 22, 26, f_sym)
    c.text((X + 160, y - 4), "Overnight stay", font=F("segoeui.ttf", 44), fill=INK); y += 80
    plane_marker(c, X + 60, y + 22, 28, F("seguisym.ttf", 34))
    c.text((X + 160, y - 4), "Airport (arrival / departure)", font=F("segoeui.ttf", 44), fill=INK); y += 80
    c.rounded_rectangle((X + 10, y, X + 120, y + 46), radius=23, fill=BLUE_DARK)
    c.text((X + 65, y + 23), "Day 3", font=F("segoeuib.ttf", 26), fill=WHITE, anchor="mm")
    c.text((X + 160, y - 4), "Day marker on the route", font=F("segoeui.ttf", 44), fill=INK); y += 100
    c.line((X, y, W + PW - 80, y), fill=(200, 195, 185), width=4); y += 40

    # napi bontás
    c.text((X, y), "Day by day", font=F("segoeuib.ttf", 52), fill=INK); y += 85
    total = 0
    for (n, date, title, _), r in zip(DAYS, routes):
        total += r["km"]
        c.ellipse((X, y, X + 64, y + 64), fill=BLUE_DARK)
        c.text((X + 32, y + 33), n, font=F("segoeuib.ttf", 38), fill=WHITE, anchor="mm")
        c.text((X + 95, y - 6), date, font=F("segoeuib.ttf", 42), fill=BLUE_DARK)
        c.text((X + 450, y - 6), f"~{r['km']:.0f} km · ~{r['h']:.1f} h driving", font=F("segoeui.ttf", 38), fill=(90, 90, 90))
        c.text((X + 95, y + 48), title, font=F("segoeui.ttf", 40), fill=INK)
        y += 125
    c.text((X, y), f"Total approx. {total:.0f} km (pure driving time, no stops)", font=F("segoeuib.ttf", 40), fill=INK); y += 90
    c.line((X, y, W + PW - 80, y), fill=(200, 195, 185), width=4); y += 40

    # városi kivágatok
    insets = [
        ("Sulaymaniyah centre", 15, (35.5525, 45.4180, 35.5680, 45.4460), [
            ((35.5622, 45.4254), "Amna Suraka (Red Security)", (1, -1)),
            ((35.5573, 45.4257), "Slemani Museum", (1, 1)),
            ((35.5649, 45.4308), "Azadi Park", (1, -1)),
            ((35.5561, 45.4375), "Bazaar (Mawlawi St)", (0, 1)),
            ((35.5580, 45.4404), "Grand Mosque", (-1, -1)),
        ]),
        ("Erbil", 14, (36.170, 43.945, 36.247, 44.025), [
            ((36.1914, 44.0093), "Citadel", (-1, -1)),
            ((36.1885, 44.0092), "Qaysari Bazaar", (-1, 1)),
            ((36.1773, 44.0135), "Civilization Museum", (-1, 1)),
            ((36.1909, 43.9832), "Sami Abdulrahman Park", (-1, 1)),
            ((36.2274, 43.9923), "Ainkawa (St Joseph Church)", (-1, 1)),
            ((36.2376, 43.9632), "AIRPORT (EBL)", (1, -1)),
        ]),
    ]
    iw = (PW - 160 - 40) // 2
    ix = X
    iy0 = y
    bottom = y
    for title, z, (s, w_, n_, e), pts in insets:
        im, pj = basemap(z, s, w_, n_, e)
        scale = iw / im.width
        im = im.resize((iw, int(im.height * scale)), Image.LANCZOS)
        dd = ImageDraw.Draw(im)
        fi = F("segoeuib.ttf", 36)
        for i, ((la, lo), name, dirn) in enumerate(pts, 1):
            x, y2 = pj(la, lo)
            x, y2 = x * scale, y2 * scale
            if "AIRPORT" in name:
                plane_marker(dd, x, y2, 22, F("seguisym.ttf", 28))
            else:
                num_marker(dd, x, y2, str(i), 22, ORANGE, F("segoeuib.ttf", 28))
            label_block(dd, x, y2, [name], [fi], dirn, gap=26)
        c.text((ix, iy0), title, font=F("segoeuib.ttf", 46), fill=INK)
        canvas.paste(im, (ix, iy0 + 70))
        c.rectangle((ix, iy0 + 70, ix + im.width, iy0 + 70 + im.height), outline=(120, 120, 120), width=3)
        ix += iw + 40
        bottom = max(bottom, iy0 + 70 + im.height)

    # emlékeztető
    y = bottom + 70
    c.text((X, y), "Remember", font=F("segoeuib.ttf", 52), fill=INK); y += 85
    for t in [
        "Always carry your passport – many Peshmerga checkpoints",
        "Lalish: barefoot in the whole sanctuary, never step on thresholds",
        "Cash (USD + IQD) – cards are rarely accepted",
        "Avoid Turkish/Iranian border zones (villages above Amedi, Haji Omaran)",
        "Erbil airport: outer pre-check, be there ~3 h before departure",
    ]:
        c.text((X, y), "•  " + t, font=F("segoeui.ttf", 40), fill=INK); y += 62
    print("panel bottom", y)

    out = os.path.join(OUT_DIR, "Irak_utvonal_terkep.png")
    canvas.save(out, optimize=True)
    canvas.save(os.path.join(OUT_DIR, "Irak_utvonal_terkep.jpg"), quality=90)
    for (n, date, title, _), r in zip(DAYS, routes):
        print(n, date, title, f"{r['km']:.0f} km {r['h']:.1f} h")
    print("saved", out, canvas.size)


if __name__ == "__main__":
    main()
