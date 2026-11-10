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
