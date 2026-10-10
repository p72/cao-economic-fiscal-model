"""国立社会保障・人口問題研究所「日本の将来推計人口（令和5年推計）」の表1-9A（男女年齢5歳階級別人口、出生中位・死亡中位）を取得する.

出力: data/raw/ipss/ipss2023_1-9A.xlsx（主要計数表の再現 projection.py で使う）
取得元: https://www.ipss.go.jp/pp-zenkoku/j/zenkoku2023/db_zenkoku2023/db_r5_suikeikekka_1.html
"""
from __future__ import annotations

from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ipss" / "ipss2023_1-9A.xlsx"
URL = "https://www.ipss.go.jp/pp-zenkoku/j/zenkoku2023/db_zenkoku2023/s_tables/1-9A.xlsx"


def main() -> None:
    if OUT.exists():
        print("将来推計人口: 取得済み")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=120, headers={"User-Agent": "cao-economic-fiscal-model (research use)"})
    r.raise_for_status()
    OUT.write_bytes(r.content)
    print(f"取得: {OUT.name}")


if __name__ == "__main__":
    main()
