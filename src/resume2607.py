"""projection2607 のフィットが途中で止まったとき、DEBUG_DIR の年次チェックポイントから再開する.

projection.run の設定手順をそのまま再現し（中立値・LG_OFFSET・GAP はチェックポイントの値から再計算）、
残りの年だけ run と同じ follow ロジックで解く。終わったら proj_state_2607_{case}.pkl に保存する。
"""
from __future__ import annotations

import os

os.environ.setdefault("CAO_LAST_VINTAGE", "2040")

import copy
import pickle
from pathlib import Path

import pandas as pd

import baseline as BL
import projection as P
import projection2607 as Q
from solver import Solver
from spec import build, compile_eq

ROOT = Path(__file__).resolve().parents[1]
DEBUG = ROOT / "output" / "debug2607"

_orig_solve = P.solve


def _rhs(name: str, data: dict, t: int) -> float:
    if name == "ZP_DSTDEC":   # @recode(expr < 0, expr, 0) = min(expr, 0)
        expr = (data["ZP_ZAITAIH$"][t] + data["ZP_ZAITAIT$"][t]) * data["ZP_LGEXI"][t] + data["ZP_LGBZ"][t]
        return expr if expr < 0 else 0.0
    if name == "Z_LGBR":
        return data["Z_LGB$"][t] * (data["ZP_LGBR1"][t] + data["ZP_LGBR2"][t])
    raise KeyError(name)


def _pin_solve(s: Solver, t: int, name: str) -> None:
    data = s.data
    for _ in range(12):
        data[name][t] = _rhs(name, data, t)
        s.solve_year(t, calibrate_pinned=False, pinned=frozenset({name}), omegas=(0.2,), max_iter=3000)
        if abs(data[name][t] - _rhs(name, data, t)) < 1e-6:
            return
    raise RuntimeError(f"{name}: ピン留め反復が収束しない（t={t}）")


def robust_solve(s: Solver, t: int) -> None:
    """projection.solve の頑丈版。ZP_DSTDEC の recode の折れ目で Newton が失敗したら、式をピン留めして解き直す."""
    try:
        _orig_solve(s, t)
    except Exception:
        for name in ("ZP_DSTDEC", "Z_LGBR"):
            try:
                _pin_solve(s, t, name)
                return
            except Exception:
                continue
        raise


P.solve = robust_solve


def resume(case: str) -> pd.DataFrame:
    Q.configure()
    with (DEBUG / f"proj_state_{case}.pkl").open("rb") as f:
        ck = pickle.load(f)
    data, af, t_done = ck["data"], ck["af"], ck["t"]
    print(f"{case}: チェックポイント {t_done} 年度まで完了。{t_done + 1} 年度から再開", flush=True)

    m = build("calibrated", "port")
    m.eqs.append(compile_eq("Z_EXPX35E", "Z_EXPX35E=Z_EXPX35+Z_ADJEXPX35E"))
    m.meta["Z_EXPX35E"] = {"label": "（追加: その他一般歳出の SNA 用）", "block": "fiscal", "estimated": False}
    af.setdefault("Z_EXPX35E", {})

    # 中立値は、run と同じ前処理（国債ブロック誤差項の固定など）をした標準ケースから取る
    with BL.out_path("calibrated", "port", "proj2607").open("rb") as f:
        b = pickle.load(f)
    bdata, baf = copy.deepcopy(b["data"]), copy.deepcopy(b["af"])
    import bond_port
    bond_vars = bond_port.endogenous()
    for eq in m.eqs:
        if (eq.name not in bond_vars and not m.meta.get(eq.name, {}).get("estimated", False)
                and set(eq.vars) & bond_vars and 2024 in baf[eq.name]):
            for t in P.YEARS:
                baf[eq.name][t] = baf[eq.name][2024]
    neutral = {v: dict(baf[v]) for _, v in P.TARGETS if v not in P.DATA_CTRL}

    P.LG_OFFSET["v"] = data["Z_LGEXTC"][2024] / 1000 - P.FISCAL_PUB[case]["地方の歳出"][0]
    P.LG_OFFSET["oh"] = data["Z_REVOH"][2026] / 1000 - P.FISCAL_PUB[case]["国のその他収入"][2026 - 2024]
    P.LG_OFFSET["rev"] = ((data["Z_LGINTOTAL"][2024] - data["Z_LGB"][2024] - data["Z_RLGFND"][2024] - data["Z_CF"][2024])
                          / 1000 - P.FISCAL_PUB[case]["地方の税収等"][0])
    P.LG_OFFSET["dst"] = data["Z_DST"][2024] / 1000 - P.FISCAL_PUB[case]["地方交付税等"][0]
    P.LG_OFFSET["p"] = ((data["Z_LGEXTC"][2024] - data["Z_LGEXTM"][2024] - data["Z_CLB"][2024]) / 1000
                        - P.FISCAL_PUB[case]["地方の一般歳出"][0])
    P.GAP.clear()
    vals26 = P.item_values(data, 2026)
    for name, _ in P.FOLLOW_TARGETS:
        if name in P.FISCAL_PUB[case]:
            P.GAP[name] = vals26[name] - P.target(case, name, 2026)

    s = Solver(m, data, af)
    for t in range(t_done + 1, 2041):
        k = P.DECAY ** (t - 2026)
        for _, v in P.TARGETS:
            if v in P.KEEP_AF:
                af[v][t] = af[v][2026]
            elif v in P.DATA_CTRL:
                data[v][t] = data[v][2026] / data["M_GDPV"][2026] * data["M_GDPV"][t - 1]
            else:
                af[v][t] = neutral[v][t] + k * (af[v][2026] - neutral[v][2026])
        if P.FUND_SNA_ONLY:
            data["Z_ADJEXPX35E"][t] = P.GAP.get("国のPB対象経費", 0.0) * 1000 * P.FUND_DECAY ** (t - 2026)
        for _, v in P.FOLLOW_TARGETS:
            if v in P.DATA_CTRL:
                data[v][t] = data[v][t - 1]
            else:
                af[v][t] = af[v][t - 1]
        P.fit_year(s, t, case, targets=P.FOLLOW_TARGETS)
        with (DEBUG / f"proj_state_{case}.pkl").open("wb") as fdbg:
            pickle.dump({"data": data, "af": af, "t": t}, fdbg)
        print(f"{case} {t}: 実質 {P.item_values(data, t)['実質GDP成長率']:.2f}% 名目GDP {data['M_GDPV'][t] / 1000:.1f}兆円 "
              f"PB {data['M_PBGAGDPV'][t]:.2f} 残高比 {data['Z_DEBTAGDP'][t]:.1f}", flush=True)

    with Q.state_path(case).open("wb") as f:
        pickle.dump({"data": data, "af": af}, f)
    rows = []
    for t in [2024] + P.YEARS:
        vals = P.item_values(data, t)
        for k_ in P.ITEMS:
            mv = P.PUB[case][k_][0] if t == 2024 else vals[k_]
            rows.append((case, k_, t, mv, P.PUB[case][k_][t - 2024]))
    return pd.DataFrame(rows, columns=["case", "item", "year", "model", "published"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=Q.CASES)
    a = ap.parse_args()
    res = resume(a.case)
    out = ROOT / "output" / "chuuchouki2607_projection.csv"
    if out.exists():
        old = pd.read_csv(out)
        res = pd.concat([old[old["case"] != a.case], res], ignore_index=True)
    res.to_csv(out, index=False)
    print(f"→ {out}")
