from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
INK = "#4A4038"
INK_SOFT = "#7A6A5C"
CREAM = "#FFF8F0"
BLUE = "#A79889"
WARM = "#E9D8C8"
LINE = "#D8CABB"

FINAL_SCENES = {
    "white": "ig_01e9a8e538311244016a30f06929dc8199a620ad212f0d7857.png",
    "sq_dining": "ig_01e9a8e538311244016a3241bed8fc8199bcfa9409ce80bbaf.png",
    "sq_breakfast": "ig_01e9a8e538311244016a324264e8b88199a0c084d4f332d302.png",
    "sq_console": "ig_01e9a8e538311244016a3244821cf08199ad214ca13217292a.png",
    "sq_close": "ig_01e9a8e538311244016a3245034e2c8199bb2f1c101cddafbd.png",
    "pt_breakfast": "ig_01e9a8e538311244016a32459aad9881998b5a94ae78a2ebc1.png",
    "pt_dining": "ig_01e9a8e538311244016a32462d025881998f92b5eac7e0190e.png",
    "pt_host": "ig_0e4801f5f0ec3b36016a32b2a732488191818b80bc484fc11c.png",
    "pt_tea": "ig_0e4801f5f0ec3b36016a32b313c2e08191b9347df0924359d3.png",
    "pt_console": "ig_0e4801f5f0ec3b36016a32b3691fc08191bd4bded79110b7c6.png",
    "pt_detail": "ig_0e4801f5f0ec3b36016a32b3cc21f08191a4cbc7d6ed3dad21.png",
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    return ImageFont.load_default()


def clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def crop_cover(src: Path, size: tuple[int, int]) -> Image.Image:
    im = Image.open(src).convert("RGB")
    sw, sh = im.size
    tw, th = size
    sr = sw / sh
    tr = tw / th
    if sr > tr:
        nh = th
        nw = int(nh * sr)
    else:
        nw = tw
        nh = int(nw / sr)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max((nw - tw) // 2, 0)
    top = max((nh - th) // 2, 0)
    return im.crop((left, top, left + tw, top + th))


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt, spacing: int = 0) -> tuple[int, int]:
    box = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=spacing)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        buf = ""
        for ch in raw:
            test = buf + ch
            w = draw.textbbox((0, 0), test, font=fnt)[2]
            if buf and w > max_width:
                lines.append(buf)
                buf = ch
            else:
                buf = test
        if buf:
            lines.append(buf)
    return lines


def draw_text_block(draw: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], fnt, fill: str, spacing: int) -> int:
    yy = y
    for line in lines:
        draw.text((x, yy), line, font=fnt, fill=fill)
        h = draw.textbbox((x, yy), line, font=fnt)[3] - draw.textbbox((x, yy), line, font=fnt)[1]
        yy += h + spacing
    return yy


def shadow_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fnt,
    fill: str,
    spacing: int = 0,
    shadow_alpha: int = 190,
) -> None:
    for dx, dy, alpha in ((3, 3, shadow_alpha), (0, 3, shadow_alpha - 20), (3, 0, shadow_alpha - 20)):
        draw.multiline_text((x + dx, y + dy), text, font=fnt, fill=(255, 250, 244, alpha), spacing=spacing)
    draw.multiline_text(
        (x, y),
        text,
        font=fnt,
        fill=fill,
        spacing=spacing,
        stroke_width=2,
        stroke_fill="#FFF9F3",
    )


def scene_copy(
    img: Image.Image,
    rect: tuple[int, int, int, int],
    tag: str,
    title: str,
    sub: str,
    title_fill: str = INK,
    sub_fill: str = INK_SOFT,
    shadow_alpha: int = 190,
    title_size: int = 46,
    sub_size: int = 24,
    tag_size: int = 11,
) -> Image.Image:
    d = ImageDraw.Draw(img)
    x1, y1, x2, y2 = rect
    pad_x = 10
    pad_y = 6
    label_x = x1 + pad_x
    label_y = y1 + pad_y
    d.line((label_x, label_y + 15, label_x + 26, label_y + 15), fill=BLUE, width=2)
    shadow_text(d, label_x + 40, label_y + 3, tag, font(tag_size), BLUE, spacing=0, shadow_alpha=95)
    title_font = font(title_size)
    sub_font = font(sub_size)
    max_width = (x2 - x1) - pad_x * 2
    title_lines = wrap_text(d, title, title_font, max_width)
    sub_lines = wrap_text(d, sub, sub_font, max_width)
    title_y = label_y + 30
    title_text = "\n".join(title_lines)
    sub_text = "\n".join(sub_lines)
    shadow_text(d, label_x, title_y, title_text, title_font, title_fill, spacing=6, shadow_alpha=shadow_alpha)
    title_w, title_h = text_size(d, title_text, title_font, spacing=7)
    sub_y = title_y + title_h + 12
    shadow_text(d, label_x, sub_y, sub_text, sub_font, sub_fill, spacing=5, shadow_alpha=shadow_alpha)
    return img


def main_square(src: Path, out: Path, title: str, sub: str, mode: int, tag_override: str | None = None) -> None:
    img = crop_cover(src, (800, 800)).convert("RGBA")
    if mode == 1:
        img = scene_copy(img, (54, 62, 424, 252), tag_override or "DINING", title, sub, title_size=44, sub_size=24, tag_size=10)
    elif mode == 2:
        img = scene_copy(img, (472, 66, 744, 242), tag_override or "BREAKFAST", title, sub, title_size=38, sub_size=21, tag_size=10)
    elif mode == 3:
        img = scene_copy(img, (78, 86, 360, 274), tag_override or "AT HOME", title, sub, title_size=36, sub_size=20, tag_size=10)
    elif mode == 4:
        img = scene_copy(img, (448, 438, 710, 660), tag_override or "FRINGE", title, sub, title_fill=INK, sub_fill=INK_SOFT, shadow_alpha=215, title_size=34, sub_size=19, tag_size=10)
    else:
        img = scene_copy(img, (64, 64, 336, 224), tag_override or "SIZE", title, sub, title_size=36, sub_size=20, tag_size=10)
    img.convert("RGB").save(out, quality=95)


def main_portrait(src: Path, out: Path, title: str, sub: str, mode: int, tag_override: str | None = None) -> None:
    img = crop_cover(src, (900, 1200)).convert("RGBA")
    if mode == 1:
        img = scene_copy(img, (92, 88, 452, 330), tag_override or "DAILY", title, sub, title_size=56, sub_size=30, tag_size=11)
    elif mode == 2:
        img = scene_copy(img, (82, 122, 462, 388), tag_override or "HOST", title, sub, title_size=58, sub_size=31, tag_size=11)
    elif mode == 3:
        img = scene_copy(img, (500, 84, 844, 300), tag_override or "CABINET", title, sub, title_size=48, sub_size=26, tag_size=11)
    elif mode == 4:
        img = scene_copy(img, (72, 102, 402, 320), tag_override or "TEXTURE", title, sub, title_fill=INK, sub_fill=INK_SOFT, shadow_alpha=215, title_size=48, sub_size=26, tag_size=11)
    else:
        img = scene_copy(img, (474, 818, 842, 1084), tag_override or "SELECT", title, sub, title_size=50, sub_size=27, tag_size=11)
    img.convert("RGB").save(out, quality=95)


def selling(src: Path, out: Path) -> None:
    canvas = Image.new("RGB", (750, 1200), CREAM)
    top = crop_cover(src, (750, 620))
    canvas.paste(top, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((36, 662, 714, 1140), radius=30, fill="#FFFDFC")
    d.rounded_rectangle((60, 700, 216, 744), radius=16, fill=WARM)
    d.text((88, 712), "SELLING POINT", font=font(18), fill=INK)
    d.text((60, 776), "让人愿意下单的细节", font=font(40), fill=INK)
    d.text((62, 834), "不是单看花型，而是铺上去后整个家都更顺眼", font=font(22), fill=INK_SOFT)
    rows = [
        ("米白底配蓝灰点", "比纯白更温和，比深色更轻盈，耐看不压空间。"),
        ("流苏收边", "桌边自然垂落，画面更完整，也更容易拍出氛围。"),
        ("亚麻感纹理", "近看有质感，日常使用不会显得单薄。"),
        ("一布多用", "餐桌 茶几 柜面都能搭，家里的风格更统一。"),
    ]
    y = 910
    for idx, (t, s) in enumerate(rows, start=1):
        d.line((60, y - 18, 690, y - 18), fill=LINE, width=1)
        d.text((60, y), f"0{idx}", font=font(18), fill=BLUE)
        d.text((118, y - 6), t, font=font(28), fill=INK)
        d.text((118, y + 32), s, font=font(19), fill=INK_SOFT)
        y += 84
    canvas.save(out, quality=95)


def detail_page(product: Path, hero: Path, tea: Path, cabinet: Path, closeup: Path, host: Path, sizes: list[str]) -> None:
    detail = product / "详情页"
    clear_dir(detail)

    # 01 hero mood
    canvas = Image.new("RGB", (750, 1200), CREAM)
    top = crop_cover(host, (750, 760))
    canvas.paste(top, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0, 760, 750, 1200), radius=0, fill="#FFFDFC")
    d.rounded_rectangle((44, 808, 206, 854), radius=16, fill=WARM)
    d.text((74, 820), "FIRST LOOK", font=font(18), fill=INK)
    multiline(d, 44, 900, ["铺上之后", "餐厅感立刻出来"], 50, INK, 4)
    d.line((44, 1020, 706, 1020), fill=LINE, width=1)
    draw_text_block(d, 44, 1052, wrap_text(d, "米白底更柔和，蓝灰波点让桌面有细节，但不过分张扬。", font(23), 634), font(23), INK_SOFT, 8)
    canvas.save(detail / "详情页_切片_01.jpg", quality=95)

    # 02 color and pattern
    canvas = Image.new("RGB", (750, 1200), CREAM)
    top = crop_cover(tea, (750, 640))
    canvas.paste(top, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0, 640, 750, 1200), radius=0, fill="#F9F3EC")
    d.rounded_rectangle((44, 690, 188, 734), radius=16, fill="#E8DCCF")
    d.text((72, 702), "COLOR", font=font(18), fill=INK)
    multiline(d, 44, 776, ["米白底配", "蓝灰波点"], 48, INK, 4)
    draw_text_block(d, 44, 900, wrap_text(d, "看起来更轻，日常耐看，也更适合木色和奶油色空间。", font(22), 300), font(22), INK_SOFT, 8)
    d.line((396, 700, 396, 1090), fill=LINE, width=1)
    d.text((430, 724), "真实波点大小", font=font(22), fill=INK)
    d.text((430, 774), "约 1cm", font=font(46), fill=INK)
    d.text((430, 842), "不是细碎印花感", font=font(20), fill=INK_SOFT)
    d.text((430, 876), "而是更自然松弛的布面节奏", font=font(20), fill=INK_SOFT)
    canvas.save(detail / "详情页_切片_02.jpg", quality=95)

    # 03 detail texture
    canvas = Image.new("RGB", (750, 1200), CREAM)
    top = crop_cover(closeup, (750, 720))
    canvas.paste(top, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0, 720, 750, 1200), radius=0, fill="#FFFDFC")
    d.rounded_rectangle((44, 764, 174, 808), radius=16, fill=WARM)
    d.text((72, 776), "DETAIL", font=font(18), fill=INK)
    multiline(d, 44, 850, ["流苏边和", "亚麻感纹理"], 48, INK, 4)
    d.line((44, 972, 706, 972), fill=LINE, width=1)
    draw_text_block(d, 44, 1004, wrap_text(d, "桌边自然垂落会让层次更完整，近看也能看到布面的肌理和分量感。", font(23), 634), font(23), INK_SOFT, 8)
    canvas.save(detail / "详情页_切片_03.jpg", quality=95)

    # 04 multi-scene
    canvas = Image.new("RGB", (750, 1200), CREAM)
    left = crop_cover(tea, (356, 540))
    right = crop_cover(cabinet, (356, 540))
    canvas.paste(left, (20, 100))
    canvas.paste(right, (374, 100))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((44, 688, 200, 732), radius=16, fill=WARM)
    d.text((72, 700), "SCENE", font=font(18), fill=INK)
    multiline(d, 44, 774, ["餐桌 柜面", "都能自然适配"], 46, INK, 4)
    d.line((44, 892, 706, 892), fill=LINE, width=1)
    d.text((44, 930), "早餐桌", font=font(22), fill=INK)
    d.text((260, 930), "更完整轻松", font=font(20), fill=INK_SOFT)
    d.text((44, 990), "柜面盖布", font=font(22), fill=INK)
    d.text((260, 990), "让家的材质和颜色更统一", font=font(20), fill=INK_SOFT)
    d.text((44, 1050), "日常搭配", font=font(22), fill=INK)
    d.text((260, 1050), "不突兀，也不会显得太满", font=font(20), fill=INK_SOFT)
    canvas.save(detail / "详情页_切片_04.jpg", quality=95)

    # 05 size guide
    canvas = Image.new("RGB", (750, 1200), CREAM)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((44, 58, 214, 104), radius=18, fill=WARM)
    d.text((72, 70), "SIZE GUIDE", font=font(20), fill=INK)
    d.text((44, 152), "常用尺寸这样选", font=font(46), fill=INK)
    d.text((44, 214), "按桌面大小挑选，铺出来更利落，也更有呼吸感。", font=font(22), fill=INK_SOFT)
    d.line((44, 274, 706, 274), fill=LINE, width=1)
    y = 330
    captions = ["小桌", "常用餐桌", "长桌"]
    notes = ["桌面更轻巧", "比例最稳妥", "铺感更舒展"]
    for idx, (size, cap, note) in enumerate(zip(sizes, captions, notes), start=1):
        d.rounded_rectangle((44, y, 706, y + 176), radius=24, fill="#FFFDFC")
        d.text((74, y + 36), f"0{idx}", font=font(18), fill=BLUE)
        d.text((150, y + 28), size, font=font(34), fill=INK)
        d.text((150, y + 86), cap, font=font(22), fill=INK_SOFT)
        d.text((492, y + 58), note, font=font(20), fill=INK)
        y += 204
    canvas.save(detail / "详情页_切片_05.jpg", quality=95)


def multiline(draw: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], size: int, fill: str, spacing: int = 10):
    f = font(size)
    yy = y
    for line in lines:
        draw.text((x, yy), line, font=f, fill=fill)
        yy += size + spacing
    return yy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    parser.add_argument("--sizes", nargs="+", required=True)
    args = parser.parse_args()

    product = Path(args.product_dir)
    gen = Path(args.generated_dir)
    scenes = {}
    for key, filename in FINAL_SCENES.items():
        path = gen / filename
        if not path.exists():
            raise RuntimeError(f"Missing final scene: {filename}")
        scenes[key] = path

    white_dir = product / "白底图"
    square_dir = product / "1比1主图"
    portrait_dir = product / "3比4主图"
    selling_dir = product / "卖点图"
    for d in [white_dir, square_dir, portrait_dir, selling_dir]:
        clear_dir(d)
    shutil.copy2(scenes["white"], white_dir / "白底图_正式_01.png")

    main_square(scenes["sq_dining"], square_dir / "主图_文案_01.jpg", "铺出更干净的餐厅感", "米白底衬蓝灰波点，日常耐看，也更显轻盈", 1, "DINING")
    main_square(scenes["pt_host"], square_dir / "主图_文案_02.jpg", "待客上桌也更有氛围", "桌面完整了，家的仪式感也会自然跟上", 2, "HOST")
    main_square(scenes["sq_console"], square_dir / "主图_文案_03.jpg", "餐桌柜面都能自然搭配", "换个位置继续好看，家的风格更容易统一", 3, "AT HOME")
    main_square(scenes["pt_detail"], square_dir / "主图_文案_04.jpg", "流苏收边让层次更丰富", "垂落感自然，近看纹理与细节都更成立", 4, "FRINGE")
    main_square(scenes["pt_tea"], square_dir / "主图_文案_05.jpg", "尺寸选对铺感更利落", "从小桌到长桌，都能铺出舒展比例", 5, "SIZE")

    main_portrait(scenes["pt_breakfast"], portrait_dir / "主图_文案_01.jpg", "日常用餐也能很精致", "不刻意造作，铺上之后桌面自然更顺眼", 1, "DAILY")
    main_portrait(scenes["pt_host"], portrait_dir / "主图_文案_02.jpg", "待客上桌更显体面", "桌面完整了，氛围和仪式感都会自然提升", 2, "HOST")
    main_portrait(scenes["pt_console"], portrait_dir / "主图_文案_03.jpg", "不只是一块桌布", "放到柜面也能成立，实用和装饰感一起兼顾", 3, "CABINET")
    main_portrait(scenes["pt_detail"], portrait_dir / "主图_文案_04.jpg", "近看更能看出质感", "亚麻感纹理和流苏边，把细节撑得更完整", 4, "TEXTURE")
    main_portrait(scenes["pt_dining"], portrait_dir / "主图_文案_05.jpg", "常用尺寸更好挑选", "铺开比例顺了，整张桌面自然更显高级", 5, "SIZE")

    selling(scenes["pt_detail"], selling_dir / "卖点图_文案_01.jpg")
    detail_page(product, scenes["pt_host"], scenes["pt_tea"], scenes["pt_console"], scenes["pt_detail"], scenes["pt_host"], args.sizes)
    print("done")


if __name__ == "__main__":
    main()
