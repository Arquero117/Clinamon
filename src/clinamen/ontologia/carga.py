"""Carga de ontologías desde YAML."""
from __future__ import annotations

from pathlib import Path

import yaml

from .esquema import Ontologia


def _lista_con_nombre(d):
    """Permite escribir en YAML ``variables: {poblacion: {...}}`` en lugar de una lista."""
    if isinstance(d, dict):
        return [dict(v, nombre=k) for k, v in d.items()]
    return d


def cargar_ontologia(ruta: str | Path) -> Ontologia:
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    # claves 'x-...' solo sirven de anclas YAML reutilizables
    datos = {k: v for k, v in datos.items() if not str(k).startswith("x-")}
    for clave in ("variables", "parametros", "fuentes", "identidades", "observables", "mecanismos", "observaciones"):
        if clave in datos:
            datos[clave] = _lista_con_nombre(datos[clave])
    if isinstance(datos.get("estado_inicial"), dict) and "nombre" not in datos["estado_inicial"]:
        datos["estado_inicial"]["nombre"] = "estado_inicial"
    return Ontologia.model_validate(datos)
