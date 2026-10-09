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
    d["ZP_LGBR2NX"] = d["ZP_LGBR2"]   # 臨時財政対策債（既往債の元利償還金分等）
    d["ZP_LGDFC"] = 18_000 * OKU      # 財源不足額 1.8兆円（総務省「令和6年度地方財政計画の概要」）
    # 地方債計画: 一般債・財源対策債の投資的経費に対する比率（臨時財政対策債を除く地方債が計画の値になるように）
    d["ZP_ZAITAIH$"] = d["ZP_ZAITAIT$"] = 0.02
    gen = d["ZP_LGB"] - d["ZP_LGBR2"] - (d["ZP_ZAITAIH$"] + d["ZP_ZAITAIT$"]) * d["ZP_LGEXI"]
    d["ZP_LGBH$"] = 0.4 * gen / d["ZP_LGEXI"]
    d["ZP_LGBT$"] = 0.6 * gen / d["ZP_LGEXI"]
    # 不交付団体の基準財政収入額・需要額の比率: 水準超経費の式 (LGKIN-LGKEX)/0.75 が計画の値になるように決める
    base_in = d["ZP_TXL"] + d["ZP_TTL"] + d["ZP_TXFLT"] + d["ZP_SGTL"]
    base_ex = d["ZP_LGEXP"] + d["ZP_LGEXSS"] + d["ZP_LGEXI"] + d["ZP_LGEXOH"] + d["ZP_SAISEI"] + d["ZP_CLB"]
    d["ZP_LGKEX$"] = 0.04
    d["ZP_LGKIN$"] = (d["ZP_SUIJUN"] * 0.75 + d["ZP_LGKEX$"] * base_ex) / base_in
    for k in ("ZP_LGAPPROP", "ZP_LGBADJ", "ZP_LGBCMP", "ZP_LGBOH", "ZP_LGBRESI", "ZP_LGBTC1", "ZP_LGBTC2",
              "ZP_LGBR2X", "ZP_CLBER", "ZP_GTLER", "ZP_SGTLER", "ZP_LGBR2NER", "ZP_LGBR2YER",
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
    # 歳出（性質別、億円）。社会保障分（民生費＋衛生費）と教育分（教育費）は地方財政白書（令和8年版）の
    # 目的別歳出の性質別内訳（第30図 民生費、第34図 教育費、第41図 衛生費、純計）と第9表（性質別）から。
    # https://www.soumu.go.jp/menu_seisaku/hakusyo/chihou/r08data/2026data/r08czb01-04.html
    # 第30図の扶助費は CSV で「18,905」となっているが、合計からの逆算（180,904）と構成比55.3%に合う値を使う
    W = {"min": {"扶助": 180_904, "繰出": 57_210, "補助": 43_275, "人件": 24_438, "物件": 14_578, "建設": 5_501},
         "kyo": {"人件": 105_951, "物件": 31_393, "建設補助": 8_231, "建設単独": 17_822, "その他": 30_128},
         "eis": {"物件": 27_861, "補助": 17_421, "人件": 11_572, "建設": 10_098, "扶助": 5_601}}
    p, bnft, clb = 243_676 * OKU, 192_622 * OKU, 121_807 * OKU
    c = (126_011 + 14_000) * OKU            # 物件費＋維持補修費（維持補修費は推定）
    t = (122_661 + 58_896) * OKU            # 補助費等＋繰出金（第9表）
    inv = 164_814 * OKU
    f = 62_000 * OKU                         # 投資及び出資金・貸付金（推定）
    tm = 48_366 * OKU                        # 積立金
    # 人件費・物件費
    d["Z_LGEXPS"] = (W["min"]["人件"] + W["eis"]["人件"]) * OKU
    d["Z_LGEXPE"] = W["kyo"]["人件"] * OKU
    d["Z_LGEXPG"] = p - d["Z_LGEXPS"] - d["Z_LGEXPE"]
    d["Z_LGEXCS"] = (W["min"]["物件"] + W["eis"]["物件"]) * OKU
    d["Z_LGEXCE"] = W["kyo"]["物件"] * OKU
    d["Z_LGEXCG"] = c - d["Z_LGEXCS"] - d["Z_LGEXCE"]
    s = SPLIT["lg_f"]
    d["Z_LGEXFS"], d["Z_LGEXFE"], d["Z_LGEXFG"] = f * s["S"], f * s["E"], f * (1 - s["S"] - s["E"])
    # 補助費等・繰出金: 民生費の繰出金を医療・介護への繰出しとし、医療・介護に分ける（介護の割合は推定）
    d["Z_LGEXIR"] = W["min"]["繰出"] * 0.65 * OKU   # 医療保険給付関係費（国保・後期高齢者）
    d["Z_LGEXKG"] = W["min"]["繰出"] * 0.35 * OKU   # 介護保険給付関係費
    d["Z_LGEXTS"] = (W["min"]["補助"] + W["eis"]["補助"]) * OKU
    d["Z_LGEXTE"] = W["kyo"]["その他"] * 0.5 * OKU  # 教育費の「その他」の半分を補助費等・繰出金とみなす（推定）
    d["Z_LGEXTG"] = t - d["Z_LGEXIR"] - d["Z_LGEXKG"] - d["Z_LGEXTS"] - d["Z_LGEXTE"]
    # 扶助費: 民生費・衛生費の扶助費を社会保障分、残りを教育費分（就学援助など）とする。
    # 社会保障分の補助事業分・単独事業分は SNA との整合で推定する（calibrate_splits）
    bs = (W["min"]["扶助"] + W["eis"]["扶助"]) * OKU
    d["Z_LGEXBSH"] = bs * 0.70
    d["Z_LGEXBST"] = bs * 0.30
    d["Z_LGEXBG$"] = 0.0
    d["Z_LGEXBE$"] = (bnft - bs) / bs   # 原典は Z_LGEXBE=Z_LGEXBE$*(Z_LGEXBSH+Z_LGEXBST-…)
    # 投資的経費: 補助・単独・直轄負担（第9表）、社会保障分・教育分（各図）
    d["Z_LGEXIC"] = (158_231 - 74_796 - 75_522) * OKU   # 普通建設事業費のうち補助・単独以外（直轄負担など）
    d["Z_LGEXIH"] = (74_796 + 4_309) * OKU
    it = inv - d["Z_LGEXIC"] - d["Z_LGEXIH"]
    ss_inv = (W["min"]["建設"] + W["eis"]["建設"]) * OKU
    d["Z_LGEXIHS"], d["Z_LGEXITS"] = ss_inv * 0.5, ss_inv * 0.5
    d["Z_LGEXIHE"], d["Z_LGEXITE"] = W["kyo"]["建設補助"] * OKU, W["kyo"]["建設単独"] * OKU
    d["Z_LGEXIHG"] = d["Z_LGEXIH"] - d["Z_LGEXIHS"] - d["Z_LGEXIHE"]
    d["Z_LGEXITG"] = it - d["Z_LGEXITS"] - d["Z_LGEXITE"]
    d["Z_LGEXTMG"], d["Z_LGEXTMS"], d["Z_LGEXTME"] = tm * 0.8, tm * 0.1, tm * 0.1
    d["Z_LGFND"] = 270_000 * OKU            # 積立金残高（推定）
    d["Z_CF"] = 39_569 * OKU                # 繰越金
    d["Z_CFB"], d["Z_CFBA"] = 39_569 * OKU, 0.0
    d["Z_RLGFNDX"] = 47_611 * OKU           # 繰入金（基金取崩し）
    d["Z_LGEXPEX"] = 0.0   # 外挿期間は前年の伸びで延ばす（外生の水準は使わない）
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
    pension_data(d)
    medical_care_data(d, medical, care)
    other_ss_data(d)
    d["S_EXR"] = 1.0
    d["S_PUAL$"] = 0.0
    d["S_OEIERBP$"] = (0.4 + 0.35 + 0.2) / 1.55   # 雇用保険料のうち事業主負担（2024年度の料率）
    for k in ("SH_HOIKUE", "SH_HOIKUL", "SH_KAIGOC", "SH_KAIGOL", "SH_SITOC", "SH_SITOG", "SH_SITOL", "SH_SITOP",
              "SH_YOJIGTOKUREI"):
        d[k] = 0.0

    # 国債・地方債の集約版
    d["ZP_GBNML2"] = 2_300.0                 # 年金特例公債（財務省資料の注、2024年度末）
    d["Z_GBNML2"] = 1_055_000.0 - d["ZP_GBNML2"]
    # マクロブロックの式で使う値（SNA と会計の差など）
    # 現金による社会保障給付（SNA、社会保障基金）。原典の M_BSSVF の式は政府の支払いを負値で持つ
    # （M_BSSVF=((-M_BSSVPEN)+…)*(-1)）ので負値で入れる
    d["M_BSSVPEN"] = -62_197.8
    d["M_TAXCER"] = 80_038.3 - (sum(d[k] for k in ("Z_TXAG", "Z_TXBG", "Z_TXOH", "Z_TXLQR", "Z_TXTBC", "Z_TCIVC",
                                                   "Z_TITX", "Z_INSI")) - d["Z_TXOH"] + d["Z_TTL"] + d["Z_TXCLT"])
    d["M_TAXLER"] = 46_482.9 - d["Z_TXL"]
    # 制度変更による増減税の累積など（0）
    for k in ("Z_TPISV", "Z_TXFLXX", "Z_TTCIVLXX", "Z_TTLXX"):
        d[k] = 0.0
    d["Z_EXPA2X"] = 100.0                    # 公共事業関係費のうち下水道分の地方補助金（推定）
    d["Z_OTXLMF"] = 57_216 * OKU             # 貸付金元利収入
    d["Z_OTXLMG"] = 63_000 * OKU             # 使用料・手数料、諸収入など（推定）
    d["B_LGBMAT$"] = 14.0                    # 地方債の元金償還の平均年数（公債費の計画値に合うように推定）
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
    # 税外収入のうち経常移転・資本移転に当たる割合（推定。経常移転は M_TRPC の式が SNA に合う水準）
    d["M_ZEIGAI$"], d["M_CZEIGAI$"] = 0.04, 0.05
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


# 国の一般会計のうち雇用者報酬（人件費）の規模（推定。一般会計の人件費は5兆円台）
X2_FIXED = 5_300.0


def pension_data(d: dict) -> None:
    """年金ブロック（原典の式）の2024年度の値（10億円、人数は万人）.

    出典（data/raw/ss_stats_sources.md の A 節）: 社会保障審議会年金数理部会「公的年金財政状況報告―令和6(2024)年度―」
    （給付費・受給者数・被保険者数・標準報酬総額・保険料収入・国庫負担・拠出金算定対象者数・積立金）、
    GPIF「2024年度業務概況書」（インカムゲイン）、厚生労働省の令和6・7年度の年金額改定の公表資料。
    厚生年金の報酬比例部分だけの給付費は公表がないので、制度全体の給付費 − 基礎年金給付費とする。
    """
    B = 0.1   # 億円 → 10億円
    # 給付
    d["S_PBPBNFT"] = 254_805 * B              # 基礎年金勘定の給付費
    d["S_PENBNFT"] = (553_401 - 254_805) * B  # 制度全体 − 基礎年金
    d["S_PPIESSC"] = 0.0
    d["S_PBPBNFTN"] = 3_630.2                 # 国民年金（基礎年金）受給者数
    d["S_PENBNFTN"] = 3_618.9 + 129.6 + 312.9 + 63.5   # 旧厚年・国共済・地共済・私学
    d["S_PBPBNFTA"] = d["S_PBPBNFT"] / d["S_PBPBNFTN"]
    d["S_PENBNFTA"] = d["S_PENBNFT"] / d["S_PENBNFTN"]
    d["S_PBPBNFTNZ"], d["S_PENBNFTNZ"] = d["S_PBPBNFTN"], d["S_PENBNFTN"]
    # 改定率: マクロ経済スライドの調整率 −0.4%（令和6・7年度）
    for k in ("S_PBPRCMSZ", "S_PENRCMSZ"):
        d[k] = 0.996
    for k in ("S_PBPRCMSY", "S_PENRCMSY", "S_PBPRCOFZ", "S_PBPRCOFY", "S_PENRCOFZ", "S_PENRCOFY", "S_PPICPIGZ"):
        d[k] = 0.0
    d["S_PBPRCYA$"] = d["S_PENRCYA$"] = 0.85   # 68歳以上（既裁定）の受給者の割合（推定）
    for k in ("S_PBPSSRY", "S_PENSSRY", "S_PBPSSRE", "S_PENSSRE"):
        d[k] = 1.0
    d["S_PPICPIC$"] = d["S_PPIRMNRA"] = 1.0
    # 基礎年金拠出金: 基礎年金給付費 − 特別国庫負担（4,366億円）を拠出金算定対象者数（万人）で割り振る
    d["S_PBPDCBC$Z"] = 4_366 / 254_805
    d["S_PBPDCBC"] = d["S_PBPDCBC$Z"] * d["S_PBPBNFT"]
    d["S_PBPTRBP"] = d["S_PBPBNFT"] - d["S_PBPDCBC"]
    n = {"EO": 4_276.2, "MP": 59.6, "MC": 122.9, "ML": 319.8, "NP": 658.7}
    for c, v in n.items():
        d[f"S_P{c}TRBPN"] = v
    d["S_PEOTRBPNZ"], d["S_PMATRBPNZ"], d["S_PNPTRBPNZ"] = n["EO"], n["MC"], n["NP"]
    d["S_PBPTRBPN"] = sum(n.values())
    for c in n:
        d[f"S_P{c}TRBP"] = d["S_PBPTRBP"] * n[c] / d["S_PBPTRBPN"]
    # 保険料収入・標準報酬総額（億円）、被保険者数（万人）
    prem = {"EO": 363_545, "MP": 5_543, "MC": 13_198, "ML": 34_978}
    rmnr = {"EO": 2_010_667, "MP": 34_417, "MC": 72_966, "ML": 195_347}
    insp = {"EO": 4_284.9, "MP": 61.0, "MC": 107.1, "ML": 294.7, "NP": 1_368.0}
    for c in prem:
        d[f"S_P{c}IPRM"] = prem[c] * B
        d[f"S_P{c}RMNR"] = rmnr[c] * B
        d[f"S_P{c}IPRM$Z"] = prem[c] / rmnr[c]
        d[f"S_P{c}INSPN"] = d[f"S_P{c}INSPNZ"] = insp[c]
        d[f"S_P{c}RMNRA"] = d[f"S_P{c}RMNR"] / insp[c]
    d["S_PNPINSPN"] = d["S_PNPINSPNZ"] = insp["NP"]
    d["S_PNPIPRMA"] = d["S_PNPIPRMAZ"] = 16_980.0   # 国民年金保険料月額（円）
    d["S_PNPIPRM"] = 13_989 * B
    d["S_PNPIPPY$Z"] = d["S_PNPIPRM"] / (d["S_PNPIPRMA"] * 12 * insp["NP"])
    # 雇主負担: 厚生年金・共済の保険料の労使折半
    d["S_PPIERBG$"] = d["S_PPIERBP$"] = 0.5
    d["S_PPIERBG"] = 0.5 * (d["S_PMCIPRM"] + d["S_PMLIPRM"])
    d["S_PPIERBP"] = 0.5 * (d["S_PEOIPRM"] + d["S_PMPIPRM"])
    # 国庫・公経済負担（億円）: 拠出金に対する割合を実額から逆算する（その他の公経済負担は0）。
    # 共済（国・地方）は拠出金の2分の1とし、残りは追加費用など（S_PMCDCACZ、S_PMLDCALZ）
    pub = {"EO": 90_957, "MP": 1_231, "MC": 2_610, "ML": 6_505, "NP": 19_685}
    for c, tag in (("EO", "C"), ("MP", "C"), ("MC", "C"), ("ML", "L"), ("NP", "C")):
        rate = pub[c] * B / d[f"S_P{c}TRBP"] if c in ("EO", "MP", "NP") else 0.5
        d[f"S_P{c}DCT{tag}$"] = rate
        d[f"S_P{c}DCT{tag}"] = rate * d[f"S_P{c}TRBP"]
        d[f"S_P{c}DCB{tag}$Z"] = 0.0
        d[f"S_P{c}DCB{tag}"] = 0.0
    d["S_PMPPEBC"] = d["S_PMPDCTC"] + d["S_PMPDCBC"]
    d["S_PMCPEBC"], d["S_PMLPEBL"] = pub["MC"] * B, pub["ML"] * B
    d["S_PMCDCACZ"] = d["S_PMCPEBC"] - d["S_PMCDCTC"] - d["S_PMCDCBC"]
    d["S_PMLDCALZ"] = d["S_PMLPEBL"] - d["S_PMLDCTL"] - d["S_PMLDCBL"]
    d["S_PNMPEBC"] = (pub["EO"] + pub["NP"]) * B   # 共済を除く国の負担
    d["S_PNMPEBCZ"] = 0.0
    # 積立金（時価、制度全体）と運用収入
    d["S_PPIFUND"] = 3_060_257 * B
    d["S_PPIFUNDBD$"] = 0.2764                     # 国内債券の割合（年金積立金全体）
    d["S_PPIFUNDBD"] = d["S_PPIFUND"] * d["S_PPIFUNDBD$"]
    d["S_PPIFUNDOT"] = d["S_PPIFUND"] - d["S_PPIFUNDBD"]
    d["S_PPIING$"] = 46_788 / 2_497_821 * 100      # GPIF のインカムゲイン / 運用資産（%）
    # 運用利回り（%）= 実質利回り × 資本収益率/基準の資本収益率 ＋ CPI上昇率（実質利回りは推定）
    d["S_PPIRTRBD$Z"], d["S_PPIRTROT$Z"] = 0.0, 3.0
    d["S_PPIPROR$2"] = 0.05                 # baseline.make で基準年度の資本収益率に置き換える


def medical_care_data(d: dict, medical: float, care: float) -> None:
    """医療・介護ブロック（原典の式、年齢別は集約）の値（10億円、人数は万人）.

    医療（data/raw/ss_stats_sources.md の B 節）: 厚生労働省保険局「医療保険に関する基礎資料〜令和5年度の医療費等の
    状況〜」の財政構造表（制度別の加入者数、医療給付費の前期調整対象分とそれ以外、公費、総報酬、後期高齢者支援金）。
    制度横断の令和6年度版は未公表なので令和5年度の値を使う。公費の割合は構造表の実額から計算する。
    介護（C 節）: 厚生労働省「令和6年度 介護保険事業状況報告（年報）」。
    """
    B = 0.1   # 億円 → 10億円
    # 加入者数（万人）: 全体、65～74歳、40～64歳（40～64歳は年齢階級別加入者数の合計）
    insp = {"HA": (3_957, 325, 1_714.6), "MA": (976, 34, 402.1), "EH": (2_809, 100, 1_204.1),
            "NH": (2_372, 1_039, 773.7), "NU": (260, 31, 111.4)}
    # 医療給付費（億円）: 前期調整対象分以外（≒65歳未満）、前期調整対象分（≒65～74歳）
    bnft = {"HA": (52_260, 13_021), "MA": (14_224, 1_189), "EH": (38_669, 3_880),
            "NH": (32_508, 51_422), "NU": (3_301, 1_319)}
    # 報酬水準: 総報酬（億円）/ 加入者数 を被用者保険の平均で割る
    comp = {"HA": 1_030_413, "MA": 329_501, "EH": 973_500}
    avg = sum(comp.values()) / sum(insp[a][0] for a in comp)
    for a in insp:
        d[f"S_M{a}INSPN"], d[f"S_M{a}INSP6574N"], d[f"S_M{a}INSP4064N"] = map(float, insp[a])
        d[f"S_M{a}BNFT0064$"], d[f"S_M{a}BNF6574B$"] = bnft[a][0] * B, bnft[a][1] * B
        d[f"S_M{a}COMPA$"] = comp[a] / insp[a][0] / avg if a in comp else 1.0
    # 国保の国・地方の負担割合: 構造表の公費 /（前期財政調整後の給付費＋後期高齢者支援金）。協会けんぽは法定の16.4%
    adj = {"NH": -32_010, "NU": 498}
    sup = {"NH": 11_764, "NU": 1_933}
    base = {a: bnft[a][0] + bnft[a][1] + adj[a] + sup[a] for a in adj}
    d["S_MHADCBC$"] = 0.164
    d["S_MNHDCBC$"] = 29_156 / base["NH"]
    d["S_MNHDCBL$"] = (9_753 + 2_439) / base["NH"]
    d["S_MNUDCBC$"] = 2_386 / base["NU"]
    d["S_MLEBNFT$"] = 172_072 * B
    d["S_MLEDCBC$"] = 55_185 / 172_072
    d["S_MLEDCBL$"] = (17_048 + 14_326) / 172_072
    d["S_MLEDCBY$"] = 71_960 / 172_072
    d["S_MYETTCB$"] = 1.0                    # 被用者保険の後期高齢者支援金は全面総報酬割
    d["S_MNRBNFT"] = d["S_MNRINSPN"] = 0.0   # 退職者医療制度は経過措置終了
    d["S_MMICOSTI"] = 1.0
    d["S_MMIRCOFX"] = d["S_MMICPIGZ"] = 0.0
    # 診療報酬改定率: 賃金と物価の平均を、当年度と前年度で半分ずつ（資料に値がないので推定）
    d["S_MMIRCCF$"], d["S_MMICFWG$"], d["S_MMICFPR$"] = 0.5, 1.0, 1.0
    d["S_MMIPEBCA"] = d["S_MMIPEBLA"] = 0.0
    d["S_MMIPEBK"] = d["S_MMIPEBC"] = medical      # 一般会計の医療給付費（2024年度決算）
    d["S_MMIPEBR"] = d["S_MMIPEBL"] = (26_801 + 16_765) * B   # 都道府県・市区町村の公費（構造表）
    d["S_MMIESSC"] = d["S_MMICSSC"] = d["S_MMIESSL"] = d["S_MMICSSL"] = 0.0
    # 雇主負担: 被用者保険の保険料の半分。共済組合の事業主は政府（私学共済の保険料の分を除く）
    d["S_MMIERBG$"] = d["S_MMIERBP$"] = 0.5
    d["S_MMAERBG$"] = 1 - 3_038 / (6_269 + 19_537 + 3_038)
    # 介護（億円）: 給付費 111,826 のうち施設 33,722。高額介護サービス費など3費目は施設・居宅の比で配分
    other3 = 2_916 + 401 + 2_322
    f = 33_722 * (1 + other3 / (111_826 - other3))
    d["S_CCIBNFF$"], d["S_CCIBNFH$"] = f * B, (111_826 - f) * B
    d["S_CCICOSTI"] = 1.0
    d["S_CCIRCOFX"] = d["S_CCICPIGZ"] = 0.0
    d["S_CCICFWG$"] = d["S_CCICFPR$"] = 0.5        # 介護報酬改定率: 賃金と物価の平均（推定）
    d["S_CCIDCFC$"], d["S_CCIDCFL$"], d["S_CCIDCHC$"], d["S_CCIDCHL$"] = 0.20, 0.30, 0.25, 0.25   # 法定
    d["P_POP65OV"] = 3_625.0                 # 65歳以上人口（万人、2024年10月）
    d["S_CCIPINSN$"] = 3_584 / d["P_POP65OV"]   # 第1号被保険者数（令和7年3月末）/ 65歳以上人口
    d["S_CCITTC$"] = 1.0                     # 第2号保険料の総報酬割
    d["S_CCIPEBC"] = care                    # 一般会計の介護給付費（2024年度決算）
    d["S_CCIPEBL"] = (17_083 + 14_006) * B   # 都道府県支出金＋市町村一般会計繰入金
    d["S_CCIESSC"] = d["S_CCICSSC"] = d["S_CCIESSL"] = d["S_CCICSSL"] = 0.0


def other_ss_data(d: dict) -> None:
    """雇用保険・社会扶助（その他10本）の2024年度の値（10億円）.

    出典（data/raw/ss_stats_sources.md の D・E 節）: 財務省「令和6年度決算の説明」労働保険特別会計 雇用勘定、
    一般会計 恩給関係費。
    """
    K = 1e-6  # 千円 → 10億円
    d["S_OUIBNFT"] = 1_216_539_951 * K       # 失業等給付費
    d["S_HPLBNFT"] = 794_363_991 * K         # 育児休業給付費
    d["S_OEIBNFT$"] = 1.0
    d["S_OEIBNFT"] = d["S_OEIBNFT$"] * d["S_OUIBNFT"] + d["S_HPLBNFT"]
    d["S_OSDBNFT"] = 404_747_338 * K         # 雇用保険二事業（防衛力強化一般会計への繰入を除く）
    d["ADJOSDBNFT"] = 0.0
    # 保険料: 徴収勘定からの繰入（失業等給付分＋育児休業給付分、二事業分）
    d["S_OUIIPRM"] = (1_668_916_698 + 834_369_750) * K
    d["S_OSDIPRM"] = 732_792_795 * K
    d["S_OEIIPRM"] = d["S_OUIIPRM"] + d["S_OSDIPRM"]
    d["S_OUIIPRM$"] = 1.0                    # 推計式の定数（アドファクターで合わせる）
    d["S_OUIPEBC"] = 120_412_917 * K         # 国庫負担金（失業等給付分＋育児休業給付分）
    d["S_OUIPEBC$"] = d["S_OUIPEBC"] / d["S_OUIBNFT"]
    d["S_OSABNFO"] = 11_000.0                # 社会扶助給付（恩給を除く、SNA ベース、推定）
    d["S_OSABNFP"] = d["Z_EXPW4"]            # 恩給関係費（2024年度決算）
    d["S_OSACPIG$"] = 1.0
    d["S_OSACPIGZ"] = 0.0


def calibrate_splits(d: dict, sna: dict) -> dict:
    """モデル独自区分の金額を、SNA の一般政府の部門別勘定に合うように推定する（最小二乗法）.

    原典のマクロブロックの振り分けの式（会計の項目 → SNA の集合消費・個別消費・補助金・移転など）の係数は
    そのまま使い、未知の按分（国のその他一般歳出の内訳、地方の性質別経費の社会保障・教育分など）を、
    SNA の値（sna、data2024 の値）に合うように決める。統計で決まらない部分は SPLIT の推定割合に近づける。
    """
    import numpy as np
    from scipy.optimize import lsq_linear

    out = {}
    # ---------- 国: その他一般歳出の内訳 ----------
    # 人件費（X2）は一般会計の人件費の規模で固定し、残りを推定する
    x2, x37 = X2_FIXED, 312_768_600 * K   # X37 は電源開発促進税財源のエネルギー対策特会への繰入（決算の税収と同額）
    out["Z_EXPX2"], out["Z_EXPX37"] = x2, x37
    keys = ["X31", "X32", "X33", "X34", "X35", "X38"]
    total = sum(d[f"Z_EXP{k}"] for k in keys + ["X2", "X37"]) - x2 - x37
    ix = {k: i for i, k in enumerate(keys)}
    A, b, w = [], [], []

    def row(coefs: dict, rhs: float, weight: float = 1.0):
        r = np.zeros(len(keys))
        for k, c in coefs.items():
            r[ix[k]] = c
        A.append(r * weight)
        b.append(rhs * weight)

    fisim_c = sna["M_FCRAR"] + sna["M_FCRLR"]
    pmc, pmp = d["S_PMCPEBC"], d["S_PMPPEBC"]
    zeigai = d["Z_REVOH"] - d["Z_REVOH2"]
    row({"X31": 0.8, "X35": 0.5},
        -sna["M_CGVCC"] - 0.8 * (x2 - pmc) - x37 + 0.5 * pmp - d["Z_EXPGBOP"] - 0.9 * sna["M_DEPC"] - fisim_c)
    row({"X31": 0.2},
        -sna["M_CGVIC"] - 0.2 * (x2 - pmc) - 0.5 * d["Z_EXPW32"] - 0.1 * sna["M_DEPC"])
    row({"X32": 0.7}, -sna["M_SUBVC"] - d["Z_EXPA4"])
    row({"X35": 0.3, "X32": 0.1}, -sna["M_TRPC"] + 0.3 * pmp + d["M_ZEIGAI$"] * zeigai)
    row({"X35": 0.2, "X32": 0.2}, -sna["M_CTRPC"] - d["Z_EXPA5"] + 0.2 * pmp + d["M_CZEIGAI$"] * zeigai)
    row({k: 1.0 for k in keys}, total, 10.0)
    # 国庫支出金（地方の決算）との整合: その他の国庫支出金 ≒ 対地方移転 + 児童手当
    ppt_o = d["Z_PPT"] - (d["Z_EXPW31MED"] + d["Z_EXPW31PUA"] + d["Z_EXPW31POA"]) - d["Z_EXPX1"] \
        - (d["Z_EXPA2"] + d["Z_EXPB2"] + d["Z_EXPC2"])
    row({"X33": 1.0}, ppt_o - d["Z_EXPW18"], 0.3)
    for k in keys:   # 推定割合に近づける弱い条件
        row({k: 1.0}, d[f"Z_EXP{k}"], 0.05)
    res = lsq_linear(np.array(A), np.array(b), bounds=(0, np.inf))
    for k, v in zip(keys, res.x):
        out[f"Z_EXP{k}"] = float(v)
    out["Z_EXPX35E"] = out["Z_EXPX35"]

    # ---------- 地方: 扶助費（社会保障分）の補助事業分・単独事業分 ----------
    # 性質別経費の社会保障分・教育分は白書の統計で決めた（build）。統計で分からない扶助費の補助事業分・
    # 単独事業分と、社会給付の式の比率 Z_LGEXBSH$ を、地方の個別消費と社会給付（SNA）に合うように決める。
    bs = d["Z_LGEXBSH"] + d["Z_LGEXBST"]
    otx = d["Z_OTXLMG"]
    w31med = d["Z_EXPW31MED"]
    ppts = d["Z_EXPW31MED"] + d["Z_EXPW31PUA"] + d["Z_EXPW31POA"]
    be = d["Z_LGEXBE$"] * bs
    # 個別消費（地方）のうち扶助費の単独事業分の0.5以外を差し引いたもの
    rest_cgvil = (0.9 * d["Z_LGEXPS"] + 0.9 * d["Z_LGEXPE"] - d["S_PMLPEBL"] + 0.8 * d["Z_LGEXCS"]
                  + 0.7 * d["Z_LGEXCE"] + 0.1 * sna["M_DEPL"] + w31med - 0.5 * otx)
    A = np.array([[0.5, 0.0], [0.5, ppts - w31med], [1.0, 0.0], [0.0, 1.0]])
    b = np.array([-sna["M_CGVIL"] - rest_cgvil,
                  -sna["M_BSSVL"] - sna["M_CSSVL"] - be,
                  0.3 * bs * 0.05, 1.0 * 50.0])
    A[2] *= 0.05
    A[3] *= 50.0
    res = lsq_linear(A, b, bounds=([0, 0], [bs, np.inf]))
    bst, bsh_ratio = res.x
    out["Z_LGEXBST"] = float(bst)
    out["Z_LGEXBSH"] = float(bs - bst)
    out["Z_LGEXBSH$"] = float(bsh_ratio)
    return out
