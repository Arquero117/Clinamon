"""Verificación de identidades contables (A3) y de rangos (M1) en cada paso."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..numerica import mat
from ..ontologia.esquema import Identidad, Ontologia


@dataclass
class Fallo:
    paso: int
    tipo: str          # 'identidad' o 'rango'
    nombre: str
    celdas: int
    peor: float        # residuo relativo máximo o valor fuera de rango

    def __str__(self):
        return f"paso {self.paso}: {self.tipo} {self.nombre} falla en {self.celdas} celdas (peor {self.peor:.3g})"


def stocks_vigilados(ont: Ontologia) -> list[str]:
    s = set()
    for i in ont.identidades:
        if i.tipo in ("stock_flujo", "stock_global_constante"):
            s.add(i.stock)
    return sorted(s)


def _suma(x, nombres):
    acc = None
    for n in nombres:
        acc = x[n] if acc is None else acc + x[n]
    return acc


def _suma_abs(x, nombres):
    acc = None
    for n in nombres:
        v = np.abs(x[n])
        acc = v if acc is None else acc + v
    return acc


def residuo_identidad(i: Identidad, previo: dict, x: dict):
    """Devuelve (residuo, escala) con la forma de las celdas que verifica la identidad."""
    if i.tipo == "stock_flujo":
        res = x[i.stock] - previo[i.stock]
        escala = np.abs(x[i.stock]) + np.abs(previo[i.stock])
        if i.entradas:
            res = res - _suma(x, i.entradas)
            escala = escala + _suma_abs(x, i.entradas)
        if i.salidas:
            res = res + _suma(x, i.salidas)
            escala = escala + _suma_abs(x, i.salidas)
        return res, escala
    if i.tipo == "conservacion_global":
        izq = mat.suma_filas(_suma(x, i.izquierda))
        der = mat.suma_filas(_suma(x, i.derecha))
        escala = mat.suma_filas(_suma_abs(x, i.izquierda)) + mat.suma_filas(_suma_abs(x, i.derecha))
        return izq - der, escala
    if i.tipo == "stock_global_constante":
        a = mat.suma_filas(x[i.stock])
        b = mat.suma_filas(previo[i.stock])
        return a - b, np.abs(a) + np.abs(b)
    if i.tipo == "desigualdad":
        # residuo positivo = violación
        return np.maximum(x[i.menor] - x[i.mayor], 0.0), np.abs(x[i.menor]) + np.abs(x[i.mayor])
    raise ValueError(i.tipo)


def verificar_paso(ont: Ontologia, paso: int, previo: dict | None, x: dict, rtol: float) -> list[Fallo]:
    fallos: list[Fallo] = []
    if previo is not None:
        for i in ont.identidades:
            res, escala = residuo_identidad(i, previo, x)
            tol = rtol * escala + 1e-300
            if i.tipo == "desigualdad":
                malo = ~(res <= tol)
            else:
                malo = ~(np.abs(res) <= tol)
            n = int(np.count_nonzero(malo))
            if n:
                rel = np.abs(res) / np.maximum(escala, 1e-300)
                fallos.append(Fallo(paso, "identidad", i.nombre, n, float(np.nanmax(np.where(malo, rel, 0.0)))))
    for v in ont.variables:
        a = x[v.nombre]
        lo, hi = v.rango
        malo = ~((a >= lo) & (a <= hi))
        n = int(np.count_nonzero(malo))
        if n:
            peor = a[malo]
            fallos.append(Fallo(paso, "rango", v.nombre, n, float(peor.flat[0])))
    return fallos
