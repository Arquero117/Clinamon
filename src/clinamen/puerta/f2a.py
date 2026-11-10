"""Evaluación de la puerta F2a (hindcast de escala social con Seshat) contra prerregistro/F2a_puerta.yaml.

Decisiones de operacionalización fijadas antes de ejecutar (docs/fases/F2_progreso.md):
* bootstrap por bloques de GRAN REGIÓN mundial (el agrupamiento del prerregistro), 1000 réplicas;
* cobertura con el PIT aleatorizado (predictivas con átomo en el cambio cero);
* inevitabilidad en las grandes regiones con ≥ 30 predicciones de SPC (como la cobertura estratificada).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import __version__
from ..hindcast.evaluacion import (OBSERVABLES, chapman_kolmogorov, hindcast_origen, hindcast_region_fuera,
                                   matrices_transicion)
from ..hindcast.modelos import R1, Transiciones
from ..hindcast.puntuacion import bootstrap_bloques, cobertura
from ..ingesta.seshat import cargar_panel
from ..motor.salida import commit_git

RAIZ = Path(__file__).resolve().parents[3]


def _prerregistro():
    c = (RAIZ / "prerregistro" / "F2a_puerta.yaml").read_bytes()
    sha = hashlib.sha256(c).hexdigest()
    if sha != (RAIZ / "prerregistro" / "F2a_puerta.sha256").read_text().split()[0]:
        raise RuntimeError("el prerregistro de F2a ha cambiado: la puerta no se mueve (§17.2)")
    return yaml.safe_load(c), sha


def evaluar_puerta_f2a(salida=RAIZ / "informes" / "F2a", informar=print) -> dict:
    pre, sha = _prerregistro()
    pu, ens = pre["puerta"], pre["ensayo"]
    rng = np.random.default_rng(ens["semillas_puerta"][0])
    n = ens["muestras_predictivas"]
    t0 = time.perf_counter()
    panel = cargar_panel()
    regs = sorted(panel.region.unique())
    informar(f"[puerta F2a] prerregistro {sha[:16]}… verificado; {len(panel)} siglos-región")

    res = []
    for o in pre["hindcast"]["origenes"]:
        r = hindcast_origen(panel, o, regs, rng, n=n)
        res.append(r)
        informar(f"[puerta F2a] origen {o}: {len(r)} predicciones")
    H = pd.concat(res, ignore_index=True)
    lor = pd.concat([hindcast_region_fuera(panel, r, regs, rng, n=n) for r in regs], ignore_index=True)
    ck = chapman_kolmogorov(panel, rng, reps=ens["bootstrap_reps"])

    # T(200) simulada por R1 ajustado con todo el panel (informativa)
    d, cortes, _ = matrices_transicion(panel, "SPC", 5, np.array(ck["cortes"]))
    r1 = R1(len(regs)).ajustar(Transiciones.desde_panel(panel, "SPC", regs), rng)
    s2 = d.groupby("NGA")["anio"].shift(-2) - d.anio == 200
    ini = d[s2]
    sim = r1.predecir(ini.SPC.to_numpy(), ini.region.map({r: i for i, r in enumerate(regs)}).to_numpy(), 2, 200, rng)
    C = np.zeros((5, 5))
    for a, fila in zip(np.digitize(ini.SPC, cortes), np.digitize(sim[:, 1], cortes)):
        np.add.at(C, (np.full(fila.size, a), fila), 1)
    ck["T200_R1_simulada"] = (C / C.sum(1, keepdims=True)).tolist()

    crit, supera = {}, {}
    # habilidad frente a persistencia
    hab = {}
    for h in pu["habilidad_persistencia"]["horizontes"]:
        s = H[(H.observable == "SPC") & (H.horizonte == h)]
        bloques = {g: s[s.region == g][["crps_apilado", "crps_persistencia"]].to_numpy() for g in s.region.unique()}
        f = lambda a: 1 - a[:, 0].sum() / a[:, 1].sum()
        b = bootstrap_bloques(bloques, f, ens["bootstrap_reps"], rng)
        hab[h] = {"habilidad": float(f(s[["crps_apilado", "crps_persistencia"]].to_numpy())),
                  "cota_inferior_90": float(np.quantile(b, 0.05)), "n": int(len(s))}
    crit["habilidad_persistencia"] = hab
    supera["habilidad_persistencia"] = all(v["cota_inferior_90"] > 0 for v in hab.values())
    # coberturas agregadas
    cob = {}
    for var in OBSERVABLES:
        for h in (100, 200, 300):
            p = H[(H.observable == var) & (H.horizonte == h)].pit_apilado.to_numpy()
            cob[f"{var}_{h}"] = {"c90": cobertura(p, 0.9), "c50": cobertura(p, 0.5), "n": int(p.size)}
    lo90, hi90 = pu["cobertura_agregada"]["cobertura_90"]
    lo50, hi50 = pu["cobertura_agregada"]["cobertura_50"]
    crit["cobertura_agregada"] = cob
    supera["cobertura_agregada"] = all(lo90 <= v["c90"] <= hi90 and lo50 <= v["c50"] <= hi50 for v in cob.values())
    # estratificada e inevitabilidad
    est, inev = {}, {}
    s = H[H.observable == "SPC"]
    for g, x in s.groupby("region"):
        if len(x) >= 30:
            est[g] = {"c90": cobertura(x.pit_apilado.to_numpy(), 0.9), "n": int(len(x))}
            inev[g] = float(x.pit_apilado.mean())
    lo, hi = pu["cobertura_estratificada"]["cobertura_90"]
    crit["cobertura_estratificada"] = est
    supera["cobertura_estratificada"] = all(lo <= v["c90"] <= hi for v in est.values())
    lo, hi = pu["inevitabilidad"]["rango"]
    crit["inevitabilidad_pit_medio"] = inev
    supera["inevitabilidad"] = all(lo <= v <= hi for v in inev.values())
    # civilización no usada
    civ = {g: {"habilidad": float(1 - x.crps_apilado.sum() / x.crps_persistencia.sum()), "n": int(len(x))}
           for g, x in lor.groupby("region")}
    crit["civilizacion_no_usada"] = civ
    supera["civilizacion_no_usada"] = sum(v["habilidad"] > 0 for v in civ.values()) >= \
        pu["civilizacion_no_usada"]["regiones_con_habilidad_positiva_min"]
    crit["chapman_kolmogorov"] = ck
    supera["chapman_kolmogorov"] = ck["fraccion_celdas_dentro"] >= pu["chapman_kolmogorov"]["fraccion_celdas_min"]
    seg = time.perf_counter() - t0
    crit["segundos"] = seg
    supera["computo"] = seg / 3600 <= pu["computo"]["horas_max_cpu_8_nucleos"] * 8

    # informativo: puntuaciones medias por método, observable y horizonte; habilidad frente a otras referencias
    metodos = [c[5:] for c in H.columns if c.startswith("crps_")]
    tabla = H.groupby(["observable", "horizonte"])[[f"crps_{m}" for m in metodos]].mean()
    out = {"fase": "F2a", "prerregistro_sha256": sha, "version": __version__, "commit": commit_git(),
           "criterios": crit, "supera": supera, "supera_puerta": all(supera.values()),
           "crps_medio": {f"{a}_{b}": r.to_dict() for (a, b), r in tabla.iterrows()},
           "n_predicciones": int(len(H)), "pesos_apilamiento": {f"{a}|{b}": v for (a, b), v in H.groupby(["origen", "observable"]).pesos.first().items()}}
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    H.to_parquet(salida / "hindcast.parquet", index=False)
    lor.to_parquet(salida / "region_fuera.parquet", index=False)
    (salida / "puerta_F2a.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    informar(f"[puerta F2a] {'SUPERADA' if out['supera_puerta'] else 'NO SUPERADA'}: {supera}")
    return out
