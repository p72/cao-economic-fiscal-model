"""projection.py の結果（中長期試算の主要計数表の再現）を表と図にする.

py src/plot_projection.py
  → output/chuuchouki_table_{kako,seicho,koseicho}.png（資料35ページの主要計数表と同じ並び。上段モデル、下段資料）
  → output/chuuchouki_projection.png（主な6項目の推移。実線モデル、点線資料）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "chuuchouki_projection.csv"

# 日本語フォント（候補のうち、このパソコンに入っているものを使う）
_JP = ["Noto Sans JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "IPAexGothic", "Noto Sans CJK JP"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
CASES = {"kako": ("過去投影ケース", "#2a78d6"), "seicho": ("成長移行ケース", "#eb6834"),
         "koseicho": ("高成長実現ケース", "#1baf7a")}
ITEMS = ["潜在成長率", "実質GDP成長率", "名目GDP成長率", "名目GDP", "1人当たり実質GDP成長率", "賃金上昇率", "完全失業率",
         "消費者物価上昇率", "GDPデフレーター変化率", "名目長期金利", "基礎的財政収支（対GDP比）", "公債等残高（対GDP比）"]
LABELS = {"基礎的財政収支（対GDP比）": "国・地方の基礎的財政収支（対名目GDP比）",
          "公債等残高（対GDP比）": "国・地方の公債等残高（対名目GDP比）"}
PANELS = [("実質GDP成長率", "実質GDP成長率（％）"), ("名目GDP成長率", "名目GDP成長率（％）"),
          ("消費者物価上昇率", "消費者物価上昇率（％）"), ("名目長期金利", "名目長期金利（％）"),
          ("基礎的財政収支（対GDP比）", "国・地方の基礎的財政収支（対GDP比、％）"),
          ("公債等残高（対GDP比）", "国・地方の公債等残高（対GDP比、％）")]


def fmt(item: str, x: float) -> str:
    if item == "名目GDP":
        return f"{x:.1f}"
    s = f"{abs(x):.1f}"
    return f"(▲{s})" if round(x, 1) < 0 else f"({s})"


def table(df: pd.DataFrame, case: str) -> None:
    name, color = CASES[case]
    x = df[df["case"] == case]
    years = sorted(x["year"].unique())
    fig, ax = plt.subplots(figsize=(13, 9.2), facecolor=SURF)
    ax.axis("off")
    left, top, rowh = 0.0, 0.93, 0.072
    colw = (1 - 0.27) / len(years)
    ax.text(0, 1.0, f"主要計数表の再現：{name}", fontsize=14, color=INK, transform=ax.transAxes, va="top")
    ax.text(1, 1.0, "（％程度）、兆円程度　上段：モデル　下段：資料", fontsize=9, color=MUTED, ha="right",
            transform=ax.transAxes, va="top")
    ax.text(left + 0.01, top, "年　　度", fontsize=10, color=INK, transform=ax.transAxes, va="center")
    for j, y in enumerate(years):
        ax.text(0.27 + colw * (j + 0.5), top, str(y), fontsize=10, color=INK, ha="center", transform=ax.transAxes,
                va="center")
    ax.plot([0, 1], [top - rowh / 2.4, top - rowh / 2.4], color=INK, lw=0.8, transform=ax.transAxes)
    for i, item in enumerate(ITEMS):
        yc = top - rowh * (i + 1)
        g = x[x["item"] == item].set_index("year")
        if i % 2 == 0:
            ax.add_patch(plt.Rectangle((0, yc - rowh / 2), 1, rowh, color="#f1f0ec", transform=ax.transAxes, lw=0))
        ax.text(left + 0.01, yc, LABELS.get(item, item), fontsize=9.5, color=INK, transform=ax.transAxes, va="center")
        for j, y in enumerate(years):
            cx = 0.27 + colw * (j + 0.5)
            ax.text(cx, yc + rowh * 0.17, fmt(item, g.loc[y, "model"]), fontsize=9.5, color=color, ha="center",
                    transform=ax.transAxes, va="center", fontweight="bold")
            ax.text(cx, yc - rowh * 0.2, fmt(item, g.loc[y, "published"]), fontsize=8.5, color=MUTED, ha="center",
                    transform=ax.transAxes, va="center")
    ax.text(0, top - rowh * (len(ITEMS) + 0.9),
            "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）計数表「1.主要計数表」。モデルは経済財政モデル（2026年度版）の Python 再現"
            "（財政ブロック移植版）。\n2025・2026年度は資料の値に合わせ、2027年度以降は付録1の前提（人口、労働参加率、TFP、世界経済、原油）を与えて計算した。\n"
            "2027年度以降も、GDPギャップの変化（実質成長率−潜在成長率）と名目長期金利は資料に合わせた。それ以外はモデルで計算した値。",
            fontsize=8, color=MUTED, transform=ax.transAxes, va="top")
    out = ROOT / "output" / f"chuuchouki_table_{case}.png"
    fig.savefig(out, dpi=150, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print(f"→ {out}")


def chart(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.8), facecolor=SURF)
    for ax, (item, title) in zip(axes.flat, PANELS):
        ax.set_facecolor(SURF)
        for case, (name, color) in CASES.items():
            g = df[(df["case"] == case) & (df["item"] == item)]
            if g.empty:
                continue
            ax.plot(g["year"], g["model"], color=color, lw=2, label=f"{name}（モデル）")
            ax.plot(g["year"], g["published"], color=color, lw=1.2, ls=":", marker="o", ms=3, label=f"{name}（資料）")
        if item == "基礎的財政収支（対GDP比）":
            ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(color=GRID, lw=0.6)
        ax.set_xticks(range(2024, 2036, 2))
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8.5)
    axes[0, 0].legend(fontsize=7.5, frameon=False, loc="best")
    fig.suptitle("中長期試算（2026年1月）の主要計数の再現（実線：モデル、点線：資料）", fontsize=12, color=INK, x=0.02, ha="left")
    fig.text(0.02, 0.01, "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）。モデルは経済財政モデル（2026年度版）の Python 再現（財政ブロック移植版）。"
             "2025・2026年度は資料の値に合わせ、2027年度以降は前提を与えて計算。\n2027年度以降もGDPギャップの変化と名目長期金利は資料に合わせた（長期金利はモデルと資料が重なる）。",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    out = ROOT / "output" / "chuuchouki_projection.png"
    fig.savefig(out, dpi=150, facecolor=SURF)
    plt.close(fig)
    print(f"→ {out}")


def main() -> None:
    df = pd.read_csv(SRC)
    for case in CASES:
        if (df["case"] == case).any():
            table(df, case)
    chart(df)


if __name__ == "__main__":
    main()
