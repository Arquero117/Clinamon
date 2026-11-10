"""M6 — Asimilación: posterior del estado y de los parámetros dada una historia observada (§11.1, §11.2).

* Filtro de partículas bootstrap sobre el motor: las columnas del lote son M valores de θ × K partículas de
  estado. Cada bloque de K columnas es un filtro independiente para su θ; se remuestrea dentro del bloque en
  los pasos con observación y se acumula la log-verosimilitud marginal ``log p̂(y | θ)``, insesgada en escala
  natural (Del Moral).
* Muestreo por importancia adaptativo sobre θ en varias etapas, con pesos prior × p̂(y|θ) / propuesta:
  pseudo-marginal, de modo que la posterior es exacta en el límite de muchas muestras de θ, sea cual sea K.
* Muestras conjuntas (θ, x_t) de la posterior de filtrado: θ por su peso y una partícula de su filtro.

La verosimilitud es la del modelo de observación declarado en la ontología (§3.1): error explícito y huecos.
El remuestreo usa un generador NumPy con semilla: el resultado es determinista dada la semilla.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp

from ..motor.motor import ConfigSimulacion, Modelo, Simulacion

LOG_2PI = np.log(2.0 * np.pi)


# ------------------------------------------------------------------------- observaciones
def observar(modelo: Modelo, x: dict, p_valores: dict, rng: np.random.Generator) -> dict:
    """Una observación sintética de cada definición: (n_entidades, B) con error y huecos (NaN)."""
    out = {}
    for ob in modelo.ontologia.observaciones:
        v = x[ob.variable][list(ob.entidades)]
        if ob.familia == "suceso":
            y = v.astype(np.float64).copy()
            y[rng.random(v.shape) < ob.fraccion_huecos] = np.nan
            out[ob.nombre] = y
            continue
        sd = p_valores[ob.sd]
        if ob.familia == "lognormal":
            y = v * np.exp(sd * rng.standard_normal(v.shape))
        else:
            y = v + sd * rng.standard_normal(v.shape)
        y[rng.random(v.shape) < ob.fraccion_huecos] = np.nan
        out[ob.nombre] = y
    return out


def log_verosimilitud(modelo: Modelo, x: dict, y: dict, p_valores: dict) -> np.ndarray:
    """log p(y_t | x_t) por columna (B,). Los huecos (NaN) no aportan."""
    B = next(iter(x.values())).shape[1]
    ll = np.zeros(B)
    for ob in modelo.ontologia.observaciones:
        yo = y.get(ob.nombre)
        if yo is None or ob.familia == "suceso":      # los sucesos entran por condicionamiento
            continue
        sd = p_valores[ob.sd]
        v = x[ob.variable][list(ob.entidades)]
        for i in range(yo.shape[0]):
            yi = yo[i]
            if not np.isfinite(yi):
                continue
            if ob.familia == "lognormal":
                r = (np.log(yi) - np.log(np.maximum(v[i], 1e-300))) / sd
                ll += -0.5 * r * r - np.log(sd) - 0.5 * LOG_2PI - np.log(yi)
            else:
                r = (yi - v[i]) / sd
                ll += -0.5 * r * r - np.log(sd) - 0.5 * LOG_2PI
    return ll


def hay_dato(y: dict) -> bool:
    return any(np.isfinite(v).any() for v in y.values())


def condiciones_de(modelo: Modelo, y: dict, B: int) -> list:
    """Sucesos registrados en y (observaciones de familia 'suceso') como condiciones del campo de azar."""
    out = []
    todas = np.ones(B, dtype=bool)
    for ob in modelo.ontologia.observaciones:
        if ob.familia != "suceso" or ob.nombre not in y:
            continue
        for i, e in enumerate(ob.entidades):
            v = y[ob.nombre][i]
            if np.isfinite(v):
                out.append((ob.fuente, ob.evento_si if v > 0.5 else ob.evento_no, int(e), todas))
    return out


# ------------------------------------------------------------------------- filtro
@dataclass
class ResultadoFiltro:
    log_verosimilitud: np.ndarray      # (M,)
    estado: dict                       # variables no flujo, arrays (E, M*K) tras el último paso
    M: int
    K: int


def _remuestreo_sistematico(logw: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """logw: (M, K). Devuelve índices globales de columna (M*K,) remuestreados dentro de cada bloque."""
    M, K = logw.shape
    w = np.exp(logw - logw.max(axis=1, keepdims=True))
    c = np.cumsum(w, axis=1)
    c /= c[:, -1:]
    u = (rng.random((M, 1)) + np.arange(K)[None, :]) / K
    fila = np.arange(M)[:, None]
    pos = np.searchsorted((c + fila).ravel(), (u + fila).ravel(), side="left")
    return np.minimum(pos, M * K - 1)


def filtro_particulas(modelo: Modelo, theta: dict, K: int, datos: list, semilla: int,
                      verificar: bool = False) -> ResultadoFiltro:
    """datos: lista de longitud T con dicts {observación: (n_ent,) con NaN en los huecos} tras cada paso 0..T−1.

    theta: {parámetro: array (M,)}. Todas las partículas parten del prior del estado inicial del modelo.
    """
    M = len(next(iter(theta.values())))
    cols = {k: np.repeat(np.asarray(v, np.float64), K)[None, :] for k, v in theta.items()}
    sim = Simulacion(modelo, ConfigSimulacion(particulas=M * K, anios=0, semilla=semilla, parametros=cols,
                                              verificar=verificar))
    rng = np.random.default_rng([semilla, 7])
    logZ = np.zeros(M)
    for y in datos:
        sim.campo.log_peso_condiciones[:] = 0.0
        sim.campo.condicionar(condiciones_de(modelo, y, M * K))
        sim.paso()
        sim.campo.condicionar([])
        if not hay_dato(y):
            continue
        yc = {k: v[:, None] for k, v in y.items()}
        ll = log_verosimilitud(modelo, sim.x, yc, sim.p.como_dict()) + sim.campo.log_peso_condiciones
        ll = ll.reshape(M, K)
        logZ += logsumexp(ll, axis=1) - np.log(K)
        sim.reindexar(_remuestreo_sistematico(ll, rng))
    estado = {v.nombre: sim.x[v.nombre].copy() for v in modelo.ontologia.variables if v.tipo != "flujo"}
    return ResultadoFiltro(logZ, estado, M, K)


# ------------------------------------------------------------------------- posterior de θ
@dataclass
class Prior:
    """Prior uniforme independiente en una caja (el de los parámetros inferidos en F1)."""
    nombres: list
    lo: np.ndarray
    hi: np.ndarray

    @classmethod
    def desde_ontologia(cls, modelo: Modelo, nombres: list):
        P = {p.nombre: p for p in modelo.ontologia.parametros}
        for n in nombres:
            if P[n].prior.familia != "uniforme":
                raise ValueError(f"{n}: solo priors uniformes en F1")
        return cls(list(nombres), np.array([P[n].prior.rango[0] for n in nombres]),
                   np.array([P[n].prior.rango[1] for n in nombres]))

    def log_densidad(self, Th):
        dentro = np.all((Th >= self.lo) & (Th <= self.hi), axis=1)
        return np.where(dentro, -np.sum(np.log(self.hi - self.lo)), -np.inf)

    def muestrear(self, n, rng):
        return self.lo + (self.hi - self.lo) * rng.random((n, len(self.nombres)))


def _t_logpdf(X, mu, L, df):
    d = X.shape[1]
    z = np.linalg.solve(L, (X - mu).T)
    q = np.sum(z * z, axis=0)
    from scipy.special import gammaln
    return (gammaln((df + d) / 2) - gammaln(df / 2) - 0.5 * d * np.log(df * np.pi)
            - np.sum(np.log(np.diag(L))) - 0.5 * (df + d) * np.log1p(q / df))


@dataclass
class Posterior:
    theta: np.ndarray        # (n, d) todas las muestras de θ de todas las etapas
    logw: np.ndarray         # (n,) log pesos de importancia normalizables
    filtros: list            # ResultadoFiltro por etapa
    etapa_de: np.ndarray     # (n,) etapa de cada muestra
    indice_en_etapa: np.ndarray
    ess: float
    nombres: list

    def pesos(self):
        w = np.exp(self.logw - self.logw.max())
        return w / w.sum()

    def muestras_conjuntas(self, S: int, rng: np.random.Generator):
        """S pares (θ, x) de la posterior de filtrado: θ por su peso, x una partícula de su filtro."""
        i = rng.choice(self.theta.shape[0], size=S, p=self.pesos())
        th = self.theta[i]
        estados = {}
        for s, j in enumerate(i):
            f = self.filtros[self.etapa_de[j]]
            col = self.indice_en_etapa[j] * f.K + rng.integers(f.K)
            for k, v in f.estado.items():
                estados.setdefault(k, []).append(v[:, col])
        return th, {k: np.stack(v, axis=1) for k, v in estados.items()}


def posterior_adaptativa(modelo: Modelo, prior: Prior, datos: list, semilla: int, M: int = 256, K: int = 128,
                         etapas: int = 3, df: float = 5.0, defensa: float = 0.1) -> Posterior:
    """Muestreo por importancia adaptativo pseudo-marginal sobre θ.

    Etapa 1: prior. Etapas siguientes: mezcla (1 − defensa) · t de Student ajustada a la posterior ponderada
    acumulada (covarianza inflada ×2) + defensa · prior. Cada muestra lleva el peso prior·p̂(y|θ)/propuesta
    de su propia etapa; las etapas se agregan.
    """
    rng = np.random.default_rng([semilla, 11])
    d = len(prior.nombres)
    TH, LW, filtros, etapa_de, idx = [], [], [], [], []
    mu = cov = None
    for e in range(etapas):
        if e == 0:
            th = prior.muestrear(M, rng)
            logq = prior.log_densidad(th)
        else:
            L = np.linalg.cholesky(cov)
            n_t = rng.binomial(M, 1 - defensa)
            z = rng.standard_normal((n_t, d)) / np.sqrt(rng.chisquare(df, (n_t, 1)) / df)
            th = np.concatenate([mu + z @ L.T, prior.muestrear(M - n_t, rng)])
            lp = prior.log_densidad(th)
            logq = np.logaddexp(np.log(1 - defensa) + _t_logpdf(th, mu, L, df), np.log(defensa) + lp)
        ok = np.isfinite(prior.log_densidad(th))
        th = np.where(ok[:, None], th, prior.lo)          # fuera del prior: peso −inf; se simula igualmente
        f = filtro_particulas(modelo, {n: th[:, j] for j, n in enumerate(prior.nombres)}, K, datos,
                              semilla=semilla * 1000 + e)
        lw = np.where(ok, f.log_verosimilitud + prior.log_densidad(th) - logq, -np.inf)
        TH.append(th); LW.append(lw); filtros.append(f)
        etapa_de.append(np.full(M, e)); idx.append(np.arange(M))
        T_all, W_all = np.concatenate(TH), np.concatenate(LW)
        w = np.exp(W_all - W_all.max()); w /= w.sum()
        mu = w @ T_all
        C = (T_all - mu).T @ ((T_all - mu) * w[:, None])
        piso = np.diag(((prior.hi - prior.lo) / 50.0) ** 2)
        cov = 2.0 * C + piso
    LW = np.concatenate(LW)
    w = np.exp(LW - LW.max()); w /= w.sum()
    return Posterior(np.concatenate(TH), LW, filtros, np.concatenate(etapa_de), np.concatenate(idx),
                     float(1.0 / np.sum(w * w)), list(prior.nombres))
