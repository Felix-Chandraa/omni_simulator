#!/usr/bin/env python3
"""Generator TEKSTUR landasan (top-down) untuk slab BALOK Feather-Flight.

Output = satu PNG top-down: aspal abu sedang + marka off-white LEMBUT
(edge line, centerline putus, piano keys threshold, aiming point, nomor RWY).
Dipetakan ke atap slab via ImageMaterialProperty (core/runway.js). Marka jadi
BAGIAN permukaan -> tidak timbul, tidak z-fighting, tidak menyilaukan.

Sumbu gambar: X = panjang landasan (kiri = threshold RWY-kecil), Y = lebar.
Nomor dihitung dari bearing (sama seperti kode: round(bearing/10)%36).

Pemakaian:
  python3 tools/gen_runway_texture.py --length 1128 --width 30 --bearing 147.7 \
      --out dist/models/runway_wiriadinata.png
"""
from __future__ import annotations
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Palet lembut (bukan hitam/putih murni -> tidak bikin mata sakit)
ASPHALT = (62, 62, 60)
ASPHALT_NOISE = 7           # amplitudo grain per-piksel
MARK = (222, 220, 210)      # off-white pudar, bukan #fff
MARK_ALPHA = 210            # 0..255 (marka sedikit transparan -> menyatu)


def rwy_numbers(bearing: float):
    a = round(bearing / 10.0) % 36 or 36
    b = round(((bearing + 180.0) % 360.0) / 10.0) % 36 or 36
    return f"{a:02d}", f"{b:02d}"


def build(length_m: float, width_m: float, bearing: float, ppm: int) -> Image.Image:
    SS = 2  # supersample utk anti-alias
    W = int(round(length_m * ppm)) * SS
    H = int(round(width_m * ppm)) * SS
    m2x = ppm * SS  # meter -> px (dgn supersample)

    # --- aspal + grain (Pillow-only, tanpa numpy) ---
    base = Image.new("RGB", (W, H), ASPHALT)
    grain = Image.effect_noise((W, H), ASPHALT_NOISE * 4).convert("RGB")
    base = Image.blend(base, grain, 0.06)  # grain halus, sedikit menaikkan value
    img = base.convert("RGBA")

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    col = (*MARK, MARK_ALPHA)

    def mx(m):  # meter (panjang) -> px x
        return m * m2x

    def my(t):  # meter dari centerline (-hw..hw) -> px y
        return H / 2 + t * m2x

    hw = width_m / 2.0

    # --- edge lines (kiri-kanan sepanjang landasan) ---
    ew = max(2, int(0.9 * m2x))
    inset = 1.0 * m2x
    d.line([(mx(0), inset), (mx(length_m), inset)], fill=col, width=ew)
    d.line([(mx(0), H - inset), (mx(length_m), H - inset)], fill=col, width=ew)

    # --- centerline putus (30 m garis / 20 m gap) ---
    clw = max(2, int(0.9 * m2x))
    s = 60.0
    while s < length_m - 60.0:
        d.line([(mx(s), my(0)), (mx(min(s + 30, length_m - 60)), my(0))],
               fill=col, width=clw)
        s += 50.0

    # --- piano keys (threshold) di dua ujung: 8 bar longitudinal ---
    def piano(x0):
        bars = 8
        blen = 22.0
        bw = 1.8
        gap = (width_m - bars * bw) / (bars + 1)
        for i in range(bars):
            t = -hw + gap * (i + 1) + bw * i
            y0 = my(t)
            y1 = my(t + bw)
            d.rectangle([x0, y0, x0 + blen * m2x, y1], fill=col)
    piano(mx(6))
    piano(mx(length_m - 6) - 22.0 * m2x)

    # --- aiming point (dua blok besar ~150 m dari tiap threshold) ---
    def aim(xc):
        bl_l, bl_w = 24.0, 3.5
        for sgn in (-1, 1):
            t = sgn * 5.0
            d.rectangle([xc - bl_l / 2 * m2x, my(t - bl_w / 2),
                         xc + bl_l / 2 * m2x, my(t + bl_w / 2)], fill=col)
    aim(mx(150))
    aim(mx(length_m - 150))

    # --- nomor RWY di tiap ujung ---
    numA, numB = rwy_numbers(bearing)
    fpx = int(width_m * 0.62 * m2x)
    try:
        font = ImageFont.truetype(FONT_PATH, fpx)
    except OSError:
        font = ImageFont.load_default()

    def stamp(text, xc_m, rot_deg):
        # tile besar; teks digambar normal lalu diputar sesuai approach.
        big = int(fpx * 2.4)
        tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        td.text((big / 2, big / 2), text[0] + " " + text[1],
                font=font, fill=col, anchor="mm")
        tile = tile.rotate(rot_deg, resample=Image.BICUBIC, expand=False)
        ov.alpha_composite(tile, (int(mx(xc_m) - big / 2), int(H / 2 - big / 2)))

    stamp(numA, 60.0, -90.0)
    stamp(numB, length_m - 60.0, +90.0)

    # composite + sedikit blur marka biar tepi tidak razor (kurangi silau)
    ov = ov.filter(ImageFilter.GaussianBlur(radius=SS * 0.6))
    img = Image.alpha_composite(img, ov)

    # downscale (anti-alias)
    img = img.resize((W // SS, H // SS), Image.LANCZOS).convert("RGB")
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=1128.0)
    ap.add_argument("--width", type=float, default=30.0)
    ap.add_argument("--bearing", type=float, default=147.7)
    ap.add_argument("--ppm", type=int, default=4, help="piksel per meter")
    ap.add_argument("--out", default="runway_wiriadinata.png")
    a = ap.parse_args()
    img = build(a.length, a.width, a.bearing, a.ppm)
    img.save(a.out, optimize=True)
    print(f"[gen-tex] {a.out}  {img.width}x{img.height}px  "
          f"RWY {rwy_numbers(a.bearing)}  ({a.length}x{a.width} m @ {a.ppm} ppm)")


if __name__ == "__main__":
    main()
