# F2 — Progreso y memoria de trabajo

> Tras cualquier compactación: protocolo de `CLAUDE.md` §0 y continuar por el primer paso no marcado.

## F2a: hindcast de escala social con Seshat (puerta `prerregistro/F2a_puerta.yaml`, aprobada y congelada)

- [x] P0. Propuesta aprobada por la persona; puerta congelada con sha256. Datos brutos en `datos/brutos/seshat_equinox/`.
- [x] P1. M2 ingesta: `src/clinamen/ingesta/seshat.py` → `datos/procesados/seshat_panel.parquet`
      (NGA, región mundial, siglo, PolID, SPC, Pop, Terr) + tests.
- [x] P2. Puntuación (M10): CRPS por muestras, PIT aleatorizado, cobertura, bootstrap por bloques de región.
- [x] P3. Modelos (M3/M6): R1, R2, R3 con componente de continuidad de polity (q), jerarquía por región
      (MLE penalizado), incertidumbre paramétrica por Laplace; predictivas por simulación; apilamiento.
- [x] P4. Referencias nulas: persistencia, tendencia lineal 500 años, climatología.
- [x] P5. Hindcast por origen móvil y por región dejada fuera; Chapman-Kolmogorov; inevitabilidad.
- [x] P6. `clinamen puerta-f2a` con la semilla 920001; informe; docs; commit; push.

## Regla anti-sobreajuste del constructor

Durante el desarrollo SOLO se usan orígenes −6000 a −3500 (no evaluados). Prohibido mirar puntuaciones de los
orígenes −3000…1500 o de la validación por regiones antes de la evaluación final. Las decisiones de modelado
se fijan antes.

## Decisiones registradas antes de ver resultados de la puerta

- Panel: una fila por región y siglo (si hay varias polities en un siglo, la de mayor población).
- Hecho de los datos: el 63 % de los cambios de SPC por siglo son exactamente 0 (88 % dentro de una polity):
  todos los rivales comparten el componente «la polity continúa con probabilidad q».
- Cobertura y PIT con PIT aleatorizado (correcto con átomos); se informa también la cobertura de intervalo.

- Bootstrap de la habilidad por bloques de GRAN REGIÓN (agrupación del prerregistro); inevitabilidad en
  grandes regiones con ≥ 30 predicciones de SPC. Fijado antes de ejecutar la puerta.
- Pruebas: sin fuga (alterar el futuro no cambia ajustes ni referencias) y Chapman-Kolmogorov con control
  positivo (Markov) y negativo (memoria).

## Iteración 1 de la puerta F2a: NO SUPERADA (informes/F2a/puerta_F2a.md)

Pasa: habilidad frente a la persistencia (+1.9 % a 100 años, +5.1 % a 200, cotas > 0), cobertura estratificada,
inevitabilidad, Chapman-Kolmogorov (84 %), cómputo. Falla: cobertura agregada (c50 ≈ 0.28, c90 0.79–0.88) y
civilización no usada (5/10). Diagnóstico: q constante; el cambio de polity depende fuertemente del nivel de SPC
y de la época.

## Iteración 2 + validación con Cliopatria (pedida por la persona)

- [x] Q0. Prerregistro `prerregistro/F2a_cliopatria.yaml` congelado ANTES de escribir las correcciones y antes
      de construir el panel de Cliopatria (mismos umbrales de F2a, observable Terr).
- [x] Q1. Correcciones en `hindcast/modelos.py`: q(y) logística y escala s(y) = s·exp(d1·z), en los tres rivales;
      probar SOLO con orígenes de desarrollo de Seshat.
- [x] Q2. `ingesta/cliopatria.py`: descarga con sha256, panel NGA × siglo (−3400…1900) de log10 del área.
- Regla técnica fijada antes de evaluar Cliopatria: si un ajuste tiene < 10 transiciones con cambio, pesos
      iguales y, si el ajuste final no es posible, el origen no aporta predicciones (MIN_CAMBIOS). Verificado:
      la iteración 1 de Seshat se reproduce idéntica con el código refactorizado.
- [ ] Q3. `puerta/f2a_cliopatria.py` + `clinamen puerta-f2a-cliopatria`; ejecutar UNA vez (semilla 930001);
      además, iteración 2 sobre Seshat marcada post hoc.
- [ ] Q4. Informe, docs, commit, push.

## Siguiente paso concreto

(Resuelto: la persona pidió iteración 2 validada con Cliopatria.) Seguir por Q1. Antes: (§17.2 permite dos). Propuesta: q y la escala del cambio como
función del nivel del observable (logística en y), mismo resto del diseño. Advertencia: la iteración 2 está
motivada por el resultado de la puerta, así que su evaluación con los mismos orígenes es en parte post hoc; se
declarará así y se añadirá como control un prerregistro de datos nuevos (p. ej. Cliopatria) si se quiere una
prueba limpia.
