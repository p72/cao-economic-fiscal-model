"""projection.py の結果（中長期試算の主要計数表の再現）を表と図にする.

py src/plot_projection.py
  → output/chuuchouki_table.png（資料35ページと同じ見た目の主要計数表。モデルの計算値、3ケース）
  → output/chuuchouki_table_{kako,seicho,koseicho}.png（同じ見た目で、各欄の上段がモデル、下段が資料）
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
_JP = ["Noto Sans JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "IPAexGothic", "Noto Sans CJK JP", "IPAGothic"]
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


LABEL_PDF = {
    "潜在成長率": "潜在成長率", "実質GDP成長率": "実質GDP成長率", "名目GDP成長率": "名目GDP成長率", "名目GDP": "名目GDP",
    "1人当たり実質GDP成長率": "１人当たり実質GDP成長率", "賃金上昇率": "賃金上昇率", "完全失業率": "完全失業率",
    "消費者物価上昇率": "消費者物価上昇率", "GDPデフレーター変化率": "ＧＤＰデフレーター変化率", "名目長期金利": "名目長期金利",
    "基礎的財政収支（対GDP比）": "国・地方の基礎的財政収支（対名目GDP比）",
    "公債等残高（対GDP比）": "国・地方の公債等残高（対名目GDP比）",
}


def _grid_table(ax, x0, y0, width, df_case, years, compare: bool, rowh: float) -> float:
    """資料と同じ罫線の表を描く（左上が (x0, y0)、座標は図の比率）。描いた表の下端の y を返す."""
    labw = 0.27 * width
    colw = (width - labw) / len(years)
    nrow = len(ITEMS) + 1
    bottom = y0 - rowh * nrow
    kw = dict(transform=ax.transAxes, color=INK)
    ax.add_patch(plt.Rectangle((x0, bottom), width, rowh * nrow, fill=False, lw=1.0, ec=INK, transform=ax.transAxes))
    for r in range(1, nrow):
        y = y0 - rowh * r
        ax.plot([x0, x0 + width], [y, y], lw=0.9 if r == 1 else 0.5, **kw)
    ax.plot([x0 + labw, x0 + labw], [bottom, y0], lw=0.6, **kw)
    for j in range(1, len(years)):
        x = x0 + labw + colw * j
        ax.plot([x, x], [bottom, y0], lw=0.4, **kw)
    yc = y0 - rowh / 2
    ax.text(x0 + labw / 2, yc, "年　　　度", ha="center", va="center", fontsize=9.5, **kw)
    for j, y in enumerate(years):
        ax.text(x0 + labw + colw * (j + 0.5), yc, str(y), ha="center", va="center", fontsize=9.5, **kw)
    for i, item in enumerate(ITEMS):
        yc = y0 - rowh * (i + 1.5)
        g = df_case[df_case["item"] == item].set_index("year")
        ax.text(x0 + 0.006, yc, LABEL_PDF[item], ha="left", va="center", fontsize=9, **kw)
        for j, y in enumerate(years):
            cx = x0 + labw + colw * (j + 0.5)
            if compare:
                ax.text(cx, yc + rowh * 0.17, fmt(item, g.loc[y, "model"]), ha="center", va="center", fontsize=8.8,
                        transform=ax.transAxes, color=INK)
                ax.text(cx, yc - rowh * 0.22, fmt(item, g.loc[y, "published"]), ha="center", va="center", fontsize=7.2,
                        transform=ax.transAxes, color="#8a8984")
            else:
                ax.text(cx, yc, fmt(item, g.loc[y, "model"]), ha="center", va="center", fontsize=9, **kw)
    return bottom


def _title_box(ax, text: str) -> None:
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((0.0, 0.962), 0.17, 0.03, boxstyle="round,pad=0.004,rounding_size=0.008", fill=False,
                                lw=1.2, ec=INK, transform=ax.transAxes))
    ax.text(0.012, 0.977, text, fontsize=15, color=INK, va="center", transform=ax.transAxes)


def table_pdf(df: pd.DataFrame) -> None:
    """資料35ページと同じ見た目の主要計数表（モデルの計算値、3ケース）."""
    years = sorted(df["year"].unique())
    fig = plt.figure(figsize=(12, 15.5), facecolor="white")
    ax = fig.add_axes([0.03, 0.02, 0.94, 0.96])
    ax.axis("off")
    _title_box(ax, "1.主要計数表")
    y = 0.935
    rowh = 0.0192
    for case, (name, _) in CASES.items():
        x = df[df["case"] == case]
        if x.empty:
            continue
        ax.text(0.03, y, name, fontsize=13.5, color=INK, va="center", transform=ax.transAxes)
        ax.text(1.0, y - 0.016, "（％程度）、兆円程度", fontsize=8.5, color=INK, ha="right", va="center",
                transform=ax.transAxes)
        y = _grid_table(ax, 0.0, y - 0.026, 1.0, x, years, compare=False, rowh=rowh) - 0.03
    ax.text(0.0, y + 0.012,
            "（注）経済財政モデル（2026年度版）の Python 再現（財政ブロック移植版）による計算値。資料：内閣府「中長期の経済財政に関する試算」（2026年1月）の前提を使用。\n"
            "　　　2025・2026年度は資料の値に合わせた。2027年度以降は、潜在成長率・実質GDP成長率・物価・賃金・失業率・名目長期金利と、"
            "国の基礎的財政収支対象経費・地方の一般歳出を資料に合わせ、\n　　　税収・利払費・基礎的財政収支・公債等残高をモデルで計算した。",
            fontsize=7.8, color=INK, va="top", transform=ax.transAxes)
    out = ROOT / "output" / "chuuchouki_table.png"
    fig.savefig(out, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"→ {out}")


def table(df: pd.DataFrame, case: str) -> None:
    """資料と同じ見た目の表で、上段にモデル、下段（灰色）に資料の値を並べる."""
    name, _ = CASES[case]
    x = df[df["case"] == case]
    years = sorted(x["year"].unique())
    fig = plt.figure(figsize=(12, 7.6), facecolor="white")
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.94])
    ax.axis("off")
    ax.text(0.0, 0.985, f"主要計数表の再現：{name}", fontsize=14, color=INK, va="center", transform=ax.transAxes)
    ax.text(1.0, 0.955, "（％程度）、兆円程度　各欄の上段：モデル　下段（灰色）：資料", fontsize=8.5, color=INK, ha="right",
            va="center", transform=ax.transAxes)
    bottom = _grid_table(ax, 0.0, 0.935, 1.0, x, years, compare=True, rowh=0.066)
    ax.text(0.0, bottom - 0.015,
            "資料：内閣府「中長期の経済財政に関する試算」（2026年1月）計数表「1.主要計数表」。モデルは経済財政モデル（2026年度版）の Python 再現（財政ブロック移植版）。\n"
            "2025・2026年度は資料の値に合わせた。2027年度以降は、マクロの7項目と国・地方の歳出を資料に合わせ、税収・利払費・基礎的財政収支・公債等残高をモデルで計算した。",
            fontsize=7.8, color=MUTED, va="top", transform=ax.transAxes)
    out = ROOT / "output" / f"chuuchouki_table_{case}.png"
    fig.savefig(out, dpi=150, facecolor="white", bbox_inches="tight")
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
             "2025・2026年度は資料の値に合わせた。\n2027年度以降は、マクロの7項目（成長率・物価・賃金・失業率・長期金利）と国・地方の歳出を資料に合わせ、基礎的財政収支と公債等残高をモデルで計算した。",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    out = ROOT / "output" / "chuuchouki_projection.png"
    fig.savefig(out, dpi=150, facecolor=SURF)
    plt.close(fig)
    print(f"→ {out}")


def main() -> None:
    df = pd.read_csv(SRC)
    table_pdf(df)
    for case in CASES:
        if (df["case"] == case).any():
            table(df, case)
    chart(df)


if __name__ == "__main__":
    main()
