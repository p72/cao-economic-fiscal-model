"""シナリオ: 消費税5%への減税（src/ctax5.py）と同じ額を、2027年度から毎年、国民に一律給付したら.

給付額は減税の事前の減収額（減税なしの課税ベースで、税率だけ5%にしたときの消費税収の減少）。
- 予算: 国の一般会計のその他一般歳出（Z_ADJEXPX35）に計上する（国債の発行が増える）。Z_EXPX35 は前年度の値を
  伸ばす式なので、前年度の給付が伸びて残る分を差し引き、その年の給付だけが上乗せされるようにする。
- SNA: 国の現物社会移転以外の社会給付（M_BSSVCER）として家計に渡す。予算の歳出増が政府消費などに配分されないよう、
  その他一般歳出の SNA 用（Z_ADJEXPX35E）からは同じ額を差し引く。
実質の政府消費・公的固定資本形成は給付なしと同じに保つ。減税なしの経路は ctax5.py と同じ（3ケースの再現経路）。
出力: output/gift_scenario.csv（列: case, scen（base=給付なし、gift=給付）, year, 各変数。gift は給付額（兆円）、
pop は人口（万人）、ydv は家計可処分所得（兆円））
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

import projection as P
from chuuchouki import hold_real_g
from ctax5 import CASES, RATE, YEARS, row, state
from solver import Solver
from spec import build, compile_eq

ROOT = Path(__file__).resolve().parents[1]


def size(base: dict, t: int) -> float:
    """減税の事前の減収額（10億円）."""
    r1, r2 = base["Z_RTCIV"][t], base["Z_RTCIV2"][t]
    k = RATE / (1 + RATE)
    return base["Z_TCIVB"][t] * (1 - k / (r1 / (1 + r1))) + base["Z_TCIVR"][t] * (1 - k / (r2 / (1 + r2)))


def run(case: str) -> list[dict]:
    m = build("calibrated", "port")
    m.eqs.append(compile_eq("Z_EXPX35E", "Z_EXPX35E=Z_EXPX35+Z_ADJEXPX35E"))   # projection.py と同じ
    m.meta["Z_EXPX35E"] = {"label": "（追加: その他一般歳出の SNA 用）", "block": "fiscal", "estimated": False}
    st = state(case)
    base, af = st["data"], copy.deepcopy(st["af"])
    data = copy.deepcopy(base)
    gift = {t: size(base, t) for t in YEARS}
    for t in YEARS:
        data["Z_ADJEXPX35E"][t] = base["Z_ADJEXPX35E"][t] - gift[t]
        data["M_BSSVCER"][t] = base["M_BSSVCER"][t] - gift[t]
    s = Solver(m, data, af)
    for t in YEARS:
        for _ in range(3):     # 伸び率 Z_GREXPXA は内生なので解き直して合わせる
            prev = gift.get(t - 1, 0.0) * data["Z_GREXPXA"][t]
            data["Z_ADJEXPX35"][t] = base["Z_ADJEXPX35"][t] + gift[t] - prev
            P.solve(s, t)
        hold_real_g(s, "gift", t, base, set())
    rows = []
    for t in [2026] + YEARS:
        for scen, d in (("base", base), ("gift", data)):
            r = row(case, scen, d, t)
            r.update(ydv=d["M_YDV"][t] / 1000, gift=gift.get(t, 0.0) / 1000 if scen == "gift" else 0.0, pop=d["P_POP"][t])
            rows.append(r)
    for t in (2027, 2030, 2035):
        print(f"{case} {t}: 給付 {gift[t] / 1000:.1f}兆円  実質GDP {(data['M_GDP'][t] / base['M_GDP'][t] - 1) * 100:+.2f}%  "
              f"PB {base['M_PBGAGDPV'][t]:.2f}→{data['M_PBGAGDPV'][t]:.2f}  "
              f"残高比 {base['Z_DEBTAGDP'][t]:.1f}→{data['Z_DEBTAGDP'][t]:.1f}", flush=True)
    return rows


if __name__ == "__main__":
    df = pd.DataFrame([r for c in CASES for r in run(c)])
    out = ROOT / "output" / "gift_scenario.csv"
    df.to_csv(out, index=False)
    print(f"→ {out}")
