# Propuesta de puerta F2a — hindcast de escala social con datos reales (borrador para aprobación)

> Estado: PROPUESTA. No se escribe código de F2 hasta que la persona apruebe estos umbrales; entonces se congelan
> en `prerregistro/F2a_puerta.yaml` con sha256.

## Alcance (F2a: primer tramo de F2)

§17.1 pide para F2: biblioteca de mecanismos con rivales, ingesta del panel, estimación jerárquica y hindcast con
origen móvil. F2a cubre ese circuito completo sobre el observable más sencillo y mejor medido; los mecanismos
demográfico-fiscales completos (F2b) vendrán después con más fuentes.

- **Datos (M2):** Seshat Equinox 2020 (Zenodo 6629022, sha256 `29127b15…`): 35 regiones (NGA), un registro por
  siglo, de −10000 a 1900. Observables: índice de complejidad social SPC (primer componente principal), log10 de
  la población del Estado (Pop) y log10 de su territorio (Terr). Error de medida: la dispersión entre las
  imputaciones múltiples de Seshat (`Scale_MI`).
- **Cautelas registradas antes de ver resultados:** (1) los valores se codifican por polity y se repiten de
  siglo en siglo, lo que favorece a la persistencia; (2) las imputaciones de Seshat usan otras variables de la
  misma polity (contemporáneas), no el futuro de la serie: se acepta, y se repite el análisis solo con valores
  codificados como control; (3) las regiones no son independientes (problema de Galton, §13.5): todas las
  incertidumbres de las puntuaciones se calculan con bootstrap por bloques de región.
- **Tres modelos rivales (A9)**, todos estocásticos, con parámetros jerárquicos por gran región mundial:
  R1 crecimiento logístico hacia un techo con colapsos de cola pesada (mecanismo de escala con rendimientos
  decrecientes); R2 paseo aleatorio con deriva y choques t de Student; R3 reversión a un nivel regional
  (Ornstein-Uhlenbeck). Predicción por apilamiento (stacking) sobre la puntuación fuera de muestra (§11.4).
- **Referencias nulas (§13.3):** persistencia (último valor más la dispersión empírica de los cambios a h años),
  tendencia lineal de los últimos 500 años y climatología (distribución de todas las regiones en esa fecha).
- **Hindcast sin fuga:** origen móvil cada 500 años de −3000 a 1500; en cada origen los modelos se ajustan SOLO con
  datos anteriores al origen (de todas las regiones) y predicen 100, 200 y 300 años después. Además, validación
  cruzada dejando fuera una gran región mundial entera (predicción de una civilización no usada).
- **Puntuación:** CRPS; habilidad = 1 − CRPS_modelo / CRPS_persistencia; PIT y cobertura de los intervalos del
  50 % y del 90 %, agregados y por gran región.

## Umbrales propuestos

| Criterio (§17.1 F2) | Umbral propuesto |
| --- | --- |
| Habilidad frente a la persistencia (el manual dice 25 años; con datos por siglos, el horizonte mínimo es 100) | Habilidad CRPS del modelo apilado > 0 a 100 y a 200 años, con la cota inferior del 90 % por bootstrap de bloques de región > 0, en SPC |
| Calibración agregada | Cobertura del 90 % en [0.85, 0.95] y del 50 % en [0.43, 0.57], por observable y horizonte |
| Calibración estratificada | En cada gran región con ≥ 30 predicciones, cobertura del 90 % en [0.75, 0.98] |
| Civilización no usada | Habilidad > 0 frente a la persistencia, a 100 años en SPC, en al menos 7 de las 10 grandes regiones dejadas fuera |
| Chapman-Kolmogorov | Para R1 ajustado: la matriz de transición a 200 años y el cuadrado de la de 100 años (SPC en 5 tramos) coinciden dentro del intervalo bootstrap del 95 % en ≥ 80 % de las celdas |
| Inevitabilidad (§12 regla 8) | Ninguna región con PIT medio fuera de [0.2, 0.8] (ni la historia siempre en el centro ni siempre en las colas) |
| Cómputo | Todo el hindcast ≤ 1 h en CPU de 8 núcleos |

## Qué no podrá decir F2a aunque pase

- Nada sobre intervenciones: un hindcast valida predicciones, no PODs (A12; eso es F3).
- Nada a menos de 100 años: los datos son por siglo.
- Si no supera la persistencia, la conclusión honesta es que la complejidad social no es predecible a esa escala
  con estos datos (§19.3), y se documenta con números.
