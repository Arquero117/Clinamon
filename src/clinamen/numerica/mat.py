"""Fachada numérica del motor.

Todo el código de mecanismos y del motor usa estas funciones en lugar de llamar directamente a
NumPy o SciPy para funciones trascendentes y reducciones. Dos razones:

1. **Determinismo por posición.** El test de POD nulo (§4.5) exige que dos columnas con la misma
   entrada den bits idénticos aunque ocupen posiciones distintas del array. Las operaciones
   aritméticas básicas IEEE (+, -, *, /, sqrt) lo garantizan siempre. Las trascendentes de NumPy
   pueden usar caminos SIMD distintos para el cuerpo y la cola del array según la CPU y la versión.
   ``verificar_determinismo_posicional`` lo comprueba al arrancar el motor y aborta si falla.
2. **Reducciones en orden fijo.** Las sumas sobre entidades se hacen en orden secuencial explícito
   para que el resultado de una partícula no dependa del tamaño del lote.

Convención de forma: las variables de entidad son arrays (E, B); las globales, (1, B); B es el eje
del ensemble (partículas por brazo).
"""
from __future__ import annotations

import numpy as np
from scipy import special as _sp

exp = np.exp
log = np.log
log1p = np.log1p
sqrt = np.sqrt
tanh = np.tanh
ndtri = _sp.ndtri


def potencia(x, y):
    """x**y para x > 0 (y real)."""
    return np.power(x, y)


def sigmoide(x):
    """1 / (1 + e^-x), estable para |x| grande."""
    return 0.5 * (1.0 + np.tanh(0.5 * np.asarray(x, dtype=np.float64)))


def suma_filas(x):
    """Suma sobre el eje 0 (entidades) en orden secuencial fijo. (E, B) -> (1, B)."""
    x = np.asarray(x)
    acc = x[0:1].copy()
    for i in range(1, x.shape[0]):
        acc += x[i:i + 1]
    return acc


def max_filas(x):
    """Máximo sobre el eje 0. (E, B) -> (1, B). El máximo es exacto: no depende del orden."""
    return np.max(x, axis=0, keepdims=True)


def media_filas(x):
    return suma_filas(x) / x.shape[0]


def acotar(x, lo, hi):
    return np.minimum(np.maximum(x, lo), hi)


def positiva(x):
    return np.maximum(x, 0.0)


def division_segura(a, b, si_cero=0.0):
    """a / b con valor fijo donde b == 0."""
    b = np.asarray(b, dtype=np.float64)
    cero = b == 0.0
    return np.where(cero, si_cero, a / np.where(cero, 1.0, b))


_VERIFICADO = False


def verificar_determinismo_posicional(forzar: bool = False) -> None:
    """Comprueba que las funciones trascendentes dan los mismos bits en cualquier posición.

    Lanza ``RuntimeError`` si la plataforma no lo cumple: en ese caso el test de POD nulo no
    podría garantizarse y el motor no debe usarse sin una implementación portable.
    """
    global _VERIFICADO
    if _VERIFICADO and not forzar:
        return
    rng = np.random.default_rng(12345)
    pos = np.exp(rng.normal(0.0, 4.0, 4099))
    uni = rng.random(4099) * 0.999 + 0.0005
    casos = {
        "exp": (np.exp, rng.normal(0.0, 20.0, 4099)),
        "log": (np.log, pos),
        "log1p": (np.log1p, pos),
        "tanh": (np.tanh, rng.normal(0.0, 3.0, 4099)),
        "potencia": (lambda v: np.power(v, 1.37), pos),
        "ndtri": (_sp.ndtri, uni),
    }
    fallos = []
    for nombre, (f, x) in casos.items():
        ref = f(x)
        for desplazamiento in range(1, 33):
            if not np.array_equal(f(x[desplazamiento:]), ref[desplazamiento:], equal_nan=True):
                fallos.append(nombre)
                break
        doble = f(np.concatenate([x[:1001], x[:1001]]))
        if not np.array_equal(doble[:1001], doble[1001:], equal_nan=True):
            fallos.append(nombre + "(concat)")
    if fallos:
        raise RuntimeError(
            "Esta combinación de CPU y NumPy no es determinista por posición en: "
            + ", ".join(fallos)
            + ". El test de POD nulo no puede garantizarse. Véase docs/decisiones/ADR-0003.")
    _VERIFICADO = True
