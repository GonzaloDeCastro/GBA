"""Genera arte y datos del mundo para PAMPA SALVAJE (todo original, reemplazable).
Uso: python tools/gen_assets.py   (desde la carpeta del proyecto)

Estilo: pixel art de 16 colores con contorno oscuro y sombreado en 3 tonos
(luz desde arriba-izquierda), como en las portatiles de la epoca.
"""
import json, math, os, random, struct
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX = os.path.join(ROOT, "graphics")
INC = os.path.join(ROOT, "include")
os.makedirs(GFX, exist_ok=True)
os.makedirs(INC, exist_ok=True)


# ------------------------------------------------------------------ utilidades
def write_bmp(path, img, pal, bpp):
    """Escribe un BMP indexado de 4 u 8 bpp (img es una imagen PIL modo 'P')."""
    w, h = img.size
    px = img.tobytes()
    ncol = 16 if bpp == 4 else 256
    pal = list(pal) + [(0, 0, 0)] * (ncol - len(pal))
    stride = ((w * bpp + 31) // 32) * 4
    rows = []
    for y in range(h - 1, -1, -1):
        row = px[y * w:(y + 1) * w]
        if bpp == 8:
            data = bytes(row)
        else:
            data = bytes((row[i] << 4) | (row[i + 1] if i + 1 < w else 0) for i in range(0, w, 2))
        rows.append(data.ljust(stride, b"\0"))
    body = b"".join(rows)
    palb = b"".join(struct.pack("BBBB", b, g, r, 0) for (r, g, b) in pal)
    off = 14 + 40 + len(palb)
    hdr = b"BM" + struct.pack("<IHHI", off + len(body), 0, 0, off)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, bpp, 0, len(body), 2835, 2835, ncol, ncol)
    with open(path, "wb") as f:
        f.write(hdr + info + palb + body)


def write_json(name, data):
    with open(os.path.join(GFX, name + ".json"), "w") as f:
        json.dump(data, f, indent=4)


class SD:
    """Proxy de dibujo: permite dibujar con coordenadas de 32x32 sobre un lienzo de 64x64 (escala k)."""

    def __init__(self, d, k):
        self.d, self.k = d, k

    def _b(self, box):
        k = self.k
        x0, y0, x1, y1 = box
        return [x0 * k, y0 * k, x1 * k + k - 1, y1 * k + k - 1]

    def _p(self, pts):
        k = self.k
        if pts and not isinstance(pts[0], (tuple, list)):
            pts = list(zip(pts[0::2], pts[1::2]))
        return [(x * k + (k - 1) / 2, y * k + (k - 1) / 2) for x, y in pts]

    def rectangle(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(self._b(box), fill=fill, outline=outline, width=width * self.k)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._b(box), fill=fill, outline=outline, width=width * self.k)

    def rounded_rectangle(self, box, r, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self._b(box), r * self.k, fill=fill, outline=outline, width=width * self.k)

    def polygon(self, pts, fill=None, outline=None):
        self.d.polygon(self._p(pts), fill=fill, outline=outline)

    def line(self, pts, fill=None, width=1):
        self.d.line(self._p(pts), fill=fill, width=max(1, width * self.k))

    def point(self, xy, fill=None):
        k = self.k
        x, y = xy
        self.d.rectangle([x * k, y * k, x * k + k - 1, y * k + k - 1], fill=fill)


class Canvas:
    """Lienzo indexado con capas sombreadas automaticamente y contorno.
    k = 1: pixel art clasico (personajes). k = 2: lienzo del doble de resolucion (animales de 64x64),
    con reborde sombreado mas grueso y tramado entre tonos para un degradado suave."""

    def __init__(self, w, h, k=1):
        self.w, self.h, self.k = w, h, k
        self.im = Image.new("P", (w, h), 0)

    def part(self, fn, base, shade=None, light=None, thick=1):
        w, h, k = self.w, self.h, self.k
        m = Image.new("1", (w, h), 0)
        d = ImageDraw.Draw(m)
        fn(SD(d, k) if k > 1 else d)
        mp = m.load()

        def inm(x, y):
            return 0 <= x < w and 0 <= y < h and mp[x, y]

        out = self.im.load()
        for y in range(h):
            for x in range(w):
                if not inm(x, y):
                    continue
                c = base
                if k == 1:
                    if shade is not None and not (inm(x, y + 1) and inm(x + 1, y) and inm(x + 1, y + 1)):
                        c = shade
                    elif shade is not None and thick >= 2 and not (inm(x, y + 2) and inm(x + 2, y)):
                        c = shade
                    elif light is not None and not (inm(x - 1, y) and inm(x, y - 1)):
                        c = light
                else:
                    if shade is not None:
                        ds = 1
                        while ds <= 3 * k + 2 and inm(x, y + ds) and inm(x + ds, y) and inm(x + ds, y + ds):
                            ds += 1
                        rim = k + (1 if thick >= 2 else 0)
                        if ds <= rim:
                            c = shade
                        elif thick >= 2 and ds <= rim + 2 * k and (x + y) % 2 == 0:
                            c = shade                              # tramado -> transicion suave
                    if c == base and light is not None:
                        dl = 1
                        while dl <= 2 * k + 1 and inm(x - dl, y) and inm(x, y - dl):
                            dl += 1
                        if dl <= 1 + (k - 1):
                            c = light
                        elif thick >= 2 and dl <= 1 + 2 * k and (x + y) % 2 == 0:
                            c = light
                out[x, y] = c

    def outline(self, color=1):
        px = self.im.load()
        marks = []
        for y in range(self.h):
            for x in range(self.w):
                if px[x, y] != 0:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and px[nx, ny] not in (0, color):
                        marks.append((x, y))
                        break
        for x, y in marks:
            px[x, y] = color

    def draw(self):
        d = ImageDraw.Draw(self.im)
        return SD(d, self.k) if self.k > 1 else d

    def raw(self):
        return ImageDraw.Draw(self.im)


# Convencion de indices en las paletas de los sprites:
# 0 transparente, 1 contorno, 2/3/4 cuerpo base/sombra/luz, 5/6/7 secundario base/sombra/luz,
# 8 blanco, 9 negro (ojos), 10 acento 1, 11 acento 2, 12 detalle oscuro, 13..15 extras
OUT, B, BS, BL, C, CS, CL, WHT, K, A, A2, D = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12


def spr_pal(*cols):
    pal = [(255, 0, 255), (28, 22, 30)]
    pal += list(cols)
    return pal + [(0, 0, 0)] * (16 - len(pal))


# ------------------------------------------------------------------ mundo
BG_PAL = [(255, 0, 255),
          (128, 208, 96), (96, 176, 72), (64, 136, 56), (40, 96, 48),         # 1-4 verdes
          (176, 220, 255), (88, 152, 236), (52, 108, 200),                     # 5-7 agua
          (240, 224, 170), (216, 188, 128), (176, 140, 88),                    # 8-10 arena
          (150, 80, 48),                                                       # 11 madera / teja
          (196, 196, 206), (140, 140, 156), (88, 88, 106),                     # 12-14 piedra
          (30, 44, 38)]                                                        # 15 contorno
MM_PAL = [(255, 0, 255), (104, 184, 80), (46, 120, 54), (56, 100, 200), (26, 66, 36), (150, 150, 156),
          (88, 88, 98), (232, 208, 150), (196, 160, 100), (250, 250, 250), (230, 40, 40)]

T_PASTO, T_ALTO, T_AGUA, T_ARBOL, T_CAMINO, T_ROCA, T_ARENA, T_ESTEPA, T_CASA, T_PUERTA, T_VET, T_VETPUERTA = range(12)
W = H = 64  # metatiles de 16x16 -> 1024x1024 px


def meta_tile(t, v, nb):
    """Dibuja un metatile 16x16. nb = (N, E, S, W) -> True si el vecino es de la misma familia."""
    rng = random.Random(t * 1000 + v * 17 + sum(1 << i for i, b in enumerate(nb) if b))
    im = Image.new("P", (16, 16), 2)
    d = ImageDraw.Draw(im)
    px = im.load()
    n, e, s, w = nb

    def edge_dist(x, y):
        """distancia al borde mas cercano que NO es de la misma familia"""
        best = 99
        if not n: best = min(best, y)
        if not s: best = min(best, 15 - y)
        if not w: best = min(best, x)
        if not e: best = min(best, 15 - x)
        return best

    if t in (T_PASTO, T_ARBOL, T_CASA, T_PUERTA, T_VET, T_VETPUERTA):
        d.rectangle([0, 0, 15, 15], fill=2)
        for _ in range(5):
            x, y = rng.randrange(1, 14), rng.randrange(1, 15)
            px[x, y] = 3; px[x + 1, y] = 3; px[x, y - 1] = 1
        if v == 1:
            fx, fy = rng.randrange(2, 13), rng.randrange(3, 13)
            px[fx, fy] = 8; px[fx, fy + 1] = 3
    if t == T_ALTO:
        d.rectangle([0, 0, 15, 15], fill=3)
        for bx in (1, 5, 9, 13):
            for by in (5, 12):
                yy = by + ((bx + v) % 3) - 1
                for k in range(4):
                    px[bx, max(0, yy - k)] = 4
                px[bx - 1 if bx > 0 else bx, max(0, yy - 3)] = 1
                px[min(15, bx + 1), max(0, yy - 2)] = 2
                px[min(15, bx + 1), max(0, yy - 3)] = 1
    elif t == T_AGUA:
        d.rectangle([0, 0, 15, 15], fill=6)
        for _ in range(3):
            x, y = rng.randrange(1, 11), rng.randrange(2, 14)
            d.line([x, y, x + 3, y], fill=5)
            d.line([x + 1, y + 1, x + 4, y + 1], fill=7)
        for y in range(16):
            for x in range(16):
                dist = edge_dist(x, y)
                if dist == 0: px[x, y] = 8
                elif dist == 1: px[x, y] = 9
                elif dist == 2: px[x, y] = 5
    elif t == T_ARBOL:
        d.ellipse([3, 11, 13, 15], fill=3)                        # sombra
        d.rectangle([7, 10, 8, 14], fill=11)                      # tronco
        d.rectangle([6, 14, 9, 14], fill=11)
        d.ellipse([1, 0, 14, 11], fill=15)                        # contorno copa
        d.ellipse([2, 1, 13, 10], fill=3)
        d.ellipse([3, 4, 13, 10], fill=4)                         # sombra copa
        d.ellipse([3, 1, 10, 7], fill=2)
        d.ellipse([4, 2, 8, 5], fill=1)
        px[11, 5] = 2
    elif t == T_CASA or t == T_VET:                               # parte de arriba: techo
        roof, roof_hi = (11, 10) if t == T_CASA else (7, 6)
        d.ellipse([0, 12, 15, 15], fill=3)
        d.polygon([(0, 15), (8, 0), (15, 15)], fill=15)           # contorno
        d.polygon([(2, 14), (8, 2), (13, 14)], fill=roof)
        d.line([3, 13, 8, 3], fill=roof_hi)
        d.line([4, 14, 8, 6], fill=roof_hi)
        d.line([8, 3, 12, 13], fill=15)
        d.rectangle([0, 14, 15, 15], fill=15)
        d.rectangle([1, 14, 14, 14], fill=roof)
        if t == T_CASA:
            d.rectangle([11, 1, 12, 5], fill=14)                  # chimenea
            d.rectangle([11, 1, 12, 1], fill=12)
        else:
            d.rectangle([6, 6, 9, 11], fill=8 if False else 12)   # cruz sobre el techo
            d.rectangle([4, 8, 11, 9], fill=12)
            d.rectangle([7, 7, 8, 10], fill=11)
            d.rectangle([5, 8, 10, 9], fill=11)
    elif t == T_PUERTA or t == T_VETPUERTA:                      # parte de abajo: pared con puerta
        wall, wall_s = (8, 9) if t == T_PUERTA else (12, 13)
        d.rectangle([1, 0, 14, 15], fill=15)
        d.rectangle([2, 0, 13, 14], fill=wall)
        d.rectangle([2, 11, 13, 14], fill=wall_s)
        d.rectangle([6, 5, 9, 15], fill=15)                       # puerta
        d.rectangle([7, 6, 8, 15], fill=11 if t == T_PUERTA else 7)
        d.point((8, 11), fill=wall)
        d.rectangle([3, 3, 5, 6], fill=15); d.point((4, 4), fill=5); d.point((4, 5), fill=5)
        d.rectangle([10, 3, 12, 6], fill=15); d.point((11, 4), fill=5); d.point((11, 5), fill=5)
        d.ellipse([0, 13, 15, 15], fill=3)
        d.rectangle([4, 15, 11, 15], fill=9)                      # felpudo
        if t == T_VETPUERTA:
            d.rectangle([7, 1, 8, 3], fill=11); d.rectangle([6, 2, 9, 2], fill=11)
    elif t == T_CAMINO:
        d.rectangle([0, 0, 15, 15], fill=9)
        for _ in range(7):
            x, y = rng.randrange(1, 15), rng.randrange(1, 15)
            px[x, y] = 10 if rng.random() < 0.6 else 8
        for y in range(16):
            for x in range(16):
                dist = edge_dist(x, y)
                if dist == 0: px[x, y] = 10
                elif dist == 1 and (x + y) % 2 == 0: px[x, y] = 10
    elif t == T_ROCA:
        d.rectangle([0, 0, 15, 15], fill=13)
        for _ in range(5):
            x, y = rng.randrange(1, 13), rng.randrange(2, 14)
            d.line([x, y, x + 2, y], fill=12)
            d.line([x + 1, y + 1, x + 3, y + 1], fill=14)
        if v == 1:
            d.polygon([(2, 12), (6, 5), (10, 12)], fill=12)
            d.line([6, 5, 6, 12], fill=14)
        for y in range(16):
            for x in range(16):
                dist = edge_dist(x, y)
                if not n and y == 1: px[x, y] = 12
                if not n and y == 0: px[x, y] = 15
                if not s and y >= 14: px[x, y] = 14 if y == 14 else 15
                if not w and x == 0: px[x, y] = 15
                if not e and x == 15: px[x, y] = 15
    elif t == T_ARENA:
        d.rectangle([0, 0, 15, 15], fill=8)
        for _ in range(6):
            x, y = rng.randrange(1, 15), rng.randrange(1, 15)
            px[x, y] = 9
            if rng.random() < 0.4:
                px[x + 1 if x < 15 else x, y] = 9
    elif t == T_ESTEPA:
        d.rectangle([0, 0, 15, 15], fill=9)
        for _ in range(4):
            x, y = rng.randrange(1, 14), rng.randrange(1, 15)
            px[x, y] = 10
        for bx, by in ((3, 6 + v), (10, 13 - v), (12, 5)):
            for k in range(3):
                px[bx, by - k] = 4
            px[bx - 1, by - 2] = 3
            px[bx + 1, by - 2] = 3
            px[bx - 2, by - 3] = 2
            px[bx + 2, by - 3] = 2
            px[bx, by - 3] = 1
    return im


FAMILY = {T_AGUA: "w", T_ROCA: "r", T_CAMINO: "c"}


def make_world():
    rng = random.Random(1853)
    m = [[T_PASTO] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if y < 22:      # Norte: Chaco / NOA
                m[y][x] = T_ALTO if rng.random() < 0.28 else (T_ARBOL if rng.random() < 0.10 else T_PASTO)
            elif y < 44:    # Pampa
                m[y][x] = T_ALTO if rng.random() < 0.22 else T_PASTO
            else:           # Patagonia
                m[y][x] = T_ESTEPA if rng.random() < 0.55 else T_ARENA
    for _ in range(40):
        cx, cy, r = rng.randrange(8, 56), rng.randrange(2, 62), rng.randrange(2, 4)
        for y in range(max(0, cy - r), min(H, cy + r)):
            for x in range(max(0, cx - r), min(W, cx + r)):
                if m[y][x] in (T_PASTO, T_ARENA):
                    m[y][x] = T_ESTEPA if y >= 44 else T_ALTO
    for y in range(H):
        wdt = 3 + (y * 7 % 5 < 2) + (1 if y < 22 else 0)
        for x in range(wdt):
            m[y][x] = T_ROCA
        if wdt + 1 < W and rng.random() < 0.5:
            m[y][wdt] = T_ROCA
    for y in range(H):
        sea = 59 + (1 if y % 7 == 0 else 0) - (1 if y % 11 == 0 else 0)
        for x in range(W):
            if x >= sea:
                m[y][x] = T_AGUA
            elif x >= sea - 2:
                m[y][x] = T_ARENA
    rx = 51
    for y in range(0, 42):
        rx += rng.choice([-1, 0, 0, 1])
        rx = max(48, min(54, rx))
        for dx in range(2):
            m[y][rx + dx] = T_AGUA
    for y in range(52, 58):
        for x in range(14, 22):
            if (x - 18) ** 2 + (y - 55) ** 2 * 2 < 14:
                m[y][x] = T_AGUA
    for y in range(H):
        if m[y][32] != T_AGUA:
            m[y][32] = T_CAMINO
    for x in range(5, 58):
        if m[30][x] != T_AGUA:
            m[30][x] = T_CAMINO
    for x in range(5, 58):
        if m[30][x] == T_AGUA and x < 56:
            m[30][x] = T_CAMINO
    for y in range(28, 33):
        for x in range(30, 35):
            if m[y][x] != T_CAMINO:
                m[y][x] = T_PASTO

    # Pueblos: se despeja el area y se levantan los edificios (se pintan aparte; aca va la colision)
    for (x0, y0, x1, y1) in VILLAGE_AREAS:
        ground = T_ARENA if y0 >= 43 else T_PASTO
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if 0 < x < W - 1 and 0 < y < H - 1 and m[y][x] != T_CAMINO:
                    m[y][x] = ground
    for kind, _variant, bx, by in BUILDINGS:
        bw, bh, dc = (VET_W, VET_H, VET_DOOR_COL) if kind == "vet" else (HOUSE_W, HOUSE_H, HOUSE_DOOR_COL)
        for yy in range(by, by + bh):
            for xx in range(bx, bx + bw):
                m[yy][xx] = T_VET if kind == "vet" else T_CASA
        m[by + bh - 1][bx + dc] = T_VETPUERTA if kind == "vet" else T_PUERTA
    # Los NPC estan siempre sobre piso transitable
    for (nx, ny, _d) in NPCS:
        if m[ny][nx] != T_CAMINO:
            m[ny][nx] = T_ARENA if ny >= 44 else T_PASTO
    return m


# Edificios: (tipo, variante de color, casillero x, casillero y) - esquina superior izquierda
BUILDINGS = [
    ("vet", 0, 36, 25), ("house", 0, 42, 25), ("house", 1, 36, 33), ("house", 2, 42, 33),   # Estancia (Pampa)
    ("vet", 0, 22, 6), ("house", 1, 28, 6), ("house", 0, 28, 10),                           # Puesto del Norte
    ("vet", 0, 46, 45), ("house", 2, 52, 45), ("house", 1, 46, 50),                         # Caleta austral
    ("vet", 0, 11, 33), ("house", 0, 17, 33),                                                # Refugio andino
]
# Zonas que se despejan para cada pueblo: (x0, y0, x1, y1)
VILLAGE_AREAS = [(33, 23, 47, 37), (20, 4, 31, 14), (44, 43, 57, 54), (9, 31, 22, 39)]
# NPCs: (tx, ty, direccion 0 abajo 1 arriba 2 izq 3 der); el orden coincide con la tabla de main.cpp
NPCS = [
    (34, 29, 2),   # 0 Don Segundo
    (27, 12, 0),   # 1 Guardaparque Lila
    (52, 51, 3),   # 2 Pescador Beto
    (32, 21, 0),   # 3 Gaucho Tomas (rival)
    (37, 30, 0),   # 4 Profe Ana
    (13, 37, 1),   # 5 Wara, andinista
]


def export_world(m):
    big = Image.new("P", (W * 16, H * 16), 2)
    cache = {}

    def same(t, x, y):
        if not (0 <= x < W and 0 <= y < H):
            return True       # el borde del mapa se considera continuo
        o = m[y][x]
        f = FAMILY.get(t)
        return f is not None and FAMILY.get(o) == f

    for y in range(H):
        for x in range(W):
            t = m[y][x]
            if t >= T_CASA:
                t = T_PASTO      # los edificios se pintan aparte sobre el pasto
            nb = (same(t, x, y - 1), same(t, x + 1, y), same(t, x, y + 1), same(t, x - 1, y))
            v = (x * 7 + y * 13) % 2
            key = (t, v, nb)
            if key not in cache:
                cache[key] = meta_tile(t, v, nb)
            big.paste(cache[key], (x * 16, y * 16))
    # edificios grandes pintados sobre el pasto
    arts = {}
    for kind, variant, bx, by in BUILDINGS:
        key = (kind, variant)
        if key not in arts:
            art = vet_art() if kind == "vet" else house_art(variant)
            mask = Image.new("L", art.size, 0)
            mask.putdata([255 if p else 0 for p in art.getdata()])
            arts[key] = (art, mask)
        art, mask = arts[key]
        big.paste(art, (bx * 16, by * 16), mask)
    write_bmp(os.path.join(GFX, "world.bmp"), big, BG_PAL, 4)
    write_json("world", {"type": "regular_bg"})

    export_argmap()
    mk = Image.new("P", (8, 8), 0)
    ImageDraw.Draw(mk).ellipse([1, 1, 6, 6], fill=3, outline=2)
    write_bmp(os.path.join(GFX, "marker.bmp"), mk, [(255, 0, 255), (20, 16, 24), (250, 250, 250), (230, 40, 40)], 4)
    write_json("marker", {"type": "sprite"})

    flat = ",".join(str(m[y][x]) for y in range(H) for x in range(W))
    with open(os.path.join(INC, "world_data.h"), "w") as f:
        f.write("// Generado por tools/gen_assets.py. No editar a mano.\n#ifndef WORLD_DATA_H\n#define WORLD_DATA_H\n\n")
        f.write("namespace world\n{\n")
        f.write(f"    inline constexpr int width = {W};\n    inline constexpr int height = {H};\n")
        f.write(f"    inline constexpr unsigned char tiles[{W * H}] = {{{flat}}};\n")
        f.write(f"    inline constexpr int npc_count = {len(NPCS)};\n")
        f.write("    inline constexpr int npc_tx[] = {" + ",".join(str(n[0]) for n in NPCS) + "};\n")
        f.write("    inline constexpr int npc_ty[] = {" + ",".join(str(n[1]) for n in NPCS) + "};\n")
        f.write("    inline constexpr int npc_dir[] = {" + ",".join(str(n[2]) for n in NPCS) + "};\n}\n\n#endif\n")


# ------------------------------------------------------------------ personajes 16x16 (caminan en 4 direcciones)
# Indices de paleta: 0 transp, 1 contorno, 2 piel, 3 piel sombra, 4 sombrero, 5 sombrero luz, 6 poncho,
# 7 poncho sombra, 8 franja, 9 pantalon, 10 pantalon sombra, 11 botas, 12 pelo, 13 ojos, 14 blanco, 15 acento
def char_pal(skin, skin_s, hat, hat_l, pon, pon_s, stripe, pants, pants_s, boots, hair,
             accent=(240, 200, 80), eye=(20, 16, 24), white=(250, 250, 250)):
    return [(255, 0, 255), (28, 22, 30), skin, skin_s, hat, hat_l, pon, pon_s, stripe, pants, pants_s, boots, hair,
            eye, white, accent]


CHARS = {
    "player": dict(pal=char_pal((240, 190, 150), (200, 140, 104), (92, 56, 36), (140, 92, 56), (206, 52, 60), (150, 32, 48),
                                (250, 240, 220), (66, 82, 120), (46, 56, 90), (60, 40, 30), (50, 34, 26)),
                   hat="sombrero", garment="poncho", extra=None),
    "npc0": dict(pal=char_pal((232, 176, 136), (190, 130, 98), (40, 40, 48), (80, 80, 96), (60, 90, 170), (40, 60, 130),
                              (250, 240, 220), (200, 180, 140), (160, 140, 104), (60, 40, 30), (110, 100, 100)),
                 hat="sombrero", garment="poncho", extra="mustache"),                      # Don Segundo
    "npc1": dict(pal=char_pal((240, 200, 170), (200, 150, 120), (60, 110, 70), (96, 156, 100), (90, 140, 80), (60, 100, 60),
                              (240, 220, 80), (120, 90, 60), (90, 66, 44), (50, 36, 28), (90, 56, 36)),
                 hat="gorra", garment="vest", extra="braid"),                              # Lila guardaparque
    "npc2": dict(pal=char_pal((210, 150, 110), (170, 112, 80), (240, 200, 60), (255, 226, 110), (70, 110, 150), (50, 80, 120),
                              (250, 240, 220), (60, 70, 90), (40, 50, 70), (40, 30, 28), (60, 40, 30)),
                 hat="sombrero", garment="vest", extra="beard"),                           # Beto pescador
    "npc3": dict(pal=char_pal((236, 186, 150), (196, 140, 106), (50, 30, 30), (100, 60, 50), (50, 50, 60), (30, 30, 40),
                              (210, 50, 50), (60, 60, 70), (40, 40, 50), (30, 20, 20), (40, 24, 20)),
                 hat="sombrero", garment="poncho", extra=None),                            # Tomas rival
    "npc4": dict(pal=char_pal((240, 196, 170), (200, 150, 124), (130, 70, 150), (170, 110, 190), (200, 120, 200), (150, 80, 160),
                              (250, 240, 250), (90, 60, 110), (60, 40, 80), (50, 30, 50), (80, 40, 90)),
                 hat="none", garment="coat", extra="bun", glasses=True),                  # Profe Ana
    "npc5": dict(pal=char_pal((200, 140, 100), (160, 104, 72), (220, 90, 50), (250, 140, 80), (50, 150, 150), (30, 110, 110),
                              (250, 210, 60), (110, 70, 50), (80, 50, 36), (40, 28, 24), (30, 20, 20)),
                 hat="chullo", garment="poncho", extra=None),                              # Wara andinista
    "npc6": dict(pal=char_pal((240, 200, 170), (200, 150, 124), (250, 250, 250), (220, 230, 240), (250, 250, 252), (200, 210, 224),
                              (70, 130, 210), (70, 90, 130), (50, 66, 100), (50, 40, 40), (60, 40, 30),
                              accent=(230, 60, 60)),
                 hat="none", garment="coat", extra="stethoscope"),                         # Dra. Lucia (veterinaria)
    "npc7": dict(pal=char_pal((240, 200, 170), (200, 150, 124), (170, 170, 176), (210, 210, 216), (230, 130, 150), (180, 90, 110),
                              (250, 230, 240), (110, 80, 110), (80, 56, 80), (60, 40, 40), (200, 200, 206)),
                 hat="none", garment="poncho", extra="bun"),                               # Abuela Rosa
    "npc8": dict(pal=char_pal((236, 186, 150), (196, 140, 106), (60, 140, 220), (110, 180, 250), (240, 200, 60), (200, 160, 30),
                              (250, 250, 250), (60, 90, 150), (40, 60, 110), (240, 240, 240), (90, 56, 36)),
                 hat="gorra", garment="vest", extra=None),                                 # Tomi (nene)
    "npc9": dict(pal=char_pal((222, 166, 126), (182, 124, 92), (200, 170, 110), (230, 200, 140), (130, 90, 60), (96, 64, 40),
                              (230, 210, 170), (90, 80, 70), (66, 58, 50), (50, 36, 28), (150, 140, 130)),
                 hat="sombrero", garment="vest", extra="mustache"),                        # Don Anselmo
}


def make_char(spec, direction, step):
    """16x16 (tamano clasico). direction: 0 abajo, 1 arriba, 2 izquierda, 3 derecha. step: 0 quieto, 1 pie izq, 2 pie der."""
    c = Canvas(16, 16)
    P = c.part
    bob = 1 if step else 0
    oy = -bob                      # al dar un paso el cuerpo sube 1 px

    def R(x0, y0, x1, y1):
        return lambda d: d.rectangle([x0, y0, x1, y1], fill=1)

    def RR(x0, y0, x1, y1, r):
        return lambda d: d.rounded_rectangle([x0, y0, x1, y1], r, fill=1)

    def E(x0, y0, x1, y1):
        return lambda d: d.ellipse([x0, y0, x1, y1], fill=1)

    def PG(pts):
        return lambda d: d.polygon(pts, fill=1)

    front = direction in (0, 1)
    garment = spec["garment"]
    hat = spec["hat"]
    extra = spec.get("extra")

    # --- piernas y botas
    if front:
        bots = {0: (15, 15), 1: (15, 14), 2: (14, 15)}[step]
        for x0, x1, bot in ((5, 6, bots[0]), (9, 10, bots[1])):
            P(R(x0, 13, x1, bot), 9, 10)
            P(R(x0, bot, x1, bot), 11)
    else:
        sh = {0: (0, 0), 1: (-1, 1), 2: (1, -1)}[step]      # (pierna delantera, trasera)
        P(R(7 + sh[1], 13, 9 + sh[1], 15), 10, 10)
        P(R(7 + sh[1], 15, 9 + sh[1], 15), 11)
        P(R(6 + sh[0], 13, 8 + sh[0], 15), 9, 10)
        P(R(5 + sh[0], 15, 8 + sh[0], 15), 11)

    # --- torso
    if garment == "poncho":
        pts = [(3, 9 + oy), (12, 9 + oy), (14, 13 + oy), (1, 13 + oy)] if front else \
              [(3, 9 + oy), (12, 9 + oy), (13, 13 + oy), (2, 13 + oy)]
        P(PG(pts), 6, 7)
        P(R(2, 11 + oy, 13, 11 + oy), 8)
    elif garment == "vest":
        P(R(3, 9 + oy, 4, 12 + oy), 14, 14)
        P(R(11, 9 + oy, 12, 12 + oy), 14, 14)
        P(R(4, 9 + oy, 11, 13 + oy), 6, 7)
        P(R(7, 10 + oy, 8, 12 + oy), 8)
        P(R(3, 12 + oy, 4, 13 + oy), 2)
        P(R(11, 12 + oy, 12, 13 + oy), 2)
    else:   # coat (guardapolvo / saco)
        P(R(3, 9 + oy, 12, 13 + oy), 6, 7)
        if front:
            P(R(7, 10 + oy, 8, 13 + oy), 8)
        P(R(2, 11 + oy, 3, 13 + oy), 6)
        P(R(12, 11 + oy, 13, 13 + oy), 6)
    # --- cabeza
    if direction == 2:
        P(RR(3, 4 + oy, 10, 9 + oy, 2), 2, 3)
    else:
        P(RR(4, 4 + oy, 11, 9 + oy, 2), 2, 3)
    if direction == 1:
        P(RR(4, 4 + oy, 11, 9 + oy, 2), 12)
    elif hat == "none":
        P(RR(3, 2 + oy, 12, 6 + oy, 2), 12)
        if extra == "bun":
            P(E(6, 0 + oy, 9, 3 + oy), 12)
    # --- sombrero
    if hat == "sombrero":
        P(E(1, 2 + oy, 14, 5 + oy), 4, 4, 5)
        P(RR(4, 0 + oy, 11, 4 + oy, 2), 4, 4, 5)
        P(R(4, 3 + oy, 11, 3 + oy), 12)
    elif hat == "gorra":
        P(RR(3, 1 + oy, 12, 5 + oy, 2), 4, 4, 5)
        if direction == 0 or direction == 3:
            P(R(3, 5 + oy, 12, 5 + oy), 4)
        elif direction == 2:
            P(R(1, 5 + oy, 8, 5 + oy), 4)
    elif hat == "chullo":
        P(E(2, 0 + oy, 13, 6 + oy), 4, 4, 5)
        P(R(2, 3 + oy, 13, 3 + oy), 8)
        P(R(2, 6 + oy, 3, 9 + oy), 4)
        P(R(12, 6 + oy, 13, 9 + oy), 4)
    if extra == "braid" and direction in (1, 2, 3):
        P(R(11 if direction != 3 else 3, 7 + oy, 12 if direction != 3 else 4, 12 + oy), 12)
    c.outline(OUT)

    # --- detalles de la cara (sobre el contorno)
    dr = c.draw()
    if direction == 0:
        dr.point((6, 6 + oy), fill=13); dr.point((9, 6 + oy), fill=13)
        dr.point((7, 8 + oy), fill=3); dr.point((8, 8 + oy), fill=3)
        if extra == "mustache":
            dr.rectangle([6, 8 + oy, 9, 8 + oy], fill=12)
        if extra == "beard":
            dr.rectangle([5, 8 + oy, 10, 9 + oy], fill=12)
        if spec.get("glasses"):
            dr.point((5, 6 + oy), fill=1); dr.point((7, 6 + oy), fill=1)
            dr.point((8, 6 + oy), fill=1); dr.point((10, 6 + oy), fill=1)
        if extra == "stethoscope":
            dr.point((5, 10 + oy), fill=15); dr.point((10, 10 + oy), fill=15)
            dr.point((6, 12 + oy), fill=15); dr.point((9, 12 + oy), fill=15)
    elif direction == 2:
        dr.point((5, 6 + oy), fill=13)
        dr.point((3, 7 + oy), fill=3)
        if extra == "mustache":
            dr.rectangle([4, 8 + oy, 5, 8 + oy], fill=12)
        if extra == "beard":
            dr.rectangle([3, 8 + oy, 6, 9 + oy], fill=12)
        if spec.get("glasses"):
            dr.point((4, 6 + oy), fill=1); dr.point((6, 6 + oy), fill=1)
    if direction == 3:
        c.im = c.im.transpose(Image.FLIP_LEFT_RIGHT)
    return c.im


def export_characters():
    # jugador: 4 direcciones x [quieto, pie izq, quieto, pie der] = 16 cuadros de 16x16
    seq = (0, 1, 0, 2)
    sheet = Image.new("P", (16, 16 * 16), 0)
    for dr_ in range(4):
        for k, st in enumerate(seq):
            sheet.paste(make_char(CHARS["player"], dr_, st), (0, 16 * (dr_ * 4 + k)))
    write_bmp(os.path.join(GFX, "player.bmp"), sheet, CHARS["player"]["pal"], 4)
    write_json("player", {"type": "sprite", "height": 16})

    # NPCs: una pose quieta por direccion
    for i in range(10):
        key = f"npc{i}"
        sheet = Image.new("P", (16, 16 * 4), 0)
        for dr_ in range(4):
            sheet.paste(make_char(CHARS[key], dr_, 0), (0, 16 * dr_))
        write_bmp(os.path.join(GFX, key + ".bmp"), sheet, CHARS[key]["pal"], 4)
        write_json(key, {"type": "sprite", "height": 16})


# ------------------------------------------------------------------ edificios grandes (se pintan sobre el mapa)
# Casas de 4x3 casilleros (64x48 px) y veterinaria de 5x3 (80x48). La puerta esta en el casillero de abajo.
HOUSE_W, HOUSE_H, HOUSE_DOOR_COL = 4, 3, 1
VET_W, VET_H, VET_DOOR_COL = 5, 3, 2
ROOFS = [(11, 10), (13, 12), (10, 9)]       # (base, luz): teja, gris piedra, arena oscura


def _roof_lines(d, pts_left, pts_right, y0, y1, light):
    for y in range(y0, y1, 4):
        t = (y - y0) / max(1, (y1 - y0))
        xl = int(pts_left[0] + (pts_left[1] - pts_left[0]) * t)
        xr = int(pts_right[0] + (pts_right[1] - pts_right[0]) * t)
        d.line([xl + 1, y, xr - 1, y], fill=light)


def house_art(variant):
    base, light = ROOFS[variant % len(ROOFS)]
    im = Image.new("P", (64, 48), 0)
    d = ImageDraw.Draw(im)
    d.ellipse([2, 40, 62, 47], fill=3)                                 # sombra sobre el pasto
    d.rectangle([43, 0, 51, 12], fill=15)                              # chimenea (detras del techo)
    d.rectangle([44, 1, 50, 12], fill=13)
    d.rectangle([42, 0, 52, 2], fill=15); d.rectangle([43, 1, 51, 2], fill=12)
    d.rectangle([4, 26, 59, 46], fill=15)                              # pared
    d.rectangle([5, 27, 58, 44], fill=8)
    d.rectangle([5, 38, 58, 44], fill=9)
    d.rectangle([4, 43, 59, 46], fill=15); d.rectangle([5, 44, 58, 45], fill=13)
    d.polygon([(0, 29), (10, 4), (53, 4), (63, 29)], fill=15)          # techo
    d.polygon([(2, 27), (11, 6), (52, 6), (61, 27)], fill=base)
    _roof_lines(d, (10, 2), (53, 61), 9, 27, light)
    for y in range(11, 27, 4):                                          # tejas
        for x in range(8 + (y // 4 % 2) * 4, 58, 8):
            if 11 - (y - 6) * 9 / 21 + 2 < x < 52 + (y - 6) * 9 / 21 - 2:
                d.point((x, y + 1), fill=15)
    d.line([11, 6, 52, 6], fill=light)
    d.rectangle([3, 28, 60, 30], fill=15); d.rectangle([4, 28, 59, 29], fill=base)   # alero
    d.rectangle([4, 30, 59, 31], fill=10)                               # sombra del alero
    for wx in (8, 46):                                                  # ventanas con postigos
        d.rectangle([wx - 1, 33, wx + 10, 42], fill=15)
        d.rectangle([wx, 34, wx + 9, 41], fill=5)
        d.line([wx + 4, 34, wx + 4, 41], fill=15); d.line([wx + 5, 34, wx + 5, 41], fill=15)
        d.line([wx, 37, wx + 9, 37], fill=15)
        d.rectangle([wx - 3, 33, wx - 2, 42], fill=11); d.rectangle([wx + 11, 33, wx + 12, 42], fill=11)
    d.rectangle([18, 32, 29, 47], fill=15)                              # puerta
    d.rectangle([19, 33, 28, 47], fill=11)
    d.rectangle([21, 35, 26, 40], fill=10)
    d.point((26, 43), fill=8)
    d.rectangle([17, 46, 30, 47], fill=12)                              # escalon
    return im


def vet_art():
    im = Image.new("P", (80, 48), 0)
    d = ImageDraw.Draw(im)
    d.ellipse([2, 40, 78, 47], fill=3)
    d.rectangle([4, 26, 75, 46], fill=15)                               # pared blanca
    d.rectangle([5, 27, 74, 44], fill=12)
    d.rectangle([5, 38, 74, 44], fill=13)
    d.rectangle([5, 31, 74, 33], fill=6)                                # franja azul
    d.rectangle([4, 43, 75, 46], fill=15); d.rectangle([5, 44, 74, 45], fill=14)
    d.polygon([(0, 29), (12, 4), (67, 4), (79, 29)], fill=15)           # techo azul
    d.polygon([(2, 27), (13, 6), (66, 6), (77, 27)], fill=7)
    _roof_lines(d, (12, 2), (67, 77), 9, 27, 6)
    d.line([13, 6, 66, 6], fill=6)
    d.rectangle([3, 28, 76, 30], fill=15); d.rectangle([4, 28, 75, 29], fill=7)
    d.rectangle([4, 30, 75, 31], fill=14)
    d.rectangle([29, 7, 50, 25], fill=15)                               # cartel con cruz
    d.rectangle([30, 8, 49, 24], fill=12)
    d.rectangle([37, 10, 42, 22], fill=11)
    d.rectangle([32, 14, 47, 18], fill=11)
    for wx in (9, 57):
        d.rectangle([wx - 1, 35, wx + 12, 43], fill=15)
        d.rectangle([wx, 36, wx + 11, 42], fill=5)
        d.line([wx + 5, 36, wx + 5, 42], fill=15); d.line([wx + 6, 36, wx + 6, 42], fill=15)
    d.rectangle([32, 32, 47, 47], fill=15)                              # puerta doble de vidrio
    d.rectangle([33, 33, 46, 47], fill=5)
    d.line([39, 33, 39, 47], fill=15); d.line([40, 33, 40, 47], fill=15)
    d.rectangle([33, 33, 46, 35], fill=6)
    d.rectangle([31, 46, 48, 47], fill=12)
    return im


# ------------------------------------------------------------------ perrito 16x16 (4 cuadros por direccion)
DOG_PAL = spr_pal((214, 168, 100), (168, 120, 64), (240, 204, 140), (248, 240, 224), (214, 204, 190),
                  (255, 255, 255), (250, 250, 250), (20, 16, 24), (210, 50, 50), (150, 30, 40), (120, 76, 40))


def dog_frames():
    frames = []
    for direction in range(4):
        for step in range(4):
            c = Canvas(16, 16)
            o = (0, 1, 0, -1)[step]
            wag = 1 if step in (1, 2) else 0
            if direction in (0, 1):
                c.part(lambda d: d.rectangle([4, 8, 11, 12], fill=1), 2, 3, 4)
                c.part(lambda d: (d.rectangle([4, 12, 6, 14 - o], fill=1), d.rectangle([9, 12, 11, 13 + o], fill=1)), 5, 6)
                c.part(lambda d: d.ellipse([4, 1, 11, 8], fill=1), 2, 3, 4)
                c.part(lambda d: (d.rectangle([2, 2, 3, 7], fill=1), d.rectangle([12, 2, 13, 7], fill=1)), D, D)
                if direction == 0:
                    c.part(lambda d: d.rectangle([6, 5, 9, 8], fill=1), 5, 6)
                    c.part(lambda d: d.rectangle([5, 8, 10, 9], fill=1), A)
                else:
                    c.part(lambda d: d.rectangle([7 + wag, 12, 8 + wag, 15], fill=1), 2, 3)
            else:
                c.part(lambda d: d.rectangle([10, 5 - wag, 14, 8 - wag], fill=1), 2, 3)
                c.part(lambda d: (d.rectangle([5, 11, 6, 14 - o], fill=1), d.rectangle([10, 11, 11, 13 + o], fill=1)), 5, 6)
                c.part(lambda d: d.ellipse([4, 6, 13, 12], fill=1), 2, 3, 4)
                c.part(lambda d: d.ellipse([1, 2, 8, 8], fill=1), 2, 3, 4)
                c.part(lambda d: d.rectangle([4, 2, 6, 6], fill=1), D, D)
                c.part(lambda d: d.rectangle([0, 5, 3, 8], fill=1), 5, 6)
                c.part(lambda d: d.rectangle([4, 8, 6, 9], fill=1), A)
                if direction == 3:
                    c.im = c.im.transpose(Image.FLIP_LEFT_RIGHT)
            c.outline(OUT)
            dr = c.draw()
            if direction == 0:
                dr.point((6, 4), fill=K); dr.point((9, 4), fill=K); dr.point((7, 6), fill=K); dr.point((8, 6), fill=K)
            elif direction in (2, 3):
                x_eye, x_nose = (3, 0) if direction == 2 else (12, 15)
                dr.point((x_eye, 4), fill=K); dr.point((x_nose, 6), fill=K)
            frames.append(c.im)
    return frames


# ------------------------------------------------------------------ interiores (15x10 casilleros de 16px = pantalla)
IN_PAL = [(30, 26, 34), (210, 160, 100), (160, 110, 64), (240, 226, 190), (200, 180, 140), (110, 72, 44),
          (190, 60, 60), (130, 36, 44), (250, 250, 250), (70, 130, 210), (160, 200, 240), (70, 150, 80),
          (40, 100, 56), (170, 170, 180), (250, 210, 80), (60, 40, 30)]
IN_W, IN_H = 15, 10
IN_OX, IN_OY = 8, 48       # el casillero (0,0) del interior cae en el pixel (8,48) de la imagen de 256x256


def _tile_px(x, y):
    return IN_OX + 16 * x, IN_OY + 16 * y


def interior_scene(kind):
    """kind: 'house' o 'vet'. Devuelve (imagen, grilla 15x10, (npc_x, npc_y))."""
    im = Image.new("P", (256, 256), 0)
    d = ImageDraw.Draw(im)
    grid = [[1] * IN_W for _ in range(IN_H)]          # 1 = bloqueado

    def box(x0, y0, x1, y1, **kw):
        a = _tile_px(x0, y0)
        b = _tile_px(x1, y1)
        d.rectangle([a[0], a[1], b[0] + 15, b[1] + 15], **kw)

    if kind == "house":
        rx0, rx1 = 3, 11
    else:
        rx0, rx1 = 2, 12
    # contorno del cuarto
    box(rx0, 1, rx1, 8, fill=15)
    # pared del fondo (filas 1 y 2)
    box(rx0 + 0, 1, rx1, 2, fill=3 if kind == "house" else 10)
    for x in range(rx0, rx1 + 1):
        px, py = _tile_px(x, 2)
        d.rectangle([px, py + 10, px + 15, py + 15], fill=5)        # zocalo
        d.rectangle([px, py + 8, px + 15, py + 9], fill=4)
    # paredes laterales
    for y in range(3, 9):
        for x in (rx0, rx1):
            px, py = _tile_px(x, y)
            d.rectangle([px, py, px + 15, py + 15], fill=4)
            d.rectangle([px + (12 if x == rx0 else 0), py, px + (15 if x == rx0 else 3), py + 15], fill=5)
    # pared de abajo
    for x in range(rx0, rx1 + 1):
        px, py = _tile_px(x, 8)
        d.rectangle([px, py, px + 15, py + 15], fill=4)
        d.rectangle([px, py, px + 15, py + 3], fill=5)
    # piso
    for y in range(3, 8):
        for x in range(rx0 + 1, rx1):
            px, py = _tile_px(x, y)
            if kind == "house":
                d.rectangle([px, py, px + 15, py + 15], fill=1)
                d.line([px, py + 7, px + 15, py + 7], fill=2)
                d.line([px + (4 if (y % 2) else 11), py, px + (4 if (y % 2) else 11), py + 7], fill=2)
                d.line([px + (11 if (y % 2) else 4), py + 8, px + (11 if (y % 2) else 4), py + 15], fill=2)
            else:
                d.rectangle([px, py, px + 15, py + 15], fill=8 if (x + y) % 2 == 0 else 13)
            grid[y][x] = 0
    for y in range(1, 3):                                              # fondo bloqueado
        for x in range(rx0, rx1 + 1):
            grid[y][x] = 1
    # felpudo / puerta de salida en (7, 8)
    px, py = _tile_px(7, 8)
    d.rectangle([px, py, px + 15, py + 15], fill=15)
    d.rectangle([px + 1, py + 1, px + 14, py + 14], fill=6)
    d.rectangle([px + 3, py + 3, px + 12, py + 12], outline=7)
    grid[8][7] = 3

    npc = (7, 4)

    def block(x, y, v=1):
        grid[y][x] = v

    def table(x, y):
        px, py = _tile_px(x, y)
        d.ellipse([px + 1, py + 11, px + 14, py + 15], fill=5)
        d.ellipse([px + 1, py + 3, px + 14, py + 12], fill=15)
        d.ellipse([px + 2, py + 4, px + 13, py + 11], fill=2)
        d.ellipse([px + 3, py + 5, px + 9, py + 9], fill=1)
        d.rectangle([px + 7, py + 1, px + 9, py + 5], fill=14)       # mate / termo
        d.rectangle([px + 7, py + 1, px + 9, py + 1], fill=13)

    def plant(x, y):
        px, py = _tile_px(x, y)
        d.rectangle([px + 4, py + 10, px + 11, py + 15], fill=15)
        d.rectangle([px + 5, py + 10, px + 10, py + 14], fill=6)
        d.ellipse([px + 1, py + 1, px + 14, py + 11], fill=12)
        d.ellipse([px + 3, py + 2, px + 10, py + 8], fill=11)

    if kind == "house":
        npc = (6, 4)
        # alfombra
        for y in range(4, 7):
            for x in range(5, 9):
                px, py = _tile_px(x, y)
                d.rectangle([px, py, px + 15, py + 15], fill=6)
                d.rectangle([px + 2, py + 2, px + 13, py + 13], outline=7)
        # cama
        px, py = _tile_px(4, 3)
        d.rectangle([px, py, px + 15, py + 15], fill=15)
        d.rectangle([px + 1, py + 1, px + 14, py + 14], fill=5)
        d.rectangle([px + 2, py + 2, px + 13, py + 6], fill=8)
        d.rectangle([px + 2, py + 7, px + 13, py + 14], fill=9)
        d.rectangle([px + 2, py + 7, px + 13, py + 8], fill=10)
        block(4, 3)
        # alacena en la pared
        px, py = _tile_px(10, 3)
        d.rectangle([px, py, px + 15, py + 15], fill=15)
        d.rectangle([px + 1, py + 1, px + 14, py + 14], fill=2)
        d.rectangle([px + 2, py + 2, px + 13, py + 7], fill=1)
        d.rectangle([px + 2, py + 9, px + 13, py + 13], fill=1)
        d.rectangle([px + 7, py + 4, px + 8, py + 5], fill=14)
        block(10, 3)
        table(8, 5); block(8, 5)
        plant(10, 7); block(10, 7)
        # ventana y cuadro en la pared del fondo
        px, py = _tile_px(5, 1)
        d.rectangle([px + 2, py + 3, px + 13, py + 13], fill=15)
        d.rectangle([px + 3, py + 4, px + 12, py + 12], fill=10)
        d.line([px + 7, py + 4, px + 7, py + 12], fill=8)
        px, py = _tile_px(9, 1)
        d.rectangle([px + 3, py + 3, px + 12, py + 11], fill=15)
        d.rectangle([px + 4, py + 4, px + 11, py + 10], fill=11)
        d.rectangle([px + 4, py + 8, px + 11, py + 10], fill=2)
    else:
        npc = (7, 3)
        # mostrador en fila 4, x 5..9 (talk-through = 2)
        for x in range(5, 10):
            px, py = _tile_px(x, 4)
            d.rectangle([px, py, px + 15, py + 15], fill=15)
            d.rectangle([px, py + 1, px + 15, py + 5], fill=1)
            d.rectangle([px, py + 6, px + 15, py + 14], fill=8)
            d.rectangle([px, py + 9, px + 15, py + 10], fill=9)
            block(x, 4, 2)
        block(7, 3)
        # cartel con cruz en la pared del fondo
        px, py = _tile_px(7, 1)
        d.rectangle([px + 1, py + 2, px + 14, py + 14], fill=15)
        d.rectangle([px + 2, py + 3, px + 13, py + 13], fill=8)
        d.rectangle([px + 6, py + 4, px + 9, py + 12], fill=6)
        d.rectangle([px + 4, py + 6, px + 11, py + 9], fill=6)
        # estantes con frascos
        for sx in (3, 11):
            px, py = _tile_px(sx, 1)
            d.rectangle([px + 1, py + 3, px + 14, py + 14], fill=15)
            d.rectangle([px + 2, py + 4, px + 13, py + 13], fill=2)
            d.rectangle([px + 2, py + 8, px + 13, py + 8], fill=15)
            for k, col in ((3, 9), (6, 6), (9, 11), (11, 14)):
                d.rectangle([px + k, py + 5, px + k + 1, py + 7], fill=col)
                d.rectangle([px + k, py + 10, px + k + 1, py + 12], fill=col)
        # camilla de examen
        px, py = _tile_px(10, 5)
        d.ellipse([px + 1, py + 12, px + 14, py + 15], fill=5)
        d.rectangle([px + 1, py + 3, px + 14, py + 11], fill=15)
        d.rectangle([px + 2, py + 4, px + 13, py + 9], fill=8)
        d.rectangle([px + 2, py + 9, px + 13, py + 10], fill=13)
        block(10, 5)
        # bancos de espera y plantas
        for bx, by in ((3, 6), (3, 7), (11, 6)):
            px, py = _tile_px(bx, by)
            d.rectangle([px + 1, py + 4, px + 14, py + 15], fill=15)
            d.rectangle([px + 2, py + 5, px + 13, py + 10], fill=9)
            d.rectangle([px + 2, py + 11, px + 13, py + 14], fill=2)
            block(bx, by)
        plant(3, 3); block(3, 3)
        plant(11, 3); block(11, 3)
        # alfombra azul frente al mostrador
        for x in range(6, 9):
            px, py = _tile_px(x, 6)
            d.rectangle([px, py, px + 15, py + 15], fill=9)
            d.rectangle([px + 2, py + 2, px + 13, py + 13], outline=10)
    return im, grid, npc


def export_interiors():
    out = ["// Generado por tools/gen_assets.py. No editar a mano.\n#ifndef INTERIOR_DATA_H\n#define INTERIOR_DATA_H\n\n",
           "namespace interior\n{\n    // 0 piso, 1 bloqueado, 2 mostrador (se puede hablar a traves), 3 salida\n",
           f"    inline constexpr int width = {IN_W};\n    inline constexpr int height = {IN_H};\n",
           "    // el casillero (0,0) esta en la pantalla en (-120,-80)\n"]
    for kind in ("house", "vet"):
        im, grid, npc = interior_scene(kind)
        write_bmp(os.path.join(GFX, f"interior_{kind}.bmp"), im, IN_PAL, 4)
        write_json(f"interior_{kind}", {"type": "regular_bg"})
        flat = ",".join(str(v) for row in grid for v in row)
        out.append(f"    inline constexpr unsigned char {kind}_grid[{IN_W * IN_H}] = {{{flat}}};\n")
        out.append(f"    inline constexpr int {kind}_npc_x = {npc[0]};\n    inline constexpr int {kind}_npc_y = {npc[1]};\n")
    out.append("    inline constexpr int spawn_x = 7;\n    inline constexpr int spawn_y = 7;\n}\n\n#endif\n")
    with open(os.path.join(INC, "interior_data.h"), "w") as f:
        f.write("".join(out))


# ------------------------------------------------------------------ criaturas 32x32
# Cada una tiene su propia paleta: contorno + 14 colores.
def creature_art(idx):
    c = Canvas(64, 64, k=2)
    p = c.part
    if idx == 0:    # Hornerito (hornero)
        pal = spr_pal((200, 120, 56), (150, 84, 40), (232, 160, 88), (240, 220, 176), (206, 178, 132), (252, 240, 210),
                      (250, 250, 250), (20, 16, 24), (96, 74, 62), (200, 150, 140), (112, 60, 30))
        p(lambda d: d.polygon([(6, 17), (1, 20), (1, 26), (9, 23)], fill=1), B, BS, BL)
        p(lambda d: d.rectangle([12, 25, 13, 30], fill=1), A2)
        p(lambda d: d.rectangle([18, 25, 19, 30], fill=1), A2)
        p(lambda d: d.ellipse([5, 11, 23, 26], fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([10, 17, 23, 27], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([4, 14, 15, 24], fill=1), BS, D)
        p(lambda d: d.ellipse([16, 4, 27, 15], fill=1), B, BS, BL)
        p(lambda d: d.polygon([(26, 8), (31, 10), (26, 12)], fill=1), A)
        c.outline(OUT)
        d = c.draw(); d.point((23, 8), fill=K); d.point((22, 7), fill=WHT)
    elif idx == 1:  # Carpinchin (carpincho)
        pal = spr_pal((150, 100, 60), (104, 66, 40), (186, 134, 84), (186, 140, 94), (140, 98, 62), (216, 176, 130),
                      (250, 250, 250), (20, 16, 24), (60, 40, 30), (190, 110, 100), (84, 52, 34))
        p(lambda d: (d.rectangle([5, 25, 9, 30], fill=1), d.rectangle([19, 25, 23, 30], fill=1)), BS, D)
        p(lambda d: d.rounded_rectangle([2, 11, 25, 27], 5, fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([6, 19, 22, 27], fill=1), C, CS, CL)
        p(lambda d: d.rounded_rectangle([19, 7, 30, 20], 4, fill=1), B, BS, BL)
        p(lambda d: d.rounded_rectangle([24, 12, 31, 20], 3, fill=1), C, CS, CL)
        p(lambda d: d.ellipse([19, 5, 23, 10], fill=1), BS, D)
        c.outline(OUT)
        d = c.draw(); d.point((29, 13), fill=K); d.point((24, 11), fill=K); d.point((23, 10), fill=WHT)
    elif idx == 2:  # Nandusito (nandu)
        pal = spr_pal((170, 166, 160), (120, 118, 118), (206, 204, 198), (214, 196, 170), (166, 146, 122), (236, 222, 200),
                      (250, 250, 250), (20, 16, 24), (96, 84, 74), (200, 170, 140), (84, 80, 80))
        p(lambda d: (d.rectangle([8, 24, 9, 30], fill=1), d.rectangle([15, 24, 16, 30], fill=1)), C, CS)
        p(lambda d: d.ellipse([0, 12, 10, 24], fill=1), BS, D)
        p(lambda d: d.ellipse([3, 13, 21, 26], fill=1), B, BS, BL, 2)
        p(lambda d: d.rectangle([18, 5, 21, 17], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([17, 1, 26, 8], fill=1), C, CS, CL)
        p(lambda d: d.polygon([(25, 3), (30, 5), (25, 6)], fill=1), A)
        c.outline(OUT)
        d = c.draw(); d.point((22, 4), fill=K)
    elif idx == 3:  # Guanaquito (guanaco)
        pal = spr_pal((206, 160, 104), (160, 114, 70), (236, 196, 140), (244, 236, 220), (206, 196, 182), (255, 252, 244),
                      (250, 250, 250), (20, 16, 24), (110, 100, 100), (84, 70, 60), (190, 150, 130))
        p(lambda d: [d.rectangle([x, 21, x + 1, 30], fill=1) for x in (4, 9, 16, 20)], BS, D)
        p(lambda d: d.polygon([(2, 14), (0, 11), (2, 11), (4, 13)], fill=1), C, CS)
        p(lambda d: d.rounded_rectangle([2, 11, 22, 23], 4, fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([12, 17, 22, 24], fill=1), C, CS, CL)
        p(lambda d: d.rectangle([17, 4, 21, 15], fill=1), B, BS, BL)
        p(lambda d: d.rounded_rectangle([17, 1, 28, 8], 3, fill=1), C, CS, CL)
        p(lambda d: d.polygon([(19, 0), (21, 0), (20, 3)], fill=1), A)
        p(lambda d: d.rectangle([24, 4, 28, 7], fill=1), A2)
        c.outline(OUT)
        d = c.draw(); d.point((23, 3), fill=K); d.point((27, 5), fill=K)
    elif idx == 4:  # Yaguarin (yaguarete)
        pal = spr_pal((236, 184, 60), (196, 138, 36), (252, 216, 104), (250, 240, 210), (214, 198, 160), (255, 252, 240),
                      (250, 250, 250), (20, 16, 24), (230, 120, 120), (200, 90, 90), (50, 30, 20))
        p(lambda d: d.line([4, 15, 1, 9], fill=1, width=3), B, BS)
        p(lambda d: (d.rounded_rectangle([5, 24, 9, 30], 1, fill=1), d.rounded_rectangle([19, 24, 23, 30], 1, fill=1)), B, BS)
        p(lambda d: d.rounded_rectangle([3, 12, 25, 26], 5, fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([8, 20, 22, 27], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([19, 5, 31, 18], fill=1), B, BS, BL)
        p(lambda d: (d.polygon([(20, 7), (21, 1), (25, 6)], fill=1), d.polygon([(26, 6), (29, 1), (31, 8)], fill=1)), B, BS)
        p(lambda d: d.ellipse([25, 11, 31, 18], fill=1), C, CS, CL)
        c.outline(OUT)
        d = c.draw()
        d.point((24, 9), fill=K); d.point((28, 9), fill=K); d.point((29, 12), fill=A); d.point((22, 8), fill=D)
    elif idx == 5:  # Zorrito (zorro pampeano)
        pal = spr_pal((150, 150, 160), (104, 104, 118), (190, 190, 200), (220, 120, 50), (170, 84, 36), (244, 160, 84),
                      (250, 250, 250), (20, 16, 24), (60, 60, 72), (230, 170, 160), (80, 76, 90))
        p(lambda d: d.polygon([(9, 15), (2, 9), (0, 14), (1, 22), (9, 23)], fill=1), C, CS, CL, 2)
        p(lambda d: d.polygon([(1, 20), (0, 14), (3, 17)], fill=1), WHT)
        p(lambda d: (d.rectangle([10, 24, 12, 30], fill=1), d.rectangle([19, 24, 21, 30], fill=1)), A, A)
        p(lambda d: d.ellipse([7, 13, 25, 26], fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([14, 18, 25, 27], fill=1), WHT, CS)
        p(lambda d: d.ellipse([18, 7, 30, 19], fill=1), B, BS, BL)
        p(lambda d: (d.polygon([(19, 8), (20, 0), (24, 7)], fill=1), d.polygon([(25, 7), (28, 0), (30, 9)], fill=1)), B, BS, BL)
        p(lambda d: d.polygon([(25, 13), (31, 16), (25, 18)], fill=1), WHT, CS)
        c.outline(OUT)
        d = c.draw(); d.point((24, 11), fill=K); d.point((31, 15), fill=K); d.point((20, 3), fill=A2); d.point((28, 3), fill=A2)
    elif idx == 6:  # Pingui (pinguino de Magallanes)
        pal = spr_pal((40, 44, 64), (24, 26, 44), (72, 80, 108), (240, 244, 250), (196, 204, 220), (255, 255, 255),
                      (250, 250, 250), (20, 16, 24), (240, 140, 40), (230, 150, 160), (70, 76, 100))
        p(lambda d: (d.rectangle([9, 27, 14, 30], fill=1), d.rectangle([18, 27, 23, 30], fill=1)), A)
        p(lambda d: d.ellipse([7, 3, 25, 29], fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([11, 11, 21, 28], fill=1), C, CS, CL)
        p(lambda d: (d.polygon([(8, 13), (3, 23), (10, 23)], fill=1), d.polygon([(24, 13), (29, 23), (22, 23)], fill=1)), B, BS)
        p(lambda d: d.polygon([(14, 8), (18, 8), (16, 12)], fill=1), A)
        c.outline(OUT)
        d = c.draw(); d.point((12, 7), fill=WHT); d.point((20, 7), fill=WHT); d.point((12, 8), fill=K); d.point((20, 8), fill=K)
        d.rectangle([13, 11, 19, 11], fill=D); d.point((10, 9), fill=A2); d.point((22, 9), fill=A2)
    elif idx == 7:  # Condorcito (condor andino)
        pal = spr_pal((44, 44, 52), (26, 26, 34), (80, 80, 96), (246, 246, 250), (200, 204, 214), (255, 255, 255),
                      (250, 250, 250), (20, 16, 24), (220, 190, 120), (200, 90, 90), (150, 56, 56))
        p(lambda d: d.polygon([(16, 9), (30, 13), (31, 20), (24, 23), (16, 18), (8, 23), (1, 20), (2, 13)], fill=1), B, BS, BL, 2)
        p(lambda d: d.polygon([(30, 14), (31, 20), (24, 23), (26, 17)], fill=1), WHT, CS)
        p(lambda d: d.polygon([(2, 14), (1, 20), (8, 23), (6, 17)], fill=1), WHT, CS)
        p(lambda d: d.ellipse([11, 14, 21, 29], fill=1), B, BS, BL)
        p(lambda d: d.ellipse([11, 10, 21, 17], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([13, 2, 19, 10], fill=1), A2, D, A2)
        p(lambda d: d.polygon([(15, 8), (17, 8), (16, 12)], fill=1), A)
        c.outline(OUT)
        d = c.draw(); d.point((14, 5), fill=K); d.point((18, 5), fill=K)
    elif idx == 8:  # Vizcachon (vizcacha)
        pal = spr_pal((150, 140, 130), (106, 98, 92), (190, 180, 170), (226, 214, 190), (186, 172, 150), (246, 240, 222),
                      (250, 250, 250), (20, 16, 24), (80, 74, 70), (210, 150, 140), (70, 64, 60))
        p(lambda d: d.ellipse([0, 18, 6, 24], fill=1), BS, D)
        p(lambda d: (d.rectangle([7, 26, 11, 30], fill=1), d.rectangle([19, 26, 23, 30], fill=1)), BS, D)
        p(lambda d: d.ellipse([3, 10, 25, 27], fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([8, 18, 22, 27], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([18, 8, 30, 20], fill=1), B, BS, BL)
        p(lambda d: (d.rectangle([20, 3, 22, 9], fill=1), d.rectangle([25, 3, 27, 9], fill=1)), BS, D)
        p(lambda d: d.ellipse([24, 12, 31, 20], fill=1), C, CS, CL)
        c.outline(OUT)
        d = c.draw(); d.point((26, 11), fill=K); d.point((30, 14), fill=K)
        d.line([27, 17, 31, 18], fill=D); d.line([27, 18, 31, 20], fill=D)
    elif idx == 9:  # Teru (tero)
        pal = spr_pal((150, 156, 168), (110, 114, 128), (190, 196, 206), (250, 250, 252), (200, 204, 214), (255, 255, 255),
                      (250, 250, 250), (20, 16, 24), (244, 170, 50), (200, 50, 50), (60, 62, 76))
        p(lambda d: (d.line([13, 25, 13, 31], fill=1), d.line([18, 25, 18, 31], fill=1)), A2)
        p(lambda d: d.ellipse([5, 11, 23, 26], fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([10, 15, 23, 27], fill=1), C, CS, CL)
        p(lambda d: d.polygon([(7, 14), (1, 23), (11, 22)], fill=1), D, K)
        p(lambda d: d.ellipse([17, 4, 27, 14], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([18, 3, 26, 9], fill=1), K)
        p(lambda d: d.polygon([(26, 8), (31, 9), (26, 11)], fill=1), A)
        c.outline(OUT)
        d = c.draw(); d.line([20, 3, 17, 0], fill=K); d.point((23, 8), fill=A2); d.point((22, 7), fill=WHT)
        d.line([12, 19, 22, 19], fill=K)
    else:           # 10: Mate, el perrito companero
        pal = spr_pal((214, 168, 100), (168, 120, 64), (240, 204, 140), (248, 240, 224), (214, 204, 190), (255, 255, 255),
                      (250, 250, 250), (20, 16, 24), (210, 50, 50), (150, 30, 40), (120, 76, 40))
        p(lambda d: d.polygon([(5, 16), (0, 8), (3, 6), (8, 14)], fill=1), B, BS, BL)
        p(lambda d: (d.rectangle([5, 24, 9, 30], fill=1), d.rectangle([17, 24, 21, 30], fill=1)), B, BS)
        p(lambda d: (d.rectangle([5, 28, 9, 30], fill=1), d.rectangle([17, 28, 21, 30], fill=1)), C, CS)
        p(lambda d: d.rounded_rectangle([3, 13, 23, 26], 5, fill=1), B, BS, BL, 2)
        p(lambda d: d.ellipse([14, 16, 24, 27], fill=1), C, CS, CL)
        p(lambda d: d.ellipse([17, 5, 30, 18], fill=1), B, BS, BL)
        p(lambda d: d.polygon([(18, 6), (15, 7), (13, 15), (17, 17), (20, 11)], fill=1), D, D)
        p(lambda d: d.ellipse([23, 10, 31, 18], fill=1), C, CS, CL)
        p(lambda d: d.polygon([(14, 16), (23, 15), (21, 21), (17, 24)], fill=1), A, A2)
        c.outline(OUT)
        d = c.draw(); d.point((30, 11), fill=K); d.point((25, 9), fill=K); d.point((24, 8), fill=WHT)
        d.point((28, 17), fill=A); d.point((28, 18), fill=A)
    enhance(c, idx)
    return c.im, pal


# ------------------------------------------------------------------ retoques de los animales (64x64)
EYE_HL = {0: [(23, 8)], 1: [(24, 11)], 2: [(22, 4)], 3: [(23, 3)], 4: [(24, 9), (28, 9)], 5: [(24, 11)],
          7: [(14, 5), (18, 5)], 8: [(26, 11)], 10: [(25, 9)]}
BIRDS = {0, 2, 6, 7, 9}


def enhance(c, idx):
    """Textura de pelo o plumas, brillo en los ojos y manchas de yaguarete (resolucion nativa 64x64)."""
    px = c.im.load()
    w, h = c.w, c.h
    rng = random.Random(100 + idx)
    # textura: trazos cortos de sombra y de luz sobre el color base y el secundario
    for _ in range(150):
        x, y = rng.randrange(2, w - 3), rng.randrange(2, h - 3)
        col = px[x, y]
        if col not in (B, C):
            continue
        sh, li = (BS, BL) if col == B else (CS, CL)
        if idx in BIRDS:
            pts = [(x, y), (x + 1, y)]
        else:
            pts = [(x, y), (x - 1, y + 1)] if rng.random() < 0.5 else [(x, y), (x, y + 1)]
        if all(px[a, b] == col for a, b in pts):
            for a, b in pts:
                px[a, b] = sh if rng.random() < 0.75 else li
    # manchas del yaguarete: rosetas (anillo con punto) sobre el pelaje
    if idx == 4:
        mask = Image.new("1", (w, h), 0)
        md = ImageDraw.Draw(mask)
        for (x, y) in [(14, 32), (24, 30), (34, 33), (20, 41), (31, 43), (43, 41), (12, 46), (28, 35), (40, 31), (9, 38)]:
            md.ellipse([x - 3, y - 2, x + 3, y + 2], outline=1)
            md.point((x, y), fill=1)
            md.point((x + 1, y), fill=1)
        for (x, y) in [(46, 20), (53, 24), (48, 26), (8, 54), (46, 54)]:
            md.rectangle([x, y, x + 1, y + 1], fill=1)
        mp = mask.load()
        for y in range(h):
            for x in range(w):
                if mp[x, y] and px[x, y] in (B, BS, BL, C, CS, CL):
                    px[x, y] = D
    # brillo en los ojos (el ojo es un bloque de 2x2 negro: se le pinta un pixel blanco)
    for (x, y) in EYE_HL.get(idx, []):
        if px[2 * x, 2 * y] == K:
            px[2 * x, 2 * y] = WHT


# ------------------------------------------------------------------ efectos de combate
def _star(cx, cy, r_out, r_in, n=8, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def export_fx():
    # golpe: 3 cuadros de 32x32 (estrella que se agranda)
    pal = [(255, 0, 255), (60, 30, 20), (255, 255, 255), (255, 226, 80), (255, 150, 40)]
    sheet = Image.new("P", (32, 32 * 3), 0)
    for f, (ro, ri) in enumerate(((8, 4), (13, 6), (15, 8))):
        im = Image.new("P", (32, 32), 0)
        d = ImageDraw.Draw(im)
        d.polygon(_star(16, 16, ro, ri, 8, 0.2 * f), fill=4, outline=1)
        d.polygon(_star(16, 16, ro * 0.72, ri * 0.7, 8, 0.2 * f), fill=3)
        d.polygon(_star(16, 16, ro * 0.38, ri * 0.4, 8, 0.2 * f), fill=2)
        sheet.paste(im, (0, 32 * f))
    write_bmp(os.path.join(GFX, "hit.bmp"), sheet, pal, 4)
    write_json("hit", {"type": "sprite", "height": 32})

    # boleadoras: tres bolas atadas a un nudo central
    pal = [(255, 0, 255), (30, 20, 16), (190, 140, 90), (120, 76, 44), (230, 214, 170)]
    im = Image.new("P", (16, 16), 0)
    d = ImageDraw.Draw(im)
    balls = [(8 + 5.2 * math.cos(math.radians(a)), 8 + 5.2 * math.sin(math.radians(a))) for a in (270, 30, 150)]
    for bx, by in balls:
        d.line([8, 8, bx, by], fill=4, width=1)
    for bx, by in balls:
        d.ellipse([bx - 2.6, by - 2.6, bx + 2.6, by + 2.6], fill=3, outline=1)
        im.putpixel((int(bx - 1), int(by - 1)), 2)
    d.ellipse([6, 6, 10, 10], fill=4, outline=1)
    write_bmp(os.path.join(GFX, "bolas.bmp"), im, pal, 4)
    write_json("bolas", {"type": "sprite"})

    # chispas de captura: 2 cuadros de 8x8
    pal = [(255, 0, 255), (255, 190, 50), (255, 255, 255)]
    sheet = Image.new("P", (8, 16), 0)
    for f, r in enumerate((4, 2.6)):
        im = Image.new("P", (8, 8), 0)
        d = ImageDraw.Draw(im)
        d.polygon([(4, 4 - r), (4 + r * 0.35, 4 - r * 0.35), (4 + r, 4), (4 + r * 0.35, 4 + r * 0.35),
                   (4, 4 + r), (4 - r * 0.35, 4 + r * 0.35), (4 - r, 4), (4 - r * 0.35, 4 - r * 0.35)], fill=2, outline=1)
        sheet.paste(im, (0, 8 * f))
    write_bmp(os.path.join(GFX, "spark.bmp"), sheet, pal, 4)
    write_json("spark", {"type": "sprite", "height": 8})

    # barra de vida: 29 cuadros de 32x8 (0..28 pasos de 1 px)
    pal = [(255, 0, 255), (24, 22, 34), (80, 84, 100), (110, 235, 120), (56, 170, 74),
           (255, 224, 84), (214, 170, 40), (245, 84, 70), (176, 40, 40), (250, 250, 250)]
    sheet = Image.new("P", (32, 8 * 29), 0)
    for k in range(29):
        im = Image.new("P", (32, 8), 0)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, 31, 7], 2, fill=1)
        d.rectangle([2, 2, 29, 5], fill=2)
        ratio = k / 28
        hi, lo = (3, 4) if ratio > 0.5 else ((5, 6) if ratio > 0.25 else (7, 8))
        if k > 0:
            d.rectangle([2, 2, 1 + k, 5], fill=lo)
            d.rectangle([2, 2, 1 + k, 3], fill=hi)
        sheet.paste(im, (0, 8 * k))
    write_bmp(os.path.join(GFX, "hpbar.bmp"), sheet, pal, 4)
    write_json("hpbar", {"type": "sprite", "height": 8})


# ------------------------------------------------------------------ fondos de combate
PANEL_FILL = (24, 28, 52)
PANEL_EDGE = (232, 232, 244)

# (cielo1, cielo2, cielo3, lejano, lejano2, suelo lejano, suelo cerca, mata, plataforma luz, plataforma sombra, borde)
BATTLE_THEMES = {
    "norte":     [(120, 190, 240), (160, 214, 250), (204, 234, 255), (44, 100, 60), (64, 130, 76), (88, 168, 80), (112, 192, 92), (56, 124, 60), (160, 220, 120), (112, 180, 84), (60, 110, 56)],
    "pampa":     [(104, 170, 244), (150, 204, 252), (210, 232, 255), (120, 160, 110), (150, 190, 130), (140, 200, 100), (170, 220, 120), (96, 160, 80), (196, 236, 140), (140, 196, 100), (80, 130, 70)],
    "patagonia": [(150, 190, 230), (196, 214, 236), (236, 232, 224), (168, 130, 96), (196, 160, 118), (214, 188, 128), (232, 208, 150), (170, 140, 90), (244, 224, 170), (200, 170, 112), (140, 112, 76)],
    "costa":     [(100, 180, 240), (150, 212, 252), (216, 240, 255), (60, 130, 220), (110, 176, 244), (236, 214, 156), (248, 230, 176), (200, 176, 120), (252, 240, 196), (220, 196, 140), (168, 140, 92)],
    "andes":     [(96, 130, 200), (140, 170, 224), (200, 216, 240), (92, 96, 124), (176, 184, 206), (140, 148, 132), (164, 170, 150), (104, 112, 96), (190, 196, 170), (140, 146, 124), (96, 100, 84)],
}


def battle_bg(name):
    th = BATTLE_THEMES[name]
    pal = [(255, 0, 255)] + th[:3] + [th[3], th[4], th[5], th[6], th[7], th[8], th[9], th[10], PANEL_FILL, PANEL_EDGE, (255, 255, 255), (255, 255, 255)]
    # indices: 1-3 cielo, 4-5 lejano, 6 suelo lejano, 7 suelo cerca, 8 mata, 9 plat luz, 10 plat sombra, 11 borde,
    # 12 panel, 13 borde panel, 14/15 blanco
    im = Image.new("P", (256, 256), 7)
    d = ImageDraw.Draw(im)
    px = im.load()
    ox = oy = 128          # coordenadas de pantalla (0,0) = centro de la imagen

    def S(x, y):
        return (x + ox, y + oy)

    horizon = -6
    # cielo en 3 bandas con transicion punteada
    for y in range(-80, horizon + 1):
        for x in range(-120, 121):
            if y < -52:
                c = 1
            elif y < -28:
                c = 1 if (y < -46 and (x + y) % 2 == 0) or y < -52 else 2
                if y >= -46: c = 2 if not ((x + y) % 2 == 0 and y < -40) else 1
            else:
                c = 3 if not ((x + y) % 2 == 0 and y < -20) else 2
            px[x + ox, y + oy] = c
    # elementos lejanos segun la region
    rng = random.Random(name)
    if name == "andes":
        pts = [(-120, horizon)]
        x = -120
        while x < 130:
            pts.append((x + 14, horizon - rng.randrange(18, 46)))
            pts.append((x + 30, horizon - rng.randrange(6, 18)))
            x += 30
        pts.append((130, horizon))
        d.polygon([S(a, b) for a, b in pts], fill=4)
        for a, b in pts[1::2]:
            d.polygon([S(a - 4, b + 7), S(a, b), S(a + 4, b + 7)], fill=5)
    elif name == "patagonia":
        for mx, mw, mh in ((-100, 50, 22), (-20, 70, 30), (70, 46, 18)):
            d.rectangle([S(mx, horizon - mh), S(mx + mw, horizon)], fill=4)
            d.rectangle([S(mx, horizon - mh), S(mx + mw, horizon - mh + 3)], fill=5)
    elif name == "costa":
        d.rectangle([S(-120, horizon - 14), S(120, horizon)], fill=4)
        for yy in range(horizon - 13, horizon, 3):
            for xx in range(-120 + (yy % 6), 120, 14):
                d.line([S(xx, yy), S(xx + 5, yy)], fill=5)
    elif name == "norte":
        for tx in range(-120, 124, 12):
            r = rng.randrange(8, 14)
            d.ellipse([S(tx - 8, horizon - r - 4), S(tx + 8, horizon + 4)], fill=4)
            d.ellipse([S(tx - 5, horizon - r - 3), S(tx + 3, horizon - r + 3)], fill=5)
    else:  # pampa
        d.rectangle([S(-120, horizon - 5), S(120, horizon)], fill=4)
        for tx in (-70, 20, 90):
            d.ellipse([S(tx - 7, horizon - 14), S(tx + 7, horizon - 2)], fill=4)
            d.ellipse([S(tx - 4, horizon - 12), S(tx + 2, horizon - 7)], fill=5)
    # suelo: franja lejana y cercana con matas
    d.rectangle([S(-120, horizon + 1), S(120, 80)], fill=6)
    for y in range(24, 81):
        for x in range(-120, 121):
            if y > 20 and (x + y * 2) % 2 == 0 and y % 3:
                px[x + ox, y + oy] = 7
            elif y > 20:
                px[x + ox, y + oy] = 7
    for _ in range(70):
        x, y = rng.randrange(-118, 118), rng.randrange(horizon + 3, 78)
        d.line([S(x, y), S(x + 2, y)], fill=8)
        d.point(S(x + 1, y - 1), fill=8)

    def platform(cx, cy, rx, ry):
        d.ellipse([S(cx - rx, cy - ry + 3), S(cx + rx, cy + ry + 3)], fill=11)
        d.ellipse([S(cx - rx, cy - ry), S(cx + rx, cy + ry)], fill=10)
        d.ellipse([S(cx - rx + 3, cy - ry), S(cx + rx - 3, cy + ry - 3)], fill=9)

    platform(56, -12, 38, 8)     # rival
    platform(-56, 20, 44, 9)     # tu perrito

    def panel(x0, y0, x1, y1):
        d.rounded_rectangle([S(x0, y0), S(x1, y1)], 3, fill=12, outline=13)
        d.rounded_rectangle([S(x0 + 1, y0 + 1), S(x1 - 1, y1 - 1)], 2, outline=12)

    panel(-118, 34, 118, 79)     # mensajes y botones
    panel(-118, -75, -2, -54)    # rival
    panel(14, 2, 118, 22)        # tu perrito
    write_bmp(os.path.join(GFX, f"battle_{name}.bmp"), im, pal, 4)
    write_json(f"battle_{name}", {"type": "regular_bg"})


# ------------------------------------------------------------------ mapa de Argentina con provincias (tecla M)
# Datos: Natural Earth (dominio publico), tools/data/arg_provinces.json
ARG_LON0, ARG_LON1 = -73.6, -53.6
ARG_LAT_MIN, ARG_LAT_MAX = -55.1, -21.7
ARG_SCALE = 4.4                    # pixeles por grado de latitud
ARG_KX = ARG_SCALE * 0.788         # pixeles por grado de longitud (cos 38 grados)
ARG_X0, ARG_Y0 = -100, -74         # esquina del mapa en coordenadas de pantalla (debe coincidir con main.cpp)
ARG_PAL = [(30, 24, 20), (232, 218, 176), (92, 60, 36), (196, 160, 100), (150, 196, 238), (150, 210, 120),
           (240, 226, 130), (240, 170, 110), (200, 170, 230), (60, 50, 70), (60, 40, 30), (250, 250, 250),
           (120, 200, 200), (190, 214, 242), (200, 60, 60), (250, 210, 60)]
ARG_TINTS = [5, 6, 7, 8, 12]


def _font():
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=8)
    except TypeError:
        return ImageFont.load_default()


def _ascii(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _load_provinces():
    with open(os.path.join(ROOT, "tools", "data", "arg_provinces.json"), encoding="utf-8") as f:
        data = json.load(f)
    provs = []
    for ft in data["features"]:
        name = _ascii(ft["properties"]["name"])
        if name.startswith("Ciudad de Buenos Aires"):
            name = "CABA"
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        provs.append((name, polys))
    provs.sort(key=lambda p: p[0])
    return provs


def _nearest(points, qx, qy):
    best, bd = None, 1e18
    for (px, py) in points:
        d = (px - qx) ** 2 + (py - qy) ** 2
        if d < bd:
            best, bd = (px, py), d
    return best


def export_argmap():
    import numpy as np
    provs = _load_provinces()
    n = len(provs)
    mw = int(round((ARG_LON1 - ARG_LON0) * ARG_KX)) + 1
    mh = int(round((ARG_LAT_MAX - ARG_LAT_MIN) * ARG_SCALE)) + 1

    def proj(lon, lat, scale=1.0):
        return ((lon - ARG_LON0) * ARG_KX * scale, (ARG_LAT_MAX - lat) * ARG_SCALE * scale)

    # raster de ids a escala del mapa y en alta resolucion (para ubicar casilleros)
    def raster(scale):
        im = Image.new("L", (int(mw * scale) + 2, int(mh * scale) + 2), 0)
        d = ImageDraw.Draw(im)
        for i, (_name, polys) in enumerate(provs):
            for rings in polys:
                d.polygon([proj(lo, la, scale) for lo, la in rings[0]], fill=i + 1)
        return np.array(im)

    ids_map = raster(1.0)
    HR = 6.0
    ids_hr = raster(HR)

    # adyacencia -> colores (greedy, las provincias mas grandes primero)
    adj = [set() for _ in range(n)]
    for a, b in ((ids_map[:, :-1], ids_map[:, 1:]), (ids_map[:-1, :], ids_map[1:, :])):
        mask = (a != b) & (a > 0) & (b > 0)
        for x, y in zip(a[mask], b[mask]):
            adj[x - 1].add(y - 1)
            adj[y - 1].add(x - 1)
    areas = [int((ids_map == i + 1).sum()) for i in range(n)]
    tint = [None] * n
    for i in sorted(range(n), key=lambda k: -areas[k]):
        used = {tint[j] for j in adj[i] if tint[j] is not None}
        tint[i] = next((c for c in ARG_TINTS if c not in used), ARG_TINTS[0])

    im = Image.new("P", (256, 256), 1)
    d = ImageDraw.Draw(im)
    ox, oy = ARG_X0 + 128, ARG_Y0 + 128
    # marco y mar
    d.rectangle([ox - 6, oy - 6, ox + mw + 5, oy + mh + 5], fill=2)
    d.rectangle([ox - 4, oy - 4, ox + mw + 3, oy + mh + 3], fill=3)
    d.rectangle([ox - 2, oy - 2, ox + mw + 1, oy + mh + 1], fill=2)
    d.rectangle([ox - 1, oy - 1, ox + mw, oy + mh], fill=4)
    for gy in range(0, mh, 8):                                      # grilla suave en el mar
        for gx in range(0, mw, 8):
            if (gx + gy) % 16 == 0:
                im.putpixel((ox + gx, oy + gy), 13)
    for i, (_name, polys) in enumerate(provs):
        for rings in polys:
            d.polygon([(ox + x, oy + y) for x, y in (proj(lo, la) for lo, la in rings[0])], fill=tint[i])
    for i, (_name, polys) in enumerate(provs):
        for rings in polys:
            for ring in rings:
                pts = [(ox + x, oy + y) for x, y in (proj(lo, la) for lo, la in ring)]
                d.line(pts + [pts[0]], fill=9, width=1)

    font = _font()

    def text(x, y, s, color=10, center=False):
        mask = Image.new("1", (256, 256), 0)
        md = ImageDraw.Draw(mask)
        if center:
            x = x - int(md.textlength(s, font=font)) // 2
        md.text((x + 128, y + 128), s, font=font, fill=1)
        im.paste(color, (0, 0), mask)

    text(60, -76, "ARGENTINA", 2, center=True)
    # rosa de los vientos
    cx, cy = 96 + 128, -40 + 128
    d.polygon([(cx, cy - 14), (cx - 4, cy), (cx + 4, cy)], fill=14, outline=9)
    d.polygon([(cx, cy + 14), (cx - 4, cy), (cx + 4, cy)], fill=11, outline=9)
    d.polygon([(cx - 14, cy), (cx, cy - 4), (cx, cy + 4)], fill=11, outline=9)
    d.polygon([(cx + 14, cy), (cx, cy - 4), (cx, cy + 4)], fill=11, outline=9)
    text(96, -62, "N", 2, center=True)
    # leyenda del marcador
    d.ellipse([-14 + 128, 51 + 128, -8 + 128, 57 + 128], fill=14, outline=11)
    text(-4, 49, "= tu posicion", 10)
    write_bmp(os.path.join(GFX, "mapscreen.bmp"), im, ARG_PAL, 4)
    write_json("mapscreen", {"type": "regular_bg"})

    # --- tablas: provincia y posicion del marcador para cada casillero del juego
    pts_hr = [(int(x), int(y)) for y, x in np.argwhere(ids_hr > 0)[::7]]
    pts_by_id = {}
    for y, x in np.argwhere(ids_map > 0):
        pts_by_id.setdefault(int(ids_map[y, x]) - 1, []).append((int(x), int(y)))

    prov_of, mark_x, mark_y = [], [], []
    for ty in range(H):
        for tx in range(W):
            lon = ARG_LON0 + (tx + 0.5) / W * (ARG_LON1 - ARG_LON0)
            lat = ARG_LAT_MAX - (ty + 0.5) / H * (ARG_LAT_MAX - ARG_LAT_MIN)
            hx, hy = proj(lon, lat, HR)
            hx, hy = int(hx), int(hy)
            pid = 0
            if 0 <= hy < ids_hr.shape[0] and 0 <= hx < ids_hr.shape[1]:
                pid = int(ids_hr[hy, hx])
            if pid == 0:
                nx, ny = _nearest(pts_hr, hx, hy)
                pid = int(ids_hr[ny, nx])
            pid -= 1
            mx, my = proj(lon, lat)
            mx, my = int(round(mx)), int(round(my))
            if not (0 <= my < ids_map.shape[0] and 0 <= mx < ids_map.shape[1] and ids_map[my, mx] == pid + 1):
                mx, my = _nearest(pts_by_id[pid], mx, my)
            prov_of.append(pid)
            mark_x.append(min(255, max(0, mx)))
            mark_y.append(min(255, max(0, my)))

    with open(os.path.join(INC, "argmap_data.h"), "w") as f:
        f.write("// Generado por tools/gen_assets.py. No editar a mano.\n#ifndef ARGMAP_DATA_H\n#define ARGMAP_DATA_H\n\n")
        f.write("namespace argmap\n{\n")
        f.write(f"    inline constexpr int screen_x0 = {ARG_X0};\n    inline constexpr int screen_y0 = {ARG_Y0};\n")
        f.write(f"    inline constexpr int province_count = {n};\n")
        f.write("    inline constexpr const char* names[] = {" + ",".join(f'"{p[0]}"' for p in provs) + "};\n")
        f.write(f"    inline constexpr unsigned char province_of[{W * H}] = {{" + ",".join(map(str, prov_of)) + "};\n")
        f.write(f"    inline constexpr unsigned char marker_x[{W * H}] = {{" + ",".join(map(str, mark_x)) + "};\n")
        f.write(f"    inline constexpr unsigned char marker_y[{W * H}] = {{" + ",".join(map(str, mark_y)) + "};\n")
        f.write("}\n\n#endif\n")
    print("Mapa de Argentina:", n, "provincias,", mw, "x", mh, "px")


# ------------------------------------------------------------------ NPCs, flechas y cartel de dialogo
def export_ui():
    ap = [(255, 0, 255), (20, 16, 24), (255, 255, 255)]
    a = Image.new("P", (8, 8), 0)
    ImageDraw.Draw(a).polygon([(0, 1), (7, 1), (4, 6), (3, 6)], fill=2, outline=1)
    write_bmp(os.path.join(GFX, "arrow_down.bmp"), a, ap, 4)
    write_json("arrow_down", {"type": "sprite"})
    r = Image.new("P", (8, 8), 0)
    ImageDraw.Draw(r).polygon([(1, 0), (1, 7), (6, 4), (6, 3)], fill=2, outline=1)
    write_bmp(os.path.join(GFX, "arrow_right.bmp"), r, ap, 4)
    write_json("arrow_right", {"type": "sprite"})

    # cartel de dialogo: panel inferior + pestana para el nombre (el resto es transparente)
    pal = [(255, 0, 255), (24, 28, 52), (232, 232, 244), (70, 78, 120)]
    im = Image.new("P", (256, 256), 0)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 150, 110, 168], 4, fill=1, outline=2)          # pestana nombre
    d.rounded_rectangle([10, 162, 246, 207], 5, fill=1, outline=2)          # panel
    d.rounded_rectangle([12, 164, 244, 205], 4, outline=3)
    d.rectangle([12, 163, 108, 167], fill=1)                                 # une pestana y panel
    write_bmp(os.path.join(GFX, "dialog_panel.bmp"), im, pal, 4)
    write_json("dialog_panel", {"type": "regular_bg"})


def export_sprites():
    export_characters()

    df = dog_frames()
    sheet = Image.new("P", (16, 16 * len(df)), 0)
    for i, f in enumerate(df):
        sheet.paste(f, (0, 16 * i))
    write_bmp(os.path.join(GFX, "dog.bmp"), sheet, DOG_PAL, 4)
    write_json("dog", {"type": "sprite", "height": 16})

    # una imagen por criatura -> bn::sprite_items::c0 .. c9 y cdog (indice 10)
    for i in range(11):
        im, pal = creature_art(i)
        name = "cdog" if i == 10 else f"c{i}"
        write_bmp(os.path.join(GFX, name + ".bmp"), im, pal, 4)
        write_json(name, {"type": "sprite"})
    for stale in ("creatures.bmp", "creatures.json"):
        p = os.path.join(GFX, stale)
        if os.path.exists(p):
            os.remove(p)

    for z in BATTLE_THEMES:
        battle_bg(z)
    export_interiors()
    export_ui()
    export_fx()


if __name__ == "__main__":
    export_world(make_world())
    export_sprites()
    print("Assets generados en", GFX)
