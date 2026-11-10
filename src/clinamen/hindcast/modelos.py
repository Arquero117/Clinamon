"""M3/M6 — Tres modelos rivales de la dinámica secular de un observable de escala social (F2a).

Todos comparten la observación por polity: en cada paso de 100 años, con probabilidad q la polity continúa y el
valor codificado no cambia (cambio exactamente 0); si no, el cambio Δ sigue la dinámica del rival:

* R1, crecimiento logístico hacia un techo con colapsos de cola pesada:
  Δ = a_r (K − y)/(K − L) + s ε con probabilidad 1 − p; Δ = a_r (K − y)/(K − L) − J con probabilidad p,
  J ~ Lomax(α, β) (cola de potencia).
* R2, paseo aleatorio con deriva: Δ = μ_r + s t_ν.
* R3, reversión a un nivel regional (Ornstein-Uhlenbeck discreto): Δ = κ (m_r − y) + s ε.

Jerarquía: el parámetro regional (a_r, μ_r, m_r) es el común más una desviación por gran región con prior normal
N(0, τ²) (encogimiento; τ es un supuesto declarado). Estimación por máxima verosimilitud penalizada (= máximo a
posteriori); incertidumbre paramétrica por aproximación de Laplace (inversa de la hessiana numérica). q tiene
posterior Beta. Una región sin datos de entrenamiento recibe una desviación sorteada de N(0, τ²).

Parámetros y procedencia (A13): todos «estimado» por los datos del panel, salvo τ y los priores débiles de los
parámetros globales, «supuesto» (valores en TAU y en los comentarios).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, special, stats

TAU = {"R1": 0.3, "R2": 0.3, "R3": 1.0}     # supuesto: escala de la variación entre regiones del parámetro regional
PASO = 100


@dataclass
class Transiciones:
    """Pares (y_t, y_{t+100}) de una misma región y siglos consecutivos."""
    y: np.ndarray
    dy: np.ndarray
    region: np.ndarray      # índice entero de gran región

    @classmethod
    def desde_panel(cls, panel, variable: str, regiones: list, hasta: float | None = None):
        d = panel.sort_values(["NGA", "anio"])
        sig = d.groupby("NGA")[variable].shift(-1)
        a_sig = d.groupby("NGA")["anio"].shift(-1)
        ok = (a_sig - d["anio"] == PASO) & sig.notna()
        if hasta is not None:
            ok &= a_sig <= hasta
        idx = {r: i for i, r in enumerate(regiones)}
        return cls(d.loc[ok, variable].to_numpy(float), (sig - d[variable])[ok].to_numpy(float),
                   d.loc[ok, "region"].map(idx).to_numpy(int))


def _e(x):
    """exp acotado: las extracciones de Laplace pueden llevar un log-parámetro a valores absurdos."""
    return np.exp(np.clip(x, -12.0, 8.0))


class Rival:
    nombre = ""

    def __init__(self, n_regiones: int):
        self.R = n_regiones

    # -- interfaz que define cada rival
    def x0(self, tr: Transiciones) -> np.ndarray: ...
    def logf(self, th, y, dy, reg) -> np.ndarray: ...
    def penalizacion(self, th) -> float: ...
    def sortear(self, th, y, reg, rng) -> np.ndarray: ...

    # -- común
    def ajustar(self, tr: Transiciones, rng: np.random.Generator, n_parametros: int = 200):
        nz = tr.dy != 0
        self.L = float(np.min(tr.y + np.minimum(tr.dy, 0)) - 0.5)
        self.U = float(np.max(tr.y + np.maximum(tr.dy, 0)) + 0.5)
        y, dy, reg = tr.y[nz], tr.dy[nz], tr.region[nz]
        self.con_datos = np.zeros(self.R, bool)
        self.con_datos[np.unique(tr.region)] = True

        def obj(th):
            v = -np.sum(self.logf(th, y, dy, reg)) + self.penalizacion(th)
            return v if np.isfinite(v) else 1e12

        x0 = self.x0(tr)
        r = optimize.minimize(obj, x0, method="L-BFGS-B")
        r = optimize.minimize(obj, r.x, method="BFGS", options={"gtol": 1e-5, "maxiter": 2000})
        self.th = r.x
        H = _hessiana(obj, r.x)
        try:
            cov = np.linalg.inv(H)
            cov = 0.5 * (cov + cov.T)
            w, V = np.linalg.eigh(cov)
            cov = (V * np.maximum(w, 1e-10)) @ V.T
        except np.linalg.LinAlgError:
            cov = np.eye(len(r.x)) * 1e-6
        self.muestras_th = rng.multivariate_normal(r.x, cov, size=n_parametros)
        self.ceros = int(np.sum(~nz)), int(np.sum(nz))
        self.nll = float(r.fun)
        return self

    def predecir(self, y0: np.ndarray, reg0: np.ndarray, pasos: int, n_muestras: int,
                 rng: np.random.Generator) -> np.ndarray:
        """Muestras de la predictiva tras 1..pasos siglos: array (len(y0), pasos, n_muestras).

        Cada muestra lleva su propio vector de parámetros (incertidumbre paramétrica de Laplace) y su q.
        """
        P = len(self.muestras_th)
        out = np.empty((len(y0), pasos, n_muestras))
        for i, (yi, ri) in enumerate(zip(y0, reg0)):
            sel = rng.integers(0, P, n_muestras)
            TH = self.muestras_th[sel].T                         # (p, n)
            q = rng.beta(self.ceros[0] + 1, self.ceros[1] + 1, size=n_muestras)
            desv = None if self.con_datos[ri] else rng.normal(0.0, TAU[self.nombre], size=n_muestras)
            y = np.full(n_muestras, float(yi))
            reg = np.full(n_muestras, int(ri))
            for k in range(pasos):
                cambia = rng.random(n_muestras) >= q
                d = self.sortear(TH, y, reg, rng, desv)
                y = np.where(cambia, np.clip(y + d, self.L - 2, self.U + 2), y)
                out[i, k] = y
        return out


def _hessiana(f, x, h=1e-4):
    n = x.size
    H = np.empty((n, n))
    f0 = f(x)
    E = np.eye(n) * h
    fi = np.array([f(x + E[i]) for i in range(n)])
    for i in range(n):
        for j in range(i, n):
            v = (f(x + E[i] + E[j]) - fi[i] - fi[j] + f0) / (h * h)
            H[i, j] = H[j, i] = v
    return H


def _regional(de, reg, desv):
    """Desviación regional por muestra: de es (R,) o (R, n); desv sustituye si la región no tiene datos."""
    if desv is not None:
        return desv
    if de.ndim == 1:
        return de[reg]
    return de[reg, np.arange(reg.size)]


class R2(Rival):
    """Paseo aleatorio con deriva regional y choques t de Student. th = [μ, δ_1..δ_R, log s, log(ν − 2)]."""
    nombre = "R2"

    def x0(self, tr):
        d = tr.dy[tr.dy != 0]
        return np.concatenate([[np.mean(d)], np.zeros(self.R), [np.log(np.std(d) + 1e-3)], [np.log(3.0)]])

    def _p(self, th):
        return th[0], th[1:1 + self.R], _e(th[1 + self.R]), 2.0 + _e(th[2 + self.R])

    def logf(self, th, y, dy, reg):
        mu, de, s, nu = self._p(th)
        return stats.t.logpdf(dy, nu, loc=mu + de[reg], scale=s)

    def penalizacion(self, th):
        mu, de, s, nu = self._p(th)
        return 0.5 * np.sum(de ** 2) / TAU["R2"] ** 2

    def sortear(self, th, y, reg, rng, desv):
        mu, de, s, nu = self._p(th)
        loc = mu + _regional(de, reg, desv)
        return loc + s * rng.standard_t(nu, size=y.size)


class R3(Rival):
    """Reversión a un nivel regional. th = [logit κ, m, δm_1..δm_R, log s]."""
    nombre = "R3"

    def x0(self, tr):
        d = tr.dy[tr.dy != 0]
        return np.concatenate([[-1.0], [np.mean(tr.y)], np.zeros(self.R), [np.log(np.std(d) + 1e-3)]])

    def _p(self, th):
        return special.expit(th[0]), th[1], th[2:2 + self.R], _e(th[2 + self.R])

    def logf(self, th, y, dy, reg):
        k, m, de, s = self._p(th)
        return stats.norm.logpdf(dy, loc=k * (m + de[reg] - y), scale=s)

    def penalizacion(self, th):
        return 0.5 * np.sum(self._p(th)[2] ** 2) / TAU["R3"] ** 2

    def sortear(self, th, y, reg, rng, desv):
        k, m, de, s = self._p(th)
        nivel = m + _regional(de, reg, desv)
        return k * (nivel - y) + s * rng.standard_normal(y.size)


class R1(Rival):
    """Logístico hacia un techo con colapsos de Lomax.
    th = [a, δa_1..δa_R, log(K − L), log s, logit p, log α, log β]."""
    nombre = "R1"

    def x0(self, tr):
        d = tr.dy[tr.dy != 0]
        return np.concatenate([[0.2], np.zeros(self.R), [np.log(self.U - self.L)],
                               [np.log(np.std(d) + 1e-3)], [-2.0], [np.log(2.0)], [np.log(0.5)]])

    def _p(self, th):
        R = self.R
        return (th[0], th[1:1 + R], self.L + _e(th[1 + R]), _e(th[2 + R]), special.expit(th[3 + R]),
                np.maximum(_e(th[4 + R]), 0.05), _e(th[5 + R]))

    def _g(self, a, de, K, y, reg_o_desv):
        return (a + reg_o_desv) * np.maximum(K - y, 0.0) / (K - self.L)

    def logf(self, th, y, dy, reg):
        a, de, K, s, p, al, be = self._p(th)
        g = self._g(a, de, K, y, de[reg])
        l_norm = np.log1p(-p) + stats.norm.logpdf(dy, loc=g, scale=s)
        x = g - dy
        l_col = np.where(x > 0, np.log(p) + np.log(al / be) - (al + 1) * np.log1p(np.maximum(x, 0) / be), -np.inf)
        return np.logaddexp(l_norm, l_col)

    def penalizacion(self, th):
        a, de, K, s, p, al, be = self._p(th)
        return 0.5 * np.sum(de ** 2) / TAU["R1"] ** 2 + 0.5 * (np.log(al) / 2.0) ** 2   # prior débil en α

    def ajustar(self, tr, rng, n_parametros=200):
        self.L = float(np.min(tr.y + np.minimum(tr.dy, 0)) - 0.5)
        self.U = float(np.max(tr.y + np.maximum(tr.dy, 0)) + 0.5)
        return super().ajustar(tr, rng, n_parametros)

    def sortear(self, th, y, reg, rng, desv):
        a, de, K, s, p, al, be = self._p(th)
        g = self._g(a, de, K, y, _regional(de, reg, desv))
        col = rng.random(y.size) < p
        u = rng.random(y.size)
        J = be * np.expm1(-np.log(u) / al)                           # Lomax por cuantil inverso
        return np.where(col, g - np.minimum(J, 20.0), g + s * rng.standard_normal(y.size))


RIVALES = {"R1": R1, "R2": R2, "R3": R3}
