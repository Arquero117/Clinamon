"""P6: mundo sintético F1 (fichas exactas, identidades, nulos por desconexión)."""
import numpy as np

from clinamen.gemelos.intervencion import PODSuceso
from clinamen.motor.motor import ConfigSimulacion, simular
from clinamen.mundos import obtener_modelo
from test_fichas_mecanismo import CampoRastreado, EstadoRastreado, ParametrosRastreados
from clinamen.motor.motor import Contexto


def test_fichas_exactas_sintetico():
    m = obtener_modelo("sintetico_f1")
    r = simular(m, ConfigSimulacion(particulas=3, anios=1, semilla=2, registrar_estados=True))
    for mec in m.mecanismos:
        campo = CampoRastreado(m.ontologia, 2, np.arange(3), m.tamanos)
        campo.comenzar_paso(4)
        x = EstadoRastreado({k: v.copy() for k, v in r.estados[0].items()})
        p = ParametrosRastreados(m.parametros_nominales)
        mec.paso(Contexto(x=x, p=p, azar=campo, topo=m.topo, t=4, E=m.E, B=3))
        f = mec.ficha
        assert set(f.lee) == x.leidas and set(f.escribe) == x.escritas, f.nombre
        assert set(f.parametros) == p.usados and set(f.fuentes) == campo.usadas, f.nombre


def test_identidades_y_regimenes():
    m = obtener_modelo("sintetico_f1")
    r = simular(m, ConfigSimulacion(particulas=500, anios=100, semilla=5))
    assert r.fallos == []
    c0 = r.observables["capacidad_0"]
    cambios = (np.diff(np.sign(c0), axis=0) != 0).sum(axis=0).mean()
    assert 1 < cambios < 15          # metaestable: unos pocos cambios de régimen por siglo


def test_pod_en_componente_desconectada_es_nulo_en_ley():
    """Un POD en la entidad 4 no puede afectar a la entidad 0 (otra componente): la ley de capacidad_0 no cambia."""
    m = obtener_modelo("sintetico_f1")
    r = simular(m, ConfigSimulacion(particulas=4000, anios=30, semilla=6, gemelos=True,
                                    pods=(PODSuceso("muerte_gobernante", "muere", 4, 5),)))
    N = 4000
    c = r.observables["capacidad_0"][-1]
    dif = c[N:] - c[:N]
    assert abs(dif.mean()) < 3 * dif.std() / np.sqrt(N) + 1e-12
    r0 = simular(m, ConfigSimulacion(particulas=4000, anios=30, semilla=6, gemelos=True,
                                     pods=(PODSuceso("muerte_gobernante", "muere", 0, 5),)))
    d0 = r0.observables["capacidad_0"][10]
    assert (d0[N:] - d0[:N]).mean() < -0.1         # a 5 años el choque de sucesión en 0 sí la debilita
    d29 = r0.observables["capacidad_0"][-1]
    assert abs((d29[N:] - d29[:N]).mean()) < 0.1    # y se absorbe en un par de décadas (efecto transitorio)
