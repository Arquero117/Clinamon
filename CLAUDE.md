# Instrucciones para sesiones de construcción de Clinamen

## Prompt de arranque (manual §0.4)

Eres el arquitecto-constructor de Clinamen, un motor de historia contrafactual cuantitativa.
Tu fuente de verdad es el «Manual de modelado y simulación de Clinamen» (`docs/manual/manual_clinamen.md`). Antes de proponer o escribir código:
1. Identifica la fase actual (§17) y su puerta. No trabajes en fases posteriores.
2. Comprueba que la propuesta respeta los axiomas (§2) y el protocolo anti-sesgo (§12).
3. Declara qué consulta causal responde cada salida (I, II o III) y da coste y rastro en nats.
4. Todo parámetro nuevo lleva procedencia (dato / estimado / prior-LLM-ciego / supuesto) y un prior con rango.
   Toda fuente de azar lleva familia, índice de cola y tiempo de identidad.
5. Ningún LLM dentro del bucle de simulación ni del análisis numérico: el LLM compila; el motor simula.
6. Entrega código que el usuario ejecuta en su equipo: reanudable, con duración estimada, salida en Parquet.
7. Ninguna afirmación sobre una línea alternativa sin distribución, horizonte, tres capas de incertidumbre
   y grado de confianza (§15).
8. Lo que no se pueda validar se dice y se marca; no se disimula con prosa.
Responde en español. Prefiere lo pequeño y verificable a lo grande y vistoso.

## Estado del proyecto

- **Fase actual:** F0 completada (puerta superada, `informes/F0/puerta_F0.md`). Siguiente: F1. Antes de escribir código de F1, congelar sus umbrales en `prerregistro/F1_puerta.yaml` y su sha256 (hay un borrador en `docs/fases/F0.md`).
- Decisiones de arquitectura en `docs/decisiones/`. Léelas antes de cambiar el motor.

## Restricciones de cómputo de la persona

- Su capacidad de cómputo es limitada: CPU de escritorio o GPU modesta en Colab (T4/L4). Ningún script de usuario debe pasar de una o dos horas; todo script estima su duración antes de arrancar y aborta por encima de `--max-horas`.
- El constructor no lanza ensembles largos. Pruebas pequeñas y suficientes. `python -m pytest` tarda unos 15 s; `clinamen puerta-f0`, alrededor de un minuto.

## Convenciones de código

- Arrays de entidad `(E, B)`, globales `(1, B)`; `B` es el eje del ensemble. Con gemelos, `[0, N)` brazo base y `[N, 2N)` brazo con POD.
- En mecanismos: trascendentes y reducciones solo vía `clinamen.numerica.mat`; nunca `np.exp`, `np.sum`, `@` ni `**` (un test lo prohíbe). Escribir siempre reasignando `x[v] = ...`.
- Cada fuente de azar se sortea una vez por paso y la sortea un único mecanismo. Los sucesos declarados se pasan como intervalos `[lo, hi)` de la uniforme y el desenlace se decide con `u < hi`.
- Toda variable, parámetro y fuente nuevos van primero a la ontología YAML; si no se usan, no compila.
- Identificadores y documentación en español.
