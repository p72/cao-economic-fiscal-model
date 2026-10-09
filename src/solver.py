"""年ごとに連立方程式を解く（同時ブロックはニュートン法、単独の式は1変数ニュートン法）.

各式は「左辺 - 右辺 - AF = 0」の形で解く。AF（アドファクター）は式ごと・年ごとの定数で、
ベースラインを作るときに、目標の値で式がちょうど成り立つように計算する（calibrate）。

- data: {変数名: {年: 値}} の辞書。年は年度（int）。
- pinned: その年に値を固定する変数の集合。固定した変数の式は解かず、AF を逆算する。
- swap: {式の名前: 代わりに解く変数}。例: 生産関数を M_GDPP ではなく M_TFP について解く。
"""
from __future__ import annotations

import math

from spec import Model


class Solver:
    def __init__(self, model: Model, data: dict[str, dict[int, float]], af: dict[str, dict[int, float]] | None = None):
        self.m = model
        self.data = data
        self.af = af if af is not None else {e.name: {} for e in model.eqs}
        self._V = self._make_getter()
        by = {e.name: e for e in model.eqs}
        self.ordered = [by[n] for comp in order_equations(model) for n in comp]

    def _make_getter(self):
        data = self.data

        def V(name, t):
            try:
                return data[name][t]
            except KeyError:
                raise KeyError(f"値がない: {name}[{t}]") from None
        return V

    def residual(self, eq, t: int) -> float:
        V = self._V
        return eq.lhs(V, t) - eq.rhs(V, t) - self.af[eq.name].get(t, 0.0)

    def calibrate(self, eq, t: int) -> None:
        """現在の値で式が成り立つように AF を決める."""
        V = self._V
        self.af[eq.name][t] = eq.lhs(V, t) - eq.rhs(V, t)

    def _solve_one(self, eq, var: str, t: int, tol: float, omega: float = 1.0) -> float:
        """式 eq を変数 var について解き、変化の大きさ（相対）を返す。omega<1 なら更新幅を縮める（緩和）."""
        col = self.data[var]
        x0 = col[t]
        x = x0
        for _ in range(30):
            try:
                f = self.residual(eq, t)
            except (ValueError, ZeroDivisionError, OverflowError):
                x = x0 * 0.99 if x0 else 1e-6
                col[t] = x
                continue
            if abs(f) < 1e-13:
                break
            h = 1e-6 * max(abs(x), 1e-6)
            col[t] = x + h
            try:
                f2 = self.residual(eq, t)
            except (ValueError, ZeroDivisionError, OverflowError):
                f2 = float("nan")
            col[t] = x
            dfdx = (f2 - f) / h
            if not math.isfinite(dfdx) or dfdx == 0:
                raise RuntimeError(f"{eq.name}: {var} について解けない（t={t}）")
            step = -f / dfdx
            # 全幅で進めて式が計算できない（対数の中が負になるなど）ときだけ歩幅を半分にする
            for _ in range(40):
                col[t] = x + step
                try:
                    if math.isfinite(self.residual(eq, t)):
                        break
                except (ValueError, ZeroDivisionError, OverflowError):
                    pass
                step *= 0.5
            x = x + step
            col[t] = x
            if abs(step) <= tol * max(abs(x), 1.0):
                break
        if omega != 1.0:
            x = x0 + omega * (x - x0)
            col[t] = x
        return abs(x - x0) / max(abs(x0), 1.0)

    def solve_year(self, t: int, pinned: set[str] = frozenset(), swap: dict[str, str] | None = None,
                   tol: float = 1e-10, max_iter: int = 500, calibrate_pinned: bool = True) -> int:
        """その年の式を解く.

        まず Gauss-Seidel（式を順に1変数ニュートン法で解く）を試し、収束しない・発散するときは
        初期値に戻して、同時に解く必要のあるブロックをブロック全体のニュートン法で解く。
        """
        swap = swap or {}
        order = [(eq, swap.get(eq.name, eq.name)) for eq in self.ordered
                 if not (eq.name in pinned and eq.name not in swap)]
        start = {v: self.data[v][t] for _, v in order}
        n_iter = None
        omegas = (0.5, 1.0, 0.3) if getattr(self.m, "fiscal", "simple") == "port" else (1.0, 0.5, 0.3)
        for omega in omegas:
            try:
                n_iter = self._gauss_seidel(order, t, tol, max_iter if omega == omegas[0] else 3 * max_iter, omega)
                break
            except (RuntimeError, OverflowError, ValueError, ZeroDivisionError):
                for v, x in start.items():
                    self.data[v][t] = x
        if n_iter is None:
            n_iter = 0
            for block in _blocks(order):
                if len(block) == 1:
                    eq, var = block[0]
                    for k in range(max_iter):
                        if self._solve_one(eq, var, t, tol * 1e-2) < tol:
                            break
                    n_iter = max(n_iter, k + 1)
                else:
                    n_iter = max(n_iter, self._newton_block(block, t, max(tol, 1e-9), 100))
        # 固定した変数の式は AF を逆算する
        for eq in (self.m.eqs if calibrate_pinned else []):
            if eq.name in pinned and eq.name not in swap:
                self.calibrate(eq, t)
        return n_iter

    def _gauss_seidel(self, order, t: int, tol: float, max_iter: int, omega: float = 1.0) -> int:
        for it in range(max_iter):
            delta = 0.0
            for eq, var in order:
                delta = max(delta, self._solve_one(eq, var, t, tol * 1e-2, omega))
            if not math.isfinite(delta) or delta > 1e12:
                raise RuntimeError(f"{t}年度: Gauss-Seidel が発散")
            if delta < tol:
                return it + 1
        worst = sorted(((abs(self.residual(eq, t)), eq.name) for eq, _ in order), reverse=True)[:5]
        raise RuntimeError(f"{t}年度: {max_iter}回で収束しない。残差の大きい式: {worst}")

    def _newton_block(self, block, t: int, tol: float, max_iter: int) -> int:
        import numpy as np
        eqs = [eq for eq, _ in block]
        vars_ = [v for _, v in block]
        idx = {v: j for j, v in enumerate(vars_)}
        users = {v: [] for v in vars_}
        for i, eq in enumerate(eqs):
            for v in contemporaneous_uses(eq) | {eq.name}:
                if v in users:
                    users[v].append(i)
        cols = [self.data[v] for v in vars_]
        n = len(eqs)

        def resid() -> np.ndarray:
            return np.array([self.residual(eq, t) for eq in eqs])

        f = resid()
        for it in range(max_iter):
            J = np.zeros((n, n))
            for j, v in enumerate(vars_):
                x = cols[j][t]
                h = 1e-7 * max(abs(x), 1.0)
                cols[j][t] = x + h
                for i in users[v]:
                    try:
                        J[i, j] = (self.residual(eqs[i], t) - f[i]) / h
                    except (ValueError, ZeroDivisionError, OverflowError):
                        J[i, j] = 0.0
                cols[j][t] = x
            try:
                dx = np.linalg.solve(J, -f)
            except np.linalg.LinAlgError:
                dx = np.linalg.lstsq(J, -f, rcond=None)[0]
            x0 = np.array([c[t] for c in cols])
            norm0 = np.max(np.abs(f))
            lam = 1.0
            for _ in range(30):
                for j, c in enumerate(cols):
                    c[t] = x0[j] + lam * dx[j]
                try:
                    f_new = resid()
                    if np.all(np.isfinite(f_new)) and (np.max(np.abs(f_new)) <= norm0 * (1 - 1e-4 * lam) or lam < 1e-3):
                        break
                except (ValueError, ZeroDivisionError, OverflowError):
                    pass
                lam *= 0.5
            else:
                raise RuntimeError(f"{t}年度: ブロック（{len(eqs)}本、{vars_[:3]}…）で歩幅を縮めても残差が下がらない")
            f = f_new
            rel = np.max(np.abs(lam * dx) / np.maximum(np.abs(x0), 1.0))
            if rel < tol:
                return it + 1
        worst = sorted(zip(np.abs(f), [e.name for e in eqs]), reverse=True)[:5]
        raise RuntimeError(f"{t}年度: ブロック（{len(eqs)}本）が {max_iter} 回で収束しない。残差の大きい式: {worst}")


def contemporaneous_uses(eq) -> set[str]:
    """式の中で同時点（ラグ0）に使われている変数."""
    import re
    return set(re.findall(r"V\('([^']+)',t\)", eq.py))


def order_equations(model: Model) -> list[list[str]]:
    """同時点の依存関係から強連結成分（同時に解くブロック）を求め、解く順に並べる（Tarjan、反復版）."""
    en = {e.name for e in model.eqs}
    deps = {e.name: sorted(contemporaneous_uses(e) & en - {e.name}) for e in model.eqs}
    index, low, onstack, stack, comps = {}, {}, set(), [], []
    counter = 0
    for root in deps:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                onstack.add(v)
            recurse = False
            ds = deps[v]
            while i < len(ds):
                w = ds[i]
                i += 1
                if w not in index:
                    work.append((v, i))
                    work.append((w, 0))
                    recurse = True
                    break
                if w in onstack:
                    low[v] = min(low[v], index[w])
            if recurse:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                comps.append(comp)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return comps  # 依存先が先に来る順（Tarjan の出力順）


def _blocks(pairs):
    """(式, 解く変数) の組を、同時点の依存関係による強連結成分に分け、解く順に並べる."""
    target = {eq.name: v for eq, v in pairs}
    by_var = {v: (eq, v) for eq, v in pairs}
    deps = {}
    for eq, v in pairs:
        used = contemporaneous_uses(eq) | {eq.name}
        deps[v] = sorted(u for u in used if u in by_var and u != v)
    index, low, onstack, stack, comps = {}, {}, set(), [], []
    counter = 0
    for root in deps:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                onstack.add(v)
            recurse = False
            ds = deps[v]
            while i < len(ds):
                w = ds[i]
                i += 1
                if w not in index:
                    work.append((v, i))
                    work.append((w, 0))
                    recurse = True
                    break
                if w in onstack:
                    low[v] = min(low[v], index[w])
            if recurse:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(by_var[w])
                    if w == v:
                        break
                comps.append(comp)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    _ = target
    return comps
