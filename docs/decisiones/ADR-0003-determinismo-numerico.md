# ADR-0003 — Determinismo numérico

**Estado:** aceptada (F0). **Afecta a:** §4.5, §14.4, puerta F0.

## Riesgos

1. **Funciones trascendentes dependientes de la posición.** En algunas combinaciones de CPU y versión de NumPy, `exp`, `log`, `power`… usan un camino SIMD para el cuerpo del array y otro para la cola. Entonces dos columnas con la misma entrada pueden dar bits distintos según dónde caigan, y el brazo con POD de un POD nulo (columnas `[N, 2N)`) diferiría del brazo base (`[0, N)`). En la máquina de construcción (NumPy 2.5, AVX-512) no ocurre; no está garantizado en general.
2. **Reducciones cuyo orden depende del tamaño del lote** (sumas por pares, BLAS multihilo): romperían la invariancia al tamaño de bloque.
3. **Generadores secuenciales**: se desincronizan entre gemelos.

## Decisiones

- `clinamen.numerica.mat` es la única puerta a trascendentes y reducciones. `verificar_determinismo_posicional()` se ejecuta al arrancar cada simulación y **aborta** si la plataforma no es determinista por posición. Si un día aborta, la salida es sustituir la fachada por implementaciones con solo operaciones IEEE exactamente redondeadas (+, −, ×, ÷, sqrt, frexp, ldexp), que sí son deterministas por construcción.
- Reducciones sobre entidades en orden secuencial explícito (`mat.suma_filas`). Agregaciones arista→entidad con listas de incidencia rellenadas y suma en orden fijo. Sin productos matriciales.
- Un test (`tests/test_fichas_mecanismo.py::test_mecanismos_sin_matematica_directa`) prohíbe `np.exp`, `np.log`, `np.sum`, `@`, `**`… dentro de los mecanismos.
- Azar solo por Philox4x32-10 indexado por contador (ADR-0004).
- `float64` en CPU como referencia. El determinismo bit a bit se exige en un mismo dispositivo; entre dispositivos se compara con tolerancia (§14.4).
- Identidades contables verificadas con residuo relativo a la suma de valores absolutos de los términos, tolerancia 1e-10 (congelada en el prerregistro).
