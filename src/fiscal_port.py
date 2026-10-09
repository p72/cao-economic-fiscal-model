"""財政ブロックの移植版（spec.build(fiscal="port") で使う）.

- 国の一般会計・公共事業関係特別会計・地方財政計画・交付税特会・地方普通会計・その他指標（249本）は
  方程式リストの式をそのまま使う。資料の誤り・欠落と判断したものだけ PATCH で直す。
- 国債・地方債の発行年度別・年限別の積み上げ（約1,400本）は集約した式（BOND）で置き換える。
- 社会保障ブロック（1,167本）は移植せず、財政・マクロブロックが参照する給付・負担だけを
  簡略な式（SS）で与える。
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
    "Z_TXBREF": ("Z_TXBREF=Z_TXBG", "資料に定義がない。法人税（Z_TXBG）とする。推定"),
}

# 使わない指標の式（定義のない変数を参照するもの）
DROP = {"Z_BONAREVT"}

# 国債・地方債の集約版（発行年度別・年限別の積み上げの代わり）
BOND = {
    # 普通国債残高: 公債金収入で増え、一般会計からの償還費で減る
    "Z_GBNML2": "Z_GBNML2=Z_GBNML2(-1)+Z_BONREV-Z_EXPGBR",
    # 普通国債の利払費: 平均調達金利（新発10年債利回りに借換えの速さで近づく）× 前年度末残高
    "M_RAVGC": "M_RAVGC=M_RAVGC(-1)+(M_RGB-M_RAVGC(-1))/Z_MATC$",
    "B_BRPAY": "B_BRPAY=M_RAVGC/100*Z_GBNML2(-1)",
    "ZP_PINTBON": "ZP_PINTBON=M_RAVGC/100*ZP_GBNML2(-1)",
    # 地方債: 原典の残高式（発行額−元金償還額）を使い、元金償還と利払いを集約する
    "B_ZLGB": "B_ZLGB=B_ZLGB(-1)+Z_LGB-B_ROPT",
    "B_ROPT": "B_ROPT=B_ZLGB(-1)/B_LGBMAT$",
    "M_RAVGL": "M_RAVGL=M_RAVGL(-1)+(M_RGB-M_RAVGL(-1))/Z_MATL$",
    "B_RRT": "B_RRT=M_RAVGL/100*B_ZLGB(-1)",
    # 臨時財政対策債の元利償還（地方財政計画で使う）は地方債全体の一定割合とする
    "Z_ROPRT": "Z_ROPRT=Z_ROPR$*B_ROPT",
    "Z_RRRT": "Z_RRRT=Z_RRR$*B_RRT",
}

# 社会保障の給付・負担の簡略版（35変数）
# 年金は前年の物価（マクロ経済スライドの調整率を差し引く）、医療・介護は報酬改定（前年の賃金と物価の平均）
# と外生の数量要因で伸びる。保険料は賃金総額、公費負担は対応する給付に比例する。
SS = {
    "S_PRICE": "dlog(S_PRICE)=dlog(M_CPIG(-1))-S_SLIDE$",
    "S_MEDP": "dlog(S_MEDP)=0.5*dlog(M_W(-1))+0.5*dlog(M_CPIG(-1))",
    "S_PPIEXPD": "S_PPIEXPD=S_PPIEXPD(-1)*(S_PRICE/S_PRICE(-1))*(1+S_PENQ$)",
    "S_MMIEXPD": "S_MMIEXPD=S_MMIEXPD(-1)*(S_MEDP/S_MEDP(-1))*(1+S_MEDQ$)",
    "S_CCIEXPD": "S_CCIEXPD=S_CCIEXPD(-1)*(S_MEDP/S_MEDP(-1))*(1+S_CAREQ$)",
    # 保険料（家計・雇主）: 賃金総額に比例
    "S_PEOIPRM": "S_PEOIPRM=S_PEOIPRM(-1)*(1+@pch(M_YWIPV))",
    "S_PMCIPRM": "S_PMCIPRM=S_PMCIPRM(-1)*(1+@pch(M_YWIGV))",
    "S_PMLIPRM": "S_PMLIPRM=S_PMLIPRM(-1)*(1+@pch(M_YWIGV))",
    "S_PMPIPRM": "S_PMPIPRM=S_PMPIPRM(-1)*(1+@pch(M_YWIPV))",
    "S_PNPIPRM": "S_PNPIPRM=S_PNPIPRM(-1)*(1+@pch(M_W))",
    "S_PPIERBG": "S_PPIERBG=S_PPIERBG(-1)*(1+@pch(M_YWIGV))",
    "S_PPIERBP": "S_PPIERBP=S_PPIERBP(-1)*(1+@pch(M_YWIPV))",
    "S_MMIERBG": "S_MMIERBG=S_MMIERBG(-1)*(1+@pch(M_YWIGV))",
    "S_MMIERBP": "S_MMIERBP=S_MMIERBP(-1)*(1+@pch(M_YWIPV))",
    "S_CCIERBG": "S_CCIERBG=S_CCIERBG(-1)*(1+@pch(M_YWIGV))",
    "S_CCIERBP": "S_CCIERBP=S_CCIERBP(-1)*(1+@pch(M_YWIPV))",
    "S_MMIIPHH": "S_MMIIPHH=S_MMIIPHH(-1)*(1+@pch(M_YWIV))",
    "S_CCIIPHH": "S_CCIIPHH=S_CCIIPHH(-1)*(1+@pch(M_YWIV))",
    "S_OEIIPRM": "S_OEIIPRM=S_OEIIPRM(-1)*(1+@pch(M_YWIV))",
    # 公費負担: 対応する給付に比例
    "S_PNMPEBC": "S_PNMPEBC=S_PNMPEBC(-1)*(1+@pch(S_PPIEXPD))",
    "S_PMCPEBC": "S_PMCPEBC=S_PMCPEBC(-1)*(1+@pch(S_PPIEXPD))",
    "S_PMLPEBL": "S_PMLPEBL=S_PMLPEBL(-1)*(1+@pch(S_PPIEXPD))",
    "S_PMPPEBC": "S_PMPPEBC=S_PMPPEBC(-1)*(1+@pch(S_PPIEXPD))",
    "S_MMIPEBC": "S_MMIPEBC=S_MMIPEBC(-1)*(1+@pch(S_MMIEXPD))",
    "S_MMIPEBL": "S_MMIPEBL=S_MMIPEBL(-1)*(1+@pch(S_MMIEXPD))",
    "S_MHAPEBC": "S_MHAPEBC=S_MHAPEBC(-1)*(1+@pch(S_MMIEXPD))",
    "S_MNHPEBC": "S_MNHPEBC=S_MNHPEBC(-1)*(1+@pch(S_MMIEXPD))",
    "S_MNUPEBC": "S_MNUPEBC=S_MNUPEBC(-1)*(1+@pch(S_MMIEXPD))",
    "S_MLEDCBC": "S_MLEDCBC=S_MLEDCBC(-1)*(1+@pch(S_MMIEXPD))",
    "S_MMIESSL": "S_MMIESSL=S_MMIESSL(-1)*(1+@pch(S_MMIEXPD))",
    "S_CCIPEBC": "S_CCIPEBC=S_CCIPEBC(-1)*(1+@pch(S_CCIEXPD))",
    "S_CCIPEBL": "S_CCIPEBL=S_CCIPEBL(-1)*(1+@pch(S_CCIEXPD))",
    "S_CCIESSL": "S_CCIESSL=S_CCIESSL(-1)*(1+@pch(S_CCIEXPD))",
    # 雇用保険: 失業等給付は原典の推計式（S_OUIBNFT）、公費負担も原典の式（S_OUIPEBC）
    "S_OUIBNFT": "S_OUIBNFT=571.1055+0.000992*((M_UR*M_W*M_LF)+(M_UR(-1)*M_W(-1)*M_LF(-1)))/2"
                 "+0.127302*(d(M_UR*M_LF)+abs(d(M_UR*M_LF)))/2",
    "S_OUIPEBC": "log(S_OUIPEBC)=0.979428*log(S_OUIPEBC$*S_OUIBNFT)",
    "S_OEIBNFT": "S_OEIBNFT=S_OEIBNFT(-1)*(1+@pch(S_OUIBNFT))",
    # 社会扶助: 原典の推計式（S_OSABNFO）。恩給は外生の減少率
    "S_OSABNFO": "@pch(S_OSABNFO/S_OSACPIG$)=-0.861729*(@pch(M_GDP)+@pch(M_GDP(-1)))/2"
                 "+1.949649*@movav(@pch(P_POP60OV),5)",
    "S_OSACPIG$": "S_OSACPIG$=M_CPIG(-1)",
    "S_OSABNFP": "S_OSABNFP=S_OSABNFP(-1)*(1+S_OSABNFPG$)",
    # 年金積立金の運用収入（インカムゲイン）: 利付資産 × 平均利回り。平均利回りは国債と同じく、
    # 借換え・新規投資の分だけ市場金利（長期金利＋上乗せ）にゆっくり近づく
    "S_PPIRAVG": "S_PPIRAVG=S_PPIRAVG(-1)+(M_RGB+S_PPISPR$-S_PPIRAVG(-1))/Z_MATC$",
    "S_PPIING": "S_PPIING=S_PPIBOND*S_PPIRAVG/100",
    "S_PPIBOND": "S_PPIBOND=S_PPIBOND(-1)*(1+@pch(M_GDPV))",
}

# 社会保障の簡略版で推計式とみなすもの（アドファクターでベースラインに合わせる）
SS_ESTIMATED = {"S_OUIBNFT", "S_OUIPEBC", "S_OSABNFO"}
