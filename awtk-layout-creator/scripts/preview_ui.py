#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch AWTK's official preview_ui, optionally screenshot it.

The official tool lives at <AWTK_ROOT>/bin/preview_ui.exe and reads the UI XML
from the explicit path argument. Other assets (styles/images/fonts/strings)
come from res_root, whose expected layout depends on the build:

  demos/preview_ui  -> <res_root>/assets/<theme>/raw/...  (packaged res)
  tools/preview_ui  -> <res_root>/<theme>/...              (design)

For the old build this script stages design/<theme> into out/preview_res when
the packaged res is missing or older than the design sources.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import awtk_common as common


def parse_lcd(value):
    import re
    match = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", value or "")
    if not match:
        raise argparse.ArgumentTypeError("expected WxH, e.g. 800x480")
    return int(match.group(1)), int(match.group(2))


def resolve_ui(project, theme, explicit):
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            candidate = project / path
            path = candidate if candidate.exists() else path
        return path.resolve()

    project_data = common.read_project_json(project)
    entry = common.project_entry(project_data)
    if not entry:
        raise SystemExit("no --ui given and project.json has no 'entry'")
    for candidate in (
        project / "design" / theme / "ui" / (entry + ".xml"),
        project / "design" / "default" / "ui" / (entry + ".xml"),
        project / "design" / theme / "ui" / entry,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("entry UI not found: %s (theme=%s)" % (entry, theme))


def build_command(preview, ui, res_root, lcd, theme, args, language=None):
    """Build argv for either preview_ui build.

    demos/preview_ui (old):  preview_ui <ui> <w> <h> <res_root> [language] [theme]
    tools/preview_ui (new):  preview_ui ui=... lcd_w=... lcd_h=... res_root=...
    """
    if common.preview_cli_style(preview) == "positional":
        cmd = [str(preview), str(ui), str(lcd[0]), str(lcd[1]), str(res_root)]
        lang = language or args.language
        if lang or theme != "default":
            cmd.append(lang or "zh_CN")
            cmd.append(theme or "default")
        return cmd

    cmd = [
        str(preview),
        "ui=%s" % ui,
        "lcd_w=%d" % lcd[0],
        "lcd_h=%d" % lcd[1],
        "res_root=%s" % res_root,
        "theme=%s" % theme,
    ]
    if args.language:
        cmd.append("language=%s" % args.language)
    if args.system_bar:
        cmd.append("system_bar=%s" % args.system_bar)
    if args.bottom_system_bar:
        cmd.append("bottom_system_bar=%s" % args.bottom_system_bar)
    if args.plugins_path:
        cmd.append("plugins_path=%s" % args.plugins_path)
    if args.render_mode:
        cmd.append("render_mode=%s" % args.render_mode)
    if args.log_level is not None:
        cmd.append("log_level=%s" % args.log_level)
    if args.fps is not None:
        cmd.append("fps=%s" % args.fps)
    if args.enable_std_font:
        cmd.append("enable_std_font=true")
    return cmd


def resolve_res_root(project, theme, preview, args):
    """Pick res_root according to the preview build and available assets.

    Returns (path, layout, note); layout is 'explicit', 'design', 'packaged'
    or 'staged'.
    """
    if args.res_root:
        return Path(args.res_root).resolve(), "explicit", None

    design_root = project / "design"
    if common.preview_cli_style(preview) != "positional":
        # tools/preview_ui uses <res_root>/<theme>/..., which matches design/.
        return design_root, "design", None

    packaged = common.packaged_res_dir(project, theme)
    need_stage = (args.stage_res or packaged is None or
                  not common.packaged_res_is_fresh(project, theme))
    if need_stage:
        staged = common.stage_preview_res(project, theme)
        if staged is not None:
            if args.stage_res:
                reason = "requested"
            elif packaged is None:
                reason = "no packaged res"
            else:
                reason = "design newer than packaged res"
            return staged.resolve(), "staged", reason
        if packaged is not None:
            return packaged.resolve(), "packaged", "design/<theme> missing; cannot stage"
        return design_root, "design", "design/<theme> missing; assets will not load"

    return packaged.resolve(), "packaged", None


def run_update_res(project):
    """Run the project's own resource generator (official AWTK workflow)."""
    script = Path(project) / "scripts" / "update_res.py"
    if not script.is_file():
        print("WARNING: --update-res: %s not found; skipping" % script, file=sys.stderr)
        return True
    print("update_res: %s all" % script)
    result = subprocess.run([sys.executable, str(script), "all"], cwd=str(project))
    return result.returncode == 0


def warn_unsupported_options(args, cli_style):
    if cli_style != "positional":
        return
    options = [
        ("--render-mode", args.render_mode),
        ("--system-bar", args.system_bar),
        ("--bottom-system-bar", args.bottom_system_bar),
        ("--plugins-path", args.plugins_path),
        ("--log-level", args.log_level),
        ("--fps", args.fps),
        ("--enable-std-font", args.enable_std_font),
    ]
    ignored = [name for name, value in options if value not in (None, False, "")]
    if ignored:
        print("WARNING: this preview_ui build ignores %s" % ", ".join(ignored),
              file=sys.stderr)


def warn_if_no_fonts(res_root, theme, cli_style):
    if cli_style == "positional":
        fonts = Path(res_root) / "assets" / theme / "raw" / "fonts"
    else:
        fonts = Path(res_root) / theme / "fonts"
    if fonts.is_dir() and any(p.is_file() for p in fonts.iterdir()):
        return
    print("WARNING: no font files under %s; text will not render. "
          "Copy <AWTK_ROOT>/design/default/fonts/default.ttf (and default_full.ttf) "
          "into your design/<theme>/fonts." % fonts, file=sys.stderr)


def tail_file(path, lines=30):
    try:
        data = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(data[-lines:])
    except Exception:
        return ""


def run_validate(project, ui, theme, lcd, quiet=False):
    script = Path(__file__).resolve().parent / "validate_ui.py"
    cmd = [sys.executable, str(script), str(ui), "--project", str(project), "--theme", theme,
           "--lcd", "%dx%d" % lcd]
    if quiet:
        print("validate: %s" % " ".join(cmd), file=sys.stderr)
        return subprocess.run(cmd, stdout=sys.stderr).returncode
    print("validate: %s" % " ".join(cmd))
    return subprocess.run(cmd).returncode


def main(argv=None):
    common.setup_stdout()
    parser = argparse.ArgumentParser(description="Preview an AWTK UI with the official preview_ui")
    parser.add_argument("--project", default=".", help="project root")
    parser.add_argument("--ui", help="UI XML path (relative to project or absolute)")
    parser.add_argument("--awtk-root", help="AWTK root (contains bin/preview_ui.exe)")
    parser.add_argument("--lcd", type=parse_lcd, help="LCD size, e.g. 800x480")
    parser.add_argument("--theme", help="theme name")
    parser.add_argument("--language", help="language, e.g. zh_CN")
    parser.add_argument("--res-root", help="resource root (default: auto; design for tools/preview_ui, "
                                           "staged or packaged res for demos/preview_ui)")
    parser.add_argument("--stage-res", action="store_true",
                        help="stage design/<theme> into out/preview_res for the old preview_ui")
    parser.add_argument("--update-res", action="store_true",
                        help="run scripts/update_res.py all before preview")
    parser.add_argument("--screenshot", help="save a PNG screenshot to this path")
    parser.add_argument("--wait", type=float, default=2.0, help="seconds to wait before capture")
    parser.add_argument("--timeout", type=float, default=20.0, help="seconds to wait for the window")
    parser.add_argument("--keep-open", action="store_true", help="keep the preview running")
    parser.add_argument("--dry-run", action="store_true", help="print the command and exit")
    parser.add_argument("--json", action="store_true", help="print JSON result")
    parser.add_argument("--validate", action="store_true", help="run validate_ui.py first")
    parser.add_argument("--render-mode", help="OpenGL (default), Software, ...")
    parser.add_argument("--log-level", help="AWTK log level: 0 debug, 1 info, 2 warn, 3 error")
    parser.add_argument("--fps", help="frame rate")
    parser.add_argument("--enable-std-font", action="store_true")
    parser.add_argument("--system-bar", help="top system bar UI name")
    parser.add_argument("--bottom-system-bar", help="bottom system bar UI name")
    parser.add_argument("--plugins-path", help="directory of custom widget DLLs")
    parser.add_argument("--log", help="preview log path (default <project>/out/preview.log)")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    project_data = common.read_project_json(project)
    theme = common.project_theme(project_data, args.theme)

    awtk_root = common.find_awtk_root(args.awtk_root, project)
    if not awtk_root:
        print("ERROR: AWTK root not found. Use --awtk-root or set AWTK_SDK_PATH.", file=sys.stderr)
        return 2
    preview = common.find_preview_ui(awtk_root)
    if not preview:
        print("ERROR: preview_ui not found under %s/bin" % awtk_root, file=sys.stderr)
        return 2

    try:
        ui = resolve_ui(project, theme, args.ui)
    except SystemExit as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if not ui.is_file():
        print("ERROR: UI file not found: %s" % ui, file=sys.stderr)
        return 2

    lcd = args.lcd or common.project_lcd(project_data, theme) or (800, 480)
    if not args.lcd and not common.project_lcd(project_data, theme):
        print("WARNING: LCD size not in project.json; using %dx%d" % lcd, file=sys.stderr)

    cli_style = common.preview_cli_style(preview)
    warn_unsupported_options(args, cli_style)

    if args.update_res:
        if not run_update_res(project):
            print("ERROR: update_res.py failed; preview aborted.", file=sys.stderr)
            return 1

    res_root, res_layout, res_note = resolve_res_root(project, theme, preview, args)
    if not res_root.is_dir():
        print("WARNING: res_root does not exist: %s" % res_root, file=sys.stderr)
    else:
        warn_if_no_fonts(res_root, theme, cli_style)
    if res_note:
        print("NOTE: res_root: %s (%s)" % (res_root, res_note), file=sys.stderr)

    if args.validate:
        code = run_validate(project, ui, theme, lcd, quiet=args.json)
        if code != 0:
            print("ERROR: validation failed; preview aborted.", file=sys.stderr)
            return code

    language = common.project_language(project_data, args.language)
    cmd = build_command(preview, ui, res_root, lcd, theme, args, language=language)

    if args.dry_run:
        if args.json:
            common.json_print({"command": cmd, "cwd": str(awtk_root),
                               "preview_cli": cli_style, "res_root": str(res_root),
                               "res_layout": res_layout, "dry_run": True})
        else:
            print(subprocess.list2cmdline(cmd))
        return 0

    log_path = Path(args.log) if args.log else (project / "out" / "preview.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(str(log_path), "wb")

    started = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(awtk_root),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:
        log_file.close()
        print("ERROR: failed to start preview: %s" % exc, file=sys.stderr)
        return 2

    result = {
        "command": cmd,
        "cwd": str(awtk_root),
        "preview_cli": cli_style,
        "ui": str(ui),
        "res_root": str(res_root),
        "res_layout": res_layout,
        "res_note": res_note,
        "theme": theme,
        "lcd": "%dx%d" % lcd,
        "pid": proc.pid,
        "log": str(log_path),
    }

    screenshot = None
    try:
        if os.name != "nt":
            print("WARNING: screenshot capture is Windows-only; keeping preview open.",
                  file=sys.stderr)
            args.keep_open = True

        hwnd = common.wait_for_window(proc.pid, timeout=args.timeout) if os.name == "nt" else None
        if os.name == "nt" and not hwnd:
            alive = proc.poll() is None
            print("ERROR: preview window did not appear (alive=%s)." % alive, file=sys.stderr)
            tail = tail_file(log_path)
            if tail:
                print("--- preview log ---\n%s\n-------------------" % tail, file=sys.stderr)
            return 1

        if args.wait > 0:
            time.sleep(args.wait)

        if args.screenshot:
            if os.name != "nt":
                print("ERROR: --screenshot requires Windows in this build.", file=sys.stderr)
                return 1
            width, height, rgb = common.capture_window(
                proc.pid, expected_size=lcd, timeout=args.timeout)
            screenshot = Path(args.screenshot)
            if not screenshot.is_absolute():
                screenshot = (Path.cwd() / screenshot).resolve()
            common.write_png(screenshot, width, height, rgb)
            result["screenshot"] = str(screenshot)
            result["capture_size"] = "%dx%d" % (width, height)
            if not args.json:
                print("screenshot: %s (%dx%d)" % (screenshot, width, height))

        result["elapsed"] = round(time.time() - started, 2)
        result["status"] = "ok"
        if args.keep_open:
            result["keep_open"] = True
            if not args.json:
                print("preview running: pid=%d ui=%s" % (proc.pid, ui))
        else:
            common.terminate_process(proc)
        if args.json:
            common.json_print(result)
        return 0
    finally:
        log_file.close()
        if not args.keep_open:
            common.terminate_process(proc)


if __name__ == "__main__":
    sys.exit(main())
