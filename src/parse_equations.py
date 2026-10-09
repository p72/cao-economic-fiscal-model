"""方程式リスト（reference/ef2026_equ.txt）を構造化して JSON に書き出す.

fetch_paper.py の後に実行する。
出力: data/processed/equations.json
  各要素 = {block, section, name, label, eqs: [式の文字列], pdl: [{expr, coefs}], stats}
  - eqs は t 値の行を除き、継続行を連結したもの。見出しの直下に式がない（式が別の見出しの下に
    まとめて書かれている）場合があるので、最後に左辺の変数名で見出しに振り直す。
  - pdl は「Lag Distribution of ...」の表。式中の pdl(...) と出現順に対応する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reference" / "ef2026_equ.txt"
OUT = ROOT / "data" / "processed" / "equations.json"

BLOCKS = {"１": "population", "２": "macro", "３": "fiscal", "４": "socsec"}
RE_BLOCK = re.compile(r"^\s*([１２３４])．\s*(人口|マクロ|財政|社会保障)")
RE_SECTION = re.compile(r"^\s*（(\d+|[０-９]+|[ａ-ｚ])）\s*(\S.*)$")
RE_HEADER = re.compile(r"^\s*----<\s*([A-Za-z0-9_$]+)\s*[：:]\s*(.*?)\s*>----")
RE_TLINE = re.compile(r"^[\s　]*(\(\s*-?[\d.]+\s*\)[\s　]*)+$")
RE_PAGE = re.compile(r"^===== PAGE (\d+) =====")
RE_LAGROW = re.compile(r"^\s*(\d+)\s+(-?[\d.E+-]+)\s+")
RE_STATS = re.compile(
    r"R2C\s*=\s*(-?[\d.]+)\s+SE\s*=\s*(-?[\d.E+-]+)\s+DW\s*=\s*(-?[\d.]+)\s+\(\s*(\d{4})\s*-\s*(\d{4})\s*\)"
)
NONASCII = re.compile("[^" + chr(0x20) + "-" + chr(0x7e) + "]")
RE_LHS = re.compile(r"^(?:d?log\()?\(?([A-Za-z][A-Za-z0-9_$]*)")


def clean(line: str) -> str:
    return line.replace("　", " ").rstrip()


def parse() -> list[dict]:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    page = 0
    block = None
    section = None
    items: list[dict] = []
    cur = None
    mode = "eq"  # eq | lag
    for raw in lines:
        m = RE_PAGE.match(raw)
        if m:
            page = int(m.group(1))
            continue
        if page < 3:
            continue
        line = clean(raw)
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d+", s):  # ページ番号
            continue
        m = RE_BLOCK.match(s)
        if m:
            block = BLOCKS[m.group(1)]
            section = None
            continue
        m = RE_HEADER.match(line)
        if m:
            cur = {"block": block, "section": section, "page": page, "name": m.group(1),
                   "label": m.group(2), "lines": [], "pdl": [], "stats": None}
            items.append(cur)
            mode = "eq"
            continue
        m = RE_SECTION.match(s)
        if m and "=" not in s:
            section = m.group(2).strip()
            continue
        if cur is None:
            continue
        if s.startswith("Lag Distribution of"):
            cur["pdl"].append({"expr": s[len("Lag Distribution of"):].strip(), "coefs": []})
            mode = "lag"
            continue
        if mode == "lag" and cur["pdl"] and not cur["pdl"][-1]["coefs"] and "=" not in s \
                and not s.startswith("Coefficient") and not RE_LAGROW.match(s):
            cur["pdl"][-1]["expr"] += s  # 見出しの折り返し
            continue
        m = RE_STATS.search(s)
        if m:
            cur["stats"] = {"R2C": float(m.group(1)), "SE": float(m.group(2)),
                            "DW": float(m.group(3)), "sample": [int(m.group(4)), int(m.group(5))]}
            mode = "eq"
            continue
        if mode == "lag":
            if s.startswith("Coefficient"):
                continue
            m = RE_LAGROW.match(s)
            if m:
                cur["pdl"][-1]["coefs"].append(float(m.group(2)))
                continue
            if s.startswith("Sum of Lags"):
                continue
            mode = "eq"
        if RE_TLINE.match(line):
            continue
        # 式の中に t 値が混ざった行（式の後ろに "(1.23)" が続く）は t 値部分を除く
        cur["lines"].append(s)
    return items


def split_statements(lines: list[str]) -> list[str]:
    """継続行（演算子で始まる行）を連結し、式ごとに分ける."""
    stmts: list[str] = []
    for s in lines:
        if stmts and (s[0] in "+-*/)" or not re.search(r"(?<![<>=!])=(?!=)", s)
                      or stmts[-1].rstrip().endswith(("+", "-", "*", "/", "(", ","))):
            stmts[-1] += s
        else:
            stmts.append(s)
    return [re.sub(r"\s+", "", t) for t in stmts]


def lhs_var(eq: str) -> str | None:
    left = eq.split("=", 1)[0]
    m = RE_LHS.match(left)
    return m.group(1) if m else None


def main() -> None:
    items = parse()
    by_name = {it["name"]: it for it in items}
    for it in items:
        it["eqs"] = []
    # 式を左辺の変数名で見出しに振り直す（左辺が見出しにない式はその見出しに残す）
    for it in items:
        it["notes"] = [t for t in it["lines"] if NONASCII.search(t)]
        for eq in split_statements([t for t in it.pop("lines") if not NONASCII.search(t)]):
            v = lhs_var(eq)
            target = by_name.get(v, it) if v else it
            target["eqs"].append(eq)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"見出し {len(items)} 件 → {OUT}")
    print("ブロック別:", dict(Counter(i["block"] for i in items)))
    print("推計式（統計あり）:", sum(1 for i in items if i["stats"]))
    noeq = [i["name"] for i in items if not i["eqs"]]
    multi = [i["name"] for i in items if len(i["eqs"]) > 1]
    print(f"式なし {len(noeq)}: {noeq[:20]}")
    print(f"式が複数 {len(multi)}: {multi[:20]}")


if __name__ == "__main__":
    main()
