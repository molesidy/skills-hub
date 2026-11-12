# Context Capsule — <项目名>

> 用途：上下文被压缩/重置后，用这一份恢复项目状态。
> 只写结论与证据路径；**不要**粘贴坐标表、日志、切图全量清单。
> 建议路径：`out/context/capsule.md`（不打包，可随时删除）。
> 更新时机：每完成一个屏幕 / 每次确认或推翻一个假设 / 每次上下文可能被压缩前。

## 1. 项目身份

| 项 | 值 |
| --- | --- |
| 项目名 | <name> |
| 输入资料 | <计划书路径>、<坐标 xlsx 路径>、<切图目录> |
| 输出根目录 | `design/<theme>/` |
| 当前阶段 | <盘点 / 归一化 / 生成 / 校验 / 预览 / 交付> |
| 最后更新 | <YYYY-MM-DD HH:MM> |

## 2. 屏幕参数

| 项 | 值 |
| --- | --- |
| LCD | <w> × <h> |
| 主题 | <theme>（如 `default` / `day` / `night`） |
| dpr | <dpr> |
| 字体 | <字体名> / 默认字号 <n> |
| 坐标基准 | <原始像素 / 设计稿 / 已按 dpr 换算> |

## 3. 屏幕清单

| 屏幕 | 模式 | 输出文件 | 状态 | 备注 |
| --- | --- | --- | --- | --- |
| <main> | day, night | `main_day.xml`、`main_night.xml` | <未开始/生成中/已生成/已校验> | <一句话> |

状态含义：未开始 → 生成中 → 已生成 → 已校验（`--strict-constraints` 通过）→ 已预览。

## 4. 已确认决策

只记录**已经确认**的，不要写猜测：

- [ ] 昼夜模式判定：<依据，例如计划书第 N 页写明 day/night>
- [ ] `<view>` 分组：<哪些控件、容器名、容器矩形来源>
- [ ] 缺失切图：<控件名 → 已省略，写入 .md>
- [ ] 错误切图/坐标：<控件名 → 暂放 + .md 标记>
- [ ] `draw_type` 例外：<控件名 → 非 default 的原因>
- [ ] 命名：未改动任何原始切图文件名
- [ ] 坐标：未做视觉微调，仅单位/缩放换算

## 5. 待确认项

| # | 问题 | 影响 | 需要谁确认 |
| --- | --- | --- | --- |
| 1 | <问题> | <哪个屏幕/控件> | <用户/设计> |

## 6. 已生成产物

| 文件 | 说明 | 对应 .md |
| --- | --- | --- |
| `design/<theme>/ui/<screen>_day.xml` | <控件数> | `design/<theme>/ui/<screen>_day.md` |
| `design/<theme>/styles/default.xml` | <样式数> | — |

## 7. 证据路径（需要时再读，不要预读）

| 资料 | 路径 | 用法 |
| --- | --- | --- |
| 计划书 | <path> | 只读相关页 |
| 坐标表 | <path> | `context_digest.py --screen <name>` |
| 切图 | <path> | `context_digest.py <dir> --top 10` |
| 校验日志 | <path> | `context_digest.py <log> --budget 3000` |

## 8. 下一步

1. <下一步动作，具体到屏幕/命令>
2. <…>

## 9. 恢复指令

```text
1. 读本胶囊
2. python scripts/context_digest.py design_spec.json
3. python scripts/context_digest.py <coords.xlsx> --screen <当前屏幕>
4. 只读当前步骤需要的一份 references/*
5. 继续生成 / 校验，完成后更新本文件
```
