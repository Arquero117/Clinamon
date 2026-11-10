# Instrucciones para sesiones de construcción de Clinamen

## 0. PROTOCOLO OBLIGATORIO al empezar una sesión o tras cualquier compactación o borrado de memoria

El historial de chat puede resumirse en cualquier momento y los resúmenes pierden detalle. El repositorio no.
Antes de escribir una sola línea de código, en este orden:

1. **Lee el manual ÍNTEGRO**: `docs/manual/manual_clinamen.md` (1290 líneas) con la herramienta Read y
   `allow_large: true`, o en tramos consecutivos de principio a fin. **Nunca** trabajes a partir de un resumen
   del manual, ni del tuyo ni del historial. Si un resumen del chat contradice el manual, manda el manual.
2. **El manual no se toca.** No se edita, no se resume, no se recorta, no se reformatea, no se sustituye por una
   versión abreviada. Su sha256 está en `prerregistro/manual.sha256` y `tests/test_integridad_manual.py` lo
   comprueba. Si alguna vez falla, restáuralo con `git checkout <commit> -- docs/manual/manual_clinamen.md`.
3. Lee el fichero de progreso de la fase en curso (`docs/fases/F<n>_progreso.md`): estado, decisiones tomadas,
   siguiente paso concreto. Es la memoria de trabajo del proyecto; **actualízalo y haz commit después de cada
   paso terminado**, antes de seguir.
4. Lee las ADR de `docs/decisiones/` que afecten a lo que vas a tocar.
5. Ejecuta `python -m pytest -q` (unos 30 s) para confirmar el punto de partida.

## 1. Prompt de arranque (manual §0.4)

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

## 2. Estado del proyecto

- **F0 Cimientos:** completada; puerta superada (`informes/F0/puerta_F0.md`, `docs/fases/F0.md`).
- **F1 Banco canónico y mundo sintético:** completada; puerta superada en la iteración 3
  (`informes/F1/puerta_F1.md`, `docs/fases/F1.md`, historial en `docs/fases/F1_progreso.md`).
- **F2 Mecanismos y hindcast:** tramo F2a CERRADO SIN SUPERAR la puerta tras dos iteraciones (Seshat; validación
  limpia con Cliopatria). Informes en `informes/F2a*`, resumen en `docs/fases/F2_progreso.md`. Siguiente: F2b
  (mecanismos multivariantes con más fuentes) cuando la persona lo decida; congelar su puerta antes.
- La puerta no se mueve (§17.2). Si F1 no la supera tras dos iteraciones, se simplifica el modelo.
- Las **semillas de puerta** del prerregistro no se usan nunca durante el desarrollo: solo en la evaluación final.

## 3. Restricciones de cómputo de la persona

- Su capacidad de cómputo es limitada: CPU de escritorio o GPU modesta en Colab (T4/L4). Ningún script de usuario
  debe pasar de una o dos horas; todo script estima su duración antes de arrancar y aborta por encima de `--max-horas`.
- El constructor no lanza ensembles largos: pruebas pequeñas y suficientes. Solo la evaluación final de una
  puerta puede durar unos minutos.

## 4. Convenciones de código

- Arrays de entidad `(E, B)`, globales `(1, B)`; `B` es el eje del ensemble. Con brazos, `[0, N)` es el brazo base
  y `[jN, (j+1)N)` el brazo j con su POD.
- En mecanismos: trascendentes y reducciones solo vía `clinamen.numerica.mat`; nunca `np.exp`, `np.sum`, `@` ni
  `**` (un test lo prohíbe). Escribir siempre reasignando `x[v] = ...`.
- Cada fuente de azar se sortea una vez por paso y la sortea un único mecanismo. Los sucesos declarados se pasan
  como intervalos `[lo, hi)` de la uniforme y el desenlace se decide con `u < hi`.
- Toda variable, parámetro y fuente nuevos van primero a la ontología YAML; si no se usan, no compila.
- Identificadores y documentación en español. Commits pequeños y frecuentes; push a la rama de trabajo.
