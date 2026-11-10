# F2 — Progreso y memoria de trabajo

> Tras cualquier compactación: protocolo de `CLAUDE.md` §0 y continuar por el primer paso no marcado.

## F2a: hindcast de escala social con Seshat (puerta `prerregistro/F2a_puerta.yaml`, aprobada y congelada)

- [x] P0. Propuesta aprobada por la persona; puerta congelada con sha256. Datos brutos en `datos/brutos/seshat_equinox/`.
- [x] P1. M2 ingesta: `src/clinamen/ingesta/seshat.py` → `datos/procesados/seshat_panel.parquet`
      (NGA, región mundial, siglo, PolID, SPC, Pop, Terr) + tests.
- [x] P2. Puntuación (M10): CRPS por muestras, PIT aleatorizado, cobertura, bootstrap por bloques de región.
- [ ] P3. Modelos (M3/M6): R1, R2, R3 con componente de continuidad de polity (q), jerarquía por región
      (MLE penalizado), incertidumbre paramétrica por Laplace; predictivas por simulación; apilamiento.
- [ ] P4. Referencias nulas: persistencia, tendencia lineal 500 años, climatología.
- [ ] P5. Hindcast por origen móvil y por región dejada fuera; Chapman-Kolmogorov; inevitabilidad.
- [ ] P6. `clinamen puerta-f2a` con la semilla 920001; informe; docs; commit; push.

## Regla anti-sobreajuste del constructor

Durante el desarrollo SOLO se usan orígenes −6000 a −3500 (no evaluados). Prohibido mirar puntuaciones de los
orígenes −3000…1500 o de la validación por regiones antes de la evaluación final. Las decisiones de modelado
se fijan antes.

## Decisiones registradas antes de ver resultados de la puerta

- Panel: una fila por región y siglo (si hay varias polities en un siglo, la de mayor población).
- Hecho de los datos: el 63 % de los cambios de SPC por siglo son exactamente 0 (88 % dentro de una polity):
  todos los rivales comparten el componente «la polity continúa con probabilidad q».
- Cobertura y PIT con PIT aleatorizado (correcto con átomos); se informa también la cobertura de intervalo.

## Siguiente paso concreto

P3 (modelos R1–R3, `src/clinamen/hindcast/modelos.py`).
