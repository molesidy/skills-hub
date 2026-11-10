# AWTK 控件速查表

本表按“设计稿里长什么样”来选控件，而不是按 AWTK 的源码目录。属性只列生成 XML 时最常用、最容易写错的部分；未列出的属性以本机 SDK 的 `src/widgets/*.h`、`src/ext_widgets/**/*.h` 为准。

> 版本基线：AWStudio 自带 AWTK SDK 1.7.1（release 2210）。`src/ext_widgets` 下的控件默认已编入 SDK；若目标工程裁剪过组件，先在 `<AWTK_ROOT>` 中确认控件注册文件存在。

## 1. 窗口与容器

| 控件 | 用途 | 关键属性 |
| --- | --- | --- |
| `window` | 普通页面/全屏窗口 | `name`、`x/y/w/h`、`style`、`anim_hint`、`fullscreen` |
| `dialog` | 模态对话框 | 同 `window`，通常 `x="c" y="m"` |
| `popup` | 轻量弹层 | 需要手动定位，常配 `floating` |
| `view` | 最常用的分组容器，默认无样式无布局 | `x/y/w/h`、`children_layout` |
| `clip_view` | 超出部分裁剪 | 同 `view`，子控件超出边界会被裁剪 |
| `scroll_view` | 可滚动容器 | 子控件总高度超过自身时滚动 |
| `list_view` / `list_view_h` | 列表容器，配合 `scroll_view` 使用 | `item_height`、`default_item_height` |
| `list_item` | 列表项容器 | 放在 `list_view` 的 `scroll_view` 下 |
| `grid` | 表格/列宽不均的网格 | `rows`、`columns_definition`、`show_grid` |
| `column` / `row` | 语义化竖排/横排容器 | **本身不会布局子控件**，必须写 `children_layout` |
| `group_box` | 带标题的边框分组 | `title` |
| `tab_control` | 选项卡整体 | 内含 `pages` + `tab_button_group` |
| `pages` | 多页面容器 | `active` / `value` 指定当前页索引 |
| `slide_view` | 左右/上下滑动翻页 | `vertical`、`loop`、`auto_play`、`anim_hint` |
| `overlay` | 覆盖层（悬浮于主窗口） | 常用于 toast、遮罩 |

### 1.1 window / dialog

```xml
<window name="main" x="0" y="0" w="800" h="480" style="default">
  ...
</window>

<dialog name="confirm" x="c" y="m" w="360" h="200" style="default">
  ...
</dialog>
```

- 窗口的 `w/h` 在嵌入式固定屏上通常等于 LCD 尺寸；省略时由窗口管理器决定。
- `fullscreen="true"` 用于全屏窗口（`image_animation.xml` 等示例中可见）。
- `anim_hint` 用于窗口打开/关闭动画，如 `htranslate`、`vtranslate`、`fade`；生成静态界面时可以省略。
- `dialog` 的进出口动画和模态行为由框架处理；布局与 `window` 相同。

### 1.2 column / row 的坑

```xml
<!-- 错误：子控件不会被排列 -->
<column x="0" y="0" w="200" h="300">
  <button text="A"/>
  <button text="B"/>
</column>

<!-- 正确：显式 children_layout -->
<column x="0" y="0" w="200" h="300" children_layout="default(r=0,c=1,s=8,m=8)">
  <button text="A" h="40"/>
  <button text="B" h="40"/>
</column>
```

`column`/`row` 只是“语义标签 + 默认样式”的容器，源码中不带任何子布局。需要排列时永远显式写 `children_layout`。

## 2. 文本与按钮

| 控件 | 用途 | 关键属性 |
| --- | --- | --- |
| `label` | 单行/多行文本 | `text`、`text_align_h/v`、`line_wrap`、`word_wrap`、`ellipses`、`max_w`、`length` |
| `button` | 普通按钮 | `text`、`enable_long_press`、`repeat`、`enable_preview` |
| `check_button` | 复选/单选 | `value`、`radio`、`indeterminate` |
| `radio_button` | 单选按钮 | `value`；同组互斥由父容器或代码保证 |
| `tab_button` | 选项卡按钮 | `value`、`icon`、`load_ui`、`max_w` |
| `rich_text` | 富文本（可内嵌图片/字体标签） | 文本放 `<property name="text"><![CDATA[...]]></property>` |
| `scroll_label` | 跑马灯文本 | `text`、`loop`、`duration` |
| `mledit` | 多行编辑框 | `text`、`tips`、`max_lines`、`max_chars`、`wrap_word`、`readonly` |

### 2.1 label

```xml
<label x="20" y="10" w="200" h="30" text="Hello"
       text_align_h="left" text_align_v="middle"/>
```

- `text_align_h`：`left` / `center` / `right`。
- `text_align_v`：`top` / `middle` / `bottom`。
- `line_wrap="true"` 按宽度换行；`word_wrap="true"` 按单词换行；`ellipses="true"` 超长显示省略号。
- 字体、字号、颜色通过 style 控制，不是 XML 属性（可用内联 `style.normal.font_size="16"`）。
- 文本中的 `&`、`<`、`>` 必须转义；复杂内容用 `property` + CDATA。

### 2.2 button

```xml
<button name="ok" x="c" y="bottom:20" w="120" h="40" text="OK"/>
```

- 按钮文字垂直居中，默认单行；需要多行时改用 `label` + 透明按钮，或 `rich_text`。
- `enable_long_press="true"` + `long_press_time="1000"` 可做长按。
- `repeat="100"` 让按住时重复触发（数值为重复间隔 ms）。
- 按钮的背景、圆角、按下态全部由 style 的 `normal/pressed/over/disable` 状态控制。

### 2.3 check_button / radio_button

```xml
<check_button name="cb" x="20" y="100" w="120" h="30" text="Enable" value="true"/>
<radio_button name="r1" x="20" y="140" w="120" h="30" text="Option A" value="true"/>
<radio_button name="r2" x="20" y="180" w="120" h="30" text="Option B"/>
```

- `radio="true"` 的 `check_button` 与 `radio_button` 等价。
- 选中态样式用 `normal_of_checked`、`pressed_of_checked` 等状态。
- 图标位置用 style 的 `icon_at`（`left`/`right`/`top`/`bottom`）。

## 3. 图片与指示器

| 控件 | 用途 | 关键属性 |
| --- | --- | --- |
| `image` | 静态图片 | `image`、`draw_type`、`rotation`、`scale_x`、`scale_y`、`anchor_x`、`anchor_y` |
| `svg` / `svg_image` | SVG 矢量图 | `image`（svg 资源名） |
| `gif` / `gif_image` | GIF 动图 | `image`、`running`、`loop` |
| `image_animation` | 序列帧动画 | `image`、`start_index`、`end_index`、`sequence`、`interval`、`auto_play`、`loop`、`format` |
| `image_value` | 数字/状态图（每位一张图） | `image`、`format`、`value`、`min`、`max` |
| `progress_bar` | 条形进度 | `value`、`max`、`vertical`、`show_text`、`format`、`reverse` |
| `progress_circle` | 环形进度/圆弧仪表 | `value`、`max`、`start_angle`、`line_width`、`line_cap`、`counter_clock_wise`、`show_text`、`format` |
| `slider` | 滑块 | `value`、`min`、`max`、`step`、`vertical`、`bar_size`、`dragger_size` |
| `switch` | 开关 | `value`、`max_xoffset_ratio` |
| `spin_box` | 数值加减框 | `value`、`min`、`max`、`step`、`button_position` |
| `combo_box` | 下拉框 | `options`、`selected_index`、`item_height`、`open_window` |
| `text_selector` | 滚轮选择器 | `options`、`visible_nr`、`selected_index`、`loop_options` |

### 3.1 image 与 draw_type

```xml
<image x="20" y="20" w="100" h="100" image="logo" draw_type="default"/>
```

`draw_type` 常用值（来自 `src/base/bitmap.h`）：

| 值 | 行为 |
| --- | --- |
| `default` | 原图大小，不缩放 |
| `center` | 居中，不缩放 |
| `icon` | 居中，按控件大小缩放（保持比例） |
| `scale` | 拉伸填满控件 |
| `scale_auto` | 按比例缩放并填满 |
| `scale_down` | 只缩小不放大 |
| `scale_w` / `scale_h` | 按宽/高缩放 |
| `fill` | 平铺填满 |
| `repeat` / `repeat_x` / `repeat_y` | 重复平铺 |
| `patch9` | 九宫格拉伸（按钮背景常用） |
| `patch3_x` / `patch3_y` | 三宫格拉伸 |

- XML 中 `image="earth"` 不带目录和扩展名；实际资源在 `design/<theme>/images/x1/earth.png` 等密度目录。
- 需要旋转的图（指针、表盘）优先用 SVG，避免位图旋转锯齿。
- `rotation` 单位是**弧度**，不是角度；XML 里一般不用它，仪表用 `gauge_pointer`。

### 3.2 image_animation

```xml
<image_animation name="loading" x="c" y="m" w="64" h="64"
                 image="loading_" start_index="1" end_index="12"
                 interval="80" auto_play="true" loop="true"/>
```

- 资源命名：`loading_1`、`loading_2` …… `loading_12`。
- `format="%s%02d"` 用于两位数编号。
- `sequence` 可指定播放顺序，如 `sequence="1,2,3,4"`。
- `interval` 是每帧间隔 ms；`delay` 是开始前延迟 ms。

### 3.3 image_value

```xml
<image_value name="speed" x="c" y="bottom:40" w="180" h="56"
             image="num_" format="%03d" value="0"/>
```

- `image` 是前缀，不是单张图；数字 3 会找 `num_3`。
- `format` 决定位数和符号，如 `%03d`、`%02.2f`、`+%d`。
- 负号和小数点也需要对应图片（`num_-`、`num_.`），否则显示不出来。
- 每位数字图必须等高，控件高度按最高位图设置。

### 3.4 progress_bar

```xml
<progress_bar name="fuel" x="40" y="400" w="300" h="16"
              value="60" max="100" show_text="true" format="%d%%"/>
```

- 水平默认从左到右；`reverse="true"` 反向。
- `vertical="true"` 垂直进度，宽高互换。
- 进度条颜色/背景由 style 的 `normal` 状态和 `fg_image`/`bg_image` 控制。

### 3.5 progress_circle

```xml
<progress_circle name="rpm" x="right:40" y="90" w="300" h="300"
                 max="8000" value="0" start_angle="135"
                 line_width="12" line_cap="round" show_text="true"/>
```

- `start_angle` 单位度；0 度在 3 点钟方向，顺时针为正。
- `counter_clock_wise="true"` 逆时针增长。
- `line_cap`：`butt` / `round` / `square`。
- 圆环颜色用 style 的 `fg_color`（进度）和 `bg_color`（底环）；`style="image"` 时用图片。
- 需要“刻度 + 指针”时用 `gauge` + `gauge_pointer`，不要用 `progress_circle` 硬凑。

### 3.6 slider / switch / spin_box

```xml
<slider name="volume" x="40" y="200" w="300" h="24" value="50" min="0" max="100"/>
<switch name="power" x="40" y="240" w="60" h="30" value="true"/>
<spin_box name="temp" x="40" y="280" w="120" h="32" value="22" min="16" max="30" step="1"/>
```

- `slider` 的滑块图片由 style 的 `icon` 指定；`bar_size` 是轨道粗细。
- `switch` 本质是 `slider` 的封装，左右图标用 style 的 `icon`/`active_icon`。
- `spin_box` 的加减按钮位置由 `button_position` 控制（`left`/`right`/`both`）。

### 3.7 combo_box / text_selector

```xml
<combo_box name="city" x="40" y="320" w="200" h="32" options="北京;上海;广州" selected_index="0"/>
<text_selector name="hour" x="40" y="360" w="120" h="120" options="0-23-%02d" visible_nr="5"/>
```

- `options` 用 `;` 分隔；`text_selector` 支持 `起-止-格式` 的区间写法。
- `combo_box` 也可用子控件 `combo_box_item` 定义选项。
- `combo_box` 的弹出列表是独立窗口，预览时点击才会出现。

## 4. 仪表盘/车载专用组合

### 4.1 gauge + gauge_pointer

```xml
<gauge name="speed_bg" x="40" y="90" w="320" h="320" image="speed_bg">
  <gauge_pointer name="needle" x="c" y="m" w="24" h="150"
                 image="needle" value="0" anchor_x="0.5" anchor_y="0.9"/>
</gauge>
```

- `gauge` **只是背景图容器**，不画刻度、不驱动指针。
- `gauge_pointer` 的 `value` 是 `angle` 的别名，单位是**度**；`0` 度为 12 点钟方向，顺时针为正。
- 指针图必须画成“垂直向上”（12 点钟方向），旋转由 `gauge_pointer` 完成。
- `anchor_x`/`anchor_y` 是旋转锚点：`0.5` 表示 50%，也可写 `12px`；指针尾部的旋转中心通常设 `y=0.9` 左右。
- 指针图优先 SVG；位图在 1.7.1 下也能旋转，但边缘会锯齿。
- 要让指针“指向某个刻度”，需要业务代码把物理值换算成角度后设置 `value`；XML 只能给静态初值。
- `gauge_pointer` 的 `x/y/w/h` 是未旋转时的包围盒，通常 `x="c"`，`y` 让锚点落在表盘中心。

### 4.2 2W cluster 典型组合

```xml
<window name="cluster" x="0" y="0" w="800" h="480">
  <!-- 左表：车速 -->
  <gauge name="speed_bg" x="20" y="80" w="300" h="300" image="speed_bg">
    <gauge_pointer name="speed_needle" x="c" y="m" w="22" h="140"
                   image="speed_needle" value="-135" anchor_x="0.5" anchor_y="0.9"/>
  </gauge>
  <!-- 右表：转速 -->
  <gauge name="rpm_bg" x="480" y="80" w="300" h="300" image="rpm_bg">
    <gauge_pointer name="rpm_needle" x="c" y="m" w="22" h="140"
                   image="rpm_needle" value="-135" anchor_x="0.5" anchor_y="0.9"/>
  </gauge>
  <!-- 中间数字车速 -->
  <image_value name="speed_digit" x="c" y="220" w="160" h="56"
               image="digit_" format="%03d" value="0"/>
  <!-- 底部圆弧油量/电量 -->
  <progress_circle name="fuel" x="c" y="bottom:30" w="120" h="120"
                   max="100" value="60" start_angle="135" line_width="8"/>
</window>
```

- 2W cluster 常见元素：车速表、转速表、数字车速、油量/电量弧、里程、档位、指示灯。
- 指示灯用 `image`/`image_value` 按状态切换图片；不要用 `label` 画图标。
- 指针动画在代码里做；XML 只负责静态首帧。
- 表盘背景图要包含刻度和文字；分辨率按设计稿 1:1 切图，避免运行时缩放。

### 4.3 指示灯 / 状态图标

```xml
<image name="turn_left" x="60" y="40" w="32" h="32" image="turn_left_off"/>
<image name="abs" x="100" y="40" w="32" h="32" image="abs_on"/>
```

- 多状态图标建议每种状态一张图，代码切换 `image`；或用 `image_value` 的数值映射。
- 需要闪烁时用 `image_animation` 或代码定时切换。

## 5. 事件与动画属性（了解即可）

生成静态 UI 时通常不需要，但不要误删用户已有的：

- `on:click="..."`：fscript 事件绑定。
- `animation="value(from=0, to=100, duration=3000, easing=linear, yoyo_times=1000)"`：属性动画。
- `visible="false"`、`enable="false"`、`sensitive="false"`：初始状态。
- `focusable="true"`：可获焦。

> 不要在 XML 中写 C 代码或自定义函数名；事件处理应由工程代码完成。生成的界面只负责结构和样式。

## 6. 控件选型速查

| 设计稿元素 | 首选控件 | 备注 |
| --- | --- | --- |
| 普通页面 | `window` | 固定屏写满 LCD 尺寸 |
| 弹窗 | `dialog` | 居中 + 半透明遮罩由主题提供 |
| 卡片/分组 | `view` + style 背景 | 不要滥用 `group_box` |
| 横排按钮组 | `view` + `children_layout="default(r=1,c=0...)"` | 比 `row` 更明确 |
| 竖排列表（少量） | `view` + `default(r=N,c=1)` | 大量用 `list_view` |
| 可滚动列表 | `list_view` + `scroll_view` + `list_item` | `item_height` 必填 |
| 表格 | `grid` + `columns_definition` | 列宽按比例/像素 |
| 图标按钮 | `button` + style `icon` | 或 `image` + `on:click` |
| 进度条 | `progress_bar` | 横向/纵向 |
| 圆环进度 | `progress_circle` | 支持起始角 |
| 指针表盘 | `gauge` + `gauge_pointer` | 指针图向上 |
| 数字显示 | `image_value` | 每位一张图 |
| 序列帧动画 | `image_animation` | 资源名带序号 |
| 多页滑动 | `slide_view` | 或 `pages` + `tab_control` |
| 下拉选择 | `combo_box` | 选项少时用 |
| 滚轮选择 | `text_selector` | 时间/档位常用 |
| 长文本 | `label` + `line_wrap` 或 `mledit` | 只读用 `mledit readonly="true"` |
| 富文本 | `rich_text` | CDATA |
| 悬浮元素 | 任意控件 + `floating="true"` | 不受父布局影响 |
