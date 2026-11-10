"""Campo de azar: sorteos indexados por (partícula, fuente, elemento del dominio, paso, flujo).

Disposición del contador Philox4x32 (128 bits) y de la clave (64 bits):

======  =====================================================================
c0      paso (uint32). El paso ``PASO_INICIAL`` se reserva al estado inicial.
c1      índice del elemento del dominio (entidad, arista o 0) * 64 + par de ranuras
c2      identificador global de partícula (no depende del bloque ni del proceso)
c3      (identificador de fuente << 8) | flujo
clave   semilla de 64 bits
======  =====================================================================

Flujos: ``COMUN`` (0) es el que usan el ensemble sin gemelos, el brazo base siempre y el brazo
con POD mientras la fuente siga compartida; ``PROPIO`` (1) es el del brazo con POD una vez
desacoplada la fuente; ``INTERVENCION`` (2) da los sorteos frescos del propio POD.

Horizonte de identidad (§4.3, A8). Una fuente se comparte entre los dos brazos mientras sea
físicamente insensible al POD. El reloj del tiempo de identidad τ_j arranca en el paso en que los
estados de los dos brazos dejan de ser idénticos (``t_div``), no en t0: un POD que no cambia nada
no desacopla nada, y por eso un POD nulo da efecto exactamente cero (§4.5). La fuente j pasa al
flujo propio en los pasos t ≥ t_div + max(1, ⌈τ_j⌉). La decisión de cambiar de flujo es medible
respecto al pasado, y ambos flujos dan sorteos frescos e independientes de él: la ley marginal de
cada brazo no cambia (ADR-0002).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..numerica import mat
from ..ontologia.esquema import Ontologia
from .philox import a_uniformes, philox4x32

COMUN = 0
PROPIO = 1
INTERVENCION = 2
PASO_INICIAL = 0xFFFFFFFF

ACOPLAMIENTOS = ("fisico", "maximo", "independiente")


class InadmisibleError(ValueError):
    """POD de coste infinito: el suceso tiene probabilidad cero en alguna partícula (A6)."""


class SorteoRepetidoError(RuntimeError):
    """Una fuente se ha sorteado dos veces en el mismo paso: los contadores colisionarían."""


@dataclass
class _PODActivo:
    tipo: str                 # 'suceso' o 'inclinacion'
    fuente: str
    paso: int
    indice: int
    evento: str | None = None
    ranura: int = 0
    desplazamiento: float = 0.0
    brazo: int = 1
    aplicado: bool = field(default=False)


class CampoAzar:
    """Campo de azar de un lote con A brazos: el brazo 0 es el base; el brazo j ≥ 1 lleva sus PODs.

    Columnas: [jN, (j+1)N) son las N partículas del brazo j. Flujos: 0 común; 2j−1 propio del brazo j una vez
    desacoplado; 2j sorteos frescos de sus intervenciones (con j = 1 coincide con F0: 1 y 2).
    """

    def __init__(self, ontologia: Ontologia, semilla: int, particulas: np.ndarray,
                 tamanos_dominio: dict[str, int], gemelos: bool = False,
                 acoplamiento: str = "fisico", pods: list | None = None,
                 motor_philox: str = "auto", ramas: list | None = None):
        if acoplamiento not in ACOPLAMIENTOS:
            raise ValueError(f"acoplamiento desconocido: {acoplamiento}")
        if not (0 <= semilla < 2 ** 64):
            raise ValueError("la semilla debe caber en 64 bits sin signo")
        if ramas is None:
            ramas = [list(pods or [])] if gemelos else []
            if pods and not gemelos:
                raise ValueError("un POD requiere ejecución con gemelos")
        elif pods:
            raise ValueError("usa ramas o pods, no ambos")
        self.A = 1 + len(ramas)
        if self.A > 127:
            raise ValueError("como mucho 126 brazos con POD")
        self.ont = ontologia
        self.fuentes = {f.nombre: f for f in ontologia.fuentes}
        self.ids = {f.nombre: i + 1 for i, f in enumerate(ontologia.fuentes)}
        if len(self.ids) >= 2 ** 24:
            raise ValueError("demasiadas fuentes")
        self.k0 = semilla & 0xFFFFFFFF
        self.k1 = (semilla >> 32) & 0xFFFFFFFF
        self.particulas = np.asarray(particulas, dtype=np.uint32)
        self.N = self.particulas.size
        self.gemelos = self.A > 1
        self.B = self.N * self.A
        self.c2 = np.tile(self.particulas, self.A)[None, :]
        self.tam = dict(tamanos_dominio)
        self.acoplamiento = acoplamiento
        self.motor_philox = motor_philox
        self.retardo = {}
        for nombre, f in self.fuentes.items():
            if acoplamiento == "maximo":
                self.retardo[nombre] = math.inf
            elif acoplamiento == "independiente":
                self.retardo[nombre] = 1
            else:
                self.retardo[nombre] = math.inf if math.isinf(f.tau) else max(1, math.ceil(f.tau))
        self.t_div_brazos = np.full((self.A, self.N), -1, dtype=np.int64)
        self.coste_brazos = np.zeros((self.A, self.N), dtype=np.float64)
        self.pods: list[_PODActivo] = []
        for j, rama in enumerate(ramas, start=1):
            for pod in rama:
                self._registrar_pod(pod, j)
        self.t = None
        self._sorteadas: set[str] = set()

    @property
    def t_div(self):
        return self.t_div_brazos[1] if self.A == 2 else self.t_div_brazos

    @property
    def coste(self):
        return self.coste_brazos[1] if self.A == 2 else self.coste_brazos

    def columnas(self, j: int) -> slice:
        return slice(j * self.N, (j + 1) * self.N)

    # ------------------------------------------------------------------ PODs
    def _registrar_pod(self, pod, brazo: int = 1):
        tipo = pod.tipo
        if tipo == "nulo":
            return
        f = self.fuentes.get(pod.fuente)
        if f is None:
            raise ValueError(f"POD sobre fuente no declarada {pod.fuente}: el catálogo es cerrado")
        if not (0 <= pod.indice < self.tam[f.dominio]):
            raise ValueError(f"POD: índice {pod.indice} fuera del dominio {f.dominio}")
        if tipo == "suceso":
            ev = {e.nombre: e for e in f.eventos}.get(pod.evento)
            if ev is None:
                raise ValueError(f"POD: la fuente {f.nombre} no declara el suceso {pod.evento}")
            self.pods.append(_PODActivo("suceso", f.nombre, pod.paso, pod.indice, evento=ev.nombre,
                                        ranura=ev.ranura, brazo=brazo))
        elif tipo == "inclinacion":
            if not f.inclinable:
                raise ValueError(f"POD: la fuente {f.nombre} no admite inclinación gaussiana")
            if not (0 <= pod.ranura < f.ranuras):
                raise ValueError("POD: ranura inexistente")
            if not math.isfinite(pod.desplazamiento):
                raise InadmisibleError("desplazamiento no finito")
            self.pods.append(_PODActivo("inclinacion", f.nombre, pod.paso, pod.indice,
                                        ranura=pod.ranura, desplazamiento=float(pod.desplazamiento), brazo=brazo))
        else:
            raise ValueError(f"tipo de POD desconocido {tipo}")

    # ------------------------------------------------------------------ pasos
    def comenzar_paso(self, t: int) -> None:
        self.t = int(t)
        self._sorteadas = set()

    def registrar_divergencia(self, difiere: np.ndarray) -> None:
        """Marca el paso actual como el de divergencia donde el brazo j difiere del base.

        ``difiere``: (N,) con dos brazos, o (A−1, N) en general.
        """
        d = np.asarray(difiere, dtype=bool).reshape(self.A - 1, self.N)
        td = self.t_div_brazos[1:]
        nuevo = (td < 0) & d
        td[nuevo] = self.t

    def _flujo(self, fuente: str) -> np.ndarray:
        """Flujo por columna (1, B) para la fuente en el paso actual."""
        if not self.gemelos or self.t == PASO_INICIAL:
            return np.zeros((1, self.B), dtype=np.uint32)
        d = self.retardo[fuente]
        if math.isinf(d):
            return np.zeros((1, self.B), dtype=np.uint32)
        td = self.t_div_brazos
        desacoplada = (td >= 0) & (self.t >= td + d)                     # (A, N)
        propio = (2 * np.arange(self.A, dtype=np.uint32) - 1)[:, None]    # 2j − 1
        flujo = np.where(desacoplada, propio, 0).astype(np.uint32).reshape(1, self.B)
        flujo[0, :self.N] = 0
        return flujo

    def _brutas(self, fuente: str, k: int, flujo, c2, indices=None):
        """k uniformes (cada una (D, columnas)) para la fuente en el paso actual."""
        f = self.fuentes[fuente]
        D = self.tam[f.dominio]
        idx = np.arange(D, dtype=np.uint32) if indices is None else np.asarray(indices, np.uint32)
        npares = (k + 1) // 2
        c0 = np.uint32(self.t)
        c1 = (idx[None, :, None] * np.uint32(64) + np.arange(npares, dtype=np.uint32)[:, None, None])
        c3 = (np.uint32(self.ids[fuente]) << np.uint32(8)) | np.asarray(flujo, np.uint32)
        w0, w1, w2, w3 = philox4x32(c0, c1, c2[None], c3[None], self.k0, self.k1, motor=self.motor_philox)
        par = a_uniformes(w0, w1)
        impar = a_uniformes(w2, w3)
        out = []
        for i in range(k):
            out.append(par[i // 2] if i % 2 == 0 else impar[i // 2])
        return out

    def _comprobar(self, fuente: str):
        if fuente not in self.fuentes:
            raise KeyError(f"fuente no declarada en la ontología: {fuente}")
        if self.t is None:
            raise RuntimeError("comenzar_paso no llamado")
        if fuente in self._sorteadas:
            raise SorteoRepetidoError(f"la fuente {fuente} ya se sorteó en el paso {self.t}")
        self._sorteadas.add(fuente)

    def uniformes(self, fuente: str, eventos: dict | None = None) -> list[np.ndarray]:
        """Uniformes en (0,1) para todas las ranuras de la fuente: lista de arrays (D, B).

        ``eventos`` debe contener exactamente los sucesos declarados por la fuente, cada uno como
        un intervalo semiabierto [lo, hi) en el espacio de la uniforme de su ranura (escalares o
        arrays difundibles a (D, B)). El mecanismo debe decidir el desenlace con esas mismas
        desigualdades: u < hi y u >= lo.
        """
        self._comprobar(fuente)
        f = self.fuentes[fuente]
        declarados = {e.nombre for e in f.eventos}
        dados = set(eventos or {})
        if dados != declarados:
            raise ValueError(f"fuente {fuente}: sucesos pasados {sorted(dados)} != declarados {sorted(declarados)}")
        u = self._brutas(fuente, f.ranuras, self._flujo(fuente), self.c2)
        for pod in self.pods:
            if pod.tipo == "suceso" and pod.fuente == fuente and pod.paso == self.t:
                lo, hi = eventos[pod.evento]
                self._forzar_suceso(pod, u, lo, hi)
        return u

    def normales(self, fuente: str, eventos: dict | None = None) -> list[np.ndarray]:
        """Normales estándar por cuantil inverso de las uniformes (los sucesos se dan en el espacio u)."""
        u = self.uniformes(fuente, eventos)
        z = [mat.ndtri(ui) for ui in u]
        for pod in self.pods:
            if pod.tipo == "inclinacion" and pod.fuente == fuente and pod.paso == self.t:
                fila = z[pod.ranura][pod.indice]
                cols = self.columnas(pod.brazo)
                fila[cols] = fila[cols] + pod.desplazamiento
                self.coste_brazos[pod.brazo] += 0.5 * pod.desplazamiento * pod.desplazamiento
                pod.aplicado = True
        return z

    def _forzar_suceso(self, pod: _PODActivo, u, lo, hi):
        """Acoplamiento máximo con la ley condicionada K(·|A): si el sorteo ya cae en A se conserva;
        si no, se sustituye por una uniforme fresca en A. Coste por partícula: −log K(A)."""
        D = self.tam[self.fuentes[pod.fuente].dominio]
        forma = (D, self.B)
        cols = self.columnas(pod.brazo)
        lo = np.broadcast_to(np.asarray(lo, np.float64), forma)[pod.indice, cols]
        hi = np.broadcast_to(np.asarray(hi, np.float64), forma)[pod.indice, cols]
        masa = hi - lo
        if not np.all(masa > 0.0):
            malas = np.flatnonzero(~(masa > 0.0))
            raise InadmisibleError(
                f"POD {pod.fuente}:{pod.evento} con probabilidad cero en partículas {self.particulas[malas][:10].tolist()}")
        v = self._brutas(pod.fuente, pod.ranura + 1, np.uint32(2 * pod.brazo),
                         self.particulas[None, :], indices=[pod.indice])[pod.ranura][0]
        fila = u[pod.ranura][pod.indice]
        actual = fila[cols]
        dentro = (actual >= lo) & (actual < hi)
        nuevo = lo + masa * v
        nuevo = np.minimum(nuevo, np.nextafter(hi, -np.inf))
        nuevo = np.maximum(nuevo, lo)
        fila[cols] = np.where(dentro, actual, nuevo)
        self.coste_brazos[pod.brazo] += -mat.log(masa)
        pod.aplicado = True


# ---------------------------------------------------------------------- transformaciones
def pareto_truncada(u, xm, alfa, xmax):
    """Pareto de escala xm e índice alfa por cuantil inverso, truncada en xmax (cota física)."""
    return np.minimum(xm * mat.exp(-mat.log(u) / alfa), xmax)


def gumbel(u):
    return -mat.log(-mat.log(u))
