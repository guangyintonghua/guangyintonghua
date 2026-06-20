# 淘宝自动上架工具

基于 Playwright CDP + PySide6 的淘宝商品自动发布工具。

## 功能

- 扫描本地产品素材文件夹，自动填写标题、主图、详情图、属性、SKU、运费模板并提交发布
- PySide6 图形界面，实时显示进度和日志
- 支持同一产品反复上架
- 连接已打开的 Chrome 调试实例（CDP），无需重新登录

## 环境要求

```
pip install -r requirements.txt
playwright install chromium
```

## 使用方式

### 图形界面（推荐）

```bash
python app.py
```

### 命令行

```bash
python run_upload.py [产品文件夹路径]
```

## 启动步骤

1. 运行 `启动调试浏览器.bat`，在打开的 Chrome 中登录淘宝卖家后台
2. 运行 `python app.py` 启动工具
3. 点击「导入文件夹」选择产品目录，点击「开始上架」

## 产品素材目录结构

```
产品文件夹/
├── SKU信息登记表.xlsx   # 标题、属性、价格等信息
├── 主图/               # 1:1 主图（最多5张）
├── 详情图/             # 详情页图片
└── 白底图/             # 可选
```
