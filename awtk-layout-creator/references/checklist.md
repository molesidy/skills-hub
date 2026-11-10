# 交付检查清单

生成前、生成后、预览后各过一遍。任何一项不通过，都不要说“已完成”。

## 1. 输入阶段

- [ ] 已确认用户身份/偏好：项目类型（2W/中控/HMI/通用）、品牌色、字体、是否深色主题。
- [ ] 已拿到效果图（或明确没有），并记录设计稿尺寸、内容区原点、缩放比。
- [ ] 已拿到切图目录，或明确哪些图缺失。
- [ ] 已拿到坐标计划书 Excel（或明确没有），并确认表头/单位/合并单元格。
- [ ] 已确认目标 LCD 尺寸与主题名（`project.json` 或用户口述）。
- [ ] 已确认 AWTK 版本；1.7.1 release 2210 **没有** `flex(...)` self_layouter。
- [ ] 已确认工程是可预览的 AWTK 工程：`project.json` + `design/<theme>/{ui,styles,images,fonts}`。

## 2. 设计规格（design_spec.json）

- [ ] 所有坐标已换算成 **LCD 像素**，不是设计稿像素。
- [ ] 每个控件有唯一 `name`；没有名字的装饰容器已自动命名。
- [ ] 控件树层级与效果图分组一致；同级按 `y` 再 `x` 排序。
- [ ] 颜色已归一化（`#RRGGBB` 或 `#RRGGBBAA`，alpha 在后）。
- [ ] 字体名在 `design/<theme>/fonts` 中存在，或明确使用 `default`。
- [ ] 缺失输入已记录（坐标估算/缺图/缺字体），并在交付说明中写明。

## 3. 资源与命名

- [ ] 图片放在 `design/<theme>/images/x1`（或 `x2`/`svg` 等密度目录）。
- [ ] XML 中只写资源名，不写路径、不写扩展名。
- [ ] 资源名与文件名一致；大小写一致。
- [ ] `image_value` / `image_animation` 的前缀资源齐全（如 `digit_0..9`、`digit_dot`）。
- [ ] 9 宫格图已设置 `patch9` / `patch3_x` 等正确的 `bg_image_draw_type`。
- [ ] 图片尺寸足够，缩放后不糊；需要 SVG 的优先用 SVG。

## 4. 布局

- [ ] 根 `<window>` 有明确的 `w`/`h`（或 100% + LCD 尺寸可推导）。
- [ ] `x/y` 使用 `c/m/r/b` 或数字/百分比；没有使用 `top:` / `left:`。
- [ ] 负值只用于 `w/h` 表示“父尺寸减 N”；`x/y` 的负值是真实负坐标。
- [ ] `column`/`row` 有 `children_layout`（或样式里定义了 `children_layout`）。
- [ ] 容器内子控件的 `x/y/w/h` 不会被 `children_layout` 覆盖（除非确实要 grid/hbox 排版）。
- [ ] 需要浮动的控件用 `floating="true"`，且没有被父布局强行排布。
- [ ] 滚动内容放在 `scroll_view`/`list_view` 内；不要指望普通 `view` 裁剪后还能滚动。
- [ ] 超出父边界的控件已确认是有意为之（或父控件可滚动）。

## 5. 样式

- [ ] `style="..."` 引用的样式名在 `styles/default.xml` 中存在（AWTK 只自动加载该文件；窗口专属 `<窗口名>.xml` 除外）。
- [ ] 没有把样式按控件拆进 `button.xml` / `dialog.xml` 等不会被加载的文件。
- [ ] `styles/default.bin` 不存在，或已与 `default.xml` 同步（`.bin` 优先）。
- [ ] 状态属性写在正确的状态节点里（`normal`/`pressed`/`normal_of_checked`...）。
- [ ] `text_color` 与 `fg_color` 没混用（文本用 `text_color`）。
- [ ] `round_radius` 只用于纯色/边框背景；图片背景用 9 宫格切图。
- [ ] `border_width` 需要 vgcanvas；软件渲染下可能不生效。
- [ ] 颜色 alpha 在最后两位（`#RRGGBBAA`），不是 CSS 的 `#AARRGGBB`。
- [ ] 渐变只用 180°（非 vgcanvas 路径）；复杂渐变用切图。
- [ ] 默认样式缺失时，控件仍能显示（至少不白屏）。

## 6. 仪表专属

- [ ] `gauge` 只是背景图，本身不画刻度/指针。
- [ ] `gauge_pointer` 的 `value` 是**角度（度）**，0=12 点，顺时针为正。
- [ ] 指针图片朝上；`anchor_x/anchor_y` 与图片旋转轴一致。
- [ ] `progress_circle` 的 `start_angle`、`line_width`、`show_text` 在 1.7.1 中有效。
- [ ] `image_value` 的 `format` 与数字图数量匹配（`%03d` 需要 0..9 和图/负号/小数点）。
- [ ] 仪表动画/交互不影响静态截图（`animation` 属性在预览首帧可能处于起始值）。

## 7. 校验

```bash
python scripts/validate_ui.py design/default/ui/main.xml --project <工程> --lcd 800x480
```

- [ ] 0 errors。
- [ ] warnings 已逐条阅读；`--strict` 时 warnings 也视为失败。
- [ ] 图片资源检查通过（或明确使用占位图）。
- [ ] 样式引用检查通过。

## 8. 预览

```bash
python scripts/preview_ui.py --project <工程> --ui design/default/ui/main.xml \
    --lcd 800x480 --screenshot out/preview.png --wait 2
```

- [ ] 预览窗口客户区尺寸 = LCD 尺寸（不是 320×1）。
- [ ] `--json` 的 `res_layout` 与构建匹配：旧构建为 `staged`/`packaged`，新构建为 `design`；没有把旧构建的 `res_root` 指向 `design`。
- [ ] 旧构建使用 `packaged` 时，`res` 不旧于 `design`（否则加 `--stage-res` 或先跑 `update_res.py all`）。
- [ ] 没有白屏；背景/文字/图片可见。
- [ ] 文字可见（若全无文字，先查资源根下 `fonts/default.ttf`）。
- [ ] 中文字体正常，没有方框/乱码。
- [ ] 控件没有被裁剪、重叠、错位。
- [ ] 交互控件（按钮/滑块/下拉）至少静态显示正确。
- [ ] 若截图黑屏：确认渲染模式，或手动截图。

## 9. 与效果图比对

```bash
python scripts/compare_images.py design/mockup.png out/preview.png \
    --out-dir out/compare --overlay --json out/compare/metrics.json
```

- [ ] 两图已统一到同一尺寸（`--scale-to` / `--crop-*`）。
- [ ] 已看 `side_by_side.png`，不只看数字。
- [ ] 已看 `diff.png`，差异区域能对应到具体控件。
- [ ] `mae` / `diff_ratio` 在可接受范围；超阈值时已定位原因。
- [ ] 每轮只改一类问题（布局/颜色/图片/字体），避免无法归因。

## 10. 交付

- [ ] `design/<theme>/ui/*.xml` 与 `design/<theme>/styles/default.xml` 已写入正确位置。
- [ ] `design_spec.json`、预览截图、比对图、`metrics.json` 一并交付。
- [ ] 交付说明包含：LCD 尺寸、主题、字体、缺失资源、估算坐标、已知差异。
- [ ] 没有把临时文件写进 `design/`（会被打包）。
- [ ] 已告诉用户如何自己预览（命令 + 与构建匹配的 `res_root`：旧构建 `res`/staging，新构建 `design`）。

## 11. 验收标准

| 等级 | 标准 |
| --- | --- |
| 可交付 | 0 errors；预览无白屏；主要控件位置/颜色/文字正确 |
| 高还原 | 关键区域 MAE ≤ 5、diff_ratio ≤ 5%；文字不截断；图片不缺 |
| 像素级 | MAE ≤ 2、diff_ratio ≤ 1%；同字体、同切图、同渲染后端 |

> 像素级还原受字体、抗锯齿、渲染后端影响，不强求；**布局与信息层级正确**优先。
