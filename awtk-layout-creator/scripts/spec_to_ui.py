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
    layout ("x,y,w,h" shorthand), comment
"""

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import awtk_common as common

# Fields handled explicitly; everything else may come from "attrs".
RESERVED = {
    "type", "name", "x", "y", "w", "h", "style", "text", "content",
    "children_layout", "self_layout", "floating", "children", "attrs",
    "inline_style", "property", "layout", "comment", "source", "file",
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


def screen_path(screen, out_dir, single_out=None):
    if single_out is not None:
        return Path(single_out)
    name = screen.get("name") or "screen"
    relative = screen.get("file") or (name + ".xml")
    path = Path(out_dir) / relative
    if path.suffix.lower() != ".xml":
        path = path.with_suffix(".xml")
    return path


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

    indent_str = " " * max(0, args.indent)
    written = []
    errors = []

    if args.stdout:
        print(build_xml(screens, indent_str, header=not args.no_header))
        return 0

    for screen in screens:
        try:
            path = screen_path(screen, args.out_dir, args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            text = build_xml([screen], indent_str, header=not args.no_header)
            path.write_text(text, encoding="utf-8")
            names = collect_names(screen)
            duplicates = sorted(name for name, count in names.items() if count > 1)
            if duplicates:
                errors.append("%s: duplicate names: %s" % (path, ", ".join(duplicates)))
            written.append(str(path.resolve()))
        except Exception as exc:
            errors.append("%s: %s" % (screen.get("name") or "screen", exc))

    for item in errors:
        print("ERROR: %s" % item, file=sys.stderr)

    if args.validate and written:
        import subprocess
        for path in written:
            cmd = [sys.executable, str(Path(__file__).resolve().parent / "validate_ui.py"), path]
            print("validate: %s" % path)
            code = subprocess.call(cmd)
            if code != 0:
                errors.append("validation failed: %s" % path)

    if args.json:
        common.json_print({"spec": str(Path(args.spec).resolve()),
                           "outputs": written, "errors": errors})
    else:
        for path in written:
            print("wrote: %s" % path)
        if errors:
            print("%d error(s)" % len(errors), file=sys.stderr)
        else:
            print("done: %d screen(s)" % len(written))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
