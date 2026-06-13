# Release Note — v1.1

全屏乐谱显示模式 + macOS 触控板双指缩放。

## 新增功能

### 全屏乐谱双页显示
- **Ctrl+Cmd+F** 一键切换全屏乐谱模式
- 侧边栏（曲目列表、信息面板）隐藏，乐谱区占满整个窗口
- **双页并排显示**：默认同时展示两页乐谱，中间留缝隙
- 单页歌曲自动居中显示单页
- 翻页每次步进 1 页，左页变右页，新页出现在右侧
- 乐谱底部翻页按钮右侧新增 **「切换显示模式」按钮**，鼠标点击触发

### macOS 触控板双指缩放
- 乐谱显示区支持双指捏合/拉伸缩放
- 缩放以双指中心为锚点，跟手且稳定
- 缩放过程流畅，松手后画面锁定不反弹
- **缩回到未放大状态时自动居中归位**（与滚轮缩放一致）
- 双指缩放与滚轮缩放互不冲突

### 交互增强
- **Cmd+F** 聚焦搜索框并全选文本（全屏乐谱模式下忽略）
- **ESC** 退出系统全屏窗口

## 技术要点

| 模块 | 变更 |
|------|------|
| `app/widgets/pdf_viewer.py` | 新增 `DualScoreCanvas` 双页渲染类；双指缩放（累加 deltas + EMA 平滑 + 指数映射 + 冻结 base_offset 锚点 + 1ms 去重） |
| `app/main_window.py` | Ctrl+Cmd+F / Cmd+F / ESC 快捷键；QApplication 全局 eventFilter 拦截 NativeGesture |
| `app/exporters.py` | 新增 Markdown 导出功能 |

### 双指缩放架构

```
macOS NSEvent → QApplication eventFilter → canvas._handle_native_gesture
                                              ↓
                                     accum += value() × 去重
                                     EMA 70/30 平滑
                                     scale = 2^(smooth × 3.0)
                                     zoom = base_zoom × scale
                                     offset = base_offset × ratio + anchor
```

- **累加**而非直接使用 value()，随手指行程自然增长
- **EMA 70%/30%** 过滤 value() 快速振荡（macOS 原始值在 ±0.02~0.10 间跳动）
- **冻结 base_offset** 避免跨帧浮点累加漂移
- **1ms 时间戳去重**：macOS 将每个手势事件投放至 3 个 NSView，eventFilter 被触发 3 次

## 已修复 (v1.0 -> v1.1)

- 搜索筛选时键盘导航跳闪（改为筛选时重建列表）
- 切换显示模式按钮高度与翻页按钮统一
- 双指缩放卡顿 → 去重 + FastTransformation 渲染
- 双指缩放锚点漂移 → 冻结 base_offset
- 双指缩放不单调/颠簸/重影 → 发现并修复三连发重复事件

## 已知限制

- 多页乐谱暂不支持并排显示，需翻页浏览（全屏双页模式下亦然）
- 部分 OCR 自动导入的曲名需手工修正
- 无 PDF 全文搜索
- 无单元测试覆盖
