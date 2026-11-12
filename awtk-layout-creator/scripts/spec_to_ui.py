#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate AWTK UI XML from a design_spec.json.

The spec is the single source of truth produced from the mockup/Excel/assets
phase. This script turns it into one XML file per screen, preserving attribute
order and references to styles/images exactly as written.

Example:
    python spec_to_ui.py design_spec.json --out-dir design/default/ui

Spec node fields:
    type, name, x, y, w, h, style, text, children_layout, self_layout,
    floating, attrs{}, inline_style{}, property{}, content, children[],
    layout ("x,y,w,h" shorthand), comment, modes, by_mode, missing,
    missing_reason, skip, omit, review_note, review_kind, review_notes,
    notes, issues
"""

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import awtk_common as common

# Fields handled explicitly; everything else may come from "attrs".
RESERVED = {
    "type", "tag", "name", "x", "y", "w", "h", "style", "text", "content",
    "children_layout", "self_layout", "floating", "children", "attrs",
    "inline_style", "property", "layout", "comment", "source", "file",
    # constraint / annotation fields (never emitted as XML attributes)
    "modes", "by_mode", "missing", "missing_reason", "skip", "omit",
    "review_note", "review_kind", "review_notes", "notes", "issues",
}

LAYOUT_KEYS = ("x", "y", "w", "h")


def xml_escape_text(value):
    return escape(str(value))


def xml_escape_attr(value):
    text = escape(str(value), {'"': "&quot;"})
    # XML attribute-value normalization would turn these into spaces.
    return (text.replace("\r", "&#13;").replace("\n", "&#10;")
            .replace("\t", "&#9;"))


def fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)


def cdata(value):
    text = str(value)
    return "<![CDATA[%s]]>" % text.replace("]]>", "]]]]><![CDATA[>")


def apply_layout_shorthand(node):
    layout = node.get("layout")
    if not layout:
        return
    parts = [part.strip() for part in str(layout).split(",")]
    if len(parts) != 4:
        raise ValueError("layout must be 'x,y,w,h', got %r" % layout)
    for key, value in zip(LAYOUT_KEYS, parts):
        node.setdefault(key, value)


def node_attributes(node):
    apply_layout_shorthand(node)
    attrs = {}

    def put(key, value):
        if value is None or value == "":
            return
        attrs[key] = fmt(value)

    for key in ("name", "x", "y", "w", "h", "style"):
        put(key, node.get(key))
    if "text" in node:
        put("text", node.get("text"))
    for key in ("children_layout", "self_layout", "floating"):
        put(key, node.get(key))

    for key, value in (node.get("attrs") or {}).items():
        put(key, value)

    inline = node.get("inline_style") or {}
    for key, value in inline.items():
        prop = key if key.startswith("style.") else "style." + key
        put(prop, value)

    for key, value in node.items():
        if key in RESERVED:
            continue
        put(key, value)

    # Constraint 1: image widgets always spell out draw_type. "default" is
    # used unless the spec explicitly asks for a special draw type.
    tag = node.get("type") or node.get("tag")
    if tag in common.IMAGE_DRAW_TYPE_WIDGETS and attrs.get("image"):
        attrs.setdefault("draw_type", "default")
    return attrs


def render_properties(node, indent):
    lines = []
    properties = node.get("property")
    if not properties:
        return lines
    if isinstance(properties, dict):
        items = list(properties.items())
    else:
        items = []
        for item in properties:
            if isinstance(item, dict):
                items.append((item.get("name"), item.get("value")))
    for name, value in items:
        if name is None:
            continue
        lines.append('%s<property name="%s">%s</property>'
                     % (indent, xml_escape_attr(name), cdata(value)))
    return lines


def render_node(node, depth, indent_str):
    if not isinstance(node, dict):
        raise ValueError("widget node must be an object, got %r" % (node,))
    if node.get("missing") or node.get("skip") or node.get("omit"):
        # Constraint 3: a missing slice is not placed at all.
        return []
    tag = node.get("type") or node.get("tag")
    if not tag:
        raise ValueError("widget without 'type': %r" % (node,))

    indent = indent_str * depth
    attrs = node_attributes(node)
    attr_text = "".join(' %s="%s"' % (key, xml_escape_attr(value))
                        for key, value in attrs.items())

    children = node.get("children") or []
    properties = render_properties(node, indent + indent_str)
    content = node.get("content")
    comment = node.get("comment")

    lines = []
    if comment:
        lines.append("%s<!-- %s -->" % (indent, str(comment).replace("--", "- -")))

    if not children and not properties and content is None:
        lines.append("%s<%s%s/>" % (indent, tag, attr_text))
        return lines

    lines.append("%s<%s%s>" % (indent, tag, attr_text))
    if content is not None:
        lines.append("%s%s" % (indent + indent_str, xml_escape_text(content)))
    lines.extend(properties)
    for child in children:
        lines.extend(render_node(child, depth + 1, indent_str))
    lines.append("%s</%s>" % (indent, tag))
    return lines


def apply_mode(node, mode):
    """Return a copy of node with mode-specific overrides applied."""
    if not isinstance(node, dict):
        return node
    clone = dict(node)
    override = (node.get("by_mode") or {}).get(mode) if mode else None
    if override:
        for key, value in override.items():
            if key in ("attrs", "inline_style") and isinstance(value, dict):
                merged = dict(clone.get(key) or {})
                merged.update(value)
                clone[key] = merged
            elif key == "children":
                clone["children"] = value
            else:
                clone[key] = value
    children = clone.get("children")
    if children:
        clone["children"] = [apply_mode(child, mode) for child in children]
    return clone


def _collect_by_mode_keys(node, keys=None):
    keys = set() if keys is None else keys
    if not isinstance(node, dict):
        return keys
    for key in (node.get("by_mode") or {}):
        keys.add(key)
    for child in node.get("children") or []:
        _collect_by_mode_keys(child, keys)
    return keys


def normalize_modes(screen, override=None):
    modes = override if override is not None else screen.get("modes")
    if not modes:
        # Constraint 4: if the spec only uses node-level by_mode, infer the
        # modes from it so day/night is never silently collapsed into one XML.
        detected = _collect_by_mode_keys(screen)
        if detected:
            # If either day or night appears, emit both: the mode without an
            # explicit override uses the base node as-is.
            if detected & {"day", "night"}:
                preferred = ["day", "night"]
            else:
                preferred = []
            rest = sorted(mode for mode in detected if mode not in preferred)
            return preferred + rest
        return [None]
    if isinstance(modes, str):
        modes = [item.strip() for item in modes.split(",") if item.strip()]
    return list(modes)


def screen_path(screen, out_dir, single_out=None, mode=None):
    if single_out is not None:
        return Path(single_out)
    name = screen.get("name") or "screen"
    relative = str(screen.get("file") or (name + ".xml"))
    if mode:
        if "{mode}" in relative:
            relative = relative.replace("{mode}", mode)
        else:
            path = Path(relative)
            relative = str(path.with_name("%s_%s%s" % (path.stem, mode, path.suffix)))
    elif "{mode}" in relative:
        raise ValueError("file %r contains {mode} but screen has no modes" % relative)
    path = Path(out_dir) / relative
    if path.suffix.lower() != ".xml":
        path = path.with_suffix(".xml")
    return path


def _note_text(item):
    if item is None:
        return ""
    if isinstance(item, dict):
        return (item.get("text") or item.get("message")
                or item.get("note") or item.get("reason") or "")
    return str(item)


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _coord_text(node):
    return "x=%s y=%s w=%s h=%s" % tuple(
        fmt(node.get(key, "")) for key in ("x", "y", "w", "h"))


class NoteCollector(object):
    """Collects missing / review items for the sibling .md file."""

    def __init__(self, spec, screen):
        self.missing = []
        self.review = []
        self.screen_notes = []
        self._seen = set()

        for item in _as_list(spec.get("missing_images")):
            if isinstance(item, dict):
                name = item.get("widget") or item.get("name") or "?"
                reason = _note_text(item) or "切图缺失"
            else:
                name, reason = str(item), "切图缺失"
            self._add_missing(name, "", "", reason)
        for item in _as_list(spec.get("review_notes")):
            self.screen_notes.append(_note_text(item))
        for item in _as_list(screen.get("review_notes")):
            self.screen_notes.append(_note_text(item))

    def _add_missing(self, name, tag, coords, reason):
        # Widget names are unique in a screen, so merge by name: the top-level
        # missing_images entry and the node-level missing flag describe the
        # same widget with different wording.
        for item in self.missing:
            if item["name"] == name:
                if coords and not item["coords"]:
                    item["coords"] = coords
                if tag and not item["type"]:
                    item["type"] = tag
                if reason and not item["reason"]:
                    item["reason"] = reason
                return
        self.missing.append({"name": name, "type": tag, "coords": coords,
                             "reason": reason})

    def _add_review(self, name, tag, coords, kind, text):
        key = ("review", name, kind, text)
        if key in self._seen:
            return
        self._seen.add(key)
        self.review.append({"name": name, "type": tag, "coords": coords,
                            "kind": kind, "text": text})

    def visit(self, node):
        if not isinstance(node, dict):
            return
        name = node.get("name") or "?"
        tag = node.get("type") or node.get("tag") or "?"
        coords = _coord_text(node)
        if node.get("missing") or node.get("skip") or node.get("omit"):
            self._add_missing(name, tag, coords,
                              node.get("missing_reason")
                              or node.get("review_note") or "切图缺失")
            return  # children of a missing node are not placed either
        if node.get("review_note") or node.get("review_kind"):
            kind = node.get("review_kind") or "review"
            text = (_note_text(node.get("review_note"))
                    or KIND_LABELS.get(kind) or kind)
            self._add_review(name, tag, coords, kind, text)
        for item in _as_list(node.get("issues")):
            if isinstance(item, dict):
                kind = item.get("kind") or item.get("type") or "review"
                text = _note_text(item)
            else:
                kind, text = "review", str(item)
            if text:
                self._add_review(name, tag, coords, kind, text)
        for child in node.get("children") or []:
            self.visit(child)

    def has_notes(self):
        return bool(self.missing or self.review
                    or any(self.screen_notes))


KIND_LABELS = {
    "wrong_image": "切图待确认",
    "wrong_coord": "坐标待确认",
    "missing": "缺失切图",
    "review": "待确认",
}


def write_notes_md(xml_path, spec_path, screen, mode, collector):
    """Write <xml-stem>.md next to the generated XML (constraint 3)."""
    xml_path = Path(xml_path)
    md_path = xml_path.with_suffix(".md")
    lines = [
        "# %s 生成说明" % xml_path.name,
        "",
        "- 规格文件：`%s`" % spec_path,
        "- 界面：`%s`" % (screen.get("name") or "?"),
        "- 模式：`%s`" % (mode or "单一模式"),
        "- 坐标/尺寸：全部按计划书原值写入，未做任何微调。",
        "",
    ]

    lines.append("## 未放置（缺失切图）")
    lines.append("")
    if collector.missing:
        lines.append("| 控件 | 类型 | 计划坐标 | 原因 |")
        lines.append("| --- | --- | --- | --- |")
        for item in collector.missing:
            lines.append("| %s | %s | %s | %s |" % (
                item["name"], item["type"], item["coords"] or "-",
                item["reason"]))
    else:
        lines.append("无。")
    lines.append("")

    lines.append("## 已放置但需确认")
    lines.append("")
    if collector.review:
        lines.append("| 控件 | 类型 | 坐标 | 类型 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in collector.review:
            lines.append("| %s | %s | %s | %s | %s |" % (
                item["name"], item["type"], item["coords"],
                KIND_LABELS.get(item["kind"], item["kind"]), item["text"]))
    else:
        lines.append("无。")
    lines.append("")

    if collector.screen_notes:
        lines.append("## 屏幕级说明")
        lines.append("")
        for text in collector.screen_notes:
            if text:
                lines.append("- %s" % text)
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def build_xml(screens, indent_str="  ", header=True):
    lines = []
    if header:
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    for index, screen in enumerate(screens):
        if index:
            lines.append("")
        lines.extend(render_node(screen, 0, indent_str))
    lines.append("")
    return "\n".join(lines)


def collect_names(node, seen=None):
    seen = {} if seen is None else seen
    if node.get("missing") or node.get("skip") or node.get("omit"):
        return seen
    name = node.get("name")
    if name:
        seen.setdefault(name, 0)
        seen[name] += 1
    for child in node.get("children") or []:
        collect_names(child, seen)
    return seen


def main(argv=None):
    common.setup_stdout()
    parser = argparse.ArgumentParser(
        description="Generate AWTK UI XML files from design_spec.json")
    parser.add_argument("spec", help="path to design_spec.json")
    parser.add_argument("--out-dir", help="output directory for screens without 'file'")
    parser.add_argument("--out", help="write a single screen to this file")
    parser.add_argument("--stdout", action="store_true", help="print XML instead of writing")
    parser.add_argument("--indent", type=int, default=2, help="indent spaces (default 2)")
    parser.add_argument("--no-header", action="store_true", help="omit XML declaration")
    parser.add_argument("--validate", action="store_true",
                        help="run validate_ui.py on generated files")
    parser.add_argument("--modes",
                        help="override screen modes, comma-separated (e.g. day,night)")
    parser.add_argument("--no-notes", action="store_true",
                        help="do not write <xml>.md annotation files")
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print("ERROR: cannot read spec: %s" % exc, file=sys.stderr)
        return 2

    screens = spec.get("screens")
    if not screens:
        print("ERROR: spec has no 'screens'", file=sys.stderr)
        return 2
    if args.out and len(screens) > 1:
        print("ERROR: --out requires a single screen", file=sys.stderr)
        return 2
    if not args.stdout and not args.out and not args.out_dir:
        print("ERROR: --out-dir is required (or use --out/--stdout)", file=sys.stderr)
        return 2

    mode_override = None
    if args.modes:
        mode_override = [item.strip() for item in args.modes.split(",")
                         if item.strip()]

    indent_str = " " * max(0, args.indent)
    written = []
    notes_written = []
    errors = []

    if args.stdout:
        if mode_override or any(normalize_modes(screen) != [None]
                                for screen in screens):
            print("ERROR: --stdout cannot expand day/night modes; "
                  "use --out-dir", file=sys.stderr)
            return 2
        print(build_xml(screens, indent_str, header=not args.no_header))
        return 0

    for screen in screens:
        modes = normalize_modes(screen, mode_override)
        if args.out and len(modes) > 1:
            errors.append("%s: --out cannot expand modes %s"
                          % (screen.get("name") or "screen", modes))
            continue
        for mode in modes:
            try:
                prepared = apply_mode(screen, mode)
                path = screen_path(screen, args.out_dir, args.out, mode)
                path.parent.mkdir(parents=True, exist_ok=True)
                text = build_xml([prepared], indent_str,
                                 header=not args.no_header)
                path.write_text(text, encoding="utf-8")
                names = collect_names(prepared)
                duplicates = sorted(name for name, count in names.items()
                                    if count > 1)
                if duplicates:
                    errors.append("%s: duplicate names: %s"
                                  % (path, ", ".join(duplicates)))
                if not args.no_notes:
                    collector = NoteCollector(spec, prepared)
                    collector.visit(prepared)
                    if collector.has_notes():
                        md_path = write_notes_md(path, args.spec, prepared,
                                                 mode, collector)
                        notes_written.append(str(md_path.resolve()))
                written.append(str(path.resolve()))
            except Exception as exc:
                label = screen.get("name") or "screen"
                if mode:
                    label += "[%s]" % mode
                errors.append("%s: %s" % (label, exc))

    if args.validate and written:
        import subprocess
        for path in written:
            cmd = [sys.executable, str(Path(__file__).resolve().parent / "validate_ui.py"), path,
                   "--strict-constraints"]
            print("validate: %s" % path)
            code = subprocess.call(cmd)
            if code != 0:
                errors.append("validation failed: %s" % path)

    for item in errors:
        print("ERROR: %s" % item, file=sys.stderr)

    if args.json:
        common.json_print({"spec": str(Path(args.spec).resolve()),
                           "outputs": written, "notes": notes_written,
                           "errors": errors})
    else:
        for path in written:
            print("wrote: %s" % path)
        for path in notes_written:
            print("notes: %s" % path)
        if errors:
            print("%d error(s)" % len(errors), file=sys.stderr)
        else:
            print("done: %d file(s)" % len(written))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
