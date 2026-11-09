"""M7: gemelos, POD nulo, coste en nats, horizonte de identidad y acoplamientos."""
import math

import numpy as np
import pytest

from clinamen.azar.campo import CampoAzar, InadmisibleError, SorteoRepetidoError
from clinamen.gemelos.intervencion import PODInclinacion, PODNulo, PODSuceso
from clinamen.motor.motor import ConfigSimulacion, simular

N = 24
T = 50
T0 = 12


def _gemelos(modelo, pod, acoplamiento="fisico", n=N, anios=T, semilla=77):
    return simular(modelo, ConfigSimulacion(particulas=n, anios=anios, semilla=semilla, gemelos=True,
                                            pods=(pod,), acoplamiento=acoplamiento, registrar_estados=True))


def _brazos_identicos(r, desde=0, hasta=None):
    n = r.N
    for est in r.estados[desde:hasta]:
        for k, v in est.items():
            if not np.array_equal(v[:, :n], v[:, n:]):
                return False
    return True


NULOS = {
    "nulo": PODNulo(),
    "inclinacion_cero": PODInclinacion("clima_interno", indice=3, paso=T0, desplazamiento=0.0),
    "suceso_intervalo_total": PODSuceso("batalla", "gana_b", indice=0, paso=T0),
}


@pytest.mark.parametrize("acoplamiento", ["fisico", "maximo", "independiente"])
@pytest.mark.parametrize("variante", list(NULOS))
def test_pod_nulo_efecto_exactamente_cero(modelo, variante, acoplamiento):
    pod = NULOS[variante]
    if variante == "suceso_intervalo_total":
        # suceso «gana b» en una arista donde no hay guerra: intervalo (0,1), coste 0.
        # Se usa una semilla y arista donde no estalla guerra en t0 en ninguna partícula.
        r0 = simular(modelo, ConfigSimulacion(particulas=N, anios=T0 + 1, semilla=77, registrar_estados=True))
        sin_guerra = None
        for k in range(modelo.topo.A):
            a, b = modelo.topo.a[k], modelo.topo.b[k]
            g = r0.estados[T0]["guerras_libradas"]
            # guerra en la arista k <=> participa a y b; se busca una arista sin guerras en ningún extremo
            if not g[a].any() and not g[b].any():
                sin_guerra = k
                break
        assert sin_guerra is not None
        pod = PODSuceso("batalla", "gana_b", indice=int(sin_guerra), paso=T0)
    r = _gemelos(modelo, pod, acoplamiento)
    assert _brazos_identicos(r), "un POD nulo debe dar efecto exactamente cero, bit a bit"
    for k, v in r.observables.items():
        assert np.array_equal(v[:, :N], v[:, N:]), k
    assert np.all(r.coste == 0.0)
    assert np.all(r.t_div == -1)


def _q_muerte(modelo, estado, e, n):
    p = modelo.parametros_nominales
    edad = estado["gobernante_edad"][e, :n] + 1.0
    h = p["gob_gompertz_a"] * estado["gobernante_fragilidad"][e, :n] * np.exp(p["gob_gompertz_b"] * (edad - 20.0))
    return np.minimum(np.maximum(1.0 - np.exp(-h), p["gob_q_min"]), p["gob_q_max"])


@pytest.mark.parametrize("evento", ["muere", "sobrevive"])
def test_pod_suceso_fuerza_el_suceso_y_coste_exacto(modelo, evento):
    e = 4
    r = _gemelos(modelo, PODSuceso("muerte_gobernante", evento, indice=e, paso=T0))
    murio = r.estados[T0]["gobernante_murio"][e]
    objetivo = 1.0 if evento == "muere" else 0.0
    assert np.all(murio[N:] == objetivo), "el POD debe forzar el suceso en el 100 % de las partículas"
    q = _q_muerte(modelo, r.estados[T0 - 1], e, N)
    esperado = -np.log(q) if evento == "muere" else -np.log(1.0 - q)
    np.testing.assert_allclose(r.coste, esperado, rtol=1e-12)
    # antes de t0, brazos idénticos
    assert _brazos_identicos(r, 0, T0)
    # divergencia exactamente en t0 donde el suceso no había ocurrido ya en el brazo base; nunca donde sí
    ya = murio[:N] == objetivo
    assert np.all(r.t_div[~ya] == T0)
    assert np.all(r.t_div[ya] == -1)
    assert (~ya).any()


def test_inclinacion_coste_cuadratico(modelo):
    v = 1.7
    r = _gemelos(modelo, PODInclinacion("clima_interno", indice=9, paso=T0, desplazamiento=v))
    np.testing.assert_array_equal(r.coste, np.full(N, 0.5 * v * v))
    assert np.all(r.t_div == T0)
    dif = r.estados[T0]["anomalia_clima"][9, N:] - r.estados[T0]["anomalia_clima"][9, :N]
    np.testing.assert_allclose(dif, modelo.parametros_nominales["clima_sigma"] * v, rtol=1e-9)


def test_costes_suman(modelo):
    """Aditividad del coste (§5.2): dos PODs en sorteos distintos suman sus costes."""
    a = PODInclinacion("clima_interno", indice=1, paso=T0, desplazamiento=0.8)
    b = PODInclinacion("vital", indice=2, paso=T0 + 1, desplazamiento=-0.5, ranura=1)
    r = simular(modelo, ConfigSimulacion(particulas=4, anios=T0 + 3, semilla=1, gemelos=True, pods=(a, b)))
    np.testing.assert_allclose(r.coste, 0.5 * 0.8 ** 2 + 0.5 * 0.5 ** 2, rtol=1e-15)


# --------------------------------------------------------------------- horizonte de identidad
def _campo(modelo, acoplamiento="fisico"):
    return CampoAzar(modelo.ontologia, 5, np.arange(6), modelo.tamanos, gemelos=True, acoplamiento=acoplamiento)


def _compartida(campo, fuente, t):
    campo.comenzar_paso(t)
    f = campo.fuentes[fuente]
    ev = {e.nombre: (0.0, 1.0) for e in f.eventos}
    u = campo.uniformes(fuente, eventos=ev)[0]
    return np.array_equal(u[:, :6], u[:, 6:])


@pytest.mark.parametrize("fuente,retardo", [("clima_interno", 1), ("batalla", 1), ("invencion", 1),
                                            ("muerte_gobernante", 2), ("epidemia", 20), ("volcan", math.inf)])
def test_horizonte_de_identidad_fisico(modelo, fuente, retardo):
    c = _campo(modelo)
    td = 10
    c.comenzar_paso(td)
    c.registrar_divergencia(np.ones(6, bool))
    assert _compartida(c, fuente, td)                      # el paso de divergencia sigue compartido
    if math.isinf(retardo):
        assert _compartida(c, fuente, td + 500)
    else:
        assert _compartida(c, fuente, td + retardo - 1)
        assert not _compartida(c, fuente, td + retardo)
        assert not _compartida(c, fuente, td + retardo + 7)


def test_sin_divergencia_nunca_se_desacopla(modelo):
    c = _campo(modelo, "independiente")
    for t in (0, 5, 100):
        assert _compartida(c, "clima_interno", t)


def test_acoplamientos_extremos(modelo):
    cmax = _campo(modelo, "maximo")
    cind = _campo(modelo, "independiente")
    for c in (cmax, cind):
        c.comenzar_paso(3)
        c.registrar_divergencia(np.ones(6, bool))
    assert _compartida(cmax, "clima_interno", 50)
    assert not _compartida(cind, "epidemia", 4)
    assert not _compartida(cind, "muerte_gobernante", 4)


def test_divergencia_parcial_por_particula(modelo):
    c = _campo(modelo)
    c.comenzar_paso(10)
    c.registrar_divergencia(np.array([True, False, True, False, False, False]))
    c.comenzar_paso(11)
    u = c.uniformes("clima_interno", eventos={"innovacion_adversa": (0, 0.1), "innovacion_no_adversa": (0.1, 1)})[0]
    distinta = np.any(u[:, :6] != u[:, 6:], axis=0)
    assert distinta.tolist() == [True, False, True, False, False, False]


# --------------------------------------------------------------------- errores de uso
def test_sorteo_repetido_prohibido(modelo):
    c = _campo(modelo)
    c.comenzar_paso(1)
    c.uniformes("sucesion")
    with pytest.raises(SorteoRepetidoError):
        c.uniformes("sucesion")


def test_sucesos_deben_coincidir_con_los_declarados(modelo):
    c = _campo(modelo)
    c.comenzar_paso(1)
    with pytest.raises(ValueError, match="declarados"):
        c.uniformes("muerte_gobernante", eventos={"muere": (0, 0.1)})


def test_pod_fuera_de_catalogo(modelo):
    with pytest.raises(ValueError, match="no declara"):
        CampoAzar(modelo.ontologia, 1, np.arange(2), modelo.tamanos, gemelos=True,
                  pods=[PODSuceso("muerte_gobernante", "resucita", 0, 1)])
    with pytest.raises(ValueError, match="inclinación"):
        CampoAzar(modelo.ontologia, 1, np.arange(2), modelo.tamanos, gemelos=True,
                  pods=[PODInclinacion("guerra", 0, 1, 1.0)])
    with pytest.raises(ValueError, match="fuera del dominio"):
        CampoAzar(modelo.ontologia, 1, np.arange(2), modelo.tamanos, gemelos=True,
                  pods=[PODSuceso("muerte_gobernante", "muere", 30, 1)])


def test_pod_de_coste_infinito_inadmisible(modelo):
    c = CampoAzar(modelo.ontologia, 1, np.arange(3), modelo.tamanos, gemelos=True,
                  pods=[PODSuceso("muerte_gobernante", "muere", 0, 2)])
    c.comenzar_paso(2)
    with pytest.raises(InadmisibleError):
        c.uniformes("muerte_gobernante", eventos={"muere": (0.0, 0.0), "sobrevive": (0.0, 1.0)})


def test_pod_fuera_de_la_ventana_no_cuesta(modelo):
    """Un POD posterior al horizonte simulado no se aplica: coste 0 y brazos idénticos."""
    r = simular(modelo, ConfigSimulacion(particulas=2, anios=3, semilla=1, gemelos=True,
                                         pods=(PODSuceso("muerte_gobernante", "muere", 0, 10),)))
    assert np.all(r.coste == 0.0) and np.all(r.t_div == -1)


# --------------------------------------------------------------------- marginales y acoplamiento
@pytest.mark.lento
def test_marginal_del_brazo_pod_no_depende_del_acoplamiento(modelo):
    """Prop. 1: los funcionales de las marginales no dependen del acoplamiento.

    Se comparan las leyes del brazo con POD bajo los acoplamientos físico e independiente con semillas
    distintas (muestras independientes): la diferencia debe ser compatible con el error de Monte Carlo.
    """
    from scipy.stats import ks_2samp
    pod = PODSuceso("muerte_gobernante", "muere", indice=7, paso=3)
    n = 300
    res = {}
    for acop, semilla in (("fisico", 101), ("independiente", 202), ("maximo", 303)):
        r = simular(modelo, ConfigSimulacion(particulas=n, anios=25, semilla=semilla, gemelos=True,
                                             pods=(pod,), acoplamiento=acop))
        res[acop] = r
    for obs in ("poblacion_total", "legitimidad_media", "tecnologia_media"):
        a = res["fisico"].observables[obs][24, n:]
        for otro in ("independiente", "maximo"):
            b = res[otro].observables[obs][24, n:]
            assert ks_2samp(a, b).pvalue > 1e-3, (obs, otro)
