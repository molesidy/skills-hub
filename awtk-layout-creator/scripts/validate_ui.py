#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate an AWTK UI XML file before previewing.

Checks XML well-formedness, duplicate names, resource/style references,
layout syntax, and obvious out-of-parent placement.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import awtk_common as common

ROOT_TAGS = {
    "window", "dialog", "popup", "overlay", "system_bar", "system_bar_bottom",
    "tool_bar", "keyboard", "sprite", "view", "toast",
}

SCROLL_TAGS = {"scroll_view", "list_view", "list_view_h", "pages", "slide_view", "clip_view"}

KNOWN_STYLE_PROPS = {
    "bg_color", "fg_color", "mask_color", "font_name", "font_size", "font_style",
    "text_color", "highlight_font_name", "highlight_font_size", "highlight_text_color",
    "tips_text_color", "text_align_h", "text_align_v", "border_color", "border_width",
    "border", "bg_image", "bg_image_draw_type", "icon", "fg_image", "fg_image_draw_type",
    "spacer", "margin", "margin_left", "margin_right", "margin_top", "margin_bottom",
    "icon_at", "active_icon", "x_offset", "y_offset", "selected_bg_color",
    "selected_fg_color", "selected_text_color", "round_radius", "round_radius_top_left",
    "round_radius_top_right", "round_radius_bottom_left", "round_radius_bottom_right",
    "children_layout", "self_layout", "focusable", "feedback", "clear_bg", "grid_color",
    "even_bg_color", "odd_bg_color",
}

STATES = {
    "normal", "pressed", "over", "disable", "focused", "checked", "unchecked",
    "empty", "empty_focus", "empty_over", "error", "selected", "activated", "changed",
    "normal_of_checked", "pressed_of_checked", "over_of_checked", "disable_of_checked",
    "focused_of_checked", "normal_of_active", "pressed_of_active", "over_of_active",
    "disable_of_active", "focused_of_active",
}

DRAW_TYPES = {
    "default", "center", "icon", "scale", "scale_auto", "scale_down", "scale_w",
    "scale_h", "fill", "repeat", "repeat_x", "repeat_y", "repeat_y_inverse",
    "patch9", "patch3_x", "patch3_y", "patch9_x", "patch9_y", "repeat3_x",
    "repeat3_y", "repeat9",
}


class Report(object):
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {}

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def infer_project(ui_path, project_arg):
    if project_arg:
        return Path(project_arg).resolve()
    ui_path = Path(ui_path).resolve()
    parts = list(ui_path.parts)
    if "design" in parts:
        idx = len(parts) - 1 - list(reversed(parts)).index("design")
        return Path(*parts[:idx])
    return Path.cwd()


def infer_theme(ui_path, project, theme_arg):
    if theme_arg:
        return theme_arg
    ui_path = Path(ui_path).resolve()
    parts = list(ui_path.parts)
    if "design" in parts:
        idx = len(parts) - 1 - list(reversed(parts)).index("design")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return common.project_theme(common.read_project_json(project))


def parse_lcd(value):
    if not value:
        return None
    match = None
    import re
    match = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", value)
    if not match:
        raise argparse.ArgumentTypeError("expected WxH, e.g. 800x480")
    return int(match.group(1)), int(match.group(2))


def active_style_files(root):
    """Style files AWTK actually loads for this window.

    tk_init_assets() loads styles/default.xml; window_base_load_theme_obj()
    additionally loads styles/<window theme>.xml or styles/<window name>.xml.
    Arbitrary files such as button.xml are never merged.
    """
    names = {"default.xml"}
    for attr in ("theme", "name"):
        value = root.get(attr)
        if value:
            names.add(str(value).strip().lower() + ".xml")
    return names


def check_bool(report, context, value):
    if value is None:
        return
    if str(value).lower() not in ("true", "false", "yes", "no", "1", "0"):
        report.warn("%s: expected boolean, got %r" % (context, value))


def _layout_scalar_ok(text):
    text = str(text).strip()
    if not text:
        return False
    head = text.split(":", 1)[0].strip().lower()
    if head in ("c", "center", "m", "middle", "r", "right", "b", "bottom"):
        return True
    if head.endswith("%"):
        head = head[:-1]
    try:
        float(head)
        return True
    except Exception:
        return False


def check_layout_attrs(report, elem, label):
    for key in ("x", "y", "w", "h"):
        value = elem.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            report.warn("%s: empty %s attribute" % (label, key))
            continue
        head = text.split(":", 1)[0].strip().lower()
        if head in ("top", "left"):
            report.warn("%s: %s=%r is not an AWTK alignment keyword; AWTK parses it "
                        "as 0. Use 0 instead" % (label, key, value))
            continue
        if not _layout_scalar_ok(text):
            report.error("%s: invalid %s=%r" % (label, key, value))


def check_children_layout(report, elem, label):
    text = elem.get("children_layout")
    if not text:
        return None
    name, params, errors = common.parse_layout(text)
    for err in errors:
        report.error("%s: children_layout %s" % (label, err))
    if name is None:
        return None
    normalized, unknown = common.normalize_layout_keys(params)
    for key in unknown:
        report.warn("%s: children_layout unknown key %r" % (label, key))
    for key in ("rows", "cols", "width", "height", "x_margin", "y_margin", "margin", "spacing"):
        if key in normalized:
            try:
                number = float(str(normalized[key]).rstrip("%"))
            except Exception:
                report.error("%s: children_layout %s must be numeric, got %r"
                             % (label, key, normalized[key]))
                continue
            if key in ("rows", "cols") and number < 0:
                report.error("%s: children_layout %s must be >= 0" % (label, key))
    for key in ("flexible", "keep_invisible", "keep_disable"):
        if key in normalized:
            check_bool(report, "%s: children_layout %s" % (label, key), normalized[key])
    if "align_h" in normalized and str(normalized["align_h"]).lower() not in ("left", "center", "right"):
        report.error("%s: children_layout align_h must be left/center/right" % label)
    return normalized


def check_self_layout(report, elem, label):
    text = elem.get("self_layout")
    if not text:
        return None
    name, params, errors = common.parse_layout(text)
    for err in errors:
        report.error("%s: self_layout %s" % (label, err))
    if name is None:
        return None
    if name.lower() == "flex":
        report.warn("%s: self_layout='flex(...)' is not available in AWTK 1.7.1 "
                    "(release 2210); verify your SDK before using it" % label)
    for key in params:
        if key.lower() not in ("x", "y", "w", "h"):
            report.warn("%s: self_layout unknown key %r" % (label, key))
        elif not _layout_scalar_ok(params[key]):
            report.error("%s: self_layout invalid %s=%r" % (label, key, params[key]))
    return {k.lower(): v for k, v in params.items()}


def check_inline_style(report, elem, label):
    for key in list(elem.attrib):
        if not key.startswith("style."):
            continue
        rest = key[len("style."):]
        if not rest:
            report.warn("%s: empty inline style attribute" % label)
            continue
        parts = rest.split(".")
        if parts[0] in STATES:
            if len(parts) < 2:
                report.warn("%s: inline style %r has state but no property" % (label, key))
                continue
            prop = parts[1]
        else:
            prop = parts[0]
        if prop not in KNOWN_STYLE_PROPS:
            report.warn("%s: unknown inline style property %r" % (label, prop))


def check_images(report, elem, label, assets):
    if not assets:
        return
    tag = elem.tag
    for attr in common.IMAGE_ATTRS:
        value = elem.get(attr)
        if not value:
            continue
        if "${" in value or value.startswith("#"):
            continue
        if "/" in value or "\\" in value or "." in value:
            report.warn("%s: %s=%r should be a bare resource name "
                        "(no path or extension)" % (label, attr, value))
        if tag in common.PREFIX_IMAGE_WIDGETS and attr == "image":
            if not any(name.startswith(value) for name in assets):
                report.error("%s: no image asset starts with %r" % (label, value))
        else:
            if value not in assets:
                report.error("%s: image asset %r not found under design/<theme>/images"
                             % (label, value))


def resolve_style_props(style_index, tag, style_name):
    bucket = style_index.get(tag) or {}
    return bucket.get(style_name) or {}


def check_styles(report, elem, label, style_index):
    if not style_index:
        return
    explicit = elem.get("style")
    if not explicit:
        return
    tag = elem.tag
    bucket = style_index.get(tag) or {}
    if explicit in bucket:
        return
    if explicit == "default":
        report.warn("%s: no explicit 'default' style for <%s>; built-in fallback will be used"
                    % (label, tag))
    else:
        report.error("%s: style %r not defined for <%s>" % (label, explicit, tag))


def effective_children_layout(elem, style_index):
    text = elem.get("children_layout")
    if text:
        return text
    style_name = elem.get("style") or "default"
    props = resolve_style_props(style_index, elem.tag, style_name)
    return props.get("children_layout")


def check_bounds(report, elem, parent, parent_w, parent_h, style_index, label):
    if parent is None or parent_w is None or parent_h is None:
        return
    if effective_children_layout(parent, style_index) and elem.get("floating") != "true":
        # Parent layout overrides child x/y/w/h; self_layout may still apply.
        if not elem.get("self_layout"):
            return
    self_params = None
    if elem.get("self_layout"):
        name, params, _ = common.parse_layout(elem.get("self_layout"))
        if name and name.lower() == "default":
            self_params = {k.lower(): v for k, v in params.items()}
    if self_params:
        values = {
            "x": self_params.get("x", elem.get("x")),
            "y": self_params.get("y", elem.get("y")),
            "w": self_params.get("w", elem.get("w")),
            "h": self_params.get("h", elem.get("h")),
        }
    else:
        values = {k: elem.get(k) for k in ("x", "y", "w", "h")}

    w = common.resolve_dimension(values.get("w"), parent_w, negative_is_relative=True)
    h = common.resolve_dimension(values.get("h"), parent_h, negative_is_relative=True)
    x = common.resolve_dimension(values.get("x"), parent_w, w)
    y = common.resolve_dimension(values.get("y"), parent_h, h)
    if None in (x, y, w, h):
        return

    eps = 1.0
    if x < -eps or y < -eps:
        report.warn("%s: starts outside parent (x=%.0f, y=%.0f)" % (label, x, y))
    if x + w > parent_w + eps or y + h > parent_h + eps:
        if parent.tag in SCROLL_TAGS:
            return
        report.warn("%s: exceeds parent bounds (child %.0fx%.0f at %.0f,%.0f; "
                    "parent %sx%s)" % (label, w, h, x, y, parent_w, parent_h))


def walk(elem, parent, parent_w, parent_h, report, ctx):
    label = "%s<%s>" % (elem.get("name") + " " if elem.get("name") else "", elem.tag)
    check_layout_attrs(report, elem, label)
    children_layout = check_children_layout(report, elem, label)
    check_self_layout(report, elem, label)
    check_inline_style(report, elem, label)
    check_images(report, elem, label, ctx["assets"])
    check_styles(report, elem, label, ctx["styles"])

    if elem.tag in ("column", "row"):
        kids = [c for c in list(elem) if isinstance(c.tag, str) and c.tag != "property"]
        if kids and not effective_children_layout(elem, ctx["styles"]):
            report.warn("%s: <%s> does not lay out its children by itself; "
                        "add children_layout (or a style with children_layout)"
                        % (label, elem.tag))

    # Geometry of this widget relative to its parent.
    w = common.resolve_dimension(elem.get("w"), parent_w, negative_is_relative=True)
    h = common.resolve_dimension(elem.get("h"), parent_h, negative_is_relative=True)
    if elem is ctx["root"] and (w is None or h is None):
        w = w or ctx["lcd"][0]
        h = h or ctx["lcd"][1]

    check_bounds(report, elem, parent, parent_w, parent_h, ctx["styles"], label)

    for child in list(elem):
        if not isinstance(child.tag, str) or child.tag == "property":
            continue
        walk(child, elem, w, h, report, ctx)


def validate(ui_path, project, theme, lcd, strict=False, check_assets=True):
    report = Report()
    ui_path = Path(ui_path)
    if not ui_path.is_file():
        report.error("file not found: %s" % ui_path)
        return report

    try:
        root = common.parse_xml_file(ui_path)
    except Exception as exc:
        report.error("XML parse failed: %s" % exc)
        return report

    if root.tag not in ROOT_TAGS:
        report.warn("root tag <%s> is not a typical window/dialog root" % root.tag)

    project = Path(project)
    theme = theme or common.project_theme(common.read_project_json(project))

    assets = set()
    style_index = {}
    if check_assets:
        try:
            assets, image_files = common.asset_index(project, theme)
            report.stats["image_files"] = len(image_files)
            if not assets:
                report.warn("no images found under design/%s/images" % theme)
        except Exception as exc:
            report.warn("cannot index images: %s" % exc)
        try:
            style_index, style_files, skipped = common.style_index(
                project, theme, only_files=active_style_files(root))
            report.stats["style_files"] = len(style_files)
            if not style_index:
                report.warn("no styles found under design/%s/styles" % theme)
            for path in skipped:
                try:
                    shown = path.relative_to(project)
                except Exception:
                    shown = path
                report.warn("%s is not loaded by AWTK for this window; only "
                            "styles/default.xml and window-specific <name>.xml are loaded"
                            % shown)
        except Exception as exc:
            report.warn("cannot index styles: %s" % exc)

    if not lcd:
        project_data = common.read_project_json(project)
        lcd = common.project_lcd(project_data, theme) or (800, 480)
        if not common.project_lcd(project_data, theme):
            report.warn("LCD size not found in project.json; assuming 800x480")

    # Duplicate names.
    names = {}
    for widget in [root] + list(common.iter_widgets(root)):
        name = widget.get("name")
        if name:
            names.setdefault(name, []).append(widget.tag)
    for name, tags in names.items():
        if len(tags) > 1:
            report.error("duplicate widget name %r (%s)" % (name, ", ".join(tags)))

    report.stats["widgets"] = 1 + len(list(common.iter_widgets(root)))
    report.stats["lcd"] = "%dx%d" % lcd

    ctx = {"assets": assets, "styles": style_index, "root": root, "lcd": lcd}
    walk(root, None, lcd[0], lcd[1], report, ctx)
    report.stats["errors"] = len(report.errors)
    report.stats["warnings"] = len(report.warnings)
    return report


def main(argv=None):
    common.setup_stdout()
    parser = argparse.ArgumentParser(description="Validate an AWTK UI XML file")
    parser.add_argument("ui", help="path to the UI XML")
    parser.add_argument("--project", help="project root (default: inferred from design/ path)")
    parser.add_argument("--theme", help="theme name")
    parser.add_argument("--lcd", type=parse_lcd, help="LCD size, e.g. 800x480")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    parser.add_argument("--no-images", action="store_true", help="skip image checks")
    parser.add_argument("--no-styles", action="store_true", help="skip style checks")
    args = parser.parse_args(argv)

    project = infer_project(args.ui, args.project)
    theme = infer_theme(args.ui, project, args.theme)
    report = validate(args.ui, project, theme, args.lcd,
                      strict=args.strict, check_assets=not (args.no_images and args.no_styles))

    if args.json:
        common.json_print({
            "file": str(Path(args.ui)),
            "project": str(project),
            "theme": theme,
            "stats": report.stats,
            "errors": report.errors,
            "warnings": report.warnings,
            "ok": not report.errors and not (args.strict and report.warnings),
        })
    else:
        print("AWTK UI validation")
        print("  file:    %s" % Path(args.ui))
        print("  project: %s" % project)
        print("  theme:   %s" % theme)
        print("  stats:   %s" % json.dumps(report.stats, ensure_ascii=False))
        if report.errors:
            print("\nERRORS (%d):" % len(report.errors))
            for item in report.errors:
                print("  - %s" % item)
        if report.warnings:
            print("\nWARNINGS (%d):" % len(report.warnings))
            for item in report.warnings:
                print("  - %s" % item)
        if not report.errors and not report.warnings:
            print("\nOK: no problems found.")
        elif not report.errors:
            print("\nOK with warnings.")

    if report.errors or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
