"""F2a P1–P2: ingesta de Seshat y puntuación."""
import numpy as np
import pytest

from clinamen.hindcast.puntuacion import cobertura, crps_muestras, pit_aleatorizado
from clinamen.ingesta.seshat import ZIP, cargar_panel


@pytest.mark.skipif(not ZIP.exists(), reason="datos brutos de Seshat no presentes")
def test_panel_seshat():
    d = cargar_panel()
    assert d.NGA.nunique() == 35 and d.region.nunique() == 10
    assert not d.duplicated(["NGA", "anio"]).any()
    assert d[["SPC", "Pop", "Terr"]].notna().all().all()
    assert (d.groupby("NGA").anio.diff().dropna() > 0).all()


def test_crps_normal():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(200000)
    # CRPS(N(0,1), 0) = 2φ(0) − 1/√π ≈ 0.2337
    assert crps_muestras(x, 0.0) == pytest.approx(0.2337, abs=3e-3)
    assert crps_muestras(np.zeros(10), 0.0) == 0.0


def test_pit_aleatorizado_uniforme_con_atomo():
    rng = np.random.default_rng(1)
    pits = []
    for _ in range(4000):
        m = np.where(rng.random(400) < 0.6, 0.0, rng.standard_normal(400))
        y = 0.0 if rng.random() < 0.6 else rng.standard_normal()
        pits.append(pit_aleatorizado(m, y, rng))
    pits = np.array(pits)
    assert abs(cobertura(pits, 0.9) - 0.9) < 0.02 and abs(cobertura(pits, 0.5) - 0.5) < 0.03


@pytest.mark.skipif(not ZIP.exists(), reason="datos brutos de Seshat no presentes")
def test_sin_fuga_del_futuro():
    """Alterar todo dato posterior al origen no cambia ni los ajustes ni las referencias nulas."""
    from clinamen.hindcast.evaluacion import ajustar_rivales, climatologia, persistencia, tendencia
    d = cargar_panel()
    regs = sorted(d.region.unique())
    origen = -4000
    d2 = d.copy()
    futuro = d2.anio > origen
    d2.loc[futuro, ["SPC", "Pop", "Terr"]] += np.random.default_rng(5).normal(0, 3, (futuro.sum(), 3))
    for var in ("SPC", "Pop"):
        a = ajustar_rivales(d, var, regs, np.random.default_rng(1), hasta=origen)
        b = ajustar_rivales(d2, var, regs, np.random.default_rng(1), hasta=origen)
        for k in a:
            assert np.array_equal(a[k].th, b[k].th), k
        y0 = d[d.anio == origen][var].to_numpy()
        ngas = list(d[d.anio == origen].NGA)
        for f, args in ((persistencia, (var, y0, 50)), (climatologia, (var, origen, len(y0), 50))):
            kw = {"hasta": origen} if f is persistencia else {}
            assert np.array_equal(f(d, *args, np.random.default_rng(2), **kw), f(d2, *args, np.random.default_rng(2), **kw))
        assert np.array_equal(tendencia(d, var, ngas, origen, y0, 50, np.random.default_rng(3), hasta=origen),
                              tendencia(d2, var, ngas, origen, y0, 50, np.random.default_rng(3), hasta=origen))


def test_chapman_kolmogorov_en_cadena_markov():
    """En datos generados por una cadena de Markov, T(200) ≈ T(100)² dentro del intervalo bootstrap."""
    import pandas as pd
    from clinamen.hindcast.evaluacion import chapman_kolmogorov
    rng = np.random.default_rng(0)
    P = np.array([[0.8, 0.2, 0, 0, 0], [0.1, 0.8, 0.1, 0, 0], [0, 0.1, 0.8, 0.1, 0], [0, 0, 0.1, 0.8, 0.1],
                  [0, 0, 0, 0.2, 0.8]])
    filas = []
    for g in range(40):
        s = rng.integers(5)
        for t in range(60):
            filas.append({"NGA": f"g{g}", "anio": 100 * t, "SPC": s + rng.random() * 0.5, "region": "x"})
            s = rng.choice(5, p=P[s])
    r = chapman_kolmogorov(pd.DataFrame(filas), rng, reps=200, cortes=np.array([1.0, 2.0, 3.0, 4.0]))
    assert r["fraccion_celdas_dentro"] >= 0.8
    # y con memoria (no markoviano) el contraste falla: proceso que alterna entre dos estados cada 2 pasos
    filas2 = [{"NGA": f"g{g}", "anio": 100 * t, "SPC": float((t + g) // 2 % 2) * 4 + 0.1, "region": "x"}
              for g in range(40) for t in range(60)]
    r2 = chapman_kolmogorov(pd.DataFrame(filas2), rng, reps=200, cortes=np.array([1.0, 2.0, 3.0, 4.0]))
    assert r2["fraccion_celdas_dentro"] < 0.8
