"""M2 — Ingesta del panel Seshat Equinox 2020 (§16 paso 4).

Lee el zip original (sin modificarlo), verifica su sha256 y produce un panel región × siglo con:
NGA, region (gran región mundial), anio, PolID, SPC (índice de complejidad social), Pop y Terr (log10).
Cada serie conserva su procedencia. Seshat codifica por polity: el valor se repite mientras la polity dura
(columna `misma_polity` = la polity del siglo anterior en la misma región es la misma).
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
ZIP = RAIZ / "datos" / "brutos" / "seshat_equinox" / "equinox.zip"
SHA256 = "29127b15366bfce0bc39e52c0b6717fd0397291f7861464bf26885d611ada013"
SALIDA = RAIZ / "datos" / "procesados" / "seshat_panel.parquet"


def _libro(ruta: Path = ZIP) -> pd.ExcelFile:
    datos = ruta.read_bytes()
    if hashlib.sha256(datos).hexdigest() != SHA256:
        raise RuntimeError("el zip de Seshat no coincide con el registrado (procedencia rota)")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombre = next(n for n in z.namelist() if n.endswith(".xlsx"))
        return pd.ExcelFile(io.BytesIO(z.read(nombre)))


def construir_panel(ruta: Path = ZIP) -> pd.DataFrame:
    x = _libro(ruta)
    imp = x.parse("ImpSCDat")[["NGA", "PolID", "Time", "Pop", "Terr"]]
    spc = x.parse("SPC_MilTech")[["NGA", "PolID", "Time", "SPC"]]
    pol = x.parse("Polities")[["PolID", "World Region"]].drop_duplicates("PolID")
    d = imp.merge(spc, on=["NGA", "PolID", "Time"], how="inner")
    d = d.merge(pol, on="PolID", how="left")
    region = d.groupby("NGA")["World Region"].agg(lambda s: s.mode().iloc[0])
    d["region"] = d["NGA"].map(region)
    # una fila por región y siglo: si hay varias polities en el mismo siglo, la de mayor población
    d = d.sort_values(["NGA", "Time", "Pop"], ascending=[True, True, False]).drop_duplicates(["NGA", "Time"])
    d = d.rename(columns={"Time": "anio"})[["NGA", "region", "anio", "PolID", "SPC", "Pop", "Terr"]]
    d = d.sort_values(["NGA", "anio"]).reset_index(drop=True)
    previa = d.groupby("NGA")["PolID"].shift()
    consecutivo = d.groupby("NGA")["anio"].diff() == 100
    d["misma_polity"] = (previa == d["PolID"]) & consecutivo
    return d


def cargar_panel(regenerar: bool = False) -> pd.DataFrame:
    if regenerar or not SALIDA.exists():
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        construir_panel().to_parquet(SALIDA, index=False)
    return pd.read_parquet(SALIDA)
