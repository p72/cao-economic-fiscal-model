"""公表されている主要乗数表（経済財政モデル 2026年度版 資料集「主要乗数表」）を読む.

出力: data/processed/published_multipliers.csv（列: case, var, period, value）
各ケースは3つの表（各5期）からなる。資料では1ページに2ケースずつ、ケース番号順に並ぶ。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reference" / "ef2026_summary.txt"
OUT = ROOT / "data" / "processed" / "published_multipliers.csv"

COLS = [
    # 表1（％）
    ["M_GDP", "M_CP", "M_IFP", "M_IHP", "M_G", "M_XGS", "M_MGS", "M_FXS"],
    # 表2（潜在GDP・デフレーター・物価・就業者は％、GDPギャップ・金利・失業率は％pt）
    ["M_GDPP", "M_GAP", "M_PGDP", "M_CPIG", "M_RCO", "M_RGB", "M_UR", "M_LE"],
    # 表3（名目GDP・国民所得・可処分所得・賃金は％、その他は対GDP比の％pt）
    ["M_GDPV", "M_NIV", "M_YDV", "M_W", "M_BCVAGDPV", "TAXAGDP", "M_BGVAGDPV", "M_PBGAGDPV", "Z_DEBTAGDP"],
]
CASES = {
    1: "実質政府支出を実質GDPの1%相当、1年間だけ増やす",
    2: "実質政府支出を実質GDPの1%相当増やし、GDP比を継続",
    3: "法人税を名目GDPの1%相当増税し、GDP比を継続",
    4: "個人所得税を名目GDPの1%相当増税し、GDP比を継続",
    5: "消費税率を1%pt引き上げ",
    6: "TFP上昇率を1%pt引き上げ",
    7: "原油価格を20%引き上げ",
    8: "短期金利を1%pt引き上げ",
}
ROW = re.compile(r"^\s*([1-5])\s+((?:-?\d+\.\d+\s*){8,9})$")


def main() -> pd.DataFrame:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    rows = []
    for ln in lines:
        m = ROW.match(ln)
        if m:
            rows.append((int(m.group(1)), [float(x) for x in m.group(2).split()]))
    if len(rows) != 8 * 3 * 5:
        raise ValueError(f"乗数表の行が {len(rows)} 行（8ケース×3表×5期=120行のはず）")
    out = []
    for i, (period, vals) in enumerate(rows):
        case, table = i // 15 + 1, (i % 15) // 5
        cols = COLS[table]
        if len(vals) != len(cols):
            raise ValueError(f"ケース{case} 表{table + 1} 期{period}: 列数 {len(vals)}")
        for c, v in zip(cols, vals):
            out.append({"case": case, "var": c, "period": period, "value": v})
    df = pd.DataFrame(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    return df


if __name__ == "__main__":
    df = main()
    print(df.pivot_table(index=["case", "period"], columns="var", values="value").loc[(slice(None), 1), ["M_GDP", "M_CPIG", "M_RCO", "Z_DEBTAGDP"]])
