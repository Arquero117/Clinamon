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
- [x] P5. Motor: topología por lista de aristas; varios brazos (un POD por brazo); estado inicial dado; API paso a
      paso con reindexado (filtro de partículas); parámetros por columna; modelo de observación en la ontología.
      F0 debe seguir pasando (tests y `clinamen puerta-f0`).
- [x] P6. Mundo sintético `sintetico_f1` (ontología + mecanismos).
- [x] P7. M6 asimilación: filtro de partículas bootstrap + muestreo por importancia adaptativo pseudo-marginal.
- [x] P8. M10: degradación, efecto verdadero, intervalos, cobertura, ranking de candidatos, BH.
- [x] P9. `clinamen puerta-f1`: evaluación con semillas de puerta; informe; docs; commit; push.

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

## P5 hecho (motor)

- `motor.Simulacion`: API paso a paso (`paso()`, `reindexar(idx)`), `estado0` + `paso0` absolutos,
  parámetros por partícula (1, N) repetidos por brazo, `ramas` = varios brazos (brazo j: flujo propio 2j−1,
  intervención 2j). `simular()` es un envoltorio. `Resultado.coste_brazos`, `t_div_brazos`, `estado_final`.
- Topología `lista` (entidades + aristas; aisladas permitidas). `Observacion` en la ontología (variable,
  entidades, familia normal|lognormal, sd = nombre de parámetro, fraccion_huecos).
- La puerta F0 sigue superándose (comprobado tras P5). La huella de ontología de banco_f0 cambió por el
  esquema (campos nuevos de topología); la dinámica no.

## P6 hecho (mundo sintético)

- `mundos/sintetico_f1/`: 6 entidades, aristas (0,1),(1,2),(3,4),(4,5); 3 mecanismos (gobernante, capacidad,
  demografía); fuentes inicial, ruido_capacidad (inclinable), muerte_gobernante (muere/sobrevive), sucesion.
- Parámetros inferibles: sf_beta U[−0.25, 0.25] (0.0) y sf_sigma U[0.15, 0.35] (0.25); el resto degenerados.
- Observación `censo`: población de las 6 entidades, lognormal sd 0.03, 50 % de huecos.
- Observable de interés: `capacidad_0` (reducción nueva 'entidad').
- Dinámica: ~5 cambios de régimen por siglo; muerte del gobernante 0 → efecto −0.36 al año, −0.28 a 5 años,
  ~0 a 24 años (transitorio). POD en la entidad 4 → nulo en ley sobre capacidad_0 (comprobado).
- Rendimiento: ~0.8 µs por trayectoria-año.

## P7 en curso (asimilación) — estado a la última actualización

- `src/clinamen/asimilacion/filtro.py`: `observar`, `log_verosimilitud`, `condiciones_de`, `filtro_particulas`
  (bloques M×K, remuestreo sistemático por bloque, log p̂(y|θ)), `Prior` uniforme, `posterior_adaptativa`
  (3 etapas, t de Student + 10 % de prior), `Posterior.muestras_conjuntas(S, rng)` → (θ, estado en el último paso).
- `CampoAzar.condicionar(...)`: sucesos observados (crónica) con propuesta óptima K(·|A); su log K(A) se suma al
  peso de la partícula (`log_peso_condiciones`). Observación de familia `suceso` en el esquema.
- Diagnóstico: sd de log p̂ con θ fijo. Censo de población (integrador sin ruido) → degeneración (sd ~10 nats).
  DECISIÓN: el mundo sintético observa solo codificación de capacidad (normal, sd 0.8, 60 % huecos) y crónica
  de sucesiones completa; la población no se observa. Con K = 256: sd log p̂ ≈ 2 (sin censo, sd 1.0, 70 %).
- Pendiente de P7: test de la asimilación y medir ESS; elegir T_obs (30–40), M, K.

## P8 hecho (experimento sintético) — resultados de DESARROLLO (semillas 1–80, no de puerta)

`clinamen/validacion/sintetico.py`: ConfigExperimento(T_obs=30, H=5, M=256, K=256, etapas=3, S=200, R=50,
R_verdad=4000), 12 candidatos (muerte y inclinación +1 por entidad en t0 = 30); plantado = muerte del
gobernante 0; nulos = entidades 3–5. ~10 s por mundo en un núcleo.
80 mundos: cobertura 0.9125, plantado en top-3 95 %, FDR 0.037, Λ ok 100 %, ESS(θ) mediana ~63.
P-valores de nulos ~uniformes (KS p 0.28/0.53; sd z 1.06). H = 10 se descartó: el efecto del choque es
transitorio y el plantado no destacaba (decisión tomada con semillas de desarrollo, antes de la puerta).

## P9 — Iteración 1 de la puerta: NO SUPERADA (documentada en informes/F1/puerta_F1_iteracion1.md)

Todo pasa (Teoremas 2 y 3, Λ, cobertura 0.925, plantado 0.94, FDR 0.023, cómputo 0.21 h/8 núcleos) salvo el
committor de doble_pozo_estable en t = 54: error 0.041 en x = −0.07 (tolerancia max(0.02, 3·e.t.) = 0.04).
Diagnóstico: cerca del horizonte h es casi un escalón junto a la silla y 12 nodos (espaciado ~0.33) no lo
capta; el mismo defecto explica el sesgo leve de la urna en el Teorema 2 (2.9 e.t., al límite).
Corrección (iteración 2): nodos elegidos por instante con log-score en un 20 % reservado entre (12, 32).
La parte de mundos sintéticos no usa el committor: sus resultados (partes cobertura_*/plantado_*) siguen
válidos con el código de la iteración 2 (deterministas, mismo código).
Iteración 2: rehacer los cinco juguetes con la semilla de puerta 910001 y, más estricto que el prerregistro,
exigir también que pasen con semillas nuevas 910011 y 910021 (contra el sobreajuste a la semilla de puerta).
Si la iteración 2 falla: simplificar el modelo (§17.2), no la puerta.
Comprobación de desarrollo (semillas 11, 12) de la corrección: estable y urna superan todo.
Iteración 2 EN EJECUCIÓN: `clinamen puerta-f1` (rehace solo los juguetes; partes de juguetes borradas) y luego
robustez con 910011/910021 (log en el scratchpad; si se pierde, relanzar
`python <script it2> <5 juguetes> 910011,910021`, script = clinamen.puerta.f1._tarea('juguete', k, s)).

## Cierre

Puerta superada en la iteración 3 (commit cef68b2). Ver `docs/fases/F1.md`.

## Siguiente paso concreto

F1 cerrada. Siguiente fase: F2 (ver CLAUDE.md §2).
