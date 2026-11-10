"""Evaluación de los estimadores de M8 contra la verdad exacta de los juguetes (puerta F1, §13.2)."""
from __future__ import annotations

import numpy as np

from . import estimadores as es
from .cadena import CadenaFinita
from .juguetes import JUGUETES


def _estado(c: CadenaFinita, x) -> int:
    """Índice del estado cuyo primer rasgo está más cerca de x (con el resto de rasgos en su mediana)."""
    d = np.abs(c.rasgos[:, 0] - x)
    if c.rasgos.shape[1] > 1:
        d = d + 1e-9 * np.abs(c.rasgos[:, 1:] - np.median(c.rasgos[:, 1:], axis=0)).sum(axis=1)
    return int(np.argmin(d))


def pods_designados(nombre: str, c: CadenaFinita) -> dict:
    """Un POD-suceso por juguete: estado de partida, instante, conjunto A de llegada y etiquetas del observable."""
    x = c.rasgos[:, 0]
    ocho = np.digitize(x, np.linspace(-1.6, 1.6, 9)[1:-1])   # observable: x_T en 8 tramos
    if nombre == "doble_pozo_gaussiano":
        return {"x0": _estado(c, -1.0), "t0": 45, "A": x > -0.2, "etiquetas": ocho}
    if nombre == "doble_pozo_estable":
        return {"x0": _estado(c, -1.0), "t0": 10, "A": x > 0.0, "etiquetas": (x > 0).astype(np.int64)}
    if nombre == "urna_polya":
        return {"x0": 1, "t0": 0, "A": np.arange(c.n) == 2, "etiquetas": np.arange(c.n)}
    if nombre == "lento_rapido":
        i0 = _estado(c, 0.0)
        return {"x0": i0, "t0": 0, "A": (x > c.rasgos[i0, 0]) & (c.rasgos[:, 1] == 1), "etiquetas": ocho}
    if nombre == "doble_pozo_deriva":
        return {"x0": _estado(c, -1.0), "t0": 30, "A": x > -0.5, "etiquetas": ocho}
    raise KeyError(nombre)


def rejilla_evaluacion(p_t: np.ndarray, rasgos: np.ndarray, n: int = 20, masa: float = 0.90):
    """Al menos n estados en la masa central de p_t (cuantiles 5 %–95 %), ordenados por el primer rasgo."""
    orden = np.argsort(rasgos[:, 0], kind="stable")
    cdf = np.cumsum(p_t[orden])
    lo, hi = (1 - masa) / 2, 1 - (1 - masa) / 2
    sel = orden[(cdf >= lo) & (cdf - p_t[orden] <= hi) & (p_t[orden] > 0)]
    return sel


def teorema_2_por_lotes(c: CadenaFinita, lotes: int, n_lote: int, semilla: int, nodos: int) -> dict:
    """Teorema 2 con lotes independientes: en cada lote, ĥ¹ y ĥ² se ajustan en dos tercios disjuntos y se evalúan
    en el tercero (productos cruzados). El error típico sale de la dispersión entre lotes e incluye por tanto el
    ruido del ajuste de ĥ, no solo el de las trayectorias de prueba."""
    difs, sumas = [], []
    for k in range(lotes):
        tr = c.simular(3 * n_lote, semilla, id0=k * 3 * n_lote, flujo=7)
        R = c.rasgos[tr]
        y = c.B[tr[-1]]
        a, b, d = slice(0, n_lote), slice(n_lote, 2 * n_lote), slice(2 * n_lote, None)
        h1 = es.Committor.ajustar(R[:, a], y[a], nodos)
        h2 = es.Committor.ajustar(R[:, b], y[b], nodos)
        r = es.presupuesto_cruzado(h1.en_trayectorias(R[:, d], y[d]), h2.en_trayectorias(R[:, d], y[d]), y[d],
                                   bootstrap=2)
        difs.append(r["diferencia"]); sumas.append(r["suma"])
    difs = np.array(difs)
    return {"suma_rho": float(np.mean(sumas)), "diferencia": float(difs.mean()),
            "error_tipico": float(difs.std(ddof=1) / np.sqrt(lotes)), "lotes": lotes, "n_lote": n_lote}


def evaluar_juguete(nombre: str, n_ajuste: int, n_prueba: int, n_pod: int, semilla: int, nodos: int = 12,
                    instantes=(0.5, 0.75, 0.9), lotes_t2: int = 16, n_lote_t2: int = 10000) -> dict:
    c = JUGUETES[nombre]()
    h = c.committor()
    p = c.marginales()
    tr = c.simular(2 * n_ajuste + n_prueba, semilla)
    R = c.rasgos[tr]
    yB = c.B[tr[-1]]
    a, b, d = slice(0, n_ajuste), slice(n_ajuste, 2 * n_ajuste), slice(2 * n_ajuste, None)
    ab = slice(0, 2 * n_ajuste)
    h12 = es.Committor.ajustar(R[:, ab], yB[ab], nodos)
    out = {"juguete": nombre, "n_ajuste": n_ajuste, "n_prueba": n_prueba, "n_pod": n_pod, "nodos": nodos,
           "P_B_exacta": float(p[0] @ h[0])}

    # committor en rejilla
    filas = []
    for f in instantes:
        t = int(round(f * c.T))
        t = min(t, c.T - 1)
        idx = rejilla_evaluacion(p[t], c.rasgos)
        est, se = h12(t, c.rasgos[idx], error_tipico=True)
        err = np.abs(est - h[t][idx])
        tol = np.maximum(0.02, 3 * se)
        filas.append({"t": t, "n_estados": int(idx.size), "error_max": float(err.max()),
                      "error_tipico_max": float(se.max()), "supera": bool(np.all(err <= tol)) and idx.size >= 20})
    out["committor"] = {"instantes": filas, "supera": all(x["supera"] for x in filas)}

    # Teorema 2
    t2 = teorema_2_por_lotes(c, lotes_t2, n_lote_t2, semilla, nodos)
    _, ini_ex = c.presupuesto()
    out["teorema_2"] = dict(t2, exacto=ini_ex, supera=abs(t2["diferencia"]) <= 3 * t2["error_tipico"])

    # Teorema 3
    H = h12.en_trayectorias(R[:, d], yB[d])
    h0, se0 = h12(0, c.rasgos[tr[0, :1]], error_tipico=True)
    kp = es.perfil_kappa(H, yB[d], error_relativo_h0=float(se0[0] / h0[0]))
    k_ex, k0 = c.kappa()
    l1 = es.error_L1_relativo(kp["kappa"], k_ex)
    out["teorema_3"] = {"suma_kappa": kp["suma"], "menos_log_PB": kp["menos_log_PB"], "exacto": float(k_ex.sum() + k0),
                        "diferencia": kp["diferencia"], "error_tipico": kp["error_tipico"], "error_L1_relativo": l1,
                        "supera": abs(kp["diferencia"]) <= 3 * kp["error_tipico"] and l1 <= 0.10}

    # Teorema 1: Λ del POD designado
    pd = pods_designados(nombre, c)
    p_ini = np.zeros(c.n); p_ini[pd["x0"]] = 1.0
    ex = c.pod_suceso(pd["t0"], pd["A"], etiquetas=pd["etiquetas"], p_inicial=p_ini)
    base, pod, coste = c.simular_gemelos(n_pod, semilla + 1, pd["t0"], pd["A"], x0=pd["x0"])
    dv = es.rastro_dv(pd["etiquetas"][pod[-1]], pd["etiquetas"][base[-1]], semilla=semilla)
    cm = float(coste.mean())
    lam, se_lam = dv["rastro"] / cm, dv["error_tipico"] / cm
    out["teorema_1"] = {"coste_exacto": ex.coste, "coste_estimado": cm, "rastro_exacto": ex.rastro,
                        "rastro_dv": dv["rastro"], "lambda_exacta": ex.eficiencia, "lambda_estimada": lam,
                        "error_tipico_lambda": se_lam,
                        "supera_cota": lam - 2 * se_lam <= 1.0,
                        "supera_tolerancia": (lam >= 0.8 * ex.eficiencia) and (lam <= ex.eficiencia + 3 * se_lam)}
    out["teorema_1"]["supera"] = out["teorema_1"]["supera_cota"] and out["teorema_1"]["supera_tolerancia"]
    out["supera"] = all(out[k]["supera"] for k in ("committor", "teorema_2", "teorema_3", "teorema_1"))
    return out
