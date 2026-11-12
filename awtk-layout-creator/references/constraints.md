# 硬性约束（必须遵守）

本文件是 `awtk-layout-creator` 的最高优先级规则。与“经验做法”“看起来更好”冲突时，一律以本文件为准。违反任何一条，都视为未完成。

## 约束 1：图片控件默认写 `draw_type="default"`

- 所有承载切图的控件，默认必须显式写 `draw_type="default"`。
  - 适用于：`image`、`image_value`、`image_animation`、`gif_image`、`svg_image` 等图片类控件。
- 只有**特殊控件/特殊用途**才允许不写 `draw_type="default"`，常见例外：
  - 整屏背景、需要随控件拉伸：`draw_type="scale"` / `scale_auto` / `scale_w` / `scale_h`；
  - 九宫格/三宫格背景：`patch9` / `patch3_x` / `patch3_y`；
  - 平铺纹理：`repeat` / `repeat_x` / `repeat_y` / `fill`；
  - 只居中不缩放：`center` / `icon`；
  - `gauge`、`gauge_pointer`、`progress_circle`、`button`、`label` 等本身不以 `draw_type` 为主的控件。
- 例外必须在 `design_spec.json` 中显式写出 `draw_type`，并在交付说明里写明原因；**不允许脚本或模型悄悄省略**。
- 如果切图原始尺寸与计划书 `w/h` 不一致：仍然使用 `draw_type="default"`，不要为了“填满”自动改成 `scale`；把这个差异写入同名 `.md`，由用户确认。
- `spec_to_ui.py` 会自动给图片类控件补 `draw_type="default"`；已经显式写了其他值的保持原值。

示例：

```xml
<!-- 默认：不缩放，按原图绘制 -->
<image name="temp_va1" x="12" y="1" w="12" h="19" draw_type="default" image="tem_n_2"/>

<!-- 特殊：整屏背景需要拉伸 -->
<image name="bg" x="0" y="0" w="1024" h="600" draw_type="scale" image="nav_bg"/>

<!-- 特殊：九宫格按钮背景 -->
<button name="ok" x="20" y="20" w="120" h="40" text="OK" draw_type="patch9" image="btn_ok_bg"/>
```

## 约束 2：禁止改动原始切图文件名

- 提供的切图文件名就是 AWTK 资源名：`design/<theme>/images/x1/<原文件名>.png` → XML 写 `image="<原文件名>"`。
- **不得重命名、不得改大小写、不得替换空格/连字符/中文、不得改名后另存**。
- 可以复制到工程的主题目录（例如 `day` / `night`），但复制后的文件名必须与原始文件名完全一致。
- 原始文件名不适合 AWTK 时（含中文、空格、`-`、大写等）：
  1. 仍然照原文件名引用，不修改；
  2. 在对应 XML 旁的 `.md` 说明文件中记录该风险；
  3. 由用户决定是否后续统一改名。
- `validate_ui.py` 会按“原始资源名”校验；找不到就报错，不会自动找近似名。

## 约束 3：缺图不放，错图/错坐标照放并写 `.md` 标记

三条子规则，按顺序判断：

| 情况 | 处理方式 |
| --- | --- |
| 切图缺失 | **不生成该控件**，不要用占位图、纯色块或从效果图抠图代替；在 `.md` 中列入“未放置” |
| 切图疑似错误 | **仍然按计划书放置**，不换图、不猜图；在 `.md` 中标记“切图待确认” |
| 坐标疑似错误 | **仍然按计划书的坐标原值放置**，不微调、不取整、不“看起来对齐”；在 `.md` 中标记“坐标待确认” |

- 所有坐标、尺寸、文本、资源名一律以提供的计划书和切图资料为准。
- **禁止自行曲解、禁止自行微调坐标、禁止为了画面好看而偏移 1～2px。**
- 生成 XML 前先对照提供的切图目录（或工程的 `design/<theme>/images`）逐个检查 `image` 资源：不存在就标 `missing: true`，不要先放上去再让校验报错。
- 每份生成的 XML 旁必须生成同名 `.md`（`main_day.xml` → `main_day.md`），至少包含：
  - 未放置的缺失切图清单（控件名、类型、计划坐标、缺失原因）；
  - 已放置但需要确认的控件（错误切图 / 错误坐标 / 其他）；
  - 屏幕级补充说明。
- 没有任何缺失或待确认项时，`.md` 可以省略；只要存在一项，就必须生成。

`design_spec.json` 中如何表达：

```json
{
  "missing_images": [
    { "name": "ind_beam", "widget": "ind_beam", "reason": "切图包中没有该文件" }
  ],
  "review_notes": ["屏幕级说明：计划书未给出本界面标题的字体"],
  "screens": [
    {
      "name": "nav",
      "review_notes": ["整屏说明"],
      "children": [
        {
          "name": "ind_abs",
          "type": "image",
          "x": 450, "y": 15, "w": 52, "h": 40,
          "attrs": { "image": "ind_abs" },
          "review_kind": "wrong_image",
          "review_note": "切图与效果图不一致，已按计划书放置"
        },
        {
          "name": "ind_missing",
          "type": "image",
          "x": 0, "y": 0, "w": 1, "h": 1,
          "missing": true,
          "missing_reason": "切图缺失，按约束不放置"
        }
      ]
    }
  ]
}
```

生成器行为：

- `missing: true` 的节点及其子树不会写入 XML；
- `review_note` 的节点照常写入，并在 `.md` 中登记；
- `missing_images` / `review_notes` 也会写入 `.md`。

## 约束 4：同主题下白天/黑夜两种模式必须输出两个 XML

- 识别到同一个主题、同一个界面同时存在白天和黑夜两套模式时，**必须生成两个 XML 文件**，不能只写一个共用 XML。
- 命名约定：
  - `file` 不含 `{mode}`：`nav.xml` → `nav_day.xml`、`nav_night.xml`；
  - `file` 含 `{mode}`：`nav_{mode}.xml` → `nav_day.xml`、`nav_night.xml`。
- 两个文件都放在该主题的 `ui/` 目录下；坐标基准完全一致，只允许切图/样式按模式不同。
- 白天/夜晚切图文件名不同（例如 `tem_n_*` / `tem_d_*`）时，在每个 XML 中分别引用各自的原始文件名，这也正是需要两个 XML 的原因。
- 如果颜色/样式也不同：在同一个 `styles/default.xml` 里定义两套命名样式（如 `text_day` / `text_night`），每个 XML 引用各自的样式；或用 `by_mode` 覆盖节点的 `style`。不要只写一个 XML 再靠运行时切主题来“省文件”。

`design_spec.json` 写法：

```json
{
  "screens": [
    {
      "name": "nav",
      "type": "window",
      "file": "nav.xml",
      "modes": ["day", "night"],
      "x": 0, "y": 0, "w": 1024, "h": 600,
      "children": [
        {
          "name": "temp_dash",
          "type": "image",
          "x": 12, "y": 1, "w": 12, "h": 19,
          "by_mode": {
            "day":   { "attrs": { "image": "tem_n_dash" } },
            "night": { "attrs": { "image": "tem_d_dash" } }
          }
        }
      ]
    }
  ]
}
```

- screen 没有 `modes` 时，如果节点使用了 `by_mode`，生成器会按 `by_mode` 的键自动识别模式并输出多个 XML；完全没有模式信息时才按单个 XML 输出。
- `by_mode` 支持覆盖任意节点字段；`attrs` / `inline_style` 会与基础值合并。
- 即使两套模式的 XML 内容完全相同，也要输出两个文件（用户明确要求）。

## 约束 5：同模块切图可以用 `<view>` 容器分组

- 当计划书/切图明确显示若干控件属于**同一个模块**（例如同一组温度数字、同一组指示灯、同一张卡片）时，允许用一个 `<view>` 包起来，便于整体移动和复用。
- 不要为了“结构好看”随意分组；单个控件、跨模块控件不要硬塞进容器。
- 分组后必须保持**绝对坐标不变**，只做坐标系换算：
  - **容器矩形优先采用计划书/示例给定的值**（例如用户示例的 `x=53 y=54 w=59 h=26`）。即使它比紧贴子控件的包围盒略大（含内边距），也**不得**为了“最小”把它缩小。
  - 只有计划书没有给出容器矩形时，才用组内最小外接矩形兜底：
    `x = min(子控件 x)`，`y = min(子控件 y)`，`w = max(子控件 x + w) - x`，`h = max(子控件 y + h) - y`；
  - 无论用哪种方式，容器都必须完整覆盖所有子控件（右边界、下边界不得小于子控件）。
  - 子控件：`x = 原 x - 容器 x`，`y = 原 y - 容器 y`，`w/h` 不变。
- 这不是“微调坐标”，而是把绝对坐标换算为相对容器的坐标；换算后整体在屏幕上的位置必须与计划书完全一致。
- 容器本身默认不写 `draw_type`；容器内的图片控件仍然遵守约束 1。
- 不要给容器加 `children_layout` 再用它“顺手排版”；分组容器主要是 `view` + 子控件绝对坐标。

示例（计划书中这一组温度切图属于同一模块）：

```xml
<view name="viewout_temp" x="53" y="54" w="59" h="26" visible="true">
  <image name="temp_heng" x="0" y="1" w="12" h="19" draw_type="default" image="tem_n_dash"/>
  <image name="temp_va1" x="12" y="1" w="12" h="19" draw_type="default" image="tem_n_2"/>
  <image name="temp_va2" x="24" y="1" w="12" h="19" draw_type="default" image="tem_n_9"/>
  <image name="temp_Unit" x="36" y="1" w="21" h="22" draw_type="default" image="tem_ssd"/>
  <image name="temp_baojing_st" x="15" y="0" w="30" h="24" draw_type="default" image="t_hi" visible="true"/>
</view>
```

> 原绝对坐标 = 容器坐标 + 子控件坐标；上例中 `temp_va1` 的绝对 x 仍是 `53 + 12 = 65`。生成前后整体位置不能变。
> 注意：这组子控件的紧贴包围盒其实是 `57×24`，而计划书/用户示例给的是 `59×26`（多出的 2px 是内边距）。**保留 `59×26`，不要按公式改成 `57×24`。**

## 与上下文压缩的关系

大输入可以用 `scripts/context_digest.py` 摘要，但压缩**只允许抽取**（计数、分组、采样、截断），不允许改写字段值。`name / type / x / y / w / h / image / style / text` 必须逐字保留；坐标只能来自原始计划书或 `design_spec.json`。压缩后的摘要不得成为“新的事实来源”。详见 `references/context-and-tokens.md`。

## 交付前自检（五条一起过）

- [ ] 所有图片控件都有 `draw_type`，默认值为 `default`；非默认值有明确理由。
- [ ] 没有任何切图文件被改名；XML 中的资源名等于原始文件名主干。
- [ ] 缺失切图没有出现在 XML 中；错误切图/错误坐标仍在 XML 中，并已写入同名 `.md`。
- [ ] 白天/黑夜双模式界面各有独立 XML（`_day.xml` / `_night.xml`）。
- [ ] `<view>` 分组只用于同模块控件，分组前后绝对坐标一致。

自动化校验：

```bash
# 结构 + 资源 + 样式 + 约束（图片 draw_type）
python scripts/validate_ui.py design/<theme>/ui/<screen>_day.xml \
    --project <工程> --theme <theme> --lcd 1024x600 --strict-constraints
```
