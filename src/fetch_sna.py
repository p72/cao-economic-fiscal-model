"""国民経済計算 2024年度年次推計（2020年基準）の統計表を ESRI のサイトから取得する.

出力: data/raw/kakuhou2024_{code}.xlsx
取得元: https://www.esri.cao.go.jp/jp/sna/data/data_list/kakuhou/files/2024/2024_kaku_top.html
このページに並んでいる Excel ファイルのリンクから、使う表だけをダウンロードする。
モデルの出発点は2024年度なので、新しい年次推計が公表されても2024年度版を使う。
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
YEAR = 2024
TOP = f"https://www.esri.cao.go.jp/jp/sna/data/data_list/kakuhou/files/{YEAR}/{YEAR}_kaku_top.html"
HEADERS = {"User-Agent": "cao-economic-fiscal-model (research use; https://github.com/p72/cao-economic-fiscal-model)"}

# 使う表: GDP（年度・名目/実質/デフレーター）、分配、所得支出勘定（一般政府・家計）、
# 一般政府の部門別勘定、社会保障、制度部門別純貸出、海外勘定、ストック
CODES = ["ffm1n", "ffm1rn", "ffm1dn", "ffm2", "i4", "i5", "s6", "s9", "s10", "s16", "s18",
         "s19", "ss3", "ss4n", "ss4rn", "ss5", "a4"]


def table_links() -> dict[str, str]:
    """年次推計のトップページから、表の記号 → Excel ファイルの URL を作る."""
    r = requests.get(TOP, headers=HEADERS, timeout=60)
    r.raise_for_status()
    html = r.content.decode(r.apparent_encoding or "utf-8", errors="replace")
    links = {}
    for href in re.findall(r'href="([^"]+\.xlsx?)"', html, re.I):
        if "tables/" not in href:
            continue
        name = href.rsplit("/", 1)[-1]
        code = re.sub(r"_jp\.xlsx?$", "", re.sub(r"^\d{4}", "", name))
        links.setdefault(code, urljoin(TOP, href))
    return links


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [c for c in CODES if not (RAW / f"kakuhou{YEAR}_{c}.xlsx").exists()]
    if not todo:
        print("国民経済計算: 取得済み")
        return
    links = table_links()
    missing = [c for c in todo if c not in links]
    if missing:
        raise SystemExit(f"年次推計のページに見つからない表: {missing}（{TOP}）")
    for code in todo:
        out = RAW / f"kakuhou{YEAR}_{code}.xlsx"
        r = requests.get(links[code], headers=HEADERS, timeout=120)
        r.raise_for_status()
        out.write_bytes(r.content)
        print(f"取得: {code} → {out.name}")
        time.sleep(1.0)   # サイトに負荷をかけないよう間隔をあける


if __name__ == "__main__":
    main()
