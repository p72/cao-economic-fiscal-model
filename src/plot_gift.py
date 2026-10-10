"""プレゼン用 1枚画像（iPad Pro 12.9 横 2732×2048px）: 消費税5%と同額の国民一律給付金シナリオ.
出力: output/gift_scenario.png（データは src/gift.py と src/ctax5.py の output/gift_scenario.csv、output/ctax5_scenario.csv）
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GIFT, CTAX, OUT = (ROOT / "output" / f for f in ("gift_scenario.csv", "ctax5_scenario.csv", "gift_scenario.png"))
_JP = ["Noto Sans JP", "Noto Sans CJK JP", "IPAPGothic", "IPAGothic", "IPAexGothic"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED, GRID, BG, PUBC = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff", "#8a8986"
CASES = {"kako": ("過去投影ケース", "#2a78d6"), "seicho": ("成長移行ケース", "#eb6834"),
         "koseicho": ("高成長実現ケース", "#1baf7a")}

g = pd.read_csv(GIFT)
x = pd.read_csv(CTAX)
b = g[g.scen == "base"].set_index(["case", "year"])
c = g[g.scen == "gift"].set_index(["case", "year"])
xb = x[x.scen == "base"].set_index(["case", "year"])
xc = x[x.scen == "cut"].set_index(["case", "year"])
for d in (b, c, xb, xc):
    d["rgdp_t"] = d.rgdp / 1000
DEV = {"rgdp_dev": (c.rgdp / b.rgdp - 1) * 100, "rw_dev": (c.rw / b.rw - 1) * 100}
XDEV = {"rgdp_dev": (xc.rgdp / xb.rgdp - 1) * 100, "rw_dev": (xc.rw / xb.rw - 1) * 100}
per = c.gift * 1e12 / (c["pop"] * 1e4) / 1e4      # 一人当たり（万円/年）

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


yrs = list(range(2027, 2036))


def rng(v, nd=0):
    lo, hi = f"{min(v):.{nd}f}", f"{max(v):.{nd}f}"
    return f"約{lo}" if lo == hi else f"{lo}〜{hi}"

pmin, pmax = per.loc[(slice(None), yrs)].min(), per.loc[(slice(None), yrs)].max()
fig.text(0.03, 0.965, "消費税5%と同じ額を国民に一律給付したら　中長期試算（2026年1月）の3ケースで試算", fontsize=15,
         color=INK, weight="bold", va="center")
fig.text(0.03, 0.935, f"2027年度から毎年、消費税を5%に下げたときの減収額（{c.gift.loc[(slice(None), yrs)].min():.0f}〜"
         f"{c.gift.loc[(slice(None), yrs)].max():.0f}兆円、一人{pmin:.0f}〜{pmax:.0f}万円）を国の歳出で家計に給付。"
         "財源は国債。実質の政府支出は給付なしと同じ。　実線：給付　点線：給付なし　破線（乖離率）：消費税5%",
         fontsize=8.5, color=MUTED, va="center")

dg = [DEV["rgdp_dev"].loc[(cs, t)] for cs in CASES for t in yrs]
xg = [XDEV["rgdp_dev"].loc[(cs, t)] for cs in CASES for t in yrs]
drw = [DEV["rw_dev"].loc[(cs, t)] for cs in CASES for t in yrs]
xrw = [XDEV["rw_dev"].loc[(cs, t)] for cs in CASES for t in yrs]
ddebt = [c.loc[(cs, 2035)].debt - b.loc[(cs, 2035)].debt for cs in CASES]
xdebt = [xc.loc[(cs, 2035)].debt - xb.loc[(cs, 2035)].debt for cs in CASES]
fig.text(0.03, 0.902, f"ポイント　実質GDPの押し上げは消費税5%とほぼ同じ（給付{min(dg):.1f}〜{max(dg):.1f}%、減税{min(xg):.1f}〜{max(xg):.1f}%）。"
         f"物価を下げないので実質賃金の押し上げは約{sum(drw) / len(drw):.1f}%（減税は約{sum(xrw) / len(xrw):.0f}%）にとどまり、"
         f"2035年度の公債等残高は対GDP比{rng(ddebt)}pt高くなる（減税は{rng(xdebt)}pt）。",
         fontsize=8.6, color=INK, va="center",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#eef4fc", edgecolor="none"))


def panel(rect, title, col, diff=False, zero=False):
    ax = fig.add_axes(rect)
    style(ax)
    if zero:
        ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvspan(2026.5, 2035.5, color="#f6f6f4", lw=0, zorder=0)
    for cs, (name, colr) in CASES.items():
        if diff:
            y = XDEV[col].loc[cs]
            ax.plot(y.index, y.values, color=colr, lw=1.1, ls=(0, (4, 2)), alpha=0.8)
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
    [("実質GDP（兆円）", "rgdp_t", False, False), ("実質GDP（給付なしからの乖離率、%）", "rgdp_dev", True, True),
     ("消費者物価上昇率（%）", "cpi_g", False, True), ("名目賃金上昇率（%）", "w_g", False, False)],
    [("実質賃金（給付なしからの乖離率、%）", "rw_dev", True, True), ("家計可処分所得（名目、兆円）", "ydv", False, False),
     ("基礎的財政収支（PB、対GDP比、%）", "pb", False, True), ("公債等残高（対GDP比、%）", "debt", False, False)],
]
gx0, gdx, gw, gh = 0.055, 0.24, 0.195, 0.2
for r, row_ in enumerate(PANELS):
    for k, (title, col, diff, zero) in enumerate(row_):
        ax = panel([gx0 + k * gdx, 0.635 - r * 0.29, gw, gh], title, col, diff, zero)
        if r == 0 and k == 0:
            ax.legend(loc="upper left", fontsize=7.5, frameon=False)

# ---- 表: 2030・2035年度（給付の行の下に消費税5%の行） ----
tb = fig.add_axes([0.03, 0.045, 0.94, 0.225])
tb.axis("off")
tb.set_xlim(0, 1)
tb.set_ylim(0, 1)
tb.text(0, 1.07, "2030年度・2035年度の姿　給付（給付なし）、灰色の行は消費税5%", fontsize=10.5, color=INK, va="top")
COLS = [("rgdp_t", "実質GDP\n（兆円）", 0), ("rw_dev", "実質賃金\n乖離率（%）", 1), ("cpi_g", "消費者物価\n上昇率（%）", 1),
        ("pb", "PB\n対GDP比（%）", 1), ("debt", "公債等残高\n対GDP比（%）", 1)]
YRS = (2030, 2035)
x0, cw = 0.17, 0.0825
yh, rh = 0.80, 0.115
for j, yr in enumerate(YRS):
    xs = x0 + j * len(COLS) * cw
    tb.text(xs + len(COLS) * cw / 2, 0.95, f"{yr}年度", ha="center", va="center", fontsize=9.5, color=INK, weight="bold")
    tb.plot([xs + 0.01, xs + len(COLS) * cw - 0.01], [0.91, 0.91], color=MUTED, lw=0.7)
    for k, (_, lab, _) in enumerate(COLS):
        tb.text(xs + k * cw + cw / 2, yh, lab, ha="center", va="center", fontsize=7.8, color=INK, linespacing=1.1)
for i, (cs, (name, colr)) in enumerate(CASES.items()):
    for sub, (cc, bb, dv, lab, fs, ink) in enumerate(((c, b, DEV, name, 9, INK), (xc, xb, XDEV, "　消費税5%", 7.8, PUBC))):
        y = yh - 0.1 - rh * (2 * i + sub + 0.5)
        if sub == 0:
            tb.add_patch(plt.Rectangle((0, y - rh * 1.5), 1, rh * 2, color="#f4f4f2" if i % 2 == 0 else BG, lw=0))
            tb.plot([0.005, 0.02], [y, y], color=colr, lw=3)
        tb.text(0.028, y, lab, va="center", fontsize=fs, color=ink)
        for j, yr in enumerate(YRS):
            for k, (col, _, nd) in enumerate(COLS):
                xcen = x0 + (j * len(COLS) + k) * cw + cw / 2
                if col in dv:
                    tb.text(xcen, y, f"{dv[col].loc[(cs, yr)]:+.{nd}f}", ha="center", va="center", fontsize=fs + 0.5,
                            color=ink, weight="bold")
                else:
                    tb.text(xcen + 0.006, y, f"{cc.loc[(cs, yr)][col]:.{nd}f}", ha="right", va="center",
                            fontsize=fs + 0.5, color=ink, weight="bold")
                    if sub == 0:
                        tb.text(xcen + 0.008, y, f"（{bb.loc[(cs, yr)][col]:.{nd}f}）", ha="left", va="center",
                                fontsize=7.8, color=PUBC)

fig.text(0.03, 0.01, "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）。給付なしの経路は同試算の3ケースを"
         "経済財政モデル（2026年度版）の Python 再現（github.com/p72/cao-economic-fiscal-model、財政ブロック移植版）で"
         "作り直したもの。\n給付・減税は同モデルによる試算で、内閣府の試算ではない。給付は国の一般会計の歳出（その他一般歳出）に計上し、"
         "SNA では家計への現金の社会給付とした。賃金は一人当たり、実質賃金は名目賃金を消費者物価で割ったもの。",
         fontsize=6.5, color=MUTED)

fig.savefig(OUT, dpi=DPI, facecolor=BG)
print(OUT)
