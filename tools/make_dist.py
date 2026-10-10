"""配布用の ZIP（コード＋資料集の PDF＋国民経済計算の Excel）を作る.

    python tools/make_dist.py   → dist/cao-economic-fiscal-model-with-data.zip

ZIP を展開すれば、インターネットにつながらない環境（AI のチャット画面の Python など）でも
python run_all.py --next を繰り返すだけで計算できる。先に fetch_paper.py と fetch_sna.py で
データを取得しておくこと。GitHub の Releases にこの ZIP を載せて配布する。
"""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "cao-economic-fiscal-model"
OUT = DIST / f"{NAME}-with-data.zip"

NOTICE = """# 同梱しているデータの出典

この ZIP には、計算に必要な次の資料・統計を同梱している。いずれも内閣府のウェブサイトのコンテンツで、
「公共データ利用規約（第1.0版）」（デジタル庁）のもとで複製・再配布している（https://www.cao.go.jp/notice/rule.html ）。
内容は取得したままで、加工していない。

- reference/ef2026_summary.pdf、ef2026_equ.pdf、ef2026_var.pdf、ef2026_all.pdf
  出典：内閣府「経済財政モデル（2026年度版）資料集」（ https://www5.cao.go.jp/keizai3/econome.html ）
- data/raw/kakuhou2024_*.xlsx
  出典：内閣府経済社会総合研究所「2024年度国民経済計算（2020年基準・2008SNA）」
  （ https://www.esri.cao.go.jp/jp/sna/data/data_list/kakuhou/files/2024/2024_kaku_top.html ）

リポジトリに含めているその他のデータ（労働力調査の集計、財務省の国債の統計、社会保障の統計の出典一覧）の出典は
README の「参照資料」の節にある。

このモデルは公表資料から再現したもので、内閣府の公式のモデルではない。
"""


def main() -> None:
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                             check=True).stdout.split("\n")
    files = [ROOT / f for f in tracked if f and (ROOT / f).is_file()]
    pdfs = [ROOT / "reference" / f"ef2026_{k}.pdf" for k in ("summary", "equ", "var", "all")]
    sna = sorted((ROOT / "data" / "raw").glob("kakuhou2024_*.xlsx"))
    missing = [p for p in pdfs if not p.exists()]
    if missing or len(sna) < 17:
        raise SystemExit("先に python src/fetch_paper.py と python src/fetch_sna.py を実行してください")
    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files + pdfs + sna:
            z.write(p, f"{NAME}/{p.relative_to(ROOT).as_posix()}")
        z.writestr(f"{NAME}/DATA_NOTICE.md", NOTICE)
    print(f"→ {OUT}（{OUT.stat().st_size / 1e6:.1f} MB、{len(files) + len(pdfs) + len(sna) + 1} ファイル）")


if __name__ == "__main__":
    main()
