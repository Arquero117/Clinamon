"""Evaluación de la puerta de la fase F1 contra el prerregistro congelado (prerregistro/F1_puerta.yaml).

Uso de las semillas de puerta (fijado antes de usarlas, docs/fases/F1_progreso.md):
910001 → juguetes; 910002 → cobertura (200 mundos: semillas 910002000 + i); 910003 → POD plantado (50 mundos).

Reanudable: cada juguete y cada mundo se guarda en <salida>/partes/*.json y no se repite.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import yaml

from .. import __version__
from ..contingencia.banco import evaluar_juguete
from ..contingencia.juguetes import JUGUETES
from ..motor.salida import commit_git
from ..validacion.sintetico import ConfigExperimento, experimento, resumir

RAIZ = Path(__file__).resolve().parents[3]
TAMANOS_JUGUETES = {"n_ajuste": 60000, "n_prueba": 40000, "n_pod": 200000, "nodos": (12, 32),
                    "lotes_t2": 16, "n_lote_t2": 10000}


def _un_hilo():
    """Un hilo de BLAS por proceso trabajador: con varios procesos, el multihilo de BLAS sobresuscribe los núcleos."""
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
        os.environ.setdefault(v, "1")


def _prerregistro():
    ruta = RAIZ / "prerregistro" / "F1_puerta.yaml"
    contenido = ruta.read_bytes()
    sha = hashlib.sha256(contenido).hexdigest()
    if sha != (RAIZ / "prerregistro" / "F1_puerta.sha256").read_text().split()[0]:
        raise RuntimeError("el prerregistro de F1 ha cambiado desde su congelación: la puerta no se mueve (§17.2)")
    return yaml.safe_load(contenido), sha


def _tarea(tipo: str, clave, semilla: int) -> dict:
    if tipo == "juguete":
        t = TAMANOS_JUGUETES
        return evaluar_juguete(clave, t["n_ajuste"], t["n_prueba"], t["n_pod"], semilla, t["nodos"],
                               lotes_t2=t["lotes_t2"], n_lote_t2=t["n_lote_t2"])
    return experimento(semilla, ConfigExperimento())


def _a_json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def evaluar_puerta_f1(salida: str | Path = RAIZ / "informes" / "F1", procesos: int = 4,
                      max_horas: float = 2.0, informar=print) -> dict:
    pre, sha = _prerregistro()
    semillas = pre["ensayo"]["semillas_puerta"]
    pu = pre["puerta"]
    salida = Path(salida)
    partes = salida / "partes"
    partes.mkdir(parents=True, exist_ok=True)
    n_cob, n_pla = pu["cobertura"]["replicas_min"], pu["pod_plantado"]["mundos_min"]
    tareas = [("juguete", k, semillas[0]) for k in JUGUETES]
    tareas += [("cobertura", i, semillas[1] * 1000 + i) for i in range(n_cob)]
    tareas += [("plantado", i, semillas[2] * 1000 + i) for i in range(n_pla)]

    def fichero(t):
        return partes / f"{t[0]}_{t[1]}.json"

    pendientes = [t for t in tareas if not fichero(t).exists()]
    informar(f"[puerta F1] prerregistro sha256 {sha[:16]}… verificado; {len(pendientes)} de {len(tareas)} tareas pendientes")
    if any(t[0] != "juguete" for t in pendientes):
        t0 = time.perf_counter()
        experimento(12345, ConfigExperimento())          # semilla de desarrollo: solo para medir
        seg_mundo = time.perf_counter() - t0
        n_m = sum(t[0] != "juguete" for t in pendientes)
        est = (n_m * seg_mundo + 600.0 * sum(t[0] == "juguete" for t in pendientes)) / procesos
        informar(f"[puerta F1] ~{seg_mundo:.0f} s por mundo; duración estimada {est / 60:.0f} min con {procesos} procesos")
        if est > max_horas * 3600:
            raise RuntimeError(f"duración estimada {est / 3600:.1f} h supera el máximo de {max_horas} h")
    t_ini = time.perf_counter()
    cpu = 0.0
    _un_hilo()
    with ProcessPoolExecutor(max_workers=procesos, mp_context=multiprocessing.get_context("spawn")) as ex:
        fut = {ex.submit(_tarea_cronometrada, *t): t for t in pendientes}
        for i, f in enumerate(as_completed(fut), 1):
            t = fut[f]
            res, seg = f.result()
            res["_segundos"] = seg
            cpu += seg
            fichero(t).write_text(json.dumps(res, default=_a_json, ensure_ascii=False), encoding="utf-8")
            if t[0] == "juguete" or i % 25 == 0 or i == len(pendientes):
                informar(f"[puerta F1] {i}/{len(pendientes)} ({t[0]} {t[1]}) {time.perf_counter() - t_ini:.0f} s")

    res = {t: json.loads(fichero(t).read_text(encoding="utf-8")) for t in tareas}
    jug = {k: res[("juguete", k, semillas[0])] for k in JUGUETES}
    cob = [res[("cobertura", i, semillas[1] * 1000 + i)] for i in range(n_cob)]
    pla = [res[("plantado", i, semillas[2] * 1000 + i)] for i in range(n_pla)]
    rc, rp = resumir(cob), resumir(pla)
    lam_toys = [j["teorema_1"]["supera_cota"] for j in jug.values()]
    lam_cands = [c["lambda"] - 2 * c["error_tipico_lambda"] <= 1.0 for r in cob + pla for c in r["candidatos"]]
    cpu_total = sum(r.get("_segundos", 0.0) for r in res.values())
    crit = {
        "committor": {k: j["committor"]["supera"] for k, j in jug.items()},
        "teorema_2": {k: j["teorema_2"]["supera"] for k, j in jug.items()},
        "teorema_3": {k: j["teorema_3"]["supera"] for k, j in jug.items()},
        "lambda_juguetes": {k: j["teorema_1"]["supera"] for k, j in jug.items()},
        "lambda_le_1_fraccion": float(np.mean(lam_toys + lam_cands)),
        "cobertura": rc["cobertura"],
        "recuperacion_top3": rp["recuperacion_top3"],
        "fdr": rp["fdr"],
        "horas_cpu_8_nucleos": cpu_total / 3600 / 8,
    }
    supera = {
        "committor": all(crit["committor"].values()),
        "teorema_2": all(crit["teorema_2"].values()),
        "teorema_3": all(crit["teorema_3"].values()),
        "cota_informacion": all(crit["lambda_juguetes"].values()) and crit["lambda_le_1_fraccion"] == 1.0,
        "cobertura": pu["cobertura"]["cobertura_min"] <= rc["cobertura"] <= pu["cobertura"]["cobertura_max"],
        "pod_plantado": rp["recuperacion_top3"] >= pu["pod_plantado"]["fraccion_recuperado_min"]
                        and rp["fdr"] <= pu["pod_plantado"]["fdr_max"],
        "computo": crit["horas_cpu_8_nucleos"] <= pu["computo"]["horas_max_cpu_8_nucleos"],
    }
    out = {"fase": "F1", "prerregistro_sha256": sha, "version": __version__, "commit": commit_git(),
           "entorno": {"python": platform.python_version(), "maquina": platform.machine(), "procesos": procesos},
           "tamanos_juguetes": TAMANOS_JUGUETES, "config_mundos": cob[0]["config"],
           "juguetes": jug, "resumen_cobertura": rc, "resumen_plantado": rp, "criterios": crit,
           "supera": supera, "supera_puerta": all(supera.values()), "segundos_reloj": time.perf_counter() - t_ini,
           "segundos_cpu": cpu_total}
    (salida / "puerta_F1.json").write_text(json.dumps(out, indent=2, default=_a_json, ensure_ascii=False),
                                           encoding="utf-8")
    (salida / "puerta_F1.md").write_text(informe_markdown(out), encoding="utf-8")
    informar(f"[puerta F1] {'SUPERADA' if out['supera_puerta'] else 'NO SUPERADA'}: {supera}")
    return out


def _tarea_cronometrada(tipo, clave, semilla):
    t = time.perf_counter()
    r = _tarea(tipo, clave, semilla)
    return r, time.perf_counter() - t


def informe_markdown(o: dict) -> str:
    si = lambda b: "✅" if b else "❌"
    L = ["# Informe de la puerta F1 (Banco canónico y mundo sintético)", "",
         f"- Prerregistro `prerregistro/F1_puerta.yaml`, sha256 `{o['prerregistro_sha256']}` (verificado, sin cambios).",
         f"- Código: versión {o['version']}, commit `{o['commit']}`. Semillas de puerta usadas por primera vez en esta evaluación.",
         f"- Cómputo: {o['segundos_cpu'] / 3600:.2f} h de CPU en total ({o['criterios']['horas_cpu_8_nucleos']:.2f} h con 8 núcleos); "
         f"{o['segundos_reloj'] / 60:.0f} min de reloj con {o['entorno']['procesos']} procesos.", "",
         f"## Resultado: {'PUERTA SUPERADA' if o['supera_puerta'] else 'PUERTA NO SUPERADA'}", "",
         "## Juguetes (semilla 910001)", "",
         "| Juguete | P(B) | ĥ: error máx. / e.t. máx. | Teorema 2: Σρ̂ − M₀(1−M₀) | Teorema 3: Σκ̂ + log P̂(B) ; L1 | Λ̂ ± e.t. (exacto) |",
         "| --- | --- | --- | --- | --- | --- |"]
    for k, j in o["juguetes"].items():
        c = j["committor"]["instantes"]
        t2, t3, t1 = j["teorema_2"], j["teorema_3"], j["teorema_1"]
        L.append(f"| {k} | {j['P_B_exacta']:.3f} | {max(x['error_max'] for x in c):.4f} / {max(x['error_tipico_max'] for x in c):.4f} {si(j['committor']['supera'])} "
                 f"| {t2['diferencia']:+.4f} ± {t2['error_tipico']:.4f} {si(t2['supera'])} "
                 f"| {t3['diferencia']:+.4f} ± {t3['error_tipico']:.4f} ; {t3['error_L1_relativo']:.3f} {si(t3['supera'])} "
                 f"| {t1['lambda_estimada']:.4f} ± {t1['error_tipico_lambda']:.4f} ({t1['lambda_exacta']:.4f}) {si(t1['supera'])} |")
    rc, rp, cr, su = o["resumen_cobertura"], o["resumen_plantado"], o["criterios"], o["supera"]
    L += ["", "Umbrales: ĥ ≤ 0.02 o ≤ 3 e.t.; Teoremas 2 y 3 ≤ 3 e.t.; L1 del perfil κ ≤ 0.10; Λ̂ ∈ [0.8 Λ, Λ + 3 e.t.] y Λ̂ − 2 e.t. ≤ 1.", "",
          "## Mundos sintéticos", "",
          "| Criterio | Medida | Umbral | |", "| --- | --- | --- | --- |",
          f"| Cobertura del IC 90 % del efecto del POD plantado ({rc['mundos']} mundos, semilla 910002) | {rc['cobertura']:.3f} | [0.85, 0.95] | {si(su['cobertura'])} |",
          f"| POD plantado entre los 3 primeros ({rp['mundos']} mundos, semilla 910003) | {rp['recuperacion_top3']:.3f} | ≥ 0.80 | {si(rp['recuperacion_top3'] >= 0.8)} |",
          f"| FDR (Benjamini-Hochberg, q = 0.05; 6 nulos de 12 candidatos) | {rp['fdr']:.3f} | ≤ 0.05 | {si(rp['fdr'] <= 0.05)} |",
          f"| Λ̂ − 2 e.t. ≤ 1 en todos los PODs (juguetes y candidatos) | {cr['lambda_le_1_fraccion']:.3f} | 1.0 | {si(su['cota_informacion'])} |",
          f"| Cómputo con 8 núcleos | {cr['horas_cpu_8_nucleos']:.2f} h | ≤ 1 h | {si(su['computo'])} |",
          f"| ESS mediana de θ en la asimilación | {rc['ess_theta_mediana']:.0f} | (informativo) | |", "",
          "## Qué no valida esta puerta", "",
          "- Nada histórico: los juguetes y el mundo sintético no describen ninguna sociedad.",
          "- La cobertura se mide en el caso bien especificado (el modelo verdadero pertenece a la clase). La mala especificación (experimentos cruzados entre rivales) es puerta de F3.",
          "- La consulta evaluada es la I (variante de hindcast). Las consultas II y III no son validables (§13.1).",
          "- Los juguetes y el mundo sintético son discretizaciones y modelos pequeños; el rendimiento en el motor completo se mide en cada caso."]
    return "\n".join(L) + "\n"
