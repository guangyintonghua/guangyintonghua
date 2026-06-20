"""
多店铺账号管理：读取 config/accounts.json，跟踪每个账号当日上架数量。
"""
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from loguru import logger


_CFG = Path('config') / 'accounts.json'
_COUNTER_FILE = Path('data') / 'daily_counter.json'
_DAILY_LIMIT = 40   # 单账号每日上架上限


@dataclass
class Account:
    name:        str
    label:       str = ''          # 店铺昵称（展示用）
    daily_limit: int = _DAILY_LIMIT
    shipping_tpl_map: dict = field(default_factory=dict)  # 运费模板名称映射
    _today_count: int = field(default=0, repr=False)

    @property
    def available(self) -> bool:
        return self._today_count < self.daily_limit

    def increment(self):
        self._today_count += 1


class AccountManager:
    def __init__(self, cfg_path: Path = _CFG):
        self._accounts: list[Account] = []
        self._counter_file = _COUNTER_FILE
        self._counter_file.parent.mkdir(parents=True, exist_ok=True)
        self._load(cfg_path)
        self._restore_counters()

    def _load(self, cfg_path: Path):
        if not cfg_path.exists():
            logger.warning(f"账号配置不存在: {cfg_path}，将使用示例账号")
            self._accounts = [Account(name='default', label='默认店铺')]
            return
        data = json.loads(cfg_path.read_text(encoding='utf-8'))
        for item in data.get('accounts', []):
            self._accounts.append(Account(
                name=item['name'],
                label=item.get('label', item['name']),
                daily_limit=item.get('daily_limit', _DAILY_LIMIT),
                shipping_tpl_map=item.get('shipping_tpl_map', {}),
            ))
        logger.info(f"加载账号 {len(self._accounts)} 个: "
                    f"{[a.label for a in self._accounts]}")

    def _restore_counters(self):
        today = str(date.today())
        if not self._counter_file.exists():
            return
        try:
            data = json.loads(self._counter_file.read_text(encoding='utf-8'))
            if data.get('date') != today:
                return   # 新的一天，计数清零
            for a in self._accounts:
                a._today_count = data.get('counts', {}).get(a.name, 0)
        except Exception:
            pass

    def save_counters(self):
        data = {
            'date': str(date.today()),
            'counts': {a.name: a._today_count for a in self._accounts}
        }
        self._counter_file.write_text(
            json.dumps(data, ensure_ascii=False), encoding='utf-8'
        )

    def get_available(self) -> Account | None:
        for a in self._accounts:
            if a.available:
                return a
        return None

    def all_full(self) -> bool:
        return all(not a.available for a in self._accounts)

    def status(self) -> list[dict]:
        return [{'name': a.label, 'today': a._today_count,
                 'limit': a.daily_limit, 'available': a.available}
                for a in self._accounts]

    def resolve_shipping_tpl(self, account: Account, tpl_name: str) -> str:
        """将通用模板名转换为该账号的实际模板名"""
        return account.shipping_tpl_map.get(tpl_name, tpl_name)
