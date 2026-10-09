"""財政ブロック移植版（fiscal="port"）の2024年度の値.

単位は10億円（原典の会計変数も10億円）。出典:
- 国の一般会計: 財務省「令和6年度決算の説明」（歳入: kessan_06_19、歳出: kessan_06_03、社会保障関係費:
  kessan_06_04、国債費: kessan_06_06） https://www.mof.go.jp/policy/budget/budger_workflow/account/fy2024/ke_setsumei06.html
- 地方財政計画: 総務省「令和6年度地方財政計画の概要」 https://www.soumu.go.jp/main_content/000927395.pdf
- 地方の普通会計決算: 総務省「令和6年度地方公共団体普通会計決算の概要」 https://www.soumu.go.jp/main_content/001042793.pdf
- 公債等残高: data2024.DEBT（財務省「国及び地方の長期債務残高」）

決算書・計画の項目と、モデル独自の区分（例: 公共事業関係費の直轄・補助・他会計繰入、地方の性質別経費の
一般・社会保障・教育の内訳）が一致しない部分は SPLIT の割合で按分する。SPLIT は推定。
調整項（*ADJ*）と残差（*ER、*XX）は0と置く（標準ケースのアドファクターが同じ役割を果たす）。
"""
from __future__ import annotations

# 千円・億円から10億円への換算
K = 1e-6   # 千円
OKU = 0.1  # 億円

# 推定の按分割合（決算書・計画の項目をモデルの区分に分ける）
SPLIT = {
    # 少子化対策費のうち児童手当（国）の割合
    "w18_in_shoushika": 0.40,
    # 生活扶助等社会福祉費・少子化対策費（児童手当以外）のうち地方への移転の割合
    "w31_share": 0.85,
    # 公共事業関係費の内訳: 直轄、補助、他会計繰入、経常補助、その他
    "exp_a": {"A1": 0.35, "A2": 0.50, "A3": 0.03, "A4": 0.02, "A5": 0.10},
    # その他一般歳出の内訳（施設費・義務教育・社会保障以外）
    "exp_x": {"X2": 0.17, "X31": 0.30, "X32": 0.18, "X33": 0.12, "X34": 0.05, "X35": 0.08, "X37": 0.04, "X38": 0.06},
    # 地方の性質別経費のうち社会保障・教育の割合
    "lg_p": {"S": 0.10, "E": 0.45},     # 人件費
    "lg_c": {"S": 0.15, "E": 0.20},     # 物件費・維持補修費
    "lg_t": {"S": 0.30, "E": 0.10},     # 補助費等・繰出金（医療・介護の繰出しを除く）
    "lg_i": {"S": 0.05, "E": 0.15},     # 投資的経費
    "lg_f": {"S": 0.05, "E": 0.02},     # 投資及び出資金・貸付金
}


def build() -> dict[str, float]:
    d: dict[str, float] = {}

    # ===== 国の一般会計 歳入（決算、千円）=====
    d["Z_TXAG"] = 21_208_582_477 * K
    d["Z_TXBG"] = 17_910_185_359 * K
    d["Z_TXOH"] = (3_552_317_822 + 6_238) * K           # 相続税・地価税
    d["Z_TCIVC"] = 25_021_206_715 * K
    d["Z_TXLQR"] = 1_182_651_766 * K
    d["Z_TXTBC"] = 950_462_240 * K
    d["Z_TITX"] = (2_046_815_735 + 4_220_422 + 32_733_254 + 578_399_923 + 312_768_600 + 394_975_320
                   + 52_482_384 + 931_175_392 + 8_882_009) * K  # 揮発油税ほか9税目
    d["Z_INSI"] = 1_044_202_507 * K
    other = (54_215_762 + 309_759_188 + 10_623_068_883) * K   # 官業益金、政府資産整理収入、雑収入
    surplus_in = 12_157_037_975 * K                           # 前年度剰余金受入
    d["Z_REVOH"] = other + surplus_in
    d["Z_REVOH2"] = surplus_in   # 前年度剰余金受入は伸ばさない部分として扱う
    d["Z_BONREV"] = 37_138_999_718 * K

    # ===== 国の一般会計 歳出（決算、千円）=====
    exp_total = 123_023_998_629 * K
    ss_total = 35_779_216_877 * K
    pension, medical, care = 11_540_991_591 * K, 12_282_104_731 * K, 3_293_312_517 * K
    shoushika, welfare = 3_159_364_985 * K, 4_723_918_340 * K
    health, employment = 703_215_731 * K, 76_308_980 * K
    d["Z_EXPW11"], d["Z_EXPW14"], d["Z_EXPW17"] = pension, medical, care
    d["Z_EXPW18"] = shoushika * SPLIT["w18_in_shoushika"]
    d["Z_EXPW2"] = employment
    rest = welfare + health + shoushika * (1 - SPLIT["w18_in_shoushika"])
    w31 = rest * SPLIT["w31_share"]
    d["Z_EXPW31MED"] = w31 * 0.30   # 生活保護の医療扶助分
    d["Z_EXPW31PUA"] = w31 * 0.25   # 医療扶助以外の生活保護分
    d["Z_EXPW31POA"] = w31 * 0.45   # その他（障害福祉・保育など）
    d["Z_EXPW32"] = rest - w31
    d["Z_EXPW4"] = 70_821_126 * K   # 恩給関係費
    d["Z_EW3D1"] = d["Z_EW3D2"] = 0.0
    d["Z_EXPX1"] = 1_617_253_582 * K   # 義務教育費国庫負担金
    pub = 8_386_842_963 * K            # 公共事業関係費
    for k, s in SPLIT["exp_a"].items():
        d[f"Z_EXPA{k[1]}"] = pub * s
    shisetsu = 214_293_855 * K         # 文教施設費（施設費として扱う）
    d["Z_EXPB1"], d["Z_EXPB2"], d["Z_EXPB3"] = 0.3 * shisetsu, 0.5 * shisetsu, 0.2 * shisetsu
    dst_total = (18_486_753_817 + 1_133_234_252) * K   # 地方交付税交付金＋地方特例交付金
    gb_total = 25_689_396_566 * K                       # 国債費
    expgrl = exp_total - dst_total - gb_total
    w = sum(d[k] for k in ("Z_EXPW11", "Z_EXPW14", "Z_EXPW17", "Z_EXPW18", "Z_EXPW2", "Z_EXPW31MED",
                           "Z_EXPW31PUA", "Z_EXPW31POA", "Z_EXPW32", "Z_EXPW4"))
    a = sum(d[f"Z_EXPA{i}"] for i in "12345")
    b = shisetsu
    x_other = expgrl - w - a - b - d["Z_EXPX1"]
    for k, s in SPLIT["exp_x"].items():
        d[f"Z_EXP{k}"] = x_other * s
    d["Z_EXPX35E"] = d["Z_EXPX35"]
    d["Z_KESSANER"] = 0.0

    # 国債費（決算、千円）
    d["Z_EXPGBRF"] = 16_407_079_319 * K   # 定率繰入
    d["Z_GBRSAN"] = 425_891_061 * K       # 剰余金の2分の1
    d["Z_GBRGEN"] = (858_240_938 - 299_571_943) * K
    d["Z_GBRYOS"] = 30_357_360 * K
    d["Z_GBRGRL"] = 299_571_943 * K       # 借入金償還
    d["Z_PINTBON"] = 7_936_576_132 * K    # 公債利子等
    d["ZP_PINTBON"] = 966_962 * K
    d["Z_PINBRW"] = 10_724_959 * K
    d["Z_PINMOF"] = 600_100 * K
    d["Z_EXPGBOP"] = 18_959_733 * K
    d["Z_EXPGBK"] = 0.0
    d["Z_SPLGPTC2"] = 0.0
    d["Z_DSTCA"] = 0.0
    d["RES_EXPGBRF"] = 0.0
    d["ZR_PINTBON"] = d["ZS_PINTBON"] = d["ZX_PINTBON"] = 0.0
    d["B_PB01"] = d["BP_PB01"] = 0.0

    # 交付税（入口ベース）: 法定率分＋地方特例交付金＋その他
    d["Z_RKF1"], d["Z_RKF2"], d["Z_RKFC"], d["Z_RKFIDLQR"], d["Z_RKFIDTBC"] = 0.331, 0.331, 0.195, 0.50, 0.0
    d["Z_SGTL"] = 1_133_234_252 * K
    d["Z_SGTL1"] = d["Z_SGTL"]
    dsta = (0.331 * d["Z_TXAG"] + 0.331 * d["Z_TXBG"] + 0.195 * d["Z_TCIVC"] + 0.50 * d["Z_TXLQR"])
    d["Z_DSTAER"] = 0.0
    d["Z_DSTCB"] = 0.0
    d["Z_DSTD"] = dst_total - dsta - d["Z_SGTL"]
    for k in "EFGH":
        d[f"Z_DST{k}"] = 0.0

    # 公共事業関係特別会計（推定）
    d["Z_EXPC1"], d["Z_EXPC2"], d["Z_EXPC4"] = 800.0, 300.0, 200.0
    d["Z_REXPA3"] = d["Z_EXPA3"] / (d["Z_EXPC1"] + d["Z_EXPC2"] + d["Z_EXPC4"])
    d["DZ_REXPA3"] = 0.0

    # ===== 地方財政計画（億円）=====
    d["ZP_TXL"] = 427_329 * OKU
    d["ZP_TTL"] = 27_293 * OKU
    d["ZP_TXFLT"] = 0.0
    d["ZP_SGTL"] = 11_320 * OKU
    d["ZP_GTL"] = 186_671 * OKU
    d["ZP_PPT"] = 158_042 * OKU
    d["ZP_LGB"] = 63_103 * OKU
    d["ZP_OTXL"] = (15_625 + 47_182 + 7_600) * OKU   # 使用料及び手数料、雑収入ほか
    d["ZP_LGEXP"] = 202_292 * OKU
    d["ZP_LGEXI"] = 119_896 * OKU
    d["ZP_CLB"] = 108_961 * OKU
    d["ZP_SUIJUN"] = 29_800 * OKU
    d["ZP_SAISEI"] = (12_500 + 4_200) * OKU   # まち・ひと・しごと創生事業費、地域社会再生事業費
    d["ZP_LGEXSS"] = 270_000 * OKU            # 社会保障関係費（一般行政経費の補助分と単独分の一部、推定）
    d["ZP_LGEXOH"] = 936_388 * OKU - (d["ZP_LGEXP"] + d["ZP_LGEXI"] + d["ZP_CLB"] + d["ZP_SUIJUN"]
                                      + d["ZP_SAISEI"] + d["ZP_LGEXSS"])
    d["ZP_LGEXPX"] = d["ZP_LGEXP"]
    d["ZP_LGEXIC"] = 6_000 * OKU                # 直轄事業負担金（推定）
    d["ZP_LGEXIH"] = 56_259 * OKU - d["ZP_LGEXIC"]
    d["ZP_LGEXIT"] = 63_637 * OKU
    d["ZP_LGBR1"], d["ZP_LGBR2"] = 0.0, 4_544 * OKU
    d["ZP_LGBH$"] = 0.10
    d["ZP_LGBT$"] = 0.15
    d["ZP_ZAITAIH$"] = d["ZP_ZAITAIT$"] = 0.02
    d["ZP_LGKIN$"] = 0.06
    d["ZP_LGKEX$"] = 0.04
    for k in ("ZP_LGAPPROP", "ZP_LGBADJ", "ZP_LGBCMP", "ZP_LGBOH", "ZP_LGBRESI", "ZP_LGBTC1", "ZP_LGBTC2",
              "ZP_LGBR2X", "ZP_LGBR2NX", "ZP_CLBER", "ZP_GTLER", "ZP_SGTLER", "ZP_LGBR2NER", "ZP_LGBR2YER",
              "ZP_LGDFCER"):
        d[k] = 0.0

    # ===== 地方の普通会計決算（億円）=====
    d["Z_TXL"] = 462_691 * OKU
    d["Z_TTL"] = 30_962 * OKU
    d["Z_GTL"] = 199_346 * OKU
    d["Z_PPT"] = 201_862 * OKU
    d["Z_LGB"] = 88_506 * OKU
    # 地方税の内訳（推定割合）
    txl = d["Z_TXL"]
    shares = {"Z_TXPLW0": 0.270, "Z_TXPLE": 0.007, "Z_TXCL1": 0.040, "Z_TXCL2": 0.012, "Z_TXRL1": 0.002,
              "Z_TXRL2": 0.006, "Z_TXRL3": 0.006, "Z_TXFL1": 0.075, "Z_TXFL2": 0.020, "Z_TXFL3": 0.008,
              "Z_TXFP": 0.215, "Z_TCIVL": 0.145, "Z_TXOL": 0.060, "Z_TXCAR": 0.055, "Z_TXTBCL": 0.025,
              "Z_TXCIT": 0.030}
    tot = sum(shares.values())
    for k, s in shares.items():
        d[k] = txl * s / tot
    d["Z_TCIVL"] = 6_914.3   # 地方消費税（SNA 一般政府の部門別勘定の付加価値型税・地方と同額）
    d["Z_TXCLT"] = 2_000.0   # 地方法人税（推定）
    d["Z_TXFLT"] = 0.0
    d["Z_TTL$"] = (d["Z_TTL"]) / d["Z_TITX"]
    d["Z_TTL2"] = 0.0
    # 歳出（性質別、億円）
    p, bnft, clb = 243_676 * OKU, 192_622 * OKU, 121_807 * OKU
    c = (126_011 + 14_000) * OKU            # 物件費＋維持補修費（維持補修費は推定）
    t = (122_661 + 64_000) * OKU            # 補助費等＋繰出金（繰出金は推定）
    inv = 164_814 * OKU
    f = 62_000 * OKU                         # 投資及び出資金・貸付金（推定）
    tm = 48_366 * OKU                        # 積立金
    for key, val, lab in (("lg_p", p, "P"), ("lg_c", c, "C"), ("lg_f", f, "F")):
        s = SPLIT[key]
        d[f"Z_LGEX{lab}S"], d[f"Z_LGEX{lab}E"] = val * s["S"], val * s["E"]
        d[f"Z_LGEX{lab}G"] = val * (1 - s["S"] - s["E"])
    d["Z_LGEXIR"] = 25_000 * OKU            # 医療保険給付関係費（国保・後期高齢者への繰出し等、推定）
    d["Z_LGEXKG"] = 18_000 * OKU            # 介護保険給付関係費（推定）
    t_rest = t - d["Z_LGEXIR"] - d["Z_LGEXKG"]
    s = SPLIT["lg_t"]
    d["Z_LGEXTS"], d["Z_LGEXTE"], d["Z_LGEXTG"] = t_rest * s["S"], t_rest * s["E"], t_rest * (1 - s["S"] - s["E"])
    # 扶助費: 補助事業分・単独事業分（推定）
    d["Z_LGEXBSH"] = bnft * 0.70
    d["Z_LGEXBST"] = bnft * 0.30
    d["Z_LGEXBG$"] = 0.0
    d["Z_LGEXBE$"] = 0.0
    # 投資的経費: 補助・単独・直轄負担
    d["Z_LGEXIC"] = 6_000 * OKU
    d["Z_LGEXIH"] = (74_796 + 4_309) * OKU
    s = SPLIT["lg_i"]
    it = inv - d["Z_LGEXIC"] - d["Z_LGEXIH"]
    d["Z_LGEXITS"], d["Z_LGEXITE"], d["Z_LGEXITG"] = it * s["S"], it * s["E"], it * (1 - s["S"] - s["E"])
    for k in ("S", "E", "G"):
        d[f"Z_LGEXIH{k}"] = d["Z_LGEXIH"] * {"S": s["S"], "E": s["E"], "G": 1 - s["S"] - s["E"]}[k]
    d["Z_LGEXTMG"], d["Z_LGEXTMS"], d["Z_LGEXTME"] = tm * 0.8, tm * 0.1, tm * 0.1
    d["Z_LGFND"] = 270_000 * OKU            # 積立金残高（推定）
    d["Z_CF"] = 39_569 * OKU                # 繰越金
    d["Z_CFB"], d["Z_CFBA"] = 39_569 * OKU, 0.0
    d["Z_RLGFNDX"] = 47_611 * OKU           # 繰入金（基金取崩し）
    d["Z_LGEXPEX"] = d["Z_LGEXPE"]
    d["Z_LGB$"] = d["Z_LGB"] / d["ZP_LGB"]
    d["Z_KEIKAKU"], d["Z_KEIKAKUL"] = 0.0, 1.0   # 計画値ではなく実績の伸び（外挿期間）
    d["Z_KESSANC"], d["Z_KESSANL"] = 0.0, 0.0
    d["Z_YOSANC"] = 0.0

    # ===== 交付税特会・その他 =====
    d["Z_SPB"] = 281123 / 10
    d["Z_SLBSTCC"] = 0.0
    d["Z_SPBC"] = d["Z_SPBL"] = 0.0
    d["Z_SPLGPYC"] = 0.0
    d["Z_SPLGPYL"] = 500.0                  # 交付税特会借入金の償還（地方負担分、推定）
    d["Z_TNS"] = 0.0
    d["Z_SPOR"] = d["Z_SPS2"] = d["Z_SEXPER"] = 0.0
    d["Z_POPJIDO"] = 1_500.0                # 児童手当の対象児童数（万人、推定）

    # 社会保障の簡略版の水準（推定。SNA の社会保障関係の値に近い規模）
    d["S_PPIEXPD"] = 56_000.0
    d["S_MMIEXPD"] = 47_000.0
    d["S_CCIEXPD"] = 12_000.0
    for k, v in {"S_PEOIPRM": 36_000, "S_PMCIPRM": 1_800, "S_PMLIPRM": 4_000, "S_PMPIPRM": 600, "S_PNPIPRM": 1_300,
                 "S_PPIERBG": 3_000, "S_PPIERBP": 18_000, "S_MMIERBG": 1_500, "S_MMIERBP": 11_000,
                 "S_CCIERBG": 200, "S_CCIERBP": 1_300, "S_MMIIPHH": 22_000, "S_CCIIPHH": 3_500,
                 "S_OEIIPRM": 2_000, "S_PNMPEBC": pension, "S_PMCPEBC": 200, "S_PMLPEBL": 300,
                 "S_PMPPEBC": 100, "S_MMIPEBC": medical * 0.6, "S_MMIPEBL": 6_000, "S_MHAPEBC": medical * 0.1,
                 "S_MNHPEBC": medical * 0.2, "S_MNUPEBC": medical * 0.02, "S_MLEDCBC": medical * 0.08,
                 "S_MMIESSL": 1_000, "S_CCIPEBC": care, "S_CCIPEBL": 3_500, "S_CCIESSL": 300,
                 "S_OUIBNFT": 1_500, "S_OUIPEBC": employment, "S_OEIBNFT": 2_500, "S_OSABNFO": 11_000,
                 "S_OSABNFP": 100, "S_PPIING": 2_500}.items():
        d[k] = float(v)
    d["S_PPIBOND"] = 100_000.0
    d["S_PPISPR$"] = d["S_PPIING"] / d["S_PPIBOND"] * 100 - 1.1
    d["S_OUIPEBC$"] = d["S_OUIPEBC"] / d["S_OUIBNFT"]
    d["S_PRICE"] = d["S_MEDP"] = 1.0
    d["S_EXR"] = 1.0
    d["S_PENQ$"] = d["S_MEDQ$"] = d["S_CAREQ$"] = d["S_SLIDE$"] = d["S_OSABNFPG$"] = 0.0
    d["S_PUAL$"] = 0.0
    d["S_OEIERBP$"] = 0.0
    for k in ("SH_HOIKUE", "SH_HOIKUL", "SH_KAIGOC", "SH_KAIGOL", "SH_SITOC", "SH_SITOG", "SH_SITOL", "SH_SITOP",
              "SH_YOJIGTOKUREI"):
        d[k] = 0.0

    # 国債・地方債の集約版
    d["ZP_GBNML2"] = 2_300.0                 # 年金特例公債（財務省資料の注、2024年度末）
    d["Z_GBNML2"] = 1_055_000.0 - d["ZP_GBNML2"]
    # マクロブロックの式で使う値（SNA と会計の差など）
    d["M_BSSVPEN"] = 62_197.8                # 現金による社会保障給付（SNA、社会保障基金）
    d["M_TAXCER"] = 80_038.3 - (sum(d[k] for k in ("Z_TXAG", "Z_TXBG", "Z_TXOH", "Z_TXLQR", "Z_TXTBC", "Z_TCIVC",
                                                   "Z_TITX", "Z_INSI")) - d["Z_TXOH"] + d["Z_TTL"] + d["Z_TXCLT"])
    d["M_TAXLER"] = 46_482.9 - d["Z_TXL"]
    # 制度変更による増減税の累積など（0）
    for k in ("Z_TPISV", "Z_TXFLXX", "Z_TTCIVLXX", "Z_TTLXX"):
        d[k] = 0.0
    d["Z_EXPA2X"] = 100.0                    # 公共事業関係費のうち下水道分の地方補助金（推定）
    d["Z_OTXLMF"] = 57_216 * OKU             # 貸付金元利収入
    d["Z_OTXLMG"] = 63_000 * OKU             # 使用料・手数料、諸収入など（推定）
    d["B_LGBMAT$"] = 12.0                    # 地方債の元金償還の平均年数（推定）
    d["Z_ROPR"] = 0.0
    d["Z_ROPR$"] = 0.35                      # 地方債の元利償還のうち臨時財政対策債の割合（推定）
    d["Z_RRR$"] = 0.35

    # その他の定数
    d["Z_GREXPX$"] = 1.0
    d["Z_IG3$"] = 0.0
    # 国の公的固定資本形成（SNA）と会計の直轄事業費などの比
    d["Z_IG1$"] = 8_505.1 / (d["Z_EXPA1"] + d["Z_EXPB1"] + d["Z_EXPB3"] + d["Z_EXPC1"] + d["Z_EXPX38"])
    d["Z_LGAPPROP"] = 0.0
    # 税外収入のうち経常移転・資本移転に当たる割合（推定）
    d["M_ZEIGAI$"], d["M_CZEIGAI$"] = 0.30, 0.05
    d["Z_JTE$"] = d["Z_JTL$"] = 0.0
    d["Z_EXPW31ADJ$"] = 0.0
    d["Z_LGEXBSH$"] = 1.0
    d["Z_RTYCVH"], d["Z_RTYCVL"], d["Z_YCVSS"] = 0.232, 0.15, 0.0
    d["Z_RTCIVC"], d["Z_RTCIVL"] = 0.78, 0.22
    d["Z_RADJTCIVC"] = d["Z_RADJTCIVL"] = 0.0
    d["Z_SPLGFND"] = d["Z_SPLGFND2"] = 0.0
    d["M_MITOSHI"] = 0.0
    d["Z_PGDPA"] = 1.0
    # 公債金収入の定義式（Z_BONREV=Z_EXPT-Z_REV1-Z_REVOH+Z_41JYOYO）が決算と合うように、
    # 当年度の剰余（翌年度繰越の財源など）を Z_41JYOYO とする
    d["Z_41JYOYO"] = d["Z_BONREV"] - (exp_total - (d["Z_TXAG"] + d["Z_TXBG"] + d["Z_TXOH"] + d["Z_TXLQR"]
                                                    + d["Z_TXTBC"] + d["Z_TCIVC"] + d["Z_TITX"] + d["Z_INSI"])
                                      - d["Z_REVOH"])
    for k in ("Z_41JYOYO1", "Z_41JYOYO2", "Z_REVOH5X", "Z_REVOH6X", "Z_REVOHADJ", "Z_REVOHADJCH"):
        d.setdefault(k, 0.0)
    return d
