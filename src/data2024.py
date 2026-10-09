"""2024年度の値をモデルの変数に対応づける（ベースラインの出発点）.

出典:
- 国民経済計算 2024年度年次推計（2020年基準）: ffm1n/rn（GDP支出側）、ffm2（分配）、i5（家計）、
  s6（一般政府の部門別勘定）、s16（固定資本減耗）、s19（海外勘定）、ss3（一般政府の資産・負債残高）、
  ss4n/rn（固定資本ストック）、ss5（対外資産・負債残高）
- 労働力調査（年度平均）: 年齢階級・男女別の15歳以上人口、労働力人口、就業者、完全失業者、雇用者

統計から直接取れない値は ASSUMED に置き、出典か根拠を書く。名目は10億円、人数は万人、
賃金 M_W は10万円（原典の変数リストの単位）。政府の支払いは負値（原典の符号）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import sna_read as S
from spec import AGES, AGES_LW, SEXES

ROOT = Path(__file__).resolve().parents[1]

# 統計から直接取れない値（仮置き）。根拠を併記する
ASSUMED = {
    # 金融・海外（2024年度平均の概数。日本銀行・財務省・米FRBの公表値の水準に合わせた仮置き）
    "M_RCO": 0.23,       # 無担保コールO/N物（年度平均、%）
    "M_RGB": 1.10,       # 新発10年国債利回り（年度平均、%）
    "MUS_RGB": 4.2,      # 米10年国債利回り（%）
    "M_FXS": 152.6,      # 円/ドル（年度平均）
    "M_POILD": 78.0,     # 原油価格（ドバイ、ドル/バレル）
    "M_CPIG": 108.7,     # 消費者物価指数（総合、2020年=100）
    "M_CGPI": 123.0,     # 国内企業物価指数（2020年=100）
    "M_VSHARE": 950000.0,  # 株式時価総額（10億円、年度末の概数）
    "M_M2CD": 1250000.0,   # マネーストック M2（10億円、平均残高の概数）
    # 公債等残高（10億円、年度末の概数）: 普通国債、地方債、交付税特会借入金
    "Z_GBNML": 1105000.0,
    "B_ZLGB": 140000.0,
    "Z_SPB": 27500.0,
    "M_YWGV": 27500.0,   # 一般政府の雇用者報酬（概数）
    "P_POP": 12380.0,    # 総人口（万人、2024年10月1日現在の概数）
    # モデルのパラメータ的な外生変数
    "M_EQLBSH": 0.62,    # 潜在労働分配率
    "M_EQCU": 1.0,       # 潜在稼働率
    "M_MPVDP": 0.85,     # 減価償却の現在価値
    "M_PSTAR": 2.0, "M_PSTARBOJ": 2.0,  # 期待インフレ率、均衡期待インフレ率（%）
    "MWE_GGDP": 3.0,     # 世界経済成長率（%）
    "Z_RTCIV": 0.10, "Z_RTCIV2": 0.08, "Z_RTCIV2$": 0.0,  # 消費税率（軽減税率は使わない）
    "M_VATAIG$": 1.0,    # 公共投資の課税標準率
    "Z_MATC$": 8.0, "Z_MATL$": 10.0,  # 借換えで平均調達金利が市場金利に近づく速さ（年）
    "M_YIGVCRLR": 400.0, "M_YIGVLRLR": 50.0,  # 国債・地方債以外の利払費（概数）
    "M_FAGCF": 180000.0,  # 国の対外資産（外貨準備の大部分）
    # 地方の収支の変化のうち地方債の増減に回る割合。公表乗数の公債等残高比に最もよく合う値
    # （0, 0.25, 0.5, 0.75 で比べ、二乗平均のずれが最小）
    "Z_LGBTH$": 0.25,
    # 法人課税の増減のうち翌年度の納付になる割合（中間納付で約半分を当年度に納める）。
    # 0, 0.5, 1 で比べ、公表乗数の公債等残高比に最もよく合う
    "Z_TYCVLAG$": 0.5,
}


def build() -> dict[str, float]:
    d: dict[str, float] = dict(ASSUMED)
    fy = S.fy

    # --- GDP 支出側（名目・実質）---
    items = {
        "M_CP": "１．民間最終消費支出", "M_IHP": "（ａ）住宅", "M_IFP": "（ｂ）企業設備",
        "M_IN": "（２）在庫変動", "M_CG": "２．政府最終消費支出", "M_IG": "ｂ．公的",
        "M_XGS": "（１）財貨・サービスの輸出", "M_MGS": "（２）（控除）財貨・サービスの輸入",
        "M_GDP": "５．国内総生産",
    }
    for v, lab in items.items():
        d[v + "V"] = fy("ffm1n", lab)
        d[v] = fy("ffm1rn", lab)
    d["M_INV"] = fy("ffm1n", "（２）在庫変動")
    d["M_IN"] = d["M_INV"] / 1.1  # 在庫変動はほぼゼロなのでデフレーターは他の価格並みと置く
    d["M_TRIVREC"] = fy("ffm1n", "海外からの所得")
    d["M_TRIVPAY"] = fy("ffm1n", "（控除）海外に対する所得")
    for p, q in [("M_PCP", "M_CP"), ("M_PIFP", "M_IFP"), ("M_PIHP", "M_IHP"), ("M_PCG", "M_CG"),
                 ("M_PIG", "M_IG"), ("M_PXGS", "M_XGS"), ("M_PMGS", "M_MGS"), ("M_PGDP", "M_GDP")]:
        d[p] = d[q + "V"] / d[q]
    d["M_GDPP"] = d["M_GDP"]  # GDPギャップ0
    d["M_BCV"] = -fy("s19", "５．経常対外収支")

    # --- 分配 ---
    d["M_YWV"] = fy("ffm2", "１．雇用者報酬")
    d["M_YWIV"] = fy("ffm2", "（１）賃金・俸給")
    d["M_YSLIV"] = fy("ffm2", "ａ．雇主の現実社会負担")
    d["M_YOLIV"] = fy("ffm2", "ｂ．雇主の帰属社会負担")
    d["M_YIV"] = fy("ffm2", "２．財産所得（非企業部門）")
    d["M_YIGV"] = fy("ffm2", "（１）一般政府")
    d["M_YCVSELF"] = fy("ffm2", "（３）個人企業")
    d["M_YCVPOST"] = fy("ffm2", "３．企業所得")
    d["M_NIV"] = fy("ffm2", "４．国民所得（要素費用表示）")
    d["M_YCGIV"] = fy("ffm2", "（２）公的企業") + d["M_YCVSELF"]
    # 配当受取（非企業部門）= 一般政府・家計・対家計民間非営利団体の法人企業の分配所得
    d["M_YCVDIV"] = fy("ffm2", "ｂ．法人企業の分配所得（受取）") + fy("ffm2", "ｂ．配当（受取）") \
        + fy("ffm2", "ｂ．配当（受取）", nth=1)
    d["M_YIVR"] = d["M_YIV"] - d["M_YCVDIV"]
    d["M_YIVRBASE"] = d["M_YIVR"]
    d["M_YCVPRE"] = d["M_YCVPOST"] + d["M_YCVDIV"]
    d["M_YCVS"] = d["M_YCVPRE"] - d["M_YCGIV"]  # 法人税課税標準（推計式の定数項から比率≒1）
    d["Z_YTCSV"] = 0.0

    # --- 家計 ---
    d["M_YDV"] = fy("i5", "2.4可処分所得（純）", sheet="年度（２）")
    d["Z_TYPV"] = fy("i5", "2.1所得・富等に課される経常税", sheet="年度（２）")

    # --- 一般政府（部門別）---
    sec = lambda lab, nth=0: S.sector("s6", lab, nth)  # noqa: E731
    C, L, F = "中央政府", "地方政府", "社会保障基金"
    vat = sec("ａ．付加価値型税")
    prod = sec("１．生産・輸入品に課される税")
    cur = sec("８．所得・富等に課される経常税")
    d["Z_TCIVC"], d["Z_TCIVL"] = vat[C], vat[L]
    d["Z_TCIV"] = d["Z_TCIVB"] = vat[C] + vat[L]
    d["Z_TCIVC$"] = vat[C] / d["Z_TCIV"]
    d["Z_OITAXVC"], d["Z_OITAXVL"] = prod[C] - vat[C], prod[L] - vat[L]
    d["M_TAXC"], d["M_TAXL"] = prod[C] + cur[C], prod[L] + cur[L]
    oth = sec("（２）その他の経常税")
    d["Z_OTAXC"], d["Z_OTAXL"] = oth[C], oth[L]
    inc = sec("（１）所得に課される税")
    # 家計の所得課税のうち地方（個人住民税）は、地方の所得課税の大半を占めると置く（概数）
    d["Z_TYPVL"] = 13600.0
    d["Z_TYPVC"] = d["Z_TYPV"] - d["Z_TYPVL"]
    d["Z_TYCVC"] = inc[C] + oth[C] - d["Z_TYPVC"] - d["Z_OTAXC"]
    d["Z_TYCVL"] = inc[L] - d["Z_TYPVL"]
    d["Z_RTYCVC$"] = d["Z_TYCVC"] / d["M_YCVS"]
    d["Z_RTYCVL$"] = d["Z_TYCVL"] / d["M_YCVS"]
    d["Z_TYCVX"] = d["Z_TYPVX"] = 0.0
    d["Z_TXOH"] = sec("うち資本税")[C]

    sub = sec("２．（控除）補助金")
    d["M_SUBVC"], d["M_SUBVL"] = -sub[C], -sub[L]
    pr, pp = sec("３．財産所得（受取）"), sec("５．財産所得（支払）")
    ir, ip = sec("（１）利子"), sec("（１）利子", 1)
    ir_pre, ip_pre = sec("(参考)受取利子"), sec("(参考)支払利子")
    for s, k in ((C, "C"), (L, "L"), (F, "F")):
        d[f"M_YIGV{k}"] = pr[s] - pp[s]
    # 利子の受取・支払（FISIM調整前）と、FISIM調整分・その他の財産所得
    d["M_YIGVCRAWF"], d["M_YIGVLRAWF"], d["M_YIGVFRAWF"] = ir_pre[C], ir_pre[L], ir_pre[F]
    d["M_FCRAR"], d["M_FLRAR"], d["M_FFRAR"] = ir[C] - ir_pre[C], ir[L] - ir_pre[L], ir[F] - ir_pre[F]
    d["M_YIGVCRLWF"], d["M_YIGVLRLWF"] = ip_pre[C], ip_pre[L]
    d["M_YIGVFRLWF"] = ip_pre[F]
    d["M_FCRLR"], d["M_FLRLR"], d["M_FFRLR"] = ip_pre[C] - ip[C], ip_pre[L] - ip[L], ip_pre[F] - ip[F]
    d["M_YIGVCAER"] = pr[C] - ir[C]
    d["M_YIGVLAER"] = pr[L] - ir[L]
    d["M_YIGVFAER"] = pr[F] - ir[F]
    d["M_YIGVCLER"] = pp[C] - ip[C]
    d["M_YIGVLLER"] = pp[L] - ip[L]
    d["M_YIGVFLER"] = pp[F] - ip[F]

    css = sec("９．社会負担（受取）")
    d["M_CSSVC"], d["M_CSSVL"], d["M_CSSVF"] = css[C], css[L], css[F]
    d["M_CSSVG"] = css[C] + css[L]
    bss = sec("１２．現物社会移転以外の社会給付")
    d["M_BSSVC"], d["M_BSSVL"], d["M_BSSVF"] = -bss[C], -bss[L], -bss[F]
    d["S_PENB"] = sec("（１）現金による社会保障給付")[F]
    d["M_BSSVFER"] = d["M_BSSVF"] + d["S_PENB"]

    trr, trp = sec("１０．その他の経常移転（受取）"), sec("１３．その他の経常移転（支払）")
    tgr, tgp = sec("（２）一般政府内の経常移転"), sec("（２）一般政府内の経常移転", 1)
    for s, k in ((C, "C"), (L, "L"), (F, "F")):
        d[f"M_TRG{k}"] = tgr[s] - tgp[s]
        d[f"M_TRP{k}"] = (trr[s] - tgr[s]) - (trp[s] - tgp[s])
    d["M_TRG"] = d["M_TRGC"] + d["M_TRGL"] + d["M_TRGF"]

    ind, col = sec("（１）現物社会移転（個別消費支出）"), sec("（２）現実最終消費（集合消費支出）")
    d["M_CGVCC"], d["M_CGVIC"] = -col[C], -ind[C]
    d["M_CGVCL"], d["M_CGVIL"] = -col[L], -ind[L]
    d["M_CGVCF"], d["M_CGVIF"] = -col[F], -ind[F]
    d["M_CGVIFE"] = sec("ｂ．現物社会移転（市場産出の購入）")["合計"]
    for k in ("CC", "IC", "CL", "IL", "IF"):
        d[f"M_CGR{k}"] = -d[f"M_CGV{k}"] / d["M_PCG"]

    ctr, ctp = sec("１９．資本移転（受取）"), sec("２０．（控除）資本移転（支払）")
    cgr, cgp = sec("（１）他の一般政府部門からのもの"), sec("（１）他の一般政府部門に対するもの")
    d["M_CTRGC"] = cgr[C] - cgp[C]
    d["M_CTRGL"] = cgr[L] - cgp[L]
    d["M_CTRPC"] = (ctr[C] - ctp[C]) - d["M_CTRGC"] - d["Z_TXOH"]
    d["M_CTRPL"] = (ctr[L] - ctp[L]) - d["M_CTRGL"]
    d["M_CTRF"] = ctr[F] - ctp[F]

    gfcf, dep, inv, lnd = (sec("２２．総固定資本形成"), sec("２３．（控除）固定資本減耗"),
                           sec("２４．在庫変動"), sec("２５．土地の購入"))
    d["Z_IG1"], d["Z_IG3"], d["Z_IG5"] = gfcf[C], gfcf[L], gfcf[F]
    d["Z_IG2"] = d["M_IGV"] - gfcf["合計"]  # 公的企業
    for z, k in (("Z_IG1", "1"), ("Z_IG2", "2"), ("Z_IG3", "3"), ("Z_IG5", "5")):
        d[f"M_IGR{k}"] = d[z] / d["M_PIG"]
    for s, k in ((C, "C"), (L, "L"), (F, "F")):
        d[f"M_DEP{k}"] = dep[s]
        d[f"M_INV{k}"] = -inv[s]
        d[f"M_PLN{k}"] = -lnd[s]
    d["MR_BGCV"] = d["MX_BGCV"] = d["MR_BGLV"] = 0.0

    # 一般政府の資産・負債残高（暦年末）
    fa = S.sector("ss3", "２．金融資産")
    fl = S.sector("ss3", "３．負債")
    ofl = S.sector("ss3", "（８）その他の負債")
    d["M_FAGC"], d["M_FAGL"], d["M_FAGF"] = fa[C], fa[L], fa[F]
    d["M_FAGCD"] = d["M_FAGC"] - d["M_FAGCF"]
    d["M_FAGLF"], d["M_FAGLD"] = 0.0, d["M_FAGL"]
    d["M_FAGCXX"] = 0.0
    d["M_FLGCF"], d["M_FLGCOH"] = 0.0, ofl[C]
    d["M_FLGCD"] = fl[C] - ofl[C]
    d["M_FLGC"] = fl[C]
    d["M_FLGLF"], d["M_FLGLD"], d["M_FLGL"] = 0.0, fl[L], fl[L]
    d["M_FLGF"] = fl[F]
    d["M_BRWC"] = S.sector("ss3", "（３）借入")[C]
    d["M_BRWL"] = S.sector("ss3", "（３）借入")[L]
    d["Z_LGFND"] = 0.0
    d["Z_DEBTOUT"] = d["Z_GBNML"] + d["B_ZLGB"] + d["Z_SPB"]
    # 平均調達金利 = (利払費 − その他の利払) / 前年度末残高（前年度末は名目成長率で割り戻す）
    d["M_RAVGC"] = (d["M_YIGVCRLWF"] - d["M_YIGVCRLR"]) / (d["Z_GBNML"] / 1.025) * 100
    d["M_RAVGL"] = (d["M_YIGVLRLWF"] - d["M_YIGVLRLR"]) / (d["B_ZLGB"] / 1.025) * 100

    # --- 固定資本ストック（実質、暦年末）と固定資本減耗 ---
    k = S.stock_matrix("ss4rn")
    kn = S.stock_matrix("ss4n")
    tot, house = "固定資産合計", "１．住宅"
    pub_ent = ["制度部門別/非金融法人企業/公的", "制度部門別/金融機関/公的"]
    d["M_KFP"] = (k.loc[tot, "（再掲）/民間部門"] - k.loc[house, "（再掲）/民間部門"]
                  + sum(k.loc[tot, c] - k.loc[house, c] for c in pub_ent))
    d["M_KHP"] = k.loc[house, "（再掲）/民間部門"]
    cfc_bus = fy("s16", "ｂ．企業設備") + fy("s16", "ｂ．企業設備", 1) + fy("s16", "ｂ．企業設備", 2)
    cfc_house = fy("s16", "ａ．住宅") + fy("s16", "ａ．住宅", 1)
    d["M_KFPCFC"] = cfc_bus / d["M_PIFP"]
    d["M_KHPCFC"] = cfc_house / d["M_PIHP"]
    d["M_KFPCFC$"] = d["M_KFPCFC"] / (d["M_KFP"] / 1.005)
    d["M_KHPCFC$"] = d["M_KHPCFC"] / (d["M_KHP"] / 1.005)
    d["M_KFPSTAR"] = d["M_EQKFP"] = d["M_KFP"]
    kg = kn.loc[tot, "制度部門別/一般政府"]
    dsum = d["M_DEPC"] + d["M_DEPL"] + d["M_DEPF"]
    for s in "CLF":
        d[f"M_KGV{s}"] = kg * d[f"M_DEP{s}"] / dsum

    # --- 対外資産・負債（暦年末、ドル建て）---
    fa_w, fl_w = fy("ss5", "対外資産"), fy("ss5", "対外負債")
    d["M_LAA$"] = fl_w / fa_w
    d["M_SBCV"] = (fa_w - fl_w) / d["M_FXS"]
    d["M_SBCVER"] = 0.0
    d["M_BCVER"] = d["M_BCV"] - (d["M_XGSV"] - d["M_MGSV"] + d["M_TRIVREC"] - d["M_TRIVPAY"])
    d["M_CTRW"] = 0.0

    # --- 労働（労働力調査、年度平均）---
    d.update(labor(2024))
    d["M_W"] = d["M_YWIV"] / d["M_LW"]
    d["M_YWIGV"] = d["M_YWGV"] * d["M_YWIV"] / d["M_YWV"]

    # 可処分所得の残余項目：家計可処分所得（統計）と原典の定義式の差
    ypv = d["M_YWV"] + (d["M_YIV"] - d["M_YIGV"]) + d["M_YCVSELF"]
    bssv = d["M_BSSVC"] + d["M_BSSVL"] + d["M_BSSVF"]
    cssv = d["M_CSSVC"] + d["M_CSSVL"] + d["M_CSSVF"]
    d["M_YDVOH"] = d["M_YDV"] - (ypv - bssv - d["Z_TYPV"] - cssv)
    d["M_YDVOH$"] = d["M_YDVOH"] / d["M_NIV"]

    # --- 比率の外生変数（今の値で固定）---
    d["M_INV$"] = d["M_INV"] / d["M_GDPV"]
    d["M_YCGIV$"] = d["M_YCGIV"] / d["M_YCVPOST"]
    d["M_YCVDIV$"] = d["M_YCVDIV"] / d["M_YCVPRE"]
    d["M_YSLIV$"] = d["M_YSLIV"] / d["M_CSSVF"]
    d["M_YSLIGV$"] = d["M_YSLIPV$"] = d["M_YSLIV"] / d["M_YWIV"]
    d["M_YOLIGV$"] = d["M_YOLIPV$"] = d["M_YOLIV"] / d["M_YWIV"]
    d["M_PLNH"] = 0.0
    d["M_SPREV"] = 0.0
    d["M_IHPADJ"] = 0.0
    d["M_CSSVFADJCH"] = 0.0
    d["M_ZEIGAIFCH"] = d["M_ZEIGAILCH"] = 0.0
    d["Z_ADJTCIVC"] = d["Z_ADJTCIVL"] = 0.0
    d["M_DPOPC"] = 0.0
    d["DM_VATACP$"] = 0.0
    d["S_PENQ$"] = d["S_SLIDE$"] = 0.0
    d["M_TFP"] = 0.0  # 生産関数のアドファクターで水準を合わせる
    d["MWE_WPI"] = d["MUS_WPI"] = 1.0
    d["M_CGPIA"] = d["M_CGPI"] / (1 + d["Z_RTCIV"])
    vatacg = (d["M_CGV"] - d["M_YWGV"] - d["M_CGVIFE"] - dsum
              - (d["M_FCRAR"] + d["M_FLRAR"] + d["M_FFRAR"] + d["M_FCRLR"] + d["M_FLRLR"] + d["M_FFRLR"])) / d["M_CGV"]
    d["M_VATACG$"] = vatacg
    base = d["Z_TCIV"] * (1 + d["Z_RTCIV"]) / d["Z_RTCIV"]
    d["M_VATACP$"] = (base - d["M_IHPV"] - vatacg * d["M_CGV"] - d["M_VATAIG$"] * d["M_IGV"]) / d["M_CPV"]
    tax_share = d["Z_RTCIV"] * d["M_VATACP$"] / (1 + d["Z_RTCIV"])
    d["M_CPIGA"] = d["M_CPIG"] * (1 - tax_share)
    d["M_PCPA"] = d["M_PCP"] * (1 - tax_share)
    return d


def labor(fy: int) -> dict[str, float]:
    df = pd.read_csv(ROOT / "data" / "raw" / "lfs_fy.csv")
    df = df[df["fy"] == fy]
    age_code = {"15～19歳": "1519", "20～24歳": "2024", "25～29歳": "2529", "30～34歳": "3034",
                "35～39歳": "3539", "40～44歳": "4044", "45～49歳": "4549", "50～54歳": "5054",
                "55～59歳": "5559", "60～64歳": "6064", "65～69歳": "6569", "70歳以上": "70OV",
                "15歳以上": "TOT"}
    st = {"15歳以上人口": "POP", "労働力人口": "LF", "就業者": "LE", "完全失業者": "UL", "雇用者": "LW"}
    v = {(st[r.status], age_code[r.age], r.sex): r.value for r in df.itertuples() if r.status in st}
    d: dict[str, float] = {}
    for s in SEXES:
        for a in AGES:
            d[f"P_POP{a}{s}"] = v[("POP", a, s)]
            d[f"P_LF{a}{s}"] = v[("LF", a, s)]
            d[f"P_UL{a}{s}"] = v[("UL", a, s)]
            d[f"P_LE{a}{s}"] = v[("LF", a, s)] - v[("UL", a, s)]
            d[f"P_RLF{a}{s}"] = v[("LF", a, s)] / v[("POP", a, s)]
        for a in AGES_LW:
            d[f"P_LW{a}{s}"] = v[("LW", a, s)]
            d[f"P_RLW{a}{s}"] = v[("LW", a, s)] / d[f"P_LE{a}{s}"]
        lw65 = v[("LW", "6569", s)] + v[("LW", "70OV", s)]
        d[f"P_LW65OV{s}"] = lw65
        d[f"P_RLW65OV{s}"] = lw65 / (d[f"P_LE6569{s}"] + d[f"P_LE70OV{s}"])
        d[f"P_LF{s}"] = v[("LF", "TOT", s)]
        d[f"P_LE{s}"] = v[("LF", "TOT", s)] - v[("UL", "TOT", s)]
        d[f"P_UL{s}"] = v[("UL", "TOT", s)]
        d[f"P_LF{s}ER"] = d[f"P_LF{s}"] - sum(d[f"P_LF{a}{s}"] for a in AGES)
        d[f"P_LE{s}ER"] = d[f"P_LE{s}"] - sum(d[f"P_LE{a}{s}"] for a in AGES)
        d[f"P_UL{s}ER"] = d[f"P_UL{s}"] - sum(d[f"P_UL{a}{s}"] for a in AGES)
        d[f"P_LE60OV{s}"] = d[f"P_LE6064{s}"] + d[f"P_LE6569{s}"] + d[f"P_LE70OV{s}"]
    d["M_LF"] = d["P_LFF"] + d["P_LFM"]
    d["M_LE"] = d["P_LEF"] + d["P_LEM"]
    d["P_UL"] = d["P_ULF"] + d["P_ULM"]
    d["M_UR"] = d["P_UL"] / d["M_LF"] * 100
    d["M_LW"] = v[("LW", "TOT", "F")] + v[("LW", "TOT", "M")]
    d["M_LWER"] = d["M_LW"] - sum(d[f"P_LW{a}{s}"] for s in SEXES for a in AGES_LW) \
        - d["P_LW65OVF"] - d["P_LW65OVM"]
    d["M_LFER"] = d["M_LEER"] = d["P_ULER"] = 0.0
    for s in SEXES:
        for a in AGES:
            d[f"P_UL{a}{s}$"] = d[f"P_UL{a}{s}"] / d["P_UL"]
    d["P_POP60OV"] = sum(v[("POP", a, s)] for s in SEXES for a in ("6064", "6569", "70OV"))
    # 年齢・男女別の労働時間のウエイトは使わない（1 に置き、マンアワー＝就業者数）
    for s in SEXES:
        for a in AGES[:10] + ["65OV"]:
            d[f"M_WT{a}{s}"] = 1.0
    d["M_LEH"] = d["M_LE"]
    d["M_LEHF"], d["M_LEHM"] = d["P_LEF"] - d["P_LEFER"], d["P_LEM"] - d["P_LEMER"]
    d["M_EQLF"], d["M_EQUR"] = d["M_LF"], d["M_UR"]
    d["M_EQLE"] = d["M_EQLF"] * (1 - d["M_EQUR"] / 100)
    d["M_EQLH"] = 1.0
    return d


if __name__ == "__main__":
    d = build()
    print(f"{len(d)} 変数")
    for k in ["M_GDPV", "M_GDP", "M_PGDP", "M_TAXC", "M_TAXL", "Z_TYCVC", "Z_TYCVL", "M_VATACP$", "M_VATACG$",
              "M_RAVGC", "M_RAVGL", "M_KFP", "M_KFPCFC$", "M_KHPCFC$", "M_W", "M_UR", "M_SBCV", "M_YCVS"]:
        print(f"  {k:12s} {d[k]:,.4f}")
