"""2026年7月の中長期試算の再現（projection2607.py）と追加財政支出なし（noextra2607.py）の、部門別の財政収支の図.

記事「日本の財政は黒字になるのか」と同じ形（6枚の図＋表）で、どのケース・シナリオの組み合わせでも描く。

    python src/plot_balance2607.py                         # あるものすべて: ケースごとの図（再現と支出なし）と、ケースの比較の図
    python src/plot_balance2607.py --series s1:base s1:noextra gen:base gen:noextra --name compare4

series は「ケース:シナリオ」。ケースは s1（成長戦略実現ケース①）、s2（同②）、gen（現状投影）、
シナリオは base（再現。追加財政支出あり）、noextra（追加財政支出なし）。内訳の棒グラフは最初の2つの series について描く。
点線は内閣府の試算（国・地方は復旧・復興対策等を除いたベース、一般政府は付録2、社会保障基金は一般政府−国・地方（含んだベース））。
入力: output/chuuchouki2607_balance.csv　出力: output/balance2607_{name}.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chuuchouki2607_data as D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
plt.rcParams["font.family"] = ["Noto Sans JP", "Noto Sans CJK JP", "IPAPGothic", "IPAGothic", "Yu Gothic", "Meiryo",
                               "Hiragino Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

CASE_LABEL = {"s1": "成長戦略実現①", "s2": "成長戦略実現②", "gen": "現状投影"}
SCEN_LABEL = {"base": "", "noextra": "（追加支出なし）"}
COLOR = {"s1": "#d6452a", "s2": "#1a9e5f", "gen": "#2a63c4"}
C_KUNI, C_CHIHO, C_SSF = "#c8553d", "#e8a33d", "#2bb07f"
INK, MUTED, GRID = "#111111", "#555555", "#e2e2e2"
TABLE_YEARS = [2024, 2025, 2026, 2027, 2028, 2030, 2035, 2040]


def label(case: str, scen: str) -> str:
    return CASE_LABEL[case] + SCEN_LABEL[scen]


def published(case: str) -> pd.DataFrame:
    """内閣府の試算の値（兆円）."""
    f, pub = D.FISCAL[case], D.PUB[case]
    df = pd.DataFrame({"year": D.YEARS, "名目GDP": pub["名目GDP"]})
    df["国・地方"] = f["財政収支（除く）"]
    df["国・地方PB"] = f["基礎的財政収支（除く）"]
    df["純利払費"] = df["国・地方PB"] - df["国・地方"]
    df["一般政府"] = [r / 100 * g for r, g in zip(D.SECTOR[case]["一般政府"], pub["名目GDP"])]
    df["社会保障基金"] = df["一般政府"] - pd.Series(f["財政収支（含む）"])
    df["公債等残高比"] = pub["公債等残高（対GDP比）"]
    return df


def style(ax, title):
    ax.set_title(title, fontsize=11, color=INK, loc="left")
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.axvspan(2026.5, 2040.5, color="#f3f3f3", zorder=0)
    ax.set_xlim(2023.4, 2040.6)
    ax.set_xticks(range(2024, 2041, 2))
    ax.tick_params(labelsize=8.5, colors=MUTED)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def line_kw(case, scen, lw=2.2):
    return dict(color=COLOR[case], lw=lw, ls="-" if scen == "base" else "--")


def to_incl(d: pd.DataFrame, case: str) -> pd.DataFrame:
    """モデルの国の財政収支（復旧・復興対策、ＧＸ対策、ＡＩ・半導体支援を含まない）に、資料の含んだベースと除いたベースの
    差を足す。一般政府（付録2）は SNA の値でこれらを含むので、一般政府と内訳はこちらで比べる."""
    f = D.FISCAL[case]
    adj = pd.Series([a - b for a, b in zip(f["国の財政収支（含む）"], f["国の財政収支（除く）"])], index=D.YEARS)
    d = d.copy()
    a = d["year"].map(adj).fillna(0.0).values
    d["国"] = d["国"] + a
    d["国・地方（含む）"] = d["国・地方"] + a
    d["一般政府"] = d["一般政府"] + a
    return d


def plot(df: pd.DataFrame, series: list[tuple[str, str]], name: str) -> Path:
    get = {(c, s): to_incl(df[(df.case == c) & (df.scen == s)].sort_values("year"), c) for c, s in series}
    cases = list(dict.fromkeys(c for c, _ in series))
    pubs = {c: published(c) for c in cases}
    n_rows = 3 * len(series)
    table_h = 0.3 * (n_rows + 1) + 0.4            # 表の高さ（インチ、題を含む）
    fig_h = 10.5 + table_h
    fig, axes = plt.subplots(2, 3, figsize=(17, fig_h))
    # (1) 一般政府と国・地方（対GDP比）
    ax = axes[0, 0]
    for c, s in series:
        d = get[(c, s)]
        ax.plot(d.year, d["一般政府"] / d["名目GDP"] * 100, marker="o", ms=3, label=f"{label(c, s)}　一般政府", **line_kw(c, s))
        ax.plot(d.year, d["国・地方（含む）"] / d["名目GDP"] * 100, label=f"{label(c, s)}　国・地方", **line_kw(c, s, 1.0))
    for c in cases:
        ax.plot(D.YEARS, D.SECTOR[c]["一般政府"], color=COLOR[c], lw=1.2, ls=":")
    style(ax, "財政収支（対GDP比、％）　太線：一般政府　細線：国・地方")
    ax.legend(fontsize=7, frameon=False, loc="lower left")
    # (2)(3) 内訳（兆円）。series が1つなら、右は内閣府試算の内訳（含んだベース）
    bars = [(get[k], f"内訳（兆円）　{label(*k)}") for k in series[:2]]
    if len(bars) == 1:
        c = series[0][0]
        f = D.FISCAL[c]
        p = pubs[c].assign(国=f["国の財政収支（含む）"], 地方=f["地方の財政収支（含む）"])
        bars.append((p, f"内訳（兆円）　{CASE_LABEL[c]}　内閣府試算（含んだベース）"))
    for ax, (d, title) in zip((axes[0, 1], axes[0, 2]), bars):
        ax.bar(d.year, d["国"], color=C_KUNI, width=0.7, label="国")
        ax.bar(d.year, d["地方"], color=C_CHIHO, width=0.7, label="地方")
        ax.bar(d.year, d["社会保障基金"], bottom=d["地方"].clip(lower=0), color=C_SSF, width=0.7, label="社会保障基金")
        ax.plot(d.year, d["一般政府"], color="black", lw=2, marker="o", ms=3.5, label="一般政府（合計）")
        style(ax, title)
        ax.legend(fontsize=7.5, frameon=False, loc="lower left", ncol=4)
    lo = min(d["国"].min() for d, _ in bars) * 1.15
    hi = max((d["地方"].clip(lower=0) + d["社会保障基金"]).max() for d, _ in bars) * 1.25
    for ax in (axes[0, 1], axes[0, 2]):
        ax.set_ylim(lo, hi)
    # (4) PB と財政収支
    ax = axes[1, 0]
    for c, s in series:
        d = get[(c, s)]
        ax.plot(d.year, d["国・地方PB"] / d["名目GDP"] * 100, label=f"{label(c, s)}　PB", **line_kw(c, s))
        ax.plot(d.year, d["国・地方"] / d["名目GDP"] * 100, label=f"{label(c, s)}　財政収支", **line_kw(c, s, 1.0))
    for c in cases:
        p = pubs[c]
        ax.plot(p.year, p["国・地方PB"] / p["名目GDP"] * 100, color=COLOR[c], lw=1.2, ls=":")
        ax.plot(p.year, p["国・地方"] / p["名目GDP"] * 100, color=COLOR[c], lw=1.2, ls=":")
    style(ax, "国・地方の PB（太線）と財政収支（細線）（対GDP比、％）")
    ax.legend(fontsize=7, frameon=False, loc="lower left", ncol=2)
    # (5) 純利払費
    ax = axes[1, 1]
    for c, s in series:
        d = get[(c, s)]
        ax.plot(d.year, d["純利払費"], marker="o", ms=3, label=label(c, s), **line_kw(c, s))
    for c in cases:
        ax.plot(pubs[c].year, pubs[c]["純利払費"], color=COLOR[c], lw=1.2, ls=":")
    style(ax, "国・地方の純利払費（PB − 財政収支、兆円）")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    # (6) 社会保障基金
    ax = axes[1, 2]
    for c, s in series:
        d = get[(c, s)]
        ax.plot(d.year, d["社会保障基金"], marker="o", ms=3, label=label(c, s), **line_kw(c, s))
    for c in cases:
        ax.plot(pubs[c].year, pubs[c]["社会保障基金"], color=COLOR[c], lw=1.2, ls=":")
    style(ax, "社会保障基金の財政収支（兆円）")
    ax.legend(fontsize=8, frameon=False, loc="lower center")
    # 表
    bottom = (table_h + 1.7) / fig_h
    fig.subplots_adjust(left=0.04, right=0.985, top=1 - 1.25 / fig_h, bottom=bottom, hspace=0.3, wspace=0.18)
    tax = fig.add_axes([0.04, 0.85 / fig_h, 0.945, table_h / fig_h])
    tax.axis("off")
    rows, colors = [], []
    for c, s in series:
        d = get[(c, s)].set_index("year")
        for item in ("国・地方", "社会保障基金", "一般政府"):
            cells = []
            for y in TABLE_YEARS:
                v = d.loc[y, item]
                txt = f"{v:+.1f}"
                if item == "一般政府":
                    txt += f" ({v / d.loc[y, '名目GDP'] * 100:+.1f}%)"
                elif item == "国・地方" and s == "base":
                    txt += f" [{pubs[c].set_index('year').loc[y, item]:+.1f}]"
                cells.append(txt)
            rows.append([label(c, s) if item == "国・地方" else "", item] + cells)
            colors.append(COLOR[c])
    tbl = tax.table(cellText=rows, colLabels=["", ""] + [f"{y}年度" for y in TABLE_YEARS],
                    bbox=[0, 0, 1, 1 - 0.4 / table_h], cellLoc="center", colLoc="center", edges="horizontal")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    for (r, k), cell in tbl.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if r > 0 and k == 0:
            cell.get_text().set_color(colors[r - 1])
            cell.get_text().set_fontweight("bold")
        if r > 0 and k >= 2 and "(" in cell.get_text().get_text():
            cell.get_text().set_color("#1a7f4b" if cell.get_text().get_text().startswith("+") else INK)
    tax.set_title("財政収支（兆円）。国・地方は除いたベース（［ ］内は内閣府試算）、一般政府は含んだベース（カッコ内は対GDP比）",
                  fontsize=10, color=INK, loc="left")
    fig.suptitle("日本の財政は黒字になるのか　2026年7月の中長期試算を経済財政モデルで作り直し、2040年度までの財政収支を計算",
                 x=0.04, ha="left", fontsize=15, color=INK, y=1 - 0.3 / fig_h)
    fig.text(0.04, 1 - 0.75 / fig_h, "財政収支は国民経済計算の純貸出（＋）／純借入（−）。実線：モデル（再現）　破線：モデル（追加財政支出なし）　"
             "点線：内閣府試算。網かけは推計期間。上段の一般政府・国・地方は復旧・復興対策等を含んだベース、"
             "下段の PB・純利払費は除いたベース。", fontsize=9.5, color=MUTED)
    fig.text(0.04, 0.008,
             "資料：内閣府「中長期の経済財政に関する試算」（2026年7月）。経路は同試算を経済財政モデル（2026年度版）の Python 再現"
             "（github.com/p72/cao-economic-fiscal-model、財政ブロック移植版）で作り直したもの。\n"
             "モデルは復旧・復興対策、ＧＸ対策、ＡＩ・半導体支援を含まないので、含んだベースの値は国の財政収支に資料の2つのベースの差を足した。"
             "表の国・地方は除いたベース。\n"
             "追加財政支出なし：2027年度以降の毎年度実質10兆円（公需と資本コストを下げる補助金が半分ずつ）を除き、ほかの前提と式の誤差項は"
             "再現と同じにして解き直した。内閣府試算の社会保障基金は一般政府（付録2、0.1%刻み）−国・地方なので±0.5兆円程度の誤差がある。",
             fontsize=7.8, color=MUTED)
    out = ROOT / "output" / f"balance2607_{name}.png"
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"→ {out}")
    return out


def main(series=None, name=None):
    df = pd.read_csv(ROOT / "output" / "chuuchouki2607_balance.csv")
    have = set(zip(df.case, df.scen))
    if series:
        ser = [tuple(x.split(":")) for x in series]
        missing = [s for s in ser if s not in have]
        if missing:
            raise SystemExit(f"計算していない組み合わせ: {missing}（projection2607.py・noextra2607.py を先に実行）")
        plot(df, ser, name or "_".join(f"{c}-{s}" for c, s in ser))
        return
    for c in ("s1", "s2", "gen"):
        ser = [(c, s) for s in ("base", "noextra") if (c, s) in have]
        if ser:
            plot(df, ser, c)
    base = [(c, "base") for c in ("s1", "s2", "gen") if (c, "base") in have]
    if len(base) > 1:
        plot(df, base, "cases")
    noex = [(c, "noextra") for c in ("s1", "s2", "gen") if (c, "noextra") in have]
    if len(noex) > 1:
        plot(df, noex, "cases_noextra")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="+", help="ケース:シナリオ（例 s1:base gen:noextra）")
    ap.add_argument("--name", help="出力ファイル名の一部")
    a = ap.parse_args()
    main(a.series, a.name)
