"""国民経済計算 年次推計（2024年度、2020年基準）の統計表を読む.

fetch_sna.py で data/raw/kakuhou2024_{code}.xlsx に保存した表を使う。表の形は3種類ある。
- 時系列表（ffm1n, ffm2, i5, s16, ss5 など）: 行=項目、列=年度 → fy_table
- 部門別表（s6, ss3）: 年度ごとに「中央政府・地方政府・社会保障基金・合計」の4列 → sector_table
- 固定資本ストックマトリックス（ss4n, ss4rn）: 年ごとのシート、行=資産分類、列=制度部門 → stock_matrix
項目名は全角空白を除いた文字列。同じ名前の行があり得るので、順番を保ったリストで返す。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
YEAR = 2024


def _path(code: str) -> Path:
    return RAW / f"kakuhou{YEAR}_{code}.xlsx"


def _label(x) -> str:
    s = str(x).replace("　", "").replace(" ", "").strip()
    return "" if s == "nan" else s


@lru_cache(maxsize=None)
def fy_table(code: str, sheet: str | None = None) -> list[tuple[str, dict[int, float]]]:
    """時系列表を [(項目名, {年度: 値})] で返す。sheet 省略時は「年度」を含む最初のシート."""
    x = pd.ExcelFile(_path(code))
    if sheet is None:
        sheet = next((s for s in x.sheet_names if "年度" in s), x.sheet_names[0])
    raw = pd.read_excel(x, sheet, header=None)
    hdr_row, cols = None, {}
    for i in range(min(12, len(raw))):
        found = {}
        for j, v in enumerate(raw.iloc[i]):
            m = re.search(r"((?:19|20)\d\d)", str(v))
            if m:
                found[j] = int(m.group(1))
        if len(found) >= 10:
            hdr_row, cols = i, found
            break
    if hdr_row is None:
        raise ValueError(f"{code}/{sheet}: 年の見出し行がない")
    out = []
    for i in range(hdr_row + 1, len(raw)):
        lab = _label(raw.iloc[i, 0]) or _label(raw.iloc[i, 1])
        if not lab:
            continue
        vals = {y: pd.to_numeric(raw.iloc[i, j], errors="coerce") for j, y in cols.items()}
        if all(pd.isna(v) for v in vals.values()):
            continue
        out.append((lab, vals))
    return out


def fy(code: str, label: str, nth: int = 0, sheet: str | None = None, year: int = YEAR) -> float:
    """時系列表から項目名（前方一致）の値を取る。nth は同名の何番目か."""
    hits = [v for lab, v in fy_table(code, sheet) if lab.startswith(label)]
    if len(hits) <= nth:
        raise KeyError(f"{code}: 項目「{label}」がない")
    return float(hits[nth][year])


@lru_cache(maxsize=None)
def sector_table(code: str, year: int = YEAR) -> list[tuple[str, dict[str, float]]]:
    raw = pd.read_excel(_path(code), header=None)
    # 年の見出し（「2024」を含むセル）と、その近くの部門名の列を探す
    yr_cols = [j for j, v in enumerate(raw.iloc[4]) if f"（{year}）" in str(v)]
    if not yr_cols:
        raise ValueError(f"{code}: {year} の列がない")
    c = yr_cols[0]
    sect = {}
    for j in range(max(c - 2, 1), min(c + 5, raw.shape[1])):
        s = _label(raw.iloc[5, j])
        if s in ("中央政府", "地方政府", "社会保障基金", "合計") and s not in sect.values():
            sect[j] = s
    out = []
    for i in range(6, len(raw)):
        lab = _label(raw.iloc[i, 0])
        if not lab or lab.startswith("（注"):
            continue
        vals = {s: pd.to_numeric(raw.iloc[i, j], errors="coerce") for j, s in sect.items()}
        if all(pd.isna(v) for v in vals.values()):
            continue
        out.append((lab, {k: (0.0 if pd.isna(v) else float(v)) for k, v in vals.items()}))
    return out


def sector(code: str, label: str, nth: int = 0, year: int = YEAR) -> dict[str, float]:
    hits = [v for lab, v in sector_table(code, year) if lab.startswith(label)]
    if len(hits) <= nth:
        raise KeyError(f"{code}: 項目「{label}」がない")
    return hits[nth]


@lru_cache(maxsize=None)
def stock_matrix(code: str, sheet: str = "令和６") -> pd.DataFrame:
    """固定資本ストック（年末）: 行=資産分類、列=制度部門（列名は見出しをつないだ文字列）."""
    raw = pd.read_excel(_path(code), sheet, header=None)
    # 6〜9列目の見出し（制度部門）が行方向に並んでいるので、転置して読む
    t = raw.T
    names = []
    for j in range(len(t)):
        parts = [_label(t.iloc[j, k]) for k in (5, 6, 7)]
        names.append("/".join(p for p in parts if p))
    # 部門名は上の段から引き継ぐ
    cur = ["", "", ""]
    full = []
    for j in range(len(t)):
        parts = [_label(t.iloc[j, k]) for k in (5, 6, 7)]
        for k, p in enumerate(parts):
            if p:
                cur[k] = p
                for kk in range(k + 1, 3):
                    cur[kk] = "" if not parts[kk] else parts[kk]
                break
        full.append("/".join(p for p in cur if p))
    rows = [_label(t.iloc[0, i]) for i in range(t.shape[1])]
    df = pd.DataFrame(t.iloc[1:, :].values, columns=rows, index=full[1:])
    return df.apply(pd.to_numeric, errors="coerce").T
