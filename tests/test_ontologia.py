"""M1: la ontología compila solo si cumple A3, A4, A8, A13 y §14.2."""
import copy
from pathlib import Path

import pytest
import yaml

from clinamen.gemelos.intervencion import catalogo
from clinamen.mundos.banco_f0.modelo import RUTA_ONTOLOGIA
from clinamen.ontologia.carga import cargar_ontologia

BASE = yaml.safe_load(Path(RUTA_ONTOLOGIA).read_text(encoding="utf-8"))


def _cargar(datos, tmp_path):
    ruta = tmp_path / "o.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return cargar_ontologia(ruta)


def test_banco_compila_y_tamano(modelo):
    o = modelo.ontologia
    por_entidad = [v for v in o.variables if v.ambito == "entidad"]
    assert modelo.E == 30
    assert len(por_entidad) >= 40
    assert len(o.mecanismos) >= 15
    assert all(v.unidad and v.rango for v in o.variables)


def test_huella_estable(modelo):
    assert modelo.ontologia.huella() == cargar_ontologia(RUTA_ONTOLOGIA).huella()


def test_todo_parametro_con_procedencia(modelo):
    for p in modelo.ontologia.parametros:
        assert p.procedencia in ("dato", "estimado", "prior-LLM-ciego", "supuesto")
        assert p.prior.rango[0] <= p.valor <= p.prior.rango[1]
        assert p.referencia


def test_parametro_sin_procedencia_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    del d["parametros"]["vol_p"]["procedencia"]
    with pytest.raises(Exception, match="procedencia"):
        _cargar(d, tmp_path)


def test_valor_fuera_del_prior_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    d["parametros"]["vol_p"]["valor"] = 0.5
    with pytest.raises(Exception, match="fuera de su prior"):
        _cargar(d, tmp_path)


def test_cola_pesada_sin_indice_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    del d["fuentes"]["volcan"]["indice_cola"]
    with pytest.raises(Exception, match="índice de cola"):
        _cargar(d, tmp_path)


def test_fuente_sin_tiempo_de_identidad_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    del d["fuentes"]["guerra"]["tiempo_identidad_anios"]
    with pytest.raises(Exception, match="tiempo_identidad_anios"):
        _cargar(d, tmp_path)


def test_stock_sin_identidad_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    del d["identidades"]["deuda"]
    with pytest.raises(Exception, match="sin identidad stock-flujo"):
        _cargar(d, tmp_path)


def test_variable_huerfana_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    d["variables"]["inventada"] = {"bloque": "M", "tipo": "estado", "unidad": "x", "rango": [0, 1],
                                   "descripcion": "sin uso"}
    with pytest.raises(Exception, match="inventada"):
        _cargar(d, tmp_path)


def test_parametro_huerfano_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    d["parametros"]["sobrante"] = dict(d["parametros"]["vol_p"])
    with pytest.raises(Exception, match="parámetro sobrante huérfano"):
        _cargar(d, tmp_path)


def test_fuente_con_dos_duenos_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    d["mecanismos"]["clima"]["fuentes"] = ["clima_interno", "volcan"]
    with pytest.raises(Exception, match="un solo dueño"):
        _cargar(d, tmp_path)


def test_ficha_incompleta_no_compila(tmp_path):
    d = copy.deepcopy(BASE)
    del d["mecanismos"]["clima"]["evidencia"]
    with pytest.raises(Exception, match="evidencia"):
        _cargar(d, tmp_path)


def test_catalogo_cerrado(modelo):
    cat = catalogo(modelo.ontologia)
    tipos = {c["tipo"] for c in cat}
    assert tipos == {"nulo", "suceso", "inclinacion"}
    sucesos = {(c["fuente"], c["evento"]) for c in cat if c["tipo"] == "suceso"}
    assert ("muerte_gobernante", "sobrevive") in sucesos
