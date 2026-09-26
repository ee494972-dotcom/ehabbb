"""Draw the Connect Four custom emoji set (100x100 PNG) and a board preview."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "pack"
S = 400                      # drawing size; saved at 100x100
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BOARD_TOP, BOARD_BOTTOM = (54, 110, 235), (22, 62, 170)
BOARD_EDGE = (12, 38, 115)
HOLE_IN, HOLE_OUT = (30, 44, 96), (6, 11, 32)
RED = {"light": (255, 105, 95), "base": (222, 38, 38), "dark": (128, 12, 18)}
YELLOW = {"light": (255, 240, 140), "base": (250, 196, 28), "dark": (170, 110, 0)}
GOLD = (255, 214, 64)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def radial(size, center, radius, inner, outer, power=1.0):
    """RGBA image with a radial gradient clipped to a circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = center
    steps = int(radius)
    for i in range(steps, 0, -1):
        t = (i / steps) ** power
        draw.ellipse((cx - i, cy - i, cx + i, cy + i), fill=lerp(inner, outer, t) + (255,))
    return img


def tile():
    """Rounded blue board square with a vertical gradient and a lit top edge."""
    grad = Image.new("RGBA", (S, S))
    draw = ImageDraw.Draw(grad)
    for y in range(S):
        draw.line((0, y, S, y), fill=lerp(BOARD_TOP, BOARD_BOTTOM, y / S) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((4, 4, S - 5, S - 5), radius=70, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    edge = ImageDraw.Draw(img)
    edge.rounded_rectangle((4, 4, S - 5, S - 5), radius=70, outline=BOARD_EDGE + (255,), width=10)
    shine = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shine).rounded_rectangle((18, 16, S - 19, S - 19), radius=58,
                                            outline=(150, 190, 255, 120), width=6)
    shine_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shine_mask).rectangle((0, 0, S, S // 2), fill=255)
    img.paste(shine, (0, 0), Image.composite(shine.getchannel("A"), Image.new("L", (S, S), 0), shine_mask))
    return img


def hole(img):
    """Cut a recessed hole: dark rim, inner shadow from the top."""
    r = 150
    c = S // 2
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).ellipse((c - r - 12, c - r - 12, c + r + 12, c + r + 12), fill=BOARD_EDGE + (255,))
    img.alpha_composite(rim)
    inside = radial(S, (c, c + 40), r + 40, HOLE_IN, HOLE_OUT, power=1.3)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((c - r, c - r, c + r, c + r), fill=255)
    img.paste(inside, (0, 0), mask)
    return img


def disc(img, colors, win=False):
    c, r = S // 2, 140
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((c - r, c - r + 14, c + r, c + r + 14), fill=(0, 0, 0, 170))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    if win:
        glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((c - r - 6, c - r - 6, c + r + 6, c + r + 6), fill=GOLD + (255,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
    body = radial(S, (c - 40, c - 50), r + 70, colors["light"], colors["dark"], power=0.9)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((c - r, c - r, c + r, c + r), fill=255)
    img.paste(body, (0, 0), mask)
    # Raised rim: an inner recessed face with a light lower edge and dark upper edge.
    inner = 96
    face = radial(S, (c - 20, c - 30), inner + 60, colors["base"], colors["dark"], power=1.1)
    fmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(fmask).ellipse((c - inner, c - inner, c + inner, c + inner), fill=255)
    img.paste(face, (0, 0), fmask)
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.arc((c - inner, c - inner, c + inner, c + inner), 200, 340, fill=colors["dark"] + (230,), width=10)
    rd.arc((c - inner, c - inner, c + inner, c + inner), 20, 160, fill=colors["light"] + (200,), width=8)
    img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(1.5)))
    shine = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse((c - 105, c - 118, c - 5, c - 58), fill=(255, 255, 255, 150))
    img.alpha_composite(shine.filter(ImageFilter.GaussianBlur(12)))
    if win:
        star(img, c, c + 4, 70, 30)
    edge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(edge).ellipse((c - r, c - r, c + r, c + r),
                                 outline=(GOLD if win else colors["dark"]) + (255,), width=10 if win else 5)
    img.alpha_composite(edge)
    return img


def star(img, cx, cy, outer, inner):
    points = []
    for k in range(10):
        angle = -math.pi / 2 + k * math.pi / 5
        radius = outer if k % 2 == 0 else inner
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x, y + 6) for x, y in points], fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(points, fill=(255, 255, 255, 255), outline=GOLD + (255,), width=5)
    img.alpha_composite(layer)


def column_key(number):
    img = tile()
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 190)
    text = str(number)
    box = draw.textbbox((0, 0), text, font=font)
    x = (S - (box[2] - box[0])) / 2 - box[0]
    y = 150 - (box[3] - box[1]) / 2 - box[1]
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x, y + 8), text, font=font, fill=(5, 20, 70, 200))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    arrow = [(S / 2 - 62, 282), (S / 2 + 62, 282), (S / 2, 350)]
    draw.polygon(arrow, fill=GOLD + (255,))
    return img


def save(img, name):
    img.resize((100, 100), Image.LANCZOS).save(OUT / f"{name}.png", optimize=True)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    art = {
        "empty": save(hole(tile()), "empty"),
        "red": save(disc(hole(tile()), RED), "red"),
        "yellow": save(disc(hole(tile()), YELLOW), "yellow"),
        "red_win": save(disc(hole(tile()), RED, win=True), "red_win"),
        "yellow_win": save(disc(hole(tile()), YELLOW, win=True), "yellow_win"),
    }
    keys = [save(column_key(n), f"col{n}") for n in range(1, 8)]

    # Preview: the key row above a mid-game board with a winning diagonal, on a
    # neutral chat-like background, at 2x emoji size.
    board = [
        ".......",
        ".......",
        "...W...",
        "..WY...",
        ".WYR...",
        "WRYYRR.",
    ]
    names = {".": "empty", "R": "red", "Y": "yellow", "W": "red_win"}
    cell, gap, pad = 200, 14, 40
    width = pad * 2 + 7 * cell + 6 * gap
    height = pad * 2 + 7 * cell + 6 * gap + 30
    preview = Image.new("RGBA", (width, height), (24, 33, 45, 255))
    for col, key in enumerate(keys):
        preview.alpha_composite(key.resize((cell, cell), Image.LANCZOS), (pad + col * (cell + gap), pad))
    for row, line in enumerate(board):
        for col, ch in enumerate(line):
            tile_img = art[names[ch]].resize((cell, cell), Image.LANCZOS)
            preview.alpha_composite(tile_img, (pad + col * (cell + gap), pad + 30 + (row + 1) * (cell + gap)))
    preview.convert("RGB").save(OUT.parent / "preview.png", optimize=True)


if __name__ == "__main__":
    main()
