"""内閣府「中長期の経済財政に関する試算」（2026年7月）のPDFから、財政収支の数値を取り出す.

使い方: python extract_2607.py <pdftotext -layout で作ったテキスト> <出力CSV>
取り出す項目（2024〜2040年度、3ケース）
- 名目GDP（主要計数表）
- 国・地方の基礎的財政収支・財政収支（国、地方の内訳を含む。復旧・復興等を除いたベースと含んだベース）
- 一般政府の部門別収支（付録2、対GDP比）
社会保障基金の財政収支は、一般政府（付録2）−国・地方の財政収支（含んだベース）で求める。
"""
import re
import sys

import pandas as pd

YEARS = list(range(2024, 2041))
CASES = ["成長戦略実現ケース①", "成長戦略実現ケース②", "現状投影ケース"]


def nums(line):
    s = line.replace("▲ ", "-").replace("▲", "-").replace("(", " ").replace(")", " ")
    v = re.findall(r"-?\d+\.\d+", s)
    return [float(x) for x in v][-17:]


def main(txt, out):
    L = open(txt, encoding="utf-8").read().splitlines()
    rows = []
    # 主要計数表（名目GDP）：「1.主要計数表」以降、ケース見出しごとに最初の「名目GDP   」行
    start = next(i for i, l in enumerate(L) if "1.主要計数表" in l)
    i = start
    for c in CASES:
        i = next(k for k in range(i, len(L)) if L[k].strip().startswith(c))
        k = next(k for k in range(i, len(L)) if re.match(r"^名目GDP\s+\d", L[k]))
        rows += [(c, "名目GDP", y, v) for y, v in zip(YEARS, nums(L[k]))]
        i = k
    # 財政の詳細計数表
    i = next(k for k, l in enumerate(L) if "２.財政の詳細計数表" in l)
    for c in CASES:
        i = next(k for k in range(i, len(L)) if L[k].strip() == c)
        for base, tag in (("除いたベース", "除く"), ("含んだベース", "含む")):
            h = next(k for k in range(i, len(L)) if "【国・地方の財政の姿】" in L[k] and base in L[k])
            blk = L[h:h + 16]
            for name in ("基礎的財政収支", "財政収支"):
                j = next(n for n, l in enumerate(blk) if l.strip().startswith(name) and nums(l) and len(nums(l)) == 17
                         and not l.strip().startswith("一般"))
                if name == "財政収支" and blk[j].strip().startswith("基礎"):
                    j = next(n for n, l in enumerate(blk) if l.strip().startswith("財政収支"))
                rows += [(c, f"国・地方{name}（{tag}）", y, v) for y, v in zip(YEARS, nums(blk[j]))]
                kuni = next(n for n in range(j + 1, len(blk)) if blk[n].strip().startswith("国"))
                chiho = next(n for n in range(j + 1, len(blk)) if blk[n].strip().startswith("地方"))
                rows += [(c, f"国{name}（{tag}）", y, v) for y, v in zip(YEARS, nums(blk[kuni]))]
                rows += [(c, f"地方{name}（{tag}）", y, v) for y, v in zip(YEARS, nums(blk[chiho]))]
            i = h + 1
    # 付録2 部門別収支
    i = next(k for k, l in enumerate(L) if "（付録２）部門別収支" in l)
    for c in CASES:
        i = next(k for k in range(i, len(L)) if L[k].strip().startswith(c))
        for sec in ("一般政府", "家計", "企業", "海外"):
            k = next(k for k in range(i, len(L)) if L[k].strip().startswith(sec))
            rows += [(c, f"部門別収支_{sec}（対GDP比）", y, v) for y, v in zip(YEARS, nums(L[k]))]
        i = k
    df = pd.DataFrame(rows, columns=["case", "item", "year", "value"])
    w = df.pivot_table(index=["case", "year"], columns="item", values="value").reset_index()
    w["一般政府財政収支"] = w["部門別収支_一般政府（対GDP比）"] / 100 * w["名目GDP"]
    w["社会保障基金財政収支"] = w["一般政府財政収支"] - w["国・地方財政収支（含む）"]
    w["国・地方純利払費（除く）"] = w["国・地方基礎的財政収支（除く）"] - w["国・地方財政収支（除く）"]
    w.to_csv(out, index=False, encoding="utf-8-sig")
    print(w[["case", "year", "名目GDP", "国・地方財政収支（含む）", "国財政収支（含む）", "地方財政収支（含む）",
             "部門別収支_一般政府（対GDP比）", "一般政府財政収支", "社会保障基金財政収支", "国・地方純利払費（除く）"]]
          .round(1).to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
