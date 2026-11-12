#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Closed-loop tests for the context digest / compression tool.

Run from the skill directory:
    python -I tests/test_context_digest.py
"""

import argparse
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import context_digest  # noqa: E402


def write(path, text=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def ns(**overrides):
    base = {
        "sheet": None, "header_row": 1, "no_header": False,
        "no_fill_merged": False, "screen": None, "grep": None,
        "top": 10, "rows": 10, "budget": 6000, "kind": "auto",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def col_name(index):
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def make_xlsx(path, rows):
    cells = []
    for row_index, row in enumerate(rows, 1):
        items = []
        for column_index, value in enumerate(row):
            if value is None:
                continue
            text = str(value).replace("&", "&amp;").replace("<", "&lt;")
            items.append(
                '<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>'
                % (col_name(column_index), row_index, text))
        cells.append('<row r="%d">%s</row>' % (row_index, "".join(items)))
    sheet = ('<?xml version="1.0"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>%s</sheetData></worksheet>' % "".join(cells))
    workbook = ('<?xml version="1.0"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


class ContextDigestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.xlsx = self.root / "coords.xlsx"
        make_xlsx(self.xlsx, [
            ["name", "type", "x", "y", "w", "h", "image", "screen", "parent"],
            ["temp_a", "image", 10, 10, 20, 20, "tem_n", "main", "temp_group"],
            ["temp_b", "image", 30, 10, 20, 20, "tem_n", "main", "temp_group"],
            ["temp_a", "image", 50, 10, 20, 20, "tem_n", "main", "temp_group"],
            ["title", "label", 0, 0, 100, 20, "", "main", ""],
            ["ghost", "image", "", "", 20, 20, "", "main", ""],
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_xlsx_digest_counts_and_anomalies(self):
        item = context_digest.digest_xlsx(self.xlsx, ns())
        self.assertEqual(item["summary"]["rows"], 5)
        self.assertEqual(item["summary"]["duplicates"], 1)
        text = context_digest.render_md([item])
        self.assertIn("temp_a×2", text)
        self.assertIn("缺 x/y/w/h：1", text)
        self.assertIn("按屏幕", text)

    def test_xlsx_screen_filter_returns_detail(self):
        item = context_digest.digest_xlsx(self.xlsx, ns(screen="main"))
        self.assertEqual(item["summary"]["filtered"], 5)
        text = context_digest.render_md([item])
        self.assertIn("行明细", text)
        self.assertIn("ghost", text)

    def test_xlsx_grep_filter(self):
        item = context_digest.digest_xlsx(self.xlsx, ns(grep="ghost"))
        self.assertEqual(item["summary"]["filtered"], 1)
        text = context_digest.render_md([item])
        self.assertIn("ghost", text)
        self.assertNotIn("temp_b", text)

    def test_budget_is_respected(self):
        text, truncated = context_digest.apply_budget("line\n" * 1000, 300, "hint")
        self.assertTrue(truncated)
        self.assertLessEqual(len(text), 300)
        self.assertIn("已截断", text)

    def test_xml_digest_finds_duplicates_and_draw_type(self):
        path = write(self.root / "ui.xml",
                     '<window name="w" w="800" h="480">'
                     '<image name="a" x="0" y="0" w="10" h="10" image="i"/>'
                     '<image name="a" x="20" y="20" w="10" h="10" '
                     'image="j" draw_type="default"/>'
                     '</window>')
        item = context_digest.digest_xml(path, ns())
        self.assertEqual(item["summary"]["duplicates"], 1)
        text = context_digest.render_md([item])
        self.assertIn("缺 draw_type", text)

    def test_spec_digest_modes_missing_and_capsule(self):
        path = write(self.root / "spec.json", json.dumps({
            "project": {"name": "p", "lcd": {"w": 800, "h": 480},
                        "theme": "day", "dpr": 1},
            "screens": [{
                "name": "main", "file": "main.xml",
                "modes": ["day", "night"],
                "children": [
                    {"name": "a", "type": "image", "x": 0, "y": 0,
                     "w": 10, "h": 10, "attrs": {"image": "x"},
                     "missing": True},
                    {"name": "b", "type": "image", "x": 20, "y": 0,
                     "w": 10, "h": 10, "attrs": {"image": "y"},
                     "review_note": "待确认"},
                ],
            }],
        }, ensure_ascii=False))
        item = context_digest.digest_spec(path, ns())
        self.assertEqual(item["summary"]["screens"], 1)
        self.assertEqual(item["summary"]["outputs"], 2)
        self.assertEqual(item["summary"]["missing"], 1)
        self.assertEqual(item["summary"]["review"], 1)
        text = context_digest.render_md([item])
        self.assertIn("main_day.xml", text)
        self.assertIn("Context Capsule", text)

    def test_assets_digest_flags_names_and_duplicates(self):
        base = self.root / "images"
        write(base / "x1" / "icon_a.png", "png")
        write(base / "x1" / "icon_a.svg", "<svg/>")
        write(base / "x1" / "Icon-B.png", "png")
        write(base / "x1" / "坏 名.png", "png")
        item = context_digest.digest_assets(base, ns())
        self.assertGreaterEqual(item["summary"]["suspicious"], 2)
        text = context_digest.render_md([item])
        self.assertIn("重复主干", text)
        self.assertIn("大写", text)

    def test_log_digest_dedupes_and_normalizes(self):
        lines = (["ERROR: failed at C:\\tmp\\a.txt line 12"] * 50
                 + ["WARN: retry 3"] * 10 + ["info"] * 5)
        path = write(self.root / "build.log", "\n".join(lines))
        item = context_digest.digest_log(path, ns())
        self.assertEqual(item["summary"]["lines"], 65)
        self.assertLessEqual(item["summary"]["unique_patterns"], 3)
        self.assertGreater(item["summary"]["level_lines"], 0)
        text = context_digest.render_md([item])
        self.assertIn("<n>", text)

    def test_main_json_output_is_valid(self):
        spec_path = write(self.root / "main_spec.json", json.dumps({
            "project": {"name": "p", "lcd": {"w": 800, "h": 480},
                        "theme": "day"},
            "screens": [{"name": "main", "type": "window",
                         "children": []}],
        }))
        out = self.root / "digest.json"
        code = context_digest.main([str(spec_path), "--json", "--out", str(out)])
        self.assertEqual(code, 0)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data["inputs"]), 1)
        self.assertIn("est_tokens", data)
        self.assertIn("summary", data["inputs"][0])

    def test_skill_index_runs(self):
        out = self.root / "index.md"
        code = context_digest.main(["--index", "--out", str(out)])
        self.assertEqual(code, 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("references/constraints.md", text)
        self.assertIn("references/context-and-tokens.md", text)
        self.assertIn("never wholesale", text)
        self.assertIn("建议阈值", text)
        self.assertNotIn("__pycache__", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
