# CLAUDE.md — X-ScoreHub

Jazz 乐谱浏览与管理桌面应用。PyQt5 + SQLite + PyMuPDF 技术栈。

## 项目概述

X-ScoreHub 是一个 Jazz 乐谱 PDF 的浏览和曲目管理工具。核心功能是将多本 PDF 分册中的上万首曲目与 PDF 页码精确关联，实现快速检索和预览。

**当前数据规模**：11566 首曲目，10 个 PDF 分册，21 首已软删除。

## 架构

```
main.py  →  MainWindow  →  ┌─ SongListPanel (左栏)
                            ├─ PdfViewerPanel (中栏) → ScoreCanvas (缩放/平移)
                            └─ SongInfoPanel  (右栏)
         ↓
    database.py (SQLite CRUD)
    importers.py / exporters.py (Markdown 导入导出)
```

- **信号驱动**：Widget 间通过 PyQt5 Signal 通信，MainWindow 充当中介（mediator 模式）
- **数据流**：左侧选中曲目 → `song_selected` → 中栏渲染 PDF + 右栏显示详情 → 右栏编辑保存 → `data_saved` → 左栏刷新列表
- **无 ORM**：直接使用 `sqlite3`，Row 对象转 dict，简单直接

## 关键文件

| 文件 | 职责 | 行数 |
|------|------|------|
| `main.py` | 入口：初始化 DB、应用图标、全局样式、启动窗口 | ~55 |
| `app/database.py` | SQLite 数据层：CRUD、批量操作、分册查询、迁移 | ~170 |
| `app/importers.py` | Markdown 解析：智能分册名匹配 + 增量导入 | ~90 |
| `app/exporters.py` | 选中曲目导出为 Markdown 表格 | ~30 |
| `app/main_window.py` | 主窗口：三栏 Splitter 布局、菜单栏、键盘事件路由 | ~170 |
| `app/widgets/song_list.py` | 曲目列表：搜索(含通配符)、筛选、排序、批量操作、懒加载 | ~420 |
| `app/widgets/pdf_viewer.py` | PDF 渲染：PyMuPDF 200DPI、ScoreCanvas 缩放平移、翻页 | ~295 |
| `app/widgets/song_info.py` | 信息编辑：表单字段、收藏/删除切换、页码◀▶预览 | ~290 |
| `apply_ocr_results.py` | OCR 结果纠偏：位置约束匹配（±20页窗口），支持 dry-run | ~110 |

## 数据库

- 文件：项目根目录 `scores.db`，首次运行自动创建
- 表：`songs`（见 README Schema）
- 索引：无显式索引，数据量 1.1w 查询无性能问题
- 软删除：`deleted` 字段标记，不物理删除（除非用户确认「彻底删除」）
- 迁移：`init_db()` 包含 `ALTER TABLE ADD COLUMN deleted` 的兼容迁移

## PDF 渲染细节

- 渲染 DPI：200（`RENDER_DPI`），在高分屏上清晰
- 缩放范围：1.0x ~ 8.0x，步进 0.12
- 缩放逻辑：以鼠标位置为中心缩放（`wheelEvent` 中的 offset 计算）
- 平移：缩放后可拖拽平移，带边界限制防止完全漂移出视野
- resize：窗口大小变化时自动重新渲染当前页（`resizeEvent` → `_render_current_page`）
- 缓存：打开过的 PDF 文档缓存在 `_docs` dict 中，关闭窗口时调用 `clear_cache()` 释放

## 列表懒加载

`song_list.py` 中的懒加载机制：
- 初始加载 100 首（`INITIAL_LOAD`）
- 滚动到底部附近时追加 50 首（`LOAD_MORE`）
- 搜索时加载全部数据再过滤（确保搜索覆盖全集）
- 筛选条件变化时 `refresh()` 重新从 DB 查询，重置显示

## 导入机制

- **智能分册名匹配**：`_resolve_volume()` 通过 `_build_pdf_index()` 建立索引，匹配不区分大小写，自动处理缺失/错误后缀
- **增量导入**：`import_from_file()` 使用 `delete_songs_by_volumes()` 只替换文件中涉及的分册，不影响其他分册数据
- **数据源**：`import-md/` 目录下存放各分册的导入 Markdown 文件

## 批量操作逻辑

左栏 `SongListPanel` 支持 ExtendedSelection 多选：
- 选中 ≥2 首 → 进入多选模式：筛选控件禁用、批量操作栏显示
- 批量删除/恢复按钮根据选中项的 `deleted` 状态动态显示/隐藏
- 操作后自动退出多选模式并刷新列表

## 开发注意事项

1. **信号阻塞**：刷新列表时使用 `blockSignals(True/False)` 避免级联信号触发
2. **页码预览**：右栏页码 spinner 的 `valueChanged` 会触发 `page_preview` 信号到中栏预览页面。加载歌曲时需阻塞信号避免错误地将 `pdf_pages` 设为 1
3. **焦点检测**：键盘左右方向键翻页前检查 `focusWidget()` 类型，避免在输入框中误触发
4. **路径计算**：各模块使用 `os.path.dirname` 相对计算项目根目录和 `pdf_repo` 路径
5. **数据库连接**：每次操作新建连接并关闭，无连接池（单用户桌面应用无需）
6. **虚拟环境**：项目使用 `.venv/` 管理依赖，**严禁在 venv 外执行 pip install**

## 已知限制

- 多页乐谱不支持并排显示，需逐页翻页
- 部分 OCR 自动导入的曲名可能需手工修正（尤其是 Eb 版 Real Book 手写体扫描）
- 无单元测试
- 无 PDF 全文搜索（仅按曲名/译名/别名搜索）
