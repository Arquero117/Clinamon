# ADR-0002 — Gemelos, horizonte de identidad y acoplamientos

**Estado:** aceptada (F0). **Afecta a:** A5, A8, §4.3, §4.5, §5.2 (rango 1–3). Esta ADR concreta la norma; no la cambia.

## Problema

§4.3 dice que la fuente j se comparte entre los dos mundos «antes de t₀ + τⱼ» y §4.5 exige que «un POD nulo produzca efecto exactamente cero, bit a bit». Leídas a la letra chocan: si el reloj arranca en t₀, un POD nulo desacopla igualmente las fuentes en t₀ + τⱼ, ambos brazos reciben sorteos distintos y el efecto deja de ser cero (aunque su esperanza lo sea).

## Decisión

1. **El reloj de identidad arranca en la divergencia física.** Para cada partícula se registra `t_div`, el primer paso al final del cual el estado completo del brazo con POD difiere bit a bit del brazo base. La fuente j pasa al flujo propio del brazo con POD en los pasos `t ≥ t_div + max(1, ⌈τⱼ⌉)`; con τ infinito, nunca.
   Es la lectura física de A8: el azar se comparte «mientras sea físicamente insensible al POD». Un POD que no cambia nada no desacopla nada.
2. **El brazo base usa siempre el flujo común.** Por tanto el brazo base de cualquier par de gemelos es bit a bit el ensemble sin intervención (verificado en la puerta). Se puede reutilizar entre PODs.
3. **POD-suceso con acoplamiento máximo.** Para K′ = K(·|A), si el sorteo del brazo base ya cae en A se conserva; si no, se sustituye por una uniforme fresca (flujo `INTERVENCION`) reescalada a A. La ley resultante es exactamente K(·|A) y el coste por partícula es −log K(A), calculado con el estado de esa partícula.
4. **Tres acoplamientos** seleccionables: `fisico` (tabla de τⱼ de la ontología), `maximo` (todo se comparte siempre) e `independiente` (todo se desacopla al paso siguiente a la divergencia). §4.3 pide informar II y III bajo el mínimo físico y el máximo; `independiente` sirve de referencia de varianza.

## Por qué no cambia las marginales (consulta I)

En el paso t, el brazo con POD toma su sorteo del flujo común o del propio según una regla que solo depende de lo ocurrido hasta t−1 (`t_div` se fija al final de un paso). Ambos flujos dan, en el paso t, uniformes independientes de todo el pasado de ese brazo. Elegir entre dos variables frescas con una regla medible respecto al pasado da una variable fresca con la misma ley. Así, la ley de cada brazo no depende del acoplamiento, como exige la Proposición 1 (§4.2). Comprobación empírica: `tests/test_gemelos.py::test_marginal_del_brazo_pod_no_depende_del_acoplamiento` (KS entre acoplamientos con semillas independientes).

Una sutileza: con el acoplamiento físico, el brazo base y el brazo con POD comparten sorteos posteriores a t₀ mientras su fuente no se haya desacoplado. Eso no altera ninguna marginal, pero sí las magnitudes pareadas. Por eso toda magnitud pareada debe informarse con su acoplamiento (§4.2, antipatrón «pares por efectos»), y el manifiesto de cada corrida lo registra.

## Limitaciones conocidas

- La divergencia es global por partícula: no se propaga por la red de contacto entidad a entidad (§4.3 «se propaga por la red de contacto»). Con fuentes atmosféricas de τ ≈ semanas el efecto práctico es nulo; para fuentes de τ largo y lejanas al POD puede ser conservador. Revisable en F2.
- «Se comparte la fragilidad intrínseca; se re-sortea la exposición» (muerte de vivos) se modela con el estado (fragilidad persiste) y la fuente de muerte desacoplada a τ = 2 años. No hay aún descomposición explícita fragilidad/exposición.
- El ruido de Gumbel de decisiones (§9.4) llega con la capa de agencia (F2+).
