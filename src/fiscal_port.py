"""財政ブロックの移植版（spec.build(fiscal="port") で使う）.

- 国の一般会計・公共事業関係特別会計・地方財政計画・交付税特会・地方普通会計・その他指標（249本）は
  方程式リストの式をそのまま使う。資料の誤り・欠落と判断したものだけ PATCH で直す。
- 普通国債の発行年度別・年限別の積み上げと地方債の経過年数別の積み上げは bond_port.py で原典のひな形を展開する。
  年金特例国債は集約した式（BOND）、復興債・GX経済移行債・半導体・AI債は外生で与える。
- 社会保障ブロックのうち年金（83本）・医療（101本）・介護（39本）は方程式リストの式を使う。
  年齢別・要介護度別の積み上げは、基準年度の給付費 × 費用の指数に集約する（SS_COLLAPSED）。
  雇用保険・社会扶助（その他10本）も方程式リストの式を使う。
"""
from __future__ import annotations

BOND_SECTIONS = {"国債", "年金特例国債", "復興債", "GX経済移行債", "半導体・AI債", "地方債"}

# 方程式リストの誤り・欠落を補う式: {変数名: (式, 理由)}
PATCH = {
    # 見出し「地方歳出（計画値）」の下に水準超経費の式が載っていて、地方歳出の式がない。
    # 不交付団体の基準財政需要額（ZP_LGKEX）の対象経費と水準超経費の合計とみなす
    "ZP_LGEXTOTAL": ("ZP_LGEXTOTAL=ZP_LGEXP+ZP_LGEXSS+ZP_LGEXI+ZP_LGEXOH+ZP_SAISEI+ZP_CLB+ZP_SUIJUN",
                     "資料に式がない（見出しの下に ZP_SUIJUN の式がある）。推定"),
    "ZP_SUIJUN": ("ZP_SUIJUN=@recode(((ZP_LGKIN-ZP_LGKEX)/0.75)>=0,((ZP_LGKIN-ZP_LGKEX)/0.75),0)",
                  "資料では地方歳出（計画値）の見出しの下にある式"),
    # 括弧の閉じ忘れ（資料の誤植）
    "Z_GREXPXCPMW": ("Z_GREXPXCPMW=1+(@pch(M_W)+@pch(M_CPIG))/2*S_EXR", "括弧の誤植を修正"),
    "Z_LGEXIR": ("Z_LGEXIR=(Z_LGEXIR(-1)-S_MMIESSL(-1))*(1+@pch(S_MMIPEBL-S_MMIESSL))+S_MMIESSL",
                 "括弧の誤植を修正"),
    "Z_LGEXKG": ("Z_LGEXKG=(Z_LGEXKG(-1)-S_CCIESSL(-1)-SH_KAIGOL(-1))*(1+@pch(S_CCIPEBL-S_CCIESSL-SH_KAIGOL))"
                 "+S_CCIESSL+SH_KAIGOL", "括弧の誤植を修正"),
    # 資料に式も変数リストの記載もない変数
    "Z_GREXPXW": ("Z_GREXPXW=1+@pch(M_W)*Z_GREXPX$",
                  "資料に定義がない。Z_GREXPXA（賃金4割・物価6割）にならい、賃金の伸び率とする。推定"),
    # 法人住民税・事業税の式は Z_TXBREF の伸び率（dlog、@pch）だけを使う。法人税額（Z_TXBG）にすると、国の法人税率を
    # 上げたとき（乗数のケース③）に地方の法人課税まで増える（事業税は所得に課す税なので本来は増えない）。
    # 税率の影響を除いた課税ベース（法人税課税標準）とする。税率が一定なら伸び率は Z_TXBG と同じ
    "Z_TXBREF": ("Z_TXBREF=M_YCVS", "資料に定義がない。法人税の課税標準（M_YCVS）とする。推定"),
}

# 社会保障ブロックで移植する節
SS_SECTIONS = {"年金", "医療", "介護", "その他（雇用保険、社会扶助等）"}

# 医療の制度区分
MED_SYSTEMS = ("HA", "MA", "EH", "NH", "NU")

# 年齢別・要介護度別・サービス別の積み上げ（使わない。SS_COLLAPSED で集約する）。
# 乗数のショックでは人口・加入者数・認定率が変わらず、どの区分の一人当たり費用も同じ改定率で伸びるので、
# 区分ごとの費用を足し上げた給付費は「基準年度の給付費 × 費用の指数」と一致する。
SS_SKIP = {
    "S_MAAINSPBBBBN", "S_MLEINSPBBBBN", "S_MNRINSPN", "S_MAAINSP0064N", "S_MAAINSP6574N", "S_MAAINSPN",
    "S_MAAINSP4064N", "S_MAACOSTBBBBA", "S_MMICOST6064A", "S_MMICOST6569A", "S_MMICOST7074A", "S_MNRCOSTA",
    "S_MAACOSTBBBB", "S_MLECOST6569", "S_MNRCOST", "S_MAABNFT0064", "S_MLEBNFTBBBB", "S_MNRBNFT",
    "S_MAABNF6574B", "S_MLEBNFT", "S_CCIBNFF", "S_CCIBNFH",
    *(f"S_MLECOST{b}A" for b in ("6569", "7074", "7579", "8084", "8589", "9094", "9599", "100O")),
}

# 集約した給付費の式（原典の積み上げの代わり）
SS_COLLAPSED = {
    # 医療: 一人当たり医療費は診療報酬改定率（S_MMIRCCF）で伸びる（原典の S_MaaCOSTbbbbA と同じ）
    "S_MMICOSTI": "S_MMICOSTI=S_MMICOSTI(-1)*(1+S_MMIRCCF*S_EXR+S_MMIRCOFX)",
    **{f"S_M{a}BNFT0064": f"S_M{a}BNFT0064=S_M{a}BNFT0064$*S_MMICOSTI" for a in MED_SYSTEMS},
    **{f"S_M{a}BNF6574B": f"S_M{a}BNF6574B=S_M{a}BNF6574B$*S_MMICOSTI" for a in MED_SYSTEMS},
    "S_MLEBNFT": "S_MLEBNFT=S_MLEBNFT$*S_MMICOSTI",
    # 介護: 一人当たり費用は介護報酬改定率（S_CCIRCCF）で伸びる（原典の S_CCICaaaabbcA と同じ）
    "S_CCICOSTI": "S_CCICOSTI=S_CCICOSTI(-1)*(1+S_CCIRCCF*S_EXR+S_CCIRCOFX)",
    "S_CCIBNFF": "S_CCIBNFF=S_CCIBNFF$*S_CCICOSTI",
    "S_CCIBNFH": "S_CCIBNFH=S_CCIBNFH$*S_CCICOSTI",
}


def socsec_eqs(name: str, section: str, eqs: list[str]) -> list[tuple[str, str]]:
    """社会保障ブロックの項目を (変数名, 式) の並びにする。年齢別の積み上げは除き、制度区分 aa は展開する."""
    if name in SS_SKIP or section not in SS_SECTIONS or "AAAA" in name:
        return []
    src = PENSION_PATCH.get(name, eqs[0] if eqs else "")
    lhs = src.split("=")[0]
    if "S_Maa" in lhs:
        return [(lhs.replace("S_Maa", f"S_M{a}").upper(), src.replace("S_Maa", f"S_M{a}")) for a in MED_SYSTEMS]
    return [(name, src)]

# 年金の式のうち、資料で行が折り返されて読み取れないもの（注記の続きをつなげて復元）
PENSION_PATCH = {
    "S_PPIRCWG": "S_PPIRCWG=S_PPIRCPR*((S_PPIRMNRA(-2)/S_PPICPIC$(-2))/(S_PPIRMNRA(-5)/S_PPICPIC$(-5)))^(1/3)"
                 "*(0.910-S_PEOIPRM$Z(-3)/2)/(0.910-S_PEOIPRM$Z(-4)/2)",
    "S_PBPRCYA": "S_PBPRCYA=@recode(S_PPIRCYB<=1,S_PPIRCYB,@recode(S_PPIRCYB*(S_PBPRCMSZ+S_PBPRCMSY)*S_PBPSSRY(-1)<1,1,"
                 "S_PPIRCYB*(S_PBPRCMSZ+S_PBPRCMSY)*S_PBPSSRY(-1)))",
    "S_PENRCYA": "S_PENRCYA=@recode(S_PPIRCYB<=1,S_PPIRCYB,@recode(S_PPIRCYB*(S_PENRCMSZ+S_PENRCMSY)*S_PENSSRY(-1)<1,1,"
                 "S_PPIRCYB*(S_PENRCMSZ+S_PENRCMSY)*S_PENSSRY(-1)))",
    # 雇用保険料: 「S_OUIIPRM$+M_W+M_LW」は単位の違う量の和になるので、積（賃金×雇用者数）の誤植と判断
    "S_OUIIPRM": "log(S_OUIIPRM)=0.949266*log(S_OUIIPRM$*M_W*M_LW)",
    "S_PBPRCEA": "S_PBPRCEA=@recode(S_PPIRCEB<=1,S_PPIRCEB,@recode(S_PPIRCEB*(S_PBPRCMSZ+S_PBPRCMSY)*S_PBPSSRE(-1)<1,1,"
                 "S_PPIRCEB*(S_PBPRCMSZ+S_PBPRCMSY)*S_PBPSSRE(-1)))",
}

# 使わない指標の式（定義のない変数を参照するもの）
DROP = {"Z_BONAREVT"}

# 国債・地方債の集約版（発行年度別・年限別の積み上げの代わり）
BOND = {
    # 年金特例国債の利払費: 平均調達金利（新発10年債利回りに借換えの速さで近づく）× 前年度末残高
    # （普通国債は bond_port.py で発行年度×年限の積み上げを移植）
    "M_RAVGC": "M_RAVGC=M_RAVGC(-1)+(M_RGB-M_RAVGC(-1))/Z_MATC$",
    "ZP_PINTBON": "ZP_PINTBON=M_RAVGC/100*ZP_GBNML2(-1)",
}

SS: dict = {}  # 簡略版は残っていない（社会保障ブロックはすべて原典の式）

# 社会保障の簡略版で推計式とみなすもの（アドファクターでベースラインに合わせる）
SS_ESTIMATED: set = set()
