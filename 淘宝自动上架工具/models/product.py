from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto


class TaskStatus(Enum):
    PENDING    = auto()
    RUNNING    = auto()
    DONE       = auto()
    FAILED     = auto()
    SKIPPED    = auto()


@dataclass
class SkuRow:
    """单个 SKU 组合：颜色 + 尺寸 + 价格 + 库存"""
    color:  str
    size:   str
    price:  float
    stock:  int = 100


@dataclass
class Product:
    """一个完整商品，包含所有 SKU 和属性"""
    seq:           str              # 序号，对应图片文件夹名
    title:         str
    skus:          list[SkuRow] = field(default_factory=list)
    shipping_tpl:  str  = '光阴童话'
    delivery_days: int  = 2         # 0=今日发, 1=24h, 2=48h, 3=大于48h
    description:   str  = ''
    cat_id:        str  = ''        # 淘宝类目 ID，用于直链跳过类目弹窗
    image_dir:     Path | None = None

    # 商品属性（可选填写，键=属性名，值=属性值）
    # 示例: {'表面材质': '棉质', '适用场景': '日常使用', '形状': '矩形'}
    attributes:    dict[str, str] = field(default_factory=dict)

    # 多件优惠设置
    multi_discount_enabled: bool  = True   # 是否启用多件优惠
    multi_discount_type:    str   = '满2件打折'
    multi_discount_rate:    str   = '9.5'  # 折扣率，如 '9.5' 表示9.5折

    # 导购标题（短标题，最多15汉字/30字符）
    guide_title: str = ''

    # 图片列表（运行时由 ImageProcessor 填充）
    main_images:      list[Path] = field(default_factory=list)   # 1:1主图，最多5张
    main_images_3x4:  list[Path] = field(default_factory=list)   # 3:4主图，最多5张
    white_bg_images:  list[Path] = field(default_factory=list)   # 白底图，最多1张
    selling_images:   list[Path] = field(default_factory=list)   # 卖点图（上传到图文详情，排在详情图前）
    detail_images:    list[Path] = field(default_factory=list)   # 详情图
    sku_images:       dict[str, Path] = field(default_factory=dict)  # {颜色: 图片路径}

    # 任务状态
    status:  TaskStatus = TaskStatus.PENDING
    error:   str        = ''
    item_id: str        = ''   # 上架成功后填入淘宝商品 ID

    @property
    def colors(self) -> list[str]:
        seen = []
        for s in self.skus:
            if s.color not in seen:
                seen.append(s.color)
        return seen

    @property
    def sizes(self) -> list[str]:
        seen = []
        for s in self.skus:
            if s.size not in seen:
                seen.append(s.size)
        return seen

    def price_for(self, color: str, size: str) -> float:
        for s in self.skus:
            if s.color == color and s.size == size:
                return s.price
        return self.skus[0].price if self.skus else 0.0

    def stock_for(self, color: str, size: str) -> int:
        for s in self.skus:
            if s.color == color and s.size == size:
                return s.stock
        return 100

    @property
    def title_char_count(self) -> int:
        """计算标题字符数（中文占2位）"""
        count = 0
        for ch in self.title:
            count += 2 if '一' <= ch <= '鿿' else 1
        return count
