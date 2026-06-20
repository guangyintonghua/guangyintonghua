from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    return ImageFont.load_default()


def add_square_copy(src: Path, out: Path) -> None:
    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((52, 54, 506, 322), radius=32, fill=(255, 249, 243, 214))
    draw.text((84, 94), "米白蓝灰波点", font=load_font(66), fill=(27, 33, 44, 255))
    draw.text((86, 174), "亚麻感桌布", font=load_font(54), fill=(27, 33, 44, 255))
    draw.text((88, 252), "流苏边一挂  餐桌更显轻松", font=load_font(28), fill=(102, 108, 118, 255))
    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(out, quality=95)


def add_portrait_copy(src: Path, out: Path) -> None:
    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((70, 88, 640, 374), radius=40, fill=(255, 249, 243, 216))
    draw.text((108, 132), "米白蓝灰波点", font=load_font(72), fill=(27, 33, 44, 255))
    draw.text((110, 220), "自然光下很耐看", font=load_font(44), fill=(27, 33, 44, 255))
    draw.text((112, 286), "低饱和家居感  更适合日常餐桌", font=load_font(30), fill=(102, 108, 118, 255))
    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(out, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish generated tablecloth images into the product folder.")
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    generated_dir = Path(args.generated_dir)
    generated_paths = sorted(generated_dir.glob("*.png"), key=lambda path: path.stat().st_mtime)
    if len(generated_paths) < 4:
        raise RuntimeError("Expected at least 4 generated images.")

    white_src, square_src, portrait_src, detail_src = generated_paths[:4]

    white_dir = product_dir / "白底图"
    square_dir = product_dir / "1比1主图"
    portrait_dir = product_dir / "3比4主图"
    detail_dir = product_dir / "详情页"

    for directory in [white_dir, square_dir, portrait_dir, detail_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(white_src, white_dir / "白底图_正式_01.png")
    shutil.copy2(square_src, square_dir / "主图_场景无文案_01.png")
    shutil.copy2(portrait_src, portrait_dir / "主图_场景无文案_01.png")
    shutil.copy2(detail_src, detail_dir / "详情页_首屏场景_01.png")

    add_square_copy(square_src, square_dir / "主图_场景文案_01.jpg")
    add_portrait_copy(portrait_src, portrait_dir / "主图_场景文案_01.jpg")

    print(white_dir / "白底图_正式_01.png")
    print(square_dir / "主图_场景无文案_01.png")
    print(square_dir / "主图_场景文案_01.jpg")
    print(portrait_dir / "主图_场景无文案_01.png")
    print(portrait_dir / "主图_场景文案_01.jpg")
    print(detail_dir / "详情页_首屏场景_01.png")


if __name__ == "__main__":
    main()
