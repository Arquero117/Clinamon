"""Puerta F0: determinismo bit a bit por semilla e invariancias de bloque."""
import numpy as np

from clinamen.gemelos.intervencion import PODNulo, PODSuceso
from clinamen.motor.motor import ConfigSimulacion, simular
from clinamen.numerica import mat


def _iguales(a: dict, b: dict):
    return set(a) == set(b) and all(np.array_equal(a[k], b[k]) for k in a)


def test_autocomprobacion_posicional():
    mat.verificar_determinismo_posicional(forzar=True)


def test_repeticion_identica(modelo):
    cfg = ConfigSimulacion(particulas=6, anios=80, semilla=42, registrar_estados=True)
    a = simular(modelo, cfg)
    b = simular(modelo, cfg)
    assert _iguales(a.observables, b.observables)
    assert all(_iguales(x, y) for x, y in zip(a.estados, b.estados))


def test_semilla_distinta_da_otra_historia(modelo):
    a = simular(modelo, ConfigSimulacion(particulas=4, anios=20, semilla=1))
    b = simular(modelo, ConfigSimulacion(particulas=4, anios=20, semilla=2))
    assert not np.array_equal(a.observables["poblacion_total"], b.observables["poblacion_total"])


def test_particula_no_depende_del_bloque(modelo):
    """La trayectoria de la partícula p depende solo de (semilla, p): no del tamaño ni del inicio del bloque."""
    grande = simular(modelo, ConfigSimulacion(particulas=11, anios=60, semilla=9, registrar_estados=True))
    trozo = simular(modelo, ConfigSimulacion(particulas=4, anios=60, semilla=9, particula0=5, registrar_estados=True))
    for k in grande.observables:
        assert np.array_equal(grande.observables[k][:, 5:9], trozo.observables[k])
    for eg, et in zip(grande.estados, trozo.estados):
        for k in eg:
            assert np.array_equal(eg[k][:, 5:9], et[k])


def test_brazo_base_igual_a_ensemble(modelo):
    """El brazo sin POD de los gemelos es bit a bit el ensemble sin gemelos."""
    N = 7
    ens = simular(modelo, ConfigSimulacion(particulas=N, anios=70, semilla=13))
    gem = simular(modelo, ConfigSimulacion(particulas=N, anios=70, semilla=13, gemelos=True,
                                           pods=(PODSuceso("muerte_gobernante", "muere", 2, 15),)))
    for k in ens.observables:
        assert np.array_equal(ens.observables[k], gem.observables[k][:, :N])
    # y el POD sí cambia el otro brazo
    assert not np.array_equal(gem.observables["sucesiones"][:, :N], gem.observables["sucesiones"][:, N:])


def test_motor_philox_numpy_y_numba_identicos(modelo):
    a = simular(modelo, ConfigSimulacion(particulas=3, anios=15, semilla=21, motor_philox="numpy"))
    b = simular(modelo, ConfigSimulacion(particulas=3, anios=15, semilla=21, motor_philox="auto"))
    assert _iguales(a.observables, b.observables)
