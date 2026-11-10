# awtk-layout-creator 目录说明

```text
awtk-layout-creator/
├── SKILL.md                          # 技能入口：触发条件、工作流、命令索引
├── scripts/
│   ├── awtk_common.py                # 公共库：SDK 定位、XML 宽松解析、布局、图片、截图
│   ├── read_xlsx.py                  # 纯标准库读取 .xlsx 坐标表
│   ├── spec_to_ui.py                 # design_spec.json -> UI XML
│   ├── validate_ui.py                # UI XML 校验
│   ├── preview_ui.py                 # 启动官方 preview_ui + 截图
│   └── compare_images.py             # 效果图 vs 预览图比对
├── references/
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
│   └── design_spec_template.json     # 规格模板
└── docs/
    └── README.md                     # 本文件
```

所有脚本只依赖 Python 3 标准库。Windows 下截图使用 GDI，图片格式转换回退到 PowerShell `System.Drawing`。

`preview_ui.py` 会识别 `preview_ui.exe` 的构建版本并自动选择资源根：旧构建（位置参数）使用打包的 `res/`，缺失或比 `design/` 旧时把 `design/<theme>` 暂存到 `out/preview_res`；新构建（key=value）直接用 `design/`。`--json` 的 `res_layout` 字段说明本次用的是哪种资源根；`out/preview_res` 是临时目录，可随时删除。

快速自检：

```bash
python scripts/read_xlsx.py --help
python scripts/spec_to_ui.py --help
python scripts/validate_ui.py --help
python scripts/preview_ui.py --help
python scripts/compare_images.py --help
```
