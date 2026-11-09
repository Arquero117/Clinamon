"""M7 — Catálogo tipado de intervenciones (POD) en F0.

Un POD es un cambio de medida admisible (A6, §5.2): sustituye el núcleo K de un sorteo concreto
(fuente, elemento del dominio, paso) por otro K' absolutamente continuo respecto a K. El catálogo
es cerrado: solo se puede intervenir sobre sucesos que la ontología declara en sus fuentes, o
inclinar fuentes gaussianas declaradas como inclinables. No hay PODs mágicos.

Coste en nats, exacto por construcción:

* ``PODSuceso``: K' = K(·|A); coste −log K(A), calculado por partícula con el estado de esa
  partícula (la media sobre partículas es el coste del POD, §5.2).
* ``PODInclinacion``: desplaza una normal estándar en v; coste v²/2 (acción de Onsager-Machlup).
* ``PODNulo``: K' = K; coste 0. Sirve para el test obligatorio de efecto exactamente cero.

La consulta causal que responde una ejecución de gemelos en F0 es la **I** (prospectiva
interventiva, §4.1): ambos brazos parten del mismo estado en t0 con azar fresco.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PODNulo:
    tipo: str = "nulo"


@dataclass(frozen=True)
class PODSuceso:
    fuente: str
    evento: str
    indice: int
    paso: int
    tipo: str = "suceso"


@dataclass(frozen=True)
class PODInclinacion:
    fuente: str
    indice: int
    paso: int
    desplazamiento: float
    ranura: int = 0
    tipo: str = "inclinacion"


def pod_desde_dict(d: dict):
    d = dict(d)
    tipo = d.pop("tipo")
    if tipo == "nulo":
        return PODNulo()
    if tipo == "suceso":
        return PODSuceso(**d)
    if tipo == "inclinacion":
        return PODInclinacion(**d)
    raise ValueError(f"tipo de POD desconocido: {tipo}")


def pod_a_dict(pod) -> dict:
    return asdict(pod)


def catalogo(ontologia) -> list[dict]:
    """Lista de todas las plantillas de intervención admitidas por la ontología."""
    out = [{"tipo": "nulo"}]
    for f in ontologia.fuentes:
        for e in f.eventos:
            out.append({"tipo": "suceso", "fuente": f.nombre, "evento": e.nombre, "dominio": f.dominio,
                        "descripcion": e.descripcion})
        if f.inclinable:
            out.append({"tipo": "inclinacion", "fuente": f.nombre, "dominio": f.dominio,
                        "ranuras": f.ranuras})
    return out
