"""国民経済計算 年次推計（2020年基準）の統計表を ESRI サイトから取得する.

出力: data/raw/kakuhou{YEAR}_{code}.xlsx
ESRI データ取得の共通処理は esri-data スキルのモジュール（scripts/esri_data.py）を使う。
環境変数 ESRI_DATA_SKILL でスキルのディレクトリを指定する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# 使う表: GDP（年度・名目/実質/デフレーター）、分配、所得支出勘定（一般政府・家計）、
# 一般政府の部門別勘定、社会保障、制度部門別純貸出、海外勘定、ストック
CODES = ["ffm1n", "ffm1rn", "ffm1dn", "ffm2", "i4", "i5", "s6", "s9", "s10", "s16", "s18",
         "s19", "ss3", "ss4n", "ss4rn", "ss5", "a4"]


def main() -> None:
    skill = os.environ.get("ESRI_DATA_SKILL")
    if not skill:
        sys.exit("環境変数 ESRI_DATA_SKILL に esri-data スキルのディレクトリを指定してください")
    sys.path.insert(0, skill)
    from scripts.esri_data import get_latest_kakuhou_year, list_kakuhou_tables, polite_get

    year = get_latest_kakuhou_year()
    tables = list_kakuhou_tables(year).drop_duplicates("code").set_index("code")
    RAW.mkdir(parents=True, exist_ok=True)
    for code in CODES:
        out = RAW / f"kakuhou{year}_{code}.xlsx"
        if out.exists():
            continue
        out.write_bytes(polite_get(tables.loc[code, "url"]))
        print(f"取得: {code} → {out.name}")


if __name__ == "__main__":
    main()
