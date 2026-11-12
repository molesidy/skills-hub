---
name: awtk-layout-creator
description: 把 UI 效果图、切图资源和坐标计划书（Excel）转换成可运行的 AWTK UI XML 与样式，并用 AWTK 官方 preview_ui 预览、截图、与效果图逐像素比对迭代。内置五条硬性约束：图片控件默认 draw_type="default"、禁止改切图文件名、缺图不放/错图错坐标照放并写同名 md、白天黑夜双模式输出两个 XML、同模块控件可用 view 分组。内置上下文压缩：大 xlsx/XML/日志/切图目录先用 context_digest.py 抽取摘要，按需懒加载参考文件，用 out/context/capsule.md 在上下文重置后恢复。适用于 AWTK / AWStudio / AWTK Designer 工程，支持 2W 仪表、中控、HMI、通用窗口。Triggers - AWTK UI, AWTK XML, AWStudio, AWTK Designer, awtk layout, mockup to AWTK, design to XML, coordinate sheet xlsx, draw_type, day night theme, 效果图转 AWTK, AWTK 布局, 仪表 UI, 上下文压缩, token 节省, 大 Excel 摘要, 日志摘要, context digest, token budget, lazy load.
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

## 硬性约束（最高优先级，必须逐条遵守）

完整说明与示例见 `references/constraints.md`。与“经验做法”冲突时以本节为准。

1. **`draw_type="default"` 是默认值。** 所有图片类控件（`image`、`image_value`、`image_animation` 等）默认显式写 `draw_type="default"`；只有特殊控件/特殊用途（整屏拉伸、九宫格、平铺等）才允许换其他 `draw_type`，且必须在 `design_spec.json` 里显式写出并说明原因。
2. **禁止改切图文件名。** 提供的切图文件名就是资源名；不重命名、不改大小写、不替换空格/连字符/中文。可以复制到主题目录，但文件名保持原样。名字不符合 AWTK 习惯时只记录到 `.md`，由用户决定是否改名。
3. **缺图不放，错图/错坐标照放并写 `.md`。** 切图缺失的控件直接从 XML 中省略，不用占位图/纯色块/抠图代替；切图疑似错误或坐标疑似错误的控件仍按计划书原值放置，并在 XML 旁生成同名 `.md` 标记。**禁止自行曲解计划书、禁止自行微调坐标。**
4. **白天/黑夜双模式输出两个 XML。** 同一主题、同一界面识别到两种模式时，必须生成 `_day.xml` 和 `_night.xml` 两个文件，不能用一个 XML 代替。
5. **同模块切图可用 `<view>` 分组。** 只有计划书/切图明确属于同一模块的控件才分组；计划书给了容器矩形就直接用（如用户示例的 `53,54,59,26`），没给才用组内最小外接矩形；子控件坐标换算为相对容器坐标，**分组前后绝对坐标必须完全不变**。容器可以比紧贴子控件的包围盒略大（含内边距），不得为了“最小”去缩小计划书给定的容器。

## Token 与上下文纪律

完整说明见 `references/context-and-tokens.md`（输入大或上下文紧张时再读）。三条规则：

1. **按需加载**：默认只读 `SKILL.md` + `constraints.md`；其他 reference 在需要该能力时读一份，不要预读全部。`references/AWTK开发实践.pdf`（9.4MB）永不整份读。
2. **先摘要后精读**：大输入先跑 `scripts/context_digest.py`，需要精确值再 `--screen` / `--grep` 取局部。
3. **压缩只抽取不改写**：摘要只做计数/分组/采样/截断；`name/x/y/w/h/image/style/text` 必须逐字保留，坐标只从原始资料或 `design_spec.json` 取。

触发压缩的阈值：xlsx >100 行或 >20 列、XML >300 控件、切图 >150 文件、日志 >200 行、`design_spec.json` >100 控件。单个屏幕无论大小都用 `--screen` 只取该屏。

| 层级 | 何时加载 |
| --- | --- |
| Tier 0（每次） | 本文件 + `references/constraints.md` |
| Tier 1（按步骤） | 当前步骤相关的一份 reference（写容器→layout-rules；选控件→widget-catalog；写样式→style-rules；归一化→input-formats；预览→preview-and-compare；交付→checklist；大输入→context-and-tokens） |
| Tier 2（需要骨架） | `assets/*` 模板 |
| 禁止 | `references/AWTK开发实践.pdf` 整份；`scripts/*.py` 整份（运行，不阅读） |

文件大小与 token 估算不要写死在文档里：`context_digest.py --index` 现场给出。

**上下文胶囊**：大项目在 `out/context/capsule.md` 保存结论（屏幕清单、已确认决策、待确认项、证据路径），不保存坐标表/日志/切图清单。模板 `assets/context_capsule_template.md`。每完成一个屏幕、每次确认或推翻假设、每次上下文可能被压缩前更新。

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

### 0.5 盘点输入规模（大项目必做）

```bash
python <SKILL_DIR>/scripts/context_digest.py --index
python <SKILL_DIR>/scripts/context_digest.py coords.xlsx --top 8
python <SKILL_DIR>/scripts/context_digest.py design/default/images --top 8
```

- 只看规模与异常，不读原始内容。超过阈值的输入后续一律先摘要。
- 把屏幕清单、模式、切图命名规则写进 `out/context/capsule.md`（模板 `assets/context_capsule_template.md`）。
- 小项目（单屏、<100 行 xlsx、<150 张切图）可跳过摘要，直接进入下一步。

### 1. 收集并归一化输入

需要的输入：

- 效果图：PNG/JPG，记录尺寸、内容区原点、缩放比。
- 切图：`design/<theme>/images/x1`（或 `x2`/`svg`），文件名即资源名。
- 坐标计划书：`.xlsx`，大表先用 `context_digest.py` 摘要，**逐屏**用 `--screen <name> --rows 40` 取明细；小表才直接 `read_xlsx.py`。没有 Excel 就人工测量。
- 工程：`project.json`、现有 `design/<theme>/{ui,styles,images,fonts}`。

把结果写成 `design_spec.json`（结构见下）。细节与 Excel 列映射见 `references/input-formats.md`。

**一次只归一化一个屏幕**：读该屏摘要 → 写该屏 `children` → 下一屏。不要把整本 xlsx 展开成 JSON 再贴进上下文，也不要每屏重复读整表。每屏完成后更新胶囊。

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
- **双模式**：screen 写 `"modes": ["day", "night"]`，生成器输出 `<stem>_day.xml` / `<stem>_night.xml`；节点用 `by_mode: { "day": {...}, "night": {...} }` 覆盖按模式不同的字段（如 `attrs.image`）。
- **缺失切图**：节点写 `"missing": true` + `"missing_reason": "..."`，生成器跳过该节点及子树。
- **错误切图/坐标**：节点写 `"review_kind": "wrong_image" | "wrong_coord"` + `"review_note": "..."`，控件照常生成，并在同名 `.md` 中登记。
- 屏幕级/规格级说明写 `review_notes`；缺失列表也可写顶层 `missing_images`。
- `draw_type` 不写时，生成器会给图片类控件自动补 `draw_type="default"`；显式写的特殊值保持原值。

模板：`assets/design_spec_template.json`。

### 3. 生成 UI XML 与样式

```bash
python <SKILL_DIR>/scripts/spec_to_ui.py design_spec.json \
    --out-dir design/default/ui --validate
```

- 每个 screen 生成一个 XML；`screen.file`（相对 `--out-dir`，省略时用 `<name>.xml`）决定文件名。
- 名字带 `modes` 时，每个模式生成一个 XML：`main.xml` → `main_day.xml`、`main_night.xml`；也可写 `main_{mode}.xml`。screen 没写 `modes` 但节点用了 `by_mode` 时，生成器会按 `by_mode` 的键自动识别模式，同样输出多个 XML。
- 有 `missing` / `review_note` / `review_notes` / `missing_images` 时，会在每个 XML 旁生成同名 `.md`（`--no-notes` 可关闭）。**这是硬性要求，不要省略。**
- 图片类控件未写 `draw_type` 时自动补 `draw_type="default"`；不要手动改成 `scale` 等值，除非确属特殊控件。
- **坐标原样写入**：生成器不做任何缩放、取整或“视觉微调”。分组只改变坐标参考系，不改变绝对位置。
- 生成后检查 `x/y/w/h`、`children_layout`、图片/样式引用。
- 样式**统一追加到** `design/<theme>/styles/default.xml`，用 `style="..."` 引用；AWTK 只自动加载 `styles/default.xml`（窗口专属文件除外），拆成 `button.xml` 等不会生效。模板见 `assets/style_template.xml`。
- 图片资源只写资源名，不带路径/扩展名；**资源名必须等于原始切图文件名主干，不得改名**。

布局语法、容器语义、控件目录见：

- `references/layout-rules.md` —— x/y/w/h、children_layout、self_layout、flex 兼容性。
- `references/widget-catalog.md` —— 控件选型与属性速查。
- `references/style-rules.md` —— 样式文件、状态、颜色、图片绘制类型。

### 4. 校验

```bash
python <SKILL_DIR>/scripts/validate_ui.py design/default/ui/main_day.xml \
    --project <工程> --theme default --lcd 1024x600 --strict-constraints
```

检查：XML 结构、重名、布局语法、`children_layout` 键、`self_layout`、内联样式、图片资源、命名样式、`column/row` 缺布局、超出父边界、图片控件 `draw_type`。

- `0 errors` 才能进入预览。
- `--strict-constraints` 把“图片控件缺 `draw_type`”等约束问题升为 error；交付前必须用它跑一遍。
- 双模式界面要对 `_day.xml` 和 `_night.xml` 各跑一遍；单模式用实际文件名。
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
# 双模式界面：两个 XML 分别预览、分别截图
python <SKILL_DIR>/scripts/preview_ui.py --project <工程> \
    --ui design/default/ui/main_day.xml --lcd 1024x600 \
    --screenshot out/preview_day.png --wait 2 --json
python <SKILL_DIR>/scripts/preview_ui.py --project <工程> \
    --ui design/default/ui/main_night.xml --lcd 1024x600 \
    --screenshot out/preview_night.png --wait 2 --json
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

- UI：`design/<theme>/ui/*.xml`（双模式界面必须同时交付 `*_day.xml` 与 `*_night.xml`）
- 标注：每个有缺失/待确认项的 XML 旁的同名 `.md`（`main_day.md` 等）
- 样式：`design/<theme>/styles/default.xml`（窗口级皮肤才用 `<窗口名>.xml`）
- 规格：`design_spec.json`
- 证据：`out/preview.png`、`out/compare/{diff,side_by_side,metrics.json}`
- 说明：LCD、主题、字体、未改名切图的原始文件名、缺失资源、错误切图/坐标的待确认项、已知差异、复现命令。

交付前过一遍 `references/constraints.md` 的五条自检和 `references/checklist.md`。

## 快速命令索引

| 任务 | 命令 |
| --- | --- |
| 看 skill 文件规模/加载建议 | `python scripts/context_digest.py --index` |
| 大 Excel 摘要 | `python scripts/context_digest.py coords.xlsx --top 12` |
| 单屏明细 | `python scripts/context_digest.py coords.xlsx --screen main --rows 40` |
| 按关键字定位控件 | `python scripts/context_digest.py coords.xlsx --grep temp` |
| XML 体检 | `python scripts/context_digest.py design/default/ui/main_day.xml` |
| spec 摘要 + 胶囊草稿 | `python scripts/context_digest.py design_spec.json --out out/context/capsule.md` |
| 日志摘要 | `python scripts/context_digest.py build.log --budget 3000` |
| 切图目录摘要 | `python scripts/context_digest.py design/default/images --top 12` |
| 读 Excel（小表） | `python scripts/read_xlsx.py coords.xlsx --json coords.json` |
| 读多个 sheet | `python scripts/read_xlsx.py coords.xlsx --list-sheets` |
| 生成 XML | `python scripts/spec_to_ui.py design_spec.json --out-dir design/default/ui` |
| 生成双模式 XML | `python scripts/spec_to_ui.py design_spec.json --out-dir design/default/ui --modes day,night` |
| 校验 | `python scripts/validate_ui.py design/default/ui/main_day.xml --project . --strict-constraints` |
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
13. **图片控件漏写 `draw_type`**：违反约束 1。生成器会自动补 `default`；手写 XML 要用 `--strict-constraints` 校验。
14. **改了切图文件名**：违反约束 2。XML 的 `image` 必须等于原始文件名主干；名字不规范只记录、不改名。
15. **缺图用了占位图/抠图**：违反约束 3。缺图控件必须省略，并在 `.md` 中列出；错图/错坐标才照放并标记。
16. **白天/黑夜只写一个 XML**：违反约束 4。双模式必须输出 `_day.xml` 与 `_night.xml` 两个文件。
17. **为了“对齐”微调坐标**：违反约束 3。坐标必须用计划书原值；`view` 分组只做坐标系换算，绝对位置不变。
18. **把整本 xlsx / 整份 XML / 整个切图目录倾倒进上下文**：token 爆炸且淹没关键信息。先 `context_digest.py`，再 `--screen` / `--grep` 取局部。
19. **用模型“总结”坐标或资源名**：会漂移。摘要只抽取，`x/y/w/h/image/name` 必须逐字来自原始资料或 `design_spec.json`。
20. **一次性预读所有 reference / 整份 PDF**：`AWTK开发实践.pdf` 只按页/关键词读；reference 只读当前步骤需要的一份。
21. **上下文重置后重新读全部原始资料**：先读 `out/context/capsule.md`，再 `context_digest.py design_spec.json`，最后只取当前屏幕。

## 参考与资源

| 文件 | 内容 |
| --- | --- |
| `references/constraints.md` | **五条硬性约束**：draw_type、切图改名、缺图/错图、双模式、view 分组 |
| `references/context-and-tokens.md` | **Token 与上下文压缩**：懒加载、摘要阈值、胶囊、逐屏循环、重置恢复 |
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
| `assets/context_capsule_template.md` | 上下文胶囊模板（`out/context/capsule.md`） |

## 完成标准

- `validate_ui.py --strict-constraints` 0 errors。
- 所有图片控件都有 `draw_type`，默认值为 `default`；非默认值有记录。
- 没有切图被改名；XML 资源名 = 原始文件名主干。
- 缺失切图未出现在 XML 中；错误切图/错误坐标已写入同名 `.md`。
- 双模式界面已输出两个 XML（`_day.xml` / `_night.xml`）。
- `preview_ui` 窗口尺寸等于 LCD 尺寸，截图无白屏。
- 主要区域的位置、尺寸、颜色、文字与效果图一致；缺失资源已在说明中列出。
- `side_by_side.png` 已生成并人工看过；`metrics.json` 已记录。
- 用户能按交付说明中的命令自行复现预览。
- 大输入（超阈值）已用 `context_digest.py` 摘要后再归一化；上下文里没有整本 xlsx/整份日志/整份 PDF。
- `out/context/capsule.md` 已更新（屏幕状态、已确认决策、待确认项、下一步），可用于上下文重置后继续。
