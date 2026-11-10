"""Registro de mundos disponibles."""
from __future__ import annotations

import importlib

MUNDOS = {
    "banco_f0": "clinamen.mundos.banco_f0.modelo:construir_modelo",
    "sintetico_f1": "clinamen.mundos.sintetico_f1.modelo:construir_modelo",
}


def obtener_modelo(nombre: str):
    if nombre not in MUNDOS:
        raise KeyError(f"mundo desconocido {nombre}; disponibles: {sorted(MUNDOS)}")
    modulo, funcion = MUNDOS[nombre].split(":")
    return getattr(importlib.import_module(modulo), funcion)()
