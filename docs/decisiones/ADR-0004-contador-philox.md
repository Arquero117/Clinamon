# ADR-0004 — Disposición del contador Philox

**Estado:** aceptada (F0). **Afecta a:** §4.5.

Philox4x32-10 (Salmon y otros, 2011), verificado con los vectores de respuesta conocida de Random123. Contador de 128 bits y clave de 64:

| Palabra | Contenido |
| --- | --- |
| c0 | paso (uint32); `0xFFFFFFFF` reservado al estado inicial |
| c1 | índice del elemento del dominio (entidad, arista o 0) × 64 + par de ranuras |
| c2 | identificador global de partícula |
| c3 | (identificador de fuente << 8) \| flujo |
| clave | semilla de 64 bits |

Flujos: 0 común, 1 propio del brazo con POD, 2 sorteos frescos de la intervención. Cada llamada a Philox da cuatro palabras: dos uniformes `float64` de 52 bits en (0, 1), nunca 0 ni 1.

Propiedades que se siguen:

- El sorteo de (partícula, fuente, elemento, paso, flujo) es único y no depende del orden de cálculo, del bloque ni del proceso. De ahí la invariancia al tamaño de bloque y al número de procesos, y la reanudación exacta.
- Una fuente sorteada dos veces en el mismo paso repetiría números: el campo de azar lo prohíbe en tiempo de ejecución (`SorteoRepetidoError`), y la ontología impide que una fuente tenga dos mecanismos dueños.
- Límites: 2^24 fuentes, 2^26 elementos de dominio, 128 uniformes por elemento y paso, 2^32 partículas y pasos.
