# awtk-layout-creator 目录说明

```text
awtk-layout-creator/
├── SKILL.md                          # 技能入口：触发条件、工作流、命令索引
├── scripts/
│   ├── awtk_common.py                # 公共库：SDK 定位、XML 宽松解析、布局、图片、截图
│   ├── read_xlsx.py                  # 纯标准库读取 .xlsx 坐标表
│   ├── spec_to_ui.py                 # design_spec.json -> UI XML（含双模式 / .md 标注）
│   ├── validate_ui.py                # UI XML 校验（含 --strict-constraints）
│   ├── context_digest.py             # 大输入抽取式摘要 / 胶囊草稿 / skill 加载索引
│   ├── preview_ui.py                 # 启动官方 preview_ui + 截图
│   └── compare_images.py             # 效果图 vs 预览图比对
├── references/
│   ├── constraints.md                # 五条硬性约束（最高优先级）
│   ├── context-and-tokens.md         # Token 与上下文压缩、懒加载、胶囊
│   ├── layout-rules.md               # 布局规则
│   ├── widget-catalog.md             # 控件目录
│   ├── style-rules.md                # 样式规则
│   ├── input-formats.md              # 输入格式与 design_spec.json
│   ├── project-structure.md          # AWTK 工程结构
│   ├── preview-and-compare.md        # 预览与比对
│   ├── checklist.md                  # 检查清单
│   └── AWTK开发实践.pdf              # 辅助资料
├── assets/
│   ├── ui_template.xml               # 通用 UI 模板
│   ├── style_template.xml            # 样式模板
│   ├── awtk_2w_cluster_template.xml  # 2W 仪表骨架
│   ├── awtk_2w_cluster_realworld.xml # 真实项目样例（旧式写法，仅参考）
│   ├── design_spec_template.json     # 规格模板
│   └── context_capsule_template.md   # 上下文胶囊模板
├── tests/
│   ├── test_constraints.py           # 五条硬性约束的闭环测试
│   └── test_context_digest.py        # 上下文摘要的闭环测试
└── docs/
    └── README.md                     # 本文件
```

硬性约束见 `references/constraints.md`：图片控件默认 `draw_type="default"`、禁止改切图文件名、缺图不放/错图错坐标照放并写 `.md`、白天黑夜输出两个 XML、同模块控件可用 `<view>` 分组。

`spec_to_ui.py` 的行为：

- 图片类控件自动补 `draw_type="default"`（显式特殊值保留）；
- screen 带 `modes`（或节点只有 `by_mode`）时，输出 `<stem>_day.xml` / `<stem>_night.xml`；生成器会按 `by_mode` 的键自动识别模式；
- 节点带 `missing` / `review_note`，或 spec 带 `missing_images` / `review_notes` 时，在 XML 旁生成同名 `.md`（`--no-notes` 可关闭）。

所有脚本只依赖 Python 3 标准库。Windows 下截图使用 GDI，图片格式转换回退到 PowerShell `System.Drawing`。

`preview_ui.py` 会识别 `preview_ui.exe` 的构建版本并自动选择资源根：旧构建（位置参数）使用打包的 `res/`，缺失或比 `design/` 旧时把 `design/<theme>` 暂存到 `out/preview_res`；新构建（key=value）直接用 `design/`。`--json` 的 `res_layout` 字段说明本次用的是哪种资源根；`out/preview_res` 是临时目录，可随时删除。

`context_digest.py` 的行为（详见 `references/context-and-tokens.md`）：

- 对 xlsx / UI XML / `design_spec.json` / 切图目录 / 日志 / 文本做**抽取式**摘要：只计数、分组、采样、截断，不改写 `name/x/y/w/h/image/style/text`；
- `--screen` / `--grep` 只取当前屏幕或关键字命中项；`--budget` 限制输出字符数，`--top` / `--rows` 限制样本数；
- `--index` 列出 skill 各文件大小、估算 token 与加载建议；
- 处理 `design_spec.json` 时顺带生成 `out/context/capsule.md` 草稿。

快速自检：

```bash
python -m unittest discover -s tests -p "test_*.py"   # 约束 + 摘要闭环测试
python scripts/context_digest.py --index
python scripts/read_xlsx.py --help
python scripts/spec_to_ui.py --help
python scripts/validate_ui.py --help
python scripts/preview_ui.py --help
python scripts/compare_images.py --help
```
