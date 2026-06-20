from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
INK = "#223043"
SUB = "#617083"
CREAM = "#FCF7F0"
WARM = "#E8D7C4"
BLUE = "#6D86A2"
SAND = "#EDE5DB"


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


def multiline(draw: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], size: int, fill: str, spacing: int = 10):
    f = font(size)
    yy = y
    for line in lines:
        draw.text((x, yy), line, font=f, fill=fill)
        yy += size + spacing
    return yy


def square_layout(src: Path, out: Path, title: list[str], sub: str, mode: int) -> None:
    canvas = Image.new("RGB", (800, 800), CREAM)
    draw = ImageDraw.Draw(canvas)

    if mode == 1:
        img = crop_cover(src, (800, 520))
        canvas.paste(img, (0, 0))
        draw.rectangle((0, 520, 800, 800), fill=CREAM)
        draw.rectangle((48, 564, 160, 574), fill=BLUE)
        y = multiline(draw, 48, 600, title, 56, INK, 0)
        multiline(draw, 50, y + 20, [sub], 24, SUB, 0)
    elif mode == 2:
        img = crop_cover(src, (520, 800))
        canvas.paste(img, (280, 0))
        draw.rectangle((0, 0, 280, 800), fill=SAND)
        draw.rounded_rectangle((40, 56, 202, 102), radius=18, fill=WARM)
        draw.text((62, 66), "SMALL TABLE", font=font(18), fill=INK)
        y = multiline(draw, 40, 146, title, 54, INK, 0)
        multiline(draw, 40, y + 18, [sub], 24, SUB, 0)
    elif mode == 3:
        img = crop_cover(src, (800, 560))
        canvas.paste(img, (0, 240))
        draw.rounded_rectangle((36, 36, 764, 210), radius=30, fill="#FFFDFC")
        draw.rounded_rectangle((36, 36, 126, 210), radius=30, fill=BLUE)
        draw.text((52, 80), "USE", font=font(20), fill="white")
        draw.text((52, 112), "AT", font=font(20), fill="white")
        draw.text((52, 144), "HOME", font=font(20), fill="white")
        y = multiline(draw, 152, 68, title, 48, INK, 0)
        multiline(draw, 152, y + 10, [sub], 22, SUB, 0)
    elif mode == 4:
        img = crop_cover(src, (800, 800))
        canvas.paste(img, (0, 0))
        draw.rounded_rectangle((38, 38, 318, 170), radius=28, fill=(252, 247, 240))
        y = multiline(draw, 64, 64, title, 42, INK, 0)
        multiline(draw, 64, y + 8, [sub], 20, SUB, 0)
        draw.rounded_rectangle((504, 42, 742, 90), radius=18, fill=WARM)
        draw.text((532, 54), "FRINGE DETAIL", font=font(18), fill=INK)
    else:
        img = crop_cover(src, (800, 620))
        canvas.paste(img, (0, 0))
        draw.rectangle((0, 620, 800, 800), fill="#FFFDFC")
        draw.text((48, 656), title[0], font=font(52), fill=INK)
        draw.text((48, 718), title[1], font=font(52), fill=INK)
        draw.text((50, 774), sub, font=font(22), fill=SUB)

    canvas.save(out, quality=95)


def portrait_layout(src: Path, out: Path, title: list[str], sub: str, mode: int) -> None:
    canvas = Image.new("RGB", (900, 1200), CREAM)
    draw = ImageDraw.Draw(canvas)

    if mode == 1:
        img = crop_cover(src, (900, 760))
        canvas.paste(img, (0, 0))
        draw.rectangle((0, 760, 900, 1200), fill="#FFFDFC")
        draw.text((60, 818), title[0], font=font(62), fill=INK)
        draw.text((60, 888), title[1], font=font(62), fill=INK)
        draw.text((64, 980), sub, font=font(28), fill=SUB)
    elif mode == 2:
        img = crop_cover(src, (620, 1200))
        canvas.paste(img, (280, 0))
        draw.rectangle((0, 0, 280, 1200), fill=SAND)
        draw.rectangle((42, 78, 54, 230), fill=BLUE)
        y = multiline(draw, 72, 86, title, 54, INK, 0)
        multiline(draw, 72, y + 18, [sub], 24, SUB, 0)
    elif mode == 3:
        img = crop_cover(src, (900, 900))
        canvas.paste(img, (0, 300))
        draw.rounded_rectangle((52, 54, 848, 250), radius=30, fill="#FFFDFC")
        y = multiline(draw, 82, 86, title, 56, INK, 0)
        multiline(draw, 82, y + 14, [sub], 24, SUB, 0)
    elif mode == 4:
        img = crop_cover(src, (900, 1200))
        canvas.paste(img, (0, 0))
        draw.rounded_rectangle((520, 54, 840, 224), radius=28, fill="#FFFDFC")
        y = multiline(draw, 548, 82, title, 40, INK, 0)
        multiline(draw, 548, y + 8, [sub], 20, SUB, 0)
    else:
        img = crop_cover(src, (900, 780))
        canvas.paste(img, (0, 0))
        draw.rectangle((0, 780, 900, 1200), fill="#FFFDFC")
        draw.rounded_rectangle((60, 824, 260, 876), radius=18, fill=WARM)
        draw.text((86, 840), "SIZE GUIDE", font=font(22), fill=INK)
        y = multiline(draw, 60, 914, title, 58, INK, 0)
        multiline(draw, 64, y + 14, [sub], 24, SUB, 0)

    canvas.save(out, quality=95)


def selling_layout(src: Path, out: Path) -> None:
    canvas = Image.new("RGB", (750, 1200), "#F8F3EC")
    draw = ImageDraw.Draw(canvas)
    img = crop_cover(src, (750, 600))
    canvas.paste(img, (0, 0))
    draw.rounded_rectangle((34, 644, 716, 1148), radius=34, fill="#FFFDFC")
    draw.text((64, 694), "为什么这块更容易让人下单", font=font(38), fill=INK)
    draw.text((66, 748), "先把上桌后的感觉讲清楚", font=font(22), fill=SUB)
    items = [
        ("01", "米白蓝灰点", "桌面更显干净，不会压空间"),
        ("02", "流苏边", "桌边一垂下来，层次更完整"),
        ("03", "亚麻感", "近看能看到纹理，不显单薄"),
        ("04", "更好卖", "餐桌 茶几 柜面都能铺"),
    ]
    y = 818
    for no, t, s in items:
        draw.text((70, y), no, font=font(22), fill=BLUE)
        draw.text((132, y - 6), t, font=font(30), fill=INK)
        draw.text((132, y + 36), s, font=font(22), fill=SUB)
        y += 90
    canvas.save(out, quality=95)


def detail_layout(product: Path, hero: Path, breakfast: Path, cabinet: Path, closeup: Path, host: Path, sizes: list[str]) -> None:
    detail = product / "详情页"
    clear_dir(detail)

    scenes = [
        (hero, ["一铺桌面", "就显干净轻松"], "米白蓝灰点更耐看，不压空间"),
        (breakfast, ["早餐 茶点", "铺上去更顺眼"], "小方桌也能铺得刚刚好"),
        (cabinet, ["不只餐桌能用"], "柜面盖布也能把家里统一起来"),
        (closeup, ["流苏边和纹理", "近看也经得住看"], "远看有氛围，近看也有细节"),
    ]
    for idx, (src, title, sub) in enumerate(scenes, start=1):
        canvas = Image.new("RGB", (750, 1200), "#FFFDFC")
        img = crop_cover(src, (750, 760))
        canvas.paste(img, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 760, 750, 1200), fill="#FFFDFC")
        draw.rectangle((46, 818, 150, 828), fill=BLUE)
        y = multiline(draw, 46, 854, title, 46, INK, 0)
        multiline(draw, 50, y + 16, [sub], 24, SUB, 0)
        canvas.save(detail / f"详情页_切片_0{idx}.jpg", quality=95)

    canvas = Image.new("RGB", (750, 1200), "#FFFDFC")
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 70), "常用尺寸这样选", font=font(44), fill=INK)
    draw.text((50, 130), "不放价格，只把规格感受讲清楚", font=font(22), fill=SUB)
    y = 250
    captions = ["小桌", "常用餐桌", "长桌"]
    for idx, (size, cap) in enumerate(zip(sizes, captions), start=1):
        draw.rounded_rectangle((48, y, 702, y + 164), radius=24, fill=SAND)
        draw.text((78, y + 24), f"0{idx}", font=font(24), fill=BLUE)
        draw.text((158, y + 20), size, font=font(36), fill=INK)
        draw.text((160, y + 84), cap, font=font(22), fill=SUB)
        y += 192
    canvas.save(detail / "详情页_切片_05.jpg", quality=95)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    parser.add_argument("--sizes", nargs="+", required=True)
    args = parser.parse_args()

    product = Path(args.product_dir)
    gen = Path(args.generated_dir)
    pngs = sorted(gen.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if len(pngs) < 31:
        raise RuntimeError("Need generated images including the latest 6 scale-correct scenes.")

    white = pngs[0]
    hero = pngs[25]
    breakfast = pngs[26]
    cabinet = pngs[27]
    closeup = pngs[28]
    breakfast_v = pngs[29]
    host_v = pngs[30]

    white_dir = product / "白底图"
    square_dir = product / "1比1主图"
    portrait_dir = product / "3比4主图"
    selling_dir = product / "卖点图"

    for d in [white_dir, square_dir, portrait_dir, selling_dir]:
        clear_dir(d)
    shutil.copy2(white, white_dir / "白底图_正式_01.png")

    square_layout(hero, square_dir / "主图_文案_01.jpg", ["一铺桌面", "就显干净轻松"], "米白蓝灰点更耐看，不压空间", 1)
    square_layout(breakfast, square_dir / "主图_文案_02.jpg", ["小桌也能铺得", "刚刚好"], "早餐茶点用起来更顺手", 2)
    square_layout(cabinet, square_dir / "主图_文案_03.jpg", ["不只餐桌能用"], "柜面盖布也能把家里统一起来", 3)
    square_layout(closeup, square_dir / "主图_文案_04.jpg", ["流苏边", "更出片"], "桌边一垂下来，层次就出来了", 4)
    square_layout(hero, square_dir / "主图_文案_05.jpg", ["常用尺寸", "更好选"], "茶几 小桌 长桌都能找到合适", 5)

    portrait_layout(breakfast_v, portrait_dir / "主图_文案_01.jpg", ["日常吃饭", "也想铺"], "平常用不突兀，看着更顺眼", 1)
    portrait_layout(host_v, portrait_dir / "主图_文案_02.jpg", ["待客上桌", "更体面"], "桌面完整了，氛围自然就更好", 2)
    portrait_layout(cabinet, portrait_dir / "主图_文案_03.jpg", ["柜面也能铺"], "不只是一块桌布，也是家里装饰", 3)
    portrait_layout(closeup, portrait_dir / "主图_文案_04.jpg", ["近看也有", "亚麻感"], "看得到纹理，不是远看好看而已", 4)
    portrait_layout(breakfast_v, portrait_dir / "主图_文案_05.jpg", ["小桌长桌", "都能用"], "常用尺寸直接选，下单更省心", 5)

    selling_layout(closeup, selling_dir / "卖点图_文案_01.jpg")
    detail_layout(product, hero, breakfast, cabinet, closeup, host_v, args.sizes)
    print("done")


if __name__ == "__main__":
    main()
