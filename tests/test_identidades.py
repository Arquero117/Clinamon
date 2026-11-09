"""A3: identidades contables en el 100 % de los pasos, y comprobación de que el verificador no es vacuo."""
import numpy as np
import pytest

from clinamen.motor.motor import TOLERANCIA_F64, ConfigSimulacion, simular
from clinamen.motor.verificacion import verificar_paso


@pytest.fixture(scope="module")
def corrida(modelo):
    return simular(modelo, ConfigSimulacion(particulas=12, anios=150, semilla=3, al_fallar="registrar",
                                            registrar_estados=True))


def test_cero_fallos_en_todos_los_pasos(corrida):
    assert corrida.pasos_verificados == 150
    assert corrida.fallos == [], [str(f) for f in corrida.fallos[:5]]


def _par(corrida, t):
    return corrida.estados[t - 1], corrida.estados[t]


def _terminos(i):
    if i.tipo == "stock_flujo":
        return [i.stock, *i.entradas, *i.salidas]
    if i.tipo == "conservacion_global":
        return [*i.izquierda, *i.derecha]
    if i.tipo == "stock_global_constante":
        return [i.stock]
    return [i.mayor]


@pytest.mark.parametrize("nombre", [
    "poblacion", "migracion_global", "grano", "comercio_global", "tesoro", "deuda", "ejercito", "elites",
    "territorio", "territorio_global", "transferencias_territorio", "ejercito_en_poblacion",
    "elites_en_poblacion", "bajas_en_muertes_guerra"])
def test_cada_identidad_detecta_corrupcion(modelo, corrida, nombre):
    """Perturbar cualquier término de una identidad debe hacerla fallar (no es tautológica)."""
    ident = next(i for i in modelo.ontologia.identidades if i.nombre == nombre)
    previo, actual = _par(corrida, 100)
    assert not [f for f in verificar_paso(modelo.ontologia, 100, previo, actual, TOLERANCIA_F64) if f.nombre == nombre]
    for termino in _terminos(ident):
        x = {k: v.copy() for k, v in actual.items()}
        if ident.tipo == "desigualdad":
            x[ident.menor] = x[ident.mayor] * 1.001 + 1.0
        else:
            x[termino] = x[termino] * (1 + 1e-6) + 1.0
        fallos = [f for f in verificar_paso(modelo.ontologia, 100, previo, x, TOLERANCIA_F64)
                  if f.nombre == nombre and f.tipo == "identidad"]
        assert fallos, f"la identidad {nombre} no detecta la corrupción de {termino}"


def test_rango_detecta_valores_fuera(modelo, corrida):
    x = {k: v.copy() for k, v in corrida.estados[50].items()}
    x["legitimidad"][0, 0] = 1.5
    x["poblacion"][1, 1] = np.nan
    fallos = {f.nombre for f in verificar_paso(modelo.ontologia, 50, None, x, TOLERANCIA_F64) if f.tipo == "rango"}
    assert fallos == {"legitimidad", "poblacion"}


def test_identidades_con_gemelos_y_pod(modelo):
    from clinamen.gemelos.intervencion import PODSuceso
    r = simular(modelo, ConfigSimulacion(particulas=8, anios=60, semilla=5, gemelos=True,
                                         pods=(PODSuceso("muerte_gobernante", "muere", 4, 10),)))
    assert r.fallos == []
