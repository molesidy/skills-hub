# AWTK 样式（style）规则

AWTK 的视觉表现由“样式”决定，不是由 XML 控件属性决定。生成界面时，**结构写在 `ui/*.xml`，视觉写在 `styles/default.xml`（窗口专属样式除外）或 inline style**。本文件给出可直接落地的样式写法与常见坑。

## 1. 样式放在哪里

```text
design/<theme>/
├── ui/
│   └── main.xml          # 界面结构
├── styles/
│   └── default.xml       # 样式：所有命名样式都写这里
├── images/
│   ├── x1/               # 1x 切图
│   ├── x2/               # 2x 切图
│   └── svg/              # SVG
└── fonts/
```

AWTK 1.7.1 的样式加载规则（源码 `assets_manager.c` / `window_base.c` / `style_const.c`）：

1. **全局默认样式只有一个文件。** `tk_init_assets()` 启动时找资源名为 `default` 的 STYLE 资源，即 `design/<theme>/styles/default.xml`（或 `.bin`）。所有控件默认从这里取样式。
2. **`.bin` 优先于 `.xml`。** `assets_manager.c` 先试 `default.bin`，再试 `default.xml`。目录里同时存在两者时，改 XML **不会生效**；先删掉旧的 `.bin`，或重新跑 `update_res.py style`。
3. **窗口可以有专属样式文件。** 文件名规则：
   - `window theme="xxx"` → `styles/xxx.xml`；
   - 没写 `theme` → `styles/<窗口 name>.xml`（窗口 `name="main"` 就找 `styles/main.xml`）；
   - 文件不存在就不加载，直接使用全局 `default.xml`。
4. **窗口样式与 default 是“逐条样式回退”，不是文件合并。** 同一条样式在窗口文件里找不到时，才去 `default.xml` 找（`style_const.c`）；两边的 `<style>` 定义不会自动拼在一起。
5. **不要按控件类型拆文件**（`button.xml`、`dialog.xml`…）。这些文件不会被自动加载；AWTK 没有“加载 `styles/` 下所有 XML 并合并”的机制。

推荐做法：**所有样式写进 `styles/default.xml`**。一个文件里可以并列多个控件类型根标签，这是 AWTK 的标准写法：

```xml
<window>
  <style name="default"><normal bg_color="#101418"/></style>
  <style name="page"><normal bg_color="#101418"/></style>
</window>

<label>
  <style name="title" font_size="28" text_color="#E6EDF3"/>
</label>

<button>
  <style name="primary" bg_color="#338FFF" text_color="#FFFFFF" round_radius="8"/>
</button>
```

只有确实需要“整套窗口皮肤”时，才使用窗口专属文件（`styles/<窗口名>.xml` 或 `theme="..."`）。窗口专属文件里没定义的样式仍会回退到 `default.xml`，所以仍建议把公共样式集中在 `default.xml`。

## 2. 样式文件结构

```xml
<button>
  <style name="default" border_color="#a0a0a0" text_color="black">
    <normal  bg_color="#f0f0f0"/>
    <pressed bg_color="#c0c0c0" x_offset="1" y_offset="1"/>
    <over    bg_color="#e0e0e0"/>
    <disable bg_color="gray" text_color="#d0d0d0"/>
  </style>

  <style name="primary" bg_color="#338FFF" text_color="white" round_radius="8">
    <normal  bg_color="#338FFF"/>
    <pressed bg_color="#1F6FD0"/>
  </style>
</button>
```

规则：

1. 根标签是控件类型（`button`、`label`、`window`…）。
2. `<style name="...">` 定义一种命名样式；`name="default"` 是控件默认样式。
3. `<style>` 上的属性是该样式**所有状态**的公共值；状态子标签里的属性覆盖公共值。
4. 状态子标签可以只写差异属性，未写的自动回退到 `normal`。
5. 控件通过 `style="primary"` 选择样式；不写则用 `default`。

## 3. 状态名

来自 `src/base/widget_consts.h`：

| 状态 | 触发条件 |
| --- | --- |
| `normal` | 正常 |
| `pressed` | 按下 |
| `over` | 鼠标悬停 |
| `disable` | 禁用（`enable="false"`） |
| `focused` | 获得焦点 |
| `checked` / `unchecked` | 选中/未选中 |
| `selected` | 选中（image 等） |
| `activated` | 激活 |
| `changed` | 值改变 |
| `empty` / `empty_focus` / `empty_over` | 空值状态 |
| `error` | 错误状态 |
| `normal_of_checked` / `pressed_of_checked` / `over_of_checked` / `disable_of_checked` / `focused_of_checked` | 选中态下的各状态 |
| `normal_of_active` / `pressed_of_active` / `over_of_active` / `disable_of_active` / `focused_of_active` | 激活态下的各状态 |

控件实际会用到哪些状态，看控件的 `*_set_state` 调用；不确定时至少提供 `normal`、`pressed`、`disable`。

## 4. 样式属性

来自 `src/base/style.h`，按用途分组：

### 4.1 颜色与背景

| 属性 | 说明 |
| --- | --- |
| `bg_color` | 背景色，支持纯色和渐变 |
| `fg_color` | 前景色；进度条已完成部分、圆弧进度等使用 |
| `text_color` | 文字颜色 |
| `tips_text_color` | 提示文字颜色（edit 等） |
| `border_color` | 边框颜色 |
| `border_width` | 边框线宽（需 `WITH_VGCANVAS`；普通 LCD 可能不生效） |
| `border` | 边框位置：`left/right/top/bottom/all` 及组合 |
| `bg_image` | 背景图片资源名 |
| `bg_image_draw_type` | 背景图绘制方式 |
| `fg_image` | 前景图片（进度条等） |
| `fg_image_draw_type` | 前景图绘制方式 |
| `clear_bg` | `true` 时用 clear 代替 fill，便于硬件层合成 |
| `selected_bg_color` / `selected_fg_color` / `selected_text_color` | 选中态颜色 |
| `grid_color` / `even_bg_color` / `odd_bg_color` | `grid` 专用 |

### 4.2 文本

| 属性 | 说明 |
| --- | --- |
| `font_name` | 字体名，对应 `design/<theme>/fonts` 中的字体 |
| `font_size` | 字号（像素） |
| `font_style` | `bold`/`italic`/`underline`，逗号分隔；部分版本只部分支持 |
| `text_align_h` | `left`/`center`/`right` |
| `text_align_v` | `top`/`middle`/`bottom` |
| `highlight_font_name` / `highlight_font_size` / `highlight_text_color` | 高亮文本（rich_text 等） |

### 4.3 图标与图片

| 属性 | 说明 |
| --- | --- |
| `icon` | 图标资源名；按钮图标、check_button 勾选图标等 |
| `active_icon` | 激活态图标（slide_view 指示器等） |
| `icon_at` | 图标相对文字的位置：`left/right/top/bottom/center` |
| `spacer` | 图标与文字间距 |
| `margin` / `margin_left` / `margin_right` / `margin_top` / `margin_bottom` | 内容边距（只影响 icon/text，不影响子控件） |
| `x_offset` / `y_offset` | 绘制偏移，按下态常用 `1` 模拟下沉 |

### 4.4 圆角与布局

| 属性 | 说明 |
| --- | --- |
| `round_radius` | 统一圆角 |
| `round_radius_top_left` / `_top_right` / `_bottom_left` / `_bottom_right` | 单角圆角 |
| `children_layout` | 在样式里预设子布局 |
| `self_layout` | 在样式里预设自身布局 |
| `focusable` | 是否可获焦 |
| `feedback` | 是否有点击反馈 |

> `round_radius` 对纯色背景和边框有效；对 `bg_image` 九宫格背景无效，圆角应做进切图。

## 5. 颜色写法

```xml
<normal bg_color="#338FFF"/>
<normal bg_color="#338FFFCC"/>            <!-- RGBA：alpha=0xCC -->
<normal bg_color="rgb(51,143,255)"/>
<normal bg_color="rgba(51,143,255,0.8)"/>
<normal bg_color="steelblue"/>
<normal bg_color="linear-gradient(180deg, #6AB2FF, #0D81FF)"/>
```

- `#RRGGBB` 不透明；`#RRGGBBAA` 最后两位是 alpha（`00` 全透明，`FF` 不透明）。
- `rgba(R,G,B,A)` 的 A 是 0～1 的小数。
- 英文色名可用，但**不要依赖冷门色名**；交付时以十六进制为准。
- 渐变支持 `linear-gradient(...)` 和 `radial-gradient(...)`；非 vgcanvas 渲染路径通常只高效支持 180°（从上到下）。能用纯色就不要用渐变。
- 半透明填充比不透明慢，嵌入式目标上谨慎使用。

## 6. 图片样式

### 6.1 bg_image vs icon

| 属性 | 用途 |
| --- | --- |
| `bg_image` | 控件背景，铺满整个控件 |
| `fg_image` | 前景（进度条已完成段） |
| `icon` | 小图标，配合文字布局 |

```xml
<!-- 九宫格按钮背景 -->
<style name="default" bg_image="btn_bg" bg_image_draw_type="patch9" text_color="white"/>

<!-- 图标按钮 -->
<style name="icon" icon="play_n" text_color="blue">
  <normal icon="play_n"/>
  <pressed icon="play_p" x_offset="1" y_offset="1"/>
</style>
```

### 6.2 draw_type 选择

| 场景 | draw_type |
| --- | --- |
| 按钮/卡片背景（可拉伸） | `patch9`（九宫格）或 `patch3_x`/`patch3_y` |
| 小图标固定大小 | `default` 或 `center` |
| 需要随控件缩放 | `scale_auto`（保持比例）或 `scale`（拉伸） |
| 只缩小不放大 | `scale_down` |
| 纹理平铺 | `repeat` / `repeat_x` / `repeat_y` / `fill` |

> 九宫格图必须在文件名或资源中保留可拉伸边界；切图时四角不要有内容。`patch9` 需要图片本身带有 9 宫格信息（AWTK 按图片尺寸均分，具体以 `image_draw_type.md` 为准）。

## 7. inline style

只影响单个控件时，直接在 UI XML 上写 `style.状态.属性`：

```xml
<label text="Title" style.font_size="24" style.text_color="green"/>
<button text="OK" style.normal.bg_color="#338FFF"
        style.pressed.bg_color="#1F6FD0"
        style.normal.round_radius="8"/>
```

- `style.font_size` 省略状态 = `normal`。
- `style.focused.text_color="red"` 只改焦点态。
- inline style 优先级高于命名样式；适合少量微调，**不要把所有样式都写成 inline**，否则无法复用、无法统一改主题。
- inline style 会创建 mutable style，比只读样式略慢；大量控件重复写同一组 inline 属性时应抽成命名样式。

## 8. 从设计稿提取样式

生成样式前，先把设计稿中的视觉规则整理成表（可写入 `design_spec.json`）：

| 设计稿信息 | 映射到 |
| --- | --- |
| 主色/强调色/警告色 | `bg_color`、`text_color`、`fg_color` |
| 圆角半径 | `round_radius` 或切图 |
| 边框颜色/粗细 | `border_color`、`border_width` |
| 字号/字重/行高 | `font_size`、`font_name` |
| 按钮三态 | `normal`/`pressed`/`disable` |
| 卡片/面板背景 | `bg_image` + `patch9` |
| 图标 | `icon` 或独立 `image` 控件 |

约定：

- 颜色统一用 `#RRGGBB` 大写或小写**保持一致**；不要同一文件混用 `#fff` 和 `#FFFFFF`。
- 字号用整数像素；AWTK 不做 pt→px 换算。
- 圆角不要超过控件短边的一半，否则部分渲染后端会画成胶囊或异常。
- 设计稿的阴影 AWTK 不直接支持；用带阴影的切图（`bg_image`）实现。

## 9. 常用样式模板

### 9.1 深色仪表主题

```xml
<window>
  <style name="default">
    <normal bg_color="#101418"/>
  </style>
</window>

<label>
  <style name="default" text_color="#E6EDF3" font_size="18">
    <normal text_color="#E6EDF3"/>
    <disable text_color="#5A6672"/>
  </style>
  <style name="unit" text_color="#8A97A5" font_size="12"/>
</label>

<button>
  <style name="default" bg_color="#1E2630" text_color="#E6EDF3" round_radius="6"
         border_color="#2E3A46" border_width="1">
    <normal  bg_color="#1E2630"/>
    <pressed bg_color="#2A3542" x_offset="1" y_offset="1"/>
    <disable bg_color="#161C22" text_color="#5A6672"/>
  </style>
</button>
```

### 9.2 浅色 HMI 主题

```xml
<window>
  <style name="default">
    <normal bg_color="#F5F7FA"/>
  </style>
</window>

<button>
  <style name="primary" bg_color="#338FFF" text_color="#FFFFFF" round_radius="8">
    <normal  bg_color="#338FFF"/>
    <pressed bg_color="#1F6FD0"/>
    <disable bg_color="#B8C4D0" text_color="#FFFFFF"/>
  </style>
  <style name="secondary" bg_color="#FFFFFF" text_color="#1F2D3D"
         border_color="#C9D3DF" border_width="1" round_radius="8">
    <normal  bg_color="#FFFFFF"/>
    <pressed bg_color="#E9EEF5"/>
  </style>
</button>
```

### 9.3 进度条/圆弧

```xml
<progress_bar>
  <style name="default" bg_color="#2A3542" fg_color="#338FFF" round_radius="4">
    <normal bg_color="#2A3542" fg_color="#338FFF"/>
  </style>
</progress_bar>

<progress_circle>
  <style name="default" bg_color="#2A3542" fg_color="#338FFF" text_color="#E6EDF3">
    <normal bg_color="#2A3542" fg_color="#338FFF"/>
  </style>
</progress_circle>
```

> `progress_circle` 在 1.7.1 中 `line_width`、`start_angle` 是控件属性，不是样式属性；颜色仍走 `fg_color`/`bg_color`。

## 10. 常见坑

- **样式写进 `styles/button.xml` 没生效**：AWTK 只自动加载 `styles/default.xml`（以及窗口专属文件）。把样式并进 `default.xml`。
- **`styles/default.bin` 抢在 `default.xml` 前面**：改 XML 后预览仍是旧样式，先删除或重新生成 `.bin`。
- **窗口名撞上样式文件名**：窗口 `name="main"` 会尝试加载 `styles/main.xml`。如果这个文件存在但你并不想让它当窗口主题，会得到意外效果；要么删掉，要么明确用它。
- **`text_color` 写成 `fg_color`**：文字不变色。文字用 `text_color`；进度条已完成部分才用 `fg_color`。
- **默认样式名写错**：`style="default"` 可省略；自定义样式必须与 `<style name="...">` 完全一致。
- **状态回退**：只写 `pressed` 不写 `normal` 时，正常态可能没有背景。至少写 `normal`。
- **`round_radius` 对图片背景无效**：圆角做进切图，或用纯色 + `round_radius`。
- **`border_width` 在普通 LCD 上不生效**：需要 vgcanvas 后端；嵌入式目标优先用切图边框或 `border_color` + 1px 图片。
- **字体名不存在**：`font_name` 必须是工程 `fonts` 中已加载的字体名，否则回退默认字体，字号行高会变。
- **inline style 写错状态名**：`style.hover.xxx` 不存在，正确是 `style.over.xxx`。
- **样式文件根标签写错**：根标签必须是控件类型；写在 `<styles>` 之类的包裹标签里不会被识别。
- **预览时资源根不对**：`res_root` 指向哪里取决于 `preview_ui` 构建。旧构建（位置参数）从 `<res_root>/assets/<theme>/raw/styles` 读样式，应指向 `res`；新构建（key=value）从 `<res_root>/<theme>/styles` 读，才指向 `design`。指错时不会报错，样式会静默回退到 AWTK 内置默认值。
- **颜色 alpha 顺序**：AWTK 是 `#RRGGBBAA`，不是 `#AARRGGBB`。
- **渐变角度**：`linear-gradient(90deg, ...)` 在部分后端不支持；横向渐变请用切图。
