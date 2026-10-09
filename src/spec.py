"""モデルの方程式体系を組み立てる（マクロ・人口ブロック＋財政・社会保障の簡略版）.

- マクロ経済・人口ブロックは方程式リストの式をそのまま使う（人口ブロックの年齢・性別の
  ひな形 aaaa/b は展開する）。
- 財政・社会保障ブロックは移植せず、マクロブロックが参照する変数だけを簡略な式で与える。
  簡略版の式は原典と同じ EViews 形式で書き、translate.py で同じように変換する。
- OVERRIDE はマクロブロックの式のうち簡略版で置き換えるもの、DROP は使わない表示用の式。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from translate import CompiledEq, compile_eq

ROOT = Path(__file__).resolve().parents[1]
EQ_JSON = ROOT / "data" / "processed" / "equations.json"

AGES = ["1519", "2024", "2529", "3034", "3539", "4044", "4549", "5054", "5559", "6064", "6569", "70OV"]
AGES_LW = AGES[:10]  # 雇用者数のひな形は 60〜64歳まで（65歳以上は別式）
SEXES = ["F", "M"]

# ---------------------------------------------------------------------------
# 財政・社会保障の簡略版（名目は10億円、政府の支払いは負値という原典の符号に合わせる）
# ---------------------------------------------------------------------------
FISCAL = {
    # --- 税収 ---
    # 消費税：原典の Z_TCIVB と同じ課税ベース（軽減税率は使わない）
    "Z_TCIVB": "Z_TCIVB=(Z_RTCIV/(1+Z_RTCIV))*(M_VATACP$*M_CPV+M_IHPV+M_VATACG$*M_CGV+M_VATAIG$*M_IGV)",
    "Z_TCIV": "Z_TCIV=Z_TCIVB",
    "Z_TCIVC": "Z_TCIVC=Z_TCIV*Z_TCIVC$",
    "Z_TCIVL": "Z_TCIVL=Z_TCIV-Z_TCIVC",
    # その他の間接税：名目GDP並み
    "Z_OITAXVC": "Z_OITAXVC=Z_OITAXVC(-1)*(1+@pch(M_GDPV))",
    "Z_OITAXVL": "Z_OITAXVL=Z_OITAXVL(-1)*(1+@pch(M_GDPV))",
    "Z_OITAXV": "Z_OITAXV=Z_OITAXVC+Z_OITAXVL",
    # 家計の所得税（国）：原典の所得税の推計式（Z_TXAG）の弾性値
    "Z_TYPVC": "dlog(Z_TYPVC-Z_TYPVX)=1.172349*dlog(M_YWIV+M_YIV-M_YIGV+M_YCVSELF)",
    # 個人住民税（地方）：原典の住民税（所得割）の推計式（Z_TXPLW0）
    "Z_TYPVL": "dlog(Z_TYPVL)=0.69124*dlog(M_YWIV(-1))+0.34562*dlog(M_YWIV(-2))",
    "Z_TYPV": "Z_TYPV=Z_TYPVC+Z_TYPVL",
    # 法人課税：法人税課税標準 M_YCVS × 実効税率。地方分は原典の法人住民税・事業税の
    # 推計式（法人税の今期と前期にかかる）に合わせて前期分も含める
    "Z_TYCVC": "Z_TYCVC=Z_RTYCVC$*M_YCVS+Z_TYCVX",
    "Z_TYCVL": "Z_TYCVL=Z_RTYCVL$*(0.53*M_YCVS+0.47*M_YCVS(-1))",
    # その他の経常税（自動車税など）：名目GDP並み
    "Z_OTAXC": "Z_OTAXC=Z_OTAXC(-1)*(1+@pch(M_GDPV))",
    "Z_OTAXL": "Z_OTAXL=Z_OTAXL(-1)*(1+@pch(M_GDPV))",
    "Z_TYCV": "Z_TYCV=M_DTAXV-Z_TYPV",
    "M_TAXC": "M_TAXC=Z_TCIVC+Z_OITAXVC+Z_TYPVC+Z_TYCVC+Z_OTAXC",
    "M_TAXL": "M_TAXL=Z_TCIVL+Z_OITAXVL+Z_TYPVL+Z_TYCVL+Z_OTAXL",
    # 法人実効税率（資本コストと株価の式で使う）
    "M_ECT$": "M_ECT$=(Z_TYCVC+Z_TYCVL)/(M_YCVPRE-M_YCGIV)",
    # --- 社会負担：雇主の現実社会負担は賃金に比例（保険料率一定）---
    "M_YSLIPV": "M_YSLIPV=M_YSLIPV$*M_YWIPV",
    "M_YSLIGV": "M_YSLIGV=M_YSLIGV$*M_YWIGV",
    # --- 歳出 ---
    # 政府の雇用者報酬：一人当たり賃金並み
    "M_YWGV": "M_YWGV=M_YWGV(-1)*(1+@pch(M_W))",
    # 政府消費（社会保障基金以外）：実質額を外生で与える（政策変数）
    "M_CGVCC": "M_CGVCC=-M_CGRCC*M_PCG",
    "M_CGVIC": "M_CGVIC=-M_CGRIC*M_PCG",
    "M_CGVCL": "M_CGVCL=-M_CGRCL*M_PCG",
    "M_CGVIL": "M_CGVIL=-M_CGRIL*M_PCG",
    # 社会保障基金の現物給付（医療・介護）も実質額を外生で与える。公表乗数は「ケース③〜⑧では
    # 実質政府支出は一定と仮定」しているので、物価が動いても実質の政府支出は変えない
    "M_CGVIF": "M_CGVIF=-M_CGRIF*M_PCG",
    # 現金給付：年金は前年の物価（マクロ経済スライドの調整率を差し引く）、ほかは前年の物価
    "S_PENB": "S_PENB=S_PENB(-1)*(1+@pch(M_CPIG(-1))-S_SLIDE$)*(1+S_PENQ$)",
    "M_BSSVF": "M_BSSVF=-S_PENB+M_BSSVFER",
    "M_BSSVC": "M_BSSVC=M_BSSVC(-1)*(1+@pch(M_CPIG(-1)))",
    "M_BSSVL": "M_BSSVL=M_BSSVL(-1)*(1+@pch(M_CPIG(-1)))",
    # 補助金・その他の移転：物価並み
    "M_SUBVC": "M_SUBVC=M_SUBVC(-1)*(1+@pch(M_PGDP))",
    "M_SUBVL": "M_SUBVL=M_SUBVL(-1)*(1+@pch(M_PGDP))",
    "M_TRPC": "M_TRPC=M_TRPC(-1)*(1+@pch(M_PGDP))",
    "M_TRPL": "M_TRPL=M_TRPL(-1)*(1+@pch(M_PGDP))",
    "M_TRPF": "M_TRPF=M_TRPF(-1)*(1+@pch(M_PGDP))",
    "M_CTRPC": "M_CTRPC=M_CTRPC(-1)*(1+@pch(M_PGDP))",
    "M_CTRPL": "M_CTRPL=M_CTRPL(-1)*(1+@pch(M_PGDP))",
    "M_CTRGC": "M_CTRGC=M_CTRGC(-1)*(1+@pch(M_PGDP))",
    "M_CTRGL": "M_CTRGL=M_CTRGL(-1)*(1+@pch(M_PGDP))",
    "Z_TXOH": "Z_TXOH=Z_TXOH(-1)*(1+@pch(M_GDPV))",
    # 一般政府内の経常移転：地方交付税は国税収、社会保障基金への公費負担は社会保障給付に連動
    "M_TRGL": "M_TRGL=M_TRGL(-1)*(1+@pch(M_TAXC))",
    "M_TRGF": "M_TRGF=M_TRGF(-1)*(1+@pch(M_CGVIF+M_BSSVF))",
    # 公的固定資本形成：実質額を外生で与える（政策変数）
    "Z_IG1": "Z_IG1=M_IGR1*M_PIG",
    "Z_IG2": "Z_IG2=M_IGR2*M_PIG",
    "Z_IG3": "Z_IG3=M_IGR3*M_PIG",
    "Z_IG5": "Z_IG5=M_IGR5*M_PIG",
    # --- 公債と利払費 ---
    # 平均調達金利は新発10年債利回りに徐々に近づく（借換えの速さ = 1/平均残存年数）
    "M_RAVGC": "M_RAVGC=M_RAVGC(-1)+(M_RGB-M_RAVGC(-1))/Z_MATC$",
    "M_RAVGL": "M_RAVGL=M_RAVGL(-1)+(M_RGB-M_RAVGL(-1))/Z_MATL$",
    # 利払費は原典の国債利払費（Z_PINTBON=0.5*B_BRPAY+0.5*B_BRPAY(-1)）と同じく半年ずれる
    "M_YIGVCRLWF": "M_YIGVCRLWF=(0.5*M_RAVGC+0.5*M_RAVGC(-1))/100*Z_GBNML(-1)+M_YIGVCRLR",
    "M_YIGVLRLWF": "M_YIGVLRLWF=(0.5*M_RAVGL+0.5*M_RAVGL(-1))/100*B_ZLGB(-1)+M_YIGVLRLR",
    "M_YIGVLRLR": "M_YIGVLRLR=M_YIGVLRLR(-1)",
    "M_YIGVFRAWF": "M_YIGVFRAWF=M_YIGVFRAWF(-1)*(1+@pch(M_GDPV))",
    # 公債等残高 = 国債 + 地方債 + 交付税特会借入金（純借入の累積）。法人課税は中間納付分を除き
    # 決算後に納付されるため、増減の一部（Z_TYCVLAG$）が会計ベースの残高に1年遅れて効く（SNA は発生主義）
    "Z_GBNML": "Z_GBNML=Z_GBNML(-1)-M_BGCV+Z_TYCVLAG$*(Z_TYCVC-Z_TYCVC(-1))",
    # 地方債は地方財政計画で発行額が決まるので、地方の収支の変化は一部（Z_LGBTH$）しか地方債に回らない
    # （残りは基金などの金融資産の増減）。原典も B_ZLGB=B_ZLGB(-1)+Z_LGB-B_ROPT（発行額−償還額）で積み上げる
    "B_ZLGB": "B_ZLGB=B_ZLGB(-1)-Z_LGBTH$*(M_BGLV-Z_TYCVLAG$*(Z_TYCVL-Z_TYCVL(-1)))",
    "Z_DEBTOUT": "Z_DEBTOUT=Z_GBNML+B_ZLGB+Z_SPB",
    "Z_DEBTAGDP": "Z_DEBTAGDP=Z_DEBTOUT/M_GDPV*100",
}

# モード
# - "calibrated"（既定）: 公表乗数に合わせた修正を入れる（EQ_FIX と data2024.MODE_PARAMS）
# - "faithful": 原典の式を書き換えず、公表乗数に合わせて選んだ値も使わない
MODES = ("calibrated", "faithful")

# 方程式リストの式を書き換えるもの（calibrated のときだけ）: {変数名: (元の文字列, 新しい文字列)}。
# 理由は README に記載。
EQ_FIX = {
    # コールレート: テイラー・ルールの今期の変化に直接反応する項（0.246378*d(M_TAYLOR)）を外す。
    # 原典どおりだと政府支出拡大の1年目の上昇が0.24%ptで公表乗数（0.08%pt）の3倍になる。
    # 外すと7ケース×5年のコールレート・長期金利の乗数が公表値とほぼ一致する（README 参照）。
    "M_RCO": ("+0.246378*d(M_TAYLOR)", ""),
}

# 簡略版で置き換えるマクロブロックの式（FISCAL に同名の式があるもの）は自動で外す。
# 次は使わない表示用・会計ベースの式。
DROP = {
    "M_BSSVCAR", "M_BSSVMED", "M_BSSVPEN", "M_BSSVSNA", "M_CSSVCAR", "M_CSSVMED", "M_CSSVPEN",
    "M_CSSVSNA", "M_CSSVAGDP", "M_CSSVANIV", "M_CZEIGAI", "M_ZEIGAI", "M_TAXCER", "M_TAXLER",
    "M_BGCVA", "M_BGLVA", "M_BGCAAGDP", "M_BGLAAGDP", "M_PBCA", "M_PBCAAGDP", "M_PBCEXR",
    "M_PBCEXRAGDP", "M_PBGEXR", "M_PBGEXRAGDP", "M_PBLA", "M_PBLAAGDP", "M_PBLEXR", "M_PBLEXRAGDP",
    "MR_PBC", "MR_PBG", "MR_PBL", "MX_PBC", "M_GNIVPERCAP",
}


@dataclass
class Model:
    eqs: list[CompiledEq]
    meta: dict = field(default_factory=dict)  # name -> {label, block, estimated}
    mode: str = "calibrated"

    @property
    def endog(self) -> list[str]:
        return [e.name for e in self.eqs]

    def exog(self) -> list[str]:
        en = set(self.endog)
        return sorted({v for e in self.eqs for v in e.vars} - en)


def expand(name: str, eq: str) -> list[tuple[str, str]]:
    """人口ブロックのひな形（aaaa=年齢、b=性別）を展開する."""
    if "aaaa" not in name:
        return [(name, eq)]
    ages = AGES_LW if name.startswith("P_LW") else AGES
    out = []
    for a in ages:
        for s in SEXES:
            out.append((name.replace("aaaab", a + s), eq.replace("aaaab", a + s)))
    return out


def build(mode: str = "calibrated") -> Model:
    if mode not in MODES:
        raise ValueError(f"mode は {MODES} のどれか: {mode}")
    items = json.loads(EQ_JSON.read_text(encoding="utf-8"))
    eqs: list[CompiledEq] = []
    meta: dict = {}
    for it in items:
        if it["block"] not in ("population", "macro"):
            continue
        raw_name = it["name"]
        name = raw_name.upper()
        if name in FISCAL or name in DROP:
            continue
        if len(it["eqs"]) != 1:
            raise ValueError(f"{name}: 式が {len(it['eqs'])} 本")
        pdl = [p["coefs"] for p in it["pdl"]]
        src = it["eqs"][0]
        if mode == "calibrated" and name in EQ_FIX:
            old, new = EQ_FIX[name]
            if old not in src:
                raise ValueError(f"{name}: 書き換え対象「{old}」が式にない")
            src = src.replace(old, new)
        for nm, eq in expand(raw_name, src):
            nm = nm.upper()
            eqs.append(compile_eq(nm, eq, pdl))
            meta[nm] = {"label": it["label"], "block": it["block"], "estimated": bool(it["stats"] or pdl
                        or _has_coef(eq))}
    for nm, eq in FISCAL.items():
        eqs.append(compile_eq(nm, eq))
        meta[nm] = {"label": "（簡略版）", "block": "fiscal_simple", "estimated": nm in ESTIMATED_FISCAL}
    names = [e.name for e in eqs]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise ValueError(f"同じ変数の式が複数: {dup}")
    return Model(eqs, meta, mode)


ESTIMATED_FISCAL = {"Z_TYPVC", "Z_TYPVL"}


def _has_coef(eq: str) -> bool:
    import re
    return bool(re.search(r"\d\.\d{4,}", eq))


if __name__ == "__main__":
    m = build()
    ex = m.exog()
    print(f"内生変数 {len(m.endog)}、外生変数 {len(ex)}、推計式 {sum(v['estimated'] for v in m.meta.values())}")
    print("外生:", " ".join(ex))
