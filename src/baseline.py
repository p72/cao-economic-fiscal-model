"""ベースライン（標準ケース）を作る.

公表されている乗数表は「外挿期間において GDP ギャップがゼロのまま推移すると仮定した標準ケース」
との乖離なので、ここでも一定の伸び率で伸びる定常的な経路を標準ケースにする。

1. 2024年度の値（data2024.py）を出発点にする。値がない内生変数は、その年の式を解いて埋める。
2. 全変数を種類ごとの一定の伸び率で過去（ラグ用）と将来に延ばす。
   実質 G_REAL、物価 G_PRICE、名目 (1+G_REAL)(1+G_PRICE)-1、金利・比率・人数は一定。
3. その経路で各式がちょうど成り立つようにアドファクターを合わせる（全変数を固定して逆算）。
"""
from __future__ import annotations

import pickle
from pathlib import Path

import data2024
from solver import Solver
from spec import Model, build

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "baseline.pkl"

BASE_YEAR = 2024
FIRST, LAST = 2005, 2045
G_REAL, G_PRICE = 0.005, 0.02
G_NOM = (1 + G_REAL) * (1 + G_PRICE) - 1

REAL = {
    "M_GDP", "M_GDPP", "M_GDI", "M_GNI", "M_CP", "M_IFP", "M_IHP", "M_IHPBASE", "M_IN", "M_CG", "M_IG", "M_G",
    "M_XGS", "M_MGS", "M_MGSEQ", "M_YD", "M_TRI", "M_TRIREC", "M_TRIPAY", "M_TRDG", "M_BG", "M_KFP",
    "M_KFPSTAR", "M_EQKFP", "M_KHP", "M_KFPCFC", "M_KHPCFC", "M_CGRCC", "M_CGRIC", "M_CGRCL", "M_CGRIL", "M_CGRIF",
    "M_IGR1", "M_IGR2", "M_IGR3", "M_IGR5", "M_IHPADJ",
}
PRICE = {
    "M_PGDP", "M_PGDPA", "M_PGDPA2", "M_CPIG", "M_CPIGA", "M_CGPI", "M_CGPIA", "M_PCP", "M_PCPA", "M_PIFP",
    "M_PIHP", "M_PIHPA", "M_PIN", "M_PINA", "M_PCG", "M_PCGA", "M_PIG", "M_PIGA", "M_PDDM", "M_PGDPD",
    "M_PXGS", "M_PMGS", "M_PNMR", "MWE_WPI", "MUS_WPI", "M_POILD",
}
# 一定（金利、比率、率、人数、指数の対数など）
CONST_PREFIX = ("P_", "M_WT", "M_EQL", "M_EQU", "M_EQC", "Z_RT", "Z_MAT", "M_D0", "M_D1", "M_D2", "M_D8",
                "M_D9", "M_R", "M_GAP")
CONST = {
    "M_LF", "M_LE", "M_LW", "M_LEH", "M_LEHF", "M_LEHM", "M_LFER", "M_LEER", "M_LWER", "M_UR", "M_EQLE",
    "M_FXS", "MUS_RGB", "M_TAYLOR", "M_HSR", "M_CPIGR", "M_CGPIR", "M_TRDT", "M_UCC", "M_TFP", "M_EQLBSH",
    "M_PSTAR", "M_PSTARBOJ", "MWE_GGDP", "Z_DEBTAGDP", "M_MPVDP", "M_DPOPC", "M_PLNH", "M_SPREV",
    "M_GAPNP", "M_INV$",
}


def growth(v: str) -> float:
    if v == "M_TIME":
        return 0.0
    if v in REAL:
        return G_REAL
    if v in PRICE:
        return G_PRICE
    if v in CONST or v.endswith("$") or "AGDP" in v or v.startswith(CONST_PREFIX):
        return 0.0
    return G_NOM


def path(v: str, x0: float) -> dict[int, float]:
    if v == "M_TIME":
        return {t: float(t - 1980) for t in range(FIRST, LAST + 1)}
    g = growth(v)
    return {t: x0 * (1 + g) ** (t - BASE_YEAR) for t in range(FIRST, LAST + 1)}


def dummies(model: Model) -> dict[str, float]:
    """M_DyyC（yy年以降1）のダミー変数."""
    out = {}
    for v in model.exog():
        if v.startswith("M_D") and v.endswith("C") and v[3:5].isdigit():
            out[v] = 1.0
    return out


def make(model: Model | None = None, verbose: bool = True) -> tuple[Model, dict, dict]:
    m = model or build()
    d0 = data2024.build()
    d0.update(dummies(m))
    allv = set(m.endog) | set(m.exog())
    missing_ex = sorted(v for v in m.exog() if v not in d0 and v != "M_TIME")
    if missing_ex:
        raise ValueError(f"2024年度の値がない外生変数: {missing_ex}")
    known = {v for v in allv if v in d0}
    unknown = sorted(set(m.endog) - known)
    if verbose:
        print(f"2024年度の値: 既知 {len(known)}、式で埋める {len(unknown)}")
    guess = {v: 1.0 for v in unknown}
    data = {}
    for _ in range(6):
        vals = {**d0, **guess}
        data = {v: path(v, vals[v]) for v in allv if v != "M_TIME"}
        data["M_TIME"] = path("M_TIME", 0.0)
        s = Solver(m, data)
        s.solve_year(BASE_YEAR, pinned=known, calibrate_pinned=False)
        new = {v: data[v][BASE_YEAR] for v in unknown}
        diff = max(abs(new[v] - guess[v]) / max(abs(guess[v]), 1.0) for v in unknown)
        guess = new
        if diff < 1e-8:
            break
    vals = {**d0, **guess}
    data = {v: path(v, vals[v]) for v in allv if v != "M_TIME"}
    data["M_TIME"] = path("M_TIME", 0.0)
    s = Solver(m, data)
    for t in range(BASE_YEAR, LAST + 1):
        for eq in m.eqs:
            s.calibrate(eq, t)
    return m, data, s.af


def main() -> None:
    m, data, af = make()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("wb") as f:
        pickle.dump({"data": data, "af": af}, f)
    print(f"ベースライン → {OUT}")


if __name__ == "__main__":
    main()
