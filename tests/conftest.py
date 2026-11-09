import pytest

from clinamen.mundos.banco_f0.modelo import construir_modelo


@pytest.fixture(scope="session")
def modelo():
    return construir_modelo()
