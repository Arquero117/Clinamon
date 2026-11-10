"""M10 — Puntuación de pronósticos probabilísticos por muestras (§13.3).

* CRPS por muestras: E|X − y| − ½ E|X − X'| (forma ordenada, O(n log n)).
* PIT aleatorizado: u ~ U[F(y⁻), F(y)]. Es la definición correcta para predictivas con átomos (aquí, el cambio
  exactamente cero cuando la polity continúa); con un modelo calibrado u es uniforme.
* Cobertura de un intervalo central de nivel c: fracción de u en [(1−c)/2, (1+c)/2].
* Bootstrap por bloques: se remuestrean regiones enteras (problema de Galton, §13.5).
"""
from __future__ import annotations

import numpy as np


def crps_muestras(muestras: np.ndarray, y: float) -> float:
    x = np.sort(np.asarray(muestras, dtype=np.float64))
    n = x.size
    t1 = np.mean(np.abs(x - y))
    i = np.arange(1, n + 1)
    t2 = np.sum((2 * i - n - 1) * x) / (n * n)          # = ½ E|X − X'|
    return float(t1 - t2)


def pit_aleatorizado(muestras: np.ndarray, y: float, rng: np.random.Generator) -> float:
    x = np.asarray(muestras)
    menor = np.mean(x < y)
    igual = np.mean(x == y)
    return float(menor + igual * rng.random())


def cobertura(pits: np.ndarray, nivel: float) -> float:
    a = (1 - nivel) / 2
    p = np.asarray(pits)
    return float(np.mean((p >= a) & (p <= 1 - a)))


def bootstrap_bloques(valores_por_bloque: dict, estadistico, reps: int, rng: np.random.Generator) -> np.ndarray:
    """valores_por_bloque: bloque -> array de filas. estadistico: f(array concatenado) -> float."""
    claves = list(valores_por_bloque)
    out = np.empty(reps)
    for r in range(reps):
        elegidos = rng.choice(len(claves), size=len(claves), replace=True)
        out[r] = estadistico(np.concatenate([valores_por_bloque[claves[k]] for k in elegidos]))
    return out
