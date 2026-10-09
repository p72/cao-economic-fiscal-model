"""公表乗数表と同じ8ケースのショックを与え、標準ケースからの乖離を計算する.

ベースライン（baseline.py）のアドファクターを固定したまま、2026年度（1期目）から5年間を解く。
出力: output/multipliers.csv（calibrated）、output/multipliers_faithful.csv（faithful）
      列: case, var, period, model, published
"""
from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pandas as pd

import baseline as BL
import published as P
from solver import Solver
from spec import build

ROOT = Path(__file__).resolve().parents[1]
START, N = 2026, 5
YEARS = list(range(START, START + N))

PCT = ["M_GDP", "M_CP", "M_IFP", "M_IHP", "M_G", "M_XGS", "M_MGS", "M_FXS", "M_GDPP", "M_PGDP", "M_CPIG",
       "M_LE", "M_GDPV", "M_NIV", "M_YDV", "M_W"]
PT = ["M_GAP", "M_RCO", "M_RGB", "M_UR", "M_BCVAGDPV", "TAXAGDP", "M_BGVAGDPV", "M_PBGAGDPV", "Z_DEBTAGDP"]


def out_path(mode: str) -> Path:
    return ROOT / "output" / ("multipliers.csv" if mode == "calibrated" else f"multipliers_{mode}.csv")


def load(mode: str = "calibrated"):
    with BL.out_path(mode).open("rb") as f:
        b = pickle.load(f)
    return b["data"], b["af"]


def gov_split(data: dict, t: int) -> dict[str, float]:
    """実質政府支出の追加分の配分（国・地方 1:1、各々の中は消費と投資の標準ケースの比）."""
    c = {k: data[k][t] for k in ("M_CGRCC", "M_CGRIC", "M_IGR1", "M_CGRCL", "M_CGRIL", "M_IGR3")}
    sc = c["M_CGRCC"] + c["M_CGRIC"] + c["M_IGR1"]
    sl = c["M_CGRCL"] + c["M_CGRIL"] + c["M_IGR3"]
    w = {k: 0.5 * c[k] / sc for k in ("M_CGRCC", "M_CGRIC", "M_IGR1")}
    w.update({k: 0.5 * c[k] / sl for k in ("M_CGRCL", "M_CGRIL", "M_IGR3")})
    return w


def shock(case: int, data: dict, base: dict) -> set[str]:
    """data を書き換えてショックを与える。外生化する内生変数の集合を返す."""
    exo = set()
    for k, t in enumerate(YEARS):
        if case in (1, 2) and (case == 2 or k == 0):
            dg = 0.01 * base["M_GDP"][t]
            for v, w in gov_split(base, t).items():
                data[v][t] = base[v][t] + w * dg
        elif case == 3:
            data["Z_TYCVX"][t] = 0.01 * base["M_GDPV"][t]
        elif case == 4:
            data["Z_TYPVX"][t] = 0.01 * base["M_GDPV"][t]
        elif case == 5:
            data["Z_RTCIV"][t] = base["Z_RTCIV"][t] + 0.01
        elif case == 6:
            data["M_TFP"][t] = base["M_TFP"][t] + 0.01 * (k + 1)
        elif case == 7:
            data["M_POILD"][t] = base["M_POILD"][t] * 1.2
        elif case == 8:
            data["M_RCO"][t] = base["M_RCO"][t] + 1.0
            exo.add("M_RCO")
    return exo


def extra(data: dict, t: int) -> dict[str, float]:
    return {"TAXAGDP": (data["M_TAXV"][t] + data["Z_TXOH"][t]) / data["M_GDPV"][t] * 100}


def run(case: int, model=None, base_data=None, af=None) -> pd.DataFrame:
    m = model or build()
    if base_data is None:
        base_data, af = load()
    data = copy.deepcopy(base_data)
    exo = shock(case, data, base_data)
    s = Solver(m, data, af)
    for t in YEARS:
        s.solve_year(t, pinned=exo, calibrate_pinned=False)
    rows = []
    for k, t in enumerate(YEARS):
        bx, sx = extra(base_data, t), extra(data, t)
        for v in PCT:
            rows.append((case, v, k + 1, (data[v][t] / base_data[v][t] - 1) * 100))
        for v in PT:
            a = sx[v] if v in sx else data[v][t]
            b = bx[v] if v in bx else base_data[v][t]
            rows.append((case, v, k + 1, a - b))
    return pd.DataFrame(rows, columns=["case", "var", "period", "model"])


def main(mode: str = "calibrated") -> pd.DataFrame:
    m = build(mode)
    base_data, af = load(mode)
    # 標準ケースがそのまま再現されることを確認する
    chk = run(0, m, base_data, af)
    worst = chk["model"].abs().max()
    print(f"ショックなしの乖離の最大値: {worst:.2e}")
    res = pd.concat([run(c, m, base_data, af) for c in P.CASES], ignore_index=True)
    pub = pd.read_csv(P.OUT) if P.OUT.exists() else P.main()
    res = res.merge(pub.rename(columns={"value": "published"}), on=["case", "var", "period"], how="left")
    out = out_path(mode)
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    print(f"→ {out}")
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    r = main(ap.parse_args().mode)
    pd.set_option("display.width", 200)
    for c in P.CASES:
        x = r[(r.case == c) & r["var"].isin(["M_GDP", "M_CPIG", "M_RCO", "M_UR", "M_PBGAGDPV", "Z_DEBTAGDP"])]
        print(f"\n=== ケース{c}: {P.CASES[c]}")
        print(x.pivot_table(index="var", columns="period", values=["model", "published"]).round(2).to_string())
