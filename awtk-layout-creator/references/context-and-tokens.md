# Token 与上下文压缩

本文件解决两件事：**不要把大输入整份塞进上下文**，以及**上下文被压缩/重置后还能继续正确布局**。它不改变五条硬性约束；与约束冲突时，以 `constraints.md` 为准。

## 1. 三条原则

1. **按需加载。** 默认只读 `SKILL.md` 和 `constraints.md`；其他参考文件在需要对应能力时再读，读完即用，不要预读全部。
2. **先摘要，后精读。** 大 xlsx / XML / 日志 / 切图目录先跑 `scripts/context_digest.py`，只把摘要放进上下文；需要精确坐标时，再用 `--screen` / `--grep` 取单个屏幕或单个控件。
3. **压缩是抽取，不是改写。** 摘要只允许计数、分组、采样、截断展示；**不得**修改 `name / type / x / y / w / h / image / style / text`。精确坐标只来自原始计划书或 `design_spec.json`。

> 红线：不要用模型“总结”坐标。坐标、资源名、控件名必须逐字保留；摘要只是索引。

## 2. 默认加载层级

| 层级 | 内容 | 何时读 |
| --- | --- | --- |
| Tier 0 | `SKILL.md`、`references/constraints.md` | 每次任务开始 |
| Tier 1 | 当前步骤对应的一份 reference（大输入时含本文件） | 需要该能力时 |
| Tier 2 | `assets/*` 模板、真实项目样例 | 需要骨架/示例时 |
| 禁止 | `references/AWTK开发实践.pdf` 整份 | 永远不要整份读；需要时先 `pdftotext` + 关键词/页码 |

同一轮只读 Tier 1 的一份文件；跨能力时再读第二份。不要为了“保险”把所有 reference 读完。

## 3. 什么时候必须先压缩

| 输入 | 阈值 | 先执行 |
| --- | --- | --- |
| 坐标 xlsx | >100 行或 >20 列 | `python scripts/context_digest.py coords.xlsx` |
| 单个屏幕 | 任意 | `--screen <name> --rows 40` 只取该屏 |
| UI XML | >300 控件 | `python scripts/context_digest.py main_day.xml` |
| 切图目录 | >150 文件 | `python scripts/context_digest.py images --top 20` |
| 预览/校验日志 | >200 行 | `python scripts/context_digest.py build.log --budget 3000` |
| `design_spec.json` | >100 控件 | `python scripts/context_digest.py design_spec.json` |
| PDF / 图片 / 二进制 | 任意 | 不转文本、不整份读 |

## 4. 压缩工具

```bash
# 查看 skill 自身各文件大小与建议加载方式
python scripts/context_digest.py --index

# xlsx：总览（行数、列映射、按屏幕、异常、重名）
python scripts/context_digest.py coords.xlsx

# xlsx：只取一个屏幕的明细（布局时用这个）
python scripts/context_digest.py coords.xlsx --screen main --rows 40

# xlsx：按控件名/关键字定位
python scripts/context_digest.py coords.xlsx --grep temp

# UI XML：控件数、图片资源、样式、缺 draw_type、越界
python scripts/context_digest.py design/default/ui/main_day.xml

# design_spec.json：屏幕/模式/缺失/预计输出，并生成胶囊草稿
python scripts/context_digest.py design_spec.json --out out/context/capsule.md

# 日志：归一化重复行、错误/警告计数、首尾样本
python scripts/context_digest.py build.log --budget 3000

# 切图目录：数量、密度、命名前缀、可疑文件名、同目录重复
python scripts/context_digest.py design/default/images --top 20
```

- `--budget` 控制 md/text 输出字符数，默认 6000；`0` 表示不限制。
- `--top` 控制每个列表的样本数，默认 12；`--rows` 控制过滤后的明细行数，默认 40。
- `--json` 输出结构化摘要（列表仍然有上限），便于脚本消费。
- `--kind` 可强制输入类型：`xlsx/xml/spec/assets/log/text/pdf/image/binary`。

## 5. 上下文胶囊

大项目每轮都重读输入会浪费 token。用一个小文件保存**结论**，而不是原文：

- 位置：`out/context/capsule.md`（`out/` 不参与打包，可随时删除）。
- 模板：`assets/context_capsule_template.md`。
- 生成：`context_digest.py design_spec.json --out out/context/capsule.md` 会给出草稿。
- 更新时机：每完成一个屏幕、每次确认/推翻一个假设、每次上下文可能被压缩前。

胶囊只放：项目身份、LCD/主题/字体、屏幕清单与状态、已确认决策、待确认项、下一步、证据路径。**不要**把坐标表、日志、切图清单粘进去。

## 6. 大输入工作流

```text
1. 盘点：--index 看文件规模；确认哪些输入超过阈值
2. 摘要：context_digest.py 生成总览；先看异常/重名/缺失/模式
3. 分屏：一次只处理一个屏幕，--screen 取该屏明细
4. 归一化：把该屏写进 design_spec.json（精确值），不要凭摘要写坐标
5. 生成/校验：spec_to_ui.py + validate_ui.py --strict-constraints
6. 记录：更新 out/context/capsule.md；清理中间输出
```

**逐屏循环**比“一次性把所有屏幕放进上下文”更省 token，也更少出错。每屏的详细坐标只需在该屏生成时存在；生成完可以丢弃，胶囊只保留结论。

## 7. 压缩时保留什么、丢弃什么

| 保留（逐字） | 可摘要/截断 |
| --- | --- |
| 控件 `name`、`type` | 备注、说明、设计说明长文 |
| `x / y / w / h` 精确值 | 重复表头、空行、合并单元格展开值 |
| `image` 资源名（原始切图名） | 日志中的时间戳、路径、数字 |
| `style` 名、`text` 文案 | 切图目录的全量文件列表 |
| 屏幕/模式/文件映射 | 预览截图元数据 |
| 缺失/错误/待确认项 | 重复错误堆栈 |

- 表格只保留：行数、列映射、按屏幕统计、异常样本、前 N 个名称。
- 日志只保留：归一化后的高频模式、错误/警告计数、首尾各 8 行。
- 切图目录只保留：数量、密度、前缀、可疑命名样本。

## 8. 上下文重置后的恢复顺序

1. 读 `out/context/capsule.md`（如果存在）。
2. `context_digest.py design_spec.json` 看屏幕/模式/缺失/输出。
3. 只读当前屏幕：`context_digest.py coords.xlsx --screen <name>`。
4. 需要规则时再读一份 reference（Tier 1）。
5. 继续生成；完成后更新胶囊。

不要因为“上下文没了”就重新读所有原始资料。

## 9. 常见错误

| 错误 | 后果 | 正确做法 |
| --- | --- | --- |
| 把 `read_xlsx.py --json -` 的整份输出贴进上下文 | 几千行、token 爆炸 | 先 `context_digest.py`，再 `--screen` |
| 一次性读 8 份 reference | 上下文被规则淹没 | 只读当前步骤的一份 |
| 用模型总结坐标 | 坐标漂移，违反约束 3 | 坐标只从原始数据/`design_spec.json` 取 |
| 把 PDF 整份读入 | 9MB+，不可控 | `pdftotext` 后按页/关键词读 |
| 每轮重新列出切图目录 | 重复消耗 | 用 assets digest + 胶囊记录命名规则 |
| 压缩后不更新胶囊 | 下次重置重复劳动 | 每屏完成后更新 |

## 10. 自检

```bash
python scripts/context_digest.py --index
python tests/test_constraints.py
python tests/test_context_digest.py
```

- 摘要输出应远小于原输入；如果接近原输入大小，说明采样/分屏不够。
- 任何“缺失/重名/模式/输出文件”结论都应能在摘要里直接看到。
- 精确坐标出现时，必须能追溯到 `design_spec.json` 或原始 xlsx 的对应行。
