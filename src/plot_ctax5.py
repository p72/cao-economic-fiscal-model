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
b = b.assign(rgdp_t=b.rgdp / 1000)
c = c.assign(rgdp_t=c.rgdp / 1000)
dev = ((c.rgdp / b.rgdp - 1) * 100).rename("rgdp_dev")
rwdev = ((c.rw / b.rw - 1) * 100).rename("rw_dev")
DEV = {"rgdp_dev": dev, "rw_dev": rwdev}

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
dgl = [c.loc[(cs, t)].rgdp_t - b.loc[(cs, t)].rgdp_t for cs in CASES for t in yrs]
drw = [rwdev.loc[(cs, t)] for cs in CASES for t in yrs]
fig.text(0.03, 0.902, f"ポイント　実質GDPは{min(dg):.1f}〜{max(dg):.1f}%（{min(dgl):.0f}〜{max(dgl):.0f}兆円）、"
         f"実質賃金は約{sum(drw) / len(drw):.0f}%押し上がる。一方、消費税収は国・地方で毎年{min(dtax):.0f}〜{max(dtax):.0f}兆円減り、"
         f"PBは対GDP比{min(dpb):.1f}〜{max(dpb):.1f}pt悪化、2035年度の公債等残高は対GDP比{min(ddebt):.0f}〜{max(ddebt):.0f}pt高くなる。",
         fontsize=9, color=INK, va="center",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#eef4fc", edgecolor="none"))


def panel(rect, title, col, diff=False, zero=False):
    ax = fig.add_axes(rect)
    style(ax)
    if zero:
        ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvspan(2026.5, 2035.5, color="#f6f6f4", lw=0, zorder=0)
    for cs, (name, colr) in CASES.items():
        if diff:
            y = DEV[col].loc[cs]
            ax.plot(y.index, y.values, color=colr, lw=2, marker="o", ms=2.5, label=name)
        else:
            yb, yc = b.loc[cs][col], c.loc[cs][col]
            ax.plot(yb.index, yb.values, color=colr, lw=1.2, ls=(0, (1.5, 1.5)))
            ax.plot(yc.index, yc.values, color=colr, lw=2, label=name)
    ax.set_xticks(range(2026, 2036, 1))
    ax.set_xticklabels([str(y) if y % 3 == 0 else "" for y in range(2026, 2036)])
    ax.set_xlim(2025.7, 2035.3)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK, pad=5)
    return ax


PANELS = [
    [("実質GDP（兆円）", "rgdp_t", False, False), ("実質GDP（減税なしからの乖離率、%）", "rgdp_dev", True, True),
     ("消費者物価上昇率（%）", "cpi_g", False, True), ("名目賃金上昇率（%）", "w_g", False, False)],
    [("実質賃金（減税なしからの乖離率、%）", "rw_dev", True, True), ("消費税収（国・地方、兆円）", "tciv", False, False),
     ("基礎的財政収支（PB、対GDP比、%）", "pb", False, True), ("公債等残高（対GDP比、%）", "debt", False, False)],
]
gx0, gdx, gw, gh = 0.055, 0.24, 0.195, 0.2
for r, row_ in enumerate(PANELS):
    for k, (title, col, diff, zero) in enumerate(row_):
        ax = panel([gx0 + k * gdx, 0.635 - r * 0.29, gw, gh], title, col, diff, zero)
        if r == 0 and k == 0:
            ax.legend(loc="upper left", fontsize=7.5, frameon=False)

# ---- 表: 2030・2035年度 ----
tb = fig.add_axes([0.03, 0.05, 0.94, 0.215])
tb.axis("off")
tb.set_xlim(0, 1)
tb.set_ylim(0, 1)
tb.text(0, 1.02, "2030年度・2035年度の姿　減税（減税なし）", fontsize=10.5, color=INK, va="top")
COLS = [("rgdp_t", "実質GDP\n（兆円）", 0), ("rw_dev", "実質賃金\n乖離率（%）", 1), ("cpi_g", "消費者物価\n上昇率（%）", 1),
        ("pb", "PB\n対GDP比（%）", 1), ("debt", "公債等残高\n対GDP比（%）", 1)]
YRS = (2030, 2035)
x0, cw = 0.17, 0.0825
yh, rh = 0.76, 0.17
for j, yr in enumerate(YRS):
    xs = x0 + j * len(COLS) * cw
    tb.text(xs + len(COLS) * cw / 2, 0.93, f"{yr}年度", ha="center", va="center", fontsize=9.5, color=INK, weight="bold")
    tb.plot([xs + 0.01, xs + len(COLS) * cw - 0.01], [0.88, 0.88], color=MUTED, lw=0.7)
    for k, (_, lab, _) in enumerate(COLS):
        tb.text(xs + k * cw + cw / 2, yh, lab, ha="center", va="center", fontsize=7.8, color=INK, linespacing=1.1)
for i, (cs, (name, colr)) in enumerate(CASES.items()):
    y = yh - 0.12 - rh * (i + 0.5)
    if i % 2 == 0:
        tb.add_patch(plt.Rectangle((0, y - rh / 2), 1, rh, color="#f4f4f2", lw=0))
    tb.plot([0.005, 0.02], [y, y], color=colr, lw=3)
    tb.text(0.028, y, name, va="center", fontsize=9, color=INK)
    for j, yr in enumerate(YRS):
        for k, (col, _, nd) in enumerate(COLS):
            xc = x0 + (j * len(COLS) + k) * cw + cw / 2
            if col in DEV:
                tb.text(xc, y, f"{DEV[col].loc[(cs, yr)]:+.{nd}f}", ha="center", va="center", fontsize=9.5, color=INK,
                        weight="bold")
            else:
                tb.text(xc + 0.006, y, f"{c.loc[(cs, yr)][col]:.{nd}f}", ha="right", va="center", fontsize=9.5,
                        color=INK, weight="bold")
                tb.text(xc + 0.008, y, f"（{b.loc[(cs, yr)][col]:.{nd}f}）", ha="left", va="center", fontsize=7.8,
                        color=PUBC)

fig.text(0.03, 0.01, "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）。減税なしの経路は同試算の3ケースを"
         "経済財政モデル（2026年度版）の Python 再現（github.com/p72/cao-economic-fiscal-model、財政ブロック移植版）で"
         "作り直したもの。\n減税は同モデルによる試算で、内閣府の試算ではない。賃金は一人当たり、実質賃金は名目賃金を消費者物価で割ったもの。",
         fontsize=6.5, color=MUTED)

fig.savefig(OUT, dpi=DPI, facecolor=BG)
print(OUT)
