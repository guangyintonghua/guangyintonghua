from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    return ImageFont.load_default()


def clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def fit_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], max_size: int, min_size: int, fill, line_spacing: int = 6):
    x1, y1, x2, y2 = box
    for size in range(max_size, min_size - 1, -2):
        f = font(size)
        bbox = draw.multiline_textbbox((0, 0), text, font=f, spacing=line_spacing)
        if bbox[2] - bbox[0] <= (x2 - x1) and bbox[3] - bbox[1] <= (y2 - y1):
            return f
    return font(min_size)


def draw_block(img: Image.Image, rect, title, sub, align="left"):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle(rect, radius=30, fill=(255, 250, 244, 220))
    x1, y1, x2, y2 = rect
    title_box = (x1 + 24, y1 + 22, x2 - 24, y1 + 126)
    title_font = fit_text(d, title, title_box, 56, 26, (28, 34, 44, 255))
    d.multiline_text((title_box[0], title_box[1]), title, font=title_font, fill=(28, 34, 44, 255), spacing=2)
    sub_box = (x1 + 24, y1 + 126, x2 - 24, y2 - 24)
    sub_font = fit_text(d, sub, sub_box, 28, 18, (95, 104, 115, 255))
    d.multiline_text((sub_box[0], sub_box[1]), sub, font=sub_font, fill=(95, 104, 115, 255), spacing=4)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def square_layout(src: Path, out: Path, title: str, sub: str, variant: int) -> None:
    img = Image.open(src).convert("RGB").resize((800, 800), Image.Resampling.LANCZOS)
    if variant == 1:
        result = draw_block(img, (44, 46, 460, 244), title, sub)
    elif variant == 2:
        result = draw_block(img, (38, 560, 438, 760), title, sub)
    elif variant == 3:
        result = draw_block(img, (386, 46, 760, 240), title, sub)
    elif variant == 4:
        result = draw_block(img, (44, 74, 380, 286), title, sub)
    else:
        result = draw_block(img, (352, 560, 760, 760), title, sub)
    result.save(out, quality=95)


def portrait_layout(src: Path, out: Path, title: str, sub: str, variant: int) -> None:
    img = Image.open(src).convert("RGB").resize((900, 1200), Image.Resampling.LANCZOS)
    if variant == 1:
        result = draw_block(img, (54, 54, 660, 260), title, sub)
    elif variant == 2:
        result = draw_block(img, (52, 880, 640, 1130), title, sub)
    elif variant == 3:
        result = draw_block(img, (54, 68, 560, 312), title, sub)
    elif variant == 4:
        result = draw_block(img, (320, 58, 844, 292), title, sub)
    else:
        result = draw_block(img, (54, 52, 700, 272), title, sub)
    result.save(out, quality=95)


def selling_page(src: Path, out: Path) -> None:
    canvas = Image.new("RGB", (750, 1200), "#F7F2EB")
    d = ImageDraw.Draw(canvas)
    d.text((44, 46), "这款桌布为什么更容易让人下单", font=font(40), fill="#1C222C")
    d.text((46, 100), "看得见的4个购买理由", font=font(22), fill="#6A7380")
    hero = Image.open(src).convert("RGB").resize((662, 410), Image.Resampling.LANCZOS)
    canvas.paste(hero, (44, 150))
    items = [
        ("配色轻松", "米白底配蓝灰点，看起来更干净。"),
        ("花边加分", "桌边一垂下来，画面就不单调。"),
        ("纹理可见", "近看能看到亚麻感，不显薄。"),
        ("尺寸好选", "常用规格直接选，下单更省心。"),
    ]
    positions = [(44, 608), (390, 608), (44, 842), (390, 842)]
    for (t, s), (x, y) in zip(items, positions):
        d.rounded_rectangle((x, y, x + 316, y + 196), radius=24, fill="#FFFDF9")
        d.text((x + 22, y + 20), t, font=font(30), fill="#1C222C")
        sf = fit_text(d, s, (x + 22, y + 72, x + 292, y + 164), 22, 16, "#6A7380")
        d.multiline_text((x + 22, y + 76), s, font=sf, fill="#6A7380", spacing=4)
    canvas.save(out, quality=95)


def detail_slices(product_dir: Path, hero: Path, closeup: Path, host: Path, sizes: list[str], prices: list[str]) -> None:
    detail = product_dir / "详情页"
    clear_dir(detail)

    def save(img: Image.Image, name: str):
        img.save(detail / name, quality=95)

    img1 = Image.open(hero).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    save(draw_block(img1, (42, 56, 520, 270), "一铺上桌面\n就显干净轻松", "米白蓝灰波点，日常看着更舒服"), "详情页_切片_01.jpg")

    img2 = Image.open(closeup).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    save(draw_block(img2, (40, 54, 500, 252), "花边不是装饰而已", "桌边多一层细节，成图和实拍都更出片"), "详情页_切片_02.jpg")

    img3 = Image.open(closeup).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    save(draw_block(img3, (40, 904, 520, 1136), "近看也有肌理感", "亚麻感纹理看得见，不是远看好看而已"), "详情页_切片_03.jpg")

    canvas = Image.new("RGB", (750, 1200), "#F8F3EC")
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((28, 34, 722, 1166), radius=28, fill="#FFFDF9")
    d.text((64, 80), "常用尺寸直接选", font=font(44), fill="#1C222C")
    d.text((66, 138), "茶几 小桌 长桌都更容易找到合适规格", font=font(22), fill="#6A7380")
    y = 248
    for i, (s, p) in enumerate(zip(sizes, prices), start=1):
        d.rounded_rectangle((60, y, 690, y + 138), radius=24, fill="#F2EADF")
        d.text((86, y + 22), f"{i:02d}", font=font(28), fill="#A8947F")
        d.text((164, y + 20), s, font=font(34), fill="#1C222C")
        d.text((546, y + 20), p, font=font(34), fill="#1C222C")
        y += 164
    d.text((66, 1034), "不用反复估尺寸，选好就能下单。", font=font(24), fill="#6A7380")
    save(canvas, "详情页_切片_04.jpg")

    img5 = Image.open(host).convert("RGB").resize((750, 1200), Image.Resampling.LANCZOS)
    save(draw_block(img5, (42, 62, 560, 286), "吃饭 待客 拍照\n都能顺手铺", "不是节日限定，平常用也能把桌面氛围补齐"), "详情页_切片_05.jpg")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    parser.add_argument("--sizes", nargs="+", required=True)
    parser.add_argument("--prices", nargs="+", required=True)
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    gen = Path(args.generated_dir)
    pngs = sorted(gen.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if len(pngs) < 19:
        raise RuntimeError("Need at least 19 generated images.")

    white = pngs[0]
    sq = [pngs[14], pngs[15], pngs[16], pngs[4], pngs[5]]
    pt = [pngs[17], pngs[18], pngs[10], pngs[11], pngs[12]]
    closeup = pngs[15]
    host = pngs[18]

    white_dir = product_dir / "白底图"
    square_dir = product_dir / "1比1主图"
    portrait_dir = product_dir / "3比4主图"
    selling_dir = product_dir / "卖点图"
    for d in [white_dir, square_dir, portrait_dir, selling_dir]:
        clear_dir(d)

    shutil.copy2(white, white_dir / "白底图_正式_01.png")

    square_copy = [
        ("一铺桌面\n就显干净轻松", "米白蓝灰点更耐看，不压空间"),
        ("桌边一垂\n层次就出来了", "流苏花边比普通平边更出片"),
        ("近看也有\n亚麻感肌理", "不是只有远看好看，近看也有细节"),
        ("日常用也顺眼", "早餐 吃饭 待客时铺上去都自然"),
        ("常用尺寸\n更好选", "茶几 小桌 长桌都能找到合适"),
    ]
    for i, (src, cp) in enumerate(zip(sq, square_copy), start=1):
        square_layout(src, square_dir / f"主图_文案_{i:02d}.jpg", cp[0], cp[1], i)

    portrait_copy = [
        ("家里一下\n更有完整感", "不是只盖桌面，是把餐桌氛围一起补齐"),
        ("待客上桌\n更体面", "低饱和配色耐看，不挑家里风格"),
        ("桌边细节\n更能加分", "流苏花边一露出来，画面就不单调"),
        ("拍照布景\n也合适", "木色 白墙 原木风都能搭进去"),
        ("小桌长桌\n都能用", "常用尺寸直接选，下单更省心"),
    ]
    for i, (src, cp) in enumerate(zip(pt, portrait_copy), start=1):
        portrait_layout(src, portrait_dir / f"主图_文案_{i:02d}.jpg", cp[0], cp[1], i)

    selling_page(closeup, selling_dir / "卖点图_文案_01.jpg")
    detail_slices(product_dir, sq[0], closeup, host, args.sizes, args.prices)
    print("done")


if __name__ == "__main__":
    main()
