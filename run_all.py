"""データの取得から、乗数の計算・図の作成までを順に実行する.

    python run_all.py          # 主な結果（移植版の乗数表、中長期試算の感応度分析）。約15〜20分
    python run_all.py --all    # README のすべての結果（4通りの乗数表、シナリオの図、主要計数表の再現も）。約2〜3時間
    python run_all.py --next   # 次の1単位（長くて70秒程度）だけ実行する。「すべて完了」と出るまで繰り返す
    python run_all.py --list   # 実行する単位の一覧と進み具合

--next は、1回の実行時間に上限がある環境のためのもの。
進み具合は output/parts/progress.json に記録する（--reset で最初からやり直す）。
取得済みのデータ（資料集の PDF、国民経済計算の Excel）は再取得しない。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PROGRESS = ROOT / "output" / "parts" / "progress.json"
SIM_CASES = range(1, 9)
CHUU_PARTS = ["tfp:kako", "rate:kako", "rate:seicho", "gov:kako", "gov:seicho"]


def units(all_results: bool) -> list[tuple[str, str, list[str]]]:
    """（説明, スクリプト, 引数）の並び."""
    u = [("資料集（方程式リストなど）を取得", "fetch_paper.py", []),
         ("方程式リストを読み取る", "parse_equations.py", []),
         ("国民経済計算（2024年度年次推計）を取得", "fetch_sna.py", [])]
    if not (ROOT / "data" / "raw" / "lfs_fy.csv").exists():
        u.append(("労働力調査を取得（e-Stat）", "fetch_lfs.py", []))
    u.append(("公表乗数表を読み取る", "published.py", []))
    configs = [("calibrated", "port")]
    if all_results:
        configs = [("calibrated", "simple"), ("faithful", "simple"), ("calibrated", "port"), ("faithful", "port")]
    for mode, fiscal in configs:
        opt = ["--mode", mode, "--fiscal", fiscal]
        u.append((f"標準ケースを作る（{mode}、{fiscal}）", "baseline.py", opt))
        for c in SIM_CASES:
            u.append((f"乗数を計算（{mode}、{fiscal}、ケース{c}）", "simulate.py", opt + ["--case", str(c)]))
        u.append((f"乗数をまとめる（{mode}、{fiscal}）", "simulate.py", opt + ["--merge"]))
    if all_results:
        for mode in ("calibrated", "faithful"):
            u.append((f"シナリオを計算（{mode}）", "scenario.py", ["--mode", mode]))
        u.append(("シナリオの図", "plot_scenario.py", []))
        u.append(("シナリオの図（2つのモードの比較）", "plot_scenario.py", ["--compare"]))
    for v in ("kako", "seicho"):
        u.append((f"標準ケースを作る（中長期試算の {v}）", "baseline.py",
                  ["--mode", "calibrated", "--fiscal", "port", "--variant", v]))
    for p in CHUU_PARTS:
        u.append((f"中長期試算の感応度分析を計算（{p}）", "chuuchouki.py", ["--part", p]))
    u.append(("中長期試算の感応度分析をまとめる", "chuuchouki.py", ["--merge"]))
    u.append(("中長期試算の感応度分析の図", "plot_chuuchouki.py", []))
    if all_results:   # 主要計数表の再現は1ケース20〜30分かかるので --all のときだけ
        u.append(("将来推計人口を取得（社人研）", "fetch_ipss.py", []))
        for v in ("proj_kako", "proj_seicho"):
            u.append((f"標準ケースを作る（主要計数表の {v}）", "baseline.py",
                      ["--mode", "calibrated", "--fiscal", "port", "--variant", v]))
        for c in ("kako", "seicho", "koseicho"):
            u.append((f"主要計数表を再現（{c}）", "projection.py", ["--case", c]))
        u.append(("主要計数表の表と図", "plot_projection.py", []))
    return u


def key(unit: tuple[str, str, list[str]]) -> str:
    return " ".join([unit[1], *unit[2]])


def run_unit(i: int, n: int, unit: tuple[str, str, list[str]]) -> None:
    title, script, args = unit
    print(f"\n=== [{i}/{n}] {title} ===", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(SRC / script), *args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"\n失敗: {title}（{key(unit)}）。上のエラーを確認してください。")
    print(f"--- 完了（{time.time() - t0:.0f}秒）", flush=True)


def load_progress(all_results: bool) -> set[str]:
    if PROGRESS.exists():
        p = json.loads(PROGRESS.read_text(encoding="utf-8"))
        if p.get("all") == all_results:
            return set(p["done"])
    return set()


def save_progress(all_results: bool, done: set[str]) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps({"all": all_results, "done": sorted(done)}, ensure_ascii=False, indent=1),
                        encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="README のすべての結果を作る")
    ap.add_argument("--next", action="store_true", help="次の1単位だけ実行する")
    ap.add_argument("--list", action="store_true", help="単位の一覧と進み具合を表示する")
    ap.add_argument("--reset", action="store_true", help="--next の進み具合を消して最初からにする")
    a = ap.parse_args()
    us = units(a.all)
    if a.reset and PROGRESS.exists():
        PROGRESS.unlink()
    done = load_progress(a.all)
    if a.list:
        for i, u in enumerate(us, 1):
            print(f"{'済' if key(u) in done else '　'} {i:2d}. {u[0]}")
        return
    if a.next:
        todo = [(i, u) for i, u in enumerate(us, 1) if key(u) not in done]
        if not todo:
            print("すべて完了。結果は output/ にある（multipliers_port.csv、chuuchouki_sensitivity.png など）。")
            return
        i, u = todo[0]
        run_unit(i, len(us), u)
        done.add(key(u))
        save_progress(a.all, done)
        left = len(todo) - 1
        if left:
            print(f"残り {left} 単位。もう一度 python run_all.py --next を実行してください。")
        else:
            print("すべて完了。結果は output/ にある（multipliers_port.csv、chuuchouki_sensitivity.png など）。")
        return
    for i, u in enumerate(us, 1):
        run_unit(i, len(us), u)
    save_progress(a.all, {key(u) for u in us})
    print("\nすべて完了。結果は output/ にある（multipliers_port.csv、chuuchouki_sensitivity.png など）。")


if __name__ == "__main__":
    main()
