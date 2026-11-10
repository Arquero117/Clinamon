"""M10 — Mundos sintéticos con verdad conocida (§13.2): la única prueba directa de la cadena completa.

Por mundo:
1. Verdad: θ sorteado del prior, historia simulada en los pasos 0..T_obs−1 y degradada por el modelo de
   observación de la ontología (solo algunas variables, con ruido y huecos).
2. Asimilación (M6): posterior de θ y del estado tras el paso T_obs−1 usando solo la historia degradada
   (consulta I, variante de hindcast, §4.4: leyes y estado filtrados hasta t0).
3. Efecto estimado de cada POD candidato en t0 = T_obs sobre Y = observable tras H pasos: para cada una de S
   muestras (θ, x_t0) de la posterior, R réplicas con todos los candidatos como brazos (azar común).
   Intervalo del 90 % = cuantiles 5–95 % de los efectos por muestra (capa paramétrica y de estado; la capa de
   Monte Carlo se informa aparte).
4. Efecto verdadero: el mismo cálculo desde (θ, x_t0) verdaderos con muchas réplicas.

Toda salida es de la consulta I: diferencia de medias marginales entre brazos, que no depende del acoplamiento.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from ..asimilacion.filtro import Prior, observar, posterior_adaptativa
from ..contingencia.estimadores import rastro_dv
from ..gemelos.intervencion import pod_desde_dict
from ..motor.motor import ConfigSimulacion, Simulacion, simular
from ..mundos import obtener_modelo


def candidatos_f1(t0: int) -> list[dict]:
    """Doce PODs: muerte del gobernante e inclinación +1 del ruido de capacidad en cada entidad, en t0.
    El POD plantado es la muerte del gobernante de la entidad 0 (índice 0). Las entidades 3–5 están en otra
    componente: sus PODs tienen efecto nulo en ley sobre capacidad_0."""
    out = [{"tipo": "suceso", "fuente": "muerte_gobernante", "evento": "muere", "indice": e, "paso": t0}
           for e in range(6)]
    out += [{"tipo": "inclinacion", "fuente": "ruido_capacidad", "indice": e, "paso": t0, "desplazamiento": 1.0}
            for e in range(6)]
    return out


NULOS_F1 = [3, 4, 5, 9, 10, 11]      # índices de candidatos con efecto nulo por construcción
PLANTADO_F1 = 0


@dataclass
class ConfigExperimento:
    mundo: str = "sintetico_f1"
    inferidos: tuple = ("sf_beta", "sf_sigma")
    observable: str = "capacidad_0"
    T_obs: int = 30
    H: int = 5
    M: int = 256
    K: int = 256
    etapas: int = 3
    S: int = 200
    R: int = 50
    R_verdad: int = 4000
    candidatos: list = field(default_factory=lambda: candidatos_f1(30))


def _no_flujo(modelo, x, col=None):
    return {v.nombre: (x[v.nombre] if col is None else x[v.nombre][:, col:col + 1]).copy()
            for v in modelo.ontologia.variables if v.tipo != "flujo"}


def mundo_verdadero(modelo, cfg: ConfigExperimento, semilla: int):
    prior = Prior.desde_ontologia(modelo, list(cfg.inferidos))
    rng = np.random.default_rng([semilla, 101])
    theta = prior.muestrear(1, rng)[0]
    sim = Simulacion(modelo, ConfigSimulacion(particulas=1, anios=0, semilla=semilla, particula0=10_000_000,
                                              parametros=dict(zip(cfg.inferidos, map(float, theta)))))
    datos = []
    for _ in range(cfg.T_obs):
        sim.paso()
        y = observar(modelo, sim.x, sim.p.como_dict(), rng)
        datos.append({k: v[:, 0] for k, v in y.items()})
    return theta, datos, _no_flujo(modelo, sim.x)


def efectos(modelo, cfg: ConfigExperimento, theta: np.ndarray, estado: dict, R: int, semilla: int,
            particula0: int):
    """Gemelos desde S estados (columnas de ``estado``) con R réplicas cada uno y un brazo por candidato.

    theta: (S, d). Devuelve dict con Y por brazo (A, S, R), costes (A, S, R).
    """
    S = theta.shape[0]
    est = {k: np.repeat(v, R, axis=1) for k, v in estado.items()}
    par = {n: np.repeat(theta[:, j], R)[None, :] for j, n in enumerate(cfg.inferidos)}
    ramas = tuple((pod_desde_dict(c),) for c in cfg.candidatos)
    r = simular(modelo, ConfigSimulacion(particulas=S * R, anios=cfg.H, semilla=semilla, particula0=particula0,
                                         estado0=est, paso0=cfg.T_obs, parametros=par, ramas=ramas,
                                         verificar=False))
    A = len(ramas) + 1
    Y = r.observables[cfg.observable][-1].reshape(A, S, R)
    return {"Y": Y, "coste": r.coste_brazos.reshape(A, S, R)}


def experimento(semilla: int, cfg: ConfigExperimento | None = None) -> dict:
    cfg = cfg or ConfigExperimento()
    modelo = obtener_modelo(cfg.mundo)
    theta_v, datos, estado_v = mundo_verdadero(modelo, cfg, semilla)
    prior = Prior.desde_ontologia(modelo, list(cfg.inferidos))
    post = posterior_adaptativa(modelo, prior, datos, semilla, M=cfg.M, K=cfg.K, etapas=cfg.etapas)
    rng = np.random.default_rng([semilla, 202])
    th_s, est_s = post.muestras_conjuntas(cfg.S, rng)

    est = efectos(modelo, cfg, th_s, est_s, cfg.R, semilla + 1, particula0=0)
    ver = efectos(modelo, cfg, theta_v[None, :], estado_v, cfg.R_verdad, semilla + 2, particula0=20_000_000)
    Yb, Yv = est["Y"][0], ver["Y"][0, 0]
    filas = []
    for i, cand in enumerate(cfg.candidatos):
        d = est["Y"][i + 1] - Yb                      # (S, R)
        ef_s = d.mean(axis=1)                         # efecto por muestra de la posterior
        dv = ver["Y"][i + 1, 0] - Yv                  # (R_verdad,)
        verdad, se_verdad = float(dv.mean()), float(dv.std(ddof=1) / np.sqrt(dv.size))
        lo, hi = np.quantile(ef_s, [0.05, 0.95])
        se_cluster = float(ef_s.std(ddof=1) / np.sqrt(cfg.S))
        z = float(ef_s.mean() / se_cluster) if se_cluster > 0 else 0.0
        from scipy.stats import norm
        rastro = rastro_dv(est["Y"][i + 1].ravel(), Yb.ravel(), semilla=semilla)
        coste = float(est["coste"][i + 1].mean())
        filas.append({
            "candidato": i, "pod": cand, "efecto_verdadero": verdad, "error_tipico_verdad": se_verdad,
            "efecto_estimado": float(ef_s.mean()), "ic90": [float(lo), float(hi)],
            "cubre": bool(lo <= verdad <= hi),
            "error_tipico_montecarlo": float(np.mean(d.std(axis=1, ddof=1)) / np.sqrt(cfg.R)),
            "z": z, "p_valor": float(2 * norm.sf(abs(z))),
            "coste_nats": coste, "rastro_dv": rastro["rastro"], "error_tipico_rastro": rastro["error_tipico"],
            "lambda": rastro["rastro"] / coste if coste > 0 else 0.0,
            "error_tipico_lambda": rastro["error_tipico"] / coste if coste > 0 else 0.0,
        })
    return {"semilla": semilla, "theta_verdadero": theta_v.tolist(), "ess_theta": post.ess,
            "theta_post_media": (post.pesos() @ post.theta).tolist(), "candidatos": filas, "config": asdict(cfg)}


# ----------------------------------------------------------------------------- agregados
def benjamini_hochberg(p: np.ndarray, q: float = 0.05) -> np.ndarray:
    p = np.asarray(p)
    n = p.size
    orden = np.argsort(p)
    umbral = q * np.arange(1, n + 1) / n
    ok = p[orden] <= umbral
    k = np.max(np.nonzero(ok)[0]) + 1 if ok.any() else 0
    desc = np.zeros(n, bool)
    desc[orden[:k]] = True
    return desc


def resumir(resultados: list, nulos=NULOS_F1, plantado=PLANTADO_F1, posicion_max=3) -> dict:
    cubre = [r["candidatos"][plantado]["cubre"] for r in resultados]
    rec, fdp, lam_ok, n_disc = [], [], [], []
    for r in resultados:
        c = r["candidatos"]
        orden = np.argsort([-abs(x["efecto_estimado"]) for x in c])
        rec.append(int(np.nonzero(orden == plantado)[0][0]) < posicion_max)
        desc = benjamini_hochberg(np.array([x["p_valor"] for x in c]))
        falsos = sum(desc[i] for i in nulos)
        fdp.append(falsos / max(1, desc.sum()))
        n_disc.append(int(desc.sum()))
        lam_ok += [x["lambda"] - 2 * x["error_tipico_lambda"] <= 1.0 for x in c]
    return {"mundos": len(resultados), "cobertura": float(np.mean(cubre)),
            "recuperacion_top3": float(np.mean(rec)), "fdr": float(np.mean(fdp)),
            "descubrimientos_medios": float(np.mean(n_disc)), "fraccion_lambda_ok": float(np.mean(lam_ok)),
            "ess_theta_mediana": float(np.median([r["ess_theta"] for r in resultados]))}
