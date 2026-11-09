"""パート2の図：2026年7月の中長期試算（2040年度まで）の国・地方・社会保障基金・一般政府の財政収支."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = ["Noto Sans JP", "IPAPGothic", "IPAGothic"]
plt.rcParams["axes.unicode_minus"] = False
HERE = Path(__file__).resolve().parent
df = pd.read_csv(HERE / "chuuchouki2607_balance.csv")
CASES = ["成長戦略実現ケース①", "成長戦略実現ケース②", "現状投影ケース"]
COL = {"成長戦略実現ケース①": "#d6452a", "成長戦略実現ケース②": "#1a9e5f", "現状投影ケース": "#2a63c4"}
C_KUNI, C_CHIHO, C_SSF = "#c8553d", "#e8a33d", "#2bb07f"
INK, MUTED, GRID = "#111111", "#555555", "#e2e2e2"


def g(case, col):
    d = df[df.case == case].sort_values("year")
    return d.year.values, d[col].values


def style(ax, title):
    ax.set_title(title, fontsize=11, color=INK, loc="left")
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.axvspan(2026.5, 2040.5, color="#f3f3f3", zorder=0)
    ax.set_xlim(2023.4, 2040.6)
    ax.set_xticks(range(2024, 2041, 2))
    ax.tick_params(labelsize=8.5, colors=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


fig, axes = plt.subplots(2, 3, figsize=(17, 10.5))
# (1) 一般政府と国・地方（対GDP比）
ax = axes[0, 0]
for c in CASES:
    y, gg = g(c, "部門別収支_一般政府（対GDP比）")
    _, kl = g(c, "国・地方財政収支（含む）")
    _, gdp = g(c, "名目GDP")
    ax.plot(y, gg, color=COL[c], lw=2.4, marker="o", ms=3.5, label=f"{c}　一般政府")
    ax.plot(y, kl / gdp * 100, color=COL[c], lw=1.0, label=f"{c}　国・地方")
style(ax, "財政収支（対GDP比、％）　太線：一般政府　細線：国・地方")
ax.legend(fontsize=7.5, frameon=False, loc="lower left")
# (2)(3) 内訳（兆円）
for ax, c in ((axes[0, 1], "成長戦略実現ケース①"), (axes[0, 2], "現状投影ケース")):
    y, kuni = g(c, "国財政収支（含む）")
    _, chiho = g(c, "地方財政収支（含む）")
    _, ssf = g(c, "社会保障基金財政収支")
    _, gg = g(c, "一般政府財政収支")
    ax.bar(y, kuni, color=C_KUNI, width=0.7, label="国")
    ax.bar(y, chiho, color=C_CHIHO, width=0.7, label="地方")
    ax.bar(y, ssf, bottom=chiho, color=C_SSF, width=0.7, label="社会保障基金")
    ax.plot(y, gg, color="black", lw=2, marker="o", ms=3.5, label="一般政府（合計）")
    style(ax, f"内訳（兆円）　{c}")
    ax.set_ylim(-60, 42)
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", ncol=4)
# (4) PBと財政収支（国・地方、除くベース、対GDP比）
ax = axes[1, 0]
for c in CASES:
    y, pb = g(c, "国・地方基礎的財政収支（除く）")
    _, fb = g(c, "国・地方財政収支（除く）")
    _, gdp = g(c, "名目GDP")
    ax.plot(y, pb / gdp * 100, color=COL[c], lw=2.2, label=f"{c}　PB")
    ax.plot(y, fb / gdp * 100, color=COL[c], lw=2.2, ls=":", label=f"{c}　財政収支")
style(ax, "国・地方の PB と財政収支（対GDP比、％）")
ax.legend(fontsize=7.2, frameon=False, loc="lower left", ncol=2)
# (5) 純利払費
ax = axes[1, 1]
for c in CASES:
    y, ni = g(c, "国・地方純利払費（除く）")
    ax.plot(y, ni, color=COL[c], lw=2.2, marker="o", ms=3, label=c)
style(ax, "国・地方の純利払費（PB − 財政収支、兆円）")
ax.legend(fontsize=8, frameon=False, loc="upper left")
# (6) 社会保障基金
ax = axes[1, 2]
for c in CASES:
    y, s = g(c, "社会保障基金財政収支")
    ax.plot(y, s, color=COL[c], lw=2.2, marker="o", ms=3, label=c)
style(ax, "社会保障基金の財政収支（兆円）")
ax.set_ylim(0, 22)
ax.legend(fontsize=8, frameon=False, loc="lower right")

fig.suptitle("日本の財政は黒字になるのか（パート2）　2026年7月の中長期試算で、2040年度までの財政収支を見る",
             x=0.015, ha="left", fontsize=16, color=INK, y=0.985)
fig.text(0.015, 0.935,
         "国・地方は試算の「財政の詳細計数表」、一般政府は付録2の部門別収支（対GDP比）。社会保障基金＝一般政府−国・地方（復旧・復興対策等を含んだベース）で求めた。"
         "財政収支は国民経済計算の純貸出（＋）／純借入（−）。網かけは推計期間。",
         fontsize=9.5, color=MUTED)
fig.text(0.015, 0.012,
         "資料：内閣府「中長期の経済財政に関する試算」（2026年7月30日、経済財政諮問会議 資料2-2）。一般政府は対GDP比（0.1%刻み）に名目GDPを掛けて兆円にしたので、"
         "一般政府と社会保障基金の兆円の値には±0.5兆円程度の丸めの誤差がある。\n"
         "PB・財政収支・純利払費（左下・中下）は復旧・復興対策、GX対策、AI・半導体支援の経費と財源を除いたベース。内訳（上段）は含んだベース。",
         fontsize=8, color=MUTED)
plt.tight_layout(rect=[0, 0.04, 1, 0.925], h_pad=2.5)
plt.savefig(HERE / "04-2_chart_surplus_2040.png", dpi=150, facecolor="white")
