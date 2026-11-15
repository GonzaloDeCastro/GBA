"""Genera la musica de PAMPA SALVAJE como modulos .mod (4 canales) con instrumentos sintetizados.

Canciones originales, de aire folklorico argentino (compas de 6/8):
  chacarera.mod : exploracion (La menor / Do mayor)
  malambo.mod   : combates (Mi menor, mas rapido)

Instrumentos (sintetizados con Karplus-Strong): guitarra, bajo, bombo legüero y charango.
Uso: python tools/gen_music.py   (desde la carpeta del proyecto)
"""
import math
import os
import random
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "audio")
os.makedirs(AUDIO, exist_ok=True)

RATE = 8287          # Hz con periodo 428 (etiqueta C-2 de ProTracker)
PERIODS_OCT1 = [856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453]
NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def period(name):
    """Altura 'sonora' (ej. A3 = 220 Hz). Con el muestreo elegido, la etiqueta C-2 suena como Do3."""
    letter = name[:-1]
    octave = int(name[-1])
    label_octave = octave - 1
    assert 1 <= label_octave <= 3, name
    return PERIODS_OCT1[NAMES[letter]] >> (label_octave - 1)


# ---------------------------------------------------------------- instrumentos
def to_int8(samples, peak=118, fade=300):
    m = max(abs(s) for s in samples) or 1.0
    out = []
    n = len(samples)
    for i, s in enumerate(samples):
        v = s / m * peak
        if i > n - fade:
            v *= (n - i) / fade
        out.append(int(round(v)))
    if len(out) % 2:
        out.append(0)
    return out


def karplus(N, length, damp, smooth, seed):
    rng = random.Random(seed)
    buf = [rng.uniform(-1, 1) for _ in range(N)]
    for _ in range(smooth):                       # filtrar el ruido inicial -> timbre mas calido
        buf = [(buf[i] + buf[(i + 1) % N]) / 2 for i in range(N)]
    out = []
    for i in range(length):
        a = buf[i % N]
        b = buf[(i + 1) % N]
        out.append(a)
        buf[i % N] = (a + b) / 2 * damp
    return out


def inst_guitar():
    return to_int8(karplus(63, 7000, 0.9965, 1, 7))


def inst_charango():
    return to_int8(karplus(63, 6000, 0.998, 0, 11), peak=112)


def inst_bass():
    s = karplus(63, 9000, 0.9945, 3, 5)
    s = [(s[i] + s[max(0, i - 1)] + s[max(0, i - 2)]) / 3 for i in range(len(s))]
    return to_int8(s, peak=120)


def inst_bombo():
    out = []
    phase = 0.0
    rng = random.Random(3)
    for i in range(3200):
        f = 42 + 95 * math.exp(-i / 420.0)
        phase += 2 * math.pi * f / RATE
        amp = math.exp(-i / 1000.0)
        v = math.sin(phase) * amp
        if i < 70:
            v += rng.uniform(-1, 1) * (1 - i / 70) * 0.5
        out.append(v)
    return to_int8(out, peak=124, fade=200)


INSTRUMENTS = [("guitarra", inst_guitar), ("bajo", inst_bass), ("bombo", inst_bombo), ("charango", inst_charango)]
S_GUITAR, S_BASS, S_BOMBO, S_CHARANGO = 1, 2, 3, 4


# ---------------------------------------------------------------- escritura del MOD
class Cell:
    def __init__(self, per=0, smp=0, eff=0, par=0):
        self.per, self.smp, self.eff, self.par = per, smp, eff, par

    def pack(self):
        return bytes([
            (self.smp & 0xF0) | ((self.per >> 8) & 0x0F),
            self.per & 0xFF,
            ((self.smp & 0x0F) << 4) | (self.eff & 0x0F),
            self.par & 0xFF,
        ])


def new_pattern():
    return [[Cell() for _ in range(4)] for _ in range(64)]


def write_mod(path, title, patterns, order, samples):
    out = bytearray()
    out += title.encode("ascii")[:20].ljust(20, b"\0")
    for i in range(31):
        if i < len(samples):
            name, data = samples[i]
            out += name.encode("ascii")[:22].ljust(22, b"\0")
            out += struct.pack(">H", len(data) // 2)
            out += bytes([0, 64])
            out += struct.pack(">HH", 0, 1)           # sin loop
        else:
            out += b"\0" * 22 + struct.pack(">H", 0) + bytes([0, 0]) + struct.pack(">HH", 0, 1)
    out += bytes([len(order), 127])
    out += bytes(order) + bytes(128 - len(order))
    out += b"M.K."
    for pat in patterns:
        for row in pat:
            for cell in row:
                out += cell.pack()
    for _name, data in samples:
        out += bytes((v & 0xFF) for v in data)
    with open(path, "wb") as f:
        f.write(out)


# ---------------------------------------------------------------- composicion
def parse_bars(text):
    """Cada compas = 6 corcheas. Tokens: nota (A3, G#3...) o '-' (silencio)."""
    toks = text.split()
    assert len(toks) % 6 == 0, len(toks)
    return toks


CHORDS = {
    "Am": dict(tones=["A3", "C4", "E4"], root="A2", fifth="E3"),
    "Dm": dict(tones=["D4", "F4", "A3"], root="D2", fifth="A2"),
    "E":  dict(tones=["E3", "G#3", "B3"], root="E2", fifth="B2"),
    "C":  dict(tones=["C4", "E4", "G4"], root="C3", fifth="G2"),
    "G":  dict(tones=["G3", "B3", "D4"], root="G2", fifth="D3"),
    "Em": dict(tones=["E3", "G3", "B3"], root="E2", fifth="B2"),
    "D":  dict(tones=["D4", "F#4", "A4"], root="D2", fifth="A2"),
}


def build_pattern(chords, melody, picking, bombo_rows, tempo=None, melody_vol=0x3C):
    pat = new_pattern()
    toks = parse_bars(melody)
    for bar, chord in enumerate(chords):
        ch = CHORDS[chord]
        for r in range(6):
            row = bar * 6 + r
            # melodia (canal 0)
            tok = toks[row]
            if tok != "-":
                pat[row][0] = Cell(period(tok), S_CHARANGO, 0xC, melody_vol)
            # acompanamiento de guitarra (canal 1)
            pk = picking[r]
            if pk is not None:
                vol = 0x38 if r == 0 else 0x2A
                pat[row][1] = Cell(period(ch["tones"][pk]), S_GUITAR, 0xC, vol)
            # bajo (canal 2)
            if r == 0:
                pat[row][2] = Cell(period(ch["root"]), S_BASS, 0xC, 0x40)
            elif r == 3:
                pat[row][2] = Cell(period(ch["fifth"]), S_BASS, 0xC, 0x34)
            # bombo (canal 3)
            if r in bombo_rows:
                pat[row][3] = Cell(428, S_BOMBO, 0xC, bombo_rows[r])
    if tempo:
        pat[0][0].eff, pat[0][0].par = 0xF, tempo
    # cortar el patron a las 48 filas (8 compases de 6/8)
    cell = pat[47][3] if pat[47][3].eff == 0 else pat[47][0]
    cell.eff, cell.par = 0xD, 0
    return pat


def chacarera():
    picking = [0, None, 1, 2, 1, None]
    bombo = {0: 0x40, 3: 0x30, 5: 0x20}
    a_mel = ("E4 - E4 D4 C4 D4  E4 - C4 - A3 -  D4 - F4 E4 D4 C4  B3 - - E4 - -  "
             "E4 - E4 D4 C4 D4  F4 - E4 D4 C4 B3  G#3 - B3 - E4 -  A3 - - - - -")
    b_mel = ("E4 - G4 - E4 -  C4 - E4 D4 C4 -  D4 - G4 F4 D4 -  B3 - D4 - G3 -  "
             "F4 - A4 - F4 -  E4 - B3 - G#3 -  A3 - C4 - E4 -  A4 - - E4 - -")
    pa = build_pattern(["Am", "Am", "Dm", "E", "Am", "Dm", "E", "Am"], a_mel, picking, bombo, tempo=0x4B)
    pb = build_pattern(["C", "C", "G", "G", "Dm", "E", "Am", "Am"], b_mel, picking, bombo)
    samples = [(n, f()) for n, f in INSTRUMENTS]
    write_mod(os.path.join(AUDIO, "chacarera.mod"), "chacarera pampa", [pa, pb], [0, 1, 0, 1], samples)


def malambo():
    picking = [0, 1, 2, 1, 2, 1]
    bombo = {0: 0x40, 1: 0x1C, 2: 0x24, 3: 0x38, 4: 0x1C, 5: 0x2C}
    mel = ("B4 G4 E4 G4 B4 G4  E4 G4 B4 - A4 G4  G4 E4 C4 E4 G4 E4  A4 F#4 D4 F#4 A4 F#4  "
           "B4 G4 E4 G4 B4 G4  G4 E4 C4 - D4 E4  F#4 A4 D4 - F#4 A4  E4 - - B3 - -")
    p = build_pattern(["Em", "Em", "C", "D", "Em", "C", "D", "Em"], mel, picking, bombo, tempo=0x70, melody_vol=0x3E)
    samples = [(n, f()) for n, f in INSTRUMENTS]
    write_mod(os.path.join(AUDIO, "malambo.mod"), "malambo de batalla", [p], [0, 0], samples)


if __name__ == "__main__":
    chacarera()
    malambo()
    print("Musica generada en", AUDIO)
