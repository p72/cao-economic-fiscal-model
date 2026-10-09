"""EViews 形式の方程式を Python の関数に変換する.

方程式リストの式（例: ``dlog(M_W)-dlog(M_GDPP/M_EQLE)=pdl(dlog(M_CPIGA),1,1,2)+...``）を
``f(V, t) -> float`` の形の関数に変換する。V(name, t) は時点 t の変数値を返す。

- 変数名は大文字に統一する（EViews は大文字小文字を区別しない。例: M_POILd = M_POILD）。
- X(-i) は i 期前。d / dlog / @pch / @pc / @movav / @movsum は式全体を時点をずらして評価する。
- pdl(x, n, k, a) は方程式リストの「Lag Distribution」表の係数で sum_j c_j * x(t-j) に置き換える。
  表は式中の pdl の出現順に対応させる。
- @recode(cond, a, b) は条件分岐。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+\.\d*(?:[Ee][+-]?\d+)?|\d*\.\d+(?:[Ee][+-]?\d+)?|\d+(?:[Ee][+-]?\d+)?)"
    r"|(?P<name>@?[A-Za-z_][A-Za-z0-9_$]*)"
    r"|(?P<op><=|>=|<>|[-+*/^(),<>=]))"
)


def tokenize(s: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    s = s.strip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise SyntaxError(f"字句解析できない: {s[pos:pos + 30]!r} in {s!r}")
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        pos = m.end()
    return out


# ---------------------------------------------------------------------------
# 構文木
# ---------------------------------------------------------------------------
@dataclass
class Node:
    pass


@dataclass
class Num(Node):
    v: float


@dataclass
class Var(Node):
    name: str
    lag: int = 0


@dataclass
class Bin(Node):
    op: str
    a: Node
    b: Node


@dataclass
class Neg(Node):
    a: Node


@dataclass
class Call(Node):
    fn: str
    args: list


class Parser:
    def __init__(self, s: str):
        self.toks = tokenize(s)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, val=None):
        tok = self.peek()
        if val is not None and tok[1] != val:
            raise SyntaxError(f"{val!r} が必要: {tok} at {self.i}")
        self.i += 1
        return tok

    def parse(self) -> Node:
        n = self.cmp()
        if self.i != len(self.toks):
            raise SyntaxError(f"余分なトークン: {self.toks[self.i:]}")
        return n

    def cmp(self):
        a = self.add()
        while self.peek()[1] in ("<", ">", "<=", ">=", "<>") or (self.peek()[1] == "=" and self.allow_eq):
            op = self.take()[1]
            a = Bin({"<>": "!=", "=": "=="}.get(op, op), a, self.add())
        return a

    allow_eq = False

    def add(self):
        a = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            a = Bin(op, a, self.mul())
        return a

    def mul(self):
        a = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            a = Bin(op, a, self.unary())
        return a

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            return Neg(self.unary())
        if self.peek()[1] == "+":
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        a = self.atom()
        if self.peek()[1] == "^":
            self.take()
            a = Bin("**", a, self.unary())
        return a

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return Num(float(val))
        if val == "(":
            n = self.cmp()
            self.take(")")
            return n
        if kind == "name":
            name = val.upper()
            if self.peek()[1] == "(":
                # 関数呼び出し or ラグ X(-i)
                if not name.startswith("@") and name not in FUNCS:
                    self.take("(")
                    neg = self.peek()[1] == "-"
                    if neg:
                        self.take()
                    k = int(self.take()[1])
                    self.take(")")
                    return Var(name, k if neg else -k)
                self.take("(")
                args = [self.cmp()]
                while self.peek()[1] == ",":
                    self.take()
                    args.append(self.cmp())
                self.take(")")
                return Call(name.lstrip("@"), args)
            return Var(name)
        raise SyntaxError(f"予期しないトークン: {val!r}")


FUNCS = {"LOG", "DLOG", "D", "PDL", "ABS", "EXP"}


def parse_expr(s: str) -> Node:
    p = Parser(s)
    p.allow_eq = False
    return p.parse()


def split_eq(eq: str) -> tuple[str, str]:
    """トップレベルの '=' で左辺と右辺に分ける（比較演算子 <=, >= は除く）."""
    depth = 0
    for i, c in enumerate(eq):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "=" and depth == 0 and eq[i - 1] not in "<>" and eq[i + 1:i + 2] != "=":
            return eq[:i], eq[i + 1:]
    raise ValueError(f"'=' がない: {eq}")


# ---------------------------------------------------------------------------
# Python ソースへの変換
# ---------------------------------------------------------------------------
class Emitter:
    """構文木を Python の式（文字列）にする。t はシフト量を含む時点の式."""

    def __init__(self, pdl_tables: list[list[float]] | None = None):
        self.pdl = list(pdl_tables or [])
        self.pdl_i = 0
        self.vars: set[str] = set()

    def emit(self, n: Node, t: str) -> str:
        if isinstance(n, Num):
            return repr(n.v)
        if isinstance(n, Var):
            self.vars.add(n.name)
            tt = t if n.lag == 0 else f"({t}{-n.lag:+d})"  # lag>0 は過去
            return f"V({n.name!r},{tt})"
        if isinstance(n, Neg):
            return f"(-{self.emit(n.a, t)})"
        if isinstance(n, Bin):
            return f"({self.emit(n.a, t)}{n.op}{self.emit(n.b, t)})"
        if isinstance(n, Call):
            return self.call(n, t)
        raise TypeError(n)

    def call(self, n: Call, t: str) -> str:
        fn, a = n.fn, n.args
        e = lambda x, tt=t: self.emit(x, tt)  # noqa: E731
        lag = lambda k: f"({t}-{k})"  # noqa: E731
        if fn == "LOG":
            return f"_log({e(a[0])})"
        if fn == "EXP":
            return f"math.exp({e(a[0])})"
        if fn == "ABS":
            return f"abs({e(a[0])})"
        if fn == "DLOG":
            return f"(_log({e(a[0])})-_log({e(a[0], lag(1))}))"
        if fn == "D":
            return f"({e(a[0])}-{e(a[0], lag(1))})"
        if fn == "PCH":
            return f"({e(a[0])}/{e(a[0], lag(1))}-1)"
        if fn == "PC":
            return f"(({e(a[0])}/{e(a[0], lag(1))}-1)*100)"
        if fn in ("MOVAV", "MOVSUM"):
            k = int(a[1].v)
            s = "+".join(e(a[0], lag(j)) if j else e(a[0]) for j in range(k))
            return f"(({s})/{k})" if fn == "MOVAV" else f"({s})"
        if fn == "RECODE":
            return f"({e(a[1])} if {e(a[0])} else {e(a[2])})"
        if fn == "PDL":
            if self.pdl_i >= len(self.pdl):
                raise ValueError("pdl の係数表が足りない")
            coefs = self.pdl[self.pdl_i]
            self.pdl_i += 1
            n_lag = int(a[1].v)
            if len(coefs) != n_lag + 1:
                raise ValueError(f"pdl のラグ数 {n_lag} と係数表 {len(coefs)} 行が合わない")
            terms = [f"{c!r}*{e(a[0], lag(j)) if j else e(a[0])}" for j, c in enumerate(coefs)]
            return "(" + "+".join(terms) + ")"
        raise ValueError(f"未対応の関数: {fn}")


def _log(x: float) -> float:
    return math.log(x)


@dataclass
class CompiledEq:
    name: str  # 左辺の対象変数
    src: str  # 元の式
    lhs: object  # f(V, t)
    rhs: object  # f(V, t)
    vars: set
    py: str


def compile_eq(name: str, eq: str, pdl_tables=None) -> CompiledEq:
    lhs_s, rhs_s = split_eq(eq)
    em = Emitter(pdl_tables)
    # pdl は通常右辺にあるが、左辺→右辺の順で出現順に割り当てる
    lhs_py = em.emit(parse_expr(lhs_s), "t")
    rhs_py = em.emit(parse_expr(rhs_s), "t")
    if em.pdl_i != len(em.pdl):
        raise ValueError(f"{name}: pdl の係数表が余る（{em.pdl_i}/{len(em.pdl)}）")
    env = {"math": math, "_log": _log}
    lhs = eval(f"lambda V,t: {lhs_py}", env)
    rhs = eval(f"lambda V,t: {rhs_py}", env)
    return CompiledEq(name, eq, lhs, rhs, em.vars, f"{lhs_py} = {rhs_py}")
