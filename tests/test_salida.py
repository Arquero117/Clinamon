"""Salida Parquet por bloques: invariancia de bloque y de procesos, reanudación y repetición."""
import json

import numpy as np
import pytest

from clinamen.motor.salida import ConfigEnsemble, ejecutar_ensemble, leer

POD = {"tipo": "suceso", "fuente": "muerte_gobernante", "evento": "sobrevive", "indice": 3, "paso": 5}


def _cfg(**k):
    base = dict(mundo="banco_f0", particulas=10, anios=20, semilla=31, pod=POD, bloque=4, anios_ancla=(0, 19))
    base.update(k)
    return ConfigEnsemble(**base)


def _tablas(ruta):
    return {t: leer(ruta, t).to_pydict() for t in ("observables", "gemelos", "anclas")}


def _iguales(a, b):
    for t in a:
        assert a[t].keys() == b[t].keys()
        for c in a[t]:
            assert np.array_equal(np.asarray(a[t][c]), np.asarray(b[t][c])), (t, c)


@pytest.fixture(scope="module")
def referencia(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("ref")
    man = ejecutar_ensemble(_cfg(), ruta, informar=lambda *_: None)
    assert man["estado"] == "completo"
    return ruta


def test_manifiesto(referencia):
    man = json.loads((referencia / "manifiesto.json").read_text())
    assert man["consulta"] == "I"
    assert man["acoplamiento"] == "fisico"
    assert man["config"]["ontologia"]
    assert len(man["bloques"]) == 3
    assert man["estimacion"]["us_por_trayectoria_anio"] > 0


def test_esquema_observables(referencia, modelo):
    t = leer(referencia, "observables")
    assert t.num_rows == 2 * 10 * 20
    assert {"mundo", "particula", "paso", "anio"} <= set(t.column_names)
    assert {o.nombre for o in modelo.ontologia.observables} <= set(t.column_names)
    a = leer(referencia, "anclas")
    assert a.num_rows == 2 * 10 * 2 * modelo.E


def test_invariancia_tamano_bloque(referencia, tmp_path):
    ejecutar_ensemble(_cfg(bloque=7), tmp_path, informar=lambda *_: None)
    _iguales(_tablas(referencia), _tablas(tmp_path))


def test_invariancia_procesos(referencia, tmp_path):
    ejecutar_ensemble(_cfg(), tmp_path, procesos=2, informar=lambda *_: None)
    _iguales(_tablas(referencia), _tablas(tmp_path))


def test_reanudacion(referencia, tmp_path):
    man = ejecutar_ensemble(_cfg(), tmp_path, max_bloques=1, informar=lambda *_: None)
    assert man["estado"] == "parcial"
    # se corrompe un bloque escrito: la reanudación lo detecta por sha256 y lo rehace
    ejecutar_ensemble(_cfg(), tmp_path, max_bloques=1, informar=lambda *_: None)
    f = tmp_path / "observables" / "bloque-00001.parquet"
    f.write_bytes(f.read_bytes()[:-10] + b"0123456789")
    man = ejecutar_ensemble(_cfg(), tmp_path, informar=lambda *_: None)
    assert man["estado"] == "completo"
    _iguales(_tablas(referencia), _tablas(tmp_path))


def test_repeticion_mismos_bytes(referencia, tmp_path):
    man_b = ejecutar_ensemble(_cfg(), tmp_path, informar=lambda *_: None)
    man_a = json.loads((referencia / "manifiesto.json").read_text())
    for i in man_a["bloques"]:
        for sub in ("observables", "gemelos", "anclas"):
            assert man_a["bloques"][i][sub] == man_b["bloques"][i][sub]


def test_config_distinta_en_misma_carpeta(referencia):
    with pytest.raises(RuntimeError, match="otra configuración"):
        ejecutar_ensemble(_cfg(semilla=1), referencia, informar=lambda *_: None)


def test_tope_de_horas(tmp_path):
    with pytest.raises(RuntimeError, match="supera el máximo"):
        ejecutar_ensemble(_cfg(particulas=10_000_000, anios=300), tmp_path, max_horas=0.01,
                          informar=lambda *_: None)


def test_cli_ontologia_y_estimar(tmp_path, capsys):
    from clinamen.cli import main
    main(["ontologia"])
    assert "Catálogo de intervenciones" in capsys.readouterr().out
    main(["ensemble", "--particulas", "8", "--anios", "10", "--semilla", "1", "--salida", str(tmp_path / "x"),
          "--estimar"])
    assert "us_por_trayectoria_anio" in capsys.readouterr().out
    main(["ensemble", "--particulas", "4", "--anios", "6", "--semilla", "1", "--salida", str(tmp_path / "y"),
          "--pod", '{"tipo": "inclinacion", "fuente": "vital", "indice": 0, "paso": 2, "desplazamiento": 0.5}'])
    assert len(leer(tmp_path / "y", "gemelos")) == 4
