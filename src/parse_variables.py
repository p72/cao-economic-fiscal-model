"""変数リスト（reference/ef2026_var.txt）を構造化して JSON に書き出す.

出力: data/processed/variables.json  {変数名: {label, unit, source, kind（endog/exog）}}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reference" / "ef2026_var.txt"
OUT = ROOT / "data" / "processed" / "variables.json"

SOURCES = {"BOJ", "CAO", "ILF", "IMF", "MHLW", "MIC", "MOF", "NIP", "CBO", "JBT", "STAT", "TSE", "Author"}
RE_VAR = re.compile(r"^\s*([A-Z][A-Za-z0-9_$]*)\s{2,}(.+?)\s*$")


def main() -> dict:
    kind = None
    out: dict = {}
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if "（1）内生変数" in line or "(1)内生変数" in line.replace(" ", ""):
            kind = "endog"
            continue
        if "外生変数" in line and "（２）" in line:
            kind = "exog"
            continue
        if kind is None:
            continue
        m = RE_VAR.match(line)
        if not m:
            continue
        name, rest = m.group(1), m.group(2)
        parts = re.split(r"\s{2,}", rest)
        source = parts[-1] if parts[-1].split()[0] in SOURCES else ""
        if source:
            parts = parts[:-1]
        unit = parts[-1] if len(parts) >= 2 else ""
        label = parts[0]
        out[name.upper()] = {"label": label, "unit": unit, "source": source, "kind": kind}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    v = main()
    from collections import Counter
    print(len(v), Counter(x["kind"] for x in v.values()))
