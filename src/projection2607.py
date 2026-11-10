"""内閣府「中長期の経済財政に関する試算」（2026年7月）を、このモデルで作り直す（2040年度まで）.

資料: https://www5.cao.go.jp/keizai-shimon/kaigi/minutes/2026/0730shiryo_02-2.pdf
計数: src/chuuchouki2607_data.py（tools/extract_chuuchouki2607.py が PDF から書き出したもの）

方法は2026年1月の試算の再現（projection.py）と同じで、その関数をそのまま使い、前提と目標の値だけを7月の試算に置き換える。
1. 出発点は2024年度の実績。標準ケースは実質ゼロ成長で物価1.6%の経路（baseline.py の proj2607）。国債の発行年度は
   2040年度まで積み上げる（環境変数 CAO_LAST_VINTAGE=2040。このファイルを最初に読み込むときに置く）。
2. マクロの項目（潜在成長率、実質GDP成長率、消費者物価、GDPデフレーター、失業率、賃金、名目長期金利）は全期間、
   資料の値に合うように対応する式の誤差項を決める。
3. 財政は資料の「財政の詳細計数表」の予算ベースの項目（国のPB対象経費、地方の歳出、国の利払費、地方の税収、
   地方交付税等、国のその他収入）を与え、SNA ベースの収支と公債等残高をモデルで計算する。2025・2026年度は
   国・地方の基礎的財政収支（除いたベース）、国の税収、公債等残高比を合わせる。
4. 前提（付録1）
   - 人口：社人研（令和5年推計）出生中位・死亡中位（projection.py と同じ）。
   - 労働参加率：2040年度の値が資料の値（成長戦略実現ケース①・②68.3%、現状投影66.5%）になるように、男女・年齢別の
     労働力率を「1−率」に比例して2040年度まで直線的に上げる（資料は2025年度63.9%）。
   - ＴＦＰ上昇率（資料: 2025年度0.3%）：①は5年程度で1.1%、さらに5年程度で1.4%（2030年度1.1%、2035年度1.4%に
     直線で上げる）。②は2030年度に1.1%で以降一定。現状投影は0.6%程度。2026・2027年度は3ケース共通（0.45%、0.6%）。
   - 世界経済：成長率は2028〜2031年度にIMF見通しに基づく2.5〜2.9%、以降2.5%。物価は1.7〜1.9%、以降1.9%
     （年ごとの値は資料にないので、資料の幅の中で置いた）。
   - 原油価格：2027年度85.4ドル（前年度比▲7.7%）、以降一定。
   - 追加財政支出：2027年度に実質10兆円、以降は物価・賃金上昇率並みに増える（extra_spending）。資料の国のPB対象経費に
     含まれているので、再現（ありのケース）では歳出の目標に合わせるだけで入る。支出なしのケースは noextra.py。
出力: output/chuuchouki2607_projection.csv（case, item, year, model, published）、
      output/chuuchouki2607_balance.csv（部門別の財政収支など、図に使う値）、output/parts/proj_state_2607_{case}.pkl
"""
from __future__ import annotations

import os

os.environ.setdefault("CAO_LAST_VINTAGE", "2040")   # bond_port を読み込む前に置く

import pickle  # noqa: E402
from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

import chuuchouki2607_data as D  # noqa: E402
import projection as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
YEARS = list(range(2025, 2041))
CASES = ("s1", "s2", "gen")
CASE_NAMES = D.CASE_NAMES
LFR_2040 = {"s1": 68.3, "s2": 68.3, "gen": 66.5}
LFR_2024_PUB = 63.4     # 2024年度の労働参加率（2026年1月の試算の値。7月の試算は2025年度63.9%）


def _tfp(case: str) -> dict[int, float]:
    out = {2025: 0.3, 2026: 0.45, 2027: 0.6}
    for t in range(2028, 2041):
        if case == "gen":
            out[t] = 0.6
        elif t <= 2030:
            out[t] = 0.6 + (1.1 - 0.6) * (t - 2027) / 3
        elif case == "s1":
            out[t] = min(1.4, 1.1 + 0.3 * (t - 2030) / 5)
        else:
            out[t] = 1.1
    return out


TFP = {c: _tfp(c) for c in CASES}
WORLD_G = {**{t: 2.5 for t in YEARS}, 2025: 2.9, 2026: 2.9, 2027: 2.9, 2028: 2.9, 2029: 2.8, 2030: 2.6, 2031: 2.5}
WORLD_P = {**{t: 1.9 for t in YEARS}, 2025: 1.7, 2026: 1.7, 2027: 1.7, 2028: 1.7, 2029: 1.8, 2030: 1.8, 2031: 1.9}
OIL = {**{t: 85.4 for t in YEARS}, 2025: 68.1, 2026: round(85.4 / (1 - 0.077), 1)}

# projection.py の主要計数表の項目（モデルで計算できるもの）
ITEMS = ["潜在成長率", "実質GDP成長率", "名目GDP成長率", "名目GDP", "1人当たり実質GDP成長率", "賃金上昇率", "完全失業率",
         "消費者物価上昇率", "GDPデフレーター変化率", "名目長期金利", "基礎的財政収支（対GDP比）", "公債等残高（対GDP比）"]


def fiscal_pub(case: str) -> dict[str, list[float]]:
    """projection.py の FISCAL_PUB と同じ名前の目標（兆円）."""
    f = D.FISCAL[case]
    out = {k: f[k] for k in ("国の税収", "国のPB対象経費", "地方の歳出", "国のその他収入", "国の利払費", "地方の税収",
                             "地方交付税等", "地方の税収等", "地方の普通会計の基礎的財政収支")}
    out["国の基礎的財政収支"] = f["国の基礎的財政収支（除く）"]
    out["地方の基礎的財政収支"] = f["地方の基礎的財政収支（除く）"]
    out["地方の一般歳出"] = [a - b for a, b in zip(out["地方の税収等"], out["地方の普通会計の基礎的財政収支"])]
    out["国・地方の基礎的財政収支"] = f["基礎的財政収支（除く）"]
    out["純利払費"] = [a - b for a, b in zip(f["基礎的財政収支（除く）"], f["財政収支（除く）"])]
    out["社会保障基金"] = ssf_pub(case)
    return out


def ssf_pub(case: str) -> list[float]:
    """社会保障基金の財政収支（兆円）。資料に表がないので、付録2の一般政府の部門別収支（対GDP比）× 名目GDP から、
    国・地方の財政収支（含んだベース。一般政府は SNA の値で、復旧・復興対策等を含む）を引いて求める。
    一般政府の対GDP比は0.1%刻みなので、±0.5兆円程度の誤差がある."""
    gg = [r / 100 * g for r, g in zip(D.SECTOR[case]["一般政府"], D.PUB[case]["名目GDP"])]
    return [a - b for a, b in zip(gg, D.FISCAL[case]["財政収支（含む）"])]


# 2026年1月の試算の再現（projection.py）に加えて合わせる項目（目標 ← 調整する変数）。
# 国の税収: 2027年度以降も資料に合わせる（所得税の調整項）。7月の試算の税収には、2027年度までの時限的な減税の終了など
#   モデルの式にない制度要因が入っている。合わせないとモデルの税収が2〜3兆円少なく、国債の発行が増えて公債等残高比が
#   2040年度に4〜5%pt高く出る。
# 国・地方の基礎的財政収支（SNA）: 国の民間への資本移転の調整項（M_ADJCTRPC、SNA だけに入る）で合わせる。予算の歳出を
#   資料どおりにしても、追加財政支出のうち地方への補助金の分などが SNA で国と地方の両方の支出になり、PB が1〜2兆円小さく出る。
# 純利払費（SNA、国・地方）: 国の支払利子の会計と SNA の差（M_YIGVCRLR の式の誤差項）で合わせる。予算の利払費（資料に
#   合わせてある）を SNA の利払いに読み替えると、SNA の利払いが2兆円前後多く出る（2026年1月の試算の記事にも書いた差）。
# 社会保障基金の財政収支（SNA）: 社会保障基金の財産所得（受取）の誤差項（M_YIGVFAER）で、資料から割り出した値（ssf_pub）に
#   合わせる。モデルの年金積立金の運用収入は企業の資本収益率に連動する式で、7月の試算の「運用利回りが経済成長とともに
#   上がる」（2024年財政検証と整合的）想定より小さく、2028〜2033年度に2〜3兆円少なく出る。
EXTRA_FOLLOW = [("国の税収", "Z_ADJTXAG"), ("国・地方の基礎的財政収支", "M_ADJCTRPC"), ("純利払費", "M_YIGVCRLR"),
                ("社会保障基金", "M_YIGVFAER")]
EXTRA_FIT = [("純利払費", "M_YIGVCRLR"), ("社会保障基金", "M_YIGVFAER")]
_item_values = P.item_values


def item_values(data: dict, t: int) -> dict[str, float]:
    v = _item_values(data, t)
    v["国・地方の基礎的財政収支"] = data["M_PBG"][t] / 1000
    v["純利払費"] = (data["M_PBG"][t] - data["M_BGGV"][t]) / 1000
    v["社会保障基金"] = data["M_BGFV"][t] / 1000
    return v


def extra_spending(case: str) -> dict[int, float]:
    """追加財政支出（名目、兆円）。2027年度に10兆円、以降は物価・賃金上昇率で伸ばす.

    「物価・賃金上昇率並み」はモデルの歳出の伸び率の式（Z_GREXPXA = 1 + 0.4×賃金上昇率 + 0.6×物価上昇率）と同じ重みにする。
    """
    pub = D.PUB[case]
    out, x = {}, 10.0
    for t in range(2027, 2041):
        k = t - 2024
        if t > 2027:
            x *= 1 + (0.6 * pub["消費者物価上昇率"][k] + 0.4 * pub["賃金上昇率"][k]) / 100
        out[t] = x
    return out


def set_participation(data: dict, case: str) -> None:
    """2040年度の労働参加率が資料の値になるよう、男女・年齢別の労働力率を「1−率」に比例して直線的に上げる."""
    base = {(a, s): data[f"P_RLF{a}{s}"][2024] for a in P.AGES for s in ("M", "F")}
    target = P.lf_rate(data, 2024) + (LFR_2040[case] - LFR_2024_PUB)

    def apply(k: float) -> None:
        for t in YEARS:
            w = (t - 2024) / (2040 - 2024)
            for (a, s), r in base.items():
                data[f"P_RLF{a}{s}"][t] = r + k * w * (1 - r)

    lo, hi = 0.0, 0.6
    for _ in range(60):
        k = (lo + hi) / 2
        apply(k)
        if P.lf_rate(data, 2040) < target:
            lo = k
        else:
            hi = k
    apply((lo + hi) / 2)


def configure() -> None:
    """projection.py の前提と目標を2026年7月の試算に置き換える."""
    P.YEARS = YEARS
    P.PUB = {c: {k: D.PUB[c][k] for k in ITEMS} for c in CASES}
    P.ITEMS = ITEMS
    P.FISCAL_PUB = {c: fiscal_pub(c) for c in CASES}
    P.CASE_NAMES = CASE_NAMES
    P.TFP = TFP
    P.WORLD_G, P.WORLD_P, P.OIL = WORLD_G, WORLD_P, OIL
    P.VARIANT = {c: "proj2607" for c in CASES}
    P.set_participation = set_participation
    P.item_values = item_values
    if EXTRA_FIT[-1] not in P.TARGETS:
        P.TARGETS = P.TARGETS + EXTRA_FIT
        P.FOLLOW_TARGETS = P.FOLLOW_TARGETS + EXTRA_FOLLOW
    P.DATA_CTRL = P.DATA_CTRL | {"M_ADJCTRPC", "M_YIGVFAER"}
    P.STEP0.update({"M_ADJCTRPC": 1000.0, "M_YIGVCRLR": 500.0, "M_YIGVFAER": 500.0})
    P.PINT_AF_FILE = ROOT / "data" / "processed" / "_pintbon_af_2607.json"   # 使わない（全ケースに利払費の表がある）


def state_path(case: str) -> Path:
    return ROOT / "output" / "parts" / f"proj_state_2607_{case}.pkl"


def balance_rows(case: str, scen: str, data: dict) -> list[dict]:
    """図に使う値（兆円・%）。財政収支は SNA の純貸出（＋）／純借入（−）.

    国・地方は交付税特会の借入金を国・地方の負担分に応じて分けた値（M_BGCVA、M_BGLVA の式。資料と同じ分け方）。
    純利払費 = 国・地方の基礎的財政収支 − 国・地方の財政収支。
    """
    rows = []
    spb = lambda t: (data["Z_SPB"][t] - data["Z_SLBSTCC"][t]) / 1000   # M_BGCVA・M_BGLVA の式と同じ分け方
    for t in [2024] + YEARS:
        g = lambda v: data[v][t] / 1000
        rows.append({
            "case": case, "scen": scen, "year": t,
            "名目GDP": g("M_GDPV"), "実質GDP成長率": (data["M_GDP"][t] / data["M_GDP"][t - 1] - 1) * 100,
            "名目GDP成長率": (data["M_GDPV"][t] / data["M_GDPV"][t - 1] - 1) * 100,
            "消費者物価上昇率": (data["M_CPIG"][t] / data["M_CPIG"][t - 1] - 1) * 100,
            "名目長期金利": data["M_RGB"][t],
            "国": g("M_BGCV") + spb(t) - spb(t - 1), "地方": g("M_BGLV") - spb(t) + spb(t - 1), "社会保障基金": g("M_BGFV"), "一般政府": g("M_BGV"),
            "国・地方": g("M_BGGV"), "国・地方PB": g("M_PBG"), "純利払費": g("M_PBG") - g("M_BGGV"),
            "公債等残高比": data["Z_DEBTAGDP"][t], "国のPB対象経費": g("Z_EXPOLICY"), "国の税収": g("Z_REV1"),
        })
    return rows


def write_balance(cases=CASES, scens=("base",)) -> pd.DataFrame:
    """保存した最終状態から、図に使う値を output/chuuchouki2607_balance.csv に書き出す（あるものだけ）."""
    rows = []
    for c in cases:
        for sc in scens:
            p = state_path(c) if sc == "base" else ROOT / "output" / "parts" / f"proj_state_2607_{c}_{sc}.pkl"
            if p.exists():
                with p.open("rb") as f:
                    rows += balance_rows(c, sc, pickle.load(f)["data"])
    out = ROOT / "output" / "chuuchouki2607_balance.csv"
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"→ {out}")
    return df


def main(cases=CASES) -> None:
    configure()
    if os.environ.get("CAO_DEBUG_DIR"):      # 調査用: 毎年の途中の状態を保存する
        P.DEBUG_DIR = os.environ["CAO_DEBUG_DIR"]
        Path(P.DEBUG_DIR).mkdir(parents=True, exist_ok=True)
    out = ROOT / "output" / "chuuchouki2607_projection.csv"
    frames = []
    for c in cases:
        res = P.run(c)
        src = Path(P.DEBUG_DIR or ROOT / "output" / "parts") / f"proj_state_{c}.pkl"
        src.replace(state_path(c))
        frames.append(res)
    res = pd.concat(frames, ignore_index=True)
    if out.exists():
        old = pd.read_csv(out)
        res = pd.concat([old[~old["case"].isin(cases)], res], ignore_index=True)
    res.to_csv(out, index=False)
    print(f"→ {out}")
    write_balance(scens=("base", "noextra"))


def baseline() -> None:
    import baseline as BL
    BL.main("calibrated", "port", "proj2607")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=CASES, action="append", help="計算するケース（くり返し指定可）。既定は3ケース")
    ap.add_argument("--baseline", action="store_true", help="標準ケース proj2607（国債の発行年度は2040年度まで）を作る")
    a = ap.parse_args()
    if a.baseline:
        baseline()
    else:
        main(tuple(a.case) if a.case else CASES)
