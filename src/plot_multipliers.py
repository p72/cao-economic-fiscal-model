"""simulate.py の結果を、資料集の「主要乗数表」と同じ見た目の表にする.

py src/plot_multipliers.py                       # 移植版・calibrated（output/multipliers_port.csv）
py src/plot_multipliers.py --fiscal simple       # 簡略版（output/multipliers.csv）
  → output/multipliers_table_port_case{1..8}.png（簡略版は multipliers_table_case{1..8}.png）（ケースごとに3つの表。各欄の上段がモデル、下段（灰色）が資料）
  → output/multipliers_table_port.xlsx（シート「モデル」「資料」「差」に、資料と同じ並びの表を8ケース分）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import pandas as pd

import baseline as BL
import published as P
import simulate as S

ROOT = Path(__file__).resolve().parents[1]

_JP = ["Noto Sans JP", "Yu Gothic", "Meiryo", "Hiragino Sans", "IPAexGothic", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "IPAGothic"]
_HAVE = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JP if f in _HAVE] + ["sans-serif"]
INK, MUTED = "#0b0b0b", "#8a8984"

# 資料と同じ見出し（published.COLS と同じ並び）。（見出し, 単位）
HEAD = {
    "M_GDP": ("実質ＧＤＰ", "％"), "M_CP": ("消費\n（実質）", "％"), "M_IFP": ("設備投資\n（実質）", "％"),
    "M_IHP": ("住宅投資\n（実質）", "％"), "M_G": ("政府支出\n（実質）", "％"), "M_XGS": ("輸出\n（実質）", "％"),
    "M_MGS": ("輸入\n（実質）", "％"), "M_FXS": ("為替レート", "％"),
    "M_GDPP": ("潜在ＧＤＰ", "％"), "M_GAP": ("ＧＤＰ\nギャップ", "％pt"), "M_PGDP": ("ＧＤＰ\nデフレーター", "％"),
    "M_CPIG": ("消費者物価", "％"), "M_RCO": ("短期金利", "％pt"), "M_RGB": ("長期金利", "％pt"),
    "M_UR": ("失業率", "％pt"), "M_LE": ("就業者数", "％"),
    "M_GDPV": ("名目ＧＤＰ", "％"), "M_NIV": ("国民所得", "％"), "M_YDV": ("可処分所得", "％"),
    "M_W": ("一人当たり\n賃金", "％"), "M_BCVAGDPV": ("経常収支\n（対ＧＤＰ比）", "％pt"),
    "TAXAGDP": ("税収\n（ＳＮＡベース\n国・地方\n対ＧＤＰ比）", "％pt"),
    "M_BGVAGDPV": ("政府部門収支\n（一般政府\n対ＧＤＰ比）", "％pt"),
    "M_PBGAGDPV": ("基礎的財政収支\n（国・地方\n対ＧＤＰ比）", "％pt"),
    "Z_DEBTAGDP": ("公債等残高\n（対ＧＤＰ比）", "％pt"),
}
PERIODS = range(1, 6)


def load(mode: str, fiscal: str) -> pd.DataFrame:
    df = pd.read_csv(S.out_path(mode, fiscal))
    if df["published"].isna().all():
        pub = pd.read_csv(P.OUT).rename(columns={"value": "published"})
        df = df.drop(columns="published").merge(pub, on=["case", "var", "period"], how="left")
    return df


def _f(x: float) -> str:
    return f"{x + 0.0:.2f}" if round(x, 2) != 0 else "0.00"


def _table(ax, y0: float, cols: list[str], g: pd.DataFrame, headh: float, rowh: float) -> float:
    """1つの表を描く（左上が (0, y0)、座標は図の比率）。下端の y を返す."""
    labw = 0.05
    colw = (1.0 - labw) / len(cols)
    unith = rowh * 0.8
    bottom = y0 - headh - unith - rowh * len(PERIODS)
    kw = dict(transform=ax.transAxes, color=INK)
    ax.add_patch(plt.Rectangle((0, bottom), 1.0, y0 - bottom, fill=False, lw=1.0, ec=INK, transform=ax.transAxes))
    ys = [y0 - headh, y0 - headh - unith] + [y0 - headh - unith - rowh * r for r in range(1, len(PERIODS))]
    for i, y in enumerate(ys):
        ax.plot([0, 1], [y, y], lw=0.8 if i < 2 else 0.4, **kw)
    for j in range(len(cols)):
        x = labw + colw * j
        ax.plot([x, x], [bottom, y0], lw=0.5, **kw)
    ax.text(labw / 2, y0 - headh - unith / 2, "期", ha="center", va="center", fontsize=8.5, **kw)
    for j, v in enumerate(cols):
        name, unit = HEAD[v]
        cx = labw + colw * (j + 0.5)
        ax.text(cx, y0 - headh / 2, name, ha="center", va="center", fontsize=8.3 if name.count("\n") < 3 else 7.2,
                linespacing=1.15, **kw)
        ax.text(labw + colw * (j + 1) - 0.004, y0 - headh - unith / 2, unit, ha="right", va="center", fontsize=8, **kw)
    for i, p in enumerate(PERIODS):
        yc = y0 - headh - unith - rowh * (i + 0.5)
        ax.text(labw / 2, yc, str(p), ha="center", va="center", fontsize=9, **kw)
        for j, v in enumerate(cols):
            m, pub = g.loc[(v, p), "model"], g.loc[(v, p), "published"]
            xr = labw + colw * (j + 1) - 0.006
            ax.text(xr, yc + rowh * 0.17, _f(m), ha="right", va="center", fontsize=9, **kw)
            if pd.notna(pub):
                ax.text(xr, yc - rowh * 0.23, _f(pub), ha="right", va="center", fontsize=7.3,
                        transform=ax.transAxes, color=MUTED)
    return bottom


def figure(df: pd.DataFrame, case: int, label: str, suffix: str) -> Path:
    g = df[df["case"] == case].set_index(["var", "period"])
    fig = plt.figure(figsize=(12, 13), facecolor="white")
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.94])
    ax.axis("off")
    ax.text(0.0, 0.99, f"主要乗数表の再現：{'①②③④⑤⑥⑦⑧'[case - 1]} {P.CASES[case]}", fontsize=13.5, color=INK,
            va="center", transform=ax.transAxes)
    ax.text(1.0, 0.958, "標準ケースからの乖離　各欄の上段：モデル　下段（灰色）：資料", fontsize=8.5, color=INK,
            ha="right", va="center", transform=ax.transAxes)
    y = 0.94
    for cols, headh in zip(P.COLS, (0.045, 0.045, 0.075)):
        y = _table(ax, y, cols, g, headh=headh, rowh=0.038) - 0.03
    ax.text(0.0, y + 0.012,
            f"資料：内閣府「経済財政モデル（2026年度版）資料集」の「主要乗数表」。モデルは同モデルの Python 再現（{label}）。\n"
            "1期目は2026年度。％は標準ケースからの乖離率、％pt は乖離幅。",
            fontsize=7.8, color=MUTED, va="top", transform=ax.transAxes)
    out = ROOT / "output" / f"multipliers_table{suffix}_case{case}.png"
    fig.savefig(out, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def workbook(df: pd.DataFrame, out: Path) -> None:
    """資料と同じ並び（ケースごとに3つの表、行が期）で、モデル・資料・差の3シートに書く."""
    df = df.assign(diff=df["model"] - df["published"])
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for sheet, col in (("モデル", "model"), ("資料", "published"), ("差（モデル－資料）", "diff")):
            r = 0
            for case in P.CASES:
                g = df[df["case"] == case].pivot_table(index="period", columns="var", values=col)
                pd.DataFrame([[f"{'①②③④⑤⑥⑦⑧'[case - 1]} {P.CASES[case]}"]]).to_excel(
                    xw, sheet_name=sheet, startrow=r, header=False, index=False)
                r += 1
                for cols in P.COLS:
                    t = g[cols].round(2)
                    t.columns = [f"{HEAD[v][0].replace(chr(10), '')}（{HEAD[v][1]}）" for v in cols]
                    t.index.name = "期"
                    t.to_excel(xw, sheet_name=sheet, startrow=r)
                    r += len(t) + 2
                r += 1
            ws = xw.sheets[sheet]
            ws.column_dimensions["A"].width = 6
            for c in "BCDEFGHIJ":
                ws.column_dimensions[c].width = 22


def main(mode: str = "calibrated", fiscal: str = "port") -> None:
    df = load(mode, fiscal)
    label = {"port": "財政ブロック移植版", "simple": "簡略版"}[fiscal] + f"、{mode}"
    for case in P.CASES:
        print(f"→ {figure(df, case, label, BL.suffix(mode, fiscal))}")
    out = ROOT / "output" / f"multipliers_table{BL.suffix(mode, fiscal)}.xlsx"
    workbook(df, out)
    print(f"→ {out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="calibrated", choices=["calibrated", "faithful"])
    ap.add_argument("--fiscal", default="port", choices=["simple", "port"])
    a = ap.parse_args()
    main(a.mode, a.fiscal)
