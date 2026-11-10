"""Ensamblado del mundo sintético F1."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ...motor.motor import Mecanismo, Modelo
from ...ontologia.carga import cargar_ontologia
from . import mecanismos as mec

RUTA_ONTOLOGIA = Path(__file__).with_name("ontologia.yaml")


@lru_cache(maxsize=1)
def ontologia():
    return cargar_ontologia(RUTA_ONTOLOGIA)


def construir_modelo() -> Modelo:
    ont = ontologia()
    funciones = {f.__name__: f for f in mec.MECANISMOS}
    mecanismos = []
    for ficha in ont.mecanismos:
        if ficha.nombre not in funciones:
            raise ValueError(f"ficha sin implementación: {ficha.nombre}")
        mecanismos.append(Mecanismo(ficha, funciones[ficha.nombre]))
    sobran = set(funciones) - {f.nombre for f in ont.mecanismos}
    if sobran:
        raise ValueError(f"implementaciones sin ficha (no compilan): {sorted(sobran)}")
    return Modelo(ontologia=ont, mecanismos=mecanismos, inicial=mec.estado_inicial)
