"""普通国債の既発債の年度別スケジュールと、発行の年限構成・利回りの統計（国債ブロックの移植用）.

原典は令和6年度以前に発行した国債（平成11年度～令和6年度発行）の年度別の残高・償還額・利払費を外生変数で与え、
令和7年度以降の発行分だけを発行年度×年限で積み上げる。ここでは2025年度末（令和8年3月末）に残っている銘柄を
既発債とし、2026年度以降の発行分をモデルで積み上げる。

入力（財務省「国債関係資料」 https://www.mof.go.jp/jgbs/reference/appendix/ 。銘柄別現在高は毎月更新され、同じ時点の版を
再取得できないので、取得したファイルをリポジトリに同梱している）:
- data/raw/mof_jgb/maturity_202603.xlsx: 普通国債の銘柄別現在高（令和8年3月末）。償還日・種類・回号・現在高（億円）
- data/raw/mof_jgb/jgb_historical_data.xls: 国債の入札結果。年限ごとの回号・発行日・償還日・表面利率・落札額

個人向け国債の利率は入札結果にないので推定値を使う（残高は計1.95兆円）。
GX経済移行債（クライメート・トランジション利付国債）は別のブロックなので除く。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "mof_jgb"

# 種類（英語名）→ (年限区分, 入札結果のシート名)
TYPES = {
    "Treasury Bills (1-Year)": ("01", None),
    "Treasury Bills (6-Month)": ("01", None),
    "2-Year Bonds": ("02", "2年債"),
    "JGBs for retail investors (3-Year fixed-rate)": ("03", None),
    "5-Year Bonds": ("05", "5年債"),
    "JGBs for retail investors (5-Year fixed-rate)": ("05", None),
    "10-Year Bonds": ("10", "10年債"),
    "10-Year Inflation-Indexed Bonds": ("10", "10年物価連動"),
    "JGBs for retail investors (10-Year floating-rate)": ("10", None),
    "20-Year Bonds": ("20", "20年債"),
    "30-year bonds": ("30", "30年債"),
    "40-year bonds": ("40", "40年債"),
}
# 個人向け国債の利率（%、推定）
RETAIL_COUPON = {
    "JGBs for retail investors (3-Year fixed-rate)": 0.5,
    "JGBs for retail investors (5-Year fixed-rate)": 0.7,
    "JGBs for retail investors (10-Year floating-rate)": 0.9,
}
TENORS = ("01", "02", "03", "05", "10", "20", "30", "40")
TENOR_SHEETS = {"02": "2年債", "05": "5年債", "10": "10年債", "20": "20年債", "30": "30年債", "40": "40年債"}


def fy(ts: pd.Timestamp) -> int:
    return ts.year if ts.month >= 4 else ts.year - 1


def _auctions() -> dict[str, pd.DataFrame]:
    """入札結果: シート → (回号, 発行日, 償還日, 表面利率, 落札額) の表."""
    out = {}
    for name, df in pd.read_excel(RAW / "jgb_historical_data.xls", sheet_name=None, header=None).items():
        body = df.iloc[5:].copy()
        body = body[pd.to_datetime(body[2], errors="coerce").notna()]
        if name.strip() in ("TB", "15変動"):
            continue
        out[name.strip()] = pd.DataFrame({
            "no": pd.to_numeric(body[0], errors="coerce"), "issue": pd.to_datetime(body[2]),
            "mat": pd.to_datetime(body[3]), "coupon": pd.to_numeric(body[4], errors="coerce"),
            "amount": pd.to_numeric(body[7], errors="coerce")})
    return out


def issues() -> pd.DataFrame:
    """2025年度末の既発債（GX経済移行債を除く）: 償還日・年限区分・現在高（億円）・表面利率（%）."""
    m = pd.read_excel(RAW / "maturity_202603.xlsx", sheet_name="Sheet2", header=None, skiprows=4)
    m = m[pd.to_datetime(m[0], errors="coerce").notna()]
    m = pd.DataFrame({"mat": pd.to_datetime(m[0]), "type": m[1].astype(str).str.split("　").str[-1].str.strip(),
                      "no": pd.to_numeric(m[2]), "amount": pd.to_numeric(m[3])})
    m = m[m["type"].isin(TYPES)].copy()
    auc = _auctions()
    coupons = {k: v.dropna(subset=["no"]).groupby("no")["coupon"].first() for k, v in auc.items()}
    m["tenor"] = m["type"].map(lambda s: TYPES[s][0])

    def coupon(r):
        sheet = TYPES[r["type"]][1]
        if sheet is None:
            return RETAIL_COUPON.get(r["type"], 0.0)
        return float(coupons[sheet].get(r["no"], float("nan")))

    m["coupon"] = m.apply(coupon, axis=1)
    if m["coupon"].isna().any():
        raise ValueError(f"利率が見つからない銘柄: {m[m['coupon'].isna()][['type', 'no']].values.tolist()}")
    m["fy"] = m["mat"].map(fy)
    return m


def schedule(first: int = 2025, last: int = 2075) -> dict[str, dict[str, dict[int, float]]]:
    """年限区分ごとの年度別スケジュール（10億円）: stock（年度末残高）、red（償還額、負値）、int（利払費）.

    利払費は年度中に残っている期間の分（償還年度は4月1日から償還日まで）。短期証券は割引で、
    割引料は発行年度（2025年度以前）に計上済みなので0。
    """
    m = issues()
    out = {q: {"stock": {}, "red": {}, "int": {}} for q in TENORS}
    for q in TENORS:
        g = m[m["tenor"] == q]
        for t in range(first, last + 1):
            start = pd.Timestamp(t, 4, 1)
            live = g[g["fy"] > t]
            due = g[g["fy"] == t]
            frac = ((due["mat"] - start).dt.days / 365).clip(0, 1)
            interest = (live["amount"] * live["coupon"]).sum() / 100 + (due["amount"] * due["coupon"] * frac).sum() / 100
            if q == "01":
                interest = 0.0
            out[q]["stock"][t] = live["amount"].sum() / 10
            out[q]["red"][t] = -due["amount"].sum() / 10
            out[q]["int"][t] = interest / 10
    return out


def issuance_fy2025() -> dict:
    """2025年度に発行した国債の年限別の構成比と、年限別の平均の表面利率・最高利回り（GXを除く）."""
    auc = _auctions()
    amt, cpn = {}, {}
    for q, sheet in TENOR_SHEETS.items():
        a = auc[sheet]
        a = a[a["issue"].map(fy) == 2025]
        amt[q] = a["amount"].sum()
        cpn[q] = (a["coupon"] * a["amount"]).sum() / a["amount"].sum()
    return {"amount": amt, "coupon": cpn}


if __name__ == "__main__":
    m = issues()
    print(f"既発債（GX除く）: {len(m)} 銘柄、{m['amount'].sum() / 1e4:,.1f} 兆円")
    print(m.groupby("tenor")["amount"].sum().div(1e4).round(1).to_string())
    s = schedule()
    for t in (2025, 2026, 2027, 2030):
        print(t, "残高", round(sum(s[q]["stock"][t] for q in TENORS)), "償還", round(sum(s[q]["red"][t] for q in TENORS)),
              "利払", round(sum(s[q]["int"][t] for q in TENORS), 1))
    print(issuance_fy2025())
