"""P5: varios brazos, estado inicial dado con paso absoluto, reindexado y topología por lista."""
import numpy as np
import pytest

from clinamen.gemelos.intervencion import PODInclinacion, PODNulo, PODSuceso
from clinamen.motor.motor import ConfigSimulacion, Simulacion, simular
from clinamen.ontologia.esquema import Topologia
from clinamen.motor.topologia import Rejilla

N, T = 6, 30
POD = PODSuceso("muerte_gobernante", "muere", 4, 8)


def test_brazo_1_igual_a_gemelos_y_brazo_nulo_igual_a_base(modelo):
    gem = simular(modelo, ConfigSimulacion(particulas=N, anios=T, semilla=3, gemelos=True, pods=(POD,)))
    multi = simular(modelo, ConfigSimulacion(particulas=N, anios=T, semilla=3,
                                             ramas=((POD,), (PODNulo(),), (PODInclinacion("vital", 1, 5, 0.7),))))
    for k, v in gem.observables.items():
        m = multi.observables[k]
        assert np.array_equal(m[:, :2 * N], v), k              # base y brazo 1 idénticos a los gemelos de F0
        assert np.array_equal(m[:, 2 * N:3 * N], m[:, :N]), k   # brazo nulo idéntico al base
    assert np.array_equal(multi.coste_brazos[1], gem.coste)
    assert np.all(multi.coste_brazos[2] == 0) and np.allclose(multi.coste_brazos[3], 0.5 * 0.7 ** 2)
    assert np.all(multi.t_div_brazos[2] == -1) and np.all(multi.t_div_brazos[3] == 5)


def test_continuacion_desde_estado_dado_es_exacta(modelo):
    """El estado (sin flujos) es markoviano completo: continuar desde él reproduce la trayectoria bit a bit."""
    completo = simular(modelo, ConfigSimulacion(particulas=N, anios=T, semilla=9, registrar_estados=True))
    t = 12
    est = {v.nombre: completo.estados[t - 1][v.nombre] for v in modelo.ontologia.variables if v.tipo != "flujo"}
    cont = simular(modelo, ConfigSimulacion(particulas=N, anios=T - t, semilla=9, estado0=est, paso0=t))
    for k, v in completo.observables.items():
        assert np.array_equal(v[t:], cont.observables[k]), k


def test_gemelos_desde_estado_dado(modelo):
    base = simular(modelo, ConfigSimulacion(particulas=N, anios=10, semilla=9))
    est = {v.nombre: base.estado_final[v.nombre] for v in modelo.ontologia.variables if v.tipo != "flujo"}
    r = simular(modelo, ConfigSimulacion(particulas=N, anios=10, semilla=9, estado0=est, paso0=10, gemelos=True,
                                         pods=(PODSuceso("muerte_gobernante", "muere", 2, 10),)))
    assert np.all(r.t_div[r.coste > 0] >= 10)
    assert np.all(r.coste > 0)


def test_parametros_por_particula(modelo):
    v = np.linspace(0.01, 0.03, N)[None, :]
    r = simular(modelo, ConfigSimulacion(particulas=N, anios=5, semilla=1, gemelos=True, pods=(PODNulo(),),
                                         parametros={"vol_p": v}))
    assert np.array_equal(r.observables["poblacion_total"][:, :N], r.observables["poblacion_total"][:, N:])
    with pytest.raises(ValueError, match="forma"):
        simular(modelo, ConfigSimulacion(particulas=N, anios=2, semilla=1, parametros={"vol_p": np.ones((1, 3))}))


def test_reindexar(modelo):
    a = Simulacion(modelo, ConfigSimulacion(particulas=N, anios=0, semilla=4,
                                            parametros={"vol_p": np.linspace(0.01, 0.03, N)[None, :]}))
    b = Simulacion(modelo, ConfigSimulacion(particulas=N, anios=0, semilla=4,
                                            parametros={"vol_p": np.linspace(0.01, 0.03, N)[None, :]}))
    for _ in range(3):
        a.paso(); b.paso()
    b.reindexar(np.arange(N))
    oa, ob = a.paso(), b.paso()
    assert all(np.array_equal(oa[k], ob[k]) for k in oa)
    idx = np.zeros(N, dtype=int)                         # todas las columnas copian la 0
    a.reindexar(idx)
    assert np.all(a.p.vol_p == 0.01)
    o = a.paso()
    assert len(np.unique(o["poblacion_total"])) > 1     # las copias reciben azar independiente


def test_topologia_lista_con_componentes_y_aislados():
    g = Rejilla(Topologia(tipo="lista", entidades=5, aristas=((0, 1), (1, 2), (3, 4))))
    x = np.arange(5, dtype=float)[:, None]
    assert g.suma_vecinos(x)[:, 0].tolist() == [1, 2, 1, 4, 3]
    g2 = Rejilla(Topologia(tipo="lista", entidades=3, aristas=((0, 1),)))
    assert g2.media_vecinos(np.ones((3, 1)))[2, 0] == 0.0
    with pytest.raises(Exception):
        Topologia(tipo="lista", entidades=3, aristas=((0, 3),))
