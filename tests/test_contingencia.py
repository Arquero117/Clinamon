"""M8 y banco canónico: identidades exactas en las cadenas y estimadores a partir de trayectorias (§6, §8, §13.2)."""
import numpy as np
import pytest

from clinamen.contingencia import estimadores as es
from clinamen.contingencia.banco import pods_designados
from clinamen.contingencia.juguetes import JUGUETES, doble_pozo_gaussiano, lento_rapido, lento_rapido_homogeneizado


@pytest.fixture(scope="module")
def cadenas():
    return {k: f() for k, f in JUGUETES.items()}


@pytest.mark.parametrize("nombre", list(JUGUETES))
def test_teoremas_exactos(cadenas, nombre):
    c = cadenas[nombre]
    rho, ini = c.presupuesto()
    assert rho.sum() == pytest.approx(ini, rel=1e-9)               # Teorema 2
    k, k0 = c.kappa()
    assert k.sum() + k0 == pytest.approx(-np.log(c.probabilidad_B()), rel=1e-9)   # Teorema 3
    assert np.all(k >= -1e-12)


@pytest.mark.parametrize("nombre", list(JUGUETES))
def test_cota_de_informacion_exacta(cadenas, nombre):
    """Teorema 1: 0 ≤ e ≤ c para el POD designado y para el estado completo como observable."""
    c = cadenas[nombre]
    pd = pods_designados(nombre, c)
    p = np.zeros(c.n); p[pd["x0"]] = 1.0
    r = c.pod_suceso(pd["t0"], pd["A"], etiquetas=pd["etiquetas"], p_inicial=p)
    completo = c.pod_suceso(pd["t0"], pd["A"], etiquetas=np.arange(c.n), p_inicial=p)
    assert 0 <= r.rastro <= completo.rastro + 1e-12 <= completo.coste + 1e-9
    assert 0 <= r.eficiencia <= 1


def test_simulacion_reproducible_y_coherente(cadenas):
    c = cadenas["doble_pozo_gaussiano"]
    a = c.simular(5000, 3)
    assert np.array_equal(a, c.simular(5000, 3))
    assert abs(c.B[a[-1]].mean() - c.probabilidad_B()) < 4 * np.sqrt(0.25 / 5000)


def test_gemelos_de_cadena_siguen_la_ley_Q(cadenas):
    c = cadenas["urna_polya"]
    pd = pods_designados("urna_polya", c)
    base, pod, coste = c.simular_gemelos(20000, 5, pd["t0"], pd["A"], x0=pd["x0"])
    assert np.all(pod[1] == 2) and np.allclose(coste, np.log(2))
    p = np.zeros(c.n); p[pd["x0"]] = 1.0
    ex = c.pod_suceso(pd["t0"], pd["A"], etiquetas=np.arange(c.n), p_inicial=p)
    emp = np.bincount(pod[-1], minlength=c.n) / pod.shape[1]
    assert 0.5 * np.abs(emp - ex.ley_Q).sum() < 0.03


def test_committor_estimado_doble_pozo():
    c = doble_pozo_gaussiano()
    h = c.committor()
    tr = c.simular(20000, 21)
    com = es.Committor.ajustar(c.rasgos[tr], c.B[tr[-1]])
    t = 30
    idx = np.argsort(np.abs(c.rasgos[:, 0] + 0.6))[:15]
    assert np.max(np.abs(com(t, c.rasgos[idx]) - h[t][idx])) < 0.04


def test_estimadores_de_teoremas_insesgados_en_la_urna(cadenas):
    c = cadenas["urna_polya"]
    tr = c.simular(30000, 8)
    R, y = c.rasgos[tr], c.B[tr[-1]]
    a, b, d = slice(0, 10000), slice(10000, 20000), slice(20000, None)
    h1 = es.Committor.ajustar(R[:, a], y[a])
    h2 = es.Committor.ajustar(R[:, b], y[b])
    t2 = es.presupuesto_cruzado(h1.en_trayectorias(R[:, d], y[d]), h2.en_trayectorias(R[:, d], y[d]), y[d], 50)
    assert abs(t2["suma"] - c.presupuesto()[1]) < 0.01
    kp = es.perfil_kappa(h1.en_trayectorias(R[:, d], y[d]), y[d], bootstrap=20)
    assert es.error_L1_relativo(kp["kappa"], c.kappa()[0]) < 0.15


def test_rastro_dv_cota_inferior_coherente():
    rng = np.random.default_rng(0)
    q = rng.normal(0.5, 1, 40000)
    p = rng.normal(0.0, 1, 40000)
    r = es.rastro_dv(q, p)
    assert abs(r["rastro"] - 0.125) < 4 * r["error_tipico"] + 0.01      # KL(N(0.5,1)‖N(0,1)) = 0.125
    nulo = es.rastro_dv(rng.normal(size=20000), rng.normal(size=20000))
    assert nulo["rastro"] < 3 * nulo["error_tipico"]


def test_kramers_escala_con_la_barrera():
    """Ley de Kramers: log E[τ] crece linealmente en 1/σ² con pendiente cercana a 2ΔV = 0.5 (ΔV = 1/4)."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spl
    inv_s2, logtau = [], []
    for sigma in (0.45, 0.5, 0.55, 0.6):
        c = doble_pozo_gaussiano(n=161, sigma=sigma, dt=0.05)
        K = c.K(0)
        x = c.rasgos[:, 0]
        dentro = x < 0
        Kd = K[dentro][:, dentro]
        tau = spl.spsolve(sp.eye(Kd.shape[0]) - Kd, np.ones(Kd.shape[0]))
        i0 = np.argmin(np.abs(x[dentro] + 1.0))
        inv_s2.append(1 / sigma ** 2); logtau.append(np.log(tau[i0] * 0.05))
    pendiente = np.polyfit(inv_s2, logtau, 1)[0]
    assert 0.4 < pendiente < 0.6


def test_lento_rapido_tiende_al_homogeneizado():
    """§3.5: el committor del sistema completo se aproxima al de la cadena homogeneizada de Green-Kubo."""
    c, r = lento_rapido(), lento_rapido_homogeneizado()
    h, hr = c.committor()[0], r.committor()[0]
    hx = h.reshape(-1, 3).mean(axis=1)
    assert np.max(np.abs(hx - hr)) < 0.02


def test_espectro_y_regimenes_desde_trayectorias():
    c = doble_pozo_gaussiano(T=4000)
    _, t_ex = c.espectro(k=3, lag=10)
    tr = c.simular(60, 2)
    micro = np.digitize(c.rasgos[tr, 0], np.linspace(-2.2, 2.2, 31)[1:-1])
    P = es.matriz_transicion(micro, 30, lag=10)
    t_est, _, _ = es.tiempos_implicitos(P, lag=10, k=3)
    assert abs(t_est[0] / t_ex[0] - 1) < 0.2
    reg = es.dos_regimenes(P)
    centros = np.linspace(-2.2, 2.2, 31)[:-1] + 4.4 / 60
    izq, der = reg[centros < -0.5], reg[centros > 0.5]
    assert len(set(izq)) == 1 and len(set(der)) == 1 and izq[0] != der[0]


def test_kappa_concentrado_con_cola_pesada(cadenas):
    """§7.3: con saltos de cola pesada, cada trayectoria hacia B paga casi todo su coste en un solo paso."""
    def concentracion(c):
        h = c.committor()
        tr = c.simular(20000, 4)
        ok = c.B[tr[-1]]
        L = np.log(np.maximum(h[np.arange(c.T + 1)[:, None], tr[:, ok]], 1e-12))
        inc = np.maximum(np.diff(L, axis=0), 0)
        return float(np.mean(inc.max(axis=0) / inc.sum(axis=0)))
    assert concentracion(cadenas["doble_pozo_estable"]) > concentracion(cadenas["doble_pozo_gaussiano"]) + 0.1
