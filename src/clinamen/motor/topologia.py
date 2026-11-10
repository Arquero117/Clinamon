"""Bloque G (meso) mínimo: grafo fijo de entidades (rejilla o lista de aristas).

Todas las agregaciones arista -> entidad y vecino -> entidad se hacen en orden fijo y explícito
(listas de incidencia rellenadas hasta el grado máximo), sin multiplicaciones matriciales: el
resultado de una partícula no depende del tamaño del lote (determinismo bit a bit).
"""
from __future__ import annotations

import numpy as np

from ..ontologia.esquema import Topologia


class Rejilla:
    """Grafo fijo de entidades: rejilla filas × columnas o lista explícita de aristas."""

    def __init__(self, topo: Topologia):
        if topo.tipo == "rejilla":
            F, C = topo.filas, topo.columnas
            self.E = F * C
            a, b = [], []
            for r in range(F):
                for c in range(C):
                    e = r * C + c
                    if c + 1 < C:
                        a.append(e); b.append(e + 1)
                    if r + 1 < F:
                        a.append(e); b.append(e + C)
        else:
            self.E = topo.entidades
            a = [int(u) for u, _ in topo.aristas]
            b = [int(v) for _, v in topo.aristas]
        self.a = np.array(a, dtype=np.int64)
        self.b = np.array(b, dtype=np.int64)
        self.A = len(a)
        grados = np.bincount(np.concatenate([self.a, self.b]), minlength=self.E) if self.A else np.zeros(self.E, int)
        G = max(1, int(grados.max()) if self.E else 1)
        self.vecinos = np.full((self.E, G), self.E, dtype=np.int64)    # relleno -> fila de ceros
        self.incidencia = np.full((self.E, G), self.A, dtype=np.int64)  # relleno -> arista nula
        self.rol = np.zeros((self.E, G), dtype=np.int8)                 # +1 extremo a, -1 extremo b
        n = np.zeros(self.E, dtype=np.int64)
        for k in range(self.A):
            for e, otro, rol in ((self.a[k], self.b[k], 1), (self.b[k], self.a[k], -1)):
                j = n[e]
                self.vecinos[e, j] = otro
                self.incidencia[e, j] = k
                self.rol[e, j] = rol
                n[e] += 1
        self.grado = np.maximum(n, 1).astype(np.float64)[:, None]   # aisladas: media de vecinos = 0
        self.G = G
        # índices sobre la pila [val_a; val_b; 0]: extremo a -> k, extremo b -> A + k, relleno -> 2A
        self._idx_pila = [np.where(self.rol[:, j] == 1, self.incidencia[:, j],
                                   np.where(self.rol[:, j] == -1, self.A + self.incidencia[:, j], 2 * self.A))
                          for j in range(G)]

    # -------------------------------------------------------------- vecinos
    def extremos(self, x):
        """Valores en los extremos a y b de cada arista: dos arrays (A, B)."""
        return x[self.a], x[self.b]

    def suma_vecinos(self, x):
        ext = np.concatenate([x, np.zeros((1, x.shape[1]), dtype=x.dtype)], axis=0)
        acc = ext[self.vecinos[:, 0]]
        for j in range(1, self.G):
            acc = acc + ext[self.vecinos[:, j]]
        return acc

    def media_vecinos(self, x):
        return self.suma_vecinos(x) / self.grado

    def max_vecinos(self, x):
        ext = np.concatenate([x, np.full((1, x.shape[1]), -np.inf, dtype=x.dtype)], axis=0)
        acc = ext[self.vecinos[:, 0]]
        for j in range(1, self.G):
            acc = np.maximum(acc, ext[self.vecinos[:, j]])
        return acc

    # -------------------------------------------------------------- aristas -> entidades
    def reunir(self, val_a, val_b):
        """Σ sobre aristas incidentes del valor del extremo que corresponde a cada entidad.

        val_a, val_b: (A, B), valor que recibe el extremo a y el extremo b de cada arista.
        Devuelve (E, B).
        """
        pila = np.concatenate([val_a, val_b, np.zeros((1, val_a.shape[1]), dtype=np.float64)], axis=0)
        acc = pila[self._idx_pila[0]]
        for j in range(1, self.G):
            acc = acc + pila[self._idx_pila[j]]
        return acc

    def flujo_a_entidades(self, f):
        """f > 0 va de a a b. Devuelve (salidas, entradas) por entidad, ambas >= 0."""
        pos = np.maximum(f, 0.0)
        neg = np.maximum(-f, 0.0)
        return self.reunir(pos, neg), self.reunir(neg, pos)
