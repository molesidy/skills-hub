# AWTK 布局规则参考

本文件是生成 AWTK XML 时的布局依据。遇到不确定的属性，先查本工程的 AWTK SDK 源码/示例，不要凭印象发明属性。

## 1. 坐标与尺寸模型

AWTK 的控件位置和大小由 5 个自身布局参数决定：

| 参数 | 含义 | 常见取值 |
| --- | --- | --- |
| `x` | 左边界 | `10`、`10%`、`c` / `center`、`r` / `right`、`r:20` |
| `y` | 上边界 | `10`、`10%`、`m` / `middle`、`b` / `bottom`、`b:20` |
| `w` | 宽度 | `100`、`40%`、`-20` |
| `h` | 高度 | `40`、`20%`、`-20` |
| `floating` | 是否脱离父控件布局 | `true` / `false` |

### 1.1 像素

```xml
<button x="10" y="5" w="80" h="30" text="OK"/>
```

### 1.2 百分比

- `x`、`w` 的百分比相对父控件宽度。
- `y`、`h` 的百分比相对父控件高度。
- 百分比最终会四舍五入为整数像素。

```xml
<button x="10%" y="10" w="50%" h="30" text="OK"/>
```

### 1.3 居中 / 右 / 下

```xml
<button x="center" y="middle" w="100" h="36" text="OK"/>
<button x="right:20" y="10" w="80" h="36" text="Cancel"/>
<button x="10" y="bottom:20" w="80" h="36" text="Bottom"/>
```

- `x="c"` 与 `x="center"` 等价。
- `y="m"` 与 `y="middle"` 等价。
- `x="r:20"` 表示“距右边 20px”；`y="b:20"` 表示“距底部 20px”。
- `x="c:10"` 表示“居中后再向右 10px”；`x="c:10%"` 表示“居中后再向右父宽的 10%”。

### 1.4 负数宽高

`w` 或 `h` 为负数时，表示“父控件尺寸减去该绝对值”：

```xml
<!-- 宽度 = 父宽 - 40，高度 = 父高 - 20 -->
<view x="20" y="10" w="-40" h="-20"/>
```

> 负数百分比也会先按百分比计算再相加，语义容易混淆，生成时优先用负数像素。

### 1.5 self_layout

当父控件启用了 `children_layout`，子控件的 `x/y/w/h` 可能被父布局覆盖。此时如果某个子控件必须使用像素定位，用 `self_layout`：

```xml
<view children_layout="default(r=2,c=2,s=5)">
  <button text="1" self_layout="default(x=0,y=0,w=50,h=50)"/>
  <button text="2" x="r" y="m" w="60%" h="60%"/>
</view>
```

`self_layout` 的语法与自身布局参数一致：

```xml
self_layout="default(x=center,y=10,w=50%,h=148)"
```

> `self_layout` 的 `w/h` 百分比相对父布局分配给该子控件的区域，而不是整个父控件。

### 1.6 floating

`floating="true"` 的控件不受父控件 `children_layout` 影响，仍按自身 `x/y/w/h` 定位。适合角标、悬浮按钮、覆盖层：

```xml
<view children_layout="default(r=2,c=2,s=5)">
  <label text="1"/>
  <label text="2"/>
  <button text="floating" floating="true" x="c" y="m" w="80" h="30"/>
</view>
```

## 2. 子控件布局 children_layout

### 2.1 语法

```xml
<view children_layout="default(r=2,c=2,s=10,m=5)">
```

完整写法与简写都可用（解析器按参数名首字母识别）：

| 参数 | 简写 | 说明 |
| --- | --- | --- |
| `rows` | `r` | 行数 |
| `cols` | `c` | 列数 |
| `width` | `w` | 子控件统一宽度；`r=0` 时用于 vflow 列宽 |
| `height` | `h` | 子控件统一高度；`c=0` 时用于 hflow 行高 |
| `x_margin` | `xm` / `x` | 水平边距 |
| `y_margin` | `ym` / `y` | 垂直边距 |
| `margin` | `m` | 同时设置水平和垂直边距 |
| `spacing` | `s` | 子控件间距 |
| `flexible` | `f` | 放不下时是否换行/换列 |
| `keep_invisible` | `ki` | 是否给不可见控件留位置（默认否） |
| `keep_disable` | `kd` | 是否给禁用控件留位置（默认是） |
| `align_h` | `a` | hbox/hflow 的整体水平对齐：`left` / `center` / `right` |

### 2.2 六种典型模式

| 模式 | 参数 | 行为 |
| --- | --- | --- |
| hbox 水平排列 | `r=1,c=0` | 一行；高度由父控件决定；宽度由子控件决定 |
| vbox 垂直排列 | `r=0,c=1` | 一列；宽度由父控件决定；高度由子控件决定 |
| listbox 均分列表 | `r=N,c=1` | 一列 N 行，行高均分 |
| grid 网格 | `r=N,c=M` | N×M 网格，单元格均分 |
| hflow 水平流式 | `h=<行高>,c=0` | 逐行排列，放不下换行；子控件决定宽度 |
| vflow 垂直流式 | `w=<列宽>,r=0` | 逐列排列，放不下换列；子控件决定高度 |

示例：

```xml
<!-- 水平工具栏 -->
<row x="0" y="0" w="100%" h="48" children_layout="default(r=1,c=0,s=8,xm=12)">
  <button text="Back" w="80"/>
  <label text="Title" w="200"/>
  <button text="Menu" w="80"/>
</row>

<!-- 4×3 图标网格 -->
<view x="20" y="60" w="-40" h="-80" children_layout="default(r=4,c=3,s=12,m=8)"/>

<!-- 垂直列表（非滚动） -->
<view x="0" y="50" w="100%" h="-50" children_layout="default(r=5,c=1,s=1)">
  <label text="Item 1"/>
  <label text="Item 2"/>
  ...
</view>
```

### 2.3 关键规则

1. **`column` / `row` 本身不会自动布局**。它们只是语义标签，必须显式写 `children_layout`，或在 style 中配置 `children_layout`。
2. 父控件启用 `children_layout` 后，子控件的 `x/y/w/h` 不保证生效：
   - hbox 中高度会被父布局覆盖；
   - vbox 中宽度会被父布局覆盖；
   - grid/listbox 中位置和单元格尺寸会被覆盖。
   需要保留像素定位时使用 `self_layout` 或 `floating="true"`。
3. `spacing` 和 margin 由父布局统一计算；不要在子控件上再重复加间距。
4. hbox 的子控件需要自己决定宽度（像素、百分比或 `self_layout`）。
5. vbox 的子控件需要自己决定高度。
6. 子控件百分比尺寸相对“父布局分配给它的区域”，不是整个屏幕。
7. 默认 `keep_disable=true`：禁用的子控件仍占位；不需要占位时设置 `kd=false`。
8. 默认 `keep_invisible=false`：不可见子控件不占位；需要保留空位时设置 `ki=true`。

## 3. ListView 布局

可滚动列表使用 `list_view` + `scroll_view`：

```xml
<list_view x="0" y="48" w="100%" h="-48" item_height="56">
  <scroll_view name="view" x="0" y="0" w="100%" h="100%"
               children_layout="list_view(m=8,s=4)">
    <list_item>...</list_item>
    <list_item>...</list_item>
  </scroll_view>
</list_view>
```

- `item_height` 是行高；可变行高用 `default_item_height` 或 `self_layout="flex(h=flex)"`（需 SDK 支持）。
- `children_layout="list_view(...)"` 只作用于 `list_view` 下的 `scroll_view`。
- 列表项多时不要把所有 item 静态写进 XML，应由 C 代码动态创建；XML 只放模板/首屏。
- 横向列表用 `list_view_h`。

## 4. Grid 表格布局

`grid` 适合列宽不一致或需要网格线的表格：

```xml
<grid x="10" y="10" w="-20" h="180" rows="5"
      columns_definition="col(w=0.4,m=5);col(w=0.3,m=5);col(w=0.3,m=5);"
      show_grid="true"
      style.normal.grid_color="gray"
      style.normal.border_color="black"
      style.normal.odd_bg_color="#f5f5f5"
      style.normal.even_bg_color="#eeeeee">
  <label text="姓名"/><label text="语文"/><label text="数学"/>
  ...
</grid>
```

- `columns_definition` 每列 `col(w=...,l=...,r=...,t=...,b=...,m=...,f=...)`。
- `w` 在 `(0,1]` 区间按比例，否则按像素；负数表示控件宽度加该值。
- `fill_available`（`f`）让某一列吃掉剩余宽度（只能一列）。

## 5. 布局策略决策树

生成 XML 前按下面顺序决策：

1. **固定分辨率嵌入式屏（仪表/HMI 常见）**
   - 优先使用设计稿坐标（像素），保证 1:1 还原。
   - 对贴边元素使用 `x="r:..."`、`y="b:..."`、`w="-..."`、`h="-..."`，让边缘随屏幕变化。
   - 对居中元素使用 `x="c"`、`y="m"`。
2. **一组同类元素水平/垂直排列**
   - 用 `children_layout="default(r=1,c=0,...)"` 或 `default(r=0,c=1,...)`。
3. **二维重复元素（图标、按键矩阵）**
   - 用 `children_layout="default(r=N,c=M,...)"`。
4. **列宽不一致的表格**
   - 用 `grid` + `columns_definition`。
5. **可滚动、动态内容**
   - 用 `list_view` + `scroll_view` + `children_layout="list_view(...)"`。
6. **层叠/悬浮元素**
   - 子控件顺序决定 z-order；需要脱离父布局时用 `floating="true"`。
7. **超出父控件需要裁剪**
   - 用 `clip_view` 或父控件裁剪。

> 不要为了“看起来高级”而嵌套多层 `view`。2～3 层通常足够；层级越深，布局和调试越难。

## 5.1 同模块切图分组（`<view>`）

当计划书或切图明确显示若干控件属于**同一个模块**（同一组温度数字、同一组指示灯、同一张卡片）时，可以用一个 `<view>` 容器把它们包起来。约束见 `references/constraints.md` 第 5 条。

规则：

1. 只在“同一模块”时分组；单个控件、跨模块控件不要硬塞进容器。
2. 容器矩形优先采用计划书/示例给定的值（如用户示例的 `53,54,59,26`）；**不要**为了“最小”把给定容器缩小。
   计划书没给容器时，才用组内最小外接矩形兜底：
   - `view.x = min(child.x)`、`view.y = min(child.y)`；
   - `view.w = max(child.x + child.w) - view.x`；
   - `view.h = max(child.y + child.h) - view.y`。
3. 子控件坐标换算为相对容器：
   - `child.x = 原 child.x - view.x`；
   - `child.y = 原 child.y - view.y`；
   - `w/h` 不变。
4. **分组前后绝对坐标必须完全一致**。这是坐标系换算，不是“微调坐标”；不允许借分组之名偏移控件。
5. 容器默认不写 `draw_type`；容器内的图片控件仍然写 `draw_type="default"`（特殊控件除外）。
6. 容器一般不用 `children_layout`，子控件继续用绝对坐标；只有确实需要统一排版时才用，并确保不会覆盖计划书坐标。
7. z-order 仍然是 XML 顺序：容器整体的绘制顺序由它在父控件中的位置决定；容器内的顺序由内部子控件顺序决定。

示例：

```xml
<view name="viewout_temp" x="53" y="54" w="59" h="26" visible="true">
  <image name="temp_heng" x="0" y="1" w="12" h="19" draw_type="default" image="tem_n_dash"/>
  <image name="temp_va1" x="12" y="1" w="12" h="19" draw_type="default" image="tem_n_2"/>
  <image name="temp_va2" x="24" y="1" w="12" h="19" draw_type="default" image="tem_n_9"/>
  <image name="temp_Unit" x="36" y="1" w="21" h="22" draw_type="default" image="tem_ssd"/>
  <image name="temp_baojing_st" x="15" y="0" w="30" h="24" draw_type="default" image="t_hi" visible="true"/>
</view>
```

校验换算：

- `temp_va1` 绝对 x = `53 + 12 = 65`，与分组前一致；
- 容器右边界 = `53 + 59 = 112`，必须覆盖组内所有子控件的右边界；
- 容器下边界 = `54 + 26 = 80`，必须覆盖组内所有子控件的下边界。
- 这组子控件的紧贴包围盒是 `57×24`，但计划书/用户示例给的是 `59×26`（含 2px 内边距）。**保留 `59×26`，不要按公式缩成 `57×24`。**

> 分组不是强制要求。计划书没有表达模块归属、或分组会让坐标换算更容易出错时，保持扁平结构即可；**正确性优先于结构美观**。

## 6. 设计稿坐标 → AWTK 坐标

### 6.1 计算缩放

```text
scale_x = mockup_width  / lcd_width
scale_y = mockup_height / lcd_height
```

- 两个 scale 不一致时，先确认设计稿是否有等比留白/设备边框；不要直接取平均值。
- 有设备边框时，先减去内容区原点：`content_x = design_x - frame_left`。
- Excel 坐标可能已经是 LCD 像素，也可能以设计稿像素为单位；用最大值和屏幕尺寸交叉验证。

### 6.2 转换

```text
lcd_x = round((design_x - origin_x) / scale_x)
lcd_y = round((design_y - origin_y) / scale_y)
lcd_w = round(design_w / scale_x)
lcd_h = round(design_h / scale_y)
```

- 固定布局保留整数像素；不要保留小数。
- **坐标只做单位/缩放换算，不做视觉微调。** 计划书给的是 `x=53` 就写 `53`，不要因为预览“看起来偏了”改成 `52`/`54`；有疑问写进同名 `.md` 待确认。
- 需要百分比时：`pct = lcd_value / lcd_dim * 100`，保留 1 位小数。
- 1px 线条/边框不要缩放成 0；至少保留 1px。
- 设计稿是 2x/3x 且切图也是 2x/3x 时，优先按 DPR 资源目录放置切图，不要在 XML 里手工除以 2 后再让图片二次缩放。

### 6.3 容差

| 场景 | 位置/尺寸容差 | 说明 |
| --- | --- | --- |
| 1x 固定布局 | ±1px | 像素级还原 |
| 2x 设计稿缩到 1x | ±2px | 缩放+取整误差 |
| 百分比/响应式布局 | ±0.5% 或 ±2px | 取较大者 |
| 文本基线 | 以视觉为准 | AWTK 与设计工具字体度量不同 |

## 7. 常见布局模式

### 7.1 全屏页面

```xml
<window name="main" x="0" y="0" w="800" h="480">
  <view name="header" x="0" y="0" w="100%" h="56" children_layout="default(r=1,c=0,s=8,xm=16)"/>
  <view name="content" x="0" y="56" w="100%" h="-56"/>
  <view name="footer" x="0" y="bottom" w="100%" h="48" children_layout="default(r=1,c=0,s=8,xm=16)"/>
</window>
```

### 7.2 居中卡片/弹窗

```xml
<dialog name="confirm" x="c" y="m" w="360" h="200">
  <label x="c" y="40" w="-40" h="60" text="Are you sure?" text_align_h="center"/>
  <button name="ok" x="20" y="bottom:20" w="-40" h="40" text="OK"/>
</dialog>
```

### 7.3 顶部状态栏 + 主内容

```xml
<window name="main" x="0" y="0" w="480" h="800">
  <system_bar x="0" y="0" w="100%" h="32"/>
  <view x="0" y="32" w="100%" h="-32"/>
</window>
```

### 7.4 仪表盘（2W cluster 常见）

```xml
<window name="cluster" x="0" y="0" w="800" h="480">
  <gauge name="speed" x="40" y="90" w="300" h="300" image="speed_bg">
    <gauge_pointer name="speed_pointer" x="c" y="m" w="24" h="140"
                   image="speed_pointer" value="-135" anchor_x="0.5" anchor_y="0.9"/>
  </gauge>
  <image_value name="speed_digit" x="c" y="bottom:40" w="160" h="48"
               image="digit_" format="%03d" value="0"/>
  <progress_circle name="rpm" x="right:40" y="90" w="300" h="300"
                   max="12000" value="0" start_angle="135" line_width="12"/>
</window>
```

> `gauge_pointer` 的图片必须“垂直向上”，旋转锚点通过 `anchor_x/anchor_y` 指定（百分比或 `xxpx`）；指针图推荐 SVG。
> `gauge_pointer` 的 `value` 是 `angle` 的别名，单位是**度**（0 度指向 12 点钟，顺时针为正），不是物理量。
> `progress_circle` 适合弧形/圆环仪表；`gauge` 只是背景图，指针必须用 `gauge_pointer` 子控件。

### 7.5 选项卡

```xml
<tab_control x="0" y="0" w="100%" h="100%">
  <pages x="0" y="0" w="100%" h="-48">
    <view name="page1"/>
    <view name="page2"/>
  </pages>
  <tab_button_group x="0" y="bottom" w="100%" h="48">
    <tab_button text="Page 1" value="true"/>
    <tab_button text="Page 2"/>
  </tab_button_group>
</tab_control>
```

## 8. 版本兼容

不同 AWTK 版本的布局能力不同。生成前检查：

```bash
<AWTK_ROOT>/src/awtk_version.h
<AWTK_ROOT>/component.json   # release_id，例如 2210
```

- `self_layouter_flex`（`self_layout="flex(...)"`）只在较新的 AWTK 中存在。**AWStudio 自带 SDK 1.7.1 release 2210 没有 `src/layouters/self_layouter_flex.c`，不要生成 `flex(...)`**；使用前先检查该文件或本机 SDK 的 `src/layouters/` 目录。
- 老版本不支持的能力，退回 `children_layout` + 百分比/像素布局。
- `gauge`、`gauge_pointer`、`progress_circle`、`image_value` 属于扩展控件，确认工程已启用对应模块（通常默认启用）。

## 9. 常见坑

- **`column`/`row` 不会自动排列子控件**：必须配 `children_layout`，或使用带 `children_layout` 的 style。
- **父布局覆盖子控件坐标**：grid/listbox/vbox/hbox 会覆盖子控件的位置/尺寸；需要精确定位时用 `self_layout` 或 `floating`。
- **百分比基准搞错**：子控件百分比相对父控件（或父布局分配区域），不是屏幕。
- **负数宽高方向搞反**：`w="-20"` 是“父宽 - 20”，不是“负 20”。
- **`x="c:10"` 与 `x="10"` 混淆**：前者是居中偏移，后者是绝对左边距。
- **`children_layout` 参数名写错**：`r/c/w/h/x/y/m/s/f/ki/kd/a` 是常用简写；不确定时用完整名。
- **z-order 搞反**：XML 中子控件顺序就是绘制顺序，后写的在上层。
- **忘记 `floating`**：在 grid 中放悬浮角标，不写 `floating` 会被布局到格子里。
- **文本溢出**：`label` 默认不换行；需要换行时设 `line_wrap="true"` 或 `word_wrap="true"`，超长省略用 `ellipses="true"`；长文本也可用 `mledit readonly="true"`。
- **固定像素在缩放屏上错位**：固定屏可以像素优先；需要适配多分辨率时，边缘/容器用相对布局，内容用 `children_layout`。
