#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Closed-loop tests for the five hard constraints.

Run from the skill directory:
    python tests/test_constraints.py
"""

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import spec_to_ui  # noqa: E402
import validate_ui  # noqa: E402


def write(path, text=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ConstraintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.theme_dir = self.project / "design" / "day"
        for name in ("bg_main", "icon_ok", "tem_n_dash", "tem_d_dash",
                     "ind_abs", "tem_n_2", "tem_d_2"):
            write(self.theme_dir / "images" / "x1" / (name + ".png"), "png")
        write(self.theme_dir / "styles" / "default.xml",
              '<window><style name="page"><normal bg_color="#000000"/></style></window>\n')
        self.out_dir = self.project / "design" / "day" / "ui"
        self.spec_path = self.root / "design_spec.json"
        self.spec = {
            "project": {"name": "demo", "lcd": {"w": 800, "h": 480},
                        "theme": "day", "dpr": 1},
            "missing_images": [
                {"name": "icon_missing", "widget": "icon_missing",
                 "reason": "切图缺失，按约束不放置"}
            ],
            "review_notes": ["屏幕级说明：计划书未给字体"],
            "screens": [{
                "name": "main", "type": "window", "file": "main.xml",
                "modes": ["day", "night"],
                "x": 0, "y": 0, "w": 800, "h": 480, "style": "page",
                "children": [
                    {"name": "bg", "type": "image", "x": 0, "y": 0,
                     "w": 800, "h": 480,
                     "attrs": {"image": "bg_main", "draw_type": "scale"}},
                    {"name": "icon_ok", "type": "image", "x": 10, "y": 10,
                     "w": 32, "h": 32, "attrs": {"image": "icon_ok"}},
                    {"name": "label_ok", "type": "label", "x": 10, "y": 50,
                     "w": 100, "h": 20, "text": "hello"},
                    {"name": "temp_group", "type": "view", "x": 53, "y": 54,
                     "w": 59, "h": 26, "children": [
                         {"name": "temp_dash", "type": "image", "x": 0, "y": 1,
                          "w": 12, "h": 19,
                          "by_mode": {
                              "day": {"attrs": {"image": "tem_n_dash"}},
                              "night": {"attrs": {"image": "tem_d_dash"}}}},
                         {"name": "temp_value_1", "type": "image", "x": 12,
                          "y": 1, "w": 12, "h": 19,
                          "by_mode": {
                              "day": {"attrs": {"image": "tem_n_2"}},
                              "night": {"attrs": {"image": "tem_d_2"}}}},
                     ]},
                    {"name": "ind_abs", "type": "image", "x": 450, "y": 15,
                     "w": 52, "h": 40, "attrs": {"image": "ind_abs"},
                     "review_kind": "wrong_image",
                     "review_note": "切图与效果图不一致，按计划书坐标原值放置"},
                    {"name": "icon_missing", "type": "image", "x": 0, "y": 0,
                     "w": 32, "h": 32, "missing": True,
                     "missing_reason": "切图缺失，按约束不放置"},
                ],
            }],
        }
        write(self.spec_path, json.dumps(self.spec, ensure_ascii=False, indent=2))

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self):
        code = spec_to_ui.main([str(self.spec_path),
                                "--out-dir", str(self.out_dir)])
        self.assertEqual(code, 0)
        return (self.out_dir / "main_day.xml", self.out_dir / "main_night.xml")

    def test_modes_and_notes_files(self):
        day_xml, night_xml = self.generate()
        self.assertTrue(day_xml.is_file())
        self.assertTrue(night_xml.is_file())
        self.assertTrue(day_xml.with_suffix(".md").is_file())
        self.assertTrue(night_xml.with_suffix(".md").is_file())
        md = day_xml.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("未放置", md)
        self.assertIn("icon_missing", md)
        self.assertIn("已放置但需确认", md)
        self.assertIn("ind_abs", md)
        self.assertIn("切图与效果图不一致", md)

    def test_draw_type_default_and_special(self):
        day_xml, _ = self.generate()
        root = ET.parse(day_xml).getroot()
        by_name = {el.get("name"): el for el in root.iter()}
        self.assertEqual(by_name["icon_ok"].get("draw_type"), "default")
        self.assertEqual(by_name["temp_dash"].get("draw_type"), "default")
        self.assertEqual(by_name["bg"].get("draw_type"), "scale")
        self.assertIsNone(by_name["label_ok"].get("draw_type"))

    def test_slice_names_are_not_renamed(self):
        node = {"name": "logo", "type": "image", "x": 0, "y": 0, "w": 10,
                "h": 10, "attrs": {"image": "Logo-Main v2"}}
        attrs = spec_to_ui.node_attributes(node)
        self.assertEqual(attrs["image"], "Logo-Main v2")
        self.assertEqual(attrs["draw_type"], "default")

    def test_missing_is_not_placed_but_review_is(self):
        day_xml, _ = self.generate()
        root = ET.parse(day_xml).getroot()
        names = {el.get("name") for el in root.iter()}
        self.assertNotIn("icon_missing", names)
        self.assertIn("ind_abs", names)

    def test_coordinates_are_not_changed(self):
        day_xml, _ = self.generate()
        root = ET.parse(day_xml).getroot()
        by_name = {el.get("name"): el for el in root.iter()}
        self.assertEqual(by_name["ind_abs"].get("x"), "450")
        self.assertEqual(by_name["ind_abs"].get("y"), "15")
        self.assertEqual(by_name["temp_group"].get("x"), "53")
        self.assertEqual(by_name["temp_group"].get("y"), "54")
        # Container rect comes from the plan (59x26), not the tight 57x24 box.
        self.assertEqual(by_name["temp_group"].get("w"), "59")
        self.assertEqual(by_name["temp_group"].get("h"), "26")
        self.assertEqual(by_name["temp_value_1"].get("x"), "12")

    def test_by_mode_images(self):
        day_xml, night_xml = self.generate()
        day = {el.get("name"): el for el in ET.parse(day_xml).getroot().iter()}
        night = {el.get("name"): el for el in ET.parse(night_xml).getroot().iter()}
        self.assertEqual(day["temp_dash"].get("image"), "tem_n_dash")
        self.assertEqual(night["temp_dash"].get("image"), "tem_d_dash")

    def test_by_mode_auto_detects_modes(self):
        # Constraint 4: node-level by_mode alone must still yield two XMLs.
        spec = json.loads(json.dumps(self.spec, ensure_ascii=False))
        spec["screens"][0].pop("modes", None)
        auto_spec = write(self.root / "auto_spec.json",
                          json.dumps(spec, ensure_ascii=False))
        auto_dir = self.out_dir / "auto"
        code = spec_to_ui.main([str(auto_spec), "--out-dir", str(auto_dir)])
        self.assertEqual(code, 0)
        self.assertTrue((auto_dir / "main_day.xml").is_file())
        self.assertTrue((auto_dir / "main_night.xml").is_file())

    def test_validate_strict_constraints_passes(self):
        day_xml, _ = self.generate()
        report = validate_ui.validate(day_xml, self.project, "day", (800, 480),
                                      strict_constraints=True)
        self.assertEqual(report.errors, [])

    def test_validate_flags_missing_draw_type(self):
        bad = write(self.out_dir / "bad.xml",
                    '<window name="bad" w="800" h="480">'
                    '<image name="x" x="0" y="0" w="10" h="10" image="icon_ok"/>'
                    '</window>')
        report = validate_ui.validate(bad, self.project, "day", (800, 480),
                                      strict_constraints=True)
        self.assertTrue(any("draw_type" in item for item in report.errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
