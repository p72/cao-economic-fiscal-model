"""経済財政モデル（2026年度版）の資料集PDFを内閣府サイトから取得し、テキストを抽出する.

資料はリポジトリには含めない。最初に実行する。取得済みなら再取得しない。
出力: reference/ef2026_{summary,equ,var,all}.pdf と同名の .txt
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
import requests

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
BASE = "https://www5.cao.go.jp/keizai3/econome/"
FILES = {
    "summary": "ef2rrrrrr-summary.pdf",  # 1. 概要・乗数
    "equ": "ef2rrrrrr-equ.pdf",  # 2. 方程式リスト
    "var": "ef2rrrrrr-var.pdf",  # 3. 変数リスト
    "all": "ef2rrrrrr-all.pdf",  # 全体版
}


def main() -> None:
    REF.mkdir(exist_ok=True)
    for key, name in FILES.items():
        pdf = REF / f"ef2026_{key}.pdf"
        if not pdf.exists():
            r = requests.get(BASE + name, timeout=120)
            r.raise_for_status()
            pdf.write_bytes(r.content)
            print(f"取得: {BASE + name} → {pdf.name} ({len(r.content):,} bytes)")
        doc = pymupdf.open(pdf)
        out = pdf.with_suffix(".txt")
        with out.open("w", encoding="utf-8") as f:
            for i, page in enumerate(doc):
                f.write(f"\n===== PAGE {i + 1} =====\n")
                f.write(page.get_text(sort=True))
        print(f"抽出: {pdf.name} {doc.page_count} ページ → {out.name}")


if __name__ == "__main__":
    main()
