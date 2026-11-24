# -*- coding: utf-8 -*-
"""氷河期世代の大量採用シナリオ（2026年7月試算の再現経路・08と同じ土台版）.

土台は projection2607.py の再現経路（proj_state_2607_{case}.pkl）と、
noextra2607.py の追加財政支出なし経路（proj_state_2607_{case}_noextra.pkl）。

前提（原記事05を踏襲し、開始を2028年度にずらす）:
- 2028年度10万人、2029年度20万人、2030年度30万人、2031年度以降40万人を地方公務員として採用
- 内訳は失業者43%、無業者（非労働力）57%
- 人件費は1人600万円（2028年度）、以降は1人当たり賃金の伸びに連動。地方の人件費（Z_ADJLGEXPG）に計上
- 失業者分: 完全失業率と構造的失業率（M_EQUR）をその分だけ下げる
- 無業者分: 45〜54歳セル（4549・5054、男女）の労働力率を、その分だけ労働力人口が増えるよう引き上げる
出力: output/hire2607_{case}{_noextra}.csv（ベースラインとの乖離）
"""
from __future__ import annotations

import os

os.environ.setdefault("CAO_LAST_VINTAGE", "2040")

import copy
import pickle
from pathlib import Path

import pandas as pd

import simulate as SIM
from solver import Solver

ROOT = Path(__file__).resolve().parents[1]
START = 2028
YEARS = list(range(START, 2041))
HIRES = {t: min((t - START + 1) * 10.0, 40.0) for t in YEARS}   # 万人（累計）
SHARE_UNEMP = 0.43
CELLS = [("4549", "M"), ("4549", "F"), ("5054", "M"), ("5054", "F")]


def _pin_iterate(s: Solver, t: int, var: str, rhs) -> None:
    """折れ目のある式の変数を固定して解き、右辺と整合するまで繰り返す."""
    d = s.data
    g = d[var][t]
    for _ in range(6):
        d[var][t] = g
        s.solve_year(t, pinned={var}, calibrate_pinned=False, omegas=(0.2,), max_iter=3000)
        g_new = rhs(d, t)
        if abs(g_new - g) < 1e-9:
            break
        g = g_new
    d[var][t] = g


_RHS = {
    "ZP_DSTDEC": lambda d, t: (lambda x: x if x < 0 else 0.0)(
        (d["ZP_ZAITAIH$"][t] + d["ZP_ZAITAIT$"][t]) * d["ZP_LGEXI"][t] + d["ZP_LGBZ"][t]),
    "Z_LGBR": lambda d, t: d["Z_LGB$"][t] * (d["ZP_LGBR1"][t] + d["ZP_LGBR2"][t]),
}


def solve(s: Solver, t: int) -> None:
    try:
        s.solve_year(t, calibrate_pinned=False)
    except (RuntimeError, ValueError, OverflowError):
        try:
            s.solve_year(t, calibrate_pinned=False, omegas=(0.2,), max_iter=3000)
        except (RuntimeError, ValueError, OverflowError) as e:
            var = str(e).split(":")[0].strip()
            if var not in _RHS:
                raise
            _pin_iterate(s, t, var, _RHS[var])


def fit_unemp_rate(s: Solver, t: int, target: float) -> None:
    """完全失業率が target（%）になるよう M_UR の誤差項を割線法で決める."""
    def val(x):
        old = s.af["M_UR"][t]
        s.af["M_UR"][t] = x
        try:
            solve(s, t)
        except Exception:
            s.af["M_UR"][t] = old
            return None
        return s.data["M_UR"][t] - target
    x0 = s.af["M_UR"][t]
    y0 = val(x0)
    if y0 is None or abs(y0) < 0.005:
        return
    x1, y1 = x0 + (0.01 if y0 < 0 else -0.01), None
    for _ in range(8):
        y1 = val(x1)
        if y1 is not None:
            break
        x1 = x0 + (x1 - x0) / 2
    if y1 is None:
        return
    for _ in range(10):
        if abs(y1) < 0.005 or y1 == y0:
            break
        x2 = x1 - y1 * (x1 - x0) / (y1 - y0)
        y2 = val(x2)
        if y2 is None:
            break
        x0, y0, x1, y1 = x1, y1, x2, y2


def run(case: str, nashi: bool = False) -> pd.DataFrame:
    tag = f"{case}_noextra" if nashi else case
    st = pickle.loads((ROOT / "output" / "parts" / f"proj_state_2607_{tag}.pkl").read_bytes())
    base = st["data"]
    data, af = copy.deepcopy(base), copy.deepcopy(st["af"])
    af.setdefault("Z_EXPX35E", {})
    m = SIM.build_model("calibrated", "port")
    s = Solver(m, data, af)
    w0 = base["M_W"][START]
    rows = []
    for t in YEARS:
        h = HIRES[t]                                    # 万人
        cost = h * 60.0 * base["M_W"][t] / w0           # 10億円（1人600万円×賃金伸び）
        data["Z_ADJLGEXPG"][t] = base["Z_ADJLGEXPG"][t] + cost
        # 無業者分: 45〜54歳セルの労働力率を引き上げる（人口比で配分）
        dlf = (1 - SHARE_UNEMP) * h
        pops = {c: base[f"P_POP{c[0]}{c[1]}"][t] for c in CELLS}
        tot = sum(pops.values())
        for c in CELLS:
            v = f"P_RLF{c[0]}{c[1]}"
            data[v][t] = base[v][t] + (dlf * pops[c] / tot) / pops[c]
        # 失業者分: 構造的失業率を下げ、完全失業率もその分だけ下げる
        dur = SHARE_UNEMP * h / base["M_LF"][t] * 100   # ポイント
        data["M_EQUR"][t] = base["M_EQUR"][t] - dur
        solve(s, t)
        fit_unemp_rate(s, t, base["M_UR"][t] - dur)
        # Z_LGEXPG は「前年の水準×伸び率＋調整項」の式なので、調整項に人件費の全額を毎年入れると
        # 水準が累積してしまう。人件費の水準そのものが cost になるよう、調整項を補正する
        for _ in range(4):
            dev = data["Z_LGEXPG"][t] - base["Z_LGEXPG"][t]
            if abs(dev - cost) < 0.5:   # 0.5（10億円）= 5億円
                break
            data["Z_ADJLGEXPG"][t] += cost - dev
            solve(s, t)
            fit_unemp_rate(s, t, base["M_UR"][t] - dur)
        g = lambda v: (data[v][t] / base[v][t] - 1) * 100
        rows.append({
            "year": t, "hires_wan": h, "cost_choen": cost / 1000,
            "rgdp_pct": g("M_GDP"), "ngdp_pct": g("M_GDPV"), "pot_pct": g("M_GDPP"),
            "emp_diff_wan": data["M_LE"][t] - base["M_LE"][t],
            "lf_diff_wan": data["M_LF"][t] - base["M_LF"][t],
            "ur_diff_pt": data["M_UR"][t] - base["M_UR"][t],
            "pb_diff_pt": data["M_PBGAGDPV"][t] - base["M_PBGAGDPV"][t],
            "debt_diff_pt": data["Z_DEBTAGDP"][t] - base["Z_DEBTAGDP"][t],
            "cpi_diff_pt": (data["M_CPIG"][t] / data["M_CPIG"][t - 1] - base["M_CPIG"][t] / base["M_CPIG"][t - 1]) * 100,
            "rgb_diff_pt": data["M_RGB"][t] - base["M_RGB"][t],
            "wage_pct": g("M_W"),
            "cons_pct": g("M_CP"),
        })
        print(f"{tag} {t}: 採用{h:.0f}万人 人件費{cost/1000:.2f}兆円 実質GDP{rows[-1]['rgdp_pct']:+.2f}% "
              f"就業者{rows[-1]['emp_diff_wan']:+.1f}万人 PB{rows[-1]['pb_diff_pt']:+.2f}pt 残高比{rows[-1]['debt_diff_pt']:+.2f}pt", flush=True)
    df = pd.DataFrame(rows)
    out = ROOT / "output" / f"hire2607_{tag}.csv"
    df.to_csv(out, index=False)
    print(f"→ {out}")
    return df


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--noextra", action="store_true")
    a = ap.parse_args()
    run(a.case, a.noextra)
