#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare an AWTK preview screenshot with a design mockup.

Outputs metrics.json, diff.png and side_by_side.png (plus overlay.png).
"""

import argparse
import json
import math
import sys
from pathlib import Path

import awtk_common as common


def parse_crop(value):
    if not value:
        return None
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x,y,w,h")
    return tuple(parts)


def parse_size(value):
    import re
    match = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", value or "")
    if not match:
        raise argparse.ArgumentTypeError("size must be WxH")
    return int(match.group(1)), int(match.group(2))


def crop_image(img, crop):
    if not crop:
        return img
    x, y, w, h = crop
    x = max(0, x)
    y = max(0, y)
    w = min(w, img.width - x)
    h = min(h, img.height - y)
    if w <= 0 or h <= 0:
        raise ValueError("invalid crop: %s" % (crop,))
    pixels = bytearray(w * h * 3)
    for row in range(h):
        src = ((y + row) * img.width + x) * 3
        dst = row * w * 3
        pixels[dst:dst + w * 3] = img.pixels[src:src + w * 3]
    return common.ImageData(w, h, pixels)


def copy_or_resize(img, width, height, method):
    if img.width == width and img.height == height:
        return img
    if method == "nearest":
        return common.resize_nearest(img, width, height)
    return common.resize_bilinear(img, width, height)


def compare(a, b, threshold=16):
    width, height = a.width, a.height
    total = width * height
    sum_abs = 0
    sum_sq = 0
    diff_count = 0
    max_diff = 0
    min_x, min_y = width, height
    max_x, max_y = -1, -1
    diff_pixels = bytearray(total * 3)
    av = a.pixels
    bv = b.pixels
    for i in range(total):
        base = i * 3
        dr = av[base] - bv[base]
        dg = av[base + 1] - bv[base + 1]
        db = av[base + 2] - bv[base + 2]
        if dr < 0:
            dr = -dr
        if dg < 0:
            dg = -dg
        if db < 0:
            db = -db
        local_max = dr if dr >= dg and dr >= db else (dg if dg >= db else db)
        sum_abs += dr + dg + db
        sum_sq += dr * dr + dg * dg + db * db
        if local_max > max_diff:
            max_diff = local_max
        if local_max > threshold:
            diff_count += 1
            x = i % width
            y = i // width
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
        # Red highlight over a faded preview.
        luma = (bv[base] * 77 + bv[base + 1] * 150 + bv[base + 2] * 29) >> 8
        faded = 255 - ((255 - luma) >> 2)
        if local_max > threshold:
            strength = min(255, local_max * 3)
            diff_pixels[base] = 255
            diff_pixels[base + 1] = max(0, 255 - strength)
            diff_pixels[base + 2] = max(0, 255 - strength)
        else:
            diff_pixels[base] = faded
            diff_pixels[base + 1] = faded
            diff_pixels[base + 2] = faded

    mae = sum_abs / float(total * 3)
    rmse = math.sqrt(sum_sq / float(total * 3))
    bbox = None
    if max_x >= 0:
        bbox = [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]
    return {
        "width": width,
        "height": height,
        "pixels": total,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "diff_ratio": round(diff_count / float(total), 6),
        "diff_pixels": diff_count,
        "max_diff": max_diff,
        "threshold": threshold,
        "bbox": bbox,
    }, diff_pixels


def side_by_side(a, b, gap=8):
    width = a.width + gap + b.width
    height = max(a.height, b.height)
    pixels = bytearray(b"\xff" * (width * height * 3))
    for row in range(a.height):
        src = row * a.width * 3
        dst = row * width * 3
        pixels[dst:dst + a.width * 3] = a.pixels[src:src + a.width * 3]
    offset = a.width + gap
    for row in range(b.height):
        src = row * b.width * 3
        dst = row * width * 3 + offset * 3
        pixels[dst:dst + b.width * 3] = b.pixels[src:src + b.width * 3]
    return common.ImageData(width, height, pixels)


def overlay(a, b):
    width, height = a.width, a.height
    pixels = bytearray(width * height * 3)
    for i in range(width * height * 3):
        pixels[i] = (a.pixels[i] + b.pixels[i]) // 2
    return common.ImageData(width, height, pixels)


def main(argv=None):
    common.setup_stdout()
    parser = argparse.ArgumentParser(description="Compare a mockup and a preview screenshot")
    parser.add_argument("mockup", help="design mockup image")
    parser.add_argument("preview", help="preview screenshot")
    parser.add_argument("--out-dir", default="out/compare", help="output directory")
    parser.add_argument("--json", help="write metrics JSON to this path")
    parser.add_argument("--threshold", type=int, default=16,
                        help="per-channel difference threshold (0-255), default 16")
    parser.add_argument("--resize", choices=("bilinear", "nearest"), default="bilinear")
    parser.add_argument("--scale-to", default="preview",
                        help="preview (default), mockup, or WxH")
    parser.add_argument("--crop-mockup", type=parse_crop, help="crop mockup: x,y,w,h")
    parser.add_argument("--crop-preview", type=parse_crop, help="crop preview: x,y,w,h")
    parser.add_argument("--overlay", action="store_true", help="also write overlay.png")
    parser.add_argument("--fail-if-mae", type=float, help="exit 1 when MAE exceeds this")
    parser.add_argument("--fail-if-diff-ratio", type=float,
                        help="exit 1 when diff ratio (0-1) exceeds this")
    args = parser.parse_args(argv)

    mockup = common.load_image(args.mockup)
    preview = common.load_image(args.preview)
    mockup = crop_image(mockup, args.crop_mockup)
    preview = crop_image(preview, args.crop_preview)

    if args.scale_to == "preview":
        target_w, target_h = preview.size
    elif args.scale_to == "mockup":
        target_w, target_h = mockup.size
    else:
        target_w, target_h = parse_size(args.scale_to)

    mockup_r = copy_or_resize(mockup, target_w, target_h, args.resize)
    preview_r = copy_or_resize(preview, target_w, target_h, args.resize)

    metrics, diff_pixels = compare(mockup_r, preview_r, args.threshold)
    metrics["mockup"] = str(Path(args.mockup))
    metrics["preview"] = str(Path(args.preview))
    metrics["mockup_size"] = "%dx%d" % mockup.size
    metrics["preview_size"] = "%dx%d" % preview.size
    metrics["target_size"] = "%dx%d" % (target_w, target_h)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    common.write_png(out_dir / "diff.png", target_w, target_h, diff_pixels)
    sbs = side_by_side(mockup_r, preview_r)
    common.write_png(out_dir / "side_by_side.png", sbs.width, sbs.height, sbs.pixels)
    if args.overlay:
        ov = overlay(mockup_r, preview_r)
        common.write_png(out_dir / "overlay.png", ov.width, ov.height, ov.pixels)

    metrics["outputs"] = {
        "diff": str(out_dir / "diff.png"),
        "side_by_side": str(out_dir / "side_by_side.png"),
    }
    if args.overlay:
        metrics["outputs"]["overlay"] = str(out_dir / "overlay.png")

    json_path = Path(args.json) if args.json else out_dir / "metrics.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print("compare: mockup %s vs preview %s" % (metrics["mockup_size"], metrics["preview_size"]))
    print("  target:   %s" % metrics["target_size"])
    print("  MAE:      %.3f" % metrics["mae"])
    print("  RMSE:     %.3f" % metrics["rmse"])
    print("  diff:     %.3f%% (%d px, threshold %d)"
          % (metrics["diff_ratio"] * 100, metrics["diff_pixels"], args.threshold))
    print("  bbox:     %s" % (metrics["bbox"] if metrics["bbox"] else "none"))
    print("  outputs:  %s" % out_dir)
    print("  metrics:  %s" % json_path)

    failed = False
    if args.fail_if_mae is not None and metrics["mae"] > args.fail_if_mae:
        print("FAIL: MAE exceeds %.3f" % args.fail_if_mae, file=sys.stderr)
        failed = True
    if args.fail_if_diff_ratio is not None and metrics["diff_ratio"] > args.fail_if_diff_ratio:
        print("FAIL: diff ratio exceeds %.4f" % args.fail_if_diff_ratio, file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
