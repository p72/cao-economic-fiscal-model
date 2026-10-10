"""内閣府「中長期の経済財政に関する試算」（2026年1月）の感応度分析を、このモデルで再現する.

資料: https://www5.cao.go.jp/keizai3/econome/r8chuuchouki2601.pdf （本文「５．リスク・不確実性」、図19～21）
資料の感応度分析は「経済財政モデル（2018年度版）」の主要乗数表を使っている。ここでは2026年度版の再現モデル
（財政ブロックの移植版）で、2027～2035年度に同じショックを与え、標準ケースからの乖離を比べる。

- tfp : ＴＦＰ上昇率が過去投影ケース対比で継続的に0.5%pt程度低下（図19）
- rate: 長期金利が継続的に0.5%pt程度上振れ（図20、過去投影ケース対比・成長移行ケース対比）
- gov : 政府支出が毎年名目ＧＤＰの0.5%程度増加（図21、同上）

標準ケースは baseline.py の変種 kako（過去投影ケースに近い一定成長の経路）と seicho（成長移行ケースに近い経路）。
出力: output/chuuchouki_sensitivity.csv、output/chuuchouki_sensitivity.png
"""
from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pandas as pd

import baseline as BL
from simulate import gov_port
from solver import Solver
from spec import build

ROOT = Path(__file__).resolve().parents[1]
YEARS = list(range(2027, 2036))

# 資料の参考計数（2027～2035年度）。乖離 = ショックのケース − 元のケース
PUB = {
    "kako": {
        "PB": [0.6, 0.9, 1.0, 1.0, 1.0, 0.9, 0.9, 0.9, 0.8],
        "DEBT": [185.1, 184.4, 184.2, 184.1, 184.3, 184.8, 185.4, 186.3, 187.5],
        "NGDP": [703.1, 711.9, 720.5, 729.2, 737.9, 746.6, 755.2, 763.5, 771.7],
        "POT": [0.7, 0.6, 0.6, 0.6, 0.5, 0.5, 0.5, 0.4, 0.4],
        "RGB": [2.1, 2.0, 2.0, 2.0, 1.9, 1.9, 1.8, 1.8, 1.7],
    },
    "seicho": {
        "PB": [0.6, 1.1, 1.3, 1.4, 1.6, 1.7, 1.7, 1.8, 1.8],
        "DEBT": [183.3, 180.1, 176.9, 173.5, 170.5, 167.9, 165.8, 164.0, 162.6],
        "RGB": [2.3, 2.5, 2.7, 2.9, 3.0, 3.1, 3.2, 3.3, 3.3],
    },
    ("tfp", "kako"): {
        "POT": [0.2, 0.1, 0.1, -0.1, -0.2, -0.2, -0.3, -0.4, -0.5],
        "NGDP": [701.2, 707.4, 713.0, 718.3, 723.1, 727.9, 732.6, 736.7, 740.4],
        "PB": [0.5, 0.8, 0.8, 0.6, 0.5, 0.4, 0.2, 0.0, -0.2],
        "DEBT": [185.7, 185.8, 186.5, 187.5, 189.0, 190.6, 192.5, 194.5, 196.9],
    },
    ("rate", "kako"): {
        "RGB": [2.6, 2.5, 2.5, 2.5, 2.4, 2.4, 2.3, 2.3, 2.2],
        "DEBT": [185.3, 185.0, 185.1, 185.4, 186.1, 186.8, 187.8, 189.1, 190.7],
    },
    ("rate", "seicho"): {
        "RGB": [2.8, 3.0, 3.2, 3.4, 3.5, 3.6, 3.7, 3.8, 3.8],
        "DEBT": [183.5, 180.6, 177.8, 174.8, 172.2, 169.9, 168.2, 166.8, 165.8],
    },
    ("gov", "kako"): {"PB": [0.2, 0.6, 0.6, 0.6, 0.5, 0.5, 0.4, 0.4, 0.3]},
    ("gov", "seicho"): {"PB": [0.3, 0.8, 0.9, 1.0, 1.1, 1.2, 1.2, 1.3, 1.3]},
}
CASES = {"tfp": ("kako",), "rate": ("kako", "seicho"), "gov": ("kako", "seicho")}
LABELS = {"tfp": "ＴＦＰ上昇率 −0.5%pt", "rate": "長期金利 +0.5%pt", "gov": "政府支出 +名目GDPの0.5%"}


def published() -> pd.DataFrame:
    """資料の乖離（ショックのケース − 元のケース）."""
    rows = []
    for case, variants in CASES.items():
        for v in variants:
            sh, bs = PUB[(case, v)], PUB[v]
            for key in sh:
                for k, t in enumerate(YEARS):
                    if key == "NGDP":
                        dev = (sh[key][k] / bs[key][k] - 1) * 100
                    else:
                        dev = sh[key][k] - bs[key][k]
                    rows.append((case, v, key, t, dev))
    return pd.DataFrame(rows, columns=["case", "variant", "var", "year", "published"])


def gov_adj(base: dict, t: int, share: float) -> dict[str, float]:
    """政府支出（SNA の政府消費＋公的固定資本形成、名目）を名目GDPの share だけ増やす歳出の調整項."""
    unit = gov_port(base, t, 1.0)
    nominal_per_unit = (unit["Z_ADJEXPX31"] + unit["Z_ADJLGEXCG"] + unit["Z_ADJEXPA1"] * base["Z_IG1$"][t]
                        + unit["Z_ADJLGEXIH"])
    return gov_port(base, t, share * base["M_GDPV"][t] / nominal_per_unit)


def shock(case: str, data: dict, base: dict) -> set[str]:
    exo = set()
    for k, t in enumerate(YEARS):
        if case == "tfp":       # 対数ＴＦＰを毎年0.005ずつ下げる（上昇率 −0.5%pt）
            data["M_TFP"][t] = base["M_TFP"][t] - 0.005 * (k + 1)
        elif case == "rate":    # 長期金利（新発10年国債利回り）を外生化して +0.5%pt
            data["M_RGB"][t] = base["M_RGB"][t] + 0.5
            exo.add("M_RGB")
        elif case == "gov":
            for v, x in gov_adj(base, t, 0.005).items():
                data[v][t] = base[v][t] + x
    return exo


def hold_real_g(s: Solver, case: str, t: int, base: dict, exo: set[str], n_iter: int = 6) -> None:
    """実質の政府消費と公的固定資本形成を、標準ケース（政府支出のケースは標準ケース＋追加分）に保つ."""
    data = s.data
    d_cg = d_ig = 0.0
    if case == "gov":
        adj = gov_adj(base, t, 0.005)
        d_cg = (adj["Z_ADJEXPX31"] + adj["Z_ADJLGEXCG"]) / base["M_PCG"][t]
        d_ig = (adj["Z_ADJEXPA1"] * base["Z_IG1$"][t] + adj["Z_ADJLGEXIH"]) / base["M_PIG"][t]
    tgt_cg, tgt_ig = base["M_CG"][t] + d_cg, base["M_IG"][t] + d_ig
    for _ in range(n_iter):
        gap_c = (tgt_cg - data["M_CG"][t]) * data["M_PCG"][t]
        gap_i = (tgt_ig - data["M_IG"][t]) * data["M_PIG"][t]
        if abs(gap_c) + abs(gap_i) < 0.05:
            break
        data["Z_ADJEXPX31"][t] += 0.5 * gap_c
        data["Z_ADJLGEXCG"][t] += 0.5 * gap_c
        data["Z_ADJEXPA1"][t] += 0.5 * gap_i / data["Z_IG1$"][t]
        data["Z_ADJLGEXIH"][t] += 0.5 * gap_i
        s.solve_year(t, pinned=exo, calibrate_pinned=False)


def run(case: str, variant: str, mode: str = "calibrated") -> pd.DataFrame:
    m = build(mode, "port")
    with BL.out_path(mode, "port", variant).open("rb") as f:
        b = pickle.load(f)
    base, af = b["data"], b["af"]
    data = copy.deepcopy(base)
    exo = shock(case, data, base)
    s = Solver(m, data, af)
    for t in YEARS:
        s.solve_year(t, pinned=exo, calibrate_pinned=False)
        hold_real_g(s, case, t, base, exo)
    rows = []
    for t in YEARS:
        pot = ((data["M_GDPP"][t] / data["M_GDPP"][t - 1]) - (base["M_GDPP"][t] / base["M_GDPP"][t - 1])) * 100
        rows += [
            (case, variant, "PB", t, data["M_PBGAGDPV"][t] - base["M_PBGAGDPV"][t]),
            (case, variant, "DEBT", t, data["Z_DEBTAGDP"][t] - base["Z_DEBTAGDP"][t]),
            (case, variant, "NGDP", t, (data["M_GDPV"][t] / base["M_GDPV"][t] - 1) * 100),
            (case, variant, "RGDP", t, (data["M_GDP"][t] / base["M_GDP"][t] - 1) * 100),
            (case, variant, "POT", t, pot),
            (case, variant, "RGB", t, data["M_RGB"][t] - base["M_RGB"][t]),
        ]
    return pd.DataFrame(rows, columns=["case", "variant", "var", "year", "model"])


def part_path(case: str, variant: str, mode: str = "calibrated") -> Path:
    """ケースごとの途中結果（run_all.py --next で1つずつ計算するとき）."""
    return ROOT / "output" / "parts" / f"chuuchouki{'' if mode == 'calibrated' else '_' + mode}_{case}_{variant}.csv"


def main(mode: str = "calibrated", part: str | None = None, merge: bool = False) -> pd.DataFrame | None:
    """全ケースを計算する。part="case:variant" ならその組だけ計算して途中結果に保存し、
    merge=True なら途中結果をまとめて最終の出力にする."""
    pairs = [(c, v) for c, vs in CASES.items() for v in vs]
    if part:
        c, v = part.split(":")
        out = part_path(c, v, mode)
        out.parent.mkdir(parents=True, exist_ok=True)
        run(c, v, mode).to_csv(out, index=False)
        print(f"→ {out}")
        return None
    if merge:
        res = pd.concat([pd.read_csv(part_path(c, v, mode)) for c, v in pairs], ignore_index=True)
    else:
        res = pd.concat([run(c, v, mode) for c, v in pairs], ignore_index=True)
    res = res.merge(published(), on=["case", "variant", "var", "year"], how="left")
    out = ROOT / "output" / f"chuuchouki_sensitivity{'' if mode == 'calibrated' else '_' + mode}.csv"
    res.to_csv(out, index=False)
    print(f"→ {out}")
    last = res[res["year"] == YEARS[-1]].dropna(subset=["published"])
    print(last[["case", "variant", "var", "model", "published"]].round(2).to_string(index=False))
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    ap.add_argument("--part", help="case:variant（例 tfp:kako）だけ計算する（途中結果に保存）")
    ap.add_argument("--merge", action="store_true", help="途中結果をまとめる")
    a = ap.parse_args()
    main(a.mode, a.part, a.merge)
