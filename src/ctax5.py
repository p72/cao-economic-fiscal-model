"""シナリオ: 消費税率を2027年度から恒久的に5%（標準税率10%・軽減税率8%をともに5%）に下げたら.

中長期試算（2026年1月）の3ケースの再現経路（projection.py）を減税なしの経路とし、誤差項はそのままで
2027〜2035年度を解き直す。実質の政府消費・公的固定資本形成は減税なしと同じに保つ（乗数表と同じ前提）。
地方消費税の割合（Z_RTCIVC、Z_RTCIVL）は変えない。

再現経路の最終状態（data と af）は output/parts/proj_state_{case}.pkl に保存する。ないときは projection.py を
実行して作る（1ケース約30分、高成長実現ケースは成長移行ケースの後）。
出力: output/ctax5_scenario.csv（列: case, scen（base=減税なし、cut=減税）, year, 各変数）
"""
from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pandas as pd

import projection as P
from chuuchouki import hold_real_g
from solver import Solver
from spec import build, compile_eq

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "parts"
YEARS = list(range(2027, 2036))
RATE = 0.05
CASES = ("kako", "seicho", "koseicho")


def state(case: str) -> dict:
    path = STATE_DIR / f"proj_state_{case}.pkl"
    if not path.exists() or "t" in pickle.loads(path.read_bytes()):   # "t" があるのは途中の状態
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        P.DEBUG_DIR = str(STATE_DIR)
        if case == "koseicho" and not P.PINT_AF_FILE.exists():
            P.run("seicho")
        P.run(case)
    return pickle.loads(path.read_bytes())


def row(case: str, scen: str, d: dict, t: int) -> dict:
    g = lambda v: (d[v][t] / d[v][t - 1] - 1) * 100  # noqa: E731
    return {"case": case, "scen": scen, "year": t, "rgdp": d["M_GDP"][t], "rgdp_g": g("M_GDP"),
            "ngdp": d["M_GDPV"][t] / 1000, "cpi_g": g("M_CPIG"), "pgdp_g": g("M_PGDP"), "cp": d["M_CP"][t],
            "pb": d["M_PBGAGDPV"][t], "debt": d["Z_DEBTAGDP"][t], "rgb": d["M_RGB"][t], "tciv": d["Z_TCIV"][t] / 1000}


def run(case: str, check: bool = False) -> list[dict]:
    """check=True なら減税せずに解き直す（減税なしの経路と一致するかの確認）."""
    m = build("calibrated", "port")
    m.eqs.append(compile_eq("Z_EXPX35E", "Z_EXPX35E=Z_EXPX35+Z_ADJEXPX35E"))   # projection.py と同じ
    m.meta["Z_EXPX35E"] = {"label": "（追加: その他一般歳出の SNA 用）", "block": "fiscal", "estimated": False}
    st = state(case)
    base, af = st["data"], copy.deepcopy(st["af"])
    data = copy.deepcopy(base)
    if not check:
        for t in YEARS:
            data["Z_RTCIV"][t] = data["Z_RTCIV2"][t] = RATE
    s = Solver(m, data, af)
    for t in YEARS:
        P.solve(s, t)
        hold_real_g(s, "ctax", t, base, set())
    rows = [row(case, scen, d, t) for t in [2026] + YEARS for scen, d in (("base", base), ("cut", data))]
    b = {r["year"]: r for r in rows if r["scen"] == "base"}
    c = {r["year"]: r for r in rows if r["scen"] == "cut"}
    for t in (2027, 2030, 2035):
        print(f"{case} {t}: 実質GDP {(c[t]['rgdp'] / b[t]['rgdp'] - 1) * 100:+.2f}%  消費者物価 {b[t]['cpi_g']:.2f}→"
              f"{c[t]['cpi_g']:.2f}  PB {b[t]['pb']:.2f}→{c[t]['pb']:.2f}  残高比 {b[t]['debt']:.1f}→{c[t]['debt']:.1f}  "
              f"消費税収 {b[t]['tciv']:.1f}→{c[t]['tciv']:.1f}兆円  長期金利 {b[t]['rgb']:.2f}→{c[t]['rgb']:.2f}", flush=True)
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="減税せずに解き直し、減税なしの経路と一致するか確かめる")
    a = ap.parse_args()
    df = pd.DataFrame([r for c in CASES for r in run(c, a.check)])
    if not a.check:
        out = ROOT / "output" / "ctax5_scenario.csv"
        df.to_csv(out, index=False)
        print(f"→ {out}")
