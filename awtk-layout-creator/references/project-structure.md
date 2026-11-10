# AWTK 工程结构

生成的文件必须放到 AWTK 工程能识别的目录，否则预览和打包都会失败。本文件说明工程布局、`project.json` 关键字段、资源生成和最小工程搭建。

## 1. 标准工程结构

```text
my_project/
├── project.json              # 工程描述（AWTK Designer / AWStudio 生成）
├── SConstruct                # 构建脚本（SDK 工程自带）
├── src/                      # C 源码
│   ├── main.c
│   └── pages/
├── design/                   # 设计期资源（源文件）
│   └── default/              # 主题目录，名字与 theme 对应
│       ├── ui/               # 界面 XML
│       │   ├── home_page.xml
│       │   └── dialog_confirm.xml
│       ├── styles/           # 窗体样式 XML
│       │   └── default.xml   # 全局样式（AWTK 只自动加载这一个）
│       ├── images/           # 切图
│       │   ├── x1/
│       │   ├── x2/
│       │   ├── x3/
│       │   ├── x4/
│       │   ├── xx/
│       │   └── svg/
│       ├── fonts/            # 字体
│       │   └── default.ttf
│       └── strings/          # 多语言
│           └── strings.xml
├── res/                      # 打包后的资源（生成物，不要手改）
│   └── assets/
│       └── default/
│           ├── raw/          # 原始资源副本
│           └── inc/          # 生成的 C 常量
├── scripts/
│   ├── update_res.py         # 资源生成入口
│   ├── awtk_locator.py
│   └── ...
├── bin/                      # 可执行文件/模拟器
└── lib/                      # 依赖库
```

> 生成 UI 时只改 `design/`；`res/` 是 `update_res.py` 的产物。

## 2. project.json

关键字段（不同版本略有差异，以工程实际为准）：

```json
{
  "name": "cluster",
  "entry": "home_page",
  "awtkRoot": "${AWTK_SDK_PATH}/awtk",
  "appType": "APP_SIMULATOR",
  "assets": {
    "activedTheme": "default",
    "outputDir": "res",
    "loadFrom": "any",
    "screenDPR": "x1",
    "defaultLanguage": "zh",
    "defaultCountry": "CN",
    "themes": {
      "default": {
        "packaged": true,
        "fonts": {
          "default": {
            "18": "包含的字符...",
            "bpp": "8bits"
          }
        },
        "lcd": {
          "width": "800",
          "height": "480",
          "colorDepth": "16bit",
          "colorFormat": "BGR(A)"
        }
      }
    }
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `entry` | 启动 UI 名（不带 `.xml`），对应 `design/<theme>/ui/<entry>.xml` |
| `awtkRoot` | AWTK SDK 路径，支持 `${AWTK_SDK_PATH}` 环境变量 |
| `assets.activedTheme` | 当前主题目录名 |
| `assets.outputDir` | 资源输出目录，默认 `res` |
| `assets.screenDPR` | 默认资源密度：`x1`/`x2`/`x3`/`x4` |
| `assets.defaultLanguage` / `defaultCountry` | 默认语言 |
| `assets.themes.<theme>.lcd.width/height` | **LCD 分辨率**，生成坐标以它为准 |
| `lcd.colorDepth` / `colorFormat` | 颜色深度/格式，影响色差和切图 |
| `assets.themes.<theme>.fonts.default.<size>` | 字体打包字符集；缺字会导致文字不显示 |
| `assets.themes.<theme>.packaged` | 是否打包进资源 |

读取优先级：

```text
命令行 --lcd > project.json 的 lcd > 询问用户
```

## 3. 主题（theme）

- 主题目录名 = `project.json` 的 `assets.activedTheme` = `preview_ui` 的 `theme=` 参数。
- 默认主题是 `default`。
- 可以有多个主题（`default`、`dark`），共享 `ui/` 或各自独立。
- 切换主题时，样式/图片从对应主题目录读取（`design/<theme>/styles/default.xml`）；UI XML 里不要硬编码资源绝对路径。
- 窗口的 `theme="xxx"` 不是切换全局主题，而是让该窗口额外加载 `design/<当前主题>/styles/xxx.xml` 作为窗口级样式，未命中的样式仍回退到全局 `default.xml`。

## 4. 资源命名与引用

### 4.1 图片

```text
design/default/images/x1/btn_ok_n.png
design/default/images/x2/btn_ok_n.png
design/default/images/svg/speed_needle.svg
```

XML 引用：

```xml
<image image="btn_ok_n"/>
<gauge_pointer image="speed_needle"/>
```

- 不写目录、不写扩展名。
- AWTK 按 `screenDPR` 或运行时 DPI 选择 `x1/x2/x3/x4`。
- 需要缩放的图放 `xx/` 或 `svg/`。

### 4.2 样式

```text
design/default/styles/default.xml
```

- 全局样式统一写在 `styles/default.xml`；AWTK 启动时只把名为 `default` 的样式资源作为全局主题加载。
- 可选窗口专属样式：`theme="xxx"` → `styles/xxx.xml`；未写 `theme` 时按窗口 `name` 找 `styles/<name>.xml`。找不到对应文件时会回退到 `default.xml`。
- 不要按控件拆成 `button.xml`、`dialog.xml`：这些文件不会被自动加载，AWTK 也没有“合并 styles 目录”的机制。
- `.bin` 与 `.xml` 同时存在时 `.bin` 优先，改 XML 后记得删除/重建 `.bin`。
- 样式根标签是控件类型，一个文件里可以并列多个根标签。

### 4.3 字体

```text
design/default/fonts/default.ttf
```

- 字体名默认是 `default`。
- 非默认字体需要在 `project.json` 的 `fonts` 中登记，并在 `assets` 初始化时加载。
- 字体子集只包含登记过的字符；新增中文/特殊符号后必须重新生成字体资源。

### 4.4 字符串

```text
design/default/strings/strings.xml
```

- 多语言文本用 `tr_text` 引用，不要硬编码。
- 单语言项目可直接用 `text`。

## 5. 资源生成 update_res.py

```bash
python scripts/update_res.py all
python scripts/update_res.py style
python scripts/update_res.py image
python scripts/update_res.py ui
python scripts/update_res.py font
python scripts/update_res.py string
python scripts/update_res.py clean
```

- `all`：全部重新生成（最常用）。
- `style` / `image` / `ui` / `font` / `string`：只生成有变化的部分。
- `clean`：清理生成物。
- 可选参数：`dpi`（`x1`/`x2`）、`image_options`（`bgra+bgr565`/`rgba`）。
- 资源生成后输出到 `res/assets/<theme>/raw` 和 `inc`。

> **预览是否需要 `update_res.py` 取决于 preview_ui 构建：**
> - `tools/preview_ui`（key=value）用自定义资源目录，直接读 `design/<theme>/{styles,images,fonts}`，不需要打包。
> - `demos/preview_ui`（AWStudio SDK 1.7.1，位置参数）按 `<res_root>/assets/<theme>/raw/...` 查找资源，`res_root` 必须指向 `res`；没有生成 `res` 或 `res` 已过期时，`preview_ui.py --stage-res` 会把 `design/<theme>` 镜像到 `out/preview_res`。
> - UI XML 始终按命令行路径直接读取，所以只改 UI 布局时不必重新打包。
> - `res` 里的 `styles/default.bin` 优先于 `default.xml`；改样式后必须重新生成或使用 staging。

## 6. 最小可预览工程

只有 UI 文件、没有完整工程时，创建最小结构即可预览：

```text
my_ui/
└── design/
    └── default/
        ├── ui/
        │   └── main.xml
        ├── styles/
        │   └── default.xml
        ├── images/
        │   └── x1/
        └── fonts/
            └── default.ttf
```

`styles/default.xml` 和 `fonts/default.ttf` 可以直接从 SDK 复制：

```text
<AWTK_ROOT>/design/default/styles/default.xml
<AWTK_ROOT>/design/default/fonts/default.ttf
```

预览命令（两种构建的资源根不同）：

```bash
# 新构建 tools/preview_ui（key=value）：res_root 指 design
<AWTK_ROOT>/bin/preview_ui.exe ui=my_ui/design/default/ui/main.xml lcd_w=800 lcd_h=480 res_root=my_ui/design

# 旧构建 demos/preview_ui（位置参数，SDK 1.7.1）：用脚本 staging 出 raw 布局
python <SKILL_DIR>/scripts/preview_ui.py --project my_ui \
    --ui design/default/ui/main.xml --lcd 800x480 --stage-res \
    --screenshot out/preview.png
```

旧构建也可以先自己生成 `<res_root>/assets/default/raw/{styles,images,fonts}`，或运行工程的 `scripts/update_res.py all` 后用 `--res-root my_ui/res`。**不要把旧构建的 `res_root` 直接指向 `design`**：UI 会显示，但样式/图片/字体会全部回退到默认值。

## 7. 新建 UI 文件

1. 在 `design/<theme>/ui/` 下新建 `<name>.xml`。
2. 根标签用 `window`/`dialog` 等。
3. 在代码中 `window_open("<name>")` 打开；如果是 `entry`，改 `project.json` 的 `entry`。
4. 新增样式追加到 `styles/default.xml`（或明确的窗口专属 `<窗口名>.xml`）。
5. 新增切图放到 `images/x1/` 等目录。
6. 重新 `update_res.py all`（编译前）。

## 8. 工程类型

| 类型 | 说明 |
| --- | --- |
| `APP_SIMULATOR` | 模拟器工程，可在 PC 上运行/调试 |
| `PROJECT_WIDGETS_APPLICATION` | 使用 AWTK Designer 控件工程 |
| 裸机/嵌入式工程 | 交叉编译，资源打包成 C 常量 |

`appType` 只影响构建方式，不影响 XML 结构。

## 9. 路径与编码

- 工程路径尽量不含中文/空格；`preview_ui.exe` 对含空格路径需要正确引号。
- XML 用 UTF-8（无 BOM）；Windows 记事本保存的带 BOM UTF-8 也可被 AWTK 读取，但建议统一无 BOM。
- 资源名区分大小写；Windows 文件系统不区分，但打包/上板后可能区分，统一小写最稳。
- `project.json` 的 `awtkRoot` 可用 `${AWTK_SDK_PATH}`；路径分隔符用 `/` 或 `\\`。

## 10. 交付物放在哪

| 交付物 | 位置 |
| --- | --- |
| UI XML | `design/<theme>/ui/*.xml` |
| 样式 XML | `design/<theme>/styles/default.xml`（窗口专属样式才是 `<窗口名>.xml`） |
| 切图 | `design/<theme>/images/x1/...` |
| 字体 | `design/<theme>/fonts/` |
| 设计规格 | 工程根或 `design/` 下 `design_spec.json`（不参与打包） |
| 预览截图/对比图 | `out/` 或临时目录（不要放 `design/`） |
