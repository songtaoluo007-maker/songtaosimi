from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def build_icon(size: int) -> Image.Image:
    scale = size / 256
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    for y in range(size):
        ratio = y / max(size - 1, 1)
        r = int(8 + 18 * ratio)
        g = int(18 + 52 * ratio)
        b = int(42 + 98 * ratio)
        draw.line((0, y, size, y), fill=(r, g, b, 255))

    mask = _rounded_mask(size, max(4, int(42 * scale)))
    canvas.alpha_composite(Image.composite(base, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask))
    draw = ImageDraw.Draw(canvas)

    inset = int(16 * scale)
    draw.rounded_rectangle(
        (inset, inset, size - inset - 1, size - inset - 1),
        radius=max(3, int(28 * scale)),
        outline=(125, 211, 252, 145),
        width=max(1, int(4 * scale)),
    )

    # Subtle finance shield.
    shield = [
        (int(128 * scale), int(34 * scale)),
        (int(198 * scale), int(62 * scale)),
        (int(188 * scale), int(148 * scale)),
        (int(128 * scale), int(213 * scale)),
        (int(68 * scale), int(148 * scale)),
        (int(58 * scale), int(62 * scale)),
    ]
    draw.polygon(shield, fill=(15, 76, 129, 115), outline=(96, 165, 250, 135))

    # Growth line: stable, readable even at 32px.
    points = [
        (int(48 * scale), int(170 * scale)),
        (int(88 * scale), int(144 * scale)),
        (int(120 * scale), int(154 * scale)),
        (int(158 * scale), int(116 * scale)),
        (int(212 * scale), int(92 * scale)),
    ]
    width = max(2, int(9 * scale))
    draw.line(points, fill=(45, 212, 191, 255), width=width, joint="curve")
    for x, y in points:
        radius = max(2, int(7 * scale))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(254, 240, 138, 255))

    if size >= 48:
        font = _font(max(18, int(82 * scale)), bold=True)
        text = "基"
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(
            ((size - (box[2] - box[0])) / 2, int(46 * scale) - box[1]),
            text,
            font=font,
            fill=(248, 250, 252, 255),
        )

    if size >= 64:
        draw.rounded_rectangle(
            (int(148 * scale), int(34 * scale), int(216 * scale), int(66 * scale)),
            radius=max(2, int(12 * scale)),
            fill=(245, 158, 11, 245),
        )
        small_font = _font(max(10, int(22 * scale)), bold=True)
        label = "AI"
        label_box = draw.textbbox((0, 0), label, font=small_font)
        draw.text(
            (int(182 * scale) - (label_box[2] - label_box[0]) / 2, int(38 * scale) - label_box[1] / 2),
            label,
            font=small_font,
            fill=(17, 24, 39, 255),
        )

    return canvas


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    for size in SIZES:
        icon = build_icon(size)
        icon.save(ASSET_DIR / f"fund-ai-{size}.png")
        images.append(icon)
    images[-1].save(ASSET_DIR / "fund-ai.ico", sizes=[(size, size) for size in SIZES])
    print(f"Generated brand assets in {ASSET_DIR}")


if __name__ == "__main__":
    main()
