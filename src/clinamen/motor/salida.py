"""Ejecución de ensembles por bloques: Parquet, reanudable, con duración estimada (§0.3).

Estructura de una corrida en disco::

    <salida>/manifiesto.json            configuración, huellas, bloques completados, estimación
    <salida>/observables/bloque-00000.parquet   mundo, particula, paso, anio, <observables macro>
    <salida>/gemelos/bloque-00000.parquet       particula, coste_nats, paso_divergencia   (si hay POD)
    <salida>/anclas/bloque-00000.parquet        mundo, particula, paso, entidad, <variables> (años ancla)

Cada bloque es un rango de partículas. Como el azar se indexa por identificador global de
partícula, el resultado no depende del tamaño de bloque ni del número de procesos, y una corrida
interrumpida se reanuda saltándose los bloques ya escritos (cuyo sha256 consta en el manifiesto).
Las escrituras son atómicas (fichero temporal + renombrado).
"""
from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .. import __version__
from ..gemelos.intervencion import pod_desde_dict
from ..mundos import obtener_modelo
from .motor import ConfigSimulacion, Resultado, simular


def _sha256_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _escribir_atomico_parquet(tabla: pa.Table, ruta: Path) -> str:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    pq.write_table(tabla, tmp, compression="zstd")
    os.replace(tmp, ruta)
    return _sha256_fichero(ruta)


def _escribir_atomico_json(datos: dict, ruta: Path) -> None:
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, ruta)


def commit_git() -> str | None:
    try:
        raiz = Path(__file__).resolve().parents[3]
        return subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


# ------------------------------------------------------------------------- tablas
def tabla_observables(res: Resultado, anio0: int = 0) -> pa.Table:
    T, B = next(iter(res.observables.values())).shape
    N = res.N
    mundo = np.repeat(np.arange(B // N, dtype=np.int8), N)
    particula = np.tile(res.particulas, B // N)
    cols = {
        "mundo": np.tile(mundo, T),
        "particula": np.tile(particula, T).astype(np.int64),
        "paso": np.repeat(np.arange(T, dtype=np.int32), B),
    }
    cols["anio"] = (cols["paso"] + anio0).astype(np.int32)
    for k, v in res.observables.items():
        cols[k] = v.reshape(-1)
    return pa.table(cols)


def tabla_gemelos(res: Resultado) -> pa.Table:
    return pa.table({"particula": res.particulas.astype(np.int64), "coste_nats": res.coste,
                     "paso_divergencia": res.t_div})


def tabla_anclas(res: Resultado, modelo) -> pa.Table | None:
    if not res.anclas:
        return None
    filas = []
    for paso, estado in sorted(res.anclas.items()):
        B = next(iter(estado.values())).shape[1]
        N = res.N
        E = modelo.E
        mundo = np.repeat(np.arange(B // N, dtype=np.int8), N)
        cols = {
            "mundo": np.tile(mundo, E),
            "particula": np.tile(np.tile(res.particulas, B // N), E).astype(np.int64),
            "paso": np.full(E * B, paso, dtype=np.int32),
            "entidad": np.repeat(np.arange(E, dtype=np.int16), B),
        }
        for k, v in estado.items():
            cols[k] = np.broadcast_to(v, (E, B)).reshape(-1)
        filas.append(pa.table(cols))
    return pa.concat_tables(filas)


# ------------------------------------------------------------------------- configuración
@dataclass
class ConfigEnsemble:
    mundo: str
    particulas: int
    anios: int
    semilla: int
    pod: dict | None = None
    acoplamiento: str = "fisico"
    bloque: int = 256
    anios_ancla: tuple = ()
    verificar: bool = True
    motor_philox: str = "auto"

    def como_dict(self) -> dict:
        return {
            "mundo": self.mundo, "particulas": self.particulas, "anios": self.anios,
            "semilla": self.semilla, "pod": self.pod, "acoplamiento": self.acoplamiento,
            "bloque": self.bloque, "anios_ancla": list(self.anios_ancla), "verificar": self.verificar,
        }

    def bloques(self) -> list[tuple[int, int, int]]:
        n = math.ceil(self.particulas / self.bloque)
        return [(i, i * self.bloque, min(self.bloque, self.particulas - i * self.bloque)) for i in range(n)]


def _config_simulacion(cfg: ConfigEnsemble, particula0: int, n: int, anios: int | None = None) -> ConfigSimulacion:
    gemelos = cfg.pod is not None
    return ConfigSimulacion(
        particulas=n, anios=cfg.anios if anios is None else anios, semilla=cfg.semilla, particula0=particula0,
        gemelos=gemelos, pods=(pod_desde_dict(cfg.pod),) if gemelos else (),
        acoplamiento=cfg.acoplamiento, verificar=cfg.verificar, al_fallar="error",
        anios_ancla=tuple(cfg.anios_ancla), motor_philox=cfg.motor_philox)


def _ejecutar_bloque(cfg: ConfigEnsemble, salida: str, i: int, p0: int, n: int) -> dict:
    modelo = obtener_modelo(cfg.mundo)
    res = simular(modelo, _config_simulacion(cfg, p0, n))
    base = Path(salida)
    info = {"particulas": [p0, p0 + n], "segundos": res.segundos,
            "pasos_verificados": res.pasos_verificados}
    nombre = f"bloque-{i:05d}.parquet"
    info["observables"] = _escribir_atomico_parquet(tabla_observables(res, modelo.anio0), base / "observables" / nombre)
    if res.gemelos:
        info["gemelos"] = _escribir_atomico_parquet(tabla_gemelos(res), base / "gemelos" / nombre)
    t_anclas = tabla_anclas(res, modelo)
    if t_anclas is not None:
        info["anclas"] = _escribir_atomico_parquet(t_anclas, base / "anclas" / nombre)
    return info


# ------------------------------------------------------------------------- estimación
def estimar_duracion(cfg: ConfigEnsemble, procesos: int = 1) -> dict:
    """Mide un tramo corto y extrapola. Conservadora: el piloto incluye sobrecostes fijos."""
    modelo = obtener_modelo(cfg.mundo)
    n = min(cfg.bloque, cfg.particulas, 128)
    anios = min(cfg.anios, 8)
    simular(modelo, _config_simulacion(cfg, 0, min(n, 4), 1))  # calentamiento (compilación Numba)
    res = simular(modelo, _config_simulacion(cfg, 0, n, anios))
    brazos = 2 if cfg.pod is not None else 1
    us = res.segundos / (n * brazos * anios) * 1e6
    total_tray_anio = cfg.particulas * brazos * cfg.anios
    segundos = us * 1e-6 * total_tray_anio / max(1, min(procesos, len(cfg.bloques())))
    obs = len(modelo.ontologia.observables)
    mb = total_tray_anio * (obs * 8 + 13) / 1e6
    return {"us_por_trayectoria_anio": us, "trayectorias_anio": total_tray_anio, "procesos": procesos,
            "segundos_estimados": segundos, "megabytes_observables_sin_comprimir": mb}


# ------------------------------------------------------------------------- ejecución
def ejecutar_ensemble(cfg: ConfigEnsemble, salida: str | Path, procesos: int = 1,
                      max_horas: float | None = None, solo_estimar: bool = False,
                      max_bloques: int | None = None, informar=print) -> dict:
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    modelo = obtener_modelo(cfg.mundo)
    config = cfg.como_dict()
    config["ontologia"] = modelo.ontologia.huella()
    config["version"] = __version__
    huella = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    ruta_man = salida / "manifiesto.json"
    if ruta_man.exists():
        man = json.loads(ruta_man.read_text(encoding="utf-8"))
        if man["huella_config"] != huella:
            raise RuntimeError(f"{salida} contiene una corrida con otra configuración; usa otra carpeta")
    else:
        man = {
            "huella_config": huella,
            "config": config,
            "consulta": "I" if cfg.pod is not None else "prediccion_sin_intervencion",
            "nota_consulta": ("Consulta I (prospectiva interventiva): ambos brazos parten del mismo estado con azar fresco. "
                              "En F0 el estado inicial sale del prior de prueba, sin asimilación.")
            if cfg.pod is not None else "Ensemble sin intervención desde el prior de prueba.",
            "acoplamiento": cfg.acoplamiento if cfg.pod is not None else None,
            "advertencia": modelo.ontologia.advertencia,
            "bloques": {},
        }
    man["entorno"] = {"commit": commit_git(), "python": platform.python_version(), "numpy": np.__version__,
                      "pyarrow": pa.__version__, "maquina": platform.machine(), "procesos": procesos}

    est = estimar_duracion(cfg, procesos)
    man["estimacion"] = est
    pendientes = []
    for i, p0, n in cfg.bloques():
        info = man["bloques"].get(str(i))
        ok = info is not None and all(
            (salida / sub / f"bloque-{i:05d}.parquet").exists()
            and _sha256_fichero(salida / sub / f"bloque-{i:05d}.parquet") == info[sub]
            for sub in ("observables", "gemelos", "anclas") if sub in info)
        if not ok:
            pendientes.append((i, p0, n))
    fraccion = sum(n for _, _, n in pendientes) / max(1, cfg.particulas)
    seg = est["segundos_estimados"] * fraccion
    informar(f"[clinamen] {est['us_por_trayectoria_anio']:.1f} µs/trayectoria-año medidos en un tramo corto; "
             f"{len(pendientes)} de {len(cfg.bloques())} bloques pendientes; duración estimada "
             f"{seg / 60:.1f} min con {procesos} proceso(s).")
    if max_horas is not None and seg > max_horas * 3600:
        _escribir_atomico_json(man, ruta_man)
        raise RuntimeError(f"duración estimada {seg / 3600:.2f} h supera el máximo de {max_horas} h; "
                           "reduce partículas o años, o aumenta procesos")
    if solo_estimar:
        return man
    if max_bloques is not None:
        pendientes = pendientes[:max_bloques]
    _escribir_atomico_json(man, ruta_man)

    t0 = time.perf_counter()
    hechos = 0

    def registrar(i, info):
        nonlocal hechos
        hechos += 1
        man["bloques"][str(i)] = info
        _escribir_atomico_json(man, ruta_man)
        trans = time.perf_counter() - t0
        resto = trans / hechos * (len(pendientes) - hechos)
        informar(f"[clinamen] bloque {i} listo ({hechos}/{len(pendientes)}); {trans:.0f} s, quedan ~{resto:.0f} s")

    if procesos <= 1:
        for i, p0, n in pendientes:
            registrar(i, _ejecutar_bloque(cfg, str(salida), i, p0, n))
    else:
        with ProcessPoolExecutor(max_workers=procesos, mp_context=multiprocessing.get_context("spawn")) as ex:
            futuros = {ex.submit(_ejecutar_bloque, cfg, str(salida), i, p0, n): i for i, p0, n in pendientes}
            for fut in as_completed(futuros):
                registrar(futuros[fut], fut.result())
    completos = len(man["bloques"]) == len(cfg.bloques())
    man["estado"] = "completo" if completos else "parcial"
    _escribir_atomico_json(man, ruta_man)
    return man


def leer(salida: str | Path, tipo: str = "observables") -> pa.Table:
    """Lee y concatena los bloques de una corrida, ordenados por (mundo, particula, paso)."""
    ficheros = sorted((Path(salida) / tipo).glob("bloque-*.parquet"))
    if not ficheros:
        raise FileNotFoundError(f"no hay bloques de {tipo} en {salida}")
    t = pa.concat_tables([pq.read_table(f) for f in ficheros])
    claves = [c for c in ("mundo", "particula", "paso", "entidad") if c in t.column_names]
    return t.sort_by([(c, "ascending") for c in claves])
