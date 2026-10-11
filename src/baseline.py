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
import re
from pathlib import Path

import data2024
from solver import Solver
from spec import Model, build

ROOT = Path(__file__).resolve().parents[1]
def suffix(mode: str, fiscal: str) -> str:
    """出力ファイル名の接尾辞（calibrated・simple は空）."""
    return ("" if mode == "calibrated" else f"_{mode}") + ("" if fiscal == "simple" else f"_{fiscal}")


def out_path(mode: str, fiscal: str = "simple", variant: str = "standard") -> Path:
    tail = "" if variant == "standard" else f"_{variant}"
    return ROOT / "data" / "processed" / f"baseline_{mode}{'' if fiscal == 'simple' else '_' + fiscal}{tail}.pkl"


# 標準ケースの変種: 実質成長率、物価上昇率（デフレーター）、長期金利・短期金利（%）。
# standard は乗数表の比較に使う既定の経路。kako・seicho は中長期試算（2026年1月）の過去投影ケース・成長移行ケースの
# 2027～2035年度の平均的な姿（実質成長率、GDPデフレーター変化率、名目長期金利）に合わせた一定成長の経路。
# 短期金利は資料にないので、2024年度の長短金利差（0.87%pt）を保つとした（推定）。
VARIANTS = {
    "standard": {"g_real": 0.005, "g_price": 0.02, "rates": None},
    "kako": {"g_real": 0.005, "g_price": 0.007, "rates": {"M_RGB": 2.0, "M_RCO": 2.0 - 0.87}},
    "seicho": {"g_real": 0.014, "g_price": 0.016, "rates": {"M_RGB": 3.0, "M_RCO": 3.0 - 0.87}},
    # 主要計数表の再現（projection.py）の出発点: 実質ゼロ成長で、物価だけが各ケースのGDPデフレーター変化率で伸びる経路。
    # 実質の成長は、人口・労働参加率・TFP などの前提を与えてモデルの式から出す
    "proj_kako": {"g_real": 0.0, "g_price": 0.007, "rates": {"M_RGB": 2.0, "M_RCO": 2.0 - 0.87}},
    "proj_seicho": {"g_real": 0.0, "g_price": 0.016, "rates": {"M_RGB": 3.0, "M_RCO": 3.0 - 0.87}},
}


def set_variant(variant: str) -> dict:
    """成長率の定数を変種に合わせて置き換える（growth() が参照する）."""
    global G_REAL, G_PRICE, G_NOM
    v = VARIANTS[variant]
    G_REAL, G_PRICE = v["g_real"], v["g_price"]
    G_NOM = (1 + G_REAL) * (1 + G_PRICE) - 1
    return v

BASE_YEAR = 2024
FIRST, LAST = 2000, 2045
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
    "M_PXGS", "M_PMGS", "M_PNMR", "MWE_WPI", "MUS_WPI", "M_POILD", "S_PPICPIC$", "S_OSACPIG$",
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


# 年金ブロックの改定率・調整率・人数・保険料率など（一定）
PENSION_CONST = re.compile(r"^S_P(PIRC|BPRC|ENRC|BPSSR|ENSSR|NPRCIP|PICPIGZ|..TRBPN|..INSPN|..BNFTN|"
                           r"NPIPRMAZ|..DC..\$|..IPRM\$|PI...\$|PIFUNDBD\$|PIRT...\$Z|PIPROR\$2|NPIPPY\$Z)")

# 財政ブロックの「1＋伸び率」の変数、比率、実効金利（%）、年金の CPI 上昇率（一定）。名目値と同じく伸ばすと、
# 式との差が誤差項に入り年々大きくなって、水準を前向きに計算したときに歳出が雪だるま式に増える
# 地方の計画・決算年度のダミー（Z_KEIKAKU、Z_KEIKAKUL、Z_KESSANL など）と交付税率（Z_RKF…）も一定
FISCAL_RATE = re.compile(r"^(Z_GREXP|Z_REXP|Z_EFRATE|S_PPICPIC$|Z_KEIKAKU|Z_KESSAN|Z_YOSAN|Z_RKF)")
# 普通国債ブロックの構成比・金利・価格・ダミー（一定）
BOND_CONST = re.compile(r"^B_(RBHQ|RP|LSSPRD|IR|IC|YC|IPR|WB|RB|RDBNEW|DDBNEW|DUM|RISKPRM|RAGBZ)")
# 医療・介護の加入者数・改定率（一定）
MEDCARE_CONST = re.compile(r"^S_(M..INSP|MY.INSP|CCI.INSN$|MMIRCCF$|CCIRCCF$)")


def growth(v: str) -> float:
    if v == "M_TIME":
        return 0.0
    if (v.startswith("S_P") and PENSION_CONST.match(v) or MEDCARE_CONST.match(v) or BOND_CONST.match(v)
            or FISCAL_RATE.match(v)):
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


def pension_profit_rate(data: dict, t: int) -> float:
    """年金積立金の運用収入の式で使う資本収益率（基準年度の値を基準 S_PPIPROR$2 にする）."""
    x = {v: data[v][t] for v in ("M_YWV", "M_YCVSELF", "M_CCAV", "M_GDPV", "M_TAXV", "M_KFP", "M_PIFP", "M_KFPCFC$")}
    return ((1 - x["M_YWV"] / (x["M_YWV"] + x["M_YCVSELF"] + x["M_CCAV"])) * (x["M_GDPV"] - x["M_TAXV"])
            / (x["M_KFP"] * x["M_PIFP"]) - x["M_KFPCFC$"])


def bond_overrides(m: Model, data: dict) -> None:
    """普通国債の既発債のスケジュールと発行年度ダミー（年度ごとに値が変わる外生変数）を入れる.

    既発債の残高は、2025年度末の普通国債残高（標準ケースの Z_GBNML2）に合うように比例で調整する。
    """
    import bond_port
    import jgb_data
    total = sum(jgb_data.schedule(2025, 2025)[q]["stock"][2025] for q in bond_port.TENORS)
    scale = data["Z_GBNML2"][2025] / total
    for v, col in bond_port.exog_series(scale, FIRST, LAST).items():
        if v in data:
            data[v] = col
    # 地方債の既発分: 2025年度末残高を平均償還年数で償還し、利払費は基準年度の平均利率（SNA の利子 / 残高）
    rate0 = (data["M_YIGVLRLWF"][BASE_YEAR] - data["M_YIGVLRLR"][BASE_YEAR]) / data["B_ZLGB"][BASE_YEAR - 1]
    for v, col in bond_port.lgb_exog_series(data["B_ZLGB"][2025], rate0, FIRST, LAST).items():
        if v in data:
            data[v] = col


def bond_forward(m: Model, data: dict) -> None:
    """標準ケースの国債・地方債ブロックを、ほかの変数を固定して2025年度から前向きに解く.

    合成の一定成長の経路のままだと、発行年度別の残高が現実の発行・償還と合わず、金利が動いたときの
    利払費の増え方が正しく出ないため。2036年度以降は新規発行の積み上げがないので解かない。
    """
    import bond_port
    bv = bond_port.endogenous() & set(m.endog)
    s = Solver(m, data)
    for t in range(2025, max(bond_port.VINTAGES) + 1):
        s.solve_year(t, pinned=set(m.endog) - bv, calibrate_pinned=False)


def make(model: Model | None = None, verbose: bool = True, mode: str = "calibrated",
         fiscal: str = "simple", variant: str = "standard") -> tuple[Model, dict, dict]:
    m = model or build(mode, fiscal)
    var = set_variant(variant)
    d0 = data2024.build(m.mode)
    if var["rates"]:
        d0.update(var["rates"])
    if m.fiscal == "port":
        import data_fiscal
        df = data_fiscal.build()
        df.update(data_fiscal.calibrate_splits(df, d0))
        d0.update(df)
        # 調整項・残差・制度変更分は0（標準ケースのアドファクターが同じ役割を果たす）
        for v in m.exog():
            if v not in d0 and re.search(r"(ADJ|ER$|XX$|ADJCH$|^Z_D[A-Z]|^RES)", v):
                d0[v] = 0.0
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
    for _ in range(2 if m.fiscal == "port" else 1):
        guess = solve_base_year(m, d0, known, unknown, guess)
        if m.fiscal == "port":
            # 臨時財政対策債（既往債の元利償還金分等）の計画値 ZP_LGBR2 は、既発債分 ZP_LGBR2N と交付税特会借入金の
            # 利払費分 ZP_LGBR2Y（＝Z_GTLR）などの和。2024年度の計画額（4,544億円）を既発債分に全部入れると利払費分が
            # 二重に入り、差が誤差項に入る。ZP_LGBR2 は0を下限とする式（@recode）なので、誤差項が残ると増税ケースなどで
            # 臨時財政対策債がマイナス（＝買入消却）になり、地方債残高が減りすぎる。差を既発債分から引いて誤差項を0にする
            x = sum(guess.get(v, d0.get(v, 0.0)) for v in ("ZP_LGBR2N", "ZP_LGBR2X", "ZP_LGBR2Y", "ZP_LGBR2Z"))
            d0["ZP_LGBR2NX"] -= x - d0["ZP_LGBR2"]
    vals = {**d0, **guess}
    data = {v: path(v, vals[v]) for v in allv if v != "M_TIME"}
    data["M_TIME"] = path("M_TIME", 0.0)
    if m.fiscal == "port":
        bond_overrides(m, data)
        bond_forward(m, data)
    s = Solver(m, data)
    for t in range(BASE_YEAR, LAST + 1):
        for eq in m.eqs:
            s.calibrate(eq, t)
    return m, data, s.af


def solve_base_year(m: Model, d0: dict, known: set, unknown: list, guess: dict) -> dict:
    """値がない内生変数の2024年度の値を、その年の式を解いて埋める（反復）."""
    allv = set(m.endog) | set(m.exog())
    for _ in range(6):
        vals = {**d0, **guess}
        data = {v: path(v, vals[v]) for v in allv if v != "M_TIME"}
        data["M_TIME"] = path("M_TIME", 0.0)
        if m.fiscal == "port":
            bond_overrides(m, data)
        s = Solver(m, data)
        s.solve_year(BASE_YEAR, pinned=known, calibrate_pinned=False)
        if "S_PPIPROR$2" in d0:
            d0["S_PPIPROR$2"] = pension_profit_rate(data, BASE_YEAR)
        new = {v: data[v][BASE_YEAR] for v in unknown}
        diff = max(abs(new[v] - guess[v]) / max(abs(guess[v]), 1.0) for v in unknown)
        guess = new
        if diff < 1e-8:
            break
    return guess


def main(mode: str = "calibrated", fiscal: str = "simple", variant: str = "standard") -> None:
    m, data, af = make(mode=mode, fiscal=fiscal, variant=variant)
    out = out_path(mode, fiscal, variant)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        pickle.dump({"data": data, "af": af}, f)
    print(f"ベースライン（{mode}、{fiscal}、{variant}）→ {out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    ap.add_argument("--fiscal", default="simple", choices=["simple", "port"])
    ap.add_argument("--variant", default="standard", choices=list(VARIANTS))
    a = ap.parse_args()
    main(a.mode, a.fiscal, a.variant)
