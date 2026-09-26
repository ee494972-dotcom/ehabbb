"""Wood board Connect Four emoji: full-bleed wood tiles with recessed holes and glossy discs."""
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / "woodboard"
S, C = 400, 200
HOLE = 150
DISC = 140
RED = {"base": (232, 32, 64), "light": (255, 120, 140), "dark": (160, 12, 40)}
CYAN = {"base": (28, 206, 214), "light": (150, 250, 250), "dark": (8, 140, 156)}
GOLD = (247, 183, 42)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def solid(color, alpha=255):
    return Image.new("RGBA", (S, S), tuple(color) + (alpha,))


def circle_mask(r, cx=C, cy=C):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    return m


def radial(inner, outer, r, cx, cy):
    g = Image.radial_gradient("L").resize((int(r * 2), int(r * 2)))
    m = Image.new("L", (S, S), 255)
    m.paste(g, (int(cx - r), int(cy - r)))
    return Image.composite(solid(outer), solid(inner), m)


def layer(mask, color, alpha=255, blur=0, dx=0, dy=0):
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(solid(color), (dx, dy), mask.point(lambda v: v * alpha // 255))
    return out.filter(ImageFilter.GaussianBlur(blur)) if blur else out


def wood():
    """Warm light wood with horizontal grain that lines up from tile to tile."""
    img = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(img)
    for y in range(S):
        t = 0.5 + 0.5 * math.sin(y / 23.0) * math.sin(y / 61.0)
        d.line((0, y, S, y), fill=lerp((236, 186, 150), (224, 164, 124), t) + (255,))
    grain = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(grain)
    rnd = random.Random(7)
    for _ in range(90):
        y = rnd.uniform(0, S)
        amp, freq, phase = rnd.uniform(0.5, 3), rnd.uniform(0.004, 0.02), rnd.uniform(0, 6)
        tone = rnd.choice(((150, 92, 60), (170, 108, 72), (250, 214, 186)))
        alpha = rnd.randint(22, 60)
        pts = [(x, y + amp * math.sin(x * freq * 6.28 + phase)) for x in range(-10, S + 11, 10)]
        g.line(pts, fill=tone + (alpha,), width=rnd.choice((1, 2, 2, 3)))
    img.alpha_composite(grain.filter(ImageFilter.GaussianBlur(0.6)))
    return img


def hole(img):
    # Bevel: dark lip on the upper edge, light lip on the lower edge, like a routed hole.
    img.alpha_composite(layer(circle_mask(HOLE + 12), (120, 70, 46), 200, 3, 0, -5))
    img.alpha_composite(layer(circle_mask(HOLE + 10), (255, 226, 200), 170, 3, 0, 6))
    inside = radial((52, 34, 82), (22, 13, 40), HOLE * 1.4, C - 40, C + 60)
    img.paste(inside, (0, 0), circle_mask(HOLE))
    shade = ImageChops.subtract(circle_mask(HOLE), circle_mask(HOLE - 26, C + 6, C + 16))
    img.alpha_composite(layer(shade, (8, 4, 18), 190, 8))
    return img


def disc(img, colors):
    base, light, dark = colors["base"], colors["light"], colors["dark"]
    img.alpha_composite(layer(circle_mask(DISC), (10, 4, 20), 170, 6, 0, 8))
    img.paste(radial(lerp(base, light, 0.25), dark, DISC * 1.25, C - 30, C - 40), (0, 0), circle_mask(DISC))
    # Raised centre face with its own soft rim.
    face = circle_mask(96)
    img.alpha_composite(layer(ImageChops.subtract(circle_mask(104), face), dark, 150, 2, 0, 3))
    img.paste(radial(lerp(base, light, 0.35), base, 120, C - 20, C - 30), (0, 0), face)
    gloss = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gloss).ellipse((C - 70, C - 84, C + 50, C - 22), fill=255)
    img.alpha_composite(layer(ImageChops.multiply(gloss, face), (255, 255, 255), 120, 10))
    spec = Image.new("L", (S, S), 0)
    ImageDraw.Draw(spec).ellipse((C - 104, C - 96, C - 64, C - 64), fill=255)
    img.alpha_composite(layer(spec, (255, 255, 255), 200, 6))
    edge = ImageChops.subtract(circle_mask(DISC), circle_mask(DISC - 6))
    img.alpha_composite(layer(edge, lerp(dark, (0, 0, 0), 0.3), 200))
    return img


def gold_ring(img):
    ring = ImageChops.subtract(circle_mask(HOLE + 12), circle_mask(HOLE - 8))
    img.alpha_composite(layer(ring, (150, 90, 10), 200, 2, 0, 3))
    img.alpha_composite(layer(ring, GOLD, 255))
    inner = ImageChops.subtract(circle_mask(HOLE + 4), circle_mask(HOLE - 2))
    img.alpha_composite(layer(inner, (255, 236, 160), 230, 1))


def tile(colors=None, state=""):
    img = hole(wood())
    if colors:
        disc(img, colors)
        if state == "win":
            gold_ring(img)
    return img


SET = {
    "empty": tile(),
    "red": tile(RED), "red_win": tile(RED, "win"),
    "yellow": tile(CYAN), "yellow_win": tile(CYAN, "win"),
}
BOARD = [".......", ".......", "...W...", "..WY...", ".WYR...", "WRYYRRV"]
CODES = {".": "empty", "R": "red", "W": "red_win", "Y": "yellow", "V": "yellow_win"}


def preview(background, gap):
    cell, pad = 96, 30
    board = [".......", ".......", ".......", "..Y....", ".RY....", "RYRY..."]
    won = BOARD
    width = pad * 2 + 7 * cell + 6 * gap
    height = pad * 3 + 2 * (6 * cell + 5 * gap)
    img = Image.new("RGBA", (width, height), background + (255,))
    for index, layout in enumerate((board, won)):
        top = pad + index * (6 * cell + 5 * gap + pad)
        for row, line in enumerate(layout):
            for col, code in enumerate(line):
                art = SET[CODES[code]].resize((100, 100), Image.LANCZOS).resize((cell, cell), Image.LANCZOS)
                img.alpha_composite(art, (pad + col * (cell + gap), top + row * (cell + gap)))
    return img


def main():
    OUT.mkdir(exist_ok=True)
    for name, image in SET.items():
        image.resize((100, 100), Image.LANCZOS).save(OUT / f"{name}.png", optimize=True)
    light = preview((255, 255, 255), 4)
    dark = preview((24, 33, 43), 4)
    sheet = Image.new("RGBA", (light.width * 2 + 20, light.height), (255, 255, 255, 255))
    sheet.alpha_composite(light, (0, 0))
    sheet.alpha_composite(dark, (light.width + 20, 0))
    sheet.convert("RGB").save(OUT.parent / "woodboard_preview.png", optimize=True)


if __name__ == "__main__":
    main()
