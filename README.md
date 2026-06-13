# X-ScoreHub

Jazz 乐谱浏览与管理应用。基于 PyQt5 + SQLite + PyMuPDF，支持多分册 PDF 乐谱的检索、预览、编辑和收藏。

## 当前状态 (v1.0)

- **11566 首曲目**（21 首已删除），覆盖 **10 个分册**
- 完整 CRUD + 软删除/恢复 + 收藏
- PDF 高 DPI 渲染，支持缩放（滚轮）和拖拽平移
- 搜索支持通配符 `*`，实时筛选
- 多选模式 + 批量操作（删除/恢复/彻底删除）
- 列表懒加载，万级数据流畅滚动
- Markdown 格式导入/导出
- OCR 结果自动纠偏脚本

## 功能

- **乐谱浏览** — 左侧曲目列表支持搜索（含 `*` 通配符）、按分册/难度/收藏/删除状态筛选，按页码/录入顺序/难度排序
- **PDF 渲染** — 选中曲目自动定位对应分册的对应页码，200 DPI 高清渲染。支持滚轮缩放（1x~8x）、拖拽平移，窗口大小变化时自适应
- **多页翻页** — 底部翻页按钮 + 键盘左右方向键（焦点不在输入框时）
- **信息编辑** — 右侧面板可编辑曲名、译名、别名、难度、页码、占用页数、分册、备注。◀▶ 按钮逐页预览定位
- **收藏 & 软删除** — 一键收藏/取消（★），删除后进入回收站可恢复，彻底删除需确认
- **批量操作** — 多选曲目（Ctrl/Shift+点击）后显示批量操作栏：批量删除、批量恢复、彻底删除
- **数据导入** — 支持 Markdown 表格批量导入。增量导入：仅替换文件中涉及的分册，不影响其他分册数据
- **数据导出** — 选中曲目导出为 Markdown 表格（Ctrl+E）
- **手动录入** — 界面中直接新增曲目（Ctrl+N 或「New」按钮）

## 环境要求

- Python 3.10+
- PyQt5
- PyMuPDF (fitz)

## 安装

```bash
cd X-ScoreHub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
source .venv/bin/activate
python main.py
```

首次运行会自动创建 `scores.db`。数据库已预置 11566 首曲目，可直接使用。

## 项目结构

```
X-ScoreHub/
├── main.py                    # 入口：初始化 DB、设置图标和样式、启动主窗口
├── app/
│   ├── __init__.py
│   ├── database.py            # SQLite 数据层（CRUD、批量操作、迁移）
│   ├── importers.py           # Markdown 导入（智能分册名匹配、增量导入）
│   ├── exporters.py           # Markdown 导出
│   ├── main_window.py         # 主窗口（三栏布局 + 键盘事件 + 菜单）
│   └── widgets/
│       ├── song_list.py       # 左栏 — 搜索/筛选/排序/批量操作/懒加载
│       ├── pdf_viewer.py      # 中栏 — PDF 渲染/缩放/平移/翻页
│       └── song_info.py       # 右栏 — 信息编辑/收藏/删除/页码预览
├── apply_ocr_results.py       # OCR 结果纠偏脚本（位置约束匹配）
├── pdf_repo/                  # PDF 乐谱分册（10 个文件）
├── import-md/                 # 导入数据源（Markdown 表格）
├── requirements.txt           # Python 依赖
├── scores.db                  # SQLite 数据库
└── IMPORT_SONG_FORMAT.md      # 导入格式规范文档
```

## 可用分册

| 文件名 | 说明 |
|--------|------|
| `557 Jazz Standards, Swing To Bop.pdf` | 557 Jazz Standards |
| `The New Real Book Vol.1.pdf` | The New Real Book 第 1 卷 |
| `The New Real Book Vol.2.pdf` | The New Real Book 第 2 卷 |
| `The New Real Book Vol.3.pdf` | The New Real Book 第 3 卷 |
| `The Real Book Of Blues (225 Songs).pdf` | The Real Book Of Blues |
| `The-Real-Book-6th-Edition-Eb.pdf` | The Real Book 6th Edition (Eb) |
| `The Rea Easy Book Volume-1-C Tunes for Beggining Improv.pdf` | The Rea Easy Book 第 1 卷 |
| `The Rea Easy Book Volume-2-C Tunes for Intermediate Improvisors.pdf` | The Rea Easy Book 第 2 卷 |
| `乐队总谱合集.pdf` | 乐队总谱合集 |
| `简谱合集.pdf` | 简谱合集 |

## 快捷键

| 按键 | 功能 |
|------|------|
| `←` `→` | PDF 前后翻页（需焦点不在输入框） |
| `Ctrl+N` | 新增曲目 |
| `Ctrl+E` | 导出选中曲目 |
| 滚轮 | PDF 缩放 |
| 拖拽 | PDF 平移（缩放后） |

## 数据库 Schema

```sql
CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER,          -- 在分册中的序号
    name TEXT NOT NULL,        -- 曲名
    name_cn TEXT DEFAULT '',   -- 中文译名
    alias TEXT DEFAULT '',     -- 别名
    difficulty INTEGER DEFAULT 0,  -- 难度 1-9
    pdf_start_page INTEGER NOT NULL,  -- PDF 起始页码
    pdf_pages INTEGER NOT NULL DEFAULT 1,  -- 占用页数
    volume TEXT NOT NULL,      -- 所属分册文件名
    notes TEXT DEFAULT '',     -- 备注
    favorite INTEGER DEFAULT 0,   -- 收藏标记
    deleted INTEGER DEFAULT 0,    -- 软删除标记
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
