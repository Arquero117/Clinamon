# F1 — Progreso y memoria de trabajo

> Fichero de continuidad. Tras cualquier compactación: seguir el protocolo de `CLAUDE.md` §0 y continuar por el
> primer paso no marcado. Actualizar y hacer commit al terminar cada paso.

## Plan (§17.1 F1: M6, M8, M10)

- [x] P0. Protocolo de continuidad (`CLAUDE.md`), hash del manual y test de integridad.
- [x] P1. Puerta F1 congelada: `prerregistro/F1_puerta.yaml` + sha256.
- [x] P2. `clinamen/contingencia/cadena.py`: cadenas de Markov finitas con cálculo exacto de h, ρ_t (Teorema 2),
      κ_t (Teorema 3, transformada h de Doob), KL marginal de un POD (Λ exacto), espectro; simulación por Philox.
- [x] P3. `clinamen/contingencia/juguetes.py`: los cinco juguetes como cadenas finitas (discretización en rejilla).
- [x] P4. `clinamen/contingencia/estimadores.py` (M8 genérico, solo trayectorias): committor por regresión
      logística con validación cruzada, disparos, presupuesto ρ̂, κ̂ sobre trayectorias condicionadas a B, rastro
      por Donsker-Varadhan, espectro de tiempos implícitos, dos regímenes por vector propio. Tests contra exactos.
- [ ] P5. Motor: topología por lista de aristas; varios brazos (un POD por brazo); estado inicial dado; API paso a
      paso con reindexado (filtro de partículas); parámetros por columna; modelo de observación en la ontología.
      F0 debe seguir pasando (tests y `clinamen puerta-f0`).
- [ ] P6. Mundo sintético `sintetico_f1` (ontología + mecanismos).
- [ ] P7. M6 asimilación: filtro de partículas bootstrap + muestreo por importancia adaptativo pseudo-marginal.
- [ ] P8. M10: degradación, efecto verdadero, intervalos, cobertura, ranking de candidatos, BH.
- [ ] P9. `clinamen puerta-f1`: evaluación con semillas de puerta; informe; docs; commit; push.

## Decisiones tomadas (resumen; detalle en ADR-0006 cuando exista)

- Juguetes = cadenas de Markov finitas (discretizaciones en rejilla de los sistemas continuos). Así h, κ, ρ y Λ
  son exactos por álgebra lineal para el MISMO modelo que se simula; los estimadores de M8 solo ven trayectorias.
- κ̂_t = media sobre trayectorias que acaban en B de log ĥ_{t+1}(X_{t+1}) − log ĥ_t(X_t) (densidad de la
  transformada h). Su suma telescópica es −log ĥ_0.
- Λ̂: cota de Donsker-Varadhan con f ajustada (regresión logística del brazo) en una mitad, evaluada en la otra.
- Mundo sintético: 6 entidades en dos componentes desconectadas {0,1,2} y {3,4,5}; Y depende de la entidad 0;
  PODs en 3–5 son nulos exactos en ley (sirven para medir la FDR). POD plantado: muerte del gobernante de 0 en t0.
- Asimilación: θ de baja dimensión inferido por importancia adaptativa en 3 etapas con verosimilitud de filtro de
  partículas (pseudo-marginal); estado en t0 tomado del filtro de cada θ. Consulta I, variante de hindcast.
- Brazos múltiples: brazo j decoupled usa flujo 2j−1 y sus sorteos de intervención el 2j (j = 1 coincide con F0).

## Resultados de desarrollo P2–P4 (semilla de desarrollo 11; NO son la puerta)

`clinamen.contingencia.banco.evaluar_juguete(nombre, 40000, 40000, 100000, 11, nodos=12)`: los cinco juguetes
superan committor, Teorema 2, Teorema 3 y Λ. Tiempos: 30–50 s por juguete (lento_rapido ~200 s).
Lecciones (ya incorporadas al código):
- Base polinómica insuficiente → B-splines cúbicos (12 nodos) + indicadores para rasgos con ≤ 5 valores.
- Σ(Δĥ)² está sesgado por el ruido de ĥ → productos cruzados Δĥ¹·Δĥ² con ajustes independientes.
- El bootstrap sobre trayectorias de prueba subestima el error típico (ignora el ruido del ajuste) → Teorema 2 con
  16 lotes independientes; Teorema 3 suma el error relativo de ĥ_0.
- PODs designados con rastro medible (no absorbidos); observable x_T en 8 tramos.

## Uso de las semillas de puerta (fijado ANTES de usarlas)

- 910001: juguetes (cada juguete con esa semilla). 910002: cobertura. 910003: POD plantado.

## Siguiente paso concreto

P5 (motor).
