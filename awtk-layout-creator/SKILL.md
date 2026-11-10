---
name: awtk-layout-creator
description: 把 UI 效果图、切图资源和坐标计划书（Excel）转换成可运行的 AWTK UI XML 与样式，并用 AWTK 官方 preview_ui 预览、截图、与效果图逐像素比对迭代。适用于 AWTK / AWStudio / AWTK Designer 工程，支持 2W 仪表、中控、HMI、通用窗口。Triggers - AWTK UI, AWTK XML, AWStudio, AWTK Designer, awtk layout, mockup to AWTK, design to XML, coordinate sheet xlsx, 效果图转 AWTK, AWTK 布局, 仪表 UI.
---

# AWTK 布局生成器

把“设计稿 + 切图 + 坐标表”变成 AWTK 工程里可直接运行的 `design/<theme>/ui/*.xml` 和 `design/<theme>/styles/default.xml`，然后用官方 `preview_ui` 预览、截图、与效果图比对，迭代到可交付。

本 skill 的脚本只依赖 Python 标准库（Windows 下用 GDI 截图、PowerShell 转图），不需要 openpyxl/Pillow/pandas。

## 何时使用

- 用户给出 UI 效果图/切图/Excel 坐标表，要求生成 AWTK 界面。
- 用户要求修改现有 AWTK XML 布局、排查“白屏/错位/图片不显示/样式不生效”。
- 用户提到 AWStudio、AWTK Designer、AWTK 1.7.1、`preview_ui`、`design/default/ui`。
- 用户要在 2W 仪表、车机中控、工业 HMI 上还原一个设计稿。

不适用：纯 Web/Android/Qt 界面；只写业务逻辑、不涉及 UI 布局的任务。

## 核心原则

1. **先问身份，再动手。** 不同项目类型（2W 仪表/中控/HMI/通用）的分辨率、字体、配色、控件习惯不同。身份没确认前不要批量生成。
2. **`design_spec.json` 是唯一事实来源。** 效果图、Excel、切图的信息先归一化进 JSON，再由脚本生成 XML。不要一边看 Excel 一边手写 XML。
3. **坐标一律是 LCD 像素。** 设计稿坐标先按 `scale` 换算；原始坐标放 `source.design_rect` 备查。
4. **先校验，再预览。** `validate_ui.py` 能挡住大部分白屏、缺图、样式名错。
5. **必须真预览。** 生成完 XML 必须用官方 `preview_ui` 打开并截图；“看起来应该对”不算完成。
6. **先看 diff 图，再看指标。** 数值只用于定位，不代替人眼确认布局与信息层级。
7. **版本要确认。** AWTK 1.7.1 release 2210 **没有** `self_layout="flex(...)"`；不要生成。用 `children_layout` + 普通 `x/y/w/h`。

## 工作流

### 0. 识别身份与设计语言

先问（一次问清，不要逐条挤牙膏）：

| 问题 | 用途 |
| --- | --- |
| 项目类型：2W 仪表 / 中控 / HMI / 通用窗口？ | 决定控件选型与布局密度 |
| LCD 分辨率与横竖屏？ | 所有坐标的基准 |
| 主题：深色 / 浅色 / 品牌主题？主色、辅色、背景色？ | 生成 styles |
| 字体：默认字体还是品牌字体？字号基准？ | 文本排版 |
| 是否有系统栏（`system_bar` / `system_bar_bottom`）？ | 内容区高度 |
| 目标 AWTK 版本 / SDK 路径？ | 兼容性与预览命令 |
| 交互要求：只看静态，还是要按钮/滑块/页面切换？ | 是否需要事件与动画 |

如果用户已经给了工程，先读 `project.json` 推断 LCD、主题、入口，再问缺的项。

### 1. 收集并归一化输入

需要的输入：

- 效果图：PNG/JPG，记录尺寸、内容区原点、缩放比。
- 切图：`design/<theme>/images/x1`（或 `x2`/`svg`），文件名即资源名。
- 坐标计划书：`.xlsx`，用 `read_xlsx.py` 读取；没有 Excel 就人工测量。
- 工程：`project.json`、现有 `design/<theme>/{ui,styles,images,fonts}`。

把结果写成 `design_spec.json`（结构见下）。细节与 Excel 列映射见 `references/input-formats.md`。

### 2. 生成 `design_spec.json`

最小结构：

```json
{
  "project": { "name": "cluster", "lcd": { "w": 1024, "h": 600 },
               "theme": "default", "dpr": 1 },
  "design": { "file": "mockup.png", "width": 2048, "height": 1200,
              "origin": [0, 0], "scale": 2.0 },
  "screens": [
    { "name": "main", "type": "window", "file": "main.xml",
      "x": 0, "y": 0, "w": 1024, "h": 600, "style": "page",
      "children": [
        { "name": "title", "type": "label", "x": 24, "y": 16, "w": 400, "h": 36,
          "text": "Vehicle Status", "style": "title" }
      ] }
  ]
}
```

- 坐标全部是 LCD 像素。
- 每个控件唯一 `name`；纯装饰容器也要命名。
- 节点字段：`type, name, x, y, w, h, style, text, children_layout, self_layout, floating, attrs{}, inline_style{}, property{}, children[]`。
- `layout: "x,y,w,h"` 是简写。
- 原始设计稿坐标放 `source`，生成器忽略。

模板：`assets/design_spec_template.json`。

### 3. 生成 UI XML 与样式

```bash
python <SKILL_DIR>/scripts/spec_to_ui.py design_spec.json \
    --out-dir design/default/ui --validate
```

- 每个 screen 生成一个 XML；`screen.file`（相对 `--out-dir`，省略时用 `<name>.xml`）决定文件名。
- 生成后检查 `x/y/w/h`、`children_layout`、图片/样式引用。
- 样式**统一追加到** `design/<theme>/styles/default.xml`，用 `style="..."` 引用；AWTK 只自动加载 `styles/default.xml`（窗口专属文件除外），拆成 `button.xml` 等不会生效。模板见 `assets/style_template.xml`。
- 图片资源只写资源名，不带路径/扩展名。

布局语法、容器语义、控件目录见：

- `references/layout-rules.md` —— x/y/w/h、children_layout、self_layout、flex 兼容性。
- `references/widget-catalog.md` —— 控件选型与属性速查。
- `references/style-rules.md` —— 样式文件、状态、颜色、图片绘制类型。

### 4. 校验

```bash
python <SKILL_DIR>/scripts/validate_ui.py design/default/ui/main.xml \
    --project <工程> --theme default --lcd 1024x600
```

检查：XML 结构、重名、布局语法、`children_layout` 键、`self_layout`、内联样式、图片资源、命名样式、`column/row` 缺布局、超出父边界。

- `0 errors` 才能进入预览。
- warnings 要逐条看；`--strict` 可把 warning 当失败。
- 校验通过不代表渲染正确（主题/字体/图片内容仍可能有问题），必须预览。

### 5. 官方预览

AWTK 自带 `preview_ui.exe`，**不需要编译工程**：

```text
<AWTK_ROOT>/bin/preview_ui.exe
```

**关键：UI XML 按路径直接读取，样式/图片/字体则从 `res_root` 按资源管理器规则查找。** 两种构建的**参数风格、窗口标题、资源布局**都不同：

| 构建 | 参数风格 | 窗口标题 | 资源查找路径 | `res_root` 应指向 |
| --- | --- | --- | --- | --- |
| `demos/preview_ui.c`（AWStudio SDK 1.7.1） | 位置参数 `<ui.xml> <w> <h> <res_root> [language] [theme]` | `AWTK Simulator` | `<res_root>/assets/<theme>/raw/{styles,images,fonts,strings}` | 工程的 `res/`（打包产物） |
| `tools/preview_ui.c`（较新） | `key=value`，如 `ui=... lcd_w=... res_root=...` | `awtk_preview` | `<res_root>/<theme>/{styles,images,fonts}` | 工程的 `design/` |

> **最常见的误判**：对旧构建把 `res_root` 指向 `design`。UI 能正常显示、不会报错，但样式/图片/字体全部回退到 AWTK 内置默认值，看起来像“样式不生效”。
> 旧构建需要先跑工程里的 `update_res.py all` 生成 `res/`；没有生成时用 `preview_ui.py --stage-res`，脚本会把 `design/<theme>` 镜像成 `out/preview_res/assets/<theme>/raw`。
> 另外 `.bin` 优先于 `.xml`：改完 `design/.../default.xml` 必须重新生成资源或使用 staging，否则预览读到的还是旧 `.bin`。
> 参数风格传错**不会报错**，只会得到一个 320×1 的空白窗口；用 `preview_ui.py` 可自动识别。

优先用脚本，自动识别构建、选择/生成正确的 `res_root`、等窗口、截图、结束进程：

```bash
python <SKILL_DIR>/scripts/preview_ui.py --project <工程> \
    --ui design/default/ui/main.xml --lcd 1024x600 \
    --screenshot out/preview.png --wait 2 --json
```

- `--dry-run` 先看命令；结果里的 `preview_cli` 和 `res_layout` 说明用了哪套参数、哪种资源根。
- 旧构建默认：`res` 不存在或比 `design` 旧 → 自动 stage 到 `out/preview_res`；否则直接用 `res`。`--stage-res` 强制从 `design` 生成。
- `--update-res` 先运行工程自己的 `scripts/update_res.py all`，再预览打包资源。
- `--keep-open` 保留窗口人工确认。
- 截图失败时先看窗口尺寸：320×1 就是参数风格传错。
- 详细参数、排错、手动截图见 `references/preview-and-compare.md`。

### 6. 与效果图比对并迭代

```bash
python <SKILL_DIR>/scripts/compare_images.py design/mockup.png out/preview.png \
    --out-dir out/compare --overlay --json out/compare/metrics.json
```

输出 `metrics.json`、`diff.png`、`side_by_side.png`（可选 `overlay.png`）。

判定参考：

| 场景 | MAE | diff_ratio |
| --- | --- | --- |
| 像素级 | ≤ 2 | ≤ 1% |
| 可接受 | ≤ 5 | ≤ 5% |
| 需检查 | > 5 | > 5% |

迭代顺序：布局 → 尺寸 → 颜色/样式 → 图片/切图 → 字体。**每轮只改一类**，否则无法归因。

常见差异原因与定位方法见 `references/preview-and-compare.md` 第 4 节。

### 7. 交付

- UI：`design/<theme>/ui/*.xml`
- 样式：`design/<theme>/styles/default.xml`（窗口级皮肤才用 `<窗口名>.xml`）
- 规格：`design_spec.json`
- 证据：`out/preview.png`、`out/compare/{diff,side_by_side,metrics.json}`
- 说明：LCD、主题、字体、缺失资源、估算坐标、已知差异、复现命令。

交付前过一遍 `references/checklist.md`。

## 快速命令索引

| 任务 | 命令 |
| --- | --- |
| 读 Excel | `python scripts/read_xlsx.py coords.xlsx --json coords.json` |
| 读多个 sheet | `python scripts/read_xlsx.py coords.xlsx --list-sheets` |
| 生成 XML | `python scripts/spec_to_ui.py design_spec.json --out-dir design/default/ui` |
| 校验 | `python scripts/validate_ui.py design/default/ui/main.xml --project .` |
| 预览+截图 | `python scripts/preview_ui.py --project . --ui design/default/ui/main.xml --screenshot out/preview.png` |
| 比对 | `python scripts/compare_images.py mockup.png out/preview.png --out-dir out/compare` |

脚本都在本 skill 的 `scripts/` 下；执行时用绝对路径或先进入 skill 目录。所有脚本 `python <script> --help` 可看完整参数。

## 常见坑（按出现频率）

1. **320×1 预览窗口**：`preview_ui` 参数风格传错。用 `preview_ui.py` 自动识别，或手动按位置参数传。
2. **白屏/样式丢失**：`res_root` 布局不对。旧构建（位置参数）要 `<res_root>/assets/<theme>/raw/...`，通常指向工程的 `res`，不是 `design`；新构建才用 `design`。用 `preview_ui.py` 自动处理。
3. **样式全丢**：`theme` 与 `design/<theme>` 不一致；或样式写进了 `styles/button.xml` 这类不会被加载的文件（必须并进 `styles/default.xml`）；或旧的 `styles/default.bin` 抢在 XML 前面。
4. **`column`/`row` 不排布子控件**：它们只是容器，必须写 `children_layout`。
5. **图片不显示**：XML 里写了路径/扩展名；或图片不在 `images/x1`；或大小写不一致。
6. **负 `w/h` 理解错**：`w="-20"` 是“父宽减 20”；负 `x/y` 仍是负坐标。
7. **`gauge_pointer` 的 `value` 是角度**：0=12 点，顺时针为正，不是物理值。
8. **`text_color` / `fg_color` 混用**：文本颜色用 `text_color`。
9. **`round_radius` 对图片背景无效**：图片背景用 9 宫格切图。
10. **`#RRGGBBAA`**：alpha 在最后两位，不是 CSS 的 `#AARRGGBB`。
11. **`y="top:0"` / `x="left:0"`**：AWTK 没有这两个关键字，会被 `atof` 解析成 0；直接写 `0`。
12. **`flex(...)` 不存在于 1.7.1**：确认 SDK 版本；1.7.1 release 2210 不支持。

## 参考与资源

| 文件 | 内容 |
| --- | --- |
| `references/layout-rules.md` | 布局规则、坐标语义、children_layout、self_layout |
| `references/widget-catalog.md` | 控件目录、属性、设计元素 → 控件 |
| `references/style-rules.md` | 样式文件结构、状态、颜色、图片绘制类型 |
| `references/input-formats.md` | 输入清单、测量/缩放、Excel 映射、`design_spec.json` |
| `references/project-structure.md` | AWTK 工程结构、`project.json`、资源命名、`update_res.py` |
| `references/preview-and-compare.md` | 预览工具、两种 CLI、截图、比对、排错 |
| `references/checklist.md` | 各阶段检查清单与验收标准 |
| `references/AWTK开发实践.pdf` | 中文实践资料（辅助，不能直接渲染） |
| `assets/ui_template.xml` | 通用窗口/网格/按钮模板 |
| `assets/style_template.xml` | 深色主题样式模板 |
| `assets/awtk_2w_cluster_template.xml` | 2W 仪表骨架（gauge/image_value/progress_circle） |
| `assets/awtk_2w_cluster_realworld.xml` | 真实 2W 项目导出样例（含旧式 `style:normal:bg.color` 写法，仅参考） |
| `assets/design_spec_template.json` | `design_spec.json` 模板 |

## 完成标准

- `validate_ui.py` 0 errors。
- `preview_ui` 窗口尺寸等于 LCD 尺寸，截图无白屏。
- 主要区域的位置、尺寸、颜色、文字与效果图一致；缺失资源已在说明中列出。
- `side_by_side.png` 已生成并人工看过；`metrics.json` 已记录。
- 用户能按交付说明中的命令自行复现预览。
