"""M5 — Motor: simulación vectorizada sobre el eje del ensemble.

Disposición de estructura de arrays (SoA): cada variable de entidad es un array (E, B) y cada
variable global uno (1, B), con B el eje del ensemble. Con gemelos, las columnas [0, N) son el
brazo base y [N, 2N) el brazo con POD de las mismas partículas.

El motor es determinista dada la semilla: la única fuente de azar es el campo Philox por contador.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..azar.campo import PASO_INICIAL, CampoAzar
from ..numerica import mat
from ..ontologia.esquema import FichaMecanismo, Ontologia
from .topologia import Rejilla
from .verificacion import Fallo, stocks_vigilados, verificar_paso

TOLERANCIA_F64 = 1.0e-10   # congelada en prerregistro/F0_puerta.yaml


class IdentidadVioladaError(RuntimeError):
    pass


class Parametros:
    """Parámetros con acceso por atributo; un nombre no declarado es un error."""

    def __init__(self, valores: dict[str, float]):
        object.__setattr__(self, "_v", dict(valores))

    def __getattr__(self, nombre):
        try:
            return self._v[nombre]
        except KeyError:
            raise AttributeError(f"parámetro no declarado: {nombre}") from None

    def __setattr__(self, k, v):
        raise AttributeError("los parámetros son de solo lectura")

    def como_dict(self):
        return dict(self._v)


@dataclass
class Contexto:
    x: dict
    p: Parametros
    azar: CampoAzar
    topo: Rejilla
    t: int
    E: int
    B: int


@dataclass
class Mecanismo:
    ficha: FichaMecanismo
    paso: Callable[[Contexto], None]


@dataclass
class Modelo:
    ontologia: Ontologia
    mecanismos: list[Mecanismo]
    inicial: Callable[[Contexto], None]
    anio0: int = 0

    def __post_init__(self):
        nombres = [m.ficha.nombre for m in self.mecanismos]
        esperados = [f.nombre for f in self.ontologia.mecanismos]
        if nombres != esperados:
            raise ValueError(f"mecanismos implementados {nombres} != fichas {esperados}")
        self.topo = Rejilla(self.ontologia.topologia)
        self.E = self.topo.E
        self.tamanos = {"entidad": self.E, "arista": self.topo.A, "global": 1}
        self.flujos = [v.nombre for v in self.ontologia.variables if v.tipo == "flujo"]
        self.vigilados = stocks_vigilados(self.ontologia)
        self.parametros_nominales = {p.nombre: p.valor for p in self.ontologia.parametros}

    def forma(self, nombre: str, B: int):
        v = self.ontologia.variable(nombre)
        return (self.E, B) if v.ambito == "entidad" else (1, B)


@dataclass
class ConfigSimulacion:
    particulas: int
    anios: int
    semilla: int
    particula0: int = 0
    gemelos: bool = False
    pods: tuple = ()
    acoplamiento: str = "fisico"
    verificar: bool = True
    al_fallar: str = "error"          # 'error' o 'registrar'
    anios_ancla: tuple = ()
    registrar_estados: bool = False   # solo para pruebas: guarda el estado completo en cada paso
    motor_philox: str = "auto"
    parametros: dict | None = None    # sustituciones de parámetros (escalares o arrays (1, B))
    al_paso: Callable | None = None   # función (t, x) llamada al final de cada paso (diagnóstico)


@dataclass
class Resultado:
    observables: dict[str, np.ndarray]          # nombre -> (T, B)
    anclas: dict[int, dict[str, np.ndarray]]    # paso -> estado completo
    coste: np.ndarray                           # (N,) nats por partícula del brazo con POD
    t_div: np.ndarray                           # (N,) paso de divergencia o -1
    fallos: list[Fallo]
    pasos_verificados: int
    segundos: float
    estados: list | None = None
    particulas: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    gemelos: bool = False

    @property
    def N(self):
        return self.particulas.size


def calcular_observables(modelo: Modelo, x: dict) -> dict[str, np.ndarray]:
    out = {}
    for o in modelo.ontologia.observables:
        v = x[o.variable]
        if o.reduccion == "suma":
            r = mat.suma_filas(v)
        elif o.reduccion == "media":
            r = mat.media_filas(v)
        elif o.reduccion == "max":
            r = mat.max_filas(v)
        elif o.reduccion == "herfindahl":
            tot = mat.suma_filas(v)
            s = v / np.where(tot > 0, tot, 1.0)
            r = mat.suma_filas(s * s)
        else:
            r = v
        out[o.nombre] = r[0]
    return out


def _divergencia(x: dict, N: int) -> np.ndarray:
    d = np.zeros(N, dtype=bool)
    for a in x.values():
        d |= np.any(a[:, N:] != a[:, :N], axis=0)
    return d


def simular(modelo: Modelo, cfg: ConfigSimulacion) -> Resultado:
    mat.verificar_determinismo_posicional()
    if cfg.pods and not cfg.gemelos:
        raise ValueError("los PODs solo se aplican con gemelos")
    N = cfg.particulas
    particulas = np.arange(cfg.particula0, cfg.particula0 + N, dtype=np.int64)
    campo = CampoAzar(modelo.ontologia, cfg.semilla, particulas, modelo.tamanos,
                      gemelos=cfg.gemelos, acoplamiento=cfg.acoplamiento, pods=list(cfg.pods),
                      motor_philox=cfg.motor_philox)
    B = campo.B
    valores = dict(modelo.parametros_nominales)
    if cfg.parametros:
        for k, v in cfg.parametros.items():
            if k not in valores:
                raise KeyError(f"parámetro no declarado: {k}")
            valores[k] = v
    p = Parametros(valores)
    x: dict[str, np.ndarray] = {}
    ctx = Contexto(x=x, p=p, azar=campo, topo=modelo.topo, t=PASO_INICIAL, E=modelo.E, B=B)
    campo.comenzar_paso(PASO_INICIAL)
    modelo.inicial(ctx)
    for f in modelo.flujos:
        x[f] = np.zeros(modelo.forma(f, B))
    faltan = {v.nombre for v in modelo.ontologia.variables} - set(x)
    if faltan:
        raise RuntimeError(f"el estado inicial no define {sorted(faltan)}")

    fallos: list[Fallo] = []
    if cfg.verificar:
        fallos += verificar_paso(modelo.ontologia, -1, None, x, TOLERANCIA_F64)
    T = cfg.anios
    obs = {o.nombre: np.empty((T, B)) for o in modelo.ontologia.observables}
    anclas = {}
    estados = [] if cfg.registrar_estados else None
    pasos_verificados = 0
    t_ini = time.perf_counter()
    for t in range(T):
        ctx.t = t
        campo.comenzar_paso(t)
        previo = {s: x[s].copy() for s in modelo.vigilados}
        for f in modelo.flujos:
            x[f] = np.zeros(modelo.forma(f, B))
        for m in modelo.mecanismos:
            m.paso(ctx)
        if cfg.verificar:
            nuevos = verificar_paso(modelo.ontologia, t, previo, x, TOLERANCIA_F64)
            pasos_verificados += 1
            if nuevos:
                fallos += nuevos
                if cfg.al_fallar == "error":
                    raise IdentidadVioladaError("\n".join(str(f) for f in nuevos[:10]))
        if cfg.gemelos:
            campo.registrar_divergencia(_divergencia(x, N))
        for k, v in calcular_observables(modelo, x).items():
            obs[k][t] = v
        if t in cfg.anios_ancla:
            anclas[t] = {k: v.copy() for k, v in x.items()}
        if cfg.al_paso is not None:
            cfg.al_paso(t, x)
        if estados is not None:
            estados.append({k: v.copy() for k, v in x.items()})
    segundos = time.perf_counter() - t_ini
    for pod in campo.pods:
        if pod.paso < T and not pod.aplicado:
            raise RuntimeError(f"el POD sobre {pod.fuente} en el paso {pod.paso} no llegó a aplicarse")
    return Resultado(observables=obs, anclas=anclas, coste=campo.coste.copy(), t_div=campo.t_div.copy(),
                     fallos=fallos, pasos_verificados=pasos_verificados, segundos=segundos,
                     estados=estados, particulas=particulas, gemelos=cfg.gemelos)
