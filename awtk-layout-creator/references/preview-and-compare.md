# 预览与比对

生成 XML 后必须预览。AWTK 自带官方预览工具 `preview_ui`，不需要编译工程；但**样式/图片/字体是否需要先打包资源，取决于 preview_ui 的构建版本**。本文件说明如何定位、启动、截图和比对。

## 1. 官方预览工具

### 1.1 可执行文件位置

```text
<AWTK_ROOT>/bin/preview_ui.exe
```

`<AWTK_ROOT>` 按以下顺序确定：

1. 命令行/脚本参数 `--awtk-root`。
2. 环境变量 `AWTK_SDK_PATH` 指向的 SDK 下的 `awtk`（AWStudio 常见布局）：

```text
D:/SoftwareHub/AWStudio/AWTK/SDK/awtk
```

3. 工程 `project.json` 的 `awtkRoot`：

```json
{ "awtkRoot": "${AWTK_SDK_PATH}/awtk" }
```

4. 常见安装路径扫描：`C:/awtk`、`D:/awtk`、`D:/SoftwareHub/AWStudio/AWTK/SDK/awtk`。
5. 从工程目录向上最多 5 层查找 `awtk/`（vendored SDK，例如把 AWTK 源码仓库克隆在工程旁边）。

都不命中时，显式传 `--awtk-root <AWTK_ROOT>`。

`scripts/awtk_common.py` 的 `find_awtk_root()` 实现了以上顺序。

### 1.2 资源查找规则（比参数更容易出错）

`preview_ui` 的 **UI XML 始终按命令行给出的文件路径直接读取**；但 `<image>`、样式、字体、多语言字符串走 AWTK 资源管理器，从 `res_root` 按固定布局查找。不同构建布局不同：

| 构建 | 资源查找路径 | `res_root` 应指向 |
| --- | --- | --- |
| `demos/preview_ui.c`（AWStudio SDK 1.7.1） | `<res_root>/assets/<theme>/raw/{styles,images,fonts,strings}` | 工程的 `res/`（`update_res.py` 产物） |
| `tools/preview_ui.c`（较新） | `<res_root>/<theme>/{styles,images,fonts}` | 工程的 `design/` |

旧构建的实际路径来自 `assets_manager_build_asset_filename()`：`<res_root>/assets/<theme>/raw/...`。因此：

```bash
# 旧构建：res_root 指向打包资源
preview_ui.exe D:/proj/design/default/ui/main.xml 800 480 D:/proj/res zh_CN default

# 旧构建：res 尚未生成或已过期时，让脚本镜像 design
python scripts/preview_ui.py --project D:/proj --ui design/default/ui/main.xml --stage-res

# 新构建：res_root 指向 design
preview_ui.exe ui=D:/proj/design/default/ui/main.xml lcd_w=800 lcd_h=480 res_root=D:/proj/design
```

常见误判：

- **旧构建 + `res_root=design`**：UI 能显示，但 `design` 下没有 `assets/<theme>/raw`，样式/图片/字体全部回退到内置默认值。不会报错，看起来像“样式不生效”。
- **旧构建 + `res_root=res` 但没跑 `update_res.py`**：`res` 不存在或过期，读到的仍是旧样式/旧图。
- **`.bin` 优先**：取样式时先试 `default.bin`，再试 `default.xml`。`res/.../styles/default.bin` 存在时，改 `design/.../default.xml` 不会生效。要么重新 `update_res.py style`，要么用 `--stage-res`（staging 会跳过被同名 XML 覆盖的 `.bin`）。
- **字体**：没有字体资源时文字不渲染。确认 `raw/fonts/default.ttf`（或 `.bin`）存在；极小工程可从 `<AWTK_ROOT>/design/default/fonts/` 复制 `default.ttf`、`default_full.ttf`。

`preview_ui.py` 会自动判断：旧构建下 `res` 存在且不旧于 `design` 时用 `res`；否则把 `design/<theme>` 暂存到 `out/preview_res/assets/<theme>/raw` 后预览；新构建直接用 `design`。`--res-root` 可手动覆盖。

### 1.3 两种命令行风格（务必先识别）

AWTK 历史上有两个 `preview_ui` 版本，参数格式不同。传错格式**不会报错**，只会得到一个 320×1 的空白窗口，很容易误判为“渲染失败”。

| 构建来源 | 参数风格 | 窗口标题 | 识别特征 |
| --- | --- | --- | --- |
| `demos/preview_ui.c`（AWStudio SDK 1.7.1 常见） | **位置参数** | `AWTK Simulator` | 二进制含 `ui_file [w] [h] [res root]` |
| `tools/preview_ui.c`（较新） | **key=value** | `awtk_preview` | 二进制含 `lcd_w=` / `res_root=` |

`scripts/awtk_common.py` 的 `preview_cli_style()` 会自动识别，`preview_ui.py` 按识别结果组装命令。

**位置参数版**：

```text
preview_ui.exe <ui.xml> <lcd_w> <lcd_h> <res_root> [language] [theme]
```

```bash
bin/preview_ui.exe D:/proj/design/default/ui/main.xml 800 480 D:/proj/res zh_CN default
```

- 第 5 个参数是语言（`zh_CN`），第 6 个才是主题；只想传主题时必须先传语言。
- 不传第 5/6 个参数时使用默认语言和 `default` 主题。
- 该版本**不支持** `system_bar=`、`plugins_path=`、`render_mode=`、`fps=` 等 key=value 参数。
- 该版本是 GUI 子系统程序，会自己 `AllocConsole()`；它的日志在**独立控制台窗口**里，不会写进父进程重定向的 stdout。

**key=value 版**：

```text
preview_ui.exe ui=<ui.xml> [lcd_w=800] [lcd_h=480] [res_root=<dir>]
               [language=zh_CN] [theme=default] [system_bar=<ui>]
               [bottom_system_bar=<ui>] [plugins_path=<dir>]
               [render_mode=OpenGL] [enable_std_font=true]
               [log_level=1] [fps=30]
```

| 参数 | 说明 |
| --- | --- |
| `ui` | **必填**，UI XML 文件路径 |
| `lcd_w` / `lcd_h` | LCD 尺寸，默认 320×480 |
| `res_root` | 资源根目录；**传工程的 `design` 目录** |
| `theme` | 主题名，对应 `design/<theme>/` |
| `language` | 语言，如 `zh_CN`、`en_US` |
| `system_bar` | 顶部系统栏 UI 名称（不是文件路径） |
| `bottom_system_bar` | 底部系统栏 UI 名称 |
| `plugins_path` | 自定义控件 DLL 目录；DLL 需导出 `xxx_register(void)` |
| `render_mode` | 渲染模式，默认 `OpenGL`；可试 `Software`/`AGGE` 等 |
| `enable_std_font` | 是否启用标准字体 |
| `log_level` | 日志级别，`0` debug、`1` info、`2` warn、`3` error |
| `fps` | 帧率 |

> key=value 版参数无顺序要求，必须写成 `key=value`；位置参数版相反，**不能**写成 `key=value`。

### 1.4 直接运行

```bash
cd <AWTK_ROOT>

# 位置参数版：res_root 指向打包资源 res
./bin/preview_ui.exe D:/proj/design/default/ui/main.xml 800 480 D:/proj/res zh_CN default

# key=value 版：res_root 指向 design
./bin/preview_ui.exe ui=D:/proj/design/default/ui/main.xml lcd_w=800 lcd_h=480 res_root=D:/proj/design theme=default
```

窗口标题可能是 `AWTK Simulator`（位置参数版）或 `awtk_preview`（key=value 版）。关闭窗口即退出。

> `preview_ui` 会阻塞在窗口事件循环。脚本启动时应放到后台，截图后主动结束进程。
>
> 若窗口大小是 **320×1**，几乎可以确定参数风格传错了（位置参数版把 `ui=...` 当成了文件名、把 `lcd_w=800` 用 `atoi` 解析成 0）。

## 2. 脚本预览

### 2.1 基本用法

```bash
python scripts/preview_ui.py --project D:/proj --ui design/default/ui/main.xml \
    --lcd 800x480 --screenshot out/preview.png --keep-open
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--project` | 工程根目录（含 `project.json` 或 `design/`） |
| `--ui` | UI XML 路径（相对工程或绝对） |
| `--awtk-root` | 手动指定 AWTK 根目录 |
| `--lcd` | `800x480`，覆盖 project.json |
| `--theme` / `--language` | 传给 preview_ui |
| `--res-root` | 手动覆盖资源根；默认按构建自动选择（见 1.2） |
| `--stage-res` | 强制把 `design/<theme>` 镜像到 `out/preview_res` 后再预览（旧构建） |
| `--update-res` | 先运行工程的 `scripts/update_res.py all`，再用打包资源预览 |
| `--screenshot PATH` | 启动后截图保存 |
| `--wait SECONDS` | 启动后等待秒数再截图（默认 2） |
| `--keep-open` | 截图后不关闭预览 |
| `--dry-run` | 只打印命令，不执行 |
| `--json` | 输出 JSON 结果（命令、PID、截图路径、`res_layout`、状态） |
| `--validate` | 启动前先做 XML 校验 |

脚本行为：

1. 解析工程/`project.json`，定位 `preview_ui.exe`。
2. 读取二进制字符串判断参数风格（`positional` / `keyvalue`），据此组装命令。
3. 按构建选择资源根：`keyvalue` 用 `design`；`positional` 用新鲜度合格的 `res`，否则自动 staging 到 `out/preview_res`。
4. 启动预览；轮询该 PID 下类名为 `SDL_app` 的窗口（标题通常是 `AWTK Simulator` 或 `awtk_preview`）。
5. 等待窗口客户区达到 `--lcd` 指定尺寸，再等 `--wait` 秒让首帧绘制完成。
6. 用 GDI 捕获窗口客户区，保存 PNG。
7. 默认结束进程；`--keep-open` 保留。

`--json` 输出里包含 `preview_cli`（参数风格）、`res_root` 和 `res_layout`（`design`/`packaged`/`staged`/`explicit`），便于确认预览到底读的是哪套资源。

### 2.2 截图原理与限制

- Windows：`ctypes` + `user32`/`gdi32` 的 `GetClientRect` + `BitBlt`，按客户区像素保存。
- 只截客户区，不含标题栏和边框；与 LCD 尺寸一致。
- DPI 缩放可能导致尺寸与 `lcd_w/lcd_h` 不一致；脚本会在尺寸不符时提示。
- OpenGL 渲染模式下个别显卡截图为黑屏；新构建可改用 `--render-mode Software`，旧构建不支持该参数，只能手动截图。
- 旧构建下 `out/preview_res` 是脚本生成的 staging 目录，可随时删除；不要把它当成工程资源。
- 无法截取弹出菜单/下拉列表（它们是独立窗口）；需要时手动打开再截。

### 2.3 手动截图

如果脚本截图失败：

1. 运行预览并保持窗口。
2. 用 Windows `Alt+PrintScreen` 截活动窗口，或 `Win+Shift+S` 框选客户区。
3. 保存 PNG，用 `compare_images.py` 与效果图比对。

## 3. 预览前校验

```bash
python scripts/validate_ui.py design/default/ui/main_day.xml --project D:/proj --strict-constraints
```

检查项：

- XML 是否 well-formed。
- 控件 `name` 是否唯一。
- 图片类控件是否写了 `draw_type`（`--strict-constraints` 下缺 `draw_type` 为 error）。
- `image` 引用的资源是否存在于 `design/<theme>/images/**`，且资源名等于原始文件名主干。
- `style="..."` 引用的命名样式是否在 AWTK 实际加载的样式文件中定义（`styles/default.xml`；窗口专属 `<name>.xml` 除外）。
- `styles/` 下不会被加载的拆分文件会给出 warning。
- `x/y/w/h` 是否可解析（数字、百分比、`c/r/b/m`、`r:20`、`b:20`）。
- `children_layout` / `self_layout` 语法是否可解析。
- 控件是否超出父控件边界（只警告，不报错）。
- 是否使用了当前 SDK 不支持的 `flex(...)`。

校验通过不代表渲染正确，但能挡住大部分“白屏/找不到图/样式丢失”。

## 4. 与效果图比对

### 4.1 比对流程

```text
效果图 ──┐
         ├─ 统一尺寸 ── 计算差异 ── 生成 diff / side-by-side ── 输出 metrics
预览截图 ┘
```

```bash
python scripts/compare_images.py design/mockup.png out/preview.png \
    --out-dir out/compare --json out/compare/metrics.json
```

输出：

| 文件 | 内容 |
| --- | --- |
| `metrics.json` | MAE、RMSE、差异像素比例、差异包围盒、尺寸 |
| `diff.png` | 差异高亮图（默认红色） |
| `side_by_side.png` | 左效果图、右预览图 |
| `overlay.png` | 半透明叠加（可选 `--overlay`） |

### 4.2 指标含义

| 指标 | 计算 | 用途 |
| --- | --- | --- |
| `mae` | 所有像素通道平均绝对差（0–255） | 整体颜色/亮度偏差 |
| `rmse` | 均方根误差 | 对大偏差更敏感 |
| `diff_ratio` | 任一通道差 > `--threshold` 的像素占比 | 局部错位/缺失 |
| `bbox` | 差异像素的包围盒 | 快速定位问题区域 |
| `size_match` | 两图尺寸是否一致 | 尺寸不一致时先缩放再比 |

### 4.3 判定参考

| 场景 | MAE | diff_ratio | 说明 |
| --- | --- | --- | --- |
| 像素级还原 | ≤ 2 | ≤ 1% | 固定屏、同字体、同切图 |
| 可接受 | ≤ 5 | ≤ 5% | 有抗锯齿/字体差异 |
| 需要检查 | > 5 | > 5% | 布局错位、图片缺失、颜色错误 |

> 这些阈值是经验值，不是硬标准。文本区域、抗锯齿边缘、图片缩放都会产生正常差异。**先看 diff 图，再看指标**。

### 4.4 常见差异原因

| 现象 | 可能原因 |
| --- | --- |
| 整体偏移 | 设计稿内容区原点算错、缩放比错 |
| 整体颜色偏 | 主题色未生效、`res_root` 错、样式名错 |
| 图片不显示 | 资源名/目录/扩展名错、密度目录缺失 |
| 文字位置偏 | 字体不同、`text_align_*` 未设、行高差异 |
| 文字缺失 | 字体缺字、`font_name` 不存在、编码问题 |
| 控件被裁剪 | 父控件尺寸不足、`clip_view`、超出父边界 |
| 控件重叠 | z-order/子控件顺序、`floating` 使用不当 |
| 圆角/阴影不对 | 切图问题、`round_radius` 与图片背景冲突 |
| 指针角度不对 | `gauge_pointer` 的 `value` 是角度（度），不是物理值 |

### 4.5 视觉确认

脚本只能给出数值和 diff 图。**最终必须由人看一眼预览图**：

- 布局是否符合设计稿的分组和层级。
- 文字是否截断、换行是否合理。
- 图标/指针/进度是否在正确位置。
- 颜色是否符合品牌/主题。

在本环境的某些终端里，图片可能无法直接内联显示；此时把 `side_by_side.png`/`diff.png` 路径交给用户打开，或让用户直接看预览窗口。

## 5. 迭代循环

```text
1. 生成/修改 design_spec.json
2. 生成 ui/*.xml + styles/default.xml
3. validate_ui.py
4. preview_ui.py --screenshot
5. compare_images.py
6. 看 diff/side-by-side，定位问题
7. 修改 XML/样式/切图，回到 3
```

建议每轮只改一类问题（布局、颜色、图片、字体），避免一次改动太多无法归因。

## 6. 预览失败排查

| 现象 | 检查 |
| --- | --- |
| 找不到 `preview_ui.exe` | `--awtk-root`、`AWTK_SDK_PATH`、`project.json` 的 `awtkRoot` |
| 窗口是 320×1 | **参数风格传错**：位置参数版收到 `ui=`/`lcd_w=`；改用 `preview_ui.py` 自动识别 |
| 窗口一闪而过 | 命令参数错误；用 `--dry-run` 打印命令，手动运行看控制台输出 |
| 白屏 | 旧构建：`res_root/assets/<theme>/raw` 是否存在；新构建：`res_root/<theme>` 是否存在。优先用 `preview_ui.py` 自动选择 |
| UI 正常但样式全丢 | 旧构建把 `res_root` 指向了 `design`；或 `res` 里 `default.bin` 抢先；或样式写进了 `button.xml` 等不会加载的文件 |
| 图片全丢 | 旧构建看 `res_root/assets/<theme>/raw/images/x1`；新构建看 `design/<theme>/images/x1`；资源名是否带扩展名 |
| 文字不显示 | 资源根下有没有 `fonts/default.ttf`（或 `.bin`）；`font_name` 是否存在；旧构建 staging 时 `design/<theme>/fonts` 是否为空 |
| 字体不对 | `fonts` 目录、`font_name`、`enable_std_font`（仅新构建） |
| 控制台无输出 | 位置参数版会自己开控制台；看任务栏里标题为 exe 路径的窗口 |
| 截图黑屏 | 新构建可换 `render_mode=Software`；旧构建只能手动截图 |
| 中文乱码 | XML 是否 UTF-8；字体是否含中文字形 |

### 6.1 大日志先摘要

预览/构建日志超过 200 行时，不要整份读：

```bash
python scripts/context_digest.py build.log --budget 3000
python scripts/context_digest.py build.log --grep error
```

摘要会归一化时间戳/路径/数字，按模式去重，统计 error/warning 行数，只保留首尾样本。定位到具体条目后再读原始日志的对应行。

## 7. 退出与清理

- `preview_ui.py` 默认在截图后 `terminate` 进程；`--keep-open` 时不结束。
- 若预览进程残留，用任务管理器结束 `preview_ui.exe`，或：

```bash
taskkill /IM preview_ui.exe /F
```

- 截图/对比输出放在工程的 `out/` 或临时目录，不要写进 `design/`，避免被当成资源打包。
