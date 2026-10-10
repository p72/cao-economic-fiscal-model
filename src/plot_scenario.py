"""scenario.py の結果を図にする.

py src/plot_scenario.py             → output/scenario_fiscal.png（calibrated）
py src/plot_scenario.py --compare   → output/scenario_fiscal_compare.png（実線 calibrated、破線 faithful）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "scenario_fiscal.csv"
SRC_F = ROOT / "output" / "scenario_fiscal_faithful.csv"
OUT = ROOT / "output" / "scenario_fiscal.png"
OUT_CMP = ROOT / "output" / "scenario_fiscal_compare.png"

# 日本語フォント（候補のうち、このパソコンに入っているものを使う）
_JP = ["Noto Sans JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "IPAexGothic", "Noto Sans CJK JP"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"消費税減税": "#2a78d6", "所得税減税": "#eb6834", "公共投資": "#1baf7a"}
PANELS = [
    ("M_GDP", "実質GDP（％）"),
    ("M_CPIG", "消費者物価（％）"),
    ("M_PBGAGDPV", "基礎的財政収支（国・地方、対GDP比、％pt）"),
    ("Z_DEBTAGDP", "公債等残高（国・地方、対GDP比、％pt）"),
]


def main(compare: bool = False) -> None:
    df = pd.read_csv(SRC)
    dff = pd.read_csv(SRC_F) if compare else None
    fig, axes = plt.subplots(2, 2, figsize=(9, 7.6), facecolor=SURF)
    for ax, (v, title) in zip(axes.flat, PANELS):
        ax.set_facecolor(SURF)
        ax.axhline(0, color=MUTED, lw=0.8)
        x = df[df["var"] == v]
        ends = []
        for label, col in COLORS.items():
            y = x[x["label"] == label].sort_values("year")
            ax.plot(y["year"], y["dev"], color=col, lw=2)
            if compare:
                yf = dff[(dff["var"] == v) & (dff["label"] == label)].sort_values("year")
                ax.plot(yf["year"], yf["dev"], color=col, lw=1.6, ls=(0, (4, 2.5)))
            ax.plot(y["year"].iloc[-1], y["dev"].iloc[-1], "o", color=col, ms=5, mec=SURF, mew=1.5)
            ends.append([y["dev"].iloc[-1], label, col])
        # 線の端のラベル（重ならないように縦にずらす）
        ends.sort()
        lo, hi = ax.get_ylim()
        gap = (hi - lo) * 0.075
        for i in range(1, len(ends)):
            if ends[i][0] - ends[i - 1][0] < gap:
                ends[i][0] = ends[i - 1][0] + gap
        for yv, label, col in ends:
            ax.text(2035.35, yv, label, color=INK, fontsize=8.5, va="center")
        ax.set_title(title, fontsize=10.5, color=INK, loc="left")
        ax.set_xlim(2025.6, 2037.6)
        ax.set_xticks(range(2026, 2036, 2), [f"{t}" for t in range(2026, 2036, 2)])
        ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle("名目GDPの1%を毎年使うなら、消費税減税・所得税減税・公共投資のどれが効くか",
                 fontsize=12.5, color=INK, x=0.02, ha="left", y=0.985)
    sub = "経済財政モデル（2026年度版）の Python 再現で、標準ケースからの乖離（2026〜2035年度）"
    if compare:
        sub += "。実線＝公表乗数に合わせた修正あり、破線＝原典どおり"
    fig.text(0.02, 0.935, sub, fontsize=9, color=MUTED)
    fig.text(0.02, 0.012,
             "注：消費税減税は事前の税収減が名目GDPの1%になるよう税率を10%→7.8%に下げる。所得税減税は名目GDPの1%。"
             "公共投資は実質GDPの1%（国・地方1:1）。\n出典：内閣府「経済財政モデル（2026年度版）」をもとに作成した再現モデル"
             "（github.com/p72/cao-economic-fiscal-model）",
             fontsize=7.5, color=MUTED)
    plt.tight_layout(rect=[0, 0.05, 1, 0.92], h_pad=2.0, w_pad=2.5)
    out = OUT_CMP if compare else OUT
    plt.savefig(out, dpi=150, facecolor=SURF)
    print(f"→ {out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true")
    main(ap.parse_args().compare)
