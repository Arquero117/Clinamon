"""Mecanismos del mundo sintético F1 (sin contenido histórico). Convenciones como en banco_f0."""
from __future__ import annotations

import numpy as np

from ...numerica import mat


def estado_inicial(c):
    x, p = c.x, c.p
    u = c.azar.uniformes("inicial")
    signo = np.where(u[0] < 0.5, -1.0, 1.0)
    x["capacidad"] = signo + p.sf_ini_cap_sd * mat.ndtri(u[1])
    x["poblacion"] = p.sf_ini_pob_min + (p.sf_ini_pob_max - p.sf_ini_pob_min) * u[2]
    x["gobernante_edad"] = p.sf_ini_edad_min + (p.sf_ini_edad_max - p.sf_ini_edad_min) * u[3]
    x["gobernante_capacidad"] = mat.ndtri(u[4])


def gobernante(c):
    x, p = c.x, c.p
    edad = x["gobernante_edad"] + 1.0
    q = mat.acotar(1.0 - mat.exp(-p.sf_gomp_a * mat.exp(p.sf_gomp_b * (edad - 20.0))), p.sf_q_min, p.sf_q_max)
    (u,) = c.azar.uniformes("muerte_gobernante", eventos={"muere": (0.0, q), "sobrevive": (q, 1.0)})
    muere = u < q
    s0, s1 = c.azar.uniformes("sucesion")
    x["gobernante_edad"] = np.where(muere, p.sf_edad_min + p.sf_edad_rango * s0, edad)
    x["gobernante_capacidad"] = np.where(muere, mat.ndtri(s1), x["gobernante_capacidad"])
    x["gobernante_murio"] = muere.astype(np.float64)


def capacidad(c):
    x, p = c.x, c.p
    cap = x["capacidad"]
    (z,) = c.azar.normales("ruido_capacidad")
    deriva = (cap - cap * cap * cap + p.sf_beta + p.sf_acople * (c.topo.media_vecinos(cap) - cap)
              + p.sf_peso_gob * mat.tanh(x["gobernante_capacidad"]))
    nuevo = cap + p.sf_escala * deriva + p.sf_sigma * z - p.sf_choque * x["gobernante_murio"]
    x["capacidad"] = mat.acotar(nuevo, -6.0, 6.0)


def demografia(c):
    x, p = c.x, c.p
    P = x["poblacion"]
    nac = P * p.sf_natalidad * (1.0 + p.sf_sens_cap * mat.tanh(x["capacidad"]))
    mue = P * p.sf_mortalidad
    x["nacimientos"] = nac
    x["muertes"] = mue
    x["poblacion"] = P + nac - mue


MECANISMOS = [gobernante, capacidad, demografia]
