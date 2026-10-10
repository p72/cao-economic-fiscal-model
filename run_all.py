"""データの取得から、乗数の計算・図の作成までを順に実行する.

    python run_all.py          # 主な結果（移植版の乗数表、中長期試算の感応度分析）。約15〜20分
    python run_all.py --all    # README のすべての結果（4通りの乗数表、シナリオの図も）。約40〜60分

途中で止まった場合は、同じコマンドをもう一度実行すればよい（取得済みのデータは再取得しない）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def step(title: str, script: str, *args: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(SRC / script), *args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"\n失敗: {title}（{script} {' '.join(args)}）。上のエラーを確認してください。")
    print(f"--- 完了（{time.time() - t0:.0f}秒）", flush=True)


def main(all_results: bool) -> None:
    # 1. データ
    step("1/6 内閣府の資料集（方程式リストなど）を取得", "fetch_paper.py")
    step("2/6 方程式リストを読み取る", "parse_equations.py")
    step("3/6 国民経済計算（2024年度年次推計）を取得", "fetch_sna.py")
    if not (ROOT / "data" / "raw" / "lfs_fy.csv").exists():
        step("3/6 労働力調査を取得（e-Stat）", "fetch_lfs.py")
    step("4/6 公表乗数表を読み取る", "published.py")
    # 2. 乗数表（財政ブロック移植版）
    configs = [("calibrated", "port")]
    if all_results:
        configs = [("calibrated", "simple"), ("faithful", "simple"), ("calibrated", "port"), ("faithful", "port")]
    for mode, fiscal in configs:
        step(f"5/6 標準ケースを作る（{mode}、{fiscal}）", "baseline.py", "--mode", mode, "--fiscal", fiscal)
        step(f"5/6 8ケースの乗数を計算（{mode}、{fiscal}）", "simulate.py", "--mode", mode, "--fiscal", fiscal)
    if all_results:
        for mode in ("calibrated", "faithful"):
            step(f"5/6 シナリオを計算（{mode}）", "scenario.py", "--mode", mode)
        step("5/6 シナリオの図", "plot_scenario.py")
        step("5/6 シナリオの図（2つのモードの比較）", "plot_scenario.py", "--compare")
    # 3. 中長期試算の感応度分析
    for v in ("kako", "seicho"):
        step(f"6/6 標準ケースを作る（中長期試算の {v}）", "baseline.py", "--mode", "calibrated", "--fiscal", "port",
             "--variant", v)
    step("6/6 中長期試算の感応度分析を計算", "chuuchouki.py")
    step("6/6 中長期試算の感応度分析の図", "plot_chuuchouki.py")
    print("\nすべて完了。結果は output/ にある（multipliers_port.csv、chuuchouki_sensitivity.png など）。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="README のすべての結果を作る")
    main(ap.parse_args().all)
