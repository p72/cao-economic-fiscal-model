"""内閣府「中長期の経済財政に関する試算」（2026年7月）の PDF（pdftotext -layout のテキスト）から、
主要計数表と財政の詳細計数表・付録2の数値を取り出し、src/chuuchouki2607_data.py を書き出す.

    pdftotext -layout 0730shiryo_02-2.pdf jul.txt
    python tools/extract_chuuchouki2607.py jul.txt
"""
import pprint
import re
import sys
from pathlib import Path

CASES = {"成長戦略実現ケース①": "s1", "成長戦略実現ケース②": "s2", "現状投影ケース": "gen"}
MAIN = {"潜在成長率": "潜在成長率", "実質GDP成長率": "実質GDP成長率", "名目GDP成長率": "名目GDP成長率",
        "名目GDP": "名目GDP", "１人当たり実質GDP成長率": "1人当たり実質GDP成長率", "賃金上昇率": "賃金上昇率",
        "完全失業率": "完全失業率", "消費者物価上昇率": "消費者物価上昇率",
        "ＧＤＰデフレーター上昇率": "GDPデフレーター変化率", "名目長期金利": "名目長期金利", "実効金利": "実効金利",
        "国・地方の基礎的財政収支（対名目GDP比）": "基礎的財政収支（対GDP比）",
        "国・地方の純利払費（対名目GDP比）": "純利払費（対GDP比）",
        "国・地方の財政収支（対名目GDP比）": "財政収支（対GDP比）",
        "国・地方の公債等残高（対名目GDP比）": "公債等残高（対GDP比）"}


def nums(line, n=17):
    s = line.replace("▲ ", "-").replace("▲", "-").replace("(", " ").replace(")", " ")
    s = re.sub(r"^\s*\S+", "", s, count=1) if not re.match(r"^\s*[-\d]", s) else s
    v = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]
    return v[-n:]


def label(line):
    return line.strip().split()[0] if line.strip() else ""


def main(txt):
    L = open(txt, encoding="utf-8").read().splitlines()
    pub, fis, sec = {}, {}, {}
    i0 = next(k for k, l in enumerate(L) if "1.主要計数表" in l)
    i1 = next(k for k, l in enumerate(L) if "２.財政の詳細計数表" in l)
    i2 = next(k for k, l in enumerate(L) if "（付録２）部門別収支" in l)
    # 主要計数表
    cur = None
    for l in L[i0:i1]:
        s = l.strip()
        for name, c in CASES.items():
            if s.startswith(name):
                cur = c
                pub[c] = {}
        if cur and label(l) in MAIN and len(nums(l)) == 17:
            pub[cur][MAIN[label(l)]] = nums(l)
    # 財政の詳細計数表（ケースごとに: 除いたベースの国・地方、国の一般会計、地方の普通会計、含んだベースの国・地方）
    cur, part, last_top = None, None, None
    for l in L[i1:i2]:
        s = l.strip()
        if s in CASES:
            if CASES[s] in fis:      # 付録1の本文にもケース名だけの行がある
                break
            cur = CASES[s]
            fis[cur] = {}
            continue
        if "【国・地方の財政の姿】" in s:
            part = "含む" if "含んだ" in s else "除く"
            continue
        if "【国の一般会計の姿】" in s:
            part = "国"
            continue
        if "【地方の普通会計の姿】" in s:
            part = "地方"
            continue
        if cur is None or not s or s.startswith("（注") or s.startswith("年"):
            continue
        lab = label(l)
        v = nums(l)
        if lab.startswith("（対名目") or len(v) < 16:
            continue
        if part in ("除く", "含む"):
            if lab in ("基礎的財政収支", "財政収支", "公債等残高"):
                last_top = lab
                key = lab
            elif lab in ("国", "地方"):
                key = f"{lab}の{last_top}"
            else:
                continue
            fis[cur][f"{key}（{part}）"] = v
        elif part == "国":
            name = {"歳出": "国の歳出", "（基礎的財政収支対象経費）": "国のPB対象経費", "社会保障関係費": "国の社会保障関係費",
                    "地方交付税等": "地方交付税等", "その他": "国のその他経費", "国債費": "国債費", "うち債務償還費": "国の債務償還費",
                    "うち利払費": "国の利払費", "税収等": "国の税収等", "税収": "国の税収", "その他収入": "国のその他収入"}.get(lab)
            if name and len(v) == 17:
                fis[cur][name] = v
        elif part == "地方":
            name = {"歳出": "地方の歳出", "公債費": "地方の公債費", "税収等": "地方の税収等", "税収": "地方の税収",
                    "普通会計における基礎的財政収支": "地方の普通会計の基礎的財政収支"}.get(lab)
            if name and len(v) == 17:
                fis[cur][name] = v
    # 付録2
    cur = None
    for l in L[i2:i2 + 40]:
        s = l.strip()
        for name, c in CASES.items():
            if s.startswith(name) and c not in sec:   # 後ろの国民総所得の表にも同じケース名がある
                cur = c
                sec[c] = {}
        if cur and label(l) in ("一般政府", "家計", "企業", "海外"):
            sec[cur][label(l)] = nums(l)
    for c in CASES.values():
        f = fis[c]
        # 地方の普通会計PBの行は2040年度がページ幅で切れることがあるので、税収等−（歳出−公債費）で補う
        if len(f.get("地方の普通会計の基礎的財政収支", [])) != 17:
            f["地方の普通会計の基礎的財政収支"] = [round(a - (b - d), 1) for a, b, d in
                                       zip(f["地方の税収等"], f["地方の歳出"], f["地方の公債費"])]
        for k, v in list(pub[c].items()) + list(f.items()) + list(sec[c].items()):
            assert len(v) == 17, (c, k, len(v))
    out = Path(__file__).resolve().parents[1] / "src" / "chuuchouki2607_data.py"
    out.write_text(
        '"""内閣府「中長期の経済財政に関する試算」（2026年7月30日、経済財政諮問会議 資料2-2）の計数（2024〜2040年度）.\n\n'
        "tools/extract_chuuchouki2607.py が PDF から書き出したもの（手で直さない）。\n"
        "資料: https://www5.cao.go.jp/keizai-shimon/kaigi/minutes/2026/0730shiryo_02-2.pdf\n"
        "ケース: s1 成長戦略実現ケース①、s2 成長戦略実現ケース②、gen 現状投影ケース。\n"
        "FISCAL の（除く）（含む）は、復旧・復興対策、ＧＸ対策及びＡＩ・半導体支援の経費・財源を除いた／含んだベース。\n"
        '国・地方の一般会計・普通会計の項目は兆円。SECTOR は付録2の部門別収支（対GDP比、%）。\n"""\n'
        f"YEARS = list(range(2024, 2041))\nCASE_NAMES = {pprint.pformat({v: k for k, v in CASES.items()}, width=120)}\n\n"
        f"PUB = {pprint.pformat(pub, width=120, sort_dicts=False)}\n\n"
        f"FISCAL = {pprint.pformat(fis, width=120, sort_dicts=False)}\n\n"
        f"SECTOR = {pprint.pformat(sec, width=120, sort_dicts=False)}\n", encoding="utf-8")
    print(f"→ {out}")
    for c in CASES.values():
        print(c, sorted(pub[c]), sorted(fis[c]), sorted(sec[c]))


if __name__ == "__main__":
    main(sys.argv[1])
