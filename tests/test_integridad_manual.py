"""El manual es la fuente de verdad y no se modifica, resume ni recorta nunca."""
import hashlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_manual_intacto():
    contenido = (RAIZ / "docs" / "manual" / "manual_clinamen.md").read_bytes()
    esperado = (RAIZ / "prerregistro" / "manual.sha256").read_text().split()[0]
    assert hashlib.sha256(contenido).hexdigest() == esperado, (
        "docs/manual/manual_clinamen.md ha cambiado: el manual no se edita ni se resume. Restáuralo desde git.")
    assert contenido.count(b"\n") >= 1290
