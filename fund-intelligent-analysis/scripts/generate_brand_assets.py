from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
SOURCE_ICON = ASSET_DIR / "fund-ai-source.png"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 192, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def load_source_icon() -> Image.Image:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE_ICON}")
    source = Image.open(SOURCE_ICON).convert("RGBA")
    side = min(source.size)
    return ImageOps.fit(source, (side, side), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def build_icon(source: Image.Image, size: int) -> Image.Image:
    return source.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    source = load_source_icon()
    for size in PNG_SIZES:
        icon = build_icon(source, size)
        icon.save(ASSET_DIR / f"fund-ai-{size}.png")
    source.save(ASSET_DIR / "fund-ai.ico", sizes=[(size, size) for size in ICO_SIZES])
    print(f"Generated brand assets in {ASSET_DIR}")


if __name__ == "__main__":
    main()
