"""Evaluación de la puerta de la fase F0 contra el prerregistro congelado.

Lee ``prerregistro/F0_puerta.yaml``, comprueba que su sha256 coincide con ``F0_puerta.sha256``
(la puerta no se ha movido) y ejecuta cada criterio con los tamaños de ensayo prerregistrados.
Todo el ensayo dura del orden de un minuto en un núcleo.
"""
from __future__ import annotations

import hashlib
import json
import platform
import tempfile
import time
from pathlib import Path

import numpy as np
import yaml

from .. import __version__
from ..gemelos.intervencion import PODInclinacion, PODNulo, PODSuceso
from ..motor.motor import TOLERANCIA_F64, ConfigSimulacion, simular
from ..motor.salida import ConfigEnsemble, commit_git, ejecutar_ensemble, leer
from ..mundos import obtener_modelo

RAIZ = Path(__file__).resolve().parents[3]


def _cargar_prerregistro(raiz: Path = RAIZ):
    ruta = raiz / "prerregistro" / "F0_puerta.yaml"
    contenido = ruta.read_bytes()
    sha = hashlib.sha256(contenido).hexdigest()
    congelado = (raiz / "prerregistro" / "F0_puerta.sha256").read_text().split()[0]
    if sha != congelado:
        raise RuntimeError("el prerregistro de F0 ha cambiado desde su congelación: la puerta no se mueve (§17.2)")
    return yaml.safe_load(contenido), sha


def _tablas_iguales(a, b) -> bool:
    for t in ("observables", "gemelos"):
        x, y = leer(a, t).to_pydict(), leer(b, t).to_pydict()
        if x.keys() != y.keys() or any(not np.array_equal(np.asarray(x[c]), np.asarray(y[c])) for c in x):
            return False
    return True


def _shas(ruta):
    man = json.loads((Path(ruta) / "manifiesto.json").read_text())
    return {i: (b["observables"], b.get("gemelos")) for i, b in man["bloques"].items()}


# ----------------------------------------------------------------------------- criterios
def criterio_determinismo(ens: dict, informar) -> dict:
    out = {}
    pod = {"tipo": "suceso", "fuente": "muerte_gobernante", "evento": "muere", "indice": 7, "paso": ens["paso_pod"]}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        detalle = {}
        for semilla in ens["semillas"]:
            base = dict(mundo="banco_f0", particulas=ens["particulas"], anios=ens["anios"], semilla=semilla, pod=pod)
            q = lambda *_: None
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=16), d / f"a{semilla}", informar=q)
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=16), d / f"b{semilla}", informar=q)
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=23), d / f"c{semilla}", informar=q)
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=16), d / f"p{semilla}", procesos=2, informar=q)
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=16), d / f"r{semilla}", max_bloques=2, informar=q)
            ejecutar_ensemble(ConfigEnsemble(**base, bloque=16), d / f"r{semilla}", informar=q)
            detalle[semilla] = {
                "repeticion_identica": _shas(d / f"a{semilla}") == _shas(d / f"b{semilla}"),
                "invariancia_tamano_bloque": _tablas_iguales(d / f"a{semilla}", d / f"c{semilla}"),
                "invariancia_procesos": _shas(d / f"a{semilla}") == _shas(d / f"p{semilla}"),
                "reanudacion_identica": _shas(d / f"a{semilla}") == _shas(d / f"r{semilla}"),
            }
            # brazo base == ensemble sin gemelos
            ejecutar_ensemble(ConfigEnsemble(**{**base, "pod": None}, bloque=16), d / f"e{semilla}", informar=q)
            g = leer(d / f"a{semilla}", "observables").to_pandas()
            e = leer(d / f"e{semilla}", "observables").to_pandas()
            gb = g[g.mundo == 0].reset_index(drop=True)
            detalle[semilla]["brazo_base_igual_ensemble"] = bool(
                all(np.array_equal(gb[c].to_numpy(), e[c].to_numpy()) for c in e.columns))
            informar(f"  determinismo, semilla {semilla}: {detalle[semilla]}")
    for k in ("repeticion_identica", "invariancia_tamano_bloque", "invariancia_procesos",
              "reanudacion_identica", "brazo_base_igual_ensemble"):
        out[k] = all(v[k] for v in detalle.values())
    out["supera"] = all(out.values())
    out["detalle"] = {str(k): v for k, v in detalle.items()}
    return out


def criterio_pod_nulo(modelo, ens: dict, umbral: float, informar) -> dict:
    t0 = ens["paso_pod"]
    variantes = {
        "nulo": PODNulo(),
        "inclinacion_cero": PODInclinacion("clima_interno", indice=11, paso=t0, desplazamiento=0.0),
        "suceso_intervalo_total": None,   # se elige una arista sin guerra en t0 en todas las partículas
    }
    resultados = []
    for semilla in ens["semillas"]:
        for nombre, pod in variantes.items():
            if pod is None:
                # arista sin guerra en t0 en todas las partículas: el suceso «gana b» tiene entonces
                # intervalo (0, 1), K(A) = 1 y coste exactamente 0 (certificado por el coste, no por la divergencia)
                for k in range(modelo.topo.A):
                    cand = PODSuceso("batalla", "gana_b", indice=k, paso=t0)
                    r0 = simular(modelo, ConfigSimulacion(particulas=ens["particulas"], anios=t0 + 1,
                                                          semilla=semilla, gemelos=True, pods=(cand,)))
                    if np.all(r0.coste == 0.0):
                        pod = cand
                        break
                if pod is None:
                    raise RuntimeError("no hay arista sin guerra en t0: no se puede construir la variante")
            for acop in ("fisico", "maximo", "independiente"):
                maxdif = [0.0]
                N = ens["particulas"]

                def vigilar(t, x, maxdif=maxdif, N=N):
                    for v in x.values():
                        d = float(np.max(np.abs(v[:, N:] - v[:, :N])))
                        if not (d <= maxdif[0]):
                            maxdif[0] = d if np.isfinite(d) else float("inf")

                r = simular(modelo, ConfigSimulacion(particulas=N, anios=ens["anios"], semilla=semilla,
                                                     gemelos=True, pods=(pod,), acoplamiento=acop, al_paso=vigilar))
                resultados.append({"semilla": semilla, "variante": nombre, "acoplamiento": acop,
                                   "max_abs_diferencia": maxdif[0], "coste_max": float(np.max(r.coste)),
                                   "particulas_divergidas": int(np.sum(r.t_div >= 0))})
    peor = max(x["max_abs_diferencia"] for x in resultados)
    # control positivo: el mismo detector ve la diferencia de un POD no nulo
    control = [0.0]

    def vigilar_control(t, x, N=ens["particulas"]):
        for v in x.values():
            control[0] = max(control[0], float(np.max(np.abs(v[:, N:] - v[:, :N]))))

    simular(modelo, ConfigSimulacion(particulas=ens["particulas"], anios=ens["anios"], semilla=ens["semillas"][0],
                                     gemelos=True, pods=(PODInclinacion("clima_interno", 11, t0, 1e-6),),
                                     al_paso=vigilar_control))
    informar(f"  POD nulo: {len(resultados)} combinaciones, máxima diferencia absoluta {peor}; "
             f"control positivo (inclinación de 1e-6): {control[0]:.3g}")
    return {"max_abs_diferencia": peor, "umbral": umbral, "supera": peor <= umbral and control[0] > 0,
            "control_positivo_max_abs_diferencia": control[0], "detalle": resultados}


def criterio_identidades(modelo, ens: dict, informar) -> dict:
    t0 = ens["paso_pod"]
    pods = [PODNulo(), PODSuceso("muerte_gobernante", "muere", 7, t0),
            PODInclinacion("clima_interno", 3, t0, 2.0), PODSuceso("epidemia", "brote", 12, t0)]
    pasos = fallidos = 0
    fallos_rango = 0
    nombres = set()
    for semilla in ens["semillas"]:
        for pod in pods:
            r = simular(modelo, ConfigSimulacion(particulas=ens["particulas"], anios=ens["anios"], semilla=semilla,
                                                 gemelos=True, pods=(pod,), al_fallar="registrar"))
            pasos += r.pasos_verificados
            fallidos += len({f.paso for f in r.fallos if f.tipo == "identidad"})
            fallos_rango += len({f.paso for f in r.fallos if f.tipo == "rango"})
            nombres |= {f.nombre for f in r.fallos}
    frac = 1.0 - fallidos / pasos
    frac_r = 1.0 - fallos_rango / pasos
    informar(f"  identidades: {pasos} pasos verificados, fracción superada {frac}, rangos {frac_r}")
    return {"pasos_verificados": pasos, "fraccion_pasos_superados": frac, "rangos_fraccion_superada": frac_r,
            "identidades_con_fallo": sorted(nombres), "n_identidades": len(modelo.ontologia.identidades),
            "tolerancia_relativa": TOLERANCIA_F64, "supera": frac == 1.0 and frac_r == 1.0}


def criterio_rendimiento(modelo, ens: dict, umbral: float, informar) -> dict:
    out = {}
    for motor in ("auto", "numpy"):
        n, T, cal = ens["particulas_rendimiento"], ens["anios_rendimiento"], ens["anios_calentamiento_rendimiento"]
        pod = (PODSuceso("muerte_gobernante", "muere", 7, 2),)
        simular(modelo, ConfigSimulacion(particulas=n, anios=cal, semilla=1, gemelos=True, pods=pod, motor_philox=motor))
        r = simular(modelo, ConfigSimulacion(particulas=n, anios=T, semilla=1, gemelos=True, pods=pod,
                                             motor_philox=motor))
        out[motor] = r.segundos / (2 * n * T) * 1e6
    E = modelo.E
    var_ent = len([v for v in modelo.ontologia.variables if v.ambito == "entidad"])
    informar(f"  rendimiento: {out['auto']:.1f} µs/trayectoria-año (Philox Numba), {out['numpy']:.1f} (NumPy puro)")
    return {"us_por_trayectoria_anio": out["auto"], "us_por_trayectoria_anio_numpy_puro": out["numpy"],
            "umbral": umbral, "entidades": E, "variables_por_entidad": var_ent,
            "mecanismos": len(modelo.mecanismos), "supera": out["auto"] <= umbral and out["numpy"] <= umbral}


# ----------------------------------------------------------------------------- informe
def evaluar_puerta_f0(salida: str | Path = RAIZ / "informes" / "F0", informar=print) -> dict:
    pre, sha = _cargar_prerregistro()
    ens = pre["puerta"]["ensayo"]
    modelo = obtener_modelo("banco_f0")
    t = time.perf_counter()
    informar(f"[puerta F0] prerregistro sha256 {sha[:16]}… verificado")
    res = {
        "fase": "F0",
        "prerregistro_sha256": sha,
        "version": __version__,
        "commit": commit_git(),
        "entorno": {"python": platform.python_version(), "numpy": np.__version__, "maquina": platform.machine(),
                    "procesador": platform.processor()},
        "ontologia": modelo.ontologia.huella(),
        "criterios": {},
    }
    c = res["criterios"]
    c["determinismo"] = criterio_determinismo(ens, informar)
    c["pod_nulo"] = criterio_pod_nulo(modelo, ens, pre["puerta"]["pod_nulo"]["max_abs_diferencia"], informar)
    c["identidades"] = criterio_identidades(modelo, ens, informar)
    rmin = pre["puerta"]["rendimiento"]["configuracion_minima"]
    c["rendimiento"] = criterio_rendimiento(modelo, ens, pre["puerta"]["rendimiento"]["umbral_us_por_trayectoria_anio"],
                                            informar)
    c["rendimiento"]["configuracion_cumplida"] = (
        c["rendimiento"]["entidades"] >= rmin["entidades"]
        and c["rendimiento"]["variables_por_entidad"] >= rmin["variables_por_entidad"]
        and c["rendimiento"]["mecanismos"] >= rmin["mecanismos"])
    c["rendimiento"]["supera"] = c["rendimiento"]["supera"] and c["rendimiento"]["configuracion_cumplida"]
    res["supera_puerta"] = all(v["supera"] for v in c.values())
    res["segundos"] = time.perf_counter() - t
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "puerta_F0.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (salida / "puerta_F0.md").write_text(informe_markdown(res), encoding="utf-8")
    informar(f"[puerta F0] {'SUPERADA' if res['supera_puerta'] else 'NO SUPERADA'} en {res['segundos']:.0f} s")
    return res


def informe_markdown(res: dict) -> str:
    c = res["criterios"]
    si = lambda b: "✅ supera" if b else "❌ no supera"
    d, p, i, r = c["determinismo"], c["pod_nulo"], c["identidades"], c["rendimiento"]
    lineas = [
        "# Informe de la puerta F0 (Cimientos)",
        "",
        f"- Prerregistro: `prerregistro/F0_puerta.yaml`, sha256 `{res['prerregistro_sha256']}` (verificado, sin cambios).",
        f"- Código: versión {res['version']}, commit `{res['commit']}`.",
        f"- Ontología `banco_f0`: huella `{res['ontologia'][:16]}…`.",
        f"- Entorno: Python {res['entorno']['python']}, NumPy {res['entorno']['numpy']}, {res['entorno']['maquina']}.",
        f"- Duración del ensayo: {res['segundos']:.0f} s.",
        "",
        f"## Resultado: {'PUERTA SUPERADA' if res['supera_puerta'] else 'PUERTA NO SUPERADA'}",
        "",
        "| Criterio | Medida | Umbral prerregistrado | Resultado |",
        "| --- | --- | --- | --- |",
        f"| Determinismo: repetición idéntica (sha256) | {d['repeticion_identica']} | sí | {si(d['repeticion_identica'])} |",
        f"| Determinismo: invariancia al tamaño de bloque | {d['invariancia_tamano_bloque']} | sí | {si(d['invariancia_tamano_bloque'])} |",
        f"| Determinismo: invariancia al nº de procesos | {d['invariancia_procesos']} | sí | {si(d['invariancia_procesos'])} |",
        f"| Determinismo: reanudación idéntica | {d['reanudacion_identica']} | sí | {si(d['reanudacion_identica'])} |",
        f"| Determinismo: brazo base = ensemble | {d['brazo_base_igual_ensemble']} | sí | {si(d['brazo_base_igual_ensemble'])} |",
        f"| POD nulo: máx. diferencia absoluta ({len(p['detalle'])} combinaciones variante × acoplamiento × semilla) | {p['max_abs_diferencia']} | {p['umbral']} | {si(p['supera'])} |",
        f"| POD nulo: control positivo (inclinación v = 1e-6, coste 5e-13 nats; el detector la ve) | {p['control_positivo_max_abs_diferencia']:.3g} | > 0 | {si(p['control_positivo_max_abs_diferencia'] > 0)} |",
        f"| Identidades contables: fracción de pasos superados ({i['pasos_verificados']} pasos, {i['n_identidades']} identidades) | {i['fraccion_pasos_superados']} | 1.0 | {si(i['fraccion_pasos_superados'] == 1.0)} |",
        f"| Rangos declarados: fracción de pasos superados | {i['rangos_fraccion_superada']} | 1.0 | {si(i['rangos_fraccion_superada'] == 1.0)} |",
        f"| Rendimiento (µs por trayectoria-año, 1 núcleo, Philox Numba) | {r['us_por_trayectoria_anio']:.1f} | ≤ {r['umbral']} | {si(r['us_por_trayectoria_anio'] <= r['umbral'])} |",
        f"| Rendimiento (µs por trayectoria-año, 1 núcleo, NumPy puro) | {r['us_por_trayectoria_anio_numpy_puro']:.1f} | ≤ {r['umbral']} | {si(r['us_por_trayectoria_anio_numpy_puro'] <= r['umbral'])} |",
        f"| Configuración del ensayo de rendimiento | {r['entidades']} entidades, {r['variables_por_entidad']} variables/entidad, {r['mecanismos']} mecanismos | ≥ 30, 40, 15 | {si(r['configuracion_cumplida'])} |",
        "",
        "## Qué no valida esta puerta",
        "",
        "- Nada sobre la historia: el mundo `banco_f0` es de prueba y sus parámetros son supuestos.",
        "- Ni Λ ≤ 1 ni el estimador del rastro: son puerta de F1.",
        "- El rendimiento se mide en la máquina donde se ejecuta el ensayo; en otra máquina hay que repetirlo "
        "(`clinamen puerta-f0`).",
    ]
    return "\n".join(lineas) + "\n"
