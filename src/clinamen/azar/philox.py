"""Philox4x32-10 vectorizado (Salmon y otros, 2011; Random123).

Generador por contador: la salida es una función pura de (contador de 128 bits, clave de 64 bits).
No hay estado secuencial, de modo que el sorteo de (partícula, fuente, entidad, paso) es siempre el
mismo con independencia del orden de cálculo, del tamaño de bloque o del número de procesos
(manual §4.5).

La aritmética es entera sin signo de 32 bits: el resultado es idéntico bit a bit en cualquier
plataforma y en cualquier backend (NumPy, Numba, CuPy). Se verifica con los vectores de respuesta
conocida de Random123 en ``tests/test_philox.py``.
"""
from __future__ import annotations

import numpy as np

M0 = 0xD2511F53
M1 = 0xCD9E8D57
W0 = 0x9E3779B9
W1 = 0xBB67AE85
RONDAS = 10

_M0 = np.uint64(M0)
_M1 = np.uint64(M1)
_W0 = np.uint32(W0)
_W1 = np.uint32(W1)
_S32 = np.uint64(32)


def philox4x32_numpy(c0, c1, c2, c3, k0, k1, rondas: int = RONDAS):
    """Philox4x32 en NumPy puro. Entradas uint32 difundibles; devuelve 4 arrays uint32."""
    c0, c1, c2, c3 = np.broadcast_arrays(
        np.asarray(c0, np.uint32), np.asarray(c1, np.uint32),
        np.asarray(c2, np.uint32), np.asarray(c3, np.uint32))
    k0 = np.uint32(k0)
    k1 = np.uint32(k1)
    with np.errstate(over="ignore"):
        for r in range(rondas):
            if r:
                k0 = np.uint32((int(k0) + W0) & 0xFFFFFFFF)
                k1 = np.uint32((int(k1) + W1) & 0xFFFFFFFF)
            p0 = _M0 * c0.astype(np.uint64)
            p1 = _M1 * c2.astype(np.uint64)
            hi0 = (p0 >> _S32).astype(np.uint32)
            lo0 = p0.astype(np.uint32)
            hi1 = (p1 >> _S32).astype(np.uint32)
            lo1 = p1.astype(np.uint32)
            c0, c1, c2, c3 = hi1 ^ c1 ^ k0, lo1, hi0 ^ c3 ^ k1, lo0
    return c0, c1, c2, c3


_philox_numba = None


def _construir_numba():
    """Compila la versión Numba si está disponible. Aritmética entera: bits idénticos a NumPy."""
    global _philox_numba
    if _philox_numba is not None:
        return _philox_numba
    try:
        import numba as nb
    except ImportError:  # pragma: no cover - depende del entorno
        _philox_numba = False
        return False

    @nb.njit(cache=True, nogil=True)
    def _kernel(c0, c1, c2, c3, k0, k1, o0, o1, o2, o3):
        n = c0.size
        for i in range(n):
            x0 = np.uint64(c0[i]); x1 = np.uint64(c1[i])
            x2 = np.uint64(c2[i]); x3 = np.uint64(c3[i])
            a = np.uint64(k0); b = np.uint64(k1)
            for r in range(10):
                if r > 0:
                    a = (a + np.uint64(0x9E3779B9)) & np.uint64(0xFFFFFFFF)
                    b = (b + np.uint64(0xBB67AE85)) & np.uint64(0xFFFFFFFF)
                p0 = np.uint64(0xD2511F53) * x0
                p1 = np.uint64(0xCD9E8D57) * x2
                hi0 = p0 >> np.uint64(32); lo0 = p0 & np.uint64(0xFFFFFFFF)
                hi1 = p1 >> np.uint64(32); lo1 = p1 & np.uint64(0xFFFFFFFF)
                x0 = hi1 ^ x1 ^ a
                x1 = lo1
                x2 = hi0 ^ x3 ^ b
                x3 = lo0
            o0[i] = np.uint32(x0); o1[i] = np.uint32(x1)
            o2[i] = np.uint32(x2); o3[i] = np.uint32(x3)

    _philox_numba = _kernel
    return _kernel


def philox4x32(c0, c1, c2, c3, k0, k1, motor: str = "auto"):
    """Philox4x32-10. ``motor``: 'numpy', 'numba' o 'auto' (Numba si está instalado)."""
    if motor in ("auto", "numba"):
        kern = _construir_numba()
        if kern:
            c0, c1, c2, c3 = np.broadcast_arrays(
                np.asarray(c0, np.uint32), np.asarray(c1, np.uint32),
                np.asarray(c2, np.uint32), np.asarray(c3, np.uint32))
            forma = c0.shape
            planos = [np.ascontiguousarray(c).reshape(-1) for c in (c0, c1, c2, c3)]
            salida = [np.empty(planos[0].size, np.uint32) for _ in range(4)]
            kern(*planos, int(k0), int(k1), *salida)
            return tuple(s.reshape(forma) for s in salida)
        if motor == "numba":
            raise RuntimeError("Numba no está instalado")
    return philox4x32_numpy(c0, c1, c2, c3, k0, k1)


_ESCALA_52 = 2.0 ** -52


def a_uniformes(x0, x1):
    """Dos palabras uint32 -> uniforme float64 en (0, 1) con 52 bits de resolución.

    u = (k + 0.5) * 2^-52 con k < 2^52 entero: es exactamente representable, nunca vale 0 ni 1
    y su mínimo es 2^-53, de modo que log(u) y log(1-u) son siempre finitos.
    """
    k = ((x0 >> np.uint32(6)).astype(np.uint64) << np.uint64(26)) | (x1 >> np.uint32(6)).astype(np.uint64)
    return (k.astype(np.float64) + 0.5) * _ESCALA_52
