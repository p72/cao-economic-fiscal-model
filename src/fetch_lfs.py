"""労働力調査（年度平均）の年齢階級・男女別の人口・労働力・就業者・失業者・雇用者を e-Stat から取得する.

出力: data/raw/lfs_fy.csv（列: table, sex, status, age, fy, value。単位は万人）
e-Stat の共通処理は estat-api スキルのモジュール（scripts/estat_api.py）を使う。
環境変数 ESTAT_API_SKILL でスキルのディレクトリを指定する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "lfs_fy.csv"

AGES = ["02", "05", "07", "08", "10", "11", "13", "14", "16", "17", "19", "20", "00"]  # 5歳階級＋15歳以上
TABLES = {
    # 労働力状態、年齢階級別15歳以上人口（年度）: 15歳以上人口・労働力人口・就業者・完全失業者
    "0002060062": {"cdCat03": "00,01,02,08"},
    # 従業上の地位、年齢階級別就業者数（年度）: 雇用者
    "0002060063": {"cdCat03": "08"},
}


def main() -> None:
    skill = os.environ.get("ESTAT_API_SKILL")
    if not skill:
        sys.exit("環境変数 ESTAT_API_SKILL に estat-api スキルのディレクトリを指定してください")
    sys.path.insert(0, skill)
    from scripts.estat_api import get_stats_df

    frames = []
    for sid, flt in TABLES.items():
        df = get_stats_df(sid, cdCat01="000", cdCat02="1,2", cdCat04=",".join(AGES),
                          cdTimeFrom="2015100000", **flt)
        frames.append(pd.DataFrame({
            "table": sid, "sex": df["cat02_code"].map({"1": "M", "2": "F"}),
            "status": df["cat03_name"], "age": df["cat04_name"],
            "fy": df["time_code"].str[:4].astype(int), "value": df["value"],
        }))
    out = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{len(out)} 行 → {OUT}（最新 {out['fy'].max()} 年度）")


if __name__ == "__main__":
    main()
