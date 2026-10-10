"""chuuchouki.py の結果（中長期試算の感応度分析の再現）を図にする.

py src/plot_chuuchouki.py → output/chuuchouki_sensitivity.png
実線がこのモデル、点線（丸印）が資料の値（「経済財政モデル（2018年度版）」の主要乗数表による）。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "chuuchouki_sensitivity.csv"
OUT = ROOT / "output" / "chuuchouki_sensitivity.png"

# 日本語フォント（候補のうち、このパソコンに入っているものを使う）
_JP = ["Noto Sans JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "IPAexGothic", "Noto Sans CJK JP"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLORS = {"kako": "#2a78d6", "seicho": "#eb6834"}
VNAME = {"kako": "過去投影ケース対比", "seicho": "成長移行ケース対比"}
PANELS = [
    ("tfp", "DEBT", "ＴＦＰ上昇率 −0.5%pt：公債等残高比（%pt）"),
    ("tfp", "PB", "ＴＦＰ上昇率 −0.5%pt：ＰＢ対ＧＤＰ比（%pt）"),
    ("rate", "DEBT", "長期金利 +0.5%pt：公債等残高比（%pt）"),
    ("gov", "PB", "政府支出 +名目ＧＤＰの0.5%：ＰＢ対ＧＤＰ比（%pt）"),
]


def main() -> None:
    df = pd.read_csv(SRC)
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.6), facecolor=SURF)
    for ax, (case, var, title) in zip(axes.flat, PANELS):
        ax.set_facecolor(SURF)
        ax.axhline(0, color=MUTED, lw=0.8)
        x = df[(df["case"] == case) & (df["var"] == var)]
        for v, g in x.groupby("variant"):
            c = COLORS[v]
            ax.plot(g["year"], g["model"], color=c, lw=2, label=f"モデル（{VNAME[v]}）")
            ax.plot(g["year"], g["published"], color=c, lw=1.2, ls=":", marker="o", ms=3.5,
                    label=f"資料（{VNAME[v]}）")
            last = g.iloc[-1]
            ax.annotate(f"{last['model']:+.1f}", (last["year"], last["model"]), xytext=(4, 0),
                        textcoords="offset points", color=c, fontsize=8.5, va="center")
            ax.annotate(f"{last['published']:+.1f}", (last["year"], last["published"]), xytext=(4, 0),
                        textcoords="offset points", color=c, fontsize=8.5, va="center", alpha=0.8)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(color=GRID, lw=0.6)
        ax.set_xticks(range(2027, 2036, 2))
        ax.set_xlim(2026.6, 2035.9)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8.5)
        ax.legend(fontsize=7.5, frameon=False, loc="best")
    fig.suptitle("中長期試算（2026年1月）の感応度分析の再現（2027〜2035年度、標準ケースからの乖離）",
                 fontsize=11.5, color=INK, x=0.02, ha="left")
    fig.text(0.02, 0.012, "資料: 内閣府「中長期の経済財政に関する試算」（2026年1月）図19〜21。資料の値は「経済財政モデル（2018年度版）」の主要乗数表による。\n"
             "モデルは2026年度版の再現（財政ブロック移植版、calibrated）。標準ケースは各ケースの成長率・物価・長期金利に近い一定成長の経路。",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    fig.savefig(OUT, dpi=150, facecolor=SURF)
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
