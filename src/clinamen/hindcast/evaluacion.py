"""M10 — Hindcast con origen móvil y validación por gran región dejada fuera (§13.3; puerta F2a).

Regla sin fuga: en cada origen O, todo ajuste (rivales, pesos de apilamiento, referencias nulas) usa solo pares
(y_t, y_{t+100}) con t + 100 ≤ O; se predicen los valores en O + 100, O + 200 y O + 300 desde el valor observado en O.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .modelos import PASO, RIVALES, Transiciones
from .puntuacion import crps_muestras, pit_aleatorizado

OBSERVABLES = ("SPC", "Pop", "Terr")
PASOS = (1, 2, 3)


def _cambios_h(panel, var, k, hasta=None, regiones_fuera=None):
    """Cambios empíricos a k siglos (pares de la misma región)."""
    d = panel.sort_values(["NGA", "anio"])
    if regiones_fuera is not None:
        d = d[~d.region.isin(regiones_fuera)]
    sig = d.groupby("NGA")[var].shift(-k)
    a_sig = d.groupby("NGA")["anio"].shift(-k)
    ok = (a_sig - d["anio"] == PASO * k) & sig.notna()
    if hasta is not None:
        ok &= a_sig <= hasta
    return (sig - d[var])[ok].to_numpy(float)


# ----------------------------------------------------------------------------- referencias nulas
def persistencia(panel, var, y0, n, rng, hasta=None, regiones_fuera=None):
    out = np.empty((len(y0), len(PASOS), n))
    for j, k in enumerate(PASOS):
        c = _cambios_h(panel, var, k, hasta, regiones_fuera)
        if c.size == 0:
            c = np.zeros(1)
        out[:, j] = np.asarray(y0)[:, None] + rng.choice(c, size=(len(y0), n))
    return out


def tendencia(panel, var, ngas, origen, y0, n, rng, hasta=None):
    out = np.empty((len(y0), len(PASOS), n))
    for i, (g, y) in enumerate(zip(ngas, y0)):
        h = panel[(panel.NGA == g) & (panel.anio >= origen - 500) & (panel.anio <= origen)]
        pend = np.polyfit(h.anio, h[var], 1)[0] if len(h) >= 3 else 0.0
        for j, k in enumerate(PASOS):
            c = _cambios_h(panel, var, k, hasta)
            c = (c - c.mean()) if c.size else np.zeros(1)
            out[i, j] = y + pend * PASO * k + rng.choice(c, size=n)
    return out


def climatologia(panel, var, origen, m, n, rng):
    v = panel[(panel.anio <= origen) & (panel.anio >= origen - 300)][var].to_numpy(float)
    if v.size == 0:
        v = panel[panel.anio <= origen][var].to_numpy(float)
    return rng.choice(v, size=(m, len(PASOS), n))


# ----------------------------------------------------------------------------- rivales y apilamiento
def ajustar_rivales(panel, var, regiones, rng, hasta=None, regiones_fuera=None):
    d = panel if regiones_fuera is None else panel[~panel.region.isin(regiones_fuera)]
    tr = Transiciones.desde_panel(d, var, regiones, hasta)
    return {k: C(len(regiones)).ajustar(tr, rng) for k, C in RIVALES.items()}


def mezcla(preds: dict, pesos: dict, rng) -> np.ndarray:
    nombres = list(preds)
    P, K, n = preds[nombres[0]].shape
    cuantos = np.floor(np.array([pesos[k] for k in nombres]) * n).astype(int)
    cuantos[np.argmax(cuantos)] += n - cuantos.sum()
    partes = [preds[k][:, :, rng.choice(n, c, replace=False)] for k, c in zip(nombres, cuantos) if c > 0]
    return np.concatenate(partes, axis=2)


def pesos_apilamiento(panel, var, regiones, rng, corte, hasta_val, regiones_fuera=None, n=1000):
    """Pesos en el símplex (rejilla de 0.1) que minimizan el CRPS medio a un siglo de las transiciones con
    destino en (corte, hasta_val], usando rivales ajustados con datos hasta `corte`."""
    mods = ajustar_rivales(panel, var, regiones, rng, hasta=corte, regiones_fuera=regiones_fuera)
    d = panel if regiones_fuera is None else panel[~panel.region.isin(regiones_fuera)]
    d = d.sort_values(["NGA", "anio"])
    sig = d.groupby("NGA")[var].shift(-1)
    a_sig = d.groupby("NGA")["anio"].shift(-1)
    ok = (a_sig - d.anio == PASO) & (a_sig > corte) & (a_sig <= hasta_val)
    if ok.sum() == 0:
        return {k: 1 / 3 for k in RIVALES}
    idx = {r: i for i, r in enumerate(regiones)}
    y0, reg0, yv = d.loc[ok, var].to_numpy(), d.loc[ok, "region"].map(idx).to_numpy(), sig[ok].to_numpy()
    pr = {k: m.predecir(y0, reg0, 1, n, rng)[:, 0] for k, m in mods.items()}
    mejor = None
    rej = np.round(np.arange(0, 1.0001, 0.1), 1)
    for a in rej:
        for b in rej:
            c = round(1 - a - b, 1)
            if c < -1e-9:
                continue
            w = {"R1": a, "R2": b, "R3": max(c, 0.0)}
            mz = mezcla({k: v[:, None] for k, v in pr.items()}, w, rng)[:, 0]
            sc = np.mean([crps_muestras(mz[i], yv[i]) for i in range(len(yv))])
            if mejor is None or sc < mejor[0]:
                mejor = (sc, w)
    return mejor[1]


# ----------------------------------------------------------------------------- hindcast
def hindcast_origen(panel, origen, regiones, rng, n=2000, observables=OBSERVABLES) -> pd.DataFrame:
    filas = []
    idx = {r: i for i, r in enumerate(regiones)}
    for var in observables:
        base = panel[panel.anio == origen]
        if base.empty:
            continue
        objetivo = {k: panel[panel.anio == origen + PASO * k].set_index("NGA")[var] for k in PASOS}
        sirve = [g for g in base.NGA if any(g in objetivo[k].index for k in PASOS)]
        base = base.set_index("NGA").loc[sirve]
        if base.empty:
            continue
        y0, reg0, ngas = base[var].to_numpy(float), base.region.map(idx).to_numpy(), list(base.index)
        w = pesos_apilamiento(panel, var, regiones, rng, corte=origen - 500, hasta_val=origen)
        mods = ajustar_rivales(panel, var, regiones, rng, hasta=origen)
        pr = {k: m.predecir(y0, reg0, len(PASOS), n, rng) for k, m in mods.items()}
        metodos = {"apilado": mezcla(pr, w, rng), **pr,
                   "persistencia": persistencia(panel, var, y0, n, rng, hasta=origen),
                   "tendencia": tendencia(panel, var, ngas, origen, y0, n, rng, hasta=origen),
                   "climatologia": climatologia(panel, var, origen, len(y0), n, rng)}
        for i, g in enumerate(ngas):
            for j, k in enumerate(PASOS):
                if g not in objetivo[k].index:
                    continue
                y = float(objetivo[k][g])
                fila = {"origen": origen, "NGA": g, "region": regiones[reg0[i]], "observable": var,
                        "horizonte": PASO * k, "y0": y0[i], "y": y, "pesos": str(w)}
                for nombre, S in metodos.items():
                    fila[f"crps_{nombre}"] = crps_muestras(S[i, j], y)
                    fila[f"pit_{nombre}"] = pit_aleatorizado(S[i, j], y, rng)
                filas.append(fila)
    return pd.DataFrame(filas)


def hindcast_region_fuera(panel, region, regiones, rng, var="SPC", n=2000) -> pd.DataFrame:
    """Ajuste con todas las demás grandes regiones (todas las fechas); predicción a 100 años de la región dejada
    fuera desde cada uno de sus siglos. Pesos de apilamiento validados en los últimos 500 años del resto."""
    idx = {r: i for i, r in enumerate(regiones)}
    fuera = [region]
    amax = int(panel.anio.max())
    w = pesos_apilamiento(panel, var, regiones, rng, corte=amax - 500, hasta_val=amax, regiones_fuera=fuera)
    mods = ajustar_rivales(panel, var, regiones, rng, regiones_fuera=fuera)
    d = panel[panel.region == region].sort_values(["NGA", "anio"])
    sig = d.groupby("NGA")[var].shift(-1)
    ok = (d.groupby("NGA")["anio"].shift(-1) - d.anio == PASO) & sig.notna()
    if ok.sum() == 0:
        return pd.DataFrame()
    y0, yv = d.loc[ok, var].to_numpy(float), sig[ok].to_numpy(float)
    reg0 = np.full(len(y0), idx[region])
    pr = {k: m.predecir(y0, reg0, 1, n, rng) for k, m in mods.items()}
    ap = mezcla(pr, w, rng)[:, 0]
    pe = persistencia(panel, var, y0, n, rng, regiones_fuera=fuera)[:, 0]
    return pd.DataFrame({"region": region, "NGA": d.loc[ok, "NGA"].to_numpy(), "anio": d.loc[ok, "anio"].to_numpy(),
                         "crps_apilado": [crps_muestras(ap[i], yv[i]) for i in range(len(yv))],
                         "crps_persistencia": [crps_muestras(pe[i], yv[i]) for i in range(len(yv))]})


# ----------------------------------------------------------------------------- Chapman-Kolmogorov
def matrices_transicion(panel, var="SPC", tramos=5, cortes=None):
    if cortes is None:
        cortes = np.quantile(panel[var], np.linspace(0, 1, tramos + 1)[1:-1])
    d = panel.sort_values(["NGA", "anio"]).copy()
    d["tramo"] = np.digitize(d[var], cortes)

    def T(k, dd):
        a = dd.groupby("NGA")["tramo"].shift(-k)
        ok = (dd.groupby("NGA")["anio"].shift(-k) - dd.anio == PASO * k) & a.notna()
        C = np.zeros((tramos, tramos))
        np.add.at(C, (dd.loc[ok, "tramo"].to_numpy(int), a[ok].to_numpy(int)), 1)
        s = C.sum(1, keepdims=True)
        return np.where(s > 0, C / np.where(s > 0, s, 1), np.nan)

    return d, cortes, T


def chapman_kolmogorov(panel, rng, var="SPC", tramos=5, reps=1000, cortes=None):
    d, cortes, T = matrices_transicion(panel, var, tramos, cortes)
    T1, T2 = T(1, d), T(2, d)
    pred = T1 @ T1
    ngas = d.NGA.unique()
    boot = []
    for _ in range(reps):
        elegidas = rng.choice(ngas, size=ngas.size, replace=True)
        partes = []
        for k, g in enumerate(elegidas):
            p = d[d.NGA == g].copy()
            p["NGA"] = f"{g}#{k}"
            partes.append(p)
        boot.append(T(2, pd.concat(partes)))
    boot = np.array(boot)
    lo, hi = np.nanpercentile(boot, 2.5, axis=0), np.nanpercentile(boot, 97.5, axis=0)
    dentro = (pred >= lo - 1e-12) & (pred <= hi + 1e-12)
    return {"T100": T1.tolist(), "T200": T2.tolist(), "T100_al_cuadrado": pred.tolist(),
            "fraccion_celdas_dentro": float(np.mean(dentro)), "cortes": cortes.tolist()}
