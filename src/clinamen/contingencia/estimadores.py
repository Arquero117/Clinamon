"""M8 — Estimadores de contingencia a partir de trayectorias simuladas.

Estos estimadores no conocen el modelo: solo ven rasgos del estado por instante y el desenlace. Se usan igual
con un juguete del banco canónico que con el motor completo, y en F1 se validan contra los valores exactos.

* Committor por regresión logística por instante sobre una base polinómica (§6.5, vía por defecto).
* Committor por disparos (§6.5, validación en puntos clave).
* Presupuesto de contingencia ρ̂_t (Teorema 2).
* Perfil de la ruta más barata κ̂_t sobre trayectorias que acaban en B (Teorema 3): κ̂_t es la media de
  log ĥ_{t+1}(X_{t+1}) − log ĥ_t(X_t), que es el logaritmo de la densidad de la transformada h de Doob.
* Rastro de un POD por la cota de Donsker-Varadhan con función ajustada en una mitad (§5.7).
* Espectro de tiempos implícitos y dos regímenes por el segundo vector propio (§7.1, §8.1).

Todas las cifras van con su error típico de Monte Carlo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.polynomial import legendre


# ---------------------------------------------------------------------- base y regresión
@dataclass
class Escalado:
    lo: np.ndarray
    hi: np.ndarray

    @classmethod
    def ajustar(cls, X):
        lo, hi = X.min(axis=0), X.max(axis=0)
        return cls(lo, np.where(hi > lo, hi, lo + 1.0))

    def __call__(self, X):
        return np.clip(2.0 * (X - self.lo) / (self.hi - self.lo) - 1.0, -1.0, 1.0)


def base_polinomica(Z: np.ndarray, grado: int) -> np.ndarray:
    """Polinomios de Legendre de grado total ≤ grado en las columnas de Z ∈ [−1, 1]^d (d ≤ 3)."""
    n, d = Z.shape
    P = [legendre.legvander(Z[:, j], grado) for j in range(d)]
    cols = []
    if d == 1:
        cols = [P[0][:, k] for k in range(grado + 1)]
    elif d == 2:
        cols = [P[0][:, a] * P[1][:, b] for a in range(grado + 1) for b in range(grado + 1 - a)]
    elif d == 3:
        cols = [P[0][:, a] * P[1][:, b] * P[2][:, c] for a in range(grado + 1) for b in range(grado + 1 - a)
                for c in range(grado + 1 - a - b)]
    else:
        raise ValueError("base polinómica para d ≤ 3; usa rasgos reducidos")
    return np.stack(cols, axis=1)


def _bsplines(z: np.ndarray, nodos: int) -> np.ndarray:
    """B-splines cúbicos con nodos interiores equiespaciados en [−1, 1]; sus columnas suman 1."""
    from scipy.interpolate import BSpline
    k = 3
    interior = np.linspace(-1.0, 1.0, nodos + 2)
    t = np.concatenate([[-1.0] * k, interior, [1.0] * k])
    zz = np.clip(z, -1.0, 1.0 - 1e-12)
    return BSpline.design_matrix(zz, t, k).toarray()


@dataclass
class Base:
    """Base de regresión flexible: B-splines en rasgos continuos, indicadores en rasgos con ≤ 5 valores,
    producto tensorial entre bloques (d ≤ 2) y constante implícita (las columnas de cada bloque suman 1)."""
    escala: Escalado
    categorias: list          # por rasgo: array de valores si es categórico, None si continuo
    nodos: int

    @classmethod
    def ajustar(cls, X, nodos: int = 12):
        cats = []
        for j in range(X.shape[1]):
            v = np.unique(X[:, j])
            cats.append(v if v.size <= 5 else None)
        return cls(Escalado.ajustar(X), cats, nodos)

    def __call__(self, X):
        Z = self.escala(X)
        bloques = []
        for j, c in enumerate(self.categorias):
            if c is not None:
                bloques.append((X[:, j][:, None] == c[None, :]).astype(float))
            else:
                bloques.append(_bsplines(Z[:, j], self.nodos))
        M = bloques[0]
        for b in bloques[1:]:
            M = (M[:, :, None] * b[:, None, :]).reshape(M.shape[0], -1)
        return M


@dataclass
class Logistica:
    """Regresión logística con penalización L2 suave, por Newton-IRLS."""
    beta: np.ndarray
    cov: np.ndarray

    @classmethod
    def ajustar(cls, Phi, y, w=None, ridge=1e-4, iters=50):
        n, k = Phi.shape
        w = np.ones(n) if w is None else w
        beta = np.zeros(k)
        R = ridge * n * np.eye(k)
        H = R
        for _ in range(iters):
            eta = Phi @ beta
            p = 1.0 / (1.0 + np.exp(-eta))
            W = w * p * (1 - p)
            g = Phi.T @ (w * (y - p)) - R @ beta
            H = Phi.T @ (Phi * W[:, None]) + R + 1e-10 * np.eye(k)
            paso = np.linalg.solve(H, g)
            beta = beta + paso
            if np.max(np.abs(paso)) < 1e-9:
                break
        return cls(beta, np.linalg.inv(H))

    def eta(self, Phi):
        return Phi @ self.beta

    def prob(self, Phi):
        return 1.0 / (1.0 + np.exp(-self.eta(Phi)))

    def error_tipico_prob(self, Phi):
        p = self.prob(Phi)
        var_eta = np.einsum("ij,jk,ik->i", Phi, self.cov, Phi)
        return p * (1 - p) * np.sqrt(np.maximum(var_eta, 0.0))


# ---------------------------------------------------------------------- committor
@dataclass
class Committor:
    """ĥ_t(x) = P(B | X_t = x) estimado por regresión logística independiente en cada instante."""
    modelos: list
    bases: list
    nodos: int
    constantes: list   # instantes donde el rasgo no varía: ĥ = frecuencia (con su error típico)

    @classmethod
    def ajustar(cls, rasgos: np.ndarray, desenlace: np.ndarray, nodos: int = 12):
        """rasgos: (T+1, n, d); desenlace: (n,) booleano. El instante T se fija al indicador."""
        T1, n, d = rasgos.shape
        y = desenlace.astype(np.float64)
        modelos, bases, ctes = [], [], []
        for t in range(T1 - 1):
            X = rasgos[t]
            if np.all(X.max(axis=0) == X.min(axis=0)):
                f = (y.sum() + 0.5) / (n + 1.0)
                modelos.append(None); bases.append(None); ctes.append((f, np.sqrt(f * (1 - f) / n)))
                continue
            base = Base.ajustar(X, nodos)
            modelos.append(Logistica.ajustar(base(X), y, ridge=1e-6)); bases.append(base); ctes.append(None)
        return cls(modelos, bases, nodos, ctes)

    @property
    def T(self):
        return len(self.modelos)

    def __call__(self, t: int, X: np.ndarray, error_tipico: bool = False):
        if self.constantes[t] is not None:
            f, se = self.constantes[t]
            h = np.full(X.shape[0], f)
            return (h, np.full(X.shape[0], se)) if error_tipico else h
        Phi = self.bases[t](X)
        m = self.modelos[t]
        return (m.prob(Phi), m.error_tipico_prob(Phi)) if error_tipico else m.prob(Phi)

    def en_trayectorias(self, rasgos, desenlace):
        """ĥ_t(X_t) a lo largo de trayectorias: (T+1, n), con ĥ_T = 1_B."""
        T1, n, _ = rasgos.shape
        H = np.empty((T1, n))
        for t in range(T1 - 1):
            H[t] = self(t, rasgos[t])
        H[-1] = desenlace
        return H


def committor_disparos(simular_desde, n: int):
    """h(x, t) por disparos: simular_desde(n) devuelve n desenlaces booleanos desde el estado de interés."""
    y = np.asarray(simular_desde(n), bool)
    p = y.mean()
    return p, np.sqrt(max(p * (1 - p), 1e-12) / n)


# ---------------------------------------------------------------------- Teorema 2
def _bootstrap(f, n, reps=200, semilla=0):
    rng = np.random.default_rng(semilla)
    vals = [f(rng.integers(0, n, n)) for _ in range(reps)]
    return float(np.std(vals, ddof=1))


def presupuesto_cruzado(H1: np.ndarray, H2: np.ndarray, desenlace: np.ndarray, bootstrap: int = 200):
    """ρ̂_t sin sesgo por ruido del committor: media de Δĥ¹_t · Δĥ²_t con ĥ¹ y ĥ² ajustados en mitades
    independientes y evaluados en trayectorias de prueba ajenas a ambas.

    Si ĥ^k = h + ε^k con ε¹ y ε² independientes y de media cero, E[Δĥ¹ Δĥ²] = E[(Δh)²]: el ruido de ajuste no
    se suma al presupuesto, como sí ocurre con (Δĥ)².
    """
    P = np.diff(H1, axis=0) * np.diff(H2, axis=0)
    y = desenlace.astype(float)

    def dif(idx):
        m0 = y[idx].mean()
        return P[:, idx].mean(axis=1).sum() - m0 * (1 - m0)

    rho = P.mean(axis=1)
    m0 = y.mean()
    return {"rho": rho, "suma": float(rho.sum()), "incertidumbre_inicial": float(m0 * (1 - m0)),
            "diferencia": float(dif(np.arange(y.size))), "error_tipico": _bootstrap(dif, y.size, bootstrap)}


def presupuesto(H: np.ndarray, desenlace: np.ndarray, bootstrap: int = 200):
    """ρ̂_t = media de (ĥ_{t+1} − ĥ_t)² y contraste del Teorema 2 con su error típico.

    Devuelve dict con rho (T,), suma, incertidumbre_inicial = M̂0 (1 − M̂0) con M̂0 la frecuencia de B,
    diferencia y su error típico por bootstrap sobre trayectorias.
    """
    D2 = np.diff(H, axis=0) ** 2
    y = desenlace.astype(float)

    def dif(idx):
        m0 = y[idx].mean()
        return D2[:, idx].mean(axis=1).sum() - m0 * (1 - m0)

    rho = D2.mean(axis=1)
    m0 = y.mean()
    return {"rho": rho, "suma": float(rho.sum()), "incertidumbre_inicial": float(m0 * (1 - m0)),
            "diferencia": float(dif(np.arange(y.size))), "error_tipico": _bootstrap(dif, y.size, bootstrap)}


# ---------------------------------------------------------------------- Teorema 3
def perfil_kappa(H: np.ndarray, desenlace: np.ndarray, piso: float = 1e-6, bootstrap: int = 200,
                 error_relativo_h0: float = 0.0):
    """κ̂_t sobre las trayectorias que acaban en B y contraste Σκ̂ = −log P̂(B).

    Σκ̂ telescopa a −log ĥ_0, de modo que el contraste compara dos estimaciones de P(B): la del committor
    ajustado y la frecuencia en las trayectorias de prueba. El error típico suma ambas fuentes:
    bootstrap sobre las trayectorias de prueba y ``error_relativo_h0`` = se(ĥ_0)/ĥ_0 del ajuste.
    """
    y = desenlace.astype(bool)
    L = np.log(np.maximum(H[:, y], piso))
    inc = np.diff(L, axis=0)                     # (T, n_B)
    kappa = inc.mean(axis=1)
    n = y.size
    nB = int(y.sum())

    def dif(idx):
        yy = y[idx]
        pb = max(yy.mean(), 1.0 / n)
        LB = np.log(np.maximum(H[:, idx][:, yy], piso))
        return float(np.diff(LB, axis=0).mean(axis=1).sum() + np.log(pb))

    return {"kappa": kappa, "error_tipico_t": inc.std(axis=1, ddof=1) / np.sqrt(nB), "suma": float(kappa.sum()),
            "menos_log_PB": float(-np.log(y.mean())), "diferencia": dif(np.arange(n)),
            "error_tipico": float(np.hypot(_bootstrap(dif, n, bootstrap), error_relativo_h0)), "n_B": nB}


def agregar_tramos(v: np.ndarray, tramos: int = 10) -> np.ndarray:
    return np.array([s.sum() for s in np.array_split(v, tramos)])


def error_L1_relativo(est: np.ndarray, exacto: np.ndarray, tramos: int = 10) -> float:
    a, b = agregar_tramos(est, tramos), agregar_tramos(exacto, tramos)
    return float(np.abs(a - b).sum() / np.abs(b).sum())


# ---------------------------------------------------------------------- Teorema 1: rastro
def _rasgos_y(Y):
    Y = np.asarray(Y)
    return Y[:, None].astype(float) if Y.ndim == 1 else Y.astype(float)


def rastro_dv(Y_Q: np.ndarray, Y_P: np.ndarray, grado: int = 4, categorico: bool | None = None,
              semilla: int = 0):
    """Cota inferior de Donsker-Varadhan de KL(Q_Y ‖ P_Y), con f ajustada en una mitad y evaluada en la otra.

    f es el log-cociente de densidades estimado por regresión logística (brazo Q frente a P) sobre una base
    polinómica de Y, o sobre indicadores si Y es categórico con pocos valores.
    ê = E_Q2[f] − log E_P2[e^f]. Error típico por el método delta.
    """
    YQ, YP = _rasgos_y(Y_Q), _rasgos_y(Y_P)
    rng = np.random.default_rng(semilla)
    iq, ip = rng.permutation(len(YQ)), rng.permutation(len(YP))
    q1, q2 = iq[: len(iq) // 2], iq[len(iq) // 2:]
    p1, p2 = ip[: len(ip) // 2], ip[len(ip) // 2:]
    if categorico is None:
        categorico = YQ.shape[1] == 1 and len(np.unique(np.concatenate([YQ[:, 0], YP[:, 0]]))) <= 12
    if categorico:
        vals = np.unique(np.concatenate([YQ[:, 0], YP[:, 0]]))
        nq = np.array([(YQ[q1, 0] == v).sum() for v in vals]) + 0.5
        np_ = np.array([(YP[p1, 0] == v).sum() for v in vals]) + 0.5
        tabla = np.log(nq / nq.sum()) - np.log(np_ / np_.sum())
        f = lambda Y: tabla[np.searchsorted(vals, Y[:, 0])]
    else:
        X = np.concatenate([YQ[q1], YP[p1]])
        etiqueta = np.concatenate([np.ones(len(q1)), np.zeros(len(p1))])
        esc = Escalado.ajustar(X)
        m = Logistica.ajustar(base_polinomica(esc(X), grado), etiqueta)
        sesgo = np.log(len(q1) / len(p1))
        f = lambda Y: m.eta(base_polinomica(esc(Y), grado)) - sesgo
    fq, fp = f(YQ[q2]), f(YP[p2])
    ef = np.exp(fp)
    e = float(fq.mean() - np.log(ef.mean()))
    se = float(np.sqrt(fq.var(ddof=1) / len(fq) + ef.var(ddof=1) / (len(ef) * ef.mean() ** 2)))
    return {"rastro": e, "error_tipico": se}


# ---------------------------------------------------------------------- espectro y regímenes
def matriz_transicion(micro: np.ndarray, k: int, lag: int = 1) -> np.ndarray:
    """micro: (T+1, n) microestados enteros en [0, k). Cuenta transiciones a retardo lag y normaliza por filas."""
    a = micro[:-lag].ravel()
    b = micro[lag:].ravel()
    C = np.zeros((k, k))
    np.add.at(C, (a, b), 1.0)
    C = C + C.T                    # estimador reversible simple (simetrización de cuentas)
    s = C.sum(axis=1, keepdims=True)
    return np.where(s > 0, C / np.where(s > 0, s, 1.0), 0.0)


def tiempos_implicitos(P: np.ndarray, lag: int = 1, k: int = 4):
    val, vec = np.linalg.eig(P)
    orden = np.argsort(-np.abs(val))
    val, vec = val[orden], vec[:, orden]
    with np.errstate(divide="ignore"):
        t = -lag / np.log(np.abs(val[1:k]))
    return t.real, val[:k].real, vec[:, :k].real


def dos_regimenes(P: np.ndarray):
    """Asigna cada microestado a uno de dos conjuntos metaestables por el signo del segundo vector propio."""
    _, _, vec = tiempos_implicitos(P, 1, 2)
    return (vec[:, 1] > 0).astype(int)
