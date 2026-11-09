# ADR-0001 — Pila tecnológica de F0

**Estado:** aceptada (F0). **Rango normativo:** 4 (arquitectura; §0.2 permite cambiarla documentando por qué).

## Decisión

- **Python + NumPy** con disposición de estructura de arrays (SoA): cada variable de entidad es un array `(E, B)`, cada global `(1, B)`, con `B` el eje del ensemble. Con gemelos, las columnas `[0, N)` son el brazo base y `[N, 2N)` el brazo con POD.
- **Numba opcional** y solo para Philox (aritmética entera: bits idénticos a la versión NumPy, comprobado en `tests/test_philox.py`). Sin Numba todo funciona igual, más lento.
- **Pydantic + YAML** para la ontología (M1). **PyArrow/Parquet** (zstd) para la salida.
- **SciPy** solo para `ndtri` (cuantil normal).

## Por qué no Rust ni JAX (alternativas de §14.1)

- El objetivo de rendimiento (§14.3) se alcanza ya con NumPy: 28.7 µs por trayectoria-año en un núcleo con Philox en Numba y 45.6 µs con NumPy puro, frente a un objetivo de 20 y una puerta de 200. No compensa el coste de mantener una cadena de compilación Rust para la persona que ejecuta.
- JAX obliga a arrays inmutables y a compilar el bucle completo; complica el rastreo de lecturas y escrituras que verifica las fichas (§14.2) y el control fino del determinismo. Se puede reconsiderar para el emulador diferenciable de F1–F4 (acción mínima, §6.4), que es otro componente.
- Todo el motor usa solo operaciones elemento a elemento, índices enteros y reducciones explícitas: es portable a CuPy (GPU T4/L4) sustituyendo el espacio de nombres de arrays. **No validado en F0**: no hay GPU en el entorno de construcción. Se validará cuando un ensemble lo necesite (§0.3).

## Consecuencias

- Rendimiento en CPU de escritorio, extrapolado de la medida en un núcleo (28.7 µs) y suponiendo escalado lineal con 16 procesos: la propagación de un POD de §14.3 (1.000 partículas × 2 × 200 años, 11 s en un núcleo) tarda unos segundos; la certificación de 50 PODs × 1.000 × 2 × 150 × 3 modelos (unos 21 min en un núcleo) tarda alrededor de un minuto y medio. Hay que confirmarlo en el equipo real con `clinamen ensemble --estimar`.
- Siguiente palanca de rendimiento si hiciera falta: fusionar mecanismos completos en núcleos Numba (cuidado: sin `fastmath`, para conservar el determinismo).
