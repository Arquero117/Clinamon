"""Cadenas de Markov finitas con respuesta exacta (banco canónico, §13.2).

Una cadena finita, posiblemente no homogénea en el tiempo, con núcleos K_t (matrices estocásticas por filas),
horizonte T, distribución inicial p0 y desenlace B ⊂ estados en T. Todo lo que el manual define sobre el
generador tiene aquí una expresión exacta por álgebra lineal:

* committor de tiempo finito h_t = K_t h_{t+1}, h_T = 1_B (§6.1);
* presupuesto de contingencia ρ_t = E[(h_{t+1}(X_{t+1}) − h_t(X_t))²] (Teorema 2, §6.2);
* perfil de la ruta más barata κ_t = E_{Q*}[KL(K^h_t ‖ K_t)] con la transformada h de Doob (Teorema 3, §6.4);
* coste, rastro y eficiencia de un POD-suceso (Teorema 1, §5.3);
* espectro del operador de transferencia (§8.1).

Estos valores son la verdad contra la que se validan los estimadores de M8, que solo ven trayectorias simuladas
de la MISMA cadena.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from ..azar.philox import a_uniformes, philox4x32


def _csr(K) -> sp.csr_matrix:
    K = sp.csr_matrix(K, dtype=np.float64)
    K.eliminate_zeros()
    K.sort_indices()
    s = np.asarray(K.sum(axis=1)).ravel()
    if not np.allclose(s, 1.0, atol=1e-12):
        raise ValueError("núcleo no estocástico por filas")
    return K


def _xlogx(a):
    a = np.asarray(a, dtype=np.float64)
    return np.where(a > 0, a * np.log(np.where(a > 0, a, 1.0)), 0.0)


def kl_discreta(q, p) -> float:
    """KL(q ‖ p) en nats para distribuciones discretas; inf si q no es absolutamente continua respecto a p."""
    q = np.asarray(q, np.float64)
    p = np.asarray(p, np.float64)
    m = q > 0
    if np.any(p[m] <= 0):
        return float("inf")
    return float(np.sum(q[m] * (np.log(q[m]) - np.log(p[m]))))


@dataclass
class ResultadoPOD:
    coste: float              # E_{p_t0}[−log K_t0(x, A)]
    rastro: float             # KL(Q_Y ‖ P_Y)
    eficiencia: float         # rastro / coste
    ley_P: np.ndarray
    ley_Q: np.ndarray


@dataclass
class CadenaFinita:
    nucleos: list                      # longitud 1 (homogénea) o T
    T: int
    p0: np.ndarray
    B: np.ndarray                      # máscara booleana sobre estados en T
    rasgos: np.ndarray                 # (n, d) coordenadas de cada estado (lo único que ven los estimadores)
    nombre: str = ""
    etiquetas: np.ndarray | None = None  # observable Y = etiqueta del estado (por defecto, el estado)
    _acum: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.nucleos = [_csr(K) for K in self.nucleos]
        self.n = self.nucleos[0].shape[0]
        self.p0 = np.asarray(self.p0, np.float64)
        self.B = np.asarray(self.B, bool)
        if self.rasgos.ndim == 1:
            self.rasgos = self.rasgos[:, None]
        if len(self.nucleos) not in (1, self.T):
            raise ValueError("hace falta un núcleo o uno por paso")

    def K(self, t: int) -> sp.csr_matrix:
        return self.nucleos[0] if len(self.nucleos) == 1 else self.nucleos[t]

    # ------------------------------------------------------------------ exacto
    def committor(self) -> np.ndarray:
        h = np.empty((self.T + 1, self.n))
        h[self.T] = self.B
        for t in range(self.T - 1, -1, -1):
            h[t] = self.K(t) @ h[t + 1]
        return h

    def marginales(self, p0=None) -> np.ndarray:
        p = np.empty((self.T + 1, self.n))
        p[0] = self.p0 if p0 is None else p0
        for t in range(self.T):
            p[t + 1] = self.K(t).T @ p[t]
        return p

    def probabilidad_B(self) -> float:
        return float(self.p0 @ self.committor()[0])

    def presupuesto(self):
        """ρ_t exacto y la incertidumbre inicial E[M0(1 − M0)] (Teorema 2: Σρ_t = E[M0(1−M0)])."""
        h = self.committor()
        p = self.marginales()
        rho = np.array([p[t] @ (self.K(t) @ (h[t + 1] ** 2) - h[t] ** 2) for t in range(self.T)])
        return rho, float(p[0] @ (h[0] * (1.0 - h[0])))

    def kappa(self):
        """κ_t exacto (Teorema 3) y κ_inicial = KL(q0 ‖ p0). Σ = −log P(B)."""
        h = self.committor()
        p = self.marginales()
        PB = float(p[0] @ h[0])
        k = np.empty(self.T)
        for t in range(self.T):
            q = p[t] * h[t] / PB
            m = h[t] > 0
            hlog = self.K(t) @ _xlogx(h[t + 1])      # Σ_y K(x,y) h(y) log h(y)
            val = np.zeros(self.n)
            val[m] = hlog[m] / h[t][m] - np.log(h[t][m])
            k[t] = q @ val
        q0 = p[0] * h[0] / PB
        return k, kl_discreta(q0, p[0])

    def pod_suceso(self, t0: int, A: np.ndarray, etiquetas=None, p_inicial=None) -> ResultadoPOD:
        """POD que sustituye K_t0(x, ·) por K_t0(x, · | A) en todos los estados (A: máscara de estados de llegada)."""
        A = np.asarray(A, bool)
        p = self.marginales(p_inicial)
        Kt = self.K(t0)
        masa = Kt @ A.astype(np.float64)
        vivos = p[t0] > 0
        if np.any(masa[vivos] <= 0):
            raise ValueError("POD inadmisible: K(x, A) = 0 en un estado alcanzable")
        coste = float(p[t0][vivos] @ -np.log(masa[vivos]))
        Kc = sp.diags(np.where(masa > 0, 1.0 / np.where(masa > 0, masa, 1.0), 0.0)) @ Kt @ sp.diags(A.astype(float))
        q = Kc.T @ p[t0]
        for t in range(t0 + 1, self.T):
            q = self.K(t).T @ q
        et = self.etiquetas if etiquetas is None else etiquetas
        PY, QY = p[self.T], q
        if et is not None:
            k = int(et.max()) + 1
            PY = np.bincount(et, weights=PY, minlength=k)
            QY = np.bincount(et, weights=QY, minlength=k)
        e = kl_discreta(QY, PY)
        return ResultadoPOD(coste, e, e / coste, PY, QY)

    def espectro(self, k: int = 5, lag: int = 1):
        """Autovalores dominantes del núcleo homogéneo elevado a lag y tiempos implícitos −lag/log|λ|."""
        if len(self.nucleos) != 1:
            raise ValueError("espectro definido para núcleos homogéneos")
        M = self.nucleos[0].toarray()
        Ml = np.linalg.matrix_power(M, lag)
        val = np.linalg.eigvals(Ml)
        val = val[np.argsort(-np.abs(val))][:k]
        with np.errstate(divide="ignore"):
            tiempos = -lag / np.log(np.abs(val[1:]))
        return val, tiempos

    # ------------------------------------------------------------------ simulación
    def _tabla(self, t):
        clave = 0 if len(self.nucleos) == 1 else t
        if clave not in self._acum:
            K = self.K(t)
            filas = np.repeat(np.arange(self.n), np.diff(K.indptr))
            acum = np.empty_like(K.data)
            for i in range(self.n):  # suma acumulada por fila; último valor exactamente 1
                a, b = K.indptr[i], K.indptr[i + 1]
                c = np.cumsum(K.data[a:b])
                c /= c[-1]
                acum[a:b] = c
            self._acum[clave] = (filas + acum, K.indices)
        return self._acum[clave]

    def paso(self, t: int, estados: np.ndarray, u: np.ndarray) -> np.ndarray:
        clave, cols = self._tabla(t)
        pos = np.searchsorted(clave, estados + u, side="left")
        return cols[np.minimum(pos, cols.size - 1)]

    def uniformes(self, semilla: int, t: int, ids: np.ndarray, flujo: int = 0) -> np.ndarray:
        w = philox4x32(np.uint32(t), np.uint32(0), ids.astype(np.uint32), np.uint32(flujo),
                       semilla & 0xFFFFFFFF, (semilla >> 32) & 0xFFFFFFFF)
        return a_uniformes(w[0], w[1])

    def simular(self, n: int, semilla: int, x0: np.ndarray | None = None, desde: int = 0,
                id0: int = 0, flujo: int = 0) -> np.ndarray:
        """Trayectorias (T+1−desde, n) de índices de estado. x0: estados iniciales o None (se sortean de p0)."""
        ids = np.arange(id0, id0 + n, dtype=np.int64)
        if x0 is None:
            c = np.cumsum(self.p0)
            c /= c[-1]
            x = np.searchsorted(c, self.uniformes(semilla, 0xFFFFFFFF, ids, flujo), side="left")
        else:
            x = np.broadcast_to(np.asarray(x0, np.int64), (n,)).copy()
        out = np.empty((self.T + 1 - desde, n), dtype=np.int64)
        out[0] = x
        for i, t in enumerate(range(desde, self.T)):
            x = self.paso(t, x, self.uniformes(semilla, t, ids, flujo))
            out[i + 1] = x
        return out

    def simular_gemelos(self, n: int, semilla: int, t0: int, A: np.ndarray, x0=None):
        """Brazo base y brazo con POD-suceso en t0 (acoplamiento máximo en t0; azar independiente después).

        Devuelve (base, pod, coste_por_trayectoria) con trayectorias completas (T+1, n).
        """
        A = np.asarray(A, bool)
        base = self.simular(n, semilla, x0)
        pod = base.copy()
        ids = np.arange(n, dtype=np.int64)
        xt = base[t0]
        masa = self.K(t0) @ A.astype(np.float64)
        m = masa[xt]
        if np.any(m <= 0):
            raise ValueError("POD inadmisible en alguna trayectoria")
        siguiente = base[t0 + 1]
        dentro = A[siguiente]
        # K(x, · | A) por cuantil inverso con un flujo fresco (acoplamiento máximo: se conserva si ya cae en A)
        Kt = self.K(t0)
        inv = np.where(masa > 0, 1.0 / np.where(masa > 0, masa, 1.0), 0.0)
        Kc = (sp.diags(inv) @ Kt @ sp.diags(A.astype(np.float64))).tocsr()
        Kc = Kc + sp.diags((masa <= 0).astype(np.float64))      # filas inalcanzables: identidad
        aux = CadenaFinita([Kc], 1, self.p0, self.B, self.rasgos)
        cand = aux.paso(0, xt, self.uniformes(semilla, t0, ids, flujo=2))
        nuevo = np.where(dentro, siguiente, cand)
        pod[t0 + 1] = nuevo
        for t in range(t0 + 1, self.T):
            pod[t + 1] = self.paso(t, pod[t], self.uniformes(semilla, t, ids, flujo=1))
        return base, pod, -np.log(m)
