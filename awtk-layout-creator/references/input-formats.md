# 输入资料格式与处理规则

本 skill 的输入通常有三类：**UI 效果图**、**切图资源**、**切图坐标计划书（Excel）**。本文件规定如何读取、校验、命名和落盘，避免“图对不上、图找不到、坐标单位搞错”。

## 1. 输入清单

开始生成 XML 前，先确认拿到以下资料（缺一项就明确告知用户，不要猜）：

| 输入 | 必需 | 用途 |
| --- | --- | --- |
| UI 效果图（PNG/JPG） | 是 | 视觉基准、颜色/字号/间距参考 |
| 切图资源（目录或压缩包） | 是 | `design/<theme>/images/` 的素材 |
| 坐标计划书（Excel/CSV） | 建议 | 精确的 x/y/w/h、控件名、类型 |
| 屏幕分辨率 | 是 | `lcd_w`/`lcd_h`，决定坐标换算 |
| 设计稿尺寸 | 是 | 与屏幕分辨率一起算缩放 |
| 字体文件 | 可选 | 非默认字体时提供 |
| 已有工程/AWTK 路径 | 是 | 决定输出位置和预览工具 |

## 2. UI 效果图

### 2.1 读取

- 支持 PNG/JPG/BMP。
- 环境没有 Pillow 时，用 `scripts/awtk_common.py` 的 `load_image()`：优先 Pillow，缺失时调用 PowerShell `System.Drawing` 转 BMP 再用 stdlib 解析。
- 读取后至少获取：宽、高、像素颜色。用于取色、测量边界、生成对比图。

### 2.2 测量

生成前先测量以下基准，记录到 `design_spec.json`：

1. **画布尺寸**：效果图是否包含设备边框/阴影/背景留白。
2. **内容区原点**：`origin_x`、`origin_y`（设备边框左侧/顶部厚度）。
3. **内容区尺寸**：`content_w`、`content_h`。
4. **缩放比**：

```text
scale_x = content_w / lcd_w
scale_y = content_h / lcd_h
```

5. **主色**：标题栏、按钮、背景、强调色的十六进制值。
6. **字号**：按效果图字高估算，最终以 AWTK 预览为准。

> 如果 `scale_x != scale_y`，先检查效果图是否被非等比缩放，或内容区是否测错；不要直接取平均。

### 2.3 切图与效果图的关系

- 效果图是“合成后的样子”，切图是“拆开的零件”。按钮的圆角、阴影、渐变通常在切图里，不在 XML 里重复实现。
- 效果图上是一个整体卡片时，切图可能是一张 `patch9` 背景 + 若干文字/图标控件。**不要为每个像素都创建控件**。
- 效果图上的文字应生成 `label`/`button` 的 `text`，不要当图片切进去（除非是艺术字/图标字）。

## 3. 切图资源

### 3.1 目录结构

AWTK 按密度分目录：

```text
design/<theme>/images/
├── x1/        # 1x，基准
├── x2/        # 2x
├── x3/        # 3x
├── x4/        # 4x
├── xx/        # 与屏幕密度无关的背景大图
└── svg/       # 矢量图（指针、图标）
```

- XML 中引用**不带目录、不带扩展名**：`image="btn_ok"`。
- 同一资源可只提供 `x1`，高密度屏由系统放大；要清晰则提供 `x2/x3`。
- 指针、表盘、可缩放图标优先 `svg/`。

### 3.2 命名规范

生成 XML 前统一重命名切图，规则：

| 类型 | 命名 | 示例 |
| --- | --- | --- |
| 普通图片 | `<模块>_<元素>` | `cluster_bg`、`icon_fuel` |
| 按钮背景 | `<元素>_<状态>` | `btn_ok_n`、`btn_ok_p`、`btn_ok_d` |
| 图标状态 | `<图标>_<状态>` | `turn_left_on`、`abs_off` |
| 数字位图 | `digit_<字符>` | `digit_0` … `digit_9`、`digit_-`、`digit_.` |
| 序列帧 | `<动画>_<序号>` | `loading_1` … `loading_12` |
| 指针 | `<表盘>_needle` | `speed_needle`、`rpm_needle` |

约束：

- 只用小写字母、数字、下划线；不要空格、中文、`-`（AWTK 资源名对 `-` 支持不稳定）。
- 名字全局唯一；同名资源放在不同密度目录下表示同一资源的不同分辨率。
- 切图不要带设备边框外的透明大边，否则布局会“看起来偏了”。

### 3.3 切图检查

对每张切图确认：

- 尺寸与设计稿标注一致（2x 图是 1x 的两倍）。
- 背景透明的图是 PNG 且带 alpha。
- 九宫格背景四角无内容、可拉伸区域干净。
- 指针图方向朝上（12 点钟），旋转中心在图片内。
- 数字图等高等宽（同一位数风格一致）。

## 4. 坐标计划书（Excel）

### 4.1 常见列

用户提供的 Excel 可能列名不统一。先读表头，映射到标准字段：

| 标准字段 | 常见列名 |
| --- | --- |
| `name` | 控件名、名称、name、id |
| `type` | 类型、控件类型、type、widget |
| `x` | X、x、left、左边距 |
| `y` | Y、y、top、上边距 |
| `w` | W、宽、width、宽度 |
| `h` | H、高、height、高度 |
| `text` | 文本、文字、内容、text |
| `image` | 图片、切图、资源、image |
| `style` | 样式、style |
| `parent` | 父控件、容器、parent |
| `note` | 备注、说明、note |

无法识别的列保留原样，写入 `design_spec.json` 的 `extra`，不要丢弃。

### 4.2 单位与坐标系

必须确认三件事：

1. **单位**：像素还是毫米/点？
   - 若数值范围与屏幕尺寸同量级（如 0～800），大概率是像素。
   - 若出现小数或 0～100 范围，可能是毫米/百分比。
2. **原点**：屏幕左上角，还是设计稿内容区左上角？
3. **缩放**：坐标是设计稿像素（2x）还是 LCD 像素（1x）？

校验方法：

```text
max(x + w) ≈ 设计稿宽 or LCD 宽
max(y + h) ≈ 设计稿高 or LCD 高
```

不一致时先问用户，不要自动“猜一个缩放”。

### 4.3 合并单元格与多级表头

- 合并单元格只在左上角有值；解析后要把值向下/向右填充。
- 多级表头取最后一行作为列名，或让用户确认。
- 一个 sheet 多个屏幕时，按 `screen`/`页面` 列分组；没有分组列则默认一个 sheet 一个屏幕。

### 4.4 读取工具

```bash
python scripts/read_xlsx.py <file.xlsx> --sheet 0 --json out.json
python scripts/read_xlsx.py <file.xlsx> --list-sheets
python scripts/read_xlsx.py <file.xlsx> --csv out.csv
```

- 纯标准库实现（xlsx 是 zip + XML），不依赖 openpyxl。
- 支持共享字符串、内联字符串、合并单元格、日期（原样输出序列号）。
- 输出 JSON 时保留 `sheet`、`rows`、`merged`、`headers`。

### 4.5 坐标表 → 控件树

按 `parent` 列或缩进层级建立树：

- 没有 `parent` 时，按包含关系推断：若控件 A 的矩形完全包含 B，且 A 是容器类型，则 B 是 A 的子控件。
- 推断不可靠时，让用户提供层级或按视觉分组。
- 同级控件按 `y` 再 `x` 排序，保证 XML 中的顺序（z-order）与设计一致。

## 5. 设计规格单一事实来源：design_spec.json

所有输入最终归一化成一个 JSON，后续生成 XML、校验、对比都以它为准。建议结构：

```json
{
  "project": {
    "name": "cluster",
    "lcd": { "w": 800, "h": 480 },
    "theme": "default",
    "dpr": 1,
    "awtk_root": "D:/SoftwareHub/AWStudio/AWTK/SDK/awtk"
  },
  "design": {
    "file": "mockup.png",
    "width": 1600,
    "height": 960,
    "origin": [0, 0],
    "scale": 2.0
  },
  "colors": {
    "bg": "#101418",
    "primary": "#338FFF",
    "text": "#E6EDF3"
  },
  "fonts": {
    "default": { "name": "default", "size": 18 }
  },
  "screens": [
    {
      "name": "main",
      "type": "window",
      "file": "main.xml",
      "x": 0, "y": 0, "w": 800, "h": 480,
      "style": "default",
      "children": [
        {
          "name": "title",
          "type": "label",
          "x": 24, "y": 16, "w": 300, "h": 32,
          "text": "Vehicle Status",
          "style": "title"
        }
      ]
    }
  ],
  "assets": {
    "root": "design/default/images",
    "files": ["x1/bg.png", "x1/icon_fuel.png"]
  }
}
```

约定：

- 坐标一律是 **LCD 像素**（已换算）；原始设计稿坐标放 `source` 字段备查。
- `scale` 是设计稿 → LCD 的缩放比；`dpr` 是资源密度。
- 每个控件必须有唯一 `name`；纯装饰容器可自动命名 `view_1`。
- `screen.file` 是**相对 `--out-dir` 的路径**（可含子目录，目录自动创建）；省略时用 `<name>.xml`。
- `children` 为空表示叶子控件。
- 未识别的字段原样保留，生成器忽略即可。

## 6. 输入缺失时的处理

| 缺失 | 处理 |
| --- | --- |
| 没有 Excel，只有效果图 | 用像素测量 + 人工识别生成 `design_spec.json`，在交付说明中标注“坐标为估算” |
| 没有效果图，只有 Excel | 可以生成结构，但颜色/字体用主题默认值，并提示用户预览确认 |
| 没有切图 | 用占位图/纯色块，`image` 引用保留；在交付说明中列出缺失资源 |
| 没有字体 | 用 `default` 字体，提示字号可能偏差 |
| 分辨率不明 | 从 `project.json` 读取；没有工程时询问用户 |
| 设计稿尺寸不明 | 用 Excel 最大值推断，或询问用户 |

> 任何“猜”的地方都要在最终交付说明中列出，方便用户核对。

## 7. 文件名与编码

- XML 文件 UTF-8 无 BOM。
- 文件内换行 LF 或 CRLF 均可，但同一工程保持一致。
- 资源名、控件名、文件名统一小写 + 下划线。
- 中文文本直接写入 XML（UTF-8）；需要翻译的文本用 `tr_text`，不要硬编码到多语言工程。
- XML 特殊字符转义：`&` → `&amp;`、`<` → `&lt;`、`>` → `&gt;`、`"` → `&quot;`；复杂文本用 `<property>` + CDATA。
