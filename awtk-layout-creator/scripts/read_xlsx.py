#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read .xlsx coordinate sheets with the Python standard library only.

xlsx is a zip of XML files; this avoids openpyxl/pandas, which are often not
installed on AWTK development machines.
"""

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")
RANGE_RE = re.compile(r"^([A-Z]+\d+):([A-Z]+\d+)$")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def col_to_index(letters):
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value - 1


def index_to_col(index):
    letters = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def parse_ref(ref):
    match = CELL_REF_RE.match(ref or "")
    if not match:
        return None
    return int(match.group(2)) - 1, col_to_index(match.group(1))


def parse_range(ref):
    match = RANGE_RE.match(ref or "")
    if not match:
        return None
    start = parse_ref(match.group(1))
    end = parse_ref(match.group(2))
    if not start or not end:
        return None
    return start[0], start[1], end[0], end[1]


def read_shared_strings(zf):
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings = []
    for si in root:
        if local(si.tag) != "si":
            continue
        parts = [node.text or "" for node in si.iter() if local(node.tag) == "t"]
        strings.append("".join(parts))
    return strings


def read_workbook(zf):
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = {}
    try:
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root:
            rels[rel.get("Id")] = rel.get("Target")
    except KeyError:
        pass

    sheets = []
    for node in root.iter():
        if local(node.tag) != "sheet":
            continue
        rel_id = None
        for key, value in node.attrib.items():
            if local(key) == "id":
                rel_id = value
        target = rels.get(rel_id, "")
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = target
        else:
            path = "xl/" + target
        sheets.append({
            "name": node.get("name") or "Sheet%d" % (len(sheets) + 1),
            "sheet_id": node.get("sheetId"),
            "path": path,
        })
    return sheets


def cell_value(cell, shared):
    cell_type = cell.get("t")
    value_node = None
    inline = None
    for child in cell:
        if local(child.tag) == "v":
            value_node = child
        elif local(child.tag) == "is":
            inline = child
    if cell_type == "inlineStr" and inline is not None:
        return "".join(node.text or "" for node in inline.iter() if local(node.tag) == "t")
    text = value_node.text if value_node is not None else None
    if text is None:
        return None
    if cell_type == "s":
        try:
            return shared[int(text)]
        except Exception:
            return text
    if cell_type == "b":
        return text == "1"
    if cell_type in ("str", "e"):
        return text
    # Numeric: strip trailing .0 for readability.
    try:
        number = float(text)
        if number.is_integer():
            return int(number)
        return number
    except Exception:
        return text


def read_sheet(zf, path, shared, fill_merged=True):
    root = ET.fromstring(zf.read(path))
    cells = {}
    max_row = -1
    max_col = -1
    for node in root.iter():
        if local(node.tag) != "c":
            continue
        ref = parse_ref(node.get("r"))
        if not ref:
            continue
        row, col = ref
        value = cell_value(node, shared)
        if value is not None:
            cells[(row, col)] = value
        max_row = max(max_row, row)
        max_col = max(max_col, col)

    merged = []
    for node in root.iter():
        if local(node.tag) != "mergeCell":
            continue
        ref = node.get("ref")
        area = parse_range(ref)
        if not area:
            continue
        merged.append(ref)
        if not fill_merged:
            continue
        r0, c0, r1, c1 = area
        value = cells.get((r0, c0))
        if value is None:
            continue
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cells.setdefault((r, c), value)
                max_row = max(max_row, r)
                max_col = max(max_col, c)

    if max_row < 0:
        return [], merged
    rows = []
    for r in range(max_row + 1):
        rows.append([cells.get((r, c)) for c in range(max_col + 1)])
    return rows, merged


def trim_rows(rows):
    while rows and all(value in (None, "") for value in rows[-1]):
        rows.pop()
    width = 0
    for row in rows:
        for idx, value in enumerate(row):
            if value not in (None, ""):
                width = max(width, idx + 1)
    return [row[:width] + [None] * (width - len(row[:width])) for row in rows]


def make_headers(rows, header_row=1, no_header=False):
    if no_header:
        width = max((len(r) for r in rows), default=0)
        return [index_to_col(i) for i in range(width)], rows
    index = max(0, header_row - 1)
    if index >= len(rows):
        return [], rows
    raw = rows[index]
    headers = []
    seen = {}
    for i, value in enumerate(raw):
        name = str(value).strip() if value not in (None, "") else "column_%d" % (i + 1)
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 1
        headers.append(name)
    return headers, rows[index + 1:]


def to_dict_rows(headers, rows):
    result = []
    for row in rows:
        if all(value in (None, "") for value in row):
            continue
        item = {}
        for i, header in enumerate(headers):
            item[header] = row[i] if i < len(row) else None
        result.append(item)
    return result


def load_workbook(path):
    return zipfile.ZipFile(path)


def sheet_names(zf):
    return [sheet["name"] for sheet in read_workbook(zf)]


def select_sheet(zf, selector):
    sheets = read_workbook(zf)
    if not sheets:
        raise ValueError("workbook has no sheets")
    if selector is None:
        return sheets[0]
    if str(selector).isdigit():
        index = int(selector)
        if index < 0 or index >= len(sheets):
            raise ValueError("sheet index out of range: %s" % selector)
        return sheets[index]
    for sheet in sheets:
        if sheet["name"] == selector:
            return sheet
    raise ValueError("sheet not found: %s" % selector)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Read xlsx with stdlib only")
    parser.add_argument("xlsx", help="path to .xlsx")
    parser.add_argument("--sheet", default=None, help="sheet name or 0-based index")
    parser.add_argument("--list-sheets", action="store_true", help="list sheet names and exit")
    parser.add_argument("--header-row", type=int, default=1, help="1-based header row (default 1)")
    parser.add_argument("--no-header", action="store_true", help="do not treat a row as header")
    parser.add_argument("--no-fill-merged", action="store_true", help="do not fill merged cells")
    parser.add_argument("--json", metavar="PATH", help="write JSON to PATH ('-' for stdout)")
    parser.add_argument("--csv", metavar="PATH", help="write CSV to PATH ('-' for stdout)")
    args = parser.parse_args(argv)

    path = Path(args.xlsx)
    if not path.is_file():
        print("file not found: %s" % path, file=sys.stderr)
        return 2

    with zipfile.ZipFile(path) as zf:
        if args.list_sheets:
            for i, name in enumerate(sheet_names(zf)):
                print("%d\t%s" % (i, name))
            return 0

        sheet = select_sheet(zf, args.sheet)
        shared = read_shared_strings(zf)
        rows, merged = read_sheet(zf, sheet["path"], shared,
                                  fill_merged=not args.no_fill_merged)
        rows = trim_rows(rows)
        headers, data_rows = make_headers(rows, args.header_row, args.no_header)
        dict_rows = to_dict_rows(headers, data_rows)
        all_sheets = sheet_names(zf)

    payload = {
        "file": str(path),
        "sheet": sheet["name"],
        "sheets": all_sheets,
        "headers": headers,
        "rows": dict_rows,
        "raw_rows": data_rows,
        "merged": merged,
        "row_count": len(dict_rows),
    }

    if args.json:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json == "-":
            print(text)
        else:
            Path(args.json).write_text(text, encoding="utf-8")
    if args.csv:
        output = sys.stdout if args.csv == "-" else open(args.csv, "w", encoding="utf-8-sig", newline="")
        try:
            writer = csv.writer(output)
            writer.writerow(headers)
            for row in data_rows:
                writer.writerow(["" if value is None else value for value in row])
        finally:
            if output is not sys.stdout:
                output.close()

    if not args.json and not args.csv:
        print("sheet: %s" % sheet["name"])
        print("sheets: %s" % ", ".join(payload["sheets"]))
        print("rows: %d" % len(dict_rows))
        print("headers: %s" % ", ".join(headers))
        for row in dict_rows[:10]:
            print("  %s" % json.dumps(row, ensure_ascii=False))
        if len(dict_rows) > 10:
            print("  ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
