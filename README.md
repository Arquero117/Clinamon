# Clinamen

Motor de **historia contrafactual cuantitativa**: calcula, con incertidumbre explícita, qué habría cambiado ante una desviación mínima (un POD) y busca por sí mismo los PODs de mayor palanca. La especificación completa, y fuente de verdad, es el [manual](docs/manual/manual_clinamen.md).

> El LLM compila; el motor simula. Ensembles, no líneas. Coste y efecto en la misma moneda: el nat.

## Estado

| Fase | Contenido | Estado |
| --- | --- | --- |
| **F0 Cimientos** | Ontología (M1), motor vectorizado (M5), generador por contador, gemelos (M7), salida Parquet | **Puerta superada**: véase [informe](informes/F0/puerta_F0.md) y [resumen de fase](docs/fases/F0.md) |
| **F1 Banco canónico y mundo sintético** | Juguetes exactos, committor, presupuesto, ruta, espectro, asimilación, mundo sintético | **Puerta superada** (iteración 3): [informe](informes/F1/puerta_F1.md), [resumen](docs/fases/F1.md) |
| F2–F5 | Mecanismos e hindcast, validez interventiva, caso piloto, generalización | Siguiente: F2 |

**Lo que hay hoy no dice nada sobre la historia.** El único mundo disponible, `banco_f0`, es un mundo de prueba de ingeniería con parámetros supuestos (ADR-0005).

## Instalación

Python ≥ 3.10.

```bash
pip install -e ".[rapido,pruebas]"
```

`rapido` instala Numba (acelera el generador Philox; sin él todo funciona igual y da los mismos bits). `pruebas` instala pytest.

## Uso

Validar y resumir una ontología, con su catálogo cerrado de intervenciones:

```bash
clinamen ontologia --mundo banco_f0
```

Estimar la duración de un ensemble sin ejecutarlo:

```bash
clinamen ensemble --particulas 1000 --anios 200 --semilla 1 --salida corridas/prueba --estimar
```

Ejecutar gemelos con un POD (consulta I), en 8 procesos y con tope de 2 horas:

```bash
clinamen ensemble --particulas 1000 --anios 200 --semilla 1 --salida corridas/pod1 --procesos 8 --pod '{"tipo": "suceso", "fuente": "muerte_gobernante", "evento": "sobrevive", "indice": 3, "paso": 30}'
```

Toda corrida estima su duración antes de arrancar y aborta si supera `--max-horas` (2 por defecto). Es reanudable: si se interrumpe, se repite la misma orden y continúa desde el último bloque escrito. Escribe `observables/`, `gemelos/` y `anclas/` en Parquet, más un `manifiesto.json` con la configuración, las huellas sha256 de cada bloque, el acoplamiento y la consulta causal que responde.

Evaluar la puerta F0 en tu máquina (un minuto en un núcleo; mide el rendimiento en tu equipo):

```bash
clinamen puerta-f0 --salida informes/F0_mi_equipo
```

Evaluar la puerta F1 (reanudable; unos 20–25 min con 4 procesos, 0.27 h con 8 núcleos):

```bash
clinamen puerta-f1 --procesos 8 --salida informes/F1_mi_equipo
```

Pruebas (alrededor de un minuto):

```bash
python -m pytest
```

## Estructura

```
docs/manual/          manual de Clinamen (fuente de verdad)
docs/decisiones/      ADRs: decisiones de arquitectura con su porqué
docs/fases/           resumen de cada fase
prerregistro/         umbrales de puerta congelados con sha256 (§17.2)
informes/             informes de puerta generados
src/clinamen/
  ontologia/          M1: esquema tipado (Pydantic) y carga de YAML
  azar/               Philox4x32-10 y campo de azar por contador, con gemelos
  numerica/           fachada numérica determinista
  motor/              M5: motor SoA, topología, verificación de identidades, salida Parquet
  gemelos/            M7: catálogo de intervenciones
  mundos/banco_f0/    mundo de prueba de F0 (ontología YAML + 15 mecanismos)
  puerta/             evaluación de puertas de fase
tests/                84 pruebas
```

## Reglas que el código hace cumplir

- Un parámetro sin procedencia, prior con rango, referencia y marca de invariancia **no compila** (A13).
- Una fuente de azar sin familia y tiempo de identidad, o de cola pesada sin índice de cola, **no compila** (A4, A8).
- Un stock sin identidad contable **no compila**, y las identidades se verifican en cada paso (A3).
- Una variable, parámetro o fuente que nadie usa **no compila** (antipatrón «estado sin límites»).
- Cada ficha de mecanismo declara exactamente lo que lee, escribe, parametriza y sortea; un test lo comprueba ejecutando el mecanismo (§14.2).
- El catálogo de intervenciones es cerrado: solo sucesos declarados e inclinaciones de fuentes gaussianas declaradas (A6). Un POD de coste infinito es un error.
- Un POD nulo da efecto exactamente cero, bit a bit (§4.5).
