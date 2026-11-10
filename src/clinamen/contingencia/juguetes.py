"""Los cinco juguetes del banco canónico (§13.2) como cadenas de Markov finitas.

Cada sistema continuo se discretiza en una rejilla; la cadena resultante ES el juguete: se simula y se calcula
exactamente con los mismos núcleos. Sus parámetros son supuestos de banco de pruebas, sin contenido histórico.

| Juguete | Qué pone a prueba |
| --- | --- |
| doble_pozo_gaussiano | committor, ley de Kramers, κ repartido |
| doble_pozo_estable | salida por salto único (cola pesada de índice α), κ concentrado |
| urna_polya | memoria permanente, meseta de Λ |
| lento_rapido | reducción de escalas con límite homogeneizado conocido (§3.5) |
| doble_pozo_deriva | vuelco de tipo B por deriva de parámetro, señales tempranas |
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.stats import norm

from .cadena import CadenaFinita


def _rejilla(n, L):
    x = np.linspace(-L, L, n)
    dx = x[1] - x[0]
    bordes = np.concatenate([[-np.inf], (x[:-1] + x[1:]) / 2, [np.inf]])
    return x, dx, bordes


def _nucleo_gaussiano(x, bordes, media, sd, ancho=8.0):
    """Fila i: N(media_i, sd²) integrada en las celdas (las colas van a las celdas extremas)."""
    n = x.size
    filas, cols, vals = [], [], []
    dx = x[1] - x[0]
    for i in range(n):
        lo = max(0, int(np.searchsorted(x, media[i] - ancho * sd)) - 1)
        hi = min(n, int(np.searchsorted(x, media[i] + ancho * sd)) + 2)
        j = np.arange(lo, hi)
        a = bordes[j].copy()
        b = bordes[j + 1].copy()
        if lo == 0:
            a[0] = -np.inf
        if hi == n:
            b[-1] = np.inf
        p = norm.cdf((b - media[i]) / sd) - norm.cdf((a - media[i]) / sd)
        p = np.maximum(p, 0.0)
        p /= p.sum()
        filas.append(np.full(j.size, i)); cols.append(j); vals.append(p)
    del dx
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(filas), np.concatenate(cols))), shape=(n, n))


def _deriva_doble_pozo(x, mu=0.0):
    return x - x ** 3 + mu          # −V'(x) con V = x⁴/4 − x²/2 − μ x


def doble_pozo_gaussiano(n=121, L=2.2, dt=0.1, sigma=0.65, T=60, x0=-1.0) -> CadenaFinita:
    x, dx, bordes = _rejilla(n, L)
    K = _nucleo_gaussiano(x, bordes, x + dt * _deriva_doble_pozo(x), sigma * np.sqrt(dt))
    p0 = np.zeros(n); p0[np.argmin(np.abs(x - x0))] = 1.0
    return CadenaFinita([K], T, p0, x > 0, x, nombre="doble_pozo_gaussiano",
                        etiquetas=(x > 0).astype(np.int64))


def doble_pozo_estable(n=121, L=2.2, dt=0.1, sigma=0.3, alfa=1.5, tasa_saltos=0.08, escala_salto=0.35, T=60,
                       x0=-1.0) -> CadenaFinita:
    """Deriva de doble pozo + ruido gaussiano pequeño + saltos de Pareto simétricos de índice α (cola pesada)."""
    x, dx, bordes = _rejilla(n, L)
    G = _nucleo_gaussiano(x, bordes, x + dt * _deriva_doble_pozo(x), sigma * np.sqrt(dt)).toarray()
    # núcleo de salto: |Δ| ~ Pareto(escala, α) truncada al dominio, signo simétrico
    d = np.abs(x[:, None] - x[None, :])
    J = np.where(d >= escala_salto, (np.maximum(d, escala_salto) / escala_salto) ** (-(1.0 + alfa)), 0.0)
    J /= J.sum(axis=1, keepdims=True)
    q = tasa_saltos * dt
    K = (1.0 - q) * G + q * (G @ J)
    K /= K.sum(axis=1, keepdims=True)
    p0 = np.zeros(n); p0[np.argmin(np.abs(x - x0))] = 1.0
    return CadenaFinita([sp.csr_matrix(K)], T, p0, x > 0, x, nombre="doble_pozo_estable",
                        etiquetas=(x > 0).astype(np.int64))


def urna_polya(T=80, rojas0=1, total0=2) -> CadenaFinita:
    """Estado = número de bolas rojas; en el paso t hay total0 + t bolas. B = mayoría roja en T."""
    n = total0 + T + 1
    r = np.arange(n)
    nucleos = []
    for t in range(T):
        tot = total0 + t
        p = np.clip(r / tot, 0.0, 1.0)
        filas = np.concatenate([r, r[:-1]])
        cols = np.concatenate([r, r[:-1] + 1])
        vals = np.concatenate([1.0 - p, p[:-1]])
        vals[n - 1] = 1.0 if p[-1] >= 1 else vals[n - 1]
        K = sp.csr_matrix((vals, (filas, cols)), shape=(n, n))
        K = sp.csr_matrix(K.toarray() / K.toarray().sum(axis=1, keepdims=True))
        nucleos.append(K)
    p0 = np.zeros(n); p0[rojas0] = 1.0
    final = total0 + T
    return CadenaFinita(nucleos, T, p0, r / final > 0.5, r.astype(float), nombre="urna_polya",
                        etiquetas=r.astype(np.int64))


def lento_rapido(nx=61, rho=0.6, sesgo=0.5, T=150, x0=None) -> CadenaFinita:
    """x lento (rejilla de nx puntos, se mueve ±1 por paso) empujado por y rápido ∈ {−1, 0, 1}.

    y se queda igual con probabilidad ρ; si no, se sortea de π_x, sesgada por la deriva de un doble pozo en x.
    Límite homogeneizado (Green-Kubo): deriva b(x) = E_{π_x}[y] y difusión por paso
    D(x) = Var_{π_x}(y) (1 + ρ)/(1 − ρ) (§3.5).
    """
    xs = np.linspace(-1.6, 1.6, nx)
    ys = np.array([-1, 0, 1])
    n = nx * 3
    filas, cols, vals = [], [], []
    for i in range(nx):
        b = np.tanh(sesgo * _deriva_doble_pozo(xs[i]))
        pi = np.array([(1 - b) / 3, 1 / 3, (1 + b) / 3])
        for jy in range(3):
            s = i * 3 + jy
            prob_y = (1 - rho) * pi
            prob_y[jy] += rho
            for jn in range(3):
                i2 = min(max(i + ys[jn], 0), nx - 1)
                filas.append(s); cols.append(i2 * 3 + jn); vals.append(prob_y[jn])
    K = sp.csr_matrix((vals, (filas, cols)), shape=(n, n))
    K.sum_duplicates()
    rasgos = np.stack([np.repeat(xs, 3), np.tile(ys, nx).astype(float)], axis=1)
    i0 = np.argmin(np.abs(xs - (-1.0 if x0 is None else x0)))
    p0 = np.zeros(n); p0[i0 * 3 + 1] = 1.0
    return CadenaFinita([K], T, p0, rasgos[:, 0] > 0, rasgos, nombre="lento_rapido",
                        etiquetas=(rasgos[:, 0] > 0).astype(np.int64))


def lento_rapido_homogeneizado(nx=61, rho=0.6, sesgo=0.5, T=150, x0=None) -> CadenaFinita:
    """Cadena 1D en x con la deriva y la difusión de Green-Kubo del juguete lento-rápido.

    El paso en índices de rejilla es una normal discretizada de media b(x) = E_π[y] y varianza
    D(x) = Var_π(y) (1 + ρ)/(1 − ρ), con reflexión en los bordes (masa exterior a la celda extrema).
    """
    xs = np.linspace(-1.6, 1.6, nx)
    idx = np.arange(nx, dtype=float)
    bordes = np.concatenate([[-np.inf], idx[:-1] + 0.5, [np.inf]])
    media, sd = np.empty(nx), np.empty(nx)
    for i in range(nx):
        b = np.tanh(sesgo * _deriva_doble_pozo(xs[i]))
        m = 2 * b / 3
        media[i] = i + m
        sd[i] = np.sqrt((2 / 3 - m ** 2) * (1 + rho) / (1 - rho))
    K = sp.vstack([_nucleo_gaussiano(idx, bordes, media[i:i + 1].repeat(nx), sd[i])[i] for i in range(nx)])
    p0 = np.zeros(nx); p0[np.argmin(np.abs(xs - (-1.0 if x0 is None else x0)))] = 1.0
    return CadenaFinita([sp.csr_matrix(K)], T, p0, xs > 0, xs, nombre="lento_rapido_homogeneizado")


def doble_pozo_deriva(n=121, L=2.2, dt=0.1, sigma=0.35, T=80, mu_final=0.5, x0=-1.0) -> CadenaFinita:
    """V(x, t) = x⁴/4 − x²/2 − μ(t) x con μ creciendo linealmente de 0 a mu_final: el pozo izquierdo desaparece
    en μ_c = 2/(3√3) ≈ 0.385 (bifurcación silla-nodo, vuelco de tipo B)."""
    x, dx, bordes = _rejilla(n, L)
    nucleos = []
    for t in range(T):
        mu = mu_final * t / (T - 1)
        nucleos.append(_nucleo_gaussiano(x, bordes, x + dt * _deriva_doble_pozo(x, mu), sigma * np.sqrt(dt)))
    p0 = np.zeros(n); p0[np.argmin(np.abs(x - x0))] = 1.0
    return CadenaFinita(nucleos, T, p0, x > 0, x, nombre="doble_pozo_deriva", etiquetas=(x > 0).astype(np.int64))


JUGUETES = {
    "doble_pozo_gaussiano": doble_pozo_gaussiano,
    "doble_pozo_estable": doble_pozo_estable,
    "urna_polya": urna_polya,
    "lento_rapido": lento_rapido,
    "doble_pozo_deriva": doble_pozo_deriva,
}
