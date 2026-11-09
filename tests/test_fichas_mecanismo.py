"""§14.2: cada ficha declara exactamente lo que su mecanismo lee, escribe, parametriza y sortea.

Se ejecuta un paso con el estado, los parámetros y el campo de azar envueltos en rastreadores.
"""
import re
from pathlib import Path

import numpy as np
import pytest

from clinamen.azar.campo import PASO_INICIAL, CampoAzar
from clinamen.motor.motor import Contexto, Parametros

import clinamen.mundos.banco_f0.mecanismos as mec_mod


class EstadoRastreado(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.leidas, self.escritas = set(), set()

    def __getitem__(self, k):
        self.leidas.add(k)
        return super().__getitem__(k)

    def __setitem__(self, k, v):
        self.escritas.add(k)
        super().__setitem__(k, v)


class ParametrosRastreados(Parametros):
    def __init__(self, v):
        super().__init__(v)
        object.__setattr__(self, "usados", set())

    def __getattr__(self, n):
        if n == "usados":
            return object.__getattribute__(self, "usados")
        self.usados.add(n)
        return super().__getattr__(n)


class CampoRastreado(CampoAzar):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.usadas = set()

    def _comprobar(self, fuente):
        self.usadas.add(fuente)
        super()._comprobar(fuente)


def _estado_tras_un_paso(modelo):
    from clinamen.motor.motor import ConfigSimulacion, simular
    r = simular(modelo, ConfigSimulacion(particulas=3, anios=1, semilla=11, registrar_estados=True))
    return r.estados[0]


def _contexto(modelo, estado, t):
    N = 3
    campo = CampoRastreado(modelo.ontologia, 11, np.arange(N), modelo.tamanos)
    campo.comenzar_paso(t)
    x = EstadoRastreado({k: v.copy() for k, v in estado.items()})
    p = ParametrosRastreados(modelo.parametros_nominales)
    return Contexto(x=x, p=p, azar=campo, topo=modelo.topo, t=t, E=modelo.E, B=N), x, p, campo


def test_fichas_exactas(modelo):
    estado = _estado_tras_un_paso(modelo)
    errores = []
    for m in modelo.mecanismos:
        ctx, x, p, campo = _contexto(modelo, estado, 5)
        m.paso(ctx)
        f = m.ficha
        leidas_puras = x.leidas
        if set(f.escribe) != x.escritas:
            errores.append(f"{f.nombre}: escribe declarado {sorted(f.escribe)} != real {sorted(x.escritas)}")
        if set(f.lee) != leidas_puras:
            errores.append(f"{f.nombre}: lee declarado {sorted(f.lee)} != real {sorted(leidas_puras)}")
        if set(f.parametros) != p.usados:
            errores.append(f"{f.nombre}: parámetros declarados {sorted(f.parametros)} != reales {sorted(p.usados)}")
        if set(f.fuentes) != campo.usadas:
            errores.append(f"{f.nombre}: fuentes declaradas {sorted(f.fuentes)} != reales {sorted(campo.usadas)}")
    assert not errores, "\n".join(errores)


def test_ficha_estado_inicial_exacta(modelo):
    ctx, x, p, campo = _contexto(modelo, {}, PASO_INICIAL)
    x.leidas.clear()
    modelo.inicial(ctx)
    f = modelo.ontologia.estado_inicial
    assert set(f.escribe) == x.escritas
    assert set(f.parametros) == p.usados
    assert set(f.fuentes) == campo.usadas


PROHIBIDAS = re.compile(r"np\.(exp|log|log1p|expm1|power|tanh|sinh|cosh|sin|cos|sum|mean|prod|cumsum|dot|matmul|einsum)\b|@|scipy|\*\*")


def test_mecanismos_sin_matematica_directa():
    """Trascendentes y reducciones solo vía clinamen.numerica.mat (determinismo por posición y orden)."""
    fuente = Path(mec_mod.__file__).read_text(encoding="utf-8")
    codigo = "\n".join(l.split("#")[0] for l in fuente.splitlines() if not l.strip().startswith(("\"", "'")))
    codigo = re.sub(r'""".*?"""', "", codigo, flags=re.S)
    malas = sorted(set(PROHIBIDAS.findall(codigo)))
    assert not malas, f"uso directo prohibido en mecanismos: {malas}"
