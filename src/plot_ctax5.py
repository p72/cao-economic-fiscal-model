"""プレゼン用 1枚画像（iPad Pro 12.9 横 2732×2048px）: 消費税5%への減税シナリオ.
中長期試算（2026年1月）の3ケースそれぞれで、減税なし（再現経路）と減税（2027年度から標準・軽減とも5%）を比べる。
出力: output/ctax5_scenario.png（データは src/ctax5.py の output/ctax5_scenario.csv）
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "output" / "ctax5_scenario.csv"
OUT = ROOT / "output" / "ctax5_scenario.png"
_JP = ["Noto Sans JP", "Noto Sans CJK JP", "IPAPGothic", "IPAGothic", "IPAexGothic"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED, GRID, BG, PUBC = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff", "#8a8986"
CASES = {"kako": ("過去投影ケース", "#2a78d6"), "seicho": ("成長移行ケース", "#eb6834"),
         "koseicho": ("高成長実現ケース", "#1baf7a")}

df = pd.read_csv(CSV)
b = df[df.scen == "base"].set_index(["case", "year"])
c = df[df.scen == "cut"].set_index(["case", "year"])
dev = ((c.rgdp / b.rgdp - 1) * 100).rename("rgdp_dev")

W, H, DPI = 2732, 2048, 200
fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)


def style(ax):
    ax.set_facecolor(BG)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.7)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=7.5, length=2)


fig.text(0.03, 0.965, "消費税を5%に下げたら　中長期試算（2026年1月）の3ケースで試算", fontsize=15, color=INK,
         weight="bold", va="center")
fig.text(0.03, 0.935, "2027年度から恒久的に標準税率10%・軽減税率8%をともに5%へ。実質の政府支出は減税なしと同じ。"
         "　実線：減税　点線：減税なし", fontsize=9, color=MUTED, va="center")

yrs = list(range(2027, 2036))
dtax = [(b.loc[(cs, t)].tciv - c.loc[(cs, t)].tciv) for cs in CASES for t in yrs]
dpb = [(b.loc[(cs, t)].pb - c.loc[(cs, t)].pb) for cs in CASES for t in yrs]
ddebt = [(c.loc[(cs, 2035)].debt - b.loc[(cs, 2035)].debt) for cs in CASES]
dg = [dev.loc[(cs, t)] for cs in CASES for t in yrs]
fig.text(0.03, 0.902, f"ポイント　消費税収は国・地方で毎年{min(dtax):.0f}〜{max(dtax):.0f}兆円減り、PBは対GDP比で"
         f"{min(dpb):.1f}〜{max(dpb):.1f}pt悪化。実質GDPは{min(dg):.1f}〜{max(dg):.1f}%押し上げるが、"
         f"2035年度の公債等残高は対GDP比で{min(ddebt):.0f}〜{max(ddebt):.0f}pt高くなる。",
         fontsize=9.5, color=INK, va="center",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#eef4fc", edgecolor="none"))


def panel(rect, title, col, diff=False, zero=False):
    ax = fig.add_axes(rect)
    style(ax)
    if zero:
        ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvspan(2026.5, 2035.5, color="#f6f6f4", lw=0, zorder=0)
    for cs, (name, colr) in CASES.items():
        yb = b.loc[cs][col]
        if diff:
            y = dev.loc[cs]
            ax.plot(y.index, y.values, color=colr, lw=2, marker="o", ms=3, label=name)
        else:
            ax.plot(yb.index, yb.values, color=colr, lw=1.2, ls=(0, (1.5, 1.5)))
            yc = c.loc[cs][col]
            ax.plot(yc.index, yc.values, color=colr, lw=2, label=name)
    ax.set_xticks(range(2026, 2036, 1))
    ax.set_xticklabels([str(y) if y % 2 == 0 else "" for y in range(2026, 2036)])
    ax.set_xlim(2025.7, 2035.3)
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=6)
    return ax


gw, gh = 0.40, 0.235
a1 = panel([0.065, 0.625, gw, gh], "実質GDP（減税なしからの乖離率、%）", "rgdp", diff=True, zero=True)
a1.legend(loc="lower right", fontsize=8, frameon=False)
panel([0.565, 0.625, gw, gh], "消費者物価上昇率（%）", "cpi_g", zero=True)
panel([0.065, 0.315, gw, gh], "基礎的財政収支（PB、対GDP比、%）", "pb", zero=True)
panel([0.565, 0.315, gw, gh], "公債等残高（対GDP比、%）", "debt")

# ---- 表: 2030・2035年度 ----
tb = fig.add_axes([0.03, 0.05, 0.94, 0.2])
tb.axis("off")
tb.set_xlim(0, 1)
tb.set_ylim(0, 1)
tb.text(0, 1.02, "2030年度・2035年度の姿　減税（減税なし）", fontsize=10.5, color=INK, va="top")
COLS = [("rgdp_dev", "実質GDP\n乖離率（%）", 2), ("cpi_g", "消費者物価\n上昇率（%）", 1), ("pb", "PB\n対GDP比（%）", 1),
        ("debt", "公債等残高\n対GDP比（%）", 1)]
YRS = (2030, 2035)
x0, cw = 0.205, 0.0995
yh, rh = 0.76, 0.17
for j, yr in enumerate(YRS):
    xs = x0 + j * 4 * cw
    tb.text(xs + 2 * cw - 0.01, 0.93, f"{yr}年度", ha="center", va="center", fontsize=9.5, color=INK, weight="bold")
    tb.plot([xs + 0.005, xs + 4 * cw - 0.025], [0.88, 0.88], color=MUTED, lw=0.7)
    for k, (_, lab, _) in enumerate(COLS):
        tb.text(xs + k * cw + cw / 2 - 0.01, yh, lab, ha="center", va="center", fontsize=7.8, color=INK,
                linespacing=1.1)
for i, (cs, (name, colr)) in enumerate(CASES.items()):
    y = yh - 0.12 - rh * (i + 0.5)
    if i % 2 == 0:
        tb.add_patch(plt.Rectangle((0, y - rh / 2), 1, rh, color="#f4f4f2", lw=0))
    tb.plot([0.005, 0.02], [y, y], color=colr, lw=3)
    tb.text(0.028, y, name, va="center", fontsize=9, color=INK)
    for j, yr in enumerate(YRS):
        for k, (col, _, nd) in enumerate(COLS):
            xc = x0 + (j * 4 + k) * cw + cw / 2 - 0.01
            if col == "rgdp_dev":
                tb.text(xc, y, f"{dev.loc[(cs, yr)]:+.{nd}f}", ha="center", va="center", fontsize=9.5, color=INK,
                        weight="bold")
            else:
                tb.text(xc + 0.012, y, f"{c.loc[(cs, yr)][col]:.{nd}f}", ha="right", va="center", fontsize=9.5,
                        color=INK, weight="bold")
                tb.text(xc + 0.015, y, f"（{b.loc[(cs, yr)][col]:.{nd}f}）", ha="left", va="center", fontsize=8,
                        color=PUBC)

fig.text(0.03, 0.012, "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）。減税なしの経路は同試算の3ケースを"
         "経済財政モデル（2026年度版）の Python 再現（github.com/p72/cao-economic-fiscal-model、財政ブロック移植版）で"
         "作り直したもの。減税は同モデルによる試算で、内閣府の試算ではない。", fontsize=7, color=MUTED)

fig.savefig(OUT, dpi=DPI, facecolor=BG)
print(OUT)
