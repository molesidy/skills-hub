#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AWTK layout creator - shared helpers.

Stdlib only by default. Pillow is used when available for speed; otherwise
PNG/BMP are decoded here and other formats are converted through PowerShell
(System.Drawing) on Windows.
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

# The preview window title depends on the build:
#   tools/preview_ui  -> "awtk_preview" (APP_NAME)
#   demos/preview_ui  -> "AWTK Simulator" (app_name is NULL; AWTK's default)
PREVIEW_WINDOW_TITLES = ("AWTK Simulator", "awtk_preview")

IMAGE_ATTRS = ("image", "bg_image", "fg_image", "icon", "active_icon")
PREFIX_IMAGE_WIDGETS = ("image_value", "image_animation")


def setup_stdout():
    """Make Chinese output safe on Windows consoles."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# AWTK root / project discovery
# ---------------------------------------------------------------------------

def _looks_like_awtk(path):
    path = Path(path)
    return (path / "bin" / "preview_ui.exe").is_file() or (path / "bin" / "preview_ui").is_file()


def _normalize_awtk(path):
    """Accept either an SDK root (containing awtk/) or an AWTK root."""
    if not path:
        return None
    p = Path(str(path).strip().strip('"')).expanduser()
    if _looks_like_awtk(p):
        return p.resolve()
    inner = p / "awtk"
    if _looks_like_awtk(inner):
        return inner.resolve()
    return None


def _expand_env(text):
    if not text:
        return text

    def repl(match):
        name = match.group(1) or match.group(2)
        return os.environ.get(name, "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", repl, str(text))


def read_project_json(project_dir):
    project_dir = Path(project_dir)
    path = project_dir / "project.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def find_awtk_root(explicit=None, project_dir=None):
    """Locate AWTK root in a predictable order. Returns Path or None."""
    candidates = []

    if explicit:
        candidates.append(explicit)

    for env_name in ("AWTK_SDK_PATH", "AWTK_ROOT", "AWTK_HOME"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(value)
            candidates.append(Path(value) / "awtk")

    project_dir = Path(project_dir) if project_dir else None
    project = read_project_json(project_dir) if project_dir else {}
    awtk_root = project.get("awtkRoot") if isinstance(project, dict) else None
    if awtk_root:
        expanded = _expand_env(awtk_root)
        p = Path(expanded)
        if not p.is_absolute() and project_dir:
            p = project_dir / p
        candidates.append(p)

    common = [
        r"D:/SoftwareHub/AWStudio/AWTK/SDK/awtk",
        r"C:/SoftwareHub/AWStudio/AWTK/SDK/awtk",
        r"D:/SoftwareHub/AWStudio/AWTK/SDK",
        r"C:/SoftwareHub/AWStudio/AWTK/SDK",
        r"C:/awtk",
        r"D:/awtk",
        r"E:/awtk",
    ]
    candidates.extend(common)

    # Vendored SDK inside or above the project.
    if project_dir:
        p = project_dir.resolve()
        for _ in range(5):
            candidates.append(p / "awtk")
            candidates.append(p)
            if p.parent == p:
                break
            p = p.parent

    seen = set()
    for cand in candidates:
        try:
            key = str(cand)
            if key in seen:
                continue
            seen.add(key)
            found = _normalize_awtk(cand)
            if found:
                return found
        except Exception:
            continue
    return None


def find_preview_ui(awtk_root):
    awtk_root = Path(awtk_root)
    for name in ("preview_ui.exe", "preview_ui"):
        p = awtk_root / "bin" / name
        if p.is_file():
            return p
    return None


def preview_cli_style(preview_path):
    """Return 'positional' or 'keyvalue' for a preview_ui binary.

    Two builds exist in the wild:
      demos/preview_ui.c : preview_ui <ui> <w> <h> <res_root> [language] [theme]
      tools/preview_ui.c : preview_ui ui=... lcd_w=... lcd_h=... res_root=...
    Passing the wrong style is silently accepted (old build ignores key=value),
    producing a bogus 320x1 window, so detect the build from its strings.
    """
    try:
        data = Path(preview_path).read_bytes()
    except Exception:
        return "keyvalue"
    if b"ui_file [w] [h] [res root]" in data:
        return "positional"
    return "keyvalue"


def project_theme(project, override=None):
    if override:
        return override
    assets = (project or {}).get("assets", {}) or {}
    return assets.get("activedTheme") or "default"


def project_lcd(project, theme=None):
    assets = (project or {}).get("assets", {}) or {}
    themes = assets.get("themes", {}) or {}
    theme = theme or project_theme(project)
    info = themes.get(theme) or {}
    lcd = info.get("lcd") or {}
    try:
        w = int(lcd.get("width"))
        h = int(lcd.get("height"))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    for info in themes.values():
        lcd = (info or {}).get("lcd") or {}
        try:
            w = int(lcd.get("width"))
            h = int(lcd.get("height"))
            if w > 0 and h > 0:
                return w, h
        except Exception:
            continue
    return None


def project_entry(project):
    return (project or {}).get("entry") or None


def project_language(project, override=None):
    """Return a locale such as 'zh_CN' (used by the old positional preview CLI)."""
    if override:
        return override
    assets = (project or {}).get("assets", {}) or {}
    language = assets.get("defaultLanguage")
    country = assets.get("defaultCountry")
    if language and country:
        return "%s_%s" % (language, country)
    if language:
        return str(language)
    return None


# ---------------------------------------------------------------------------
# Preview resource layouts
#
# AWTK has two preview_ui builds with different asset lookup rules:
#
#   demos/preview_ui (AWStudio SDK 1.7.1): assets_manager's default builder
#       <res_root>/assets/<theme>/raw/{styles,images,fonts,strings}
#     i.e. res_root is the packaged "res" directory.
#
#   tools/preview_ui (newer): custom builder
#       <res_root>/<theme>/{styles,images,fonts,strings}
#     i.e. res_root is the project's "design" directory.
#
# Both read the UI XML itself from the explicit path argument.
# ---------------------------------------------------------------------------

PREVIEW_STAGE_NAME = "preview_res"


def packaged_res_dir(project_dir, theme):
    """Return <project>/res when it contains the packaged raw layout."""
    root = Path(project_dir) / "res"
    if (root / "assets" / theme / "raw").is_dir():
        return root
    return None


def _newest_mtime(path):
    path = Path(path)
    newest = 0.0
    if not path.is_dir():
        return newest
    for item in path.rglob("*"):
        try:
            if item.is_file():
                newest = max(newest, item.stat().st_mtime)
        except OSError:
            pass
    return newest


def packaged_res_is_fresh(project_dir, theme):
    """Heuristic: did update_res.py run after the last design edit?"""
    res = packaged_res_dir(project_dir, theme)
    if res is None:
        return False
    design_theme = Path(project_dir) / "design" / theme
    sources = [design_theme / name for name in ("styles", "images", "fonts", "strings")]
    newest_src = max([_newest_mtime(p) for p in sources] + [0.0])
    newest_res = _newest_mtime(res / "assets" / theme / "raw")
    return newest_res >= newest_src


def _rmtree_force(path):
    path = Path(path)
    if not path.exists():
        return

    def onerror(func, target, exc_info):
        try:
            os.chmod(target, 0o700)
            func(target)
        except Exception:
            pass

    if path.is_dir():
        shutil.rmtree(str(path), onerror=onerror)
    else:
        try:
            path.unlink()
        except OSError:
            pass


def _link_or_copy(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        _rmtree_force(dst)
    try:
        os.link(str(src), str(dst))
    except OSError:
        shutil.copy2(str(src), str(dst))


def _mirror_tree(src, dst):
    """Mirror a theme directory, preferring XML styles over stale .bin files."""
    src = Path(src)
    dst = Path(dst)
    files = [p for p in src.rglob("*") if p.is_file()]
    xml_stems = {p.with_suffix("") for p in files if p.suffix.lower() == ".xml"}
    for path in files:
        if path.suffix.lower() == ".bin" and path.with_suffix("") in xml_stems:
            # design/*.bin is a packaged copy; the XML next to it is the source
            continue
        _link_or_copy(path, dst / path.relative_to(src))


def _overlay_missing(src_root, dst_root):
    """Fill gaps from the packaged raw tree without shadowing design sources."""
    src_root = Path(src_root)
    dst_root = Path(dst_root)
    if not src_root.is_dir():
        return
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        target = dst_root / path.relative_to(src_root)
        if target.exists():
            continue
        if path.suffix.lower() == ".bin" and target.with_suffix(".xml").exists():
            continue
        _link_or_copy(path, target)


def stage_preview_res(project_dir, theme, stage_dir=None):
    """Build a res_root with the old preview_ui layout from design/<theme>.

    The result is <stage_dir>/assets/<theme>/raw/... and can be passed to
    demos/preview_ui as res_root. Files are hard-linked when possible, so
    repeated calls are cheap. Returns None when design/<theme> is missing.
    """
    project_dir = Path(project_dir).resolve()
    design_theme = project_dir / "design" / theme
    if not design_theme.is_dir():
        return None

    stage_dir = Path(stage_dir) if stage_dir else project_dir / "out" / PREVIEW_STAGE_NAME
    raw = stage_dir / "assets" / theme / "raw"
    _rmtree_force(raw)
    raw.mkdir(parents=True, exist_ok=True)

    _mirror_tree(design_theme, raw)

    res = packaged_res_dir(project_dir, theme)
    if res is not None:
        # fill in generated files that do not exist in design (strings bin, ...)
        _overlay_missing(res / "assets" / theme / "raw", raw)

    return stage_dir


# ---------------------------------------------------------------------------
# Lenient XML parsing (AWTK allows on:click / animate:value attributes)
# ---------------------------------------------------------------------------

_NS_ATTR_RE = re.compile(r"(\s)([A-Za-z_][\w.-]*):([A-Za-z_][\w.-]*)(\s*=)")
_STYLE_COLON_TRIPLE_RE = re.compile(
    r"(\s)style:([A-Za-z_][\w.-]*):([A-Za-z_][\w.-]*)(\s*=)")
_STYLE_COLON_SINGLE_RE = re.compile(r"(\s)style:([A-Za-z_][\w.-]*)(\s*=)")


_ENTITY_RE = re.compile(r"&(#\d+|#x[0-9A-Fa-f]+|[A-Za-z_][\w.-]*);")


def _sanitize_attr_chars(text):
    """Escape raw '<' and bare '&' inside quoted attribute values.

    AWTK's own XML parser tolerates values like tr_text="<&quot;en&quot;>",
    but expat/ElementTree does not. Generated files should be valid XML; this
    is only a safety net for reading existing AWTK design files.
    """
    out = []
    i = 0
    n = len(text)
    quote = None
    in_tag = False
    while i < n:
        if text.startswith("<![CDATA[", i):
            end = text.find("]]>", i + 9)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 3])
            i = end + 3
            continue
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 3])
            i = end + 3
            continue
        ch = text[i]
        if quote is not None:
            if ch == quote:
                quote = None
                out.append(ch)
            elif ch == "<":
                out.append("&lt;")
            elif ch == "&":
                match = _ENTITY_RE.match(text, i)
                if match:
                    out.append(match.group(0))
                    i = match.end()
                    continue
                out.append("&amp;")
            else:
                out.append(ch)
        else:
            if ch == "<":
                in_tag = True
                out.append(ch)
            elif ch == ">":
                in_tag = False
                out.append(ch)
            elif ch in ("'", '"') and in_tag:
                quote = ch
                out.append(ch)
            else:
                out.append(ch)
        i += 1
    return "".join(out)


_ATTR_RE = re.compile(r"\s+([A-Za-z_][\w.:-]*)\s*=\s*(\"[^\"]*\"|'[^']*')")


def _dedupe_single_tag(tag):
    if not tag.startswith("<"):
        return tag
    if tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag
    match = re.match(r"<\s*([A-Za-z_][\w.:-]*)", tag)
    if not match:
        return tag
    name = match.group(1)
    body = tag[match.end():].rstrip()
    self_close = body.endswith("/>")
    if self_close:
        body = body[:-2]
    elif body.endswith(">"):
        body = body[:-1]

    attrs = []
    pos = 0
    while True:
        attr = _ATTR_RE.search(body, pos)
        if not attr:
            break
        key, value = attr.group(1), attr.group(2)
        attrs = [(k, v) for (k, v) in attrs if k != key]
        attrs.append((key, value))
        pos = attr.end()
    rendered = "".join(" %s=%s" % (key, value) for key, value in attrs)
    return "<%s%s%s>" % (name, rendered, " /" if self_close else "")


def _dedupe_tag_attrs(text):
    """Drop duplicate attributes inside start tags (AWTK tolerates them)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("<![CDATA[", i):
            end = text.find("]]>", i + 9)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 3])
            i = end + 3
            continue
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 3])
            i = end + 3
            continue
        if text[i] == "<":
            j = i + 1
            quote = None
            while j < n:
                ch = text[j]
                if quote is not None:
                    if ch == quote:
                        quote = None
                elif ch in ("'", '"'):
                    quote = ch
                elif ch == ">":
                    break
                j += 1
            if j >= n:
                out.append(text[i:])
                break
            out.append(_dedupe_single_tag(text[i:j + 1]))
            i = j + 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def lenient_xml_text(text):
    text = _sanitize_attr_chars(text)
    text = _dedupe_tag_attrs(text)
    text = _STYLE_COLON_TRIPLE_RE.sub(
        lambda m: "%sstyle.%s.%s%s" % (m.group(1), m.group(2), m.group(3), m.group(4)),
        text,
    )
    text = _STYLE_COLON_SINGLE_RE.sub(
        lambda m: "%sstyle.%s%s" % (m.group(1), m.group(2), m.group(3)),
        text,
    )

    def repl(match):
        prefix = match.group(2)
        if prefix in ("xml", "xmlns"):
            return match.group(0)
        return "%s%s_%s%s" % (match.group(1), prefix, match.group(3), match.group(4))

    return _NS_ATTR_RE.sub(repl, text)


def parse_xml_roots(path):
    """Parse a file that may contain multiple top-level elements (style files)."""
    import xml.etree.ElementTree as ET

    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    text = lenient_xml_text(text)
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    wrapped = "<awtk_file_root>%s</awtk_file_root>" % text
    root = ET.fromstring(wrapped)
    return [child for child in list(root) if isinstance(child.tag, str)]


def parse_xml_file(path):
    roots = parse_xml_roots(path)
    if not roots:
        raise ValueError("empty XML file: %s" % path)
    return roots[0]


def iter_widgets(elem):
    for child in list(elem):
        if not isinstance(child.tag, str):
            continue
        if child.tag == "property":
            continue
        yield child
        for sub in iter_widgets(child):
            yield sub


def widget_name(elem, fallback="?"):
    return elem.get("name") or fallback


# ---------------------------------------------------------------------------
# Layout parsing
# ---------------------------------------------------------------------------

_LAYOUT_ALIASES = {
    "r": "rows",
    "rows": "rows",
    "c": "cols",
    "cols": "cols",
    "w": "width",
    "width": "width",
    "h": "height",
    "height": "height",
    "x": "x_margin",
    "xm": "x_margin",
    "x_margin": "x_margin",
    "y": "y_margin",
    "ym": "y_margin",
    "y_margin": "y_margin",
    "m": "margin",
    "margin": "margin",
    "s": "spacing",
    "spacing": "spacing",
    "f": "flexible",
    "flexible": "flexible",
    "ki": "keep_invisible",
    "keep_invisible": "keep_invisible",
    "kd": "keep_disable",
    "keep_disable": "keep_disable",
    "a": "align_h",
    "align_h": "align_h",
}

_PAREN_RE = re.compile(r"^\s*([A-Za-z_][\w.-]*)\s*\((.*)\)\s*$")


def parse_layout(text):
    """Parse children_layout / self_layout. Returns (name, dict, errors)."""
    if text is None:
        return None, {}, []
    text = str(text).strip()
    if not text:
        return None, {}, []
    match = _PAREN_RE.match(text)
    if not match:
        return None, {}, ["invalid layout syntax: %r" % text]
    name, body = match.group(1), match.group(2)
    params = {}
    errors = []
    for part in body.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            errors.append("invalid layout item: %r" % part)
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append("empty layout key in %r" % part)
            continue
        params[key] = value
    return name, params, errors


def normalize_layout_keys(params):
    normalized = {}
    unknown = []
    for key, value in params.items():
        full = _LAYOUT_ALIASES.get(key.lower())
        if full is None:
            unknown.append(key)
            normalized[key] = value
        else:
            normalized[full] = value
    return normalized, unknown


def _to_number(value):
    try:
        return float(value)
    except Exception:
        return None


def resolve_dimension(value, parent_dim=None, child_dim=None, negative_is_relative=False):
    """Resolve an AWTK x/y/w/h value to pixels.

    AWTK only treats negative *width/height* as "parent size + value";
    negative x/y stay negative. Set negative_is_relative for w/h.

    Returns float or None when it cannot be resolved (e.g. x="c" without w).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lower = text.lower()

    offset = 0.0
    has_offset = False
    head = lower
    if ":" in lower:
        head, tail = lower.split(":", 1)
        has_offset = True
        tail = tail.strip()
        if tail.endswith("%"):
            num = _to_number(tail[:-1])
            if num is not None and parent_dim is not None:
                offset = parent_dim * num / 100.0
            elif num is not None:
                offset = None
        else:
            num = _to_number(tail)
            offset = num if num is not None else None

    if has_offset and offset is None:
        return None

    if head in ("c", "center", "m", "middle"):
        if parent_dim is None or child_dim is None:
            return None
        return (parent_dim - child_dim) / 2.0 + (offset if has_offset else 0)

    if head in ("r", "right", "b", "bottom"):
        if parent_dim is None or child_dim is None:
            return None
        return parent_dim - child_dim - (offset if has_offset else 0)

    if lower.endswith("%"):
        num = _to_number(lower[:-1])
        if num is None or parent_dim is None:
            return None
        result = parent_dim * num / 100.0
        if num < 0 and negative_is_relative:
            result = parent_dim + result
        return result

    num = _to_number(lower)
    if num is None:
        return None
    if num < 0 and negative_is_relative and parent_dim is not None:
        return parent_dim + num
    if has_offset:
        return num + offset
    return num


def resolve_geometry(elem, parent_w, parent_h):
    """Resolve x/y/w/h for a widget; returns dict with possible None values."""
    w = resolve_dimension(elem.get("w"), parent_w, negative_is_relative=True)
    h = resolve_dimension(elem.get("h"), parent_h, negative_is_relative=True)
    # For x/y centering the child dimension is needed.
    x = resolve_dimension(elem.get("x"), parent_w, w)
    y = resolve_dimension(elem.get("y"), parent_h, h)
    return {"x": x, "y": y, "w": w, "h": h}


# ---------------------------------------------------------------------------
# Project asset/style indexes
# ---------------------------------------------------------------------------

def _theme_dirs(project_dir, theme):
    root = Path(project_dir) / "design"
    dirs = []
    for name in (theme, "default"):
        if name and name not in [d.name for d in dirs]:
            p = root / name
            if p.is_dir():
                dirs.append(p)
    return dirs


def asset_index(project_dir, theme="default"):
    """Return (set of image resource names, list of image files)."""
    names = set()
    files = []
    for theme_dir in _theme_dirs(project_dir, theme):
        images = theme_dir / "images"
        if not images.is_dir():
            continue
        for path in images.rglob("*"):
            if not path.is_file():
                continue
            files.append(path)
            stem = path.name.split(".")[0]
            names.add(stem)
            names.add(path.stem)
    return names, files


def style_index(project_dir, theme="default", only_files=None):
    """Return (style_index, loaded_files, skipped_files).

    AWTK only loads styles/default.xml plus the window-specific file named
    after the window's `theme` or `name`. Pass only_files to model that rule;
    files outside it are returned as skipped (they would not be loaded).
    """
    index = {}
    files = []
    skipped = []
    only_files = {name.lower() for name in only_files} if only_files else None
    for theme_dir in _theme_dirs(project_dir, theme):
        styles = theme_dir / "styles"
        if not styles.is_dir():
            continue
        for path in sorted(styles.glob("*.xml")):
            if only_files is not None and path.name.lower() not in only_files:
                skipped.append(path)
                continue
            files.append(path)
            try:
                roots = parse_xml_roots(path)
            except Exception:
                continue
            for root in roots:
                tag = root.tag
                bucket = index.setdefault(tag, {})
                for style in list(root):
                    if style.tag != "style":
                        continue
                    name = style.get("name") or "default"
                    props = bucket.setdefault(name, {})
                    for key, value in style.attrib.items():
                        props[key] = value
                    for state in list(style):
                        if not isinstance(state.tag, str):
                            continue
                        for key, value in state.attrib.items():
                            props[key] = value
    return index, files, skipped


# ---------------------------------------------------------------------------
# Image loading / writing
# ---------------------------------------------------------------------------

PNG_SIG = b"\x89PNG\r\n\x1a\n"


class ImageData(object):
    __slots__ = ("width", "height", "pixels")

    def __init__(self, width, height, pixels):
        self.width = int(width)
        self.height = int(height)
        self.pixels = pixels

    @property
    def size(self):
        return self.width, self.height


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path):
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIG):
        raise ValueError("not a PNG file: %s" % path)
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    palette = None
    trns = None
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif ctype == b"PLTE":
            palette = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if not width or not height:
        raise ValueError("invalid PNG (no IHDR): %s" % path)
    if bit_depth != 8 or interlace != 0:
        raise ValueError("unsupported PNG (bit depth %s, interlace %s): %s"
                         % (bit_depth, interlace, path))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("unsupported PNG color type %s: %s" % (color_type, path))

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    bpp = channels
    out = bytearray(width * height * channels)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        if src >= len(raw):
            raise ValueError("truncated PNG: %s" % path)
        ftype = raw[src]
        src += 1
        line = bytearray(raw[src:src + stride])
        src += stride
        if len(line) < stride:
            raise ValueError("truncated PNG row: %s" % path)
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        elif ftype != 0:
            raise ValueError("unsupported PNG filter %s: %s" % (ftype, path))
        out[y * stride:(y + 1) * stride] = line
        prev = line

    rgb = bytearray(width * height * 3)
    if color_type == 2:
        rgb[:] = out
    elif color_type == 0:
        for i in range(width * height):
            v = out[i]
            rgb[i * 3:i * 3 + 3] = bytes((v, v, v))
    elif color_type == 3:
        if palette is None:
            raise ValueError("PNG palette missing: %s" % path)
        alpha = trns or b""
        for i in range(width * height):
            idx = out[i]
            r = palette[idx * 3] if idx * 3 < len(palette) else 0
            g = palette[idx * 3 + 1] if idx * 3 + 1 < len(palette) else 0
            b = palette[idx * 3 + 2] if idx * 3 + 2 < len(palette) else 0
            a = alpha[idx] if idx < len(alpha) else 255
            rgb[i * 3] = (r * a + 255 * (255 - a)) // 255
            rgb[i * 3 + 1] = (g * a + 255 * (255 - a)) // 255
            rgb[i * 3 + 2] = (b * a + 255 * (255 - a)) // 255
    elif color_type == 4:
        for i in range(width * height):
            v = out[i * 2]
            a = out[i * 2 + 1]
            rgb[i * 3] = (v * a + 255 * (255 - a)) // 255
            rgb[i * 3 + 1] = rgb[i * 3]
            rgb[i * 3 + 2] = rgb[i * 3]
    elif color_type == 6:
        for i in range(width * height):
            r, g, b, a = out[i * 4:i * 4 + 4]
            rgb[i * 3] = (r * a + 255 * (255 - a)) // 255
            rgb[i * 3 + 1] = (g * a + 255 * (255 - a)) // 255
            rgb[i * 3 + 2] = (b * a + 255 * (255 - a)) // 255
    return ImageData(width, height, rgb)


def read_bmp(path):
    data = Path(path).read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("not a BMP file: %s" % path)
    off_bits = struct.unpack("<I", data[10:14])[0]
    header_size = struct.unpack("<I", data[14:18])[0]
    width = struct.unpack("<i", data[18:22])[0]
    raw_height = struct.unpack("<i", data[22:26])[0]
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]
    if header_size < 40:
        raise ValueError("unsupported BMP header: %s" % path)
    if bpp not in (24, 32) or compression not in (0, 3):
        raise ValueError("unsupported BMP (bpp=%s, compression=%s): %s"
                         % (bpp, compression, path))
    height = abs(raw_height)
    top_down = raw_height < 0
    row_stride = ((bpp * width + 31) // 32) * 4
    rgb = bytearray(width * height * 3)
    for y in range(height):
        src_y = y if top_down else (height - 1 - y)
        row = off_bits + src_y * row_stride
        for x in range(width):
            if bpp == 24:
                b, g, r = data[row + x * 3:row + x * 3 + 3]
            else:
                b, g, r = data[row + x * 4:row + x * 4 + 3]
            i = (y * width + x) * 3
            rgb[i] = r
            rgb[i + 1] = g
            rgb[i + 2] = b
    return ImageData(width, height, rgb)


def write_png(path, width, height, rgb):
    if len(rgb) != width * height * 3:
        raise ValueError("pixel buffer size mismatch")
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    out = bytearray(PNG_SIG)
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    out += chunk(b"IEND", b"")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(out))


_PS_CONVERT = r"""
param([string]$inPath, [string]$outPath)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile($inPath)
try {
  $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  try {
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
      $g.Clear([System.Drawing.Color]::White)
      $g.DrawImage($src, 0, 0, $src.Width, $src.Height)
    } finally { $g.Dispose() }
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Bmp)
  } finally { $bmp.Dispose() }
} finally { $src.Dispose() }
"""


def _powershell_convert(src, dst):
    script = Path(tempfile.gettempdir()) / "awtk_img_convert.ps1"
    script.write_text(_PS_CONVERT, encoding="utf-8-sig")
    powershell = os.environ.get("WINDIR", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not Path(powershell).is_file():
        powershell = "powershell"
    subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         str(src), str(dst)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if not Path(dst).is_file():
        raise RuntimeError("PowerShell image conversion failed: %s" % src)


def load_image(path):
    """Load PNG/JPG/BMP into ImageData (RGB, alpha composited over white)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None

    if Image is not None:
        im = Image.open(str(path))
        try:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
                im = Image.alpha_composite(bg, im).convert("RGB")
            else:
                im = im.convert("RGB")
            return ImageData(im.width, im.height, bytearray(im.tobytes()))
        finally:
            im.close()

    suffix = path.suffix.lower()
    if suffix == ".png":
        return read_png(path)
    if suffix == ".bmp":
        try:
            return read_bmp(path)
        except Exception:
            pass

    if os.name != "nt":
        raise RuntimeError("cannot decode %s without Pillow" % path)

    tmp = Path(tempfile.mkdtemp(prefix="awtk_img_")) / "converted.bmp"
    try:
        _powershell_convert(path, tmp)
        return read_bmp(tmp)
    finally:
        try:
            tmp.unlink()
            tmp.parent.rmdir()
        except Exception:
            pass


def resize_nearest(img, width, height):
    if img.width == width and img.height == height:
        return img
    src = img.pixels
    dst = bytearray(width * height * 3)
    for y in range(height):
        sy = min(img.height - 1, int(y * img.height / height))
        srow = sy * img.width * 3
        drow = y * width * 3
        for x in range(width):
            sx = min(img.width - 1, int(x * img.width / width))
            si = srow + sx * 3
            di = drow + x * 3
            dst[di:di + 3] = src[si:si + 3]
    return ImageData(width, height, dst)


def resize_bilinear(img, width, height):
    if img.width == width and img.height == height:
        return img
    src = img.pixels
    sw, sh = img.width, img.height
    dst = bytearray(width * height * 3)

    x_ratio = (sw - 1) / float(width - 1) if width > 1 else 0.0
    y_ratio = (sh - 1) / float(height - 1) if height > 1 else 0.0
    x0s = [int(x * x_ratio) for x in range(width)]
    x1s = [min(sw - 1, x0 + 1) for x0 in x0s]
    xfs = [x * x_ratio - x0 for x, x0 in zip(range(width), x0s)]

    for y in range(height):
        sy = y * y_ratio
        y0 = int(sy)
        y1 = min(sh - 1, y0 + 1)
        yf = sy - y0
        row0 = y0 * sw * 3
        row1 = y1 * sw * 3
        drow = y * width * 3
        for x in range(width):
            x0 = x0s[x]
            x1 = x1s[x]
            xf = xfs[x]
            i00 = row0 + x0 * 3
            i01 = row0 + x1 * 3
            i10 = row1 + x0 * 3
            i11 = row1 + x1 * 3
            for c in range(3):
                top = src[i00 + c] * (1 - xf) + src[i01 + c] * xf
                bottom = src[i10 + c] * (1 - xf) + src[i11 + c] * xf
                dst[drow + x * 3 + c] = int(top * (1 - yf) + bottom * yf + 0.5)
    return ImageData(width, height, dst)


# ---------------------------------------------------------------------------
# Window capture (Windows GDI)
# ---------------------------------------------------------------------------

class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def _enum_windows_for_pid(pid):
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def callback(hwnd, lparam):
        proc_id = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append((hwnd, buf.value, cls.value))
        return True

    user32.EnumWindows(callback, 0)
    return found


def _is_preview_window(title, class_name):
    """The preview canvas is SDL's window; skip its console and IME windows."""
    if class_name == "SDL_app":
        return True
    if class_name in ("ConsoleWindowClass", "IME", "MSCTFIME UI"):
        return False
    title = title or ""
    return any(name in title for name in PREVIEW_WINDOW_TITLES)


def wait_for_window(pid, timeout=20.0, poll=0.15):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        windows = _enum_windows_for_pid(pid)
        preferred = [w for w in windows if _is_preview_window(w[1], w[2])]
        if preferred:
            sdl = [w for w in preferred if w[2] == "SDL_app"]
            return (sdl or preferred)[0][0]
        time.sleep(poll)
    return None


def capture_window(pid, expected_size=None, timeout=20.0):
    """Capture the client area of the preview window. Returns (w, h, rgb)."""
    if os.name != "nt":
        raise RuntimeError("window capture is only implemented on Windows")
    hwnd = wait_for_window(pid, timeout=timeout)
    if not hwnd:
        raise RuntimeError("preview window not found (pid=%s)" % pid)

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = _RECT()
    width = height = 0
    last = (0, 0)
    stable = 0
    matched = expected_size is None
    deadline = time.time() + timeout
    while time.time() < deadline:
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width > 0 and height > 0:
            if expected_size and (width, height) == tuple(expected_size):
                matched = True
                break
            if not expected_size and (width, height) == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
        last = (width, height)
        time.sleep(0.15)
    if width <= 0 or height <= 0:
        raise RuntimeError("preview window has empty client area")
    if expected_size and not matched:
        raise RuntimeError(
            "preview window is %dx%d, expected %dx%d; the preview_ui command-line "
            "style may be wrong (see awtk_common.preview_cli_style)"
            % (width, height, expected_size[0], expected_size[1]))

    hdc = user32.GetDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    SRCCOPY = 0x00CC0020
    ok = gdi32.BitBlt(mem_dc, 0, 0, width, height, hdc, 0, 0, SRCCOPY)

    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)

    gdi32.SelectObject(mem_dc, old)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hdc)

    if not ok:
        raise RuntimeError("BitBlt failed")

    raw = buffer.raw
    rgb = bytearray(width * height * 3)
    for y in range(height):
        src_row = (height - 1 - y) * width * 4
        dst_row = y * width * 3
        for x in range(width):
            si = src_row + x * 4
            di = dst_row + x * 3
            rgb[di] = raw[si + 2]
            rgb[di + 1] = raw[si + 1]
            rgb[di + 2] = raw[si]

    if expected_size and (width, height) != tuple(expected_size):
        print("WARNING: capture size %dx%d differs from expected %dx%d"
              % (width, height, expected_size[0], expected_size[1]), file=sys.stderr)
    return width, height, rgb


def terminate_process(proc, timeout=5.0):
    if proc is None:
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=timeout)
        except Exception:
            pass


def json_print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
