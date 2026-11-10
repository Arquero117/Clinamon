# Informe de la puerta F2a — hindcast de escala social con datos reales (iteración 1)

- Prerregistro `prerregistro/F2a_puerta.yaml` (aprobado por la persona y congelado antes de escribir código).
- Datos: Seshat Equinox 2020 (35 regiones, 10 grandes regiones, un registro por siglo). 1724 predicciones fuera
  de muestra en 10 orígenes (−3000…1500), 3 observables (SPC, log población, log territorio) y 3 horizontes
  (100, 200 y 300 años), más 1455 predicciones de grandes regiones dejadas fuera.
- Regla sin fuga verificada por test: alterar cualquier dato posterior al origen no cambia ningún ajuste.
- Semilla de puerta 920001, usada una vez (una primera ejecución abortó al serializar el JSON, después del
  cálculo y sin mostrar resultados; la repetición es determinista e idéntica). Cómputo: 95 s en un núcleo.

## Resultado: PUERTA NO SUPERADA (iteración 1)

| Criterio | Resultado | Umbral | |
| --- | --- | --- | --- |
| Habilidad CRPS frente a la persistencia, SPC a 100 años | +1.9 % (cota inferior 90 %: +0.8 %) | cota > 0 | ✅ |
| Habilidad CRPS frente a la persistencia, SPC a 200 años | +5.1 % (cota inferior 90 %: +3.4 %) | cota > 0 | ✅ |
| Cobertura del 90 % (9 combinaciones observable × horizonte) | 0.79 – 0.88 | [0.85, 0.95] | ❌ (5 de 9 por debajo) |
| Cobertura del 50 % | 0.26 – 0.35 | [0.43, 0.57] | ❌ (todas) |
| Cobertura del 90 % por gran región (≥ 30 predicciones) | 0.80 – 0.95 | [0.75, 0.98] | ✅ |
| Inevitabilidad: PIT medio por gran región | 0.55 – 0.63 | [0.2, 0.8] | ✅ |
| Civilización no usada: regiones con habilidad > 0 a 100 años | 5 de 10 (Asia oriental −44 %, Norteamérica −20 %) | ≥ 7 | ❌ |
| Chapman-Kolmogorov (SPC en 5 tramos) | 84 % de las celdas | ≥ 80 % | ✅ |
| Cómputo | 95 s | ≤ 1 h con 8 núcleos | ✅ |

CRPS medio (menor es mejor), SPC: a 100 años apilado 0.192, persistencia 0.196, tendencia 0.262, climatología
0.790; a 300 años apilado 0.329, persistencia 0.351, tendencia 0.536, climatología 0.789. El patrón es el mismo en
población y territorio: el modelo apilado gana a las tres referencias en todos los observables y horizontes,
con ventaja creciente con el horizonte. Los pesos del apilamiento favorecen a R3 (reversión a un nivel regional).

## Diagnóstico (análisis descriptivo posterior al resultado)

Los tres rivales comparten una probabilidad constante q de que la polity continúe (cambio cero). Pero esa
probabilidad cae con la complejidad (0.88 con SPC 2–3; 0.21 con SPC > 6) y con la época (0.92 antes de −3000;
0.23 después de 500). Como q se estima con todo el pasado, que es casi estático, el modelo se confía en exceso en
que «nada cambia» e infravalora el crecimiento: el PIT se acumula arriba (237 de 571 predicciones de SPC en el 20 %
superior) y la cobertura del 50 % se hunde. La misma no estacionariedad explica que trasplantar parámetros a una
gran región no vista (Asia oriental, Norteamérica) empeore a la persistencia.

## Lectura honesta

- **Sí hay señal predictiva real y sin sobreajuste**, pequeña: entre un 2 % y un 7 % mejor que la persistencia
  en CRPS, significativa con bootstrap por grandes regiones, y muy por encima de la tendencia y la climatología.
- **No hay calibración**: las bandas de incertidumbre son demasiado estrechas en el centro y están sesgadas. Con
  esta puerta no hay licencia para dar intervalos.
- **No hay transporte**: predecir una civilización entera no vista no mejora a la persistencia en la mitad de
  los casos. La simetría cultural (A17, §13.6) no se sostiene con un q y unos parámetros comunes.

Nada de esto valida intervenciones (A12): un hindcast valida predicciones, no PODs.
