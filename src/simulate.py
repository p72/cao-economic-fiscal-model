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


def out_path(mode: str, fiscal: str = "simple") -> Path:
    return ROOT / "output" / f"multipliers{BL.suffix(mode, fiscal)}.csv"


def load(mode: str = "calibrated", fiscal: str = "simple"):
    with BL.out_path(mode, fiscal).open("rb") as f:
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


def gov_port(base: dict, t: int, dg: float) -> dict[str, float]:
    """移植版: 実質政府支出の追加 dg（実質）を、会計の歳出項目の調整項（名目）に配分する.

    国・地方 1:1、各々の中は政府消費と公共投資の標準ケースの比。国の消費はその他一般歳出の中間投入
    （Z_EXPX31、SNA の政府消費に全額入る）、国の投資は公共事業の直轄事業費（Z_EXPA1、Z_IG1$ 倍が
    公的固定資本形成になる）、地方の消費は物件費（Z_LGEXCG）、地方の投資は補助事業費（Z_LGEXIH）。
    """
    pcg, pig = base["M_PCG"][t], base["M_PIG"][t]
    cc = -(base["M_CGVCC"][t] + base["M_CGVIC"][t]) / pcg
    ic = base["Z_IG1"][t] / pig
    cl = -(base["M_CGVCL"][t] + base["M_CGVIL"][t]) / pcg
    il = base["Z_IG3"][t] / pig
    return {
        "Z_ADJEXPX31": 0.5 * dg * cc / (cc + ic) * pcg,
        "Z_ADJEXPA1": 0.5 * dg * ic / (cc + ic) * pig / base["Z_IG1$"][t],
        "Z_ADJLGEXCG": 0.5 * dg * cl / (cl + il) * pcg,
        "Z_ADJLGEXIH": 0.5 * dg * il / (cl + il) * pig,
    }


def shock(case: int, data: dict, base: dict, fiscal: str = "simple") -> set[str]:
    """data を書き換えてショックを与える。外生化する内生変数の集合を返す."""
    exo = set()
    port = fiscal == "port"
    for k, t in enumerate(YEARS):
        if case in (1, 2) and (case == 2 or k == 0):
            dg = 0.01 * base["M_GDP"][t]
            if port:
                for v, x in gov_port(base, t, dg).items():
                    data[v][t] = base[v][t] + x
            else:
                for v, w in gov_split(base, t).items():
                    data[v][t] = base[v][t] + w * dg
        elif case == 3:
            if port:  # 法人税（国）の実効税率を、税収が名目GDPの1%増えるだけ引き上げる
                data["Z_RTYCVH"][t] = base["Z_RTYCVH"][t] + 0.01 * base["M_GDPV"][t] / base["M_YCVS"][t]
            else:
                data["Z_TYCVX"][t] = 0.01 * base["M_GDPV"][t]
        elif case == 4:
            if port:  # 所得税（国）を名目GDPの1%増税
                data["Z_ADJTXAG"][t] = base["Z_ADJTXAG"][t] + 0.01 * base["M_GDPV"][t]
            else:
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


def hold_real_g(s: Solver, case: int, k: int, t: int, base: dict, exo: set[str], n_iter: int = 6) -> None:
    """移植版: 実質の政府消費と公的固定資本形成を目標の値に保つ.

    公表乗数は「ケース③〜⑧では実質政府支出は一定と仮定」している。移植版では歳出が賃金・物価に
    連動して動くので、ずれを会計の歳出項目の調整項で打ち消し、その年を解き直す（数回繰り返す）。
    政府支出のケース（①②）では、標準ケースに実質GDPの1%を足した値を目標にする。
    """
    data = s.data
    d_cg = d_ig = 0.0
    if case in (1, 2) and (case == 2 or k == 0):
        adj = gov_port(base, t, 0.01 * base["M_GDP"][t])
        d_cg = (adj["Z_ADJEXPX31"] + adj["Z_ADJLGEXCG"]) / base["M_PCG"][t]
        d_ig = (adj["Z_ADJEXPA1"] * base["Z_IG1$"][t] + adj["Z_ADJLGEXIH"]) / base["M_PIG"][t]
    tgt_cg, tgt_ig = base["M_CG"][t] + d_cg, base["M_IG"][t] + d_ig
    for _ in range(n_iter):
        gap_c = (tgt_cg - data["M_CG"][t]) * data["M_PCG"][t]
        gap_i = (tgt_ig - data["M_IG"][t]) * data["M_PIG"][t]
        if abs(gap_c) + abs(gap_i) < 1e-6:
            break
        data["Z_ADJEXPX31"][t] += 0.5 * gap_c
        data["Z_ADJLGEXCG"][t] += 0.5 * gap_c
        data["Z_ADJEXPA1"][t] += 0.5 * gap_i / data["Z_IG1$"][t]
        data["Z_ADJLGEXIH"][t] += 0.5 * gap_i
        s.solve_year(t, pinned=exo, calibrate_pinned=False)


def extra(data: dict, t: int) -> dict[str, float]:
    return {"TAXAGDP": (data["M_TAXV"][t] + data["Z_TXOH"][t]) / data["M_GDPV"][t] * 100}


def run(case: int, model=None, base_data=None, af=None) -> pd.DataFrame:
    m = model or build()
    if base_data is None:
        base_data, af = load()
    data = copy.deepcopy(base_data)
    fiscal = getattr(m, "fiscal", "simple")
    exo = shock(case, data, base_data, fiscal)
    s = Solver(m, data, af)
    for k, t in enumerate(YEARS):
        s.solve_year(t, pinned=exo, calibrate_pinned=False)
        if fiscal == "port":
            hold_real_g(s, case, k, t, base_data, exo)
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


def main(mode: str = "calibrated", fiscal: str = "simple") -> pd.DataFrame:
    m = build(mode, fiscal)
    base_data, af = load(mode, fiscal)
    # 標準ケースがそのまま再現されることを確認する
    chk = run(0, m, base_data, af)
    worst = chk["model"].abs().max()
    print(f"ショックなしの乖離の最大値: {worst:.2e}")
    res = pd.concat([run(c, m, base_data, af) for c in P.CASES], ignore_index=True)
    pub = pd.read_csv(P.OUT) if P.OUT.exists() else P.main()
    res = res.merge(pub.rename(columns={"value": "published"}), on=["case", "var", "period"], how="left")
    out = out_path(mode, fiscal)
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    print(f"→ {out}")
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    ap.add_argument("--fiscal", default="simple", choices=["simple", "port"])
    a = ap.parse_args()
    r = main(a.mode, a.fiscal)
    pd.set_option("display.width", 200)
    for c in P.CASES:
        x = r[(r.case == c) & r["var"].isin(["M_GDP", "M_CPIG", "M_RCO", "M_UR", "M_PBGAGDPV", "Z_DEBTAGDP"])]
        print(f"\n=== ケース{c}: {P.CASES[c]}")
        print(x.pivot_table(index="var", columns="period", values=["model", "published"]).round(2).to_string())
