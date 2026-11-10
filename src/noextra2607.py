"""2026年7月の中長期試算の再現経路から、追加財政支出（2027年度以降、毎年度実質10兆円）を除いたケースを計算する.

再現経路（projection2607.py）の誤差項と外生変数をそのまま使い、追加財政支出だけを取り除いて解き直す。
資料は追加財政支出を「公需」と「企業の資本コストを下げる補助金」が半分ずつとしているので、それぞれ次のように除く。
- 金額: projection2607.extra_spending（2027年度10兆円、以降は物価・賃金上昇率並み。名目）。
- 公需の半分: 国の政府消費と公的固定資本形成（実質）を、半分の額だけ減らす。国の消費と投資の比は再現経路の比
  （simulate.gov_port と同じ）。予算はその他一般歳出の中間投入（Z_EXPX31）と公共事業の直轄事業費（Z_EXPA1）。
  実質の政府消費・公的固定資本形成のそのほかの部分は再現経路のまま（chuuchouki.hold_real_g と同じ考え方）。
- 補助金の半分: 国の資本移転（民間への支払い、M_CTRPC）を半分の額だけ減らし、実質資本コスト（M_UCC）を
  補助率（補助金 ÷ 民間企業設備投資（名目））の分だけ上げる（資本コスト ×1/(1−補助率)）。
- 予算: 国の一般会計の歳出（国のPB対象経費）が追加財政支出の額だけ減るように、公需の分（Z_EXPX31、Z_EXPA1 の減少）で
  足りない分をその他一般歳出（Z_EXPX35）で減らす。Z_EXPX35 の減少は SNA に入らないよう Z_ADJEXPX35E で打ち消す。
金利（長期・短期）、税収、地方交付税、社会保障などはモデルの式で動く。
出力: output/parts/proj_state_2607_{case}_noextra.pkl、output/chuuchouki2607_balance.csv（scen=noextra の行）
"""
from __future__ import annotations

import os

os.environ.setdefault("CAO_LAST_VINTAGE", "2040")

import copy  # noqa: E402
import pickle  # noqa: E402
from pathlib import Path  # noqa: E402

import projection as P  # noqa: E402
import projection2607 as Q  # noqa: E402
from solver import Solver  # noqa: E402
from spec import build, compile_eq  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
YEARS = list(range(2027, 2041))


def out_path(case: str) -> Path:
    return ROOT / "output" / "parts" / f"proj_state_2607_{case}_noextra.pkl"


def run(case: str) -> dict:
    m = build("calibrated", "port")
    m.eqs.append(compile_eq("Z_EXPX35E", "Z_EXPX35E=Z_EXPX35+Z_ADJEXPX35E"))   # projection.py と同じ
    m.meta["Z_EXPX35E"] = {"label": "（追加: その他一般歳出の SNA 用）", "block": "fiscal", "estimated": False}
    with Q.state_path(case).open("rb") as f:
        st = pickle.load(f)
    base, af = st["data"], copy.deepcopy(st["af"])
    data = copy.deepcopy(base)
    s = Solver(m, data, af)
    extra = {t: x * 1000 for t, x in Q.extra_spending(case).items()}    # 10億円
    c_prev = 0.0                       # 前年度の Z_EXPX35 の水準の変化
    for t in YEARS:
        half = extra[t] / 2
        # 補助金の半分: 民間への資本移転（支払いは負）を減らし、資本コストを上げる
        data["M_ADJCTRPC"][t] = base["M_ADJCTRPC"][t] + half
        rate = half / base["M_IFPV"][t]
        af["M_UCC"][t] = st["af"]["M_UCC"][t] + base["M_UCC"][t] * rate / (1 - rate)
        # 公需の半分: 国の消費と投資の比（再現経路）で、実質の減少額を決める
        pcg, pig = base["M_PCG"][t], base["M_PIG"][t]
        cc = -(base["M_CGVCC"][t] + base["M_CGVIC"][t]) / pcg
        ic = base["Z_IG1"][t] / pig
        tgt_cg = base["M_CG"][t] - half * cc / (cc + ic) / pcg
        tgt_ig = base["M_IG"][t] - half * ic / (cc + ic) / pig
        data["Z_ADJEXPX31"][t] = base["Z_ADJEXPX31"][t] - half * cc / (cc + ic)
        data["Z_ADJEXPA1"][t] = base["Z_ADJEXPA1"][t] - half * ic / (cc + ic) / base["Z_IG1$"][t]
        for _ in range(10):
            # 予算の残り: 国のPB対象経費の減少が追加財政支出の額になるように、Z_EXPX35 の水準を c だけ動かす
            cut_pub = -((data["Z_EXPX31"][t] - base["Z_EXPX31"][t]) + (data["Z_EXPA1"][t] - base["Z_EXPA1"][t]))
            c = -(extra[t] - cut_pub)
            data["Z_ADJEXPX35"][t] = base["Z_ADJEXPX35"][t] + c - c_prev * data["Z_GREXPXA"][t]
            data["Z_ADJEXPX35E"][t] = base["Z_ADJEXPX35E"][t] - c
            P.solve(s, t)
            gap_c = (tgt_cg - data["M_CG"][t]) * data["M_PCG"][t]
            gap_i = (tgt_ig - data["M_IG"][t]) * data["M_PIG"][t]
            # 予算で直接減らした額（地方交付税など、税収の変化で動く歳出は含めない）と追加財政支出の差
            off = sum(data[v][t] - base[v][t] for v in ("Z_EXPX31", "Z_EXPA1", "Z_EXPX35")) + extra[t]
            if abs(gap_c) + abs(gap_i) < 1.0 and abs(off) < 5.0:
                break
            data["Z_ADJEXPX31"][t] += gap_c
            data["Z_ADJEXPA1"][t] += gap_i / data["Z_IG1$"][t]
        else:
            P.solve(s, t)
        c_prev = data["Z_EXPX35"][t] - base["Z_EXPX35"][t]
        d = lambda v: (data[v][t] - base[v][t]) / 1000
        print(f"{case} {t}: 追加財政支出 {extra[t] / 1000:.1f}兆円  国のPB対象経費 {d('Z_EXPOLICY'):+.1f}"
              f"（うち地方交付税等 {d('Z_DST'):+.1f}）  "
              f"実質GDP {(data['M_GDP'][t] / base['M_GDP'][t] - 1) * 100:+.2f}%  名目GDP {d('M_GDPV'):+.1f}兆円  "
              f"長期金利 {data['M_RGB'][t] - base['M_RGB'][t]:+.2f}  国・地方の財政収支 {d('M_BGGV'):+.1f}  "
              f"一般政府 {d('M_BGV'):+.1f}  残高比 {data['Z_DEBTAGDP'][t] - base['Z_DEBTAGDP'][t]:+.1f}", flush=True)
    with out_path(case).open("wb") as f:
        pickle.dump({"data": data, "af": af}, f)
    return data


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=Q.CASES, action="append")
    a = ap.parse_args()
    cases = tuple(a.case) if a.case else Q.CASES
    for c in cases:
        run(c)
    Q.write_balance(scens=("base", "noextra"))
