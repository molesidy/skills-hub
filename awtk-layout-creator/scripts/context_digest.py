#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compress large inputs into a small, layout-safe digest.

This is the skill's context-compression tool. It is extractive: it counts,
groups, samples and caps list sizes. It never rewrites coordinates, widget
names, image resource names or style names. Use it before reading a large
xlsx / XML / log / asset folder into the model context.

Examples:
    python scripts/context_digest.py --index
    python scripts/context_digest.py coords.xlsx
    python scripts/context_digest.py coords.xlsx --screen main --top 12
    python scripts/context_digest.py coords.xlsx --grep temp --rows 40
    python scripts/context_digest.py design/default/ui/main_day.xml
    python scripts/context_digest.py design_spec.json --out out/context/capsule.md
    python scripts/context_digest.py design/default/images --top 20
    python scripts/context_digest.py build.log --budget 3000
"""

import argparse
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

# Direct execution with -I should still find sibling scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import awtk_common as common  # noqa: E402
import read_xlsx as xlsx  # noqa: E402
import spec_to_ui as spec  # noqa: E402

DEFAULT_BUDGET = 6000
DEFAULT_TOP = 12
DEFAULT_ROWS = 40
TEXT_SAMPLE_BYTES = 2 * 1024 * 1024

CJK_RE = re.compile(r"[㐀-䶿一-鿿　-〿＀-￯]")
NUMBER_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
SUSPICIOUS_RE = re.compile(r"[^A-Za-z0-9_]")

COLUMN_ALIASES = {
    "name": ("name", "名称", "控件名", "控件名称", "id", "widget", "控件"),
    "type": ("type", "类型", "控件类型", "widgettype", "widget_type", "类别"),
    "x": ("x", "left", "左边", "左边距"),
    "y": ("y", "top", "上边", "上边距"),
    "w": ("w", "width", "宽", "宽度"),
    "h": ("h", "height", "高", "高度"),
    "image": ("image", "图片", "切图", "资源", "图片名", "切图名"),
    "parent": ("parent", "父控件", "父容器", "容器", "parentname"),
    "screen": ("screen", "页面", "界面", "page", "screenname"),
    "text": ("text", "文本", "文字", "内容"),
    "style": ("style", "样式"),
    "note": ("note", "备注", "说明"),
}

LEVEL_RE = re.compile(r"\b(error|warn|warning|fail|failed|fatal)\b|错误|失败|警告|异常", re.I)
LAYOUT_KEYWORDS = {"c", "m", "center", "middle", "r", "b", "right", "bottom"}


def is_layout_keyword(value):
    return str(value or "").strip().lower() in LAYOUT_KEYWORDS


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text):
    """Rough token estimate: CJK ~1 token/char, ASCII ~4 chars/token."""
    cjk = len(CJK_RE.findall(text))
    other = max(0, len(text) - cjk)
    return int(math.ceil(cjk + other / 4.0))


def human_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d %s" % (value, unit)
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%d B" % size


def clip(value, limit=60):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def table_cell(value, limit=40):
    return clip(value, limit).replace("|", "\\|")


def render_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(table_cell(value) for value in row) + " |")
    return lines


def normalize_header(value):
    return (str(value or "").strip().lower()
            .replace(" ", "").replace("_", "").replace("-", ""))


def build_mapping(headers):
    normalized = {}
    for header in headers:
        normalized.setdefault(normalize_header(header), header)
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = normalize_header(alias)
            if key in normalized:
                mapping[canonical] = normalized[key]
                break
    return mapping


def as_number(value):
    """Return a plain pixel number, or None for %, keywords and text."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.endswith("%"):
        return None
    if NUMBER_RE.match(text):
        try:
            return float(text)
        except ValueError:
            return None
    return None


def is_binary(path):
    try:
        with open(path, "rb") as handle:
            return b"\x00" in handle.read(8192)
    except Exception:
        return True


def read_text_sample(path, max_bytes=TEXT_SAMPLE_BYTES):
    size = path.stat().st_size
    if size <= max_bytes:
        return path.read_text(encoding="utf-8", errors="replace"), False
    half = max_bytes // 2
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        head = handle.read(half)
    with open(path, "rb") as handle:
        handle.seek(-half, os.SEEK_END)
        tail = handle.read().decode("utf-8", errors="replace")
    return head + "\n... [middle omitted for context] ...\n" + tail, True


def detect_kind(path):
    if path.is_dir():
        return "assets"
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".xml":
        return "xml"
    if suffix == ".json":
        return "spec"
    if suffix == ".log":
        return "log"
    if suffix == ".pdf":
        return "pdf"
    if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg", ".ttf"):
        return "image"
    if suffix in (".md", ".txt", ".csv", ".ini", ".cfg", ".yaml", ".yml"):
        return "text"
    return "binary" if is_binary(path) else "text"


def section(title, lines):
    return {"title": title, "lines": [line for line in lines if line]}


# ---------------------------------------------------------------------------
# xlsx digest
# ---------------------------------------------------------------------------

def _xlsx_bounds(stats):
    if stats["min_x"] is None:
        return "-"
    return "x=%g..%g y=%g..%g" % (
        stats["min_x"], stats["max_right"], stats["min_y"], stats["max_bottom"])


def digest_xlsx(path, args):
    with zipfile.ZipFile(path) as zf:
        all_sheets = xlsx.sheet_names(zf)
        sheet = xlsx.select_sheet(zf, args.sheet)
        shared = xlsx.read_shared_strings(zf)
        rows, merged = xlsx.read_sheet(
            zf, sheet["path"], shared, fill_merged=not args.no_fill_merged)
        rows = xlsx.trim_rows(rows)
        headers, data_rows = xlsx.make_headers(
            rows, args.header_row, args.no_header)
        dict_rows = xlsx.to_dict_rows(headers, data_rows)

    mapping = build_mapping(headers)
    has_coords = any(key in mapping for key in ("x", "y", "w", "h"))
    records = []
    for row in dict_rows:
        record = {key: row.get(header) for key, header in mapping.items()}
        record["_raw"] = row
        records.append(record)

    notes = []
    filtered = records
    if args.screen:
        needle = args.screen.lower()
        if "screen" in mapping:
            filtered = [r for r in records
                        if needle in str(r.get("screen") or "").lower()]
            if not filtered:
                notes.append("`--screen %s` 没有匹配行；可用 `--grep` 按名称搜索"
                             % args.screen)
        elif needle == str(sheet["name"]).lower():
            notes.append("该表没有 screen 列，按工作表名匹配，保留全部行")
        else:
            notes.append("该表没有 screen 列，`--screen` 已忽略")
    if args.grep:
        needle = args.grep.lower()
        filtered = [r for r in filtered
                    if needle in " ".join(
                        str(value) for value in (r.get("_raw") or {}).values()
                        if value is not None).lower()]
        if not filtered:
            notes.append("`--grep %s` 没有匹配行" % args.grep)

    type_counts = Counter()
    name_counts = Counter()
    screen_stats = {}
    missing_name = missing_coord = non_numeric = 0
    negative_wh = percent_values = image_without_ref = 0
    for record in filtered:
        name = record.get("name")
        if name in (None, ""):
            missing_name += 1
        else:
            name_counts[str(name).strip()] += 1

        tag = str(record.get("type") or "?").strip()
        type_counts[tag] += 1

        screen_name = str(record.get("screen") or "all").strip() or "all"
        stats = screen_stats.setdefault(screen_name, {
            "rows": 0, "types": Counter(), "images": set(),
            "min_x": None, "min_y": None, "max_right": None, "max_bottom": None,
        })
        stats["rows"] += 1
        stats["types"][tag] += 1
        if record.get("image"):
            stats["images"].add(str(record.get("image")))

        x = as_number(record.get("x"))
        y = as_number(record.get("y"))
        w = as_number(record.get("w"))
        h = as_number(record.get("h"))
        if has_coords and any(value in (None, "") for value in
                              (record.get("x"), record.get("y"),
                               record.get("w"), record.get("h"))):
            missing_coord += 1
        for key in ("x", "y", "w", "h"):
            raw = record.get(key)
            if raw in (None, ""):
                continue
            if str(raw).strip().endswith("%"):
                percent_values += 1
            elif (as_number(raw) is None and ":" not in str(raw)
                  and not is_layout_keyword(raw)):
                non_numeric += 1
        if w is not None and w < 0 or h is not None and h < 0:
            negative_wh += 1
        if tag in ("image", "image_value", "image_animation") and not record.get("image"):
            image_without_ref += 1
        if None not in (x, y, w, h) and w > 0 and h > 0:
            for key, value in (("min_x", x), ("min_y", y)):
                if stats[key] is None or value < stats[key]:
                    stats[key] = value
            right, bottom = x + w, y + h
            if stats["max_right"] is None or right > stats["max_right"]:
                stats["max_right"] = right
            if stats["max_bottom"] is None or bottom > stats["max_bottom"]:
                stats["max_bottom"] = bottom

    duplicates = sorted((name, count) for name, count in name_counts.items()
                        if count > 1)

    summary = {
        "sheet": sheet["name"],
        "rows": len(records),
        "filtered": len(filtered),
        "columns": len(headers),
        "screens": len(screen_stats),
        "duplicates": len(duplicates),
    }

    sections = [
        section("工作表", [
            "- 文件：`%s`" % path,
            "- 工作表：`%s`（全部：%s）" % (sheet["name"], ", ".join(all_sheets)),
            "- 行数：%d（过滤后 %d）；列数：%d；合并单元格：%d"
            % (len(records), len(filtered), len(headers), len(merged)),
        ]),
    ]

    mapped = ["%s→`%s`" % (key, header) for key, header in mapping.items()]
    unmapped = [header for header in headers if header not in mapping.values()]
    sections.append(section("列映射", [
        "- 已识别：" + ("，".join(mapped) if mapped else "无"),
        "- 未识别：%s" % (clip("、".join(unmapped), 120) if unmapped else "无"),
    ]))

    if screen_stats:
        rows_out = []
        for name, stats in sorted(screen_stats.items(),
                                  key=lambda item: (-item[1]["rows"], item[0]))[: args.top]:
            top_types = ", ".join("%s×%d" % (tag, count)
                                  for tag, count in stats["types"].most_common(4))
            rows_out.append([name, stats["rows"], top_types,
                             len(stats["images"]), _xlsx_bounds(stats)])
        sections.append(section("按屏幕", render_table(
            ["screen", "rows", "types", "images", "bounds"], rows_out)))
        if len(screen_stats) > args.top:
            sections.append(section("按屏幕（其余）", [
                "- 另有 %d 个屏幕未展开；用 `--screen <name>` 查看"
                % (len(screen_stats) - args.top)]))

    issue_lines = [
        "- 缺 name：%d" % missing_name,
        "- 缺 x/y/w/h：%d" % missing_coord,
        "- 非数字坐标：%d；百分比值：%d" % (non_numeric, percent_values),
        "- 负 w/h（相对父尺寸）：%d" % negative_wh,
        "- 图片控件缺 image 引用：%d" % image_without_ref,
    ]
    if duplicates:
        issue_lines.append("- 重名：%s" % clip(
            "、".join("%s×%d" % pair for pair in duplicates[: args.top]), 160))
    sections.append(section("异常", issue_lines))

    if name_counts:
        names = [name for name, _ in name_counts.most_common(args.top)]
        sections.append(section("名称样本", [
            "- 前 %d 个：%s" % (len(names), clip("、".join(names), 240)),
        ]))

    if args.screen or args.grep:
        detail = []
        for record in filtered[: args.rows]:
            detail.append([
                record.get("name"), record.get("type"),
                record.get("x"), record.get("y"), record.get("w"), record.get("h"),
                record.get("image"), record.get("parent"),
                record.get("screen"), record.get("text"),
            ])
        sections.append(section("行明细（过滤后，最多 %d 行）" % args.rows,
                                render_table(
                                    ["name", "type", "x", "y", "w", "h",
                                     "image", "parent", "screen", "text"],
                                    detail)))
        if len(filtered) > args.rows:
            sections.append(section("行明细（截断）", [
                "- 还有 %d 行未显示；缩小 `--screen/--grep` 或提高 `--rows`"
                % (len(filtered) - args.rows)]))

    if notes:
        sections.append(section("提示", ["- " + note for note in notes]))

    return {"path": str(path), "kind": "xlsx", "summary": summary,
            "sections": sections}


# ---------------------------------------------------------------------------
# UI XML digest
# ---------------------------------------------------------------------------

def _walk_nodes(node):
    yield node
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from _walk_nodes(child)


def _node_images(node):
    images = set()
    for item in _walk_nodes(node):
        for key in ("image",):
            value = item.get(key)
            if value:
                images.add(str(value))
        for key in common.IMAGE_ATTRS:
            value = (item.get("attrs") or {}).get(key)
            if value:
                images.add(str(value))
        for override in (item.get("by_mode") or {}).values():
            for key in common.IMAGE_ATTRS:
                value = (override.get("attrs") or {}).get(key)
                if value:
                    images.add(str(value))
    return images


def _node_count(node):
    return 1 + sum(_node_count(child) for child in node.get("children") or []
                   if isinstance(child, dict))


def digest_xml(path, args):
    root = common.parse_xml_file(path)
    widgets = [root] + list(common.iter_widgets(root))
    tag_counts = Counter(widget.tag for widget in widgets)
    names = [widget.get("name") for widget in widgets if widget.get("name")]
    duplicate_names = sorted((name, count) for name, count in
                             Counter(names).items() if count > 1)

    images = set()
    missing_draw_type = []
    styles = set()
    missing_names = 0
    for widget in widgets:
        if not widget.get("name"):
            missing_names += 1
        for key in common.IMAGE_ATTRS:
            value = widget.get(key)
            if value and "${" not in value and not value.startswith("#"):
                images.add(str(value))
        if widget.tag in common.IMAGE_DRAW_TYPE_WIDGETS and widget.get("image"):
            if not widget.get("draw_type"):
                missing_draw_type.append(widget.get("name") or widget.tag)
        if widget.get("style"):
            styles.add(str(widget.get("style")))

    root_w = as_number(root.get("w"))
    root_h = as_number(root.get("h"))
    top_right = top_bottom = None
    unresolved = 0
    for child in list(root):
        if not isinstance(child.tag, str) or child.tag == "property":
            continue
        w = common.resolve_dimension(child.get("w"), root_w, negative_is_relative=True)
        h = common.resolve_dimension(child.get("h"), root_h, negative_is_relative=True)
        x = common.resolve_dimension(child.get("x"), root_w, w)
        y = common.resolve_dimension(child.get("y"), root_h, h)
        if None in (x, y, w, h):
            unresolved += 1
            continue
        top_right = x + w if top_right is None else max(top_right, x + w)
        top_bottom = y + h if top_bottom is None else max(top_bottom, y + h)

    summary = {
        "root": "%s:%s" % (root.tag, root.get("name") or "?"),
        "widgets": len(widgets),
        "tags": len(tag_counts),
        "images": len(images),
        "duplicates": len(duplicate_names),
    }
    sections = [
        section("概览", [
            "- 文件：`%s`" % path,
            "- 根控件：`%s`，name=`%s`，w=%s h=%s"
            % (root.tag, root.get("name") or "?", root.get("w"), root.get("h")),
            "- 控件数：%d；标签种类：%d；最大层级：%d"
            % (len(widgets), len(tag_counts), _max_depth(root)),
            "- 缺 name 控件：%d；重名：%s"
            % (missing_names,
               clip("、".join("%s×%d" % pair for pair in duplicate_names[: args.top]), 160)
               if duplicate_names else "无"),
        ]),
        section("控件类型", render_table(
            ["tag", "count"],
            [[tag, count] for tag, count in tag_counts.most_common(args.top)])),
    ]
    if images:
        sample = sorted(images)[: args.top]
        sections.append(section("图片资源", [
            "- 唯一资源数：%d" % len(images),
            "- 样本：%s" % clip("、".join(sample), 260),
        ]))
    if styles:
        sections.append(section("样式引用", [
            "- 唯一命名样式：%d" % len(styles),
            "- 样本：%s" % clip("、".join(sorted(styles)[: args.top]), 200),
        ]))
    issue_lines = []
    if missing_draw_type:
        issue_lines.append("- 缺 draw_type 的图片控件：%s"
                           % clip("、".join(missing_draw_type[: args.top]), 200))
    if unresolved:
        issue_lines.append("- 顶层控件无法解析坐标：%d" % unresolved)
    if top_right is not None and root_w is not None and top_right > root_w + 1:
        issue_lines.append("- 顶层右边界 %g 超出根宽 %g" % (top_right, root_w))
    if top_bottom is not None and root_h is not None and top_bottom > root_h + 1:
        issue_lines.append("- 顶层下边界 %g 超出根高 %g" % (top_bottom, root_h))
    if issue_lines:
        sections.append(section("风险", issue_lines))

    return {"path": str(path), "kind": "xml", "summary": summary,
            "sections": sections}


def _max_depth(elem, depth=1):
    children = [child for child in list(elem)
                if isinstance(child.tag, str) and child.tag != "property"]
    if not children:
        return depth
    return max(_max_depth(child, depth + 1) for child in children)


# ---------------------------------------------------------------------------
# design_spec.json digest
# ---------------------------------------------------------------------------

def _predicted_outputs(screen):
    name = screen.get("name") or "screen"
    relative = str(screen.get("file") or (name + ".xml"))
    modes = spec.normalize_modes(screen)
    if modes == [None]:
        return [relative]
    outputs = []
    for mode in modes:
        path = Path(relative)
        if "{mode}" in relative:
            outputs.append(relative.replace("{mode}", mode))
        else:
            outputs.append(str(path.with_name(
                "%s_%s%s" % (path.stem, mode, path.suffix))))
    return outputs


def _screen_issues(screen):
    missing = review = 0
    for node in _walk_nodes(screen):
        if node.get("missing") or node.get("skip") or node.get("omit"):
            missing += 1
        elif node.get("review_note") or node.get("review_kind") or node.get("issues"):
            review += 1
    return missing, review


def _generic_json_digest(path, data):
    if isinstance(data, dict):
        keys = list(data.keys())
    elif isinstance(data, list):
        keys = ["[list length=%d]" % len(data)]
    else:
        keys = [type(data).__name__]
    text = json.dumps(data, ensure_ascii=False)
    return {"path": str(path), "kind": "spec",
            "summary": {"json_keys": len(keys), "chars": len(text)},
            "sections": [
                section("JSON 概览", [
                    "- 顶层键：%s" % clip("、".join(keys), 200),
                    "- 字符数：%d（约 %d tokens）"
                    % (len(text), estimate_tokens(text)),
                ]),
                section("片段", ["- `%s`" % clip(text, 240)]),
            ]}


def digest_spec(path, args):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"path": str(path), "kind": "spec",
                "summary": {"error": str(exc)},
                "sections": [section("错误", ["- %s" % exc])]}
    if not isinstance(data, dict) or "screens" not in data:
        return _generic_json_digest(path, data)

    project = data.get("project") or {}
    lcd = project.get("lcd") or {}
    design = data.get("design") or {}
    screens = [screen for screen in data.get("screens") or []
               if isinstance(screen, dict)]

    rows = []
    outputs = []
    all_images = set()
    total_missing = total_review = 0
    for screen in screens:
        missing, review = _screen_issues(screen)
        total_missing += missing
        total_review += review
        all_images |= _node_images(screen)
        names = spec.collect_names(screen)
        duplicates = [name for name, count in names.items() if count > 1]
        nodes = _node_count(screen) - 1
        top_types = Counter(
            str((child.get("type") or child.get("tag") or "?"))
            for child in screen.get("children") or [] if isinstance(child, dict))
        screen_outputs = _predicted_outputs(screen)
        outputs.extend(screen_outputs)
        rows.append([
            screen.get("name") or "?",
            screen.get("file") or "-",
            ",".join(str(mode) for mode in spec.normalize_modes(screen) if mode) or "-",
            nodes,
            ", ".join("%s×%d" % pair for pair in top_types.most_common(4)),
            missing, review,
            "、".join(screen_outputs),
            "重名:%s" % clip("、".join(duplicates[:5]), 60) if duplicates else "-",
        ])

    summary = {
        "project": project.get("name") or "?",
        "lcd": "%sx%s" % (lcd.get("w") or "?", lcd.get("h") or "?"),
        "theme": project.get("theme") or "?",
        "screens": len(screens),
        "outputs": len(outputs),
        "images": len(all_images),
        "missing": total_missing,
        "review": total_review,
    }
    sections = [
        section("项目", [
            "- 文件：`%s`" % path,
            "- 项目：`%s`；LCD：%sx%s；主题：`%s`；dpr：%s"
            % (project.get("name") or "?",
               lcd.get("w") or "?", lcd.get("h") or "?",
               project.get("theme") or "?", project.get("dpr", 1)),
            "- 设计稿：`%s`，scale=%s，origin=%s"
            % (design.get("file") or "?", design.get("scale", 1),
               design.get("origin", [0, 0])),
            "- 顶层缺失切图：%d；屏幕级缺失：%d；待确认：%d"
            % (len(data.get("missing_images") or []), total_missing, total_review),
        ]),
        section("屏幕", render_table(
            ["name", "file", "modes", "nodes", "top types", "missing",
             "review", "outputs", "issues"], rows)),
        section("预计输出", ["- `%s`" % output for output in outputs]),
    ]

    capsule = [
        "# Context Capsule",
        "",
        "- 项目：`%s`" % (project.get("name") or "?"),
        "- LCD：%sx%s；主题：`%s`；dpr：%s"
        % (lcd.get("w") or "?", lcd.get("h") or "?",
           project.get("theme") or "?", project.get("dpr", 1)),
        "- 设计稿：`%s`，scale=%s，origin=%s"
        % (design.get("file") or "?", design.get("scale", 1),
           design.get("origin", [0, 0])),
        "- 屏幕清单：",
    ]
    for row in rows:
        capsule.append("  - `%s` → %s；节点 %d；缺失 %d；待确认 %d"
                       % (row[0], row[7], row[3], row[5], row[6]))
    capsule.extend([
        "- 已确认决策：",
        "  - 五条硬性约束（见 constraints.md）",
        "  - 坐标只做单位/缩放换算，不做视觉微调",
        "- 待确认/风险：",
        "  - 缺失切图 %d；错误切图/坐标 %d" % (total_missing, total_review),
        "- 下一步：按屏幕生成 XML，并更新本文件",
        "- 证据路径：`out/preview.png`、`out/compare/`",
    ])
    sections.append(section("Context Capsule（可保存到 out/context/capsule.md）",
                            ["```markdown"] + capsule + ["```"]))

    return {"path": str(path), "kind": "spec", "summary": summary,
            "sections": sections}


# ---------------------------------------------------------------------------
# Asset folder digest
# ---------------------------------------------------------------------------

def digest_assets(path, args):
    files = [item for item in path.rglob("*") if item.is_file()]
    ext_counts = Counter((item.suffix.lower() or "(none)") for item in files)
    density_counts = Counter(item.parent.name for item in files)
    stem_counts = Counter()
    density_stem_counts = Counter()
    suspicious = []
    uppercase = []
    zero_byte = 0
    prefixes = Counter()
    total_size = 0
    for item in files:
        stem = item.stem
        stem_counts[stem] += 1
        density_stem_counts[(item.parent.name, stem)] += 1
        if SUSPICIOUS_RE.search(stem):
            suspicious.append(item.name)
        if re.search(r"[A-Z]", stem):
            uppercase.append(item.name)
        if item.stat().st_size == 0:
            zero_byte += 1
        total_size += item.stat().st_size
        prefix = re.split(r"[_\-\d]", stem, 1)[0] or stem
        prefixes[prefix] += 1

    duplicates = sorted((key, count) for key, count in density_stem_counts.items()
                        if count > 1)
    summary = {
        "files": len(files),
        "unique_stems": len(stem_counts),
        "extensions": len(ext_counts),
        "suspicious": len(suspicious),
        "size": human_size(total_size),
    }
    sections = [
        section("概览", [
            "- 目录：`%s`" % path,
            "- 文件数：%d；唯一文件名主干：%d；总大小：%s"
            % (len(files), len(stem_counts), human_size(total_size)),
            "- 扩展名：%s" % clip(
                "，".join("%s×%d" % pair for pair in ext_counts.most_common(args.top)),
                200),
        ]),
        section("密度目录", render_table(
            ["dir", "files"],
            [[name, count] for name, count in density_counts.most_common(args.top)])),
        section("命名前缀", render_table(
            ["prefix", "files"],
            [[name, count] for name, count in prefixes.most_common(args.top)])),
    ]
    issue_lines = [
        "- 含非 `[A-Za-z0-9_]` 字符：%d%s"
        % (len(suspicious),
           ("；样本：" + clip("、".join(suspicious[: args.top]), 200)) if suspicious else ""),
        "- 含大写字母：%d%s"
        % (len(uppercase),
           ("；样本：" + clip("、".join(uppercase[: args.top]), 200)) if uppercase else ""),
        "- 0 字节文件：%d" % zero_byte,
        "- 同一密度目录内重复主干：%d%s"
        % (len(duplicates),
           ("；" + clip("、".join("%s/%s×%d" % (d, s, c) for (d, s), c in duplicates[: args.top]), 200))
           if duplicates else ""),
    ]
    sections.append(section("风险", issue_lines))
    if files:
        samples = sorted(item.name for item in files)[: args.top]
        sections.append(section("名称样本", ["- " + clip("、".join(samples), 300)]))
        largest = sorted(files, key=lambda item: item.stat().st_size,
                         reverse=True)[: min(5, args.top)]
        sections.append(section("最大文件", [
            "- `%s` %s" % (item.name, human_size(item.stat().st_size))
            for item in largest]))

    return {"path": str(path), "kind": "assets", "summary": summary,
            "sections": sections}


# ---------------------------------------------------------------------------
# Log / text digest
# ---------------------------------------------------------------------------

def _normalize_log_line(line):
    text = line.strip()
    if not text:
        return ""
    text = re.sub(r"[A-Za-z]:\\[^\s\"']+", "<path>", text)
    text = re.sub(r"(?<!\w)/[^\s\"']+", "<path>", text)
    text = re.sub(r"\b[0-9a-fA-F]{8,}\b", "<hex>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", text)
    text = re.sub(r"\s+", " ", text)
    return text[:160]


def digest_log(path, args):
    if is_binary(path):
        return {"path": str(path), "kind": "log",
                "summary": {"binary": True},
                "sections": [section("跳过", [
                    "- 二进制文件，未读入上下文；只检查大小：%s"
                    % human_size(path.stat().st_size)])]}
    text, truncated = read_text_sample(path)
    lines = text.splitlines()
    pattern_counts = Counter()
    examples = {}
    level_count = 0
    for line in lines:
        normalized = _normalize_log_line(line)
        if not normalized:
            continue
        pattern_counts[normalized] += 1
        examples.setdefault(normalized, clip(line, 160))
        if LEVEL_RE.search(line):
            level_count += 1
    summary = {
        "lines": len(lines),
        "unique_patterns": len(pattern_counts),
        "level_lines": level_count,
        "truncated": truncated,
    }
    sections = [
        section("概览", [
            "- 文件：`%s`" % path,
            "- 行数：%d；归一化模式：%d；错误/警告行：%d%s"
            % (len(lines), len(pattern_counts), level_count,
               "；文件过大，已只读首尾" if truncated else ""),
        ]),
        section("高频模式", render_table(
            ["count", "pattern"],
            [[count, clip(pattern, 100)]
             for pattern, count in pattern_counts.most_common(args.top)])),
        section("示例", [
            "- `%s`" % examples[pattern]
            for pattern, _ in pattern_counts.most_common(min(args.top, 5))
            if examples.get(pattern)
        ]),
        section("首部", ["- " + clip(line, 160) for line in lines[:8]]),
        section("尾部", ["- " + clip(line, 160) for line in lines[-8:]]),
    ]
    return {"path": str(path), "kind": "log", "summary": summary,
            "sections": sections}


def digest_text(path, args):
    if is_binary(path):
        return {"path": str(path), "kind": "text",
                "summary": {"binary": True},
                "sections": [section("跳过", [
                    "- 二进制文件，未读入上下文；大小：%s"
                    % human_size(path.stat().st_size)])]}
    text, truncated = read_text_sample(path)
    lines = text.splitlines()
    headings = [line.strip() for line in lines
                if re.match(r"^\s{0,3}(#{1,3}\s|\d+(?:\.\d+)*[、.]\s*)", line)]
    key_lines = [line for line in lines if LEVEL_RE.search(line) or
                 re.search(r"TODO|FIXME|待确认|注意", line, re.I)]
    summary = {"lines": len(lines), "chars": len(text),
               "headings": len(headings), "truncated": truncated}
    sections = [
        section("概览", [
            "- 文件：`%s`" % path,
            "- 行数：%d；字符数：%d；约 %d tokens%s"
            % (len(lines), len(text), estimate_tokens(text),
               "；已只读首尾" if truncated else ""),
        ]),
    ]
    if headings:
        sections.append(section("标题", ["- " + clip(line, 120)
                                        for line in headings[: args.top]]))
    if key_lines:
        sections.append(section("关键行", ["- " + clip(line, 160)
                                         for line in key_lines[: args.top]]))
    sections.append(section("首部", ["- " + clip(line, 160) for line in lines[:8]]))
    sections.append(section("尾部", ["- " + clip(line, 160) for line in lines[-8:]]))
    return {"path": str(path), "kind": "text", "summary": summary,
            "sections": sections}


# ---------------------------------------------------------------------------
# Rendering / budget
# ---------------------------------------------------------------------------

def _summary_line(summary):
    if not summary:
        return ""
    return "- " + "；".join("%s=%s" % (key, clip(value, 80))
                            for key, value in summary.items())


def render_md(items):
    lines = ["# Context Digest", ""]
    for item in items:
        lines.append("## `%s`（%s）" % (item.get("path"), item.get("kind")))
        summary = _summary_line(item.get("summary"))
        if summary:
            lines.append(summary)
        for part in item.get("sections") or []:
            lines.append("")
            lines.append("### " + part["title"])
            lines.extend(part["lines"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_text(items):
    lines = ["Context Digest", ""]
    for item in items:
        lines.append("== %s (%s) ==" % (item.get("path"), item.get("kind")))
        summary = _summary_line(item.get("summary"))
        if summary:
            lines.append(summary)
        for part in item.get("sections") or []:
            lines.append("[%s]" % part["title"])
            lines.extend(part["lines"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def apply_budget(text, budget, hint):
    if not budget or budget <= 0 or len(text) <= budget:
        return text, False
    marker = "\n\n... [已截断到约 %d 字符；%s]\n" % (budget, hint)
    keep = max(0, budget - len(marker))
    cut = text[:keep]
    if "\n" in cut:
        cut = cut.rsplit("\n", 1)[0]
    return cut + marker, True


def digest_path(path, args):
    kind = args.kind if args.kind != "auto" else detect_kind(path)
    try:
        if kind == "xlsx":
            return digest_xlsx(path, args)
        if kind == "xml":
            return digest_xml(path, args)
        if kind == "spec":
            return digest_spec(path, args)
        if kind == "assets":
            return digest_assets(path, args)
        if kind == "log":
            return digest_log(path, args)
        if kind == "pdf":
            return {"path": str(path), "kind": "pdf",
                    "summary": {"bytes": path.stat().st_size},
                    "sections": [section("PDF 未加载", [
                        "- PDF 约 %s；不要整份读入上下文。"
                        % human_size(path.stat().st_size),
                        "- 需要时先 `pdftotext` 提取，再用 `--grep` 或文本编辑器只读相关页。",
                    ])]}
        if kind == "image":
            return {"path": str(path), "kind": "image",
                    "summary": {"bytes": path.stat().st_size},
                    "sections": [section("图片", [
                        "- 图片元数据请用 `scripts/compare_images.py` 或图像工具读取，不要转成文本贴入上下文。",
                    ])]}
        if kind == "text":
            return digest_text(path, args)
        return {"path": str(path), "kind": "binary",
                "summary": {"bytes": path.stat().st_size},
                "sections": [section("跳过", [
                    "- 二进制文件，未读入上下文；大小：%s"
                    % human_size(path.stat().st_size)])]}
    except Exception as exc:
        return {"path": str(path), "kind": kind,
                "summary": {"error": clip(exc, 120)},
                "sections": [section("错误", ["- `%s`" % clip(exc, 240)])]}


# ---------------------------------------------------------------------------
# Skill index
# ---------------------------------------------------------------------------

def _skip_index_entry(item):
    """Skip caches and generated artifacts that say nothing about load cost."""
    parts = set(item.parts)
    if "__pycache__" in parts:
        return True
    return item.suffix.lower() in (".pyc", ".pyo")


def render_skill_index():
    root = Path(__file__).resolve().parents[1]
    targets = ["SKILL.md", "references", "assets", "scripts", "tests", "docs"]
    entries = []
    for target in targets:
        base = root / target
        if base.is_file():
            entries.append(base)
        elif base.is_dir():
            entries.extend(item for item in sorted(base.rglob("*"))
                           if item.is_file() and not _skip_index_entry(item))
    lines = [
        "# Skill Index",
        "",
        "> 只为决定“读不读”而看；不要据此整份读取大文件。",
        "",
        "| file | size | ~tokens | load |",
        "| --- | --- | --- | --- |",
    ]
    for item in entries:
        relative = item.relative_to(root).as_posix()
        size = item.stat().st_size
        suffix = item.suffix.lower()
        if suffix == ".pdf":
            tokens = "-"
            load = "never wholesale"
        elif suffix in (".md", ".txt", ".json", ".xml", ".py"):
            text, _ = read_text_sample(item, max_bytes=20000)
            tokens = "~%d" % estimate_tokens(text) if size <= 20000 else "~%d+" % estimate_tokens(text)
            if relative == "SKILL.md":
                load = "always"
            elif relative == "references/constraints.md":
                load = "always"
            elif relative.startswith("references/context-and-tokens"):
                load = "on demand (large input)"
            elif relative.startswith("references/"):
                load = "on demand"
            elif relative.startswith("scripts/"):
                load = "run, don't read whole"
            elif relative.startswith("tests/"):
                load = "run"
            else:
                load = "on demand"
        else:
            tokens = "-"
            load = "on demand"
        lines.append("| `%s` | %s | %s | %s |"
                     % (relative, human_size(size), tokens, load))
    lines.extend([
        "",
        "## 建议阈值",
        "",
        "| 输入 | 阈值 | 先做什么 |",
        "| --- | --- | --- |",
        "| xlsx | >100 行 / >20 列 | `context_digest.py coords.xlsx` |",
        "| 单个屏幕 | 任意 | `--screen <name> --rows 40` 只取该屏 |",
        "| UI XML | >300 控件 | `context_digest.py main_day.xml` |",
        "| 切图目录 | >150 文件 | `context_digest.py images --top 20` |",
        "| 日志 | >200 行 | `context_digest.py build.log --budget 3000` |",
        "| PDF | 任意 | 不整份读；`pdftotext` 后只读相关页 |",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    common.setup_stdout()
    parser = argparse.ArgumentParser(
        description="Compress large inputs into a layout-safe context digest")
    parser.add_argument("inputs", nargs="*",
                        help="xlsx / xml / json / directory / log / text")
    parser.add_argument("--index", action="store_true",
                        help="show a compact index of skill files and sizes")
    parser.add_argument("--kind", default="auto",
                        choices=("auto", "xlsx", "xml", "spec", "assets",
                                 "log", "text", "pdf", "image", "binary"),
                        help="override input kind")
    parser.add_argument("--sheet", help="xlsx sheet name or 0-based index")
    parser.add_argument("--header-row", type=int, default=1,
                        help="xlsx header row (1-based, default 1)")
    parser.add_argument("--no-header", action="store_true",
                        help="xlsx has no header row")
    parser.add_argument("--no-fill-merged", action="store_true",
                        help="do not fill merged cells")
    parser.add_argument("--screen", help="xlsx: filter rows by screen/页面")
    parser.add_argument("--grep", help="xlsx: filter rows by any cell text")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help="max items per list (default %d)" % DEFAULT_TOP)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help="max detail rows when filtering (default %d)" % DEFAULT_ROWS)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                        help="max output chars for md/text (0 = no limit)")
    parser.add_argument("--format", default="md", choices=("md", "text", "json"),
                        help="output format (default md)")
    parser.add_argument("--json", action="store_true",
                        help="shorthand for --format json")
    parser.add_argument("--out", help="write to this file ('-' for stdout)")
    args = parser.parse_args(argv)

    if args.index:
        text = render_skill_index()
        _emit(text, args.out)
        return 0

    if not args.inputs:
        parser.error("provide at least one input (or use --index)")

    items = []
    for raw in args.inputs:
        path = Path(raw)
        if not path.exists():
            items.append({
                "path": raw, "kind": "missing",
                "summary": {"error": "file not found"},
                "sections": [section("错误", ["- 文件不存在：`%s`" % raw])],
            })
            continue
        items.append(digest_path(path, args))

    fmt = "json" if args.json else args.format
    if fmt == "json":
        payload = {"inputs": items, "budget": args.budget}
        rough = json.dumps(payload, ensure_ascii=False, indent=2)
        payload["est_chars"] = len(rough)
        payload["est_tokens"] = estimate_tokens(rough)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    else:
        text = render_md(items) if fmt == "md" else render_text(items)
        text, truncated = apply_budget(
            text, args.budget,
            "用 --screen/--grep 缩小范围，或提高 --budget")
        header = ("<!-- context_digest: chars=%d est_tokens=%d budget=%d%s -->\n"
                  % (len(text), estimate_tokens(text), args.budget,
                     " truncated" if truncated else ""))
        text = header + text

    _emit(text, args.out)
    return 0


def _emit(text, out):
    if out and out != "-":
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        print("wrote: %s" % out)
    else:
        print(text, end="" if text.endswith("\n") else "\n")


if __name__ == "__main__":
    sys.exit(main())
