"""シナリオ: 同じ規模（名目GDPの1%）の消費税減税・所得税減税・公共投資を10年間続けたら.

標準ケース（baseline.py）からの乖離を2026〜2035年度で計算する。
出力: output/scenario_fiscal.csv（calibrated）、output/scenario_fiscal_faithful.csv（faithful）
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

import simulate as SIM
from solver import Solver
from spec import build

ROOT = Path(__file__).resolve().parents[1]
START, N = 2026, 10
YEARS = list(range(START, START + N))

SCENARIOS = {
    "ctax": "消費税減税",
    "itax": "所得税減税",
    "pubinv": "公共投資",
}


def out_path(mode: str, fiscal: str = "simple") -> Path:
    import baseline as BL
    return ROOT / "output" / f"scenario_fiscal{BL.suffix(mode, fiscal)}.csv"


VARS = {"M_GDP": "pct", "M_CPIG": "pct", "M_PBGAGDPV": "pt", "Z_DEBTAGDP": "pt", "M_CP": "pct", "M_IFP": "pct"}


def shock(name: str, data: dict, base: dict) -> None:
    for t in YEARS:
        size = 0.01 * base["M_GDPV"][t]
        if name == "ctax":
            # 事前の税収減が名目GDPの1%になるだけ、標準税率と軽減税率を同じ幅で下げる（課税ベースは標準ケースの値）
            rt, rt2 = base["Z_RTCIV"][t], base["Z_RTCIV2"][t]
            b1, b2 = base["Z_TCIVB"][t] / (rt / (1 + rt)), base["Z_TCIVR"][t] / (rt2 / (1 + rt2))
            cut = lambda x: b1 * (rt / (1 + rt) - (rt - x) / (1 + rt - x)) + b2 * (rt2 / (1 + rt2) - (rt2 - x) / (1 + rt2 - x))  # noqa: E731
            lo, hi = 0.0, rt2
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if cut(mid) < size else (lo, mid)
            data["Z_RTCIV"][t], data["Z_RTCIV2"][t] = rt - lo, rt2 - lo
        elif name == "itax":
            data["Z_TYPVX"][t] = -size
        elif name == "pubinv":
            # 実質公的固定資本形成を実質GDPの1%相当増やす（国・地方 1:1）
            dg = 0.01 * base["M_GDP"][t]
            data["M_IGR1"][t] = base["M_IGR1"][t] + 0.5 * dg
            data["M_IGR3"][t] = base["M_IGR3"][t] + 0.5 * dg


def run(mode: str = "calibrated", fiscal: str = "simple") -> pd.DataFrame:
    m = build(mode, fiscal)
    base, af = SIM.load(mode, fiscal)
    rows = []
    for name, label in SCENARIOS.items():
        data = copy.deepcopy(base)
        shock(name, data, base)
        s = Solver(m, data, af)
        for t in YEARS:
            s.solve_year(t, calibrate_pinned=False)
        for k, t in enumerate(YEARS):
            for v, kind in VARS.items():
                dev = (data[v][t] / base[v][t] - 1) * 100 if kind == "pct" else data[v][t] - base[v][t]
                rows.append({"scenario": name, "label": label, "var": v, "year": t, "period": k + 1, "dev": dev})
        print(f"{label}: 消費税率 {data['Z_RTCIV'][START]*100:.2f}%" if name == "ctax" else label)
    df = pd.DataFrame(rows)
    out = out_path(mode, fiscal)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    ap.add_argument("--fiscal", default="simple", choices=["simple", "port"])
    a = ap.parse_args()
    df = run(a.mode, a.fiscal)
    pd.set_option("display.width", 200)
    print(df[df.period.isin([1, 3, 5, 10])].pivot_table(index=["var", "label"], columns="period", values="dev").round(2).to_string())
