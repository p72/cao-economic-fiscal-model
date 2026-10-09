"""国債ブロック（普通国債）と地方債の移植版: 発行年度×年限（経過年数）の積み上げ.

方程式リスト「国債」節のひな形（B_BR07Q01 など、令和7年度～令和17年度発行）を、2026年度～2035年度発行分に
展開する。既発債（2025年度末に残っている銘柄）は、原典と同じく年度別の残高・償還額・利払費を外生で与える
（jgb_data.schedule。変数名は B_EXBOUTqq、B_EXDBqq、B_EXPBqq）。原典の残高・償還額・利払費の合計式
（B_BOUT01 など）は資料上は令和7年度以降の発行分だけを並べているが、既発債も変数リストにあり、
普通国債残高（Z_GBNML2 = B_BOUT）に含まれるので、合計に既発債を加える。

発行年度のダミー（原典の M_D25 など、その年度だけ1）は B_DUMyyyy とする。
"""
from __future__ import annotations

TENORS = ("01", "02", "03", "05", "10", "20", "30", "40")
VINTAGES = tuple(range(2026, 2036))
LAST_DUMMY = 2045          # ダミー変数を用意する最後の年度（これより後に満期が来る債券は満期の項を省く）


def dum(y: int) -> str:
    return f"B_DUM{y}"


def rtag(v: int) -> str:
    """発行年度の記号（令和）: 2026年度 → R08."""
    return f"R{v - 2018:02d}"


def vintage_eqs() -> dict[str, str]:
    """発行年度×年限ごとの残高・償還額・金利・利払費（原典のひな形）."""
    eqs = {}
    for v in VINTAGES:
        r = rtag(v)
        for q in TENORS:
            n = f"{r}Q{q}"
            mat = v + int(q)
            eqs[f"B_B{n}"] = f"B_B{n}=(B_DB{n}+B_B{n}(-1))*(1-{dum(v)})+B_DBNEW{q}*{dum(v)}"
            if mat <= LAST_DUMMY:
                eqs[f"B_DB{n}"] = f"B_DB{n}=-B_B{n}(-1)*{dum(mat)}+(1-{dum(mat)})*B_RDBNEW*B_B{n}(-1)"
            else:
                eqs[f"B_DB{n}"] = f"B_DB{n}=B_RDBNEW*B_B{n}(-1)"
            if q == "01":
                eqs[f"B_RB{n}"] = f"B_RB{n}=B_YCSY01*{dum(v)}"
                eqs[f"B_PB{n}"] = f"B_PB{n}=B_B{n}*B_RB{n}/100/(1+B_RB{n}/100)"
            else:
                rate = f"B_YCCR{q}" if q in ("02", "03", "05", "10") else f"(B_IRLT+B_RP{q}Y)"
                eqs[f"B_RB{n}"] = f"B_RB{n}={rate}*{dum(v)}+B_RB{n}(-1)*(1-{dum(v)})"
                eqs[f"B_PB{n}"] = f"B_PB{n}=B_B{n}*B_RB{n}/100"
    return eqs


def sum_eqs() -> dict[str, str]:
    """年限別の残高・償還額・利払費（割引料）の合計（既発債を含む）."""
    eqs = {}
    for q in TENORS:
        ns = [f"{rtag(v)}Q{q}" for v in VINTAGES]
        eqs[f"B_BOUT{q}"] = f"B_BOUT{q}=" + "+".join(f"B_B{n}" for n in ns) + f"+B_EXBOUT{q}"
        eqs[f"B_DB{q}"] = f"B_DB{q}=" + "+".join(f"B_DB{n}" for n in ns) + f"+B_EXDB{q}"
        eqs[f"B_PB{q}"] = f"B_PB{q}=" + "+".join(f"B_PB{n}" for n in ns) + f"+B_EXPB{q}"
    return eqs


# 方程式リストの「国債」節のうち、ひな形と合計以外でそのまま使う式（名前）
COPY = {
    "B_BOUT", "B_DBALL", "B_BRPAY", "B_RP20Y", "B_RP30Y", "B_RP40Y", "B_IRST", "B_IRLT", "B_ICST", "B_ICLT",
    "B_YCSY01", "B_YCSY02", "B_YCSY05", "B_YCSY10", "B_YCCR02", "B_YCCR03", "B_YCCR05", "B_YCCR10", "B_YCCR20",
    "B_YCCR30", "B_YCCR40", "B_IPR02", "B_IPR05", "B_IPR10", "B_DBNEW", "B_DBNEW01", "B_DBNEW02", "B_DBNEW03",
    "B_DBNEW05", "B_DBNEW10", "B_DBNEW20", "B_DBNEW30", "B_DBNEW40", "B_DDBNEW", "B_RDBNEW", "B_WB01", "Z_GBNML2",
    "Z_GOVDFC",
}


def all_eqs(items: list[dict]) -> dict[str, str]:
    """国債ブロックの全式（items は equations.json の項目）."""
    eqs = {}
    for it in items:
        if it["section"] == "国債" and it["name"].upper() in COPY:
            eqs[it["name"].upper()] = it["eqs"][0]
    missing = COPY - set(eqs)
    if missing:
        raise ValueError(f"国債節に見つからない式: {sorted(missing)}")
    eqs.update(vintage_eqs())
    eqs.update(sum_eqs())
    eqs.update(lgb_eqs())
    return eqs


def endogenous() -> set[str]:
    """国債・地方債ブロックの内生変数（標準ケースで前向きに解く対象）."""
    return set(vintage_eqs()) | set(sum_eqs()) | COPY | lgb_endogenous()


def exog_series(scale: float, first: int, last: int) -> dict[str, dict[int, float]]:
    """既発債のスケジュールと発行年度ダミー（外生変数の年度別の値）.

    scale: 既発債の残高を、普通国債残高（Z_GBNML2、年金特例国債・復興債などを除く）に合わせる倍率。
    2024年度以前は2025年度の値を使う（標準ケースでは値が固定され、アドファクターで合う）。
    """
    import jgb_data
    s = jgb_data.schedule(2025, max(last, 2075))
    out = {}
    for q in TENORS:
        for key, name in (("stock", "B_EXBOUT"), ("red", "B_EXDB"), ("int", "B_EXPB")):
            col = s[q][key]
            out[f"{name}{q}"] = {t: scale * col[max(t, 2025)] for t in range(first, last + 1)}
    for y in range(min(VINTAGES), LAST_DUMMY + 1):
        out[dum(y)] = {t: 1.0 if t == y else 0.0 for t in range(first, last + 1)}
    return out


def params() -> dict[str, float]:
    """発行の年限構成（2025年度の入札の落札額。1年債は短期証券の2025年度末残高で代用）と利回りの差."""
    import jgb_data
    iss = jgb_data.issuance_fy2025()
    amt = dict(iss["amount"])
    amt["01"] = sum(jgb_data.schedule(2025, 2025)["01"]["stock"].values()) * 10   # 億円
    amt["03"] = 0.0                                                                  # 3年債は発行していない
    tot = sum(amt.values())
    p = {f"B_RBHQ{q}": amt[q] / tot for q in TENORS}
    c = iss["coupon"]
    # 超長期債の上乗せ（20・30・40年債の表面利率 − 10年債）。B_RPqqYX / B_LSSPRDX ×（長期−短期）の形なので、
    # 基準年度の長短金利差を B_LSSPRDX とおけば、上乗せが基準年度の値になる
    for q in ("20", "30", "40"):
        p[f"B_RP{q}YX"] = c[q] - c["10"]
    p["B_IRSTER"] = p["B_IRLTER"] = 0.0
    p["B_DBNEWER"] = 0.0
    return p


# ---------- 地方債 ----------
# 方程式リスト「地方債」節: 発行年度からの経過年数 k（0～20）ごとに、元本残高（B_LRZk）・元金償還（B_ROPk）・
# 利払費（B_RRk）を積み上げる。20年元利均等償還（据置2年、3年目は半分）で、利率は発行時の財政融資資金貸出利回り。
# 原典は令和7年度（M_D25C）から積み上げるが、ここでは2026年度発行分から積み上げ、2025年度末までの既発債の
# 元金償還（B_ROP）・利払費（B_DRP）は外生で与える。臨時財政対策債（Z_LRZRk など）も同じ形。
LGB_START = 2026
AGES = range(0, 21)


def cdum(y: int) -> str:
    """その年度以降1のダミー（原典の M_D25C など）."""
    return f"B_DUMC{y}"


def lgb_eqs() -> dict[str, str]:
    eqs = {}
    annuity = "(B_RAGBZ*(1+B_RAGBZ)^(20-2))/((1+B_RAGBZ)^(20-2)-1)"
    for stock, rop, rr, rip, iss in (("B_LRZ", "B_ROP", "B_RR", "B_RIP", "Z_LGB"),
                                     ("Z_LRZR", "Z_ROPR", "Z_RRR", "Z_RIPR", "(ZP_LGBR1+ZP_LGBR2)")):
        eqs[rip] = f"{rip}={iss}*{annuity}*{cdum(LGB_START)}"
        for k in AGES:
            c = cdum(LGB_START + k)
            if k == 0:
                eqs[f"{stock}00"] = f"{stock}00=({iss}-{rop}00)*{c}"
            else:
                eqs[f"{stock}{k:02d}"] = f"{stock}{k:02d}=({stock}{k - 1:02d}(-1)-{rop}{k:02d})*{c}"
                eqs[f"{rr}{k:02d}"] = f"{rr}{k:02d}={stock}{k - 1:02d}(-1)*B_RAGBZ(-{k})*{c}"
            if k <= 2:
                eqs[f"{rop}{k:02d}"] = f"{rop}{k:02d}=0*B_RAGBZ"
            elif k == 3:
                eqs[f"{rop}03"] = f"{rop}03=0.5*({rip}(-3)-{rr}03)*{c}"
            else:
                eqs[f"{rop}{k:02d}"] = f"{rop}{k:02d}=({rip}(-{k})-{rr}{k:02d})*{c}"
    roppart = "+".join(f"B_ROP{k:02d}" for k in AGES)
    rrpart = "+".join(f"B_RR{k:02d}" for k in AGES if k > 0)
    eqs["B_ROPT"] = f"B_ROPT=B_ROP+{roppart}"
    eqs["B_RRT"] = f"B_RRT=@recode((B_DRP+{rrpart})>=0,(B_DRP+{rrpart}),0)"
    eqs["Z_ROPRT"] = "Z_ROPRT=Z_ROPR+(" + "+".join(f"Z_ROPR{k:02d}" for k in AGES) + ")"
    # Z_RRRT（臨時財政対策債の利払費の合計）は財政ブロックに原典の式がある
    eqs["B_RAGBZ"] = "B_RAGBZ=(M_RGB+B_RISKPRM)/100"
    eqs["B_ZLGB"] = "B_ZLGB=B_ZLGB(-1)+Z_LGB-B_ROPT"
    return eqs


LGB_MAT = 14.0        # 既発の地方債の平均償還年数（2024年度の公債費の元金償還に合うように推定）
ROPR_SHARE = 0.35     # 既発債の元金償還のうち臨時財政対策債の割合（推定）


def lgb_exog_series(stock0: float, rate0: float, first: int, last: int,
                    mat: float = LGB_MAT, rop_share: float = ROPR_SHARE) -> dict:
    """2025年度末の既発の地方債の元金償還（B_ROP）・利払費（B_DRP）と、年度以降ダミー.

    既発債の年度別の償還予定は公表の統計がないので、2025年度末残高 stock0 を平均償還年数 mat で
    毎年 1/mat ずつ償還し、利払費は前年度末残高 × 平均利率 rate0（基準年度の利払費 / 残高）とする（推定）。
    臨時財政対策債の既発分の元金償還（Z_ROPR）は B_ROP の rop_share 倍（Z_ROPRT − Z_ROPR だけが使われるので
    結果には効かない）。
    """
    out = {"B_ROP": {}, "B_DRP": {}, "Z_ROPR": {}}
    s = stock0
    for t in range(first, last + 1):
        if t <= 2025:
            rop, drp = stock0 / mat, stock0 * rate0
        else:
            rop, drp = s / mat, s * rate0
            s -= rop
        out["B_ROP"][t], out["B_DRP"][t], out["Z_ROPR"][t] = rop, drp, rop_share * rop
    for y in range(LGB_START, LGB_START + max(AGES) + 1):
        out[cdum(y)] = {t: 1.0 if t >= y else 0.0 for t in range(first, last + 1)}
    return out


def lgb_endogenous() -> set[str]:
    return set(lgb_eqs()) | {"Z_RRRT"}
