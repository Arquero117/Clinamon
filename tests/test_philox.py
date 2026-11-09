"""Generador por contador: vectores de respuesta conocida de Random123 y propiedades de las uniformes."""
import numpy as np
import pytest

from clinamen.azar.philox import _construir_numba, a_uniformes, philox4x32, philox4x32_numpy

# Random123, kat_vectors: philox4x32 10 rondas
KAT = [
    ((0, 0, 0, 0), (0, 0), (0x6627E8D5, 0xE169C58D, 0xBC57AC4C, 0x9B00DBD8)),
    ((0xFFFFFFFF,) * 4, (0xFFFFFFFF,) * 2, (0x408F276D, 0x41C83B0E, 0xA20BC7C6, 0x6D5451FD)),
    ((0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344), (0xA4093822, 0x299F31D0),
     (0xD16CFE09, 0x94FDCCEB, 0x5001E420, 0x24126EA1)),
]


@pytest.mark.parametrize("c,k,esperado", KAT)
def test_vectores_conocidos_numpy(c, k, esperado):
    assert tuple(int(v) for v in philox4x32_numpy(*c, *k)) == esperado


@pytest.mark.parametrize("c,k,esperado", KAT)
def test_vectores_conocidos_auto(c, k, esperado):
    assert tuple(int(np.asarray(v).reshape(-1)[0]) for v in philox4x32(*c, *k)) == esperado


@pytest.mark.skipif(not _construir_numba(), reason="Numba no instalado")
def test_numba_identico_a_numpy():
    rng = np.random.default_rng(0)
    c = [rng.integers(0, 2 ** 32, size=(3, 7, 11), dtype=np.uint32) for _ in range(4)]
    a = philox4x32_numpy(*c, 123456789, 987654321)
    b = philox4x32(*c, 123456789, 987654321, motor="numba")
    for x, y in zip(a, b):
        assert np.array_equal(x, y)


def test_uniformes_en_intervalo_abierto():
    ceros = np.zeros(1, np.uint32)
    unos = np.full(1, 0xFFFFFFFF, np.uint32)
    u_min = a_uniformes(ceros, ceros)[0]
    u_max = a_uniformes(unos, unos)[0]
    assert 0.0 < u_min < 1e-15
    assert u_max < 1.0 and 1.0 - u_max < 1e-15
    assert np.isfinite(np.log(u_min)) and np.isfinite(np.log1p(-u_max))


def test_uniformes_aproximadamente_uniformes():
    c0 = np.arange(200_000, dtype=np.uint32)
    w = philox4x32(c0, 1, 2, 3, 5, 8)
    u = np.concatenate([a_uniformes(w[0], w[1]), a_uniformes(w[2], w[3])])
    hist, _ = np.histogram(u, bins=20, range=(0, 1))
    esperado = u.size / 20
    chi2 = ((hist - esperado) ** 2 / esperado).sum()
    assert chi2 < 45  # gl = 19; p ~ 1e-3
    assert abs(u.mean() - 0.5) < 0.003
