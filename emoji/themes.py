"""Ten modern Connect Four emoji themes (empty, red, yellow, red_win, yellow_win) plus a preview."""
import colorsys
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "themes"
S, C = 400, 200
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
RED, YELLOW = "red", "yellow"
# Warm-red and amber pairs tuned to stay distinct at emoji size.
HUE = {RED: ((255, 92, 92), (230, 20, 90)), YELLOW: ((255, 224, 80), (255, 140, 0))}


def blank():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def solid(color):
    return Image.new("RGBA", (S, S), tuple(color) + ((255,) if len(color) == 3 else ()))


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


@lru_cache(None)
def squircle_mask(inset=8, n=5.0):
    m = Image.new("L", (S, S), 0)
    px = m.load()
    half = (S - 2 * inset) / 2
    for y in range(S):
        for x in range(S):
            u, v = abs(x + 0.5 - C) / half, abs(y + 0.5 - C) / half
            if u <= 1 and v <= 1 and u ** n + v ** n <= 1:
                px[x, y] = 255
    return m.filter(ImageFilter.GaussianBlur(0.8))


def circle_mask(r, cx=C, cy=C):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    return m


def linear(c1, c2, angle=90):
    """Gradient from c1 to c2; angle 90 runs top to bottom."""
    g = Image.linear_gradient("L").resize((S * 2, S * 2)).rotate(90 - angle, resample=Image.BICUBIC)
    g = g.crop((S // 2, S // 2, S // 2 + S, S // 2 + S))
    return Image.composite(solid(c2), solid(c1), g)


def radial(c_in, c_out, r, cx=C, cy=C):
    g = Image.radial_gradient("L").resize((int(r * 2), int(r * 2)))
    m = Image.new("L", (S, S), 255)
    m.paste(g, (int(cx - r), int(cy - r)))
    return Image.composite(solid(c_out), solid(c_in), m)


def put(img, layer, mask):
    img.paste(layer, (0, 0), ImageChops.multiply(mask, layer.getchannel("A")))


def blur_shape(mask, color, blur, dx=0, dy=0, alpha=255):
    layer = blank()
    layer.paste(solid(color), (dx, dy), mask.point(lambda v: v * alpha // 255))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def ring_mask(r, width, cx=C, cy=C):
    return ImageChops.subtract(circle_mask(r, cx, cy), circle_mask(r - width, cx, cy))


def star(cx, cy, outer, inner, n=5, rot=-math.pi / 2):
    return [(cx + (outer if k % 2 == 0 else inner) * math.cos(rot + k * math.pi / n),
             cy + (outer if k % 2 == 0 else inner) * math.sin(rot + k * math.pi / n)) for k in range(n * 2)]


def sparkle(img, cx, cy, size, color=(255, 255, 255, 255)):
    ImageDraw.Draw(img).polygon(star(cx, cy, size, size * 0.2, n=4, rot=0), fill=color)


def win_star(img, cx, cy, size):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(star(cx, cy, size, size * 0.45), fill=255)
    img.alpha_composite(blur_shape(m, (0, 0, 0), 6, 0, 5, 110))
    put(img, solid((255, 255, 255)), m)


def glass_sheen(img, mask, strength=150):
    """White top-down sheen clipped to the shape, like light on glass."""
    sheen = linear((255, 255, 255), (255, 255, 255), 90)
    fade = Image.linear_gradient("L").resize((S, S)).point(lambda v: max(0, strength - v * 2))
    sheen.putalpha(ImageChops.multiply(fade, mask))
    img.alpha_composite(sheen)


# 1 --------------------------------------------------------- Liquid Glass
def liquid_glass(kind, win):
    img = blank()
    tile = squircle_mask()
    img.alpha_composite(blur_shape(tile, (60, 80, 140), 14, 0, 10, 70))
    put(img, linear((236, 242, 255), (196, 210, 240)), tile)
    edge = ImageChops.subtract(tile, squircle_mask(16))
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), edge.point(lambda v: v * 200 // 255)))
    hole = circle_mask(138)
    put(img, linear((170, 186, 222), (214, 224, 246)), hole)
    img.alpha_composite(blur_shape(ring_mask(138, 22), (90, 110, 170), 8, 0, 6, 120))
    if kind is None:
        return img
    top, bottom = HUE[kind]
    body = circle_mask(128)
    img.alpha_composite(blur_shape(body, bottom, 14, 0, 12, 150))
    if win:
        img.alpha_composite(blur_shape(circle_mask(150), top, 18, 0, 0, 255))
    put(img, linear(top, bottom, 60), body)
    glass_sheen(img, circle_mask(118, C, C - 8), 190)
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(128, 7).point(lambda v: v * 180 // 255)))
    if win:
        win_star(img, C, C + 4, 64)
    return img


# 2 --------------------------------------------------------- Aurora Orbs
def aurora(kind, win):
    img = blank()
    tile = squircle_mask()
    base = solid((12, 13, 24))
    for color, x, y, r in (((70, 40, 160), 90, 70, 150), ((0, 150, 150), 330, 330, 150)):
        base.alpha_composite(blur_shape(circle_mask(r, x, y), color, 70, 0, 0, 110))
    put(img, base, tile)
    put(img, solid((24, 26, 44)), circle_mask(120))
    img.alpha_composite(Image.composite(solid((52, 56, 90)), blank(), ring_mask(120, 5)))
    if kind is None:
        return img
    top, bottom = HUE[kind]
    img.alpha_composite(blur_shape(circle_mask(150 if win else 125), bottom, 34 if win else 26, 0, 0, 255))
    put(img, radial(lerp(top, (255, 255, 255), 0.45), bottom, 150, C - 40, C - 50), circle_mask(118))
    if win:
        img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(126, 10)))
        win_star(img, C, C + 4, 60)
    return img


# 3 --------------------------------------------------------- Clay
def clay(kind, win):
    img = blank()
    tile = squircle_mask()
    put(img, linear((255, 250, 255), (240, 232, 255)), tile)
    put(img, solid((232, 222, 252)), circle_mask(132))
    rim = blur_shape(ring_mask(150, 34, C + 10, C + 12), (200, 184, 236), 10, 0, 0, 255)
    put(img, rim, circle_mask(132))
    if kind is None:
        return img
    color = {RED: (255, 110, 120), YELLOW: (255, 204, 70)}[kind]
    img.alpha_composite(blur_shape(circle_mask(138), (190, 170, 230), 12, 4, 10, 150))
    disc = circle_mask(138)
    body = solid(color)
    body.alpha_composite(blur_shape(circle_mask(104, C + 50, C + 56), lerp(color, (200, 60, 90), 0.22), 36, 0, 0, 150))
    body.alpha_composite(blur_shape(circle_mask(70, C - 36, C - 42), lerp(color, (255, 255, 255), 0.75), 30, 0, 0, 255))
    put(img, body, disc)
    if win:
        pts = star(C, C + 4, 70, 32)
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        img.alpha_composite(blur_shape(m, lerp(color, (90, 30, 50), 0.5), 8, 4, 8, 140))
        put(img, solid((255, 255, 255)), m)
    return img


# 4 --------------------------------------------------------- Neumorphism
def neumorph(kind, win):
    img = blank()
    bg = (34, 37, 46)
    tile = squircle_mask()
    put(img, solid(bg), tile)
    hole = circle_mask(132)
    put(img, solid((28, 30, 38)), hole)
    inner = blank()
    inner.alpha_composite(blur_shape(ring_mask(150, 36, C + 12, C + 12), (10, 11, 16), 12, 0, 0, 255))
    inner.alpha_composite(blur_shape(ring_mask(150, 36, C - 12, C - 12), (58, 62, 76), 12, 0, 0, 220))
    put(img, inner, hole)
    if kind is None:
        return img
    top, bottom = HUE[kind]
    disc = circle_mask(112)
    img.alpha_composite(blur_shape(disc, (8, 9, 14), 14, 12, 12, 230))
    img.alpha_composite(blur_shape(disc, (64, 68, 84), 14, -10, -10, 160))
    put(img, linear(lerp(top, (255, 255, 255), 0.15), bottom, 45), disc)
    if win:
        img.alpha_composite(blur_shape(ring_mask(132, 12), top, 10, 0, 0, 255))
        win_star(img, C, C + 4, 58)
    return img


# 5 --------------------------------------------------------- Holographic
def holo_layer(kind):
    layer = blank()
    px = layer.load()
    tint = HUE[kind][0]
    for y in range(S):
        for x in range(S):
            angle = math.atan2(y - C, x - C)
            hue = (angle / (2 * math.pi) + (x + y) / (4 * S)) % 1
            r, g, b = colorsys.hsv_to_rgb(hue, 0.35, 1.0)
            rainbow = (r * 255, g * 255, b * 255)
            px[x, y] = tuple(round(t * 0.78 + rb * 0.22) for t, rb in zip(tint, rainbow)) + (255,)
    return layer


@lru_cache(None)
def holo(kind_key):
    return holo_layer(kind_key)


def holographic(kind, win):
    img = blank()
    tile = squircle_mask()
    img.alpha_composite(blur_shape(tile, (0, 0, 0), 14, 0, 10, 60))
    put(img, linear((246, 244, 252), (222, 226, 240), 120), tile)
    put(img, linear((210, 214, 232), (232, 234, 246)), circle_mask(134))
    if kind is None:
        return img
    disc = circle_mask(124)
    img.alpha_composite(blur_shape(disc, HUE[kind][1], 16, 0, 12, 140))
    put(img, holo(kind), disc)
    edge = Image.radial_gradient("L").resize((260, 260))
    shade = Image.new("L", (S, S), 0)
    shade.paste(edge.point(lambda v: max(0, v - 120) * 2), (C - 130, C - 130))
    put(img, Image.composite(solid(HUE[kind][1]), blank(), shade), disc)
    glass_sheen(img, circle_mask(112, C, C - 10), 170)
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(124, 6)))
    if win:
        win_star(img, C, C + 4, 60)
        for x, y, s in ((C + 112, C - 112, 40), (C - 100, C + 110, 28)):
            sparkle(img, x, y, s)
    return img


# 6 --------------------------------------------------------- Neo-Brutalism
def brutal(kind, win):
    img = blank()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((34, 34, 386, 386), radius=36, fill=(0, 0, 0))
    d.rounded_rectangle((14, 14, 366, 366), radius=36, fill=(255, 248, 231), outline=(0, 0, 0), width=14)
    if kind is None:
        d.ellipse((72, 72, 308, 308), outline=(0, 0, 0), width=12)
        return img
    color = {RED: (255, 82, 82), YELLOW: (255, 214, 0)}[kind]
    d.ellipse((82, 82, 318, 318), fill=(0, 0, 0))
    d.ellipse((62, 62, 298, 298), fill=color, outline=(0, 0, 0), width=14)
    if win:
        d.polygon(star(180, 184, 80, 34), fill=(255, 255, 255), outline=(0, 0, 0), width=10)
    return img


# 7 --------------------------------------------------------- Liquid Chrome
def chrome(kind, win):
    img = blank()
    tile = squircle_mask()
    put(img, linear((26, 26, 32), (10, 10, 14)), tile)
    img.alpha_composite(Image.composite(solid((70, 70, 84)), blank(), ring_mask(134, 6)))
    if kind is None:
        return img
    top, bottom = HUE[kind]
    bands = blank()
    bd = ImageDraw.Draw(bands)
    stops = [(0, lerp(top, (255, 255, 255), 0.85)), (0.38, top), (0.5, lerp(bottom, (0, 0, 0), 0.55)),
             (0.56, lerp(top, (255, 255, 255), 0.6)), (0.8, bottom), (1, lerp(bottom, (0, 0, 0), 0.4))]
    for y in range(S):
        t = y / S
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                bd.line((0, y, S, y), fill=lerp(c0, c1, (t - t0) / (t1 - t0)) + (255,))
                break
    disc = circle_mask(124)
    if win:
        img.alpha_composite(blur_shape(circle_mask(146), top, 22, 0, 0, 255))
    put(img, bands, disc)
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(124, 5).point(lambda v: v * 200 // 255)))
    highlight = blank()
    ImageDraw.Draw(highlight).ellipse((C - 90, C - 108, C - 10, C - 76), fill=(255, 255, 255, 230))
    img.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(6)))
    if win:
        sparkle(img, C + 70, C - 70, 60)
    return img


# 8 --------------------------------------------------------- Soft Glow Lights
def lights(kind, win):
    img = blank()
    tile = squircle_mask()
    put(img, linear((20, 22, 44), (8, 9, 22)), tile)
    if kind is None:
        put(img, solid((34, 38, 70)), circle_mask(24))
        img.alpha_composite(Image.composite(solid((34, 38, 70)), blank(), ring_mask(118, 4)))
        return img
    top, bottom = HUE[kind]
    img.alpha_composite(blur_shape(circle_mask(150 if win else 130), bottom, 40, 0, 0, 255))
    img.alpha_composite(blur_shape(circle_mask(96), top, 18, 0, 0, 255))
    img.alpha_composite(blur_shape(circle_mask(56), lerp(top, (255, 255, 255), 0.8), 14, 0, 0, 255))
    if win:
        rays = Image.new("L", (S, S), 0)
        rd = ImageDraw.Draw(rays)
        for k in range(8):
            a = k * math.pi / 4
            rd.polygon([(C, C), (C + 190 * math.cos(a - 0.06), C + 190 * math.sin(a - 0.06)),
                        (C + 190 * math.cos(a + 0.06), C + 190 * math.sin(a + 0.06))], fill=160)
        img.alpha_composite(blur_shape(ImageChops.multiply(rays, tile), (255, 255, 255), 3, 0, 0, 255))
    return img


# 9 --------------------------------------------------------- Squircle Icons
def icons(kind, win):
    img = blank()
    if kind is None:
        ghost = squircle_mask(40)
        put(img, solid((44, 48, 62)), ghost)
        put(img, solid((30, 33, 44)), squircle_mask(52))
        return img
    top, bottom = HUE[kind]
    shape = squircle_mask(30)
    img.alpha_composite(blur_shape(shape, bottom, 18, 0, 16, 170))
    put(img, linear(top, bottom, 60), shape)
    glass_sheen(img, squircle_mask(44), 120)
    d = ImageDraw.Draw(img)
    if win:
        d.polygon(star(C, C + 6, 96, 40), fill=(255, 255, 255))
    else:
        d.ellipse((C - 62, C - 62, C + 62, C + 62), outline=(255, 255, 255, 235), width=22)
    return img


# 10 -------------------------------------------------------- Mesh Gradient Frost
def mesh(kind, win):
    img = blank()
    tile = squircle_mask()
    base = solid((88, 60, 220))
    for color, x, y, r in (((255, 90, 170), 60, 60, 170), ((0, 200, 255), 360, 90, 160),
                           ((120, 255, 200), 330, 360, 150), ((140, 80, 255), 60, 360, 170)):
        base.alpha_composite(blur_shape(circle_mask(r, x, y), color, 60, 0, 0, 255))
    put(img, base, tile)
    frost = circle_mask(132)
    put(img, Image.composite(solid((255, 255, 255)), blank(), frost.point(lambda v: v * 70 // 255)), frost)
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(132, 6).point(lambda v: v * 190 // 255)))
    if kind is None:
        return img
    top, bottom = HUE[kind]
    disc = circle_mask(116)
    img.alpha_composite(blur_shape(disc, (30, 10, 60), 14, 0, 12, 140))
    put(img, linear(lerp(top, (255, 255, 255), 0.2), bottom, 70), disc)
    glass_sheen(img, circle_mask(104, C, C - 10), 150)
    img.alpha_composite(Image.composite(solid((255, 255, 255)), blank(), ring_mask(116, 6)))
    if win:
        img.alpha_composite(blur_shape(ring_mask(138, 10), (255, 255, 255), 6, 0, 0, 255))
        win_star(img, C, C + 4, 60)
    return img


THEMES = [
    ("Liquid Glass", liquid_glass), ("Aurora Orbs", aurora), ("Clay", clay), ("Neumorphism", neumorph),
    ("Holographic", holographic), ("Neo-Brutalism", brutal), ("Liquid Chrome", chrome),
    ("Soft Glow", lights), ("Squircle Icons", icons), ("Mesh Frost", mesh),
]
BOARD = [".......", ".......", "...W...", "..WY...", ".WYR...", "WRYYRRV"]
PIECES = {".": (None, False), "R": (RED, False), "Y": (YELLOW, False), "W": (RED, True), "V": (YELLOW, True)}


def main():
    OUT.mkdir(exist_ok=True)
    cell, gap, pad, label_h = 64, 5, 26, 58
    board_w, board_h = 7 * cell + 6 * gap, 6 * cell + 5 * gap
    sheet = Image.new("RGBA", (pad + 2 * (board_w + pad), pad + 5 * (label_h + board_h + pad)), (23, 33, 43, 255))
    font = ImageFont.truetype(FONT, 30)
    draw = ImageDraw.Draw(sheet)
    for index, (name, painter) in enumerate(THEMES, 1):
        folder = OUT / f"{index:02d}_{name.lower().replace(' ', '_').replace('-', '_')}"
        folder.mkdir(exist_ok=True)
        art = {code: painter(kind, win).resize((100, 100), Image.LANCZOS) for code, (kind, win) in PIECES.items()}
        for code, file in ((".", "empty"), ("R", "red"), ("Y", "yellow"), ("W", "red_win"), ("V", "yellow_win")):
            art[code].save(folder / f"{file}.png", optimize=True)
        x0 = pad + ((index - 1) % 2) * (board_w + pad)
        y0 = pad + ((index - 1) // 2) * (label_h + board_h + pad)
        draw.text((x0, y0 + 8), f"{index}. {name}", font=font, fill=(235, 240, 248))
        for row, line in enumerate(BOARD):
            for col, code in enumerate(line):
                sheet.alpha_composite(art[code].resize((cell, cell), Image.LANCZOS),
                                      (x0 + col * (cell + gap), y0 + label_h + row * (cell + gap)))
    sheet.convert("RGB").save(OUT.parent / "themes_preview.png", optimize=True)


if __name__ == "__main__":
    main()
