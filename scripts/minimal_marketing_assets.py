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


def draw_shadow_text(draw: ImageDraw.ImageDraw, pos, text: str, fnt, fill, shadow=(255, 255, 255), offset=(2, 2), spacing=4):
    x, y = pos
    draw.multiline_text((x + offset[0], y + offset[1]), text, font=fnt, fill=shadow, spacing=spacing)
    draw.multiline_text((x, y), text, font=fnt, fill=fill, spacing=spacing)


def square_image(src: Path, out: Path, title: str, sub: str, placement: str) -> None:
    img = crop_cover(src, (800, 800))
    draw = ImageDraw.Draw(img)
    title_font = font(60)
    sub_font = font(28)
    if placement == "tl":
        draw_shadow_text(draw, (58, 54), title, title_font, "#23303f")
        draw_shadow_text(draw, (62, 174), sub, sub_font, "#556270")
    elif placement == "tr":
        draw_shadow_text(draw, (418, 54), title, title_font, "#23303f")
        draw_shadow_text(draw, (422, 174), sub, sub_font, "#556270")
    elif placement == "bl":
        draw_shadow_text(draw, (56, 618), title, title_font, "#23303f")
        draw_shadow_text(draw, (60, 738), sub, sub_font, "#556270")
    elif placement == "br":
        draw_shadow_text(draw, (386, 618), title, title_font, "#23303f")
        draw_shadow_text(draw, (390, 738), sub, sub_font, "#556270")
    else:
        band = Image.new("RGBA", (800, 118), (255, 250, 244, 168))
        base = img.convert("RGBA")
        base.alpha_composite(band, (0, 682))
        img = base.convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text((40, 704), title, font=font(46), fill="#23303f")
        draw.text((40, 756), sub, font=font(24), fill="#556270")
    img.save(out, quality=95)


def portrait_image(src: Path, out: Path, title: str, sub: str, placement: str) -> None:
    img = crop_cover(src, (900, 1200))
    draw = ImageDraw.Draw(img)
    title_font = font(64)
    sub_font = font(30)
    if placement == "top":
        draw_shadow_text(draw, (68, 60), title, title_font, "#23303f")
        draw_shadow_text(draw, (74, 190), sub, sub_font, "#556270")
    elif placement == "bottom":
        band = Image.new("RGBA", (900, 180), (255, 250, 244, 176))
        base = img.convert("RGBA")
        base.alpha_composite(band, (0, 1020))
        img = base.convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text((52, 1048), title, font=font(52), fill="#23303f")
        draw.text((56, 1112), sub, font=font(26), fill="#556270")
    else:
        draw_shadow_text(draw, (472, 66), title, font(54), "#23303f")
        draw_shadow_text(draw, (476, 176), sub, font(26), "#556270")
    img.save(out, quality=95)


def selling(src: Path, out: Path) -> None:
    hero = crop_cover(src, (750, 680))
    canvas = Image.new("RGB", (750, 1200), "#F7F2EB")
    canvas.paste(hero, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 680, 750, 1200), fill="#FFFDF9")
    d.text((42, 724), "为什么这块更容易让人下单", font=font(38), fill="#23303f")
    d.text((44, 776), "看的是上桌后的体验感，不只是花型", font=font(22), fill="#556270")
    points = [
        "米白蓝灰点，桌面更显干净",
        "流苏边一垂下来，层次更完整",
        "近看能看到亚麻感，不显单薄",
        "餐桌 茶几 柜面都能铺，更好卖",
    ]
    y = 850
    for p in points:
        d.text((56, y), f"• {p}", font=font(28), fill="#23303f")
        y += 72
    canvas.save(out, quality=95)


def detail_page(product_dir: Path, hero: Path, cabinet: Path, closeup: Path, host: Path, sizes: list[str]) -> None:
    detail = product_dir / "详情页"
    clear_dir(detail)

    imgs = [
        crop_cover(hero, (750, 760)),
        crop_cover(cabinet, (750, 760)),
        crop_cover(closeup, (750, 760)),
        crop_cover(host, (750, 760)),
    ]
    texts = [
        ("一铺上桌面\n就显干净轻松", "米白蓝灰点更耐看，不压空间"),
        ("不只餐桌能用", "柜面盖布也顺眼，家里更容易统一"),
        ("流苏边和纹理\n近看也经得住看", "远看有氛围，近看也有细节"),
        ("日常吃饭 待客\n顺手一铺就够体面", "不是节日限定，平常用也不突兀"),
    ]
    for i, (im, tx) in enumerate(zip(imgs, texts), start=1):
        canvas = Image.new("RGB", (750, 1200), "#FFFCF8")
        canvas.paste(im, (0, 0))
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 760, 750, 1200), fill="#FFFDF9")
        d.text((42, 816), tx[0], font=font(46), fill="#23303f")
        d.text((46, 946), tx[1], font=font(24), fill="#556270")
        canvas.save(detail / f"详情页_切片_0{i}.jpg", quality=95)

    size_canvas = Image.new("RGB", (750, 1200), "#FFFDF9")
    d = ImageDraw.Draw(size_canvas)
    d.text((42, 68), "常用尺寸这样选", font=font(46), fill="#23303f")
    d.text((44, 132), "不展示价格，只把规格讲清楚", font=font(22), fill="#556270")
    y = 250
    for idx, size in enumerate(sizes, start=1):
        d.rounded_rectangle((52, y, 698, y + 150), radius=24, fill="#F3ECE3")
        d.text((86, y + 34), f"{idx:02d}", font=font(28), fill="#A58E77")
        d.text((176, y + 30), size, font=font(36), fill="#23303f")
        y += 182
    d.text((44, 1044), "茶几 小桌 长桌都能更快找到合适尺寸。", font=font(24), fill="#556270")
    size_canvas.save(detail / "详情页_切片_05.jpg", quality=95)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--generated-dir", required=True)
    parser.add_argument("--sizes", nargs="+", required=True)
    args = parser.parse_args()

    product = Path(args.product_dir)
    gen = Path(args.generated_dir)
    pngs = sorted(gen.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if len(pngs) < 25:
        raise RuntimeError("Need generated images including the latest 6 diverse scenes.")

    white = pngs[0]
    hero = pngs[19]
    breakfast_small = pngs[20]
    cabinet = pngs[21]
    closeup = pngs[22]
    breakfast_portrait = pngs[23]
    host = pngs[24]

    white_dir = product / "白底图"
    square_dir = product / "1比1主图"
    portrait_dir = product / "3比4主图"
    selling_dir = product / "卖点图"
    for d in [white_dir, square_dir, portrait_dir, selling_dir]:
        clear_dir(d)
    shutil.copy2(white, white_dir / "白底图_正式_01.png")

    square_image(hero, square_dir / "主图_文案_01.jpg", "一铺桌面\n就显干净轻松", "米白蓝灰点更耐看，不压空间", "tl")
    square_image(breakfast_small, square_dir / "主图_文案_02.jpg", "小桌也能铺得\n刚刚好", "早餐茶点用起来更顺手", "tr")
    square_image(cabinet, square_dir / "主图_文案_03.jpg", "不只餐桌能用", "柜面盖布也能把家里统一起来", "bl")
    square_image(closeup, square_dir / "主图_文案_04.jpg", "流苏边\n更出片", "桌边一垂下来，层次就出来了", "br")
    square_image(hero, square_dir / "主图_文案_05.jpg", "常用尺寸\n更好选", "茶几 小桌 长桌都能找到合适", "band")

    portrait_image(breakfast_portrait, portrait_dir / "主图_文案_01.jpg", "日常吃饭\n也想铺", "平常用不突兀，看着更顺眼", "top")
    portrait_image(host, portrait_dir / "主图_文案_02.jpg", "待客上桌\n更体面", "不需要复杂布置，桌面先完整起来", "bottom")
    portrait_image(cabinet, portrait_dir / "主图_文案_03.jpg", "柜面也能铺", "不只是一块桌布，也是家里装饰", "top")
    portrait_image(closeup, portrait_dir / "主图_文案_04.jpg", "近看也有\n亚麻感", "看得到纹理，不是远看好看而已", "right")
    portrait_image(breakfast_portrait, portrait_dir / "主图_文案_05.jpg", "小桌长桌\n都能用", "常用尺寸直接选，下单更省心", "bottom")

    selling(closeup, selling_dir / "卖点图_文案_01.jpg")
    detail_page(product, hero, cabinet, closeup, host, args.sizes)
    print("done")


if __name__ == "__main__":
    main()
