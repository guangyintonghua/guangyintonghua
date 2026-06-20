from __future__ import annotations

import argparse
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    return ImageFont.load_default()


def clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    title: str,
    subtitle: str,
    title_size: int,
    subtitle_size: int,
    fill: tuple[int, int, int, int],
    subfill: tuple[int, int, int, int],
    width: int,
) -> int:
    ty = y
    title_font = load_font(title_size)
    subtitle_font = load_font(subtitle_size)
    for line in wrap_lines(title, width):
        draw.text((x, ty), line, font=title_font, fill=fill)
        ty += title_size + 4
    ty += 8
    for line in wrap_lines(subtitle, width + 2):
        draw.text((x, ty), line, font=subtitle_font, fill=subfill)
        ty += subtitle_size + 6
    return ty


def compose_square(src: Path, out: Path, title: str, subtitle: str) -> None:
    img = Image.open(src).convert("RGBA").resize((800, 800), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((44, 42, 468, 294), radius=34, fill=(255, 249, 243, 222))
    draw_text_block(draw, 78, 82, title, subtitle, 58, 28, (26, 33, 44, 255), (98, 106, 116, 255), 8)
    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(out, quality=95)


def compose_portrait(src: Path, out: Path, title: str, subtitle: str) -> None:
    img = Image.open(src).convert("RGBA").resize((900, 1200), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((58, 60, 668, 332), radius=40, fill=(255, 249, 243, 220))
    draw_text_block(draw, 92, 104, title, subtitle, 66, 30, (26, 33, 44, 255), (98, 106, 116, 255), 9)
    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(out, quality=95)


def compose_selling(src: Path, out: Path) -> None:
    base = Image.new("RGB", (750, 1200), "#F6F1E9")
    draw = ImageDraw.Draw(base)
    draw.text((48, 54), "这款桌布先看 4 个点", font=load_font(46), fill="#1B212C")
    draw.text((50, 114), "不是只看花型，更要看上桌后的购买理由", font=load_font(24), fill="#6B7280")

    closeup = Image.open(src).convert("RGB")
    closeup = closeup.resize((650, 420), Image.Resampling.LANCZOS)
    base.paste(closeup, (50, 170))

    cards = [
        ("清爽配色", "米白底配蓝灰点，桌面更显干净。"),
        ("流苏花边", "桌边一垂下来，层次更完整。"),
        ("亚麻感纹理", "近看有织物肌理，不会显单薄。"),
        ("常用尺寸", "茶几小桌长桌都能选。"),
    ]
    positions = [(50, 632), (392, 632), (50, 874), (392, 874)]
    for (title, body), (x, y) in zip(cards, positions):
        draw.rounded_rectangle((x, y, x + 308, y + 202), radius=28, fill="#FFFCF7")
        draw.text((x + 24, y + 22), title, font=load_font(30), fill="#1B212C")
        text_y = y + 74
        for line in wrap_lines(body, 7):
            draw.text((x + 24, text_y), line, font=load_font(20), fill="#6B7280")
            text_y += 30
    base.save(out, quality=95)


def compose_detail_slices(product_dir: Path, bases: list[Path], closeup: Path, sizes: list[str], prices: list[str]) -> None:
    detail_dir = product_dir / "详情页"
    clear_dir(detail_dir)

    # slice 1
    base = Image.open(bases[0]).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (750, 1200), "#F9F5EF")
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((44, 52, 530, 330), radius=34, fill=(255, 249, 243))
    draw_text_block(draw, 72, 92, "米白蓝灰波点桌布", "一铺上桌面，家里就更显干净轻松", 52, 28, (26, 33, 44), (98, 106, 116), 9)
    canvas.save(detail_dir / "详情页_切片_01.jpg", quality=95)

    # slice 2
    base = Image.open(bases[1]).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (750, 1200), "#FAF6F0")
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((48, 60, 560, 356), radius=36, fill=(255, 251, 245))
    draw_text_block(draw, 78, 104, "低饱和配色更耐看", "米白底配蓝灰点，比纯白更耐脏，比深色更轻盈", 48, 28, (26, 33, 44), (98, 106, 116), 10)
    canvas.save(detail_dir / "详情页_切片_02.jpg", quality=95)

    # slice 3
    close = Image.open(closeup).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (750, 1200), "#F6F1EA")
    canvas.paste(close, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((42, 52, 516, 344), radius=34, fill=(255, 249, 243))
    draw_text_block(draw, 72, 92, "流苏花边更出片", "远看有装饰感，近看也能看到边缘细节", 46, 24, (26, 33, 44), (98, 106, 116), 8)
    canvas.save(detail_dir / "详情页_切片_03.jpg", quality=95)

    # slice 4
    canvas = Image.new("RGB", (750, 1200), "#F8F3EC")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((30, 36, 720, 1160), radius=34, fill="#FFFCF7")
    draw.text((68, 86), "常用尺寸都能选", font=load_font(48), fill="#1B212C")
    draw.text((70, 150), "小桌、餐桌、长桌都更容易找到合适规格", font=load_font(26), fill="#6B7280")
    y = 260
    for idx, (size, price) in enumerate(zip(sizes, prices), start=1):
        draw.rounded_rectangle((64, y, 686, y + 146), radius=26, fill="#F3ECE3")
        draw.text((96, y + 34), f"{idx:02d}", font=load_font(30), fill="#A08F7A")
        draw.text((170, y + 30), size, font=load_font(34), fill="#1B212C")
        draw.text((540, y + 30), price, font=load_font(34), fill="#1B212C")
        y += 174
    draw.text((70, 1036), "下单更直接，不用再自己估尺寸感受。", font=load_font(24), fill="#6B7280")
    canvas.save(detail_dir / "详情页_切片_04.jpg", quality=95)

    # slice 5
    base = Image.open(bases[2]).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (750, 1200), "#F8F3EC")
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((42, 60, 540, 392), radius=36, fill=(255, 249, 243))
    draw_text_block(draw, 72, 98, "餐桌 茶几 柜面都能铺", "吃饭 待客 拍照时铺上去，桌面会更完整", 42, 22, (26, 33, 44), (98, 106, 116), 7)
    canvas.save(detail_dir / "详情页_切片_05.jpg", quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final marketing assets for the tablecloth product.")
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    parser.add_argument("--sizes", nargs="+", required=True)
    parser.add_argument("--prices", nargs="+", required=True)
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    generated_dir = Path(args.generated_dir)
    pngs = sorted(generated_dir.glob("*.png"), key=lambda path: path.stat().st_mtime)
    if len(pngs) < 14:
        raise RuntimeError("Expected at least 14 generated png files.")

    white_src = pngs[0]
    square_bases = pngs[1:6]
    portrait_bases = pngs[6:11]
    detail_bases = [pngs[3], pngs[5], pngs[10]]
    closeup_src = pngs[13]

    white_dir = product_dir / "白底图"
    square_dir = product_dir / "1比1主图"
    portrait_dir = product_dir / "3比4主图"
    selling_dir = product_dir / "卖点图"

    for directory in [white_dir, square_dir, portrait_dir, selling_dir]:
        clear_dir(directory)

    shutil.copy2(white_src, white_dir / "白底图_正式_01.png")

    square_copy = [
        ("米白蓝灰波点", "一铺桌面就显干净轻松"),
        ("流苏边更出片", "比普通平边更有层次感"),
        ("亚麻感肌理", "近看也有细节，不会显单薄"),
        ("低饱和更百搭", "木色白墙都能轻松搭进去"),
        ("三档尺寸好选", "茶几餐桌都更容易挑合适"),
    ]
    for idx, (src, copy) in enumerate(zip(square_bases, square_copy), start=1):
        compose_square(src, square_dir / f"主图_文案_{idx:02d}.jpg", copy[0], copy[1])

    portrait_copy = [
        ("米白蓝灰波点", "自然光下更耐看，上桌就有轻松家居感"),
        ("桌边一垂更有层次", "流苏花边比普通桌布更显完整"),
        ("日常吃饭也想铺", "不是节日限定，平常用也很顺眼"),
        ("低饱和不挑家", "白墙 木色 原木风都能搭进去"),
        ("小桌长桌都能用", "常用尺寸更好选，下单更直接"),
    ]
    for idx, (src, copy) in enumerate(zip(portrait_bases, portrait_copy), start=1):
        compose_portrait(src, portrait_dir / f"主图_文案_{idx:02d}.jpg", copy[0], copy[1])

    compose_selling(closeup_src, selling_dir / "卖点图_文案_01.jpg")
    compose_detail_slices(product_dir, detail_bases, closeup_src, args.sizes, args.prices)

    print("done")


if __name__ == "__main__":
    main()
