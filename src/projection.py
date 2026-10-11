"""内閣府「中長期の経済財政に関する試算」（2026年1月）の主要計数表（資料35ページ）を、このモデルで作り直す.

資料: https://www5.cao.go.jp/keizai3/econome/r8chuuchouki2601.pdf （計数表「1.主要計数表」、付録1「詳細な前提」）

方法（財政ブロック移植版、calibrated）
1. 出発点は2024年度の実績。標準ケースは、実質ゼロ成長で物価だけが各ケースのGDPデフレーター変化率（過去投影0.7%、
   成長移行・高成長実現1.6%）で伸びる経路（baseline.py の proj_kako・proj_seicho）とし、各式の誤差項（アドファクター）は
   この経路で式がちょうど成り立つ値（中立の値）にする。国債・地方債ブロックの変数を参照する定義式（残高の足し上げ、
   国債費など）の誤差項は、2024年度の値（実績との一定のずれ）で固定する。実質の成長は、下の前提（人口、労働参加率、TFP など）から
   モデルの式で決まる。物価の基調だけは資料のケースに合わせている（資料に誤差項の置き方が書かれていないため）。
2. マクロの項目は全期間、資料の値に合うように対応する式の誤差項を決める（目標 ← 調整する式）。
   潜在成長率 ← 潜在GDP、実質GDP成長率 ← 民間消費、消費者物価上昇率 ← 消費者物価、GDPデフレーター変化率 ← 輸出デフレーター、
   完全失業率 ← 失業率、賃金上昇率 ← 一人当たり賃金、名目長期金利 ← 長期金利、短期金利 ← 短期金利（資料にないので
   長期金利 − 2024年度の長短金利差）。
3. 財政は、資料の「財政の詳細計数表」の予算ベースの項目を与え、SNA ベースの基礎的財政収支と公債等残高をモデルで計算する。
   与える項目（目標 ← 調整する変数）：国の基礎的財政収支対象経費 ← その他一般歳出の調整項、地方の一般歳出（歳出から
   公債費・積立金を除く）← 補助費等の調整項、国の利払費 ← 利払費の式、地方の税収 ← 地方税収の式、地方交付税等 ← 地方交付税
   交付金等の式。2025・2026年度は、歳出の代わりに国・地方の基礎的財政収支を合わせ、国の税収（所得税の調整項）と
   公債等残高比（普通国債残高の式）も合わせる。2026年度の歳出のモデルと資料の差（補正予算の基金からの支出とみなす）は、
   2027年度以降毎年半分ずつ減るとする。高成長実現ケースは資料に財政の表がないので、成長移行ケースの値を賃金上昇率の差で
   延ばし（賃金上昇率の差の半分。歳出は物価・賃金上昇率並みに伸びるため）、利払費は成長移行ケースで決めた誤差項を使う（成長移行ケースを先に計算する）。
4. 前提（付録1）
   - 人口：国立社会保障・人口問題研究所「日本の将来推計人口（令和5年推計）」出生中位（死亡中位）の男女・5歳階級別人口
     （表1-9A、5年おきの値を対数線形で補間）の伸び率を、2024年度の実績に掛ける。
   - 労働参加率：2035年度の労働参加率（15歳以上人口に占める労働力人口）が資料の値（過去投影65.7%、成長移行66.9%）に
     なるように、男女・年齢別の労働力率を「1−労働力率」に比例して直線的に引き上げる（JILPT の推計の代わりの簡略な方法）。
   - ＴＦＰ上昇率：過去投影 0.6%、成長移行は2027年度から上がり2029年度に1.1%、高成長実現は2029年度に1.4%。
     高成長実現ケースの労働参加率は成長移行ケースと同じ。資料の高成長実現ケースは「経済財政モデル（2018年度版）」の
     乗数表を成長移行ケースに足して作られているが、ここではモデルで直接計算する。
   - 世界経済：成長率 2027〜2030年度 2.8→2.5%、以降 2.5%。物価上昇率 2027〜2030年度 1.7→1.9%、以降 1.9%
     （資料の幅の中で年ごとに置いた。輸出の伸びは世界経済成長率から1.4%pt差し引く。WORLD_G などの注を参照）。
   - 原油価格：2025・2026年度 68.1ドル、2027年度以降 73.7ドル（ドバイ）。
出力: output/chuuchouki_projection.csv（列: case, item, year, model, published）
"""
from __future__ import annotations

import copy
import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import baseline as BL
from solver import Solver
from spec import build

ROOT = Path(__file__).resolve().parents[1]
IPSS = ROOT / "data" / "raw" / "ipss" / "ipss2023_1-9A.xlsx"
YEARS = list(range(2025, 2036))
FIT_YEARS = (2025, 2026)
AGES = ["1519", "2024", "2529", "3034", "3539", "4044", "4549", "5054", "5559", "6064", "6569", "70OV"]

# 資料の主要計数表（2024～2035年度）
PUB = {
    "kako": {
        "潜在成長率": [0.5, 0.6, 0.8, 0.7, 0.6, 0.6, 0.6, 0.5, 0.5, 0.5, 0.4, 0.4],
        "実質GDP成長率": [0.5, 1.1, 1.3, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4, 0.4],
        "名目GDP成長率": [3.7, 4.2, 3.4, 1.6, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.1, 1.1],
        "名目GDP": [642.4, 669.2, 691.9, 703.1, 711.9, 720.5, 729.2, 737.9, 746.6, 755.2, 763.5, 771.7],
        "1人当たり実質GDP成長率": [0.9, 1.5, 1.8, 1.1, 1.1, 1.0, 1.0, 1.1, 1.1, 1.0, 1.0, 1.0],
        "賃金上昇率": [3.2, 3.2, 3.2, 1.6, 1.5, 1.4, 1.3, 1.2, 1.2, 1.2, 1.2, 1.2],
        "完全失業率": [2.5, 2.5, 2.4, 2.4, 2.5, 2.5, 2.5, 2.6, 2.6, 2.6, 2.6, 2.6],
        "消費者物価上昇率": [3.0, 2.6, 1.9, 1.4, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1],
        "GDPデフレーター変化率": [3.2, 3.1, 2.0, 1.1, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
        "名目長期金利": [1.1, 1.7, 2.1, 2.1, 2.0, 2.0, 2.0, 1.9, 1.9, 1.8, 1.8, 1.7],
        "基礎的財政収支（対GDP比）": [-1.8, -1.0, -0.1, 0.6, 0.9, 1.0, 1.0, 1.0, 0.9, 0.9, 0.9, 0.8],
        "公債等残高（対GDP比）": [193.5, 192.8, 186.6, 185.1, 184.4, 184.2, 184.1, 184.3, 184.8, 185.4, 186.3, 187.5],
    },
    "seicho": {
        "潜在成長率": [0.5, 0.6, 0.8, 1.1, 1.3, 1.5, 1.6, 1.6, 1.5, 1.5, 1.4, 1.4],
        "実質GDP成長率": [0.5, 1.1, 1.3, 1.1, 1.1, 1.3, 1.6, 1.6, 1.5, 1.5, 1.4, 1.4],
        "名目GDP成長率": [3.7, 4.2, 3.4, 2.6, 2.7, 2.9, 3.2, 3.2, 3.1, 3.0, 3.0, 3.0],
        "名目GDP": [642.4, 669.2, 691.9, 710.1, 729.2, 750.3, 774.4, 799.5, 824.6, 849.7, 875.4, 901.7],
        "1人当たり実質GDP成長率": [0.9, 1.5, 1.8, 1.6, 1.6, 1.8, 2.1, 2.2, 2.1, 2.1, 2.1, 2.0],
        "賃金上昇率": [3.2, 3.2, 3.2, 3.1, 3.0, 3.1, 3.1, 3.0, 3.0, 3.0, 3.0, 3.0],
        "完全失業率": [2.5, 2.5, 2.4, 2.4, 2.5, 2.5, 2.6, 2.6, 2.6, 2.6, 2.6, 2.6],
        "消費者物価上昇率": [3.0, 2.6, 1.9, 2.1, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "GDPデフレーター変化率": [3.2, 3.1, 2.0, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6],
        "名目長期金利": [1.1, 1.7, 2.1, 2.3, 2.5, 2.7, 2.9, 3.0, 3.1, 3.2, 3.3, 3.3],
        "基礎的財政収支（対GDP比）": [-1.8, -1.0, -0.1, 0.6, 1.1, 1.3, 1.4, 1.6, 1.7, 1.7, 1.8, 1.8],
        "公債等残高（対GDP比）": [193.5, 192.8, 186.6, 183.3, 180.1, 176.9, 173.5, 170.5, 167.9, 165.8, 164.0, 162.6],
    },
    "koseicho": {
        "潜在成長率": [0.5, 0.6, 0.8, 1.2, 1.5, 1.9, 1.9, 2.0, 1.9, 1.9, 1.9, 1.9],
        "実質GDP成長率": [0.5, 1.1, 1.3, 1.1, 1.2, 1.5, 1.8, 1.9, 1.9, 1.8, 1.8, 1.8],
        "名目GDP成長率": [3.7, 4.2, 3.4, 2.7, 2.8, 3.1, 3.5, 3.6, 3.5, 3.4, 3.4, 3.4],
        "名目GDP": [642.4, 669.2, 691.9, 710.5, 730.6, 753.6, 779.9, 807.8, 836.0, 864.5, 894.1, 924.5],
        "1人当たり実質GDP成長率": [0.9, 1.5, 1.8, 1.6, 1.7, 2.0, 2.4, 2.5, 2.5, 2.4, 2.4, 2.4],
        "賃金上昇率": [3.2, 3.2, 3.2, 3.2, 3.2, 3.4, 3.4, 3.4, 3.4, 3.4, 3.5, 3.5],
        "完全失業率": [2.5, 2.5, 2.4, 2.4, 2.5, 2.5, 2.6, 2.6, 2.6, 2.6, 2.6, 2.6],
        "消費者物価上昇率": [3.0, 2.6, 1.9, 2.1, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "GDPデフレーター変化率": [3.2, 3.1, 2.0, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6],
        "名目長期金利": [1.1, 1.7, 2.1, 2.4, 2.7, 3.0, 3.2, 3.3, 3.5, 3.6, 3.6, 3.7],
        "基礎的財政収支（対GDP比）": [-1.8, -1.0, -0.1, 0.6, 1.1, 1.4, 1.6, 1.8, 1.9, 2.1, 2.2, 2.3],
        "公債等残高（対GDP比）": [193.5, 192.8, 186.6, 183.2, 179.7, 176.1, 172.1, 168.4, 165.1, 162.3, 159.8, 157.6],
    },
}
ITEMS = list(PUB["kako"])

# 資料の「2.財政の詳細計数表」（資料36・37ページ、兆円）。歳出は政策の前提（2026年度は予算、以降は物価・賃金並み等）
# なのでモデルに与え、税収は2025・2026年度（補正後予算・予算政府案）だけ合わせる。高成長実現ケースは資料に表がないので、
# 成長移行ケースの歳出を賃金上昇率の差で延ばす
FISCAL_PUB = {
    "kako": {
        "国の税収": [75.2, 80.7, 83.7, 86.0, 87.9, 88.7, 89.7, 90.7, 91.8, 92.8, 93.8, 94.8],
        "国のPB対象経費": [97.7, 105.7, 91.4, 96.3, 97.4, 98.7, 99.9, 101.0, 102.3, 103.6, 104.9, 106.2],
        "地方の歳出": [115.5, 119.2, 113.2, 120.4, 122.1, 123.3, 124.7, 126.0, 127.5, 128.9, 130.5, 131.8],
        "国の基礎的財政収支": [-15.0, -14.7, -10.4, -7.3, -4.8, -4.1, -4.0, -4.0, -4.0, -4.0, -4.3, -4.6],
        "国のその他収入": [13.4, 12.5, 9.0, 8.2, 8.2, 8.3, 8.5, 8.7, 8.8, 9.0, 9.2, 9.3],
        "国の利払費": [7.9, 9.4, 13.0, 12.9, 14.5, 16.1, 17.4, 18.7, 19.8, 20.8, 21.6, 22.2],
        "地方の税収": [49.4, 51.5, 52.2, 52.8, 53.5, 54.1, 54.8, 55.4, 56.1, 56.7, 57.5, 58.0],
        "地方交付税等": [19.6, 20.2, 20.9, 22.2, 22.7, 22.9, 23.1, 23.3, 23.5, 23.7, 23.9, 24.1],
        "地方の税収等": [102.7, 108.1, 103.5, 110.4, 112.1, 113.2, 114.6, 115.9, 117.4, 118.7, 120.3, 121.5],
        "地方の普通会計の基礎的財政収支": [4.0, 3.4, 7.1, 9.7, 9.9, 9.5, 9.6, 9.6, 9.6, 9.5, 9.6, 9.4],
        "地方の基礎的財政収支": [3.6, 7.8, 9.5, 11.1, 11.6, 11.3, 11.2, 11.1, 11.0, 10.8, 10.8, 10.7],
    },
    "seicho": {
        "国の税収": [75.2, 80.7, 83.7, 87.1, 90.5, 93.1, 96.0, 99.1, 102.1, 105.2, 108.3, 111.6],
        "国のPB対象経費": [97.7, 105.7, 91.4, 97.1, 99.2, 101.8, 104.4, 107.0, 109.8, 112.8, 116.0, 119.2],
        "地方の歳出": [115.5, 119.2, 113.2, 121.6, 124.8, 128.0, 131.4, 135.0, 138.8, 142.6, 146.6, 150.7],
        "国の基礎的財政収支": [-15.0, -14.7, -10.4, -7.0, -4.2, -2.8, -2.0, -1.2, -0.5, 0.1, 0.5, 0.8],
        "国のその他収入": [13.4, 12.5, 9.0, 8.2, 8.3, 8.6, 9.0, 9.3, 9.7, 10.1, 10.4, 10.8],
        "国の利払費": [7.9, 9.4, 13.0, 13.1, 15.2, 17.4, 19.7, 22.1, 24.6, 27.2, 29.6, 31.8],
        "地方の税収": [49.4, 51.5, 52.2, 53.5, 54.9, 56.5, 58.2, 60.0, 61.8, 63.5, 65.4, 67.2],
        "地方交付税等": [19.6, 20.2, 20.9, 22.5, 23.4, 24.1, 24.8, 25.5, 26.2, 27.0, 27.8, 28.6],
        "地方の税収等": [102.7, 108.1, 103.5, 111.6, 114.8, 117.9, 121.4, 125.0, 128.7, 132.5, 136.5, 140.6],
        "地方の普通会計の基礎的財政収支": [4.0, 3.4, 7.1, 10.0, 10.6, 11.0, 11.7, 12.6, 13.4, 14.2, 15.0, 15.8],
        "地方の基礎的財政収支": [3.6, 7.8, 9.5, 11.5, 12.2, 12.6, 13.1, 13.7, 14.2, 14.7, 15.1, 15.4],
    },
}


def _scaled_koseicho() -> dict:
    w_s, w_k = PUB["seicho"]["賃金上昇率"], PUB["koseicho"]["賃金上昇率"]
    ratio, r = [], 1.0
    for k in range(len(w_s)):
        if k > 2:
            # 歳出は「物価・賃金上昇率並み」に伸びる（資料の付録）。物価上昇率は2つのケースで同じなので、賃金上昇率の差の半分だけ
            # 余分に伸ばす（賃金の差をそのまま使うと、歳出が伸びすぎて基礎的財政収支が成長移行ケースより悪くなる）
            r *= 1 + (w_k[k] - w_s[k]) / 2 / 100
        ratio.append(r)
    out = {k: [x * q for x, q in zip(v, ratio)] for k, v in FISCAL_PUB["seicho"].items()}
    for k in ("国の税収", "国の基礎的財政収支", "地方の基礎的財政収支"):   # 2025・2026年度だけ使う（同じ値）
        out[k] = FISCAL_PUB["seicho"][k]
    out.pop("国の利払費")   # 金利が違うので賃金の比では延ばせない。成長移行ケースの利払費の誤差項を使う（run）
    return out


# 地方の一般歳出（歳出から公債費と積立金を除いたもの）= 税収等 − 普通会計における基礎的財政収支（資料の注４）
for _c in ("kako", "seicho"):
    FISCAL_PUB[_c]["地方の一般歳出"] = [a - b for a, b in zip(FISCAL_PUB[_c]["地方の税収等"],
                                                        FISCAL_PUB[_c]["地方の普通会計の基礎的財政収支"])]
FISCAL_PUB["koseicho"] = _scaled_koseicho()


def target(case: str, name: str, t: int) -> float:
    k = t - 2024
    if name == "短期金利":
        return PUB[case]["名目長期金利"][k] - SPREAD
    if name.endswith("の伸び率"):      # 歳出の伸び率（%）
        v = FISCAL_PUB[case][name.replace("の伸び率", "")]
        return (v[k] / v[k - 1] - 1) * 100
    return PUB[case][name][k] if name in PUB[case] else FISCAL_PUB[case][name][k]
CASE_NAMES = {"kako": "過去投影ケース", "seicho": "成長移行ケース", "koseicho": "高成長実現ケース"}

# 前提
# 成長移行・高成長実現は「今後３年程度を経て」（本文 p.2）到達するので、2027〜2029年度に等分で上げ、2029年度に到達する
TFP = {"kako": {t: 0.6 for t in YEARS},
       "seicho": {**{t: 0.6 for t in YEARS}, 2027: 0.77, 2028: 0.93, **{t: 1.1 for t in range(2029, 2036)}},
       "koseicho": {**{t: 0.6 for t in YEARS}, 2027: 0.87, 2028: 1.13, **{t: 1.4 for t in range(2029, 2036)}}}
LFR_2035 = {"kako": 65.7, "seicho": 66.9, "koseicho": 66.9}
LFR_2024_PUB = 63.4
# 世界経済（日本からの輸出ウェイトを勘案した主要10か国）。資料は2027〜2030年度を「年率2.5〜2.8%程度」「1.7〜1.9%程度」、
# 以降を2.5%・1.9%で横ばいとする。年ごとの値は資料にないので、IMF の見通しを輸出額のウェイトで平均した形（成長率は
# 年々下がり、物価上昇率は上がって2031年度以降の値につながる）に合わせて、資料の幅の中で置く（推定）
WORLD_G = {**{t: 2.5 for t in YEARS}, 2025: 2.8, 2026: 2.8, 2027: 2.8, 2028: 2.7, 2029: 2.6, 2030: 2.5}
WORLD_P = {**{t: 1.9 for t in YEARS}, 2025: 1.7, 2026: 1.7, 2027: 1.7, 2028: 1.8, 2029: 1.8, 2030: 1.9}
# 輸出の伸び = 世界経済成長率 − WORLD_G_BASE（資料にない推定）。2014→2024年度の日本の実質輸出の伸びは年2.06%
# （国民経済計算 2024年度確報）で、同じ期間の主要10か国の成長率を輸出額のウェイト（2024年、概数）で平均した値
# （IMF「世界経済見通し」の実績、暦年を年度に換算）は年3.44%なので、その差1.4%ptを差し引く
WORLD_G_BASE = 1.4
OIL = {t: (68.1 if t <= 2026 else 73.7) for t in YEARS}

# 2025・2026年度の目標（資料の値）と、調整する式の誤差項
MACRO_TARGETS = [
    ("潜在成長率", "M_GDPP"),                     # 潜在GDPの式（対数）の誤差項
    ("実質GDP成長率", "M_CP"),
    ("消費者物価上昇率", "M_CPIGA"),
    ("GDPデフレーター変化率", "M_PXGS"),
    ("完全失業率", "M_UR"),
    ("賃金上昇率", "M_W"),
    ("名目長期金利", "M_RGB"),
    ("短期金利", "M_RCO"),                       # 資料にない。長期金利 − 2024年度の長短金利差（下の SPREAD）
]
# 短期金利は資料にないので、長短金利差を2024年度の実績（新発10年国債利回り1.10% − 無担保コール0.23%）に保つ。
# テイラー・ルールのままだと短期金利が長期金利を上回り（逆イールド）、超長期債の上乗せ
# （上乗せの基準値 ×（長期 − 短期）/ 基準年度の長短金利差）が負になって、国債の利払費が小さく出るため
SPREAD = 1.10 - 0.23
# 2025・2026年度: マクロ＋国・地方の基礎的財政収支（国はその他一般歳出、地方は補助費等（一般分）の調整項）、
# 国の税収（所得税の調整項）、公債等残高比（普通国債残高の式の誤差項）を資料に合わせる。
# 資料の2026年度の歳出は補正予算のない予算の水準で、補正予算の多くは基金を通じて翌年度以降に支出されるため、
# 歳出の水準ではなく SNA ベースの基礎的財政収支に合わせる
# 地方の税収（地方税＋地方譲与税）と地方交付税等（国の一般会計から地方への交付）は、資料の財政の詳細計数表の値に
# 合わせる（全期間）。それぞれ合計の定義式（Z_TXL、Z_DST）の誤差項で調整する
LOCAL_TARGETS = [("地方の税収", "Z_TXL"), ("地方交付税等", "Z_DST")]
# 国の一般会計のその他収入と地方の税収等は合わせない。どちらも会計の上だけの項目で、合わせても SNA の
# 基礎的財政収支はほとんど変わらない（国はその他収入を下げると国債の発行が増えて残高がずれ、地方は積立金が変わるだけ）
# 国の利払費（一般会計の国債費のうち利払費）も資料に合わせる（全期間）。資料の利払費は予算の積算金利（市場の金利より
# 高め）によるので、国債ブロックの利払費（市場の金利）を上回る。差を利払費の式（Z_PINTBON）の誤差項で埋める。
# 高成長実現ケースは資料に表がないので、成長移行ケースで決めた誤差項をそのまま使う
INTEREST_TARGETS = [("国の利払費", "Z_PINTBON")]
# 2027年度以降は、国の一般会計のその他収入の2026年度からの増減も資料に合わせる。モデルの式は2024年度の特殊要因分
# （Z_REVOH2）まで名目GDPで伸ばすので資料より増え方が大きく、そのぶん国債の発行が減って公債等残高比が低く出る。
# 特殊要因による増減額（Z_REVOHADJ）で調整する。水準はモデルと資料で定義が違う（2024年度に約10兆円、2026年度に約15兆円の差）
# ので、2026年度の差を保つ。SNA には税外収入の数%しか入らないので、基礎的財政収支はほとんど動かない
OTHER_REV_TARGETS = [("国のその他収入", "Z_REVOHADJ")]
PINT_AF_FILE = ROOT / "data" / "processed" / "_pintbon_af_seicho.json"
TARGETS = MACRO_TARGETS + LOCAL_TARGETS + INTEREST_TARGETS + [("国の基礎的財政収支", "Z_ADJEXPX35"), ("地方の基礎的財政収支", "Z_ADJLGEXTG"),
                           ("国の税収", "Z_ADJTXAG"), ("公債等残高（対GDP比）", "Z_GBNML2")]
# 2027年度以降: マクロ＋歳出の水準（資料の財政の詳細計数表の国のPB対象経費・地方の歳出。補正予算を見込まない）。
# 2026年度の SNA の支出には補正予算（基金）からの支出が入っているので、伸び率ではなく水準に合わせる
FOLLOW_TARGETS = MACRO_TARGETS + LOCAL_TARGETS + INTEREST_TARGETS + OTHER_REV_TARGETS + [("国のPB対象経費", "Z_ADJEXPX35"), ("地方の一般歳出", "Z_ADJLGEXTG")]
DATA_CTRL = {"Z_ADJTXAG", "Z_ADJEXPX35", "Z_ADJLGEXTG", "Z_REVOHADJ"}   # 誤差項ではなく外生変数で調整するもの
KEEP_AF = {"Z_GBNML2"}      # 2027年度以降も2026年度の値のまま置く誤差項（残高の水準）


def _ipss_rows():
    """社人研の表1-9A を (年, 年齢階級の表記, 男, 女, 総数) の行にする（千人）."""
    import re
    for _, df in pd.read_excel(IPSS, sheet_name=None, header=None).items():
        year = None
        for _, row in df.iterrows():
            label = str(row[0]).strip().replace(" ", "").replace("　", "")
            mt = re.match(r"^\(\d+\).*?\((\d{4})\)年$", label)
            if mt:
                year = int(mt.group(1))
                continue
            if year is not None and pd.notna(row[1]) and label != "nan":
                yield year, label, float(row[2]), float(row[3]), float(row[1])


def ipss_population() -> dict[int, dict[tuple[str, str], float]]:
    """社人研の推計（5年おき）を、モデルの年齢区分（15〜19歳 … 70歳以上）× 男女に集計する（千人）."""
    out = {}
    for year, label, male, female, _ in _ipss_rows():
        if label in ("総数", "0～14", "15～64", "65+"):
            continue
        lo = 100 if label == "100+" else int(label.split("～")[0])
        if lo < 15:
            continue
        age = "70OV" if lo >= 70 else f"{lo:02d}{lo + 4:02d}"
        d = out.setdefault(year, {})
        d[(age, "M")] = d.get((age, "M"), 0.0) + male
        d[(age, "F")] = d.get((age, "F"), 0.0) + female
    return out


def ipss_totals() -> dict[int, dict[str, float]]:
    out = {}
    for year, label, _, _, total in _ipss_rows():
        key = {"総数": "total", "65+": "65+", "60～64": "6064"}.get(label)
        if key:
            out.setdefault(year, {})[key] = total
    return out


def interp(series: dict[int, float], t: int) -> float:
    """5年おきの値を対数線形で補間する."""
    ys = sorted(series)
    lo = max(y for y in ys if y <= t)
    hi = min(y for y in ys if y >= t)
    if lo == hi:
        return series[lo]
    w = (t - lo) / (hi - lo)
    return math.exp((1 - w) * math.log(series[lo]) + w * math.log(series[hi]))


def set_population(data: dict) -> None:
    pop = ipss_population()
    tot = ipss_totals()
    for age in AGES:
        for sex in ("M", "F"):
            s = {y: pop[y][(age, sex)] for y in pop}
            v = f"P_POP{age}{sex}"
            base = data[v][2024]
            for t in YEARS:
                data[v][t] = base * interp(s, t) / interp(s, 2024)
    s_tot = {y: tot[y]["total"] for y in tot}
    s65 = {y: tot[y]["65+"] for y in tot}
    s60 = {y: tot[y]["65+"] + tot[y]["6064"] for y in tot}
    for v, s in (("P_POP", s_tot), ("P_POP65OV", s65), ("P_POP60OV", s60)):
        if v in data:
            base = data[v][2024]
            for t in YEARS:
                data[v][t] = base * interp(s, t) / interp(s, 2024)


def lf_rate(data: dict, t: int) -> float:
    lf = sum(data[f"P_POP{a}{s}"][t] * data[f"P_RLF{a}{s}"][t] for a in AGES for s in ("M", "F"))
    pop = sum(data[f"P_POP{a}{s}"][t] for a in AGES for s in ("M", "F"))
    return lf / pop * 100


def set_participation(data: dict, case: str) -> None:
    """2035年度の労働参加率が資料の値になるよう、男女・年齢別の労働力率を「1−率」に比例して直線的に上げる."""
    base = {(a, s): data[f"P_RLF{a}{s}"][2024] for a in AGES for s in ("M", "F")}
    target = lf_rate(data, 2024) + (LFR_2035[case] - LFR_2024_PUB)

    def apply(k: float) -> None:
        for t in YEARS:
            w = (t - 2024) / (2035 - 2024)
            for (a, s), r in base.items():
                data[f"P_RLF{a}{s}"][t] = r + k * w * (1 - r)

    lo, hi = 0.0, 0.5
    for _ in range(60):
        k = (lo + hi) / 2
        apply(k)
        if lf_rate(data, 2035) < target:
            lo = k
        else:
            hi = k
    apply((lo + hi) / 2)


def set_world(data: dict, case: str) -> None:
    tfp0 = data["M_TFP"][2024]
    acc = 0.0
    for t in YEARS:
        acc += TFP[case][t] / 100
        data["M_TFP"][t] = tfp0 + acc
        # 標準ケースは実質ゼロ成長で、輸出の式の誤差項はその経路（2024年度の世界経済成長率のまま輸出が横ばい）に
        # 合わせてあるので、標準ケースの値に「輸出の伸び」を足す
        data["MWE_GGDP"][t] = data["MWE_GGDP"][2024] + (WORLD_G[t] - WORLD_G_BASE) / 100
        data["MWE_WPI"][t] = data["MWE_WPI"][t - 1] * (1 + WORLD_P[t] / 100)
        data["MUS_WPI"][t] = data["MUS_WPI"][t - 1] * (1 + WORLD_P[t] / 100)
        data["M_POILD"][t] = OIL[t]


LG_OFFSET: dict = {}
# 2026年度の歳出の、モデル（SNA の基礎的財政収支に合わせた水準）と資料（補正予算を含まない予算）の差。
# 過去の補正予算による基金からの支出とみなし、2027年度以降は毎年 FUND_DECAY の割合で残るとする
GAP: dict = {}
# 資料の国の表で、SNA の基礎的財政収支と予算ベースの収支（税収＋その他収入−PB対象経費）の差は、2026年度 −11.7兆円、
# 2027年度 −5.2兆円、2028年度 −3.5〜−3.8兆円で、2029年度以降は −2.4兆円前後で落ち着く。落ち着いた値を上回る部分
# （基金からの支出）は2027年度に約3割、2028年度に約1割強残るので、毎年3割ずつ残るとする
FUND_DECAY = 0.3


def item_values(data: dict, t: int) -> dict[str, float]:
    g = lambda v: (data[v][t] / data[v][t - 1] - 1) * 100
    return {
        "潜在成長率": g("M_GDPP"),
        "実質GDP成長率": g("M_GDP"),
        "名目GDP成長率": g("M_GDPV"),
        "名目GDP": data["M_GDPV"][t] / 1000,
        "1人当たり実質GDP成長率": ((data["M_GDP"][t] / data["P_POP"][t]) / (data["M_GDP"][t - 1] / data["P_POP"][t - 1])
                              - 1) * 100,
        "賃金上昇率": g("M_W"),
        "完全失業率": data["M_UR"][t],
        "消費者物価上昇率": g("M_CPIG"),
        "GDPデフレーター変化率": g("M_PGDP"),
        "名目長期金利": data["M_RGB"][t],
        "基礎的財政収支（対GDP比）": data["M_PBGAGDPV"][t],
        "公債等残高（対GDP比）": data["Z_DEBTAGDP"][t],
        "国の税収": data["Z_REV1"][t] / 1000,
        "国のPB対象経費": data["Z_EXPOLICY"][t] / 1000,
        # 地方の歳出（普通会計）。モデルの Z_LGEXTC（形式収支を含む）と資料の定義の差は2024年度の差で一定とみなす
        # 地方の歳出は積立金（Z_LGEXTM）を除く。モデルでは歳入と歳出の差が積立金に入り、歳出の合計は歳入でほぼ決まるため
        "地方の歳出": data["Z_LGEXTC"][t] / 1000 - LG_OFFSET.get("v", 0.0),
        # 地方の一般歳出（公債費・積立金を除く）。モデルでは歳入と歳出の差が積立金（Z_LGEXTM）に入り、
        # 歳出の合計は歳入でほぼ決まるので、こちらを資料に合わせる
        "地方の一般歳出": (data["Z_LGEXTC"][t] - data["Z_LGEXTM"][t] - data["Z_CLB"][t]) / 1000 - LG_OFFSET.get("p", 0.0),
        "短期金利": data["M_RCO"][t],
        "国の利払費": data["Z_PINTBON"][t] / 1000,
        "国のその他収入": data["Z_REVOH"][t] / 1000 - LG_OFFSET.get("oh", 0.0),
        "地方の税収等": (data["Z_LGINTOTAL"][t] - data["Z_LGB"][t] - data["Z_RLGFND"][t] - data["Z_CF"][t]) / 1000
                    - LG_OFFSET.get("rev", 0.0),
        "地方の税収": (data["Z_TXL"][t] + data["Z_TTL"][t]) / 1000,
        "地方交付税等": data["Z_DST"][t] / 1000 - LG_OFFSET.get("dst", 0.0),
        "国のPB対象経費の伸び率": (data["Z_EXPOLICY"][t] / data["Z_EXPOLICY"][t - 1] - 1) * 100,
        "地方の歳出の伸び率": (data["Z_LGEXTC"][t] / data["Z_LGEXTC"][t - 1] - 1) * 100,
        "国の基礎的財政収支": data["M_PBC"][t] / 1000,
        "地方の基礎的財政収支": data["M_PBL"][t] / 1000,
    }


def fit_year(s: Solver, t: int, case: str, sweeps: int = 16, tol: float = 0.01, targets=None) -> None:
    """2025・2026年度: 目標の値になるよう、対応する式の誤差項（所得税・国債は調整項）を決める.

    各目標はほぼ対応する1つの調整項だけで動くので、目標を1つずつ割線法で合わせ、全体を何周か繰り返す。
    """
    targets = targets or TARGETS
    tgt = {name: target(case, name, t) + GAP.get(name, 0.0) * FUND_DECAY ** (t - 2026) for name, _ in targets}
    step0 = {"M_RGB": 0.1, "M_RCO": 0.1, "Z_PINTBON": 1000.0, "Z_TXL": 500.0, "Z_DST": 500.0, "Z_ADJTXAG": 2000.0, "Z_REVOHADJ": 1000.0, "Z_GBNML2": 10000.0, "M_GDPP": 0.002, "Z_ADJEXPX35": 2000.0,
             "Z_ADJLGEXTG": 2000.0}

    def get(v):
        return s.data[v][t] if v in DATA_CTRL else s.af[v][t]

    def put(v, x):
        if v in DATA_CTRL:
            s.data[v][t] = x
        else:
            s.af[v][t] = x

    def value(name, v, x):
        """調整項を x にして解き、目標との差を返す。解けないときは元に戻して None を返す."""
        snap = {k: col[t] for k, col in s.data.items() if t in col}
        old = get(v)
        put(v, x)
        try:
            solve(s, t)
        except (RuntimeError, ValueError, OverflowError, ZeroDivisionError):
            for k, x_ in snap.items():
                s.data[k][t] = x_
            put(v, old)
            return None
        return item_values(s.data, t)[name] - tgt[name]

    solve(s, t)
    for sweep in range(sweeps):
        worst = 0.0
        for name, v in targets:
            y0 = item_values(s.data, t)[name] - tgt[name]
            worst = max(worst, abs(y0))
            if abs(y0) < tol / 2:
                continue
            x0 = get(v)
            d = step0.get(v, 0.005) * (1 if y0 < 0 else -1)
            x1, y1 = x0 + d, None
            for _ in range(8):           # 解けないときは歩幅を半分にする
                y1 = value(name, v, x1)
                if y1 is not None:
                    break
                x1 = x0 + (x1 - x0) / 2
            if y1 is None:
                continue
            for _ in range(8):
                if abs(y1) < tol / 2 or y1 == y0:
                    break
                x2 = x1 - y1 * (x1 - x0) / (y1 - y0)
                lim = 4 * max(abs(x1 - x0), abs(d))     # 1回で動かす幅を抑える
                x2 = min(max(x2, x1 - lim), x1 + lim)
                y2 = None
                for _ in range(8):
                    y2 = value(name, v, x2)
                    if y2 is not None:
                        break
                    x2 = x1 + (x2 - x1) / 2
                if y2 is None:
                    break
                x0, y0, x1, y1 = x1, y1, x2, y2
        if worst < tol:
            break
    vals = item_values(s.data, t)
    print(f"  {t}年度の合わせ込み: 目標との差 " + "、".join(f"{n} {vals[n] - tgt[n]:+.2f}" for n, _ in targets), flush=True)


def follow_gap(s: Solver, t: int, case: str, tol: float = 0.005) -> None:
    """2027年度以降: GDPギャップの変化（実質成長率 − 潜在成長率）と名目長期金利が資料と同じになるよう、
    民間消費の式と長期金利の式の誤差項を決める（長期金利は FOLLOW_RATE のとき）."""
    k = t - 2024
    gap_target = PUB[case]["実質GDP成長率"][k] - PUB[case]["潜在成長率"][k]
    rate_target = PUB[case]["名目長期金利"][k]

    def gap_change():
        v = item_values(s.data, t)
        return v["実質GDP成長率"] - v["潜在成長率"] - gap_target

    solve(s, t)
    for _ in range(6):
        if FOLLOW_RATE:      # 長期金利の式は水準の式なので、ずれをそのまま誤差項に足す
            s.af["M_RGB"][t] += rate_target - s.data["M_RGB"][t]
            solve(s, t)
        y0 = gap_change()
        if abs(y0) < tol and (not FOLLOW_RATE or abs(s.data["M_RGB"][t] - rate_target) < tol):
            return
        x0 = s.af["M_CP"][t]
        x1 = x0 - 0.005 * (1 if y0 > 0 else -1)
        s.af["M_CP"][t] = x1
        solve(s, t)
        y1 = gap_change()
        for _ in range(8):
            if abs(y1) < tol or y1 == y0:
                break
            x2 = x1 - y1 * (x1 - x0) / (y1 - y0)
            x0, y0, x1 = x1, y1, x2
            s.af["M_CP"][t] = x1
            solve(s, t)
            y1 = gap_change()


VARIANT = {"kako": "proj_kako", "seicho": "proj_seicho", "koseicho": "proj_seicho"}
FOLLOW_MACRO = True  # 2027年度以降、マクロ経済の7項目（潜在成長率、実質成長率、物価、デフレーター、失業率、賃金、長期金利）を資料に合わせる
FOLLOW_RATE = True  # 2027年度以降、名目長期金利を資料に合わせる（長期金利の式の誤差項で調整）
FOLLOW_GAP = True  # 2027年度以降、GDPギャップの変化を資料に合わせる（消費の誤差項で調整）
DEBUG_DIR = None   # 途中の値を保存するフォルダ（調査用）
DECAY = 0.5   # 2025・2026年度に合わせた誤差項の、中立の値からのずれが毎年残る割合


def solve(s: Solver, t: int) -> None:
    """その年を解く。収束しないときは歩幅を小さくして解き直す."""
    try:
        s.solve_year(t, calibrate_pinned=False)
    except (RuntimeError, ValueError, OverflowError, ZeroDivisionError):
        s.solve_year(t, calibrate_pinned=False, omegas=(0.2,), max_iter=3000)


def run(case: str, mode: str = "calibrated") -> pd.DataFrame:
    m = build(mode, "port")
    with BL.out_path(mode, "port", VARIANT[case]).open("rb") as f:
        b = pickle.load(f)
    data, af = copy.deepcopy(b["data"]), copy.deepcopy(b["af"])
    # その他一般歳出（Z_EXPX35）のうち SNA の支出に使う Z_EXPX35E は、方程式リストに式がなく外生（ベースラインでは
    # Z_EXPX35 と同じ値）。このままでは国の歳出を動かしても SNA の基礎的財政収支が動かないので、
    # Z_EXPX35 の式の形（前年度の Z_EXPX35E − Z_ADJEXPX35E を伸ばす）に合う定義式を加える
    from spec import compile_eq
    m.eqs.append(compile_eq("Z_EXPX35E", "Z_EXPX35E=Z_EXPX35+Z_ADJEXPX35E"))
    m.meta["Z_EXPX35E"] = {"label": "（追加: その他一般歳出の SNA 用）", "block": "fiscal", "estimated": False}
    af["Z_EXPX35E"] = {}
    # 国債・地方債ブロックの変数を参照する定義式（残高の足し上げ、国債費、公債費など）の誤差項は、2024年度の値（実績との
    # 一定のずれ）で固定する。標準ケースでは国債・地方債ブロックだけを前向きに解き直したので、受け取る側の定義式の誤差項に
    # 合成の経路とのずれが入り、年々大きくなっているため（例: 普通国債残高 Z_GBNML の足し上げ）
    import bond_port
    bond_vars = bond_port.endogenous()
    for eq in m.eqs:
        if (eq.name not in bond_vars and not m.meta.get(eq.name, {}).get("estimated", False)
                and set(eq.vars) & bond_vars and 2024 in af[eq.name]):
            for t in YEARS:
                af[eq.name][t] = af[eq.name][2024]
    neutral = {v: dict(af[v]) for _, v in TARGETS if v not in DATA_CTRL}
    LG_OFFSET["v"] = data["Z_LGEXTC"][2024] / 1000 - FISCAL_PUB[case]["地方の歳出"][0]
    LG_OFFSET["oh"] = data["Z_REVOH"][2024] / 1000 - FISCAL_PUB[case]["国のその他収入"][0]
    LG_OFFSET["rev"] = ((data["Z_LGINTOTAL"][2024] - data["Z_LGB"][2024] - data["Z_RLGFND"][2024] - data["Z_CF"][2024])
                        / 1000 - FISCAL_PUB[case]["地方の税収等"][0])
    LG_OFFSET["dst"] = data["Z_DST"][2024] / 1000 - FISCAL_PUB[case]["地方交付税等"][0]
    LG_OFFSET["p"] = ((data["Z_LGEXTC"][2024] - data["Z_LGEXTM"][2024] - data["Z_CLB"][2024]) / 1000
                      - FISCAL_PUB[case]["地方の一般歳出"][0])
    GAP.clear()
    set_population(data)
    set_participation(data, case)
    set_world(data, case)
    s = Solver(m, data, af)
    fit_targets, follow_targets = TARGETS, FOLLOW_TARGETS
    if "国の利払費" not in FISCAL_PUB[case]:
        import json
        pint = {int(k): v for k, v in json.loads(PINT_AF_FILE.read_text(encoding="utf-8")).items()}
        for t in YEARS:
            af["Z_PINTBON"][t] = pint[t]
        fit_targets = [x for x in TARGETS if x not in INTEREST_TARGETS]
        follow_targets = [x for x in FOLLOW_TARGETS if x not in INTEREST_TARGETS]
    for t in YEARS:
        if t in FIT_YEARS:
            fit_year(s, t, case, targets=fit_targets)
            if t == 2026:
                LG_OFFSET["oh"] = data["Z_REVOH"][t] / 1000 - FISCAL_PUB[case]["国のその他収入"][t - 2024]
                vals = item_values(data, t)
                for name, _ in FOLLOW_TARGETS:
                    if name in FISCAL_PUB[case]:
                        GAP[name] = vals[name] - target(case, name, t)
                print("  2026年度の歳出のモデルと資料の差: " + "、".join(f"{k} {v:+.1f}" for k, v in GAP.items()), flush=True)
        else:
            k = DECAY ** (t - 2026)
            for _, v in fit_targets:
                if v in KEEP_AF:
                    af[v][t] = af[v][2026]
                elif v in DATA_CTRL:        # 所得税の調整項は2026年度の名目GDP比を保つ
                    data[v][t] = data[v][2026] / data["M_GDPV"][2026] * data["M_GDPV"][t - 1]
                else:
                    af[v][t] = neutral[v][t] + k * (af[v][2026] - neutral[v][2026])
            if FOLLOW_MACRO:                 # 前年度の値から始めて、マクロの7項目と歳出を資料に合わせる
                for _, v in follow_targets:
                    if v in DATA_CTRL:
                        data[v][t] = data[v][t - 1]
                    else:
                        af[v][t] = af[v][t - 1]
                fit_year(s, t, case, targets=follow_targets)
            elif FOLLOW_GAP:
                follow_gap(s, t, case)
            else:
                solve(s, t)
        if DEBUG_DIR:
            with (Path(DEBUG_DIR) / f"proj_state_{case}.pkl").open("wb") as fdbg:
                pickle.dump({"data": data, "af": af, "t": t}, fdbg)
        print(f"{case} {t}: 実質 {item_values(data, t)['実質GDP成長率']:.2f}% 名目GDP {data['M_GDPV'][t] / 1000:.1f}兆円 "
              f"PB {data['M_PBGAGDPV'][t]:.2f} 残高比 {data['Z_DEBTAGDP'][t]:.1f}", flush=True)
    if DEBUG_DIR:
        with (Path(DEBUG_DIR) / f"proj_state_{case}.pkl").open("wb") as f:
            pickle.dump({"data": data, "af": af}, f)
    if case == "seicho":   # 高成長実現ケースで使う利払費の誤差項
        import json
        PINT_AF_FILE.write_text(json.dumps({t: af["Z_PINTBON"][t] for t in YEARS}), encoding="utf-8")
    rows = []
    for t in [2024] + YEARS:
        vals = item_values(data, t)
        for k_ in ITEMS:
            # 2024年度は実績。前年度（2023年度）の実績をモデルに入れていないので、伸び率は資料の値を表示する
            mv = PUB[case][k_][0] if t == 2024 else vals[k_]
            rows.append((case, k_, t, mv, PUB[case][k_][t - 2024]))
    return pd.DataFrame(rows, columns=["case", "item", "year", "model", "published"])


def main(mode: str = "calibrated", cases=tuple(PUB)) -> pd.DataFrame:
    out = ROOT / "output" / "chuuchouki_projection.csv"
    res = pd.concat([run(c, mode) for c in cases], ignore_index=True)
    if out.exists() and len(cases) < len(PUB):   # 1ケースだけ計算したときは、ほかのケースの結果を残す
        old = pd.read_csv(out)
        res = pd.concat([old[~old["case"].isin(cases)], res], ignore_index=True)
    res.to_csv(out, index=False)
    print(f"→ {out}")
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=list(PUB), help="1つのケースだけ計算する")
    a = ap.parse_args()
    main(cases=(a.case,) if a.case else tuple(PUB))
