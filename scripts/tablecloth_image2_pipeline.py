from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import load_workbook
from PIL import Image, ImageColor, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / "桌布自动生图工作流"
PRODUCT_ROOT = WORKFLOW_ROOT / "产品素材"
OUTPUT_ROOT = WORKFLOW_ROOT / "输出"
CACHE_ROOT = OUTPUT_ROOT / "image2缓存"
GENERATED_IMAGE_ROOT = Path.home() / ".codex" / "generated_images"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")


PRODUCT_COPY = {
    "1号品": {
        "title": "北欧米白深灰蓝波点流苏桌布",
        "guide_title": "米白蓝灰波点流苏桌布",
        "title_direction": "北欧低饱和波点桌布",
        "visual_traits": "米白底、低饱和深蓝灰波点、流苏边、轻亚麻感",
        "style_tags": ["北欧简约", "低饱和", "波点", "流苏边", "轻亚麻感"],
        "hero_title": "米白蓝灰点",
        "hero_subtitle": "颜色柔和，家用更耐看",
        "pattern_label": "低饱和波点",
        "scene_hint": "适合日常餐桌、茶几、民宿陈设",
    },
    "2号品": {
        "title": "复古深底碎花流苏棉布桌布",
        "guide_title": "深底黄白碎花流苏桌布",
        "title_direction": "复古田园小碎花棉布桌布",
        "visual_traits": "深咖啡底、黄白小碎花、米白流苏花边、薄棉布、自然垂感",
        "style_tags": ["复古田园", "深底碎花", "米白流苏", "棉布印花", "轻薄垂感"],
        "hero_title": "深底黄白碎花",
        "hero_subtitle": "复古田园感更明显，木色餐桌更好搭",
        "pattern_label": "复古碎花更耐看",
        "scene_hint": "适合餐桌、早餐角、边柜、复古家居陈列",
    },
}


@dataclass
class ProductContext:
    product_name: str
    product_dir: Path
    workbook_path: Path
    texture_image: Path
    edge_image: Path
    title: str
    guide_title: str
    title_direction: str
    visual_traits: str
    category: str
    material: str
    sizes: list[str]
    prices: list[str]
    style_tags: list[str]
    hero_title: str
    hero_subtitle: str
    pattern_label: str
    scene_hint: str


@dataclass
class SceneSpec:
    scene_id: str
    bucket: str
    aspect_label: str
    size: tuple[int, int]
    headline: str
    subtitle: str
    prompt: str


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size=size)
    return ImageFont.load_default()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def reset_dir(path: Path) -> None:
    if path.exists():
        for child in path.iterdir():
            if child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    path.mkdir(parents=True, exist_ok=True)


def wrap_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    line_gap: int = 8,
    max_chars: int = 12,
) -> int:
    x, y = xy
    for line in wrap_text(text, max_chars):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def crop_cover(source: Image.Image, size: tuple[int, int], focus_bottom: bool = False) -> Image.Image:
    target_w, target_h = size
    src_ratio = source.width / source.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)
    resized = source.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max((new_w - target_w) // 2, 0)
    top = max(new_h - target_h - 40, 0) if focus_bottom else max((new_h - target_h) // 2, 0)
    return resized.crop((left, top, left + target_w, top + target_h))


def clean_edge_source(source: Image.Image) -> Image.Image:
    right = int(source.width * 0.8)
    bottom = int(source.height * 0.9)
    return source.crop((0, 0, right, bottom))


def clean_text(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if "?" in text and len(text.replace("?", "")) <= 2:
        return fallback
    return text


def read_visual_copy(product_name: str) -> dict[str, str | list[str]]:
    copy = PRODUCT_COPY.get(product_name)
    if copy:
        return copy

    md_path = PRODUCT_ROOT / "印花布品类" / "识别分组结果.md"
    if not md_path.exists():
        raise RuntimeError(f"{product_name} 缺少产品文案与识别描述。")

    lines = md_path.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"- `{product_name}`":
            start = index
            break
    if start is None:
        raise RuntimeError(f"识别分组结果中未找到 {product_name}。")

    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("- `") and line.strip() != f"- `{product_name}`":
            break
        if line.strip():
            block.append(line.strip())

    title_direction = ""
    visual_traits = ""
    for line in block:
        if line.startswith("- 标题方向："):
            title_direction = line.split("：", 1)[1].strip()
        if line.startswith("- 视觉特征："):
            visual_traits = line.split("：", 1)[1].strip()

    if not title_direction:
        title_direction = f"{product_name}棉布桌布"
    if not visual_traits:
        visual_traits = "印花棉布、统一米白流苏花边、轻薄自然垂感"

    return {
        "title": title_direction[:30],
        "guide_title": title_direction[:30],
        "title_direction": title_direction,
        "visual_traits": visual_traits,
        "style_tags": ["印花桌布", "棉布", "流苏边", "轻薄垂感"],
        "hero_title": title_direction[:8],
        "hero_subtitle": visual_traits[:24],
        "pattern_label": title_direction[:10],
        "scene_hint": "适合家用餐桌、茶几、边柜和生活化陈设",
    }


def read_context(product_name: str) -> ProductContext:
    product_dir = PRODUCT_ROOT / product_name
    if not product_dir.exists():
        raise RuntimeError(f"产品目录不存在：{product_dir}")

    workbook_path = next(product_dir.glob("*.xlsx"))
    images = sorted([path for path in product_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    texture_image = next((path for path in images if "_ref" in path.stem.lower()), None)
    if texture_image is None:
        texture_image = next((path for path in images if "_source" not in path.stem.lower()), None)
    if texture_image is None:
        raise RuntimeError(f"{product_dir} 缺少布样参考图。")

    local_edge = next((path for path in images if "edge" in path.stem.lower() or "花边" in path.stem), None)
    global_edge = PRODUCT_ROOT / "花边图" / "统一花边参考图.jpg"
    edge_image = local_edge if local_edge else global_edge
    if not edge_image.exists():
        raise RuntimeError(f"{product_dir} 缺少花边参考图。")

    wb = load_workbook(workbook_path)
    ws = wb["SKU信息登记"]
    sizes = [str(cell.value) for cell in ws[7][1:4] if cell.value]
    prices = [str(cell.value) for cell in ws[8][1:4] if cell.value]
    category = clean_text(ws["B4"].value, "桌布")
    material = clean_text(ws["B10"].value, "棉布")

    copy = read_visual_copy(product_name)
    title = clean_text(ws["B2"].value, str(copy["title"]))[:30]
    guide_title = clean_text(ws["B3"].value, str(copy["guide_title"]))[:30]
    style_raw = clean_text(ws["B6"].value, "、".join(copy["style_tags"]))
    style_tags = [item.strip() for item in style_raw.replace("，", "、").split("、") if item.strip()]

    return ProductContext(
        product_name=product_name,
        product_dir=product_dir,
        workbook_path=workbook_path,
        texture_image=texture_image,
        edge_image=edge_image,
        title=title,
        guide_title=guide_title,
        title_direction=str(copy["title_direction"]),
        visual_traits=str(copy["visual_traits"]),
        category=category,
        material=material,
        sizes=sizes,
        prices=prices,
        style_tags=style_tags,
        hero_title=str(copy["hero_title"]),
        hero_subtitle=str(copy["hero_subtitle"]),
        pattern_label=str(copy["pattern_label"]),
        scene_hint=str(copy["scene_hint"]),
    )


def build_prompt(ctx: ProductContext, *, aspect_label: str, scene_name: str, composition: str, light: str, props: str, focus: str) -> str:
    return "\n".join(
        [
            "Use case: photorealistic-natural",
            f"Asset type: Taobao {aspect_label} tablecloth listing image",
            f"Primary request: generate one premium ecommerce lifestyle image for {ctx.title}",
            "Input images: Image 1 reference fabric pattern; Image 2 reference tassel edge",
            f"Scene/backdrop: {scene_name}",
            f"Subject: {ctx.visual_traits}; the product is a thin cotton printed tablecloth with an off-white tassel trim about 3 cm wide around the edges",
            "Style/medium: premium ecommerce photography, realistic home textile rendering",
            f"Composition/framing: {composition}",
            f"Lighting/mood: {light}",
            "Color palette: keep the product color accurate; warm neutral interior tones are allowed but must not shift the tablecloth colors",
            "Materials/textures: thin cotton print, clear woven textile texture, natural drape, no plastic sheen, no heavy thick fabric look",
            f"Constraints: keep the pattern accurate and readable; tassel trim must be visible and natural; {focus}; use props like {props}; no text; no watermark",
            "Avoid: collage, patchwork layout board, flat pasted fabric, floating cloth, excessive blur, deformed tassels, extra layers, synthetic sheen, thick upholstery look",
        ]
    )


def build_scene_specs(ctx: ProductContext) -> list[SceneSpec]:
    square_scenes = [
        ("sq01", "日常餐桌", "bright apartment dining room with a light oak table and linen curtains", "square composition, three-quarter angle, full tabletop visible, tassels visible on two sides", "soft side-window morning light", "plates, glassware, folded cloth napkin", "show the overall pattern clearly"),
        ("sq02", "庭院茶桌", "small outdoor courtyard table under a light parasol with potted olive trees", "square composition, slightly elevated angle, one near corner visible, edge drape visible", "warm late-morning sun with gentle shade", "teapot, dessert plates, fruit dish", "show a fresh outdoor hosting atmosphere"),
        ("sq03", "阳台早餐", "city balcony breakfast nook with a compact round table and rattan chair", "square composition, near eye-level angle, round tabletop centered, tassel edge flowing naturally", "soft morning glow", "coffee cup, toast plate, small vase", "show lightweight drape and everyday comfort"),
        ("sq04", "厨边陈列", "country-style kitchen island with open shelving and stoneware", "square composition, frontal angle, tablecloth spread on a console or side cabinet with edge overhang", "warm afternoon light", "books, candle, tray, branch leaves", "show this is suitable beyond dining tables"),
        ("sq05", "花园桌角", "garden side table with wildflower styling and a woven basket nearby", "square composition, close-up angle, corner fold and tassels dominant, still clearly a tablecloth scene", "soft directional highlight", "ceramic cup, linen napkin, small plate", "show thin cotton texture and neat tassel finish"),
    ]
    portrait_scenes = [
        ("pt01", "餐桌主图", "minimal Scandinavian dining nook with pale oak furniture and stoneware", "portrait composition, three-quarter angle, room depth visible behind the table", "clean side-window diffuse light", "plate set, glass cup, greenery", "make the tablecloth the main subject"),
        ("pt02", "待客氛围", "garden-facing dining scene with restrained decor and open French doors", "portrait composition, slightly wider frame, table and surrounding chair hints visible", "warm late-morning light", "tea set, serving tray, fruit bowl", "show richer decor without overpowering the product"),
        ("pt03", "圆桌茶点", "round tea table in a sunroom corner beside tall plants", "portrait composition, gentle high angle, round table fully readable", "soft afternoon light", "tea cup, pastry plate, small flowers", "show a different table shape and scene rhythm"),
        ("pt04", "玄关边柜", "bright entry console styling scene with art prints and a brass tray", "portrait composition, frontal angle, cabinet styling emphasized", "soft indoor light with slight highlight separation", "frame, candle, stack of books, tray", "show multi-scene adaptability"),
        ("pt05", "近景垂感", "close scene focused on one corner of a dining table near a window seat", "portrait composition, close-up with one corner hanging naturally, tassels crisp", "controlled side light with texture emphasis", "plate rim, fork, cup", "show the lightweight cotton drape and edge workmanship"),
    ]
    detail_scenes = [
        ("dt01", "详情首屏", "warm dining room hero scene with product fully styled", "portrait composition, polished full-scene hero shot with clear negative space", "soft natural daylight", "plates, cup, foliage", "build first-screen purchase desire"),
        ("dt02", "花型说明", "tabletop scene emphasizing print readability and color accuracy", "portrait composition, medium-close view across the tabletop", "soft window light", "simple dishware, no clutter", "focus on print and color explanation"),
        ("dt03", "材质流苏", "close edge scene showing tassels and textile weave on a dark wood bench", "portrait composition, close framing on one hanging edge", "angled light with texture shadow", "minimal props only", "focus on texture, tassel trim, and thin cotton feel"),
        ("dt04", "多场景适配", "different home furniture setting such as console, tea table, or balcony table", "portrait composition, wider environment context", "warm indoor daylight", "books, tray, candle", "show scene adaptability without repeating main-image composition"),
        ("dt05", "尺寸选择", "clean listing-friendly dining scene with stable visual structure", "portrait composition, calm background and clear product silhouette", "balanced soft light", "minimal props", "leave visual rhythm suitable for a size selection page"),
    ]

    specs: list[SceneSpec] = [
        SceneSpec(
            scene_id="white01",
            bucket="white",
            aspect_label="白底图",
            size=(1536, 1536),
            headline=ctx.hero_title,
            subtitle=ctx.hero_subtitle,
            prompt="\n".join(
            [
                "Use case: product-mockup",
                "Asset type: Taobao white background product image",
                f"Primary request: create one photorealistic product image for {ctx.title}",
                "Input images: Image 1 reference fabric pattern; Image 2 reference tassel edge",
                "Scene/backdrop: pure clean white studio background",
                f"Subject: {ctx.visual_traits}; the tablecloth is neatly draped on a real solid dining table with a flat tabletop and sturdy legs that are mostly hidden, tassel trim about 3 cm wide visible on multiple sides, the hem hanging about 15 to 20 cm below the tabletop edge, corners relaxed and not stretched open, floor not visible or only a very small sliver at most",
                "Style/medium: clean ecommerce studio photography",
                "Composition/framing: square product-centered composition, clear margins, full product shape readable",
                "Lighting/mood: bright even studio light with soft grounding shadows only",
                "Color palette: keep the product colors accurate and neutral",
                "Materials/textures: thin cotton print, soft relaxed drape, crisp tassel strands, no plastic sheen, no heavy thick fabric feel, no board-like stiffness",
                "Constraints: realistic isolated catalog look; no text; no watermark; no decorative room scene; frame the table so the lower floor area is minimized",
                "Avoid: collage, floating fabric, clipped edges, overexposed whites, deformed tassels, hollow-looking table, warped tabletop, stretched corners, too much floor visible",
            ]
        ),
    )
    ]

    for scene_id, label, scene_name, composition, light, props, focus in square_scenes:
        specs.append(
            SceneSpec(
                scene_id=scene_id,
                bucket="square",
                aspect_label="1:1主图",
                size=(1536, 1536),
                headline=label,
                subtitle=focus,
                prompt=build_prompt(
                    ctx,
                    aspect_label="1:1 main image",
                    scene_name=scene_name,
                    composition=composition,
                    light=light,
                    props=props,
                    focus=focus,
                ),
            )
        )

    for scene_id, label, scene_name, composition, light, props, focus in portrait_scenes:
        specs.append(
            SceneSpec(
                scene_id=scene_id,
                bucket="portrait",
                aspect_label="3:4主图",
                size=(1536, 2048),
                headline=label,
                subtitle=focus,
                prompt=build_prompt(
                    ctx,
                    aspect_label="3:4 main image",
                    scene_name=scene_name,
                    composition=composition,
                    light=light,
                    props=props,
                    focus=focus,
                ),
            )
        )

    for scene_id, label, scene_name, composition, light, props, focus in detail_scenes:
        specs.append(
            SceneSpec(
                scene_id=scene_id,
                bucket="detail",
                aspect_label="详情页场景",
                size=(1536, 2048),
                headline=label,
                subtitle=focus,
                prompt=build_prompt(
                    ctx,
                    aspect_label="detail page image",
                    scene_name=scene_name,
                    composition=composition,
                    light=light,
                    props=props,
                    focus=focus,
                ),
            )
        )
    return specs


def get_cache_paths(product_name: str) -> dict[str, Path]:
    base = CACHE_ROOT / product_name
    raw_dir = base / "raw"
    refs_dir = base / "refs"
    manifest = base / "scene_manifest.json"
    prompts = base / "scene_prompts.md"
    review = base / "self_check.json"
    return {
        "base": base,
        "raw": raw_dir,
        "refs": refs_dir,
        "manifest": manifest,
        "prompts": prompts,
        "review": review,
    }


def write_prompt_book(ctx: ProductContext, specs: list[SceneSpec], prompts_path: Path) -> None:
    lines = [
        f"# {ctx.product_name} image-2 生图任务",
        "",
        f"- 标题：{ctx.title}",
        f"- 标题方向：{ctx.title_direction}",
        f"- 视觉特征：{ctx.visual_traits}",
        "- 花边要求：统一米白流苏花边，视觉宽度约 3 厘米，排布参考 1 号品。",
        "- 布料要求：薄棉布，自然垂感，不做厚重面料。",
        "- 正式目录只保留最终成品，中间 raw 图留在缓存目录。",
        "",
    ]
    for spec in specs:
        lines.extend(
            [
                f"## {spec.scene_id} | {spec.aspect_label} | {spec.headline}",
                "",
                spec.prompt,
                "",
            ]
        )
    prompts_path.write_text("\n".join(lines), encoding="utf-8")


def prepare_product(product_name: str) -> dict[str, Path]:
    ctx = read_context(product_name)
    cache = get_cache_paths(product_name)
    ensure_dir(cache["base"])
    ensure_dir(cache["raw"])
    reset_dir(cache["refs"])
    shutil.copy2(ctx.texture_image, cache["refs"] / f"{product_name}_ref{ctx.texture_image.suffix.lower()}")
    shutil.copy2(ctx.edge_image, cache["refs"] / f"{product_name}_edge{ctx.edge_image.suffix.lower()}")

    specs = build_scene_specs(ctx)
    manifest_payload = {
        "product": asdict(ctx) | {
            "product_dir": str(ctx.product_dir),
            "workbook_path": str(ctx.workbook_path),
            "texture_image": str(ctx.texture_image),
            "edge_image": str(ctx.edge_image),
        },
        "cache_raw_dir": str(cache["raw"]),
        "scenes": [
            {
                "scene_id": spec.scene_id,
                "bucket": spec.bucket,
                "aspect_label": spec.aspect_label,
                "size": list(spec.size),
                "headline": spec.headline,
                "subtitle": spec.subtitle,
                "prompt": spec.prompt,
                "raw_path": str(cache["raw"] / f"{spec.scene_id}.png"),
            }
            for spec in specs
        ],
    }
    cache["manifest"].write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_prompt_book(ctx, specs, cache["prompts"])
    return cache


def latest_generated_image() -> Path:
    if not GENERATED_IMAGE_ROOT.exists():
        raise RuntimeError("未找到订阅生图输出文件。")

    session_dirs = [path for path in GENERATED_IMAGE_ROOT.iterdir() if path.is_dir()]
    if session_dirs:
        latest_session = max(session_dirs, key=lambda path: path.stat().st_mtime)
        candidates = [path for path in latest_session.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)

    direct_files = [path for path in GENERATED_IMAGE_ROOT.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if direct_files:
        return max(direct_files, key=lambda path: path.stat().st_mtime)

    raise RuntimeError("未找到订阅生图输出文件。")


def capture_latest(product_name: str, scene_id: str, source: str | None = None) -> Path:
    cache = get_cache_paths(product_name)
    if not cache["manifest"].exists():
        raise RuntimeError("请先执行 prepare。")
    payload = json.loads(cache["manifest"].read_text(encoding="utf-8"))
    scene = next((item for item in payload["scenes"] if item["scene_id"] == scene_id), None)
    if scene is None:
        raise RuntimeError(f"未找到 scene_id：{scene_id}")
    src = Path(source) if source else latest_generated_image()
    ensure_dir(cache["raw"])
    dst = Path(scene["raw_path"])
    shutil.copy2(src, dst)
    return dst


def load_manifest(product_name: str) -> tuple[dict, dict[str, Path]]:
    cache = get_cache_paths(product_name)
    if not cache["manifest"].exists():
        raise RuntimeError("请先执行 prepare。")
    return json.loads(cache["manifest"].read_text(encoding="utf-8")), cache


def fit_image_to_canvas(src: Path, size: tuple[int, int]) -> Image.Image:
    return crop_cover(Image.open(src).convert("RGB"), size)


def render_copy_overlay(img: Image.Image, headline: str, subtitle: str, aspect: str) -> Image.Image:
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if aspect == "square":
        box = (54, 52, 498, 286)
        headline_font = load_font(58)
        body_font = load_font(28)
    else:
        box = (70, 70, 720, 360)
        headline_font = load_font(70)
        body_font = load_font(30)
    draw.rounded_rectangle(box, radius=30, fill=(248, 243, 236, 196))
    y = box[1] + 34
    draw.text((box[0] + 28, y), headline, font=headline_font, fill=(30, 36, 44, 255))
    y += headline_font.size + 24
    draw_multiline(draw, subtitle, (box[0] + 28, y), body_font, "#5B6470", line_gap=8, max_chars=14)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def render_detail_slice(src: Path, title: str, body: str, out_path: Path) -> None:
    hero = fit_image_to_canvas(src, (750, 1200))
    canvas = hero.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((40, 54, 540, 286), radius=28, fill=(248, 243, 236, 202))
    draw.text((74, 88), title, font=load_font(48), fill=(30, 36, 44, 255))
    draw_multiline(draw, body, (76, 160), load_font(26), "#5B6470", max_chars=14)
    Image.alpha_composite(canvas, overlay).convert("RGB").save(out_path, quality=95)


def average_hash(path: Path, size: int = 8) -> str:
    img = Image.open(path).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def hamming_distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def write_self_check(product_name: str, payload: dict, final_paths: list[Path], review_path: Path) -> None:
    hashes = {path.name: average_hash(path) for path in final_paths}
    duplicate_pairs = []
    names = list(hashes)
    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            dist = hamming_distance(hashes[name_a], hashes[name_b])
            if dist <= 6:
                duplicate_pairs.append({"a": name_a, "b": name_b, "distance": dist})
    report = {
        "product": product_name,
        "generated_scene_count": len(payload["scenes"]),
        "final_asset_count": len(final_paths),
        "checks": {
            "raw_scene_count_ready": all(Path(scene["raw_path"]).exists() for scene in payload["scenes"]),
            "formal_directories_final_only": True,
            "potential_duplicate_pairs": duplicate_pairs,
            "manual_review": {
                "product_accuracy": "pending",
                "pattern_color_accuracy": "pending",
                "dot_or_floral_scale_accuracy": "pending",
                "tassel_and_edge_accuracy": "pending",
                "fabric_not_too_thick": "pending",
                "copy_not_overlapping": "pending",
                "detail_pages_not_repeating_main_images": "pending",
            },
        },
    }
    review_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def update_workbook(ctx: ProductContext) -> None:
    wb = load_workbook(ctx.workbook_path)
    ws = wb["SKU信息登记"]
    ws["B2"] = ctx.title[:30]
    ws["B3"] = ctx.guide_title[:30]
    ws["B6"] = "、".join(ctx.style_tags)
    if str(ws["B27"].value or "").strip() == "3厘米":
        ws["B27"] = "无"
    wb.save(ctx.workbook_path)


def publish_product(product_name: str) -> list[Path]:
    payload, cache = load_manifest(product_name)
    ctx = read_context(product_name)
    scenes = payload["scenes"]
    missing = [scene["scene_id"] for scene in scenes if not Path(scene["raw_path"]).exists()]
    if missing:
        raise RuntimeError(f"以下 raw 图缺失，无法正式出图：{', '.join(missing)}")

    white_dir = ctx.product_dir / "白底图"
    square_dir = ctx.product_dir / "1比1主图"
    portrait_dir = ctx.product_dir / "3比4主图"
    detail_dir = ctx.product_dir / "详情页"
    for path in [white_dir, square_dir, portrait_dir, detail_dir]:
        reset_dir(path)

    final_paths: list[Path] = []

    white_scene = next(scene for scene in scenes if scene["bucket"] == "white")
    white_out = white_dir / "01_白底图_01.png"
    shutil.copy2(white_scene["raw_path"], white_out)
    final_paths.append(white_out)

    square_scenes = [scene for scene in scenes if scene["bucket"] == "square"]
    for index, scene in enumerate(square_scenes, start=1):
        rendered = render_copy_overlay(
            fit_image_to_canvas(Path(scene["raw_path"]), (800, 800)),
            scene["headline"],
            scene["subtitle"],
            "square",
        )
        out = square_dir / f"02_1比1主图_{index:02d}.jpg"
        rendered.save(out, quality=95)
        final_paths.append(out)

    portrait_scenes = [scene for scene in scenes if scene["bucket"] == "portrait"]
    for index, scene in enumerate(portrait_scenes, start=1):
        rendered = render_copy_overlay(
            fit_image_to_canvas(Path(scene["raw_path"]), (900, 1200)),
            scene["headline"],
            scene["subtitle"],
            "portrait",
        )
        out = portrait_dir / f"03_3比4主图_{index:02d}.jpg"
        rendered.save(out, quality=95)
        final_paths.append(out)

    detail_text = {
        "dt01": ("首屏氛围", ctx.hero_subtitle),
        "dt02": ("花型配色", ctx.visual_traits),
        "dt03": ("材质流苏", "薄棉布质感更自然，边缘米白流苏更完整。"),
        "dt04": ("多场景适配", ctx.scene_hint),
        "dt05": ("尺寸选择", "按桌型和垂边需求选择常用尺寸。"),
    }
    detail_scenes = [scene for scene in scenes if scene["bucket"] == "detail"]
    for index, scene in enumerate(detail_scenes, start=1):
        title, body = detail_text[scene["scene_id"]]
        out = detail_dir / f"05_详情页_切片_{index:02d}.jpg"
        render_detail_slice(Path(scene["raw_path"]), title, body, out)
        final_paths.append(out)

    update_workbook(ctx)
    write_self_check(product_name, payload, final_paths, cache["review"])
    return final_paths


def print_status(product_name: str) -> None:
    payload, _ = load_manifest(product_name)
    ready = []
    missing = []
    for scene in payload["scenes"]:
        raw_path = Path(scene["raw_path"])
        (ready if raw_path.exists() else missing).append(scene["scene_id"])
    print("READY:", ", ".join(ready) if ready else "NONE")
    print("MISSING:", ", ".join(missing) if missing else "NONE")


def main() -> None:
    parser = argparse.ArgumentParser(description="桌布 image-2 真实场景工作流")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="生成 raw 缓存目录、scene manifest 和 prompts")
    prepare_parser.add_argument("--product", required=True, help="产品目录名，例如 2号品")

    capture_parser = subparsers.add_parser("capture-latest", help="把最近一张订阅生图抓到指定 scene_id")
    capture_parser.add_argument("--product", required=True)
    capture_parser.add_argument("--scene-id", required=True)
    capture_parser.add_argument("--source", help="可选：指定原图路径，不指定则抓最近一张订阅生图")

    publish_parser = subparsers.add_parser("publish", help="把 raw 图排版为正式目录成品")
    publish_parser.add_argument("--product", required=True)

    status_parser = subparsers.add_parser("status", help="查看 scene raw 图是否齐全")
    status_parser.add_argument("--product", required=True)

    args = parser.parse_args()

    if args.command == "prepare":
        paths = prepare_product(args.product)
        print(paths["manifest"])
        print(paths["prompts"])
        print(paths["raw"])
        return
    if args.command == "capture-latest":
        print(capture_latest(args.product, args.scene_id, args.source))
        return
    if args.command == "publish":
        for path in publish_product(args.product):
            print(path)
        return
    if args.command == "status":
        print_status(args.product)
        return


if __name__ == "__main__":
    main()
