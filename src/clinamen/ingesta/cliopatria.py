"""M2 — Ingesta de Cliopatria v0.2.1 (fronteras de polities): panel de territorio independiente de Seshat.

Para cada una de las 35 NGA de Seshat (sus coordenadas) y cada siglo de −3400 a 1900: Terr = log10 del área
(km²) de la polity de Cliopatria vigente ese año (FromYear ≤ año ≤ ToYear) cuyo polígono contiene el punto; si
hay varias (vasallos dentro de imperios), la de mayor área; si ninguna, el siglo queda como hueco.
Diseño congelado en prerregistro/F2a_cliopatria.yaml.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .seshat import _libro, cargar_panel

RAIZ = Path(__file__).resolve().parents[3]
DIR = RAIZ / "datos" / "brutos" / "cliopatria"
GEOJSON_ZIP = DIR / "cliopatria.geojson.zip"
SHA256 = "e10a4e429fca708788ff9e7572a95fce801fae55852d217cffabc1c59cd4eed4"
URL = "https://zenodo.org/api/records/23128623/files/Seshat-Global-History-Databank/cliopatria-v0.2.1.zip/content"
SALIDA = RAIZ / "datos" / "procesados" / "cliopatria_panel.parquet"
ANIOS = range(-3400, 1901, 100)


def descargar() -> Path:
    """Descarga el paquete de Zenodo y extrae solo cliopatria.geojson.zip, verificando su sha256."""
    if not GEOJSON_ZIP.exists():
        DIR.mkdir(parents=True, exist_ok=True)
        datos = urllib.request.urlopen(URL, timeout=900).read()
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            nombre = next(n for n in z.namelist() if n.endswith("cliopatria.geojson.zip"))
            GEOJSON_ZIP.write_bytes(z.read(nombre))
    if hashlib.sha256(GEOJSON_ZIP.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("cliopatria.geojson.zip no coincide con el registrado (procedencia rota)")
    return GEOJSON_ZIP


def construir_panel() -> pd.DataFrame:
    from shapely import STRtree, points
    from shapely.geometry import shape

    with zipfile.ZipFile(descargar()) as z:
        g = json.loads(z.read(z.namelist()[0]))
    feats = g["features"]
    geoms = [shape(f["geometry"]) for f in feats]
    desde = np.array([f["properties"]["FromYear"] for f in feats])
    hasta = np.array([f["properties"]["ToYear"] for f in feats])
    area = np.array([f["properties"]["Area"] for f in feats], dtype=float)
    nombre = np.array([f["properties"]["Name"] for f in feats], dtype=object)
    arbol = STRtree(geoms)

    ngas = _libro().parse("NGAs")[["NGA", "Latitude", "Longitude"]]
    region = cargar_panel().groupby("NGA").region.first()
    filas = []
    for _, r in ngas.iterrows():
        cand = arbol.query(points(r.Longitude, r.Latitude), predicate="within")
        for anio in ANIOS:
            v = cand[(desde[cand] <= anio) & (hasta[cand] >= anio) & (area[cand] > 0)]
            if v.size == 0:
                continue
            k = v[np.argmax(area[v])]
            filas.append({"NGA": r.NGA, "region": region[r.NGA], "anio": anio, "PolID": nombre[k],
                          "Terr": float(np.log10(area[k]))})
    d = pd.DataFrame(filas).sort_values(["NGA", "anio"]).reset_index(drop=True)
    previa = d.groupby("NGA")["PolID"].shift()
    d["misma_polity"] = (previa == d.PolID) & (d.groupby("NGA").anio.diff() == 100)
    return d


def cargar_panel_cliopatria(regenerar: bool = False) -> pd.DataFrame:
    if regenerar or not SALIDA.exists():
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        construir_panel().to_parquet(SALIDA, index=False)
    return pd.read_parquet(SALIDA)
