"""P7–P8: asimilación (filtro de partículas, sucesos condicionados, posterior) y experimento sintético."""
import numpy as np

from clinamen.asimilacion.filtro import (Prior, condiciones_de, filtro_particulas, observar,
                                         posterior_adaptativa)
from clinamen.motor.motor import ConfigSimulacion, Simulacion
from clinamen.mundos import obtener_modelo
from clinamen.validacion.sintetico import (ConfigExperimento, benjamini_hochberg, candidatos_f1,
                                           experimento, mundo_verdadero, resumir)

M = obtener_modelo("sintetico_f1")
CFG = ConfigExperimento(T_obs=15, H=3, M=24, K=48, etapas=2, S=40, R=10, R_verdad=400,
                        candidatos=candidatos_f1(15))


def test_condicionamiento_reproduce_la_cronica():
    theta, datos, _ = mundo_verdadero(M, CFG, 3)
    sim = Simulacion(M, ConfigSimulacion(particulas=50, anios=0, semilla=8))
    for y in datos:
        sim.campo.log_peso_condiciones[:] = 0.0
        sim.campo.condicionar(condiciones_de(M, y, 50))
        sim.paso()
        assert np.all(sim.x["gobernante_murio"] == y["cronica_sucesiones"][:, None])
        assert np.all(np.isfinite(sim.campo.log_peso_condiciones))
        assert np.all(sim.campo.log_peso_condiciones <= 0.0)


def test_verosimilitud_favorece_theta_verdadero():
    """La verosimilitud del filtro es mayor en θ cerca del verdadero que lejos (sigma: 0.15 frente a 0.35)."""
    sim = Simulacion(M, ConfigSimulacion(particulas=1, anios=0, semilla=5, particula0=10_000_000,
                                         parametros={"sf_beta": 0.0, "sf_sigma": 0.35}))
    rng = np.random.default_rng(1)
    datos = []
    for _ in range(40):
        sim.paso()
        datos.append({k: v[:, 0] for k, v in observar(M, sim.x, sim.p.como_dict(), rng).items()})
    f = filtro_particulas(M, {"sf_beta": np.zeros(8), "sf_sigma": np.repeat([0.15, 0.35], 4)}, 128, datos, 7)
    assert f.log_verosimilitud[4:].mean() > f.log_verosimilitud[:4].mean()


def test_posterior_y_muestras_conjuntas():
    theta, datos, _ = mundo_verdadero(M, CFG, 4)
    prior = Prior.desde_ontologia(M, ["sf_beta", "sf_sigma"])
    post = posterior_adaptativa(M, prior, datos, 4, M=24, K=48, etapas=2)
    assert post.theta.shape == (48, 2) and post.ess >= 1
    th, est = post.muestras_conjuntas(10, np.random.default_rng(0))
    assert th.shape == (10, 2) and est["capacidad"].shape == (6, 10)
    assert np.all(prior.log_densidad(th) > -np.inf)


def test_experimento_pequeno():
    r = experimento(5, CFG)
    c = r["candidatos"]
    assert len(c) == 12
    for i in (3, 4, 5, 9, 10, 11):          # nulos por construcción: efecto verdadero ~ 0
        assert abs(c[i]["efecto_verdadero"]) < 4 * c[i]["error_tipico_verdad"] + 1e-9
    assert all(x["lambda"] - 2 * x["error_tipico_lambda"] <= 1 for x in c)
    s = resumir([r])
    assert 0 <= s["fdr"] <= 1


def test_benjamini_hochberg():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    assert benjamini_hochberg(p, 0.05).sum() == 2
    assert benjamini_hochberg(np.array([0.5, 0.9]), 0.05).sum() == 0
