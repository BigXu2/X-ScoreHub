# 歌曲导入 Markdown 文件格式说明

本文档面向需要生成歌曲导入数据的 agent，请严格按以下规范编写。

---

## 文件格式

文件为 UTF-8 编码的 Markdown 文件，内容是**管道分隔的表格**。格式如下：

```
| 序号 | 曲名 | 翻译曲名 | 别名 | 难度 | PDF 起始页码 | 占用页数 | 所属分册 |
|------|------|---------|------|------|-------------|---------|---------|
| 1 | Autumn Leaves | 秋叶 |  | 3 | 5 | 1 | The New Real Book Vol.1 |
| 2 | Blue Bossa | 蓝色波萨 |  | 4 | 6 | 2 | The New Real Book Vol.1 |
```

---

## 解析规则（由 `app/importers.py` 的 `parse_markdown_table` 执行）

1. **首行**（表头行）：必须包含 `序号` 字样，该行会被跳过。
2. **第二行**（分隔行）：必须包含 `------`，该行会被跳过。
3. **后续所有行**：必须为数据行，每行必须以 `|` 开头，否则跳过。
4. **列数**：每行按 `|` 分割后至少 9 个部分（含首尾空段），不足 9 个的行跳过。
5. **字段类型转换**：序号、难度、PDF 起始页码、占用页数 会转为 `int`，转换失败则该行跳过。
6. **`.pdf` 后缀**：分册名若不以 `.pdf` 结尾，会自动追加。建议直接写完整文件名。
7. **导入行为**：`import_from_file` 会**清空数据库中所有现有数据**再插入，请确保文件包含完整的歌曲列表。

---

## 8 列字段定义

| 列号 (1-based) | 列名 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| 1 | 序号 | int | 是 | 歌曲在分册中的排列序号，用于默认排序 |
| 2 | 曲名 | str | 是 | 歌曲英文原名 |
| 3 | 翻译曲名 | str | 否 | 中文译名，无数据时留空 |
| 4 | 别名 | str | 否 | 歌曲别名/副标题，无数据时留空 |
| 5 | 难度 | int | 否 | 1-9 星评级，无数据时填 `0` |
| 6 | PDF 起始页码 | int | 是 | 歌曲在 PDF 中的起始页码（从 1 开始） |
| 7 | 占用页数 | int | 是 | 歌曲占用的 PDF 页数，单页填 `1` |
| 8 | 所属分册 | str | 是 | PDF 文件名，见下方可用分册列表 |

---

## 可用分册（必须与 `pdf_repo/` 中的文件一一对应）

| 文件名 | 说明 |
|--------|------|
| `The New Real Book Vol.1.pdf` | The New Real Book 第 1 卷 |
| `The New Real Book Vol.2.pdf` | The New Real Book 第 2 卷 |
| `The New Real Book Vol.3.pdf` | The New Real Book 第 3 卷 |
| `The Real Book Of Blues.pdf` | The Real Book Of Blues |
| `The-Real-Book-6th-Edition-Eb.pdf` | The Real Book 6th Edition (Eb) |
| `The Rea Easy Book Volume-1-C Tunes for Beggining Improv.pdf` | The Rea Easy Book 第 1 卷 (C Tunes) |
| `The Rea Easy Book Volume-2-C Tunes for Intermediate Improvisors.pdf` | The Rea Easy Book 第 2 卷 (C Tunes) |

> **注意**：文件名区分大小写，拼写必须完全一致。

---

## 示例（可直接复制）

```
| 序号 | 曲名 | 翻译曲名 | 别名 | 难度 | PDF 起始页码 | 占用页数 | 所属分册 |
|------|------|---------|------|------|-------------|---------|---------|
| 1 | Autumn Leaves | 秋叶 |  | 3 | 5 | 1 | The New Real Book Vol.1 |
| 2 | Blue Bossa | 蓝色波萨 | Bossa Nova | 4 | 6 | 2 | The New Real Book Vol.1 |
| 3 | Giant Steps | 巨人步伐 |  | 9 | 10 | 2 | The New Real Book Vol.2 |
| 4 | St. Thomas | 圣托马斯 |  | 5 | 12 | 1 | The Real Book Of Blues |
```

---

## 常见错误（务必避免）

1. **缺少分隔行**：表头行后必须有 `|------|------|...` 行。
2. **列数不足**：8 个字段都需要 `|` 分隔，即使某些字段留空。
3. **序号不连续**：不要求完全连续，但序号用于排序，建议保持连续。
4. **空别名写成空格**：留空写 `| |` 即可，不要填 `| 无 |` 或 `| - |`。
5. **分册名拼写错误**：必须与 `pdf_repo/` 中实际文件名一致。
6. **难度超出范围**：只能填 0-9，0 表示未评级。
