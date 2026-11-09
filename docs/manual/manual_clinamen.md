# Clinamen — Manual de modelado y simulación de historia contrafactual

Nov 9, 2026 · @Claude

## 0. Cómo usar este manual

Este documento es la especificación completa de **Clinamen**: un motor que calcula, con incertidumbre explícita, qué habría cambiado en la historia ante una desviación mínima (un POD), y que busca por sí mismo los PODs de mayor palanca. Contiene la teoría, la ingeniería y la ruta de construcción.

Está escrito para un modelo constructor (Claude u otro agente) que diseñe e implemente el sistema por fases, y sirve de contrato para la persona que lo supervisa. El nombre viene del *clinamen* de Lucrecio: la desviación mínima e impredecible de un átomo que basta para cambiar el curso de las cosas.

### 0.1 Mapa del manual

| Parte | Secciones | Contenido |
| --- | --- | --- |
| Fundamentos | §1 y §2 | Alcance, preguntas que el sistema responde, axiomas |
| Teoría | §3 a §9 | Objeto matemático, causalidad, PODs, contingencia, regímenes, memoria, agencia |
| Método | §10 a §13 | Búsqueda de PODs, inferencia, protocolo anti-sesgo, validación |
| Construcción | §14 a §17 | Arquitectura, contrato de salida, flujo de un caso, hoja de ruta |
| Horizonte | §18 a §21 | Prospectiva, programa de investigación, antipatrones, notación y referencias |

### 0.2 Jerarquía de normas

Si dos indicaciones chocan, manda la de rango superior.

1. **Axiomas (§2).** No se negocian: si una decisión de diseño viola uno, la decisión está mal.
2. **Protocolo anti-sesgo (§12) y contrato de salida (§15).**
3. **Teoría y método (§3 a §11, §13).** Las definiciones matemáticas son vinculantes.
4. **Arquitectura y hoja de ruta (§14, §17).** Son la propuesta por defecto. El constructor puede cambiarlas si documenta por qué y no viola nada de rango superior.
5. **Ejemplos y heurísticas.** Orientativos.

### 0.3 Reparto del trabajo

El modelo constructor escribe código, tests, esquemas y documentación. No ejecuta simulaciones largas. Los ensembles los lanza la persona en su equipo y devuelve los resultados para que el modelo los analice.

Equipos de referencia: un portátil de 16 núcleos y 32 GB, o una GPU modesta en la nube (clase T4 o L4) en precisión simple. Todo script de ejecución está optimizado para uno de los dos, estima su duración antes de arrancar, es reanudable y escribe en formato columnar (Parquet).

### 0.4 Prompt de arranque

Se pega como instrucción de sistema al empezar cada sesión de construcción.

```markdown
Eres el arquitecto-constructor de Clinamen, un motor de historia contrafactual cuantitativa.
Tu fuente de verdad es el «Manual de modelado y simulación de Clinamen». Antes de proponer o escribir código:
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
```

## 1. Alcance y preguntas

Clinamen es un laboratorio de contrafactuales condicionado a modelos explícitos. Produce distribuciones sobre unas decenas de variables macro, a horizontes de décadas a un par de siglos, y mide cuándo deja de poder afirmar algo. No es un oráculo que narre los acontecimientos de una línea alternativa.

### 1.1 Tres condiciones de seriedad

1. **El LLM compila, no simula.** Con miles de trayectorias de 200 años, un LLM por paso es inviable en coste y además cuela su conocimiento de la historia real. El LLM traduce casos a configuraciones y priores, a ciegas; un motor numérico hace el resto.
2. **Un contrafactual no es una simulación hacia delante.** Primero se infiere qué estado oculto es compatible con lo que ocurrió; solo después se interviene. Sin ese paso se compara un mundo inventado con otro mundo inventado.
3. **Validación antes que ambición.** El contrafactual nunca se observa. Se valida el motor hacia delante, cada mecanismo por separado y la cadena completa en mundos sintéticos con verdad conocida. Si eso falla, lo demás no vale nada.

### 1.2 Ideas rectoras

- **Lo micro es caótico; lo macro está canalizado.** La contingencia de sucesos y personas se satura en pocos años. La señal predecible vive en variables agregadas sujetas a restricciones.
- **Los atractores absorben o amplifican.** Un mismo POD se disuelve en una cuenca profunda y cambia la historia cerca de una divisoria.
- **Ensembles, no líneas.** Nunca se modela una línea temporal alternativa: se modela una distribución de ellas.
- **Coste y efecto en la misma moneda.** La improbabilidad de un POD y la huella que deja se miden en nats, y la segunda no puede superar a la primera.

### 1.3 Cinco preguntas computables

Cada pregunta tiene una salida numérica definida. Si una funcionalidad no contribuye a alguna de ellas, no se construye.

| Pregunta | Entrada | Salida principal | Dónde |
| --- | --- | --- | --- |
| Q1. Mapa de contingencia: ¿cuándo, y por qué fuente de azar, se decidió un desenlace? | Teatro, ventana y desenlace | Presupuesto de contingencia: incertidumbre resuelta por instante y por fuente a lo largo de la historia asimilada | §6 |
| Q2. Ranking de PODs: ¿qué desviaciones mínimas y plausibles cambian más el resultado macro? | Teatro, ventana y catálogo de intervenciones | Frontera coste–rastro y listas ordenadas, certificadas | §5, §10 |
| Q3. Propagación: dado un POD, ¿qué pasa después y hasta cuándo puede afirmarse algo? | Un POD concreto | Abanico de cada observable, perfil de eficiencia, clase de efecto, semivida y horizonte | §5, §8 |
| Q4. Atribución: ¿por qué? | Resultado de Q3 | Canales que transmiten o amortiguan el efecto, y variables que deciden | §5.6, §6.5 |
| Q5. Ruta a un desenlace: ¿cuál es la historia menos milagrosa que lleva a un desenlace que no ocurrió? | Un desenlace | Factura en nats, su reparto en el tiempo y si existe un POD único | §6.4 |

### 1.4 Forma de una respuesta

Valores ilustrativos, no calculados:

> **Consulta:** I, prospectiva desde t₀. **POD:** el gobernante de P3 sobrevive a la enfermedad de t₀; probabilidad 0,35, coste 1,05 nats. **Régimen «Estado unificado» a +25 años:** 0,62 \[0,48–0,74\] con POD; 0,30 en el abanico sin intervenir; 0,13 en la rama real. **Ganancia dirigida:** 0,73 nats; eficiencia 0,69. **Rastro sobre el régimen:** al menos 0,22 nats. **Clase:** bifurcación. **Semivida del rastro:** 60 años. **Canales:** capacidad fiscal 46 %, cohesión de élites 31 %, comercio 12 %. **Dependencia estructural:** 1,6. **Extrapolación:** baja. **Confianza:** C.

La narración de la línea alternativa es opcional y siempre posterior. Se redactan tres trayectorias muestreadas (mediana, p10 y p90 de un índice macro), etiquetadas como «una muestra posible», nunca como «lo que pasó».

## 2. Axiomas

Los axiomas fijan qué cuenta como respuesta válida. Cada uno lleva su consecuencia operativa: lo que el constructor debe hacer o tiene prohibido.

**Sobre el objeto**

- **A1. La historia real es una muestra, no la ley.** Lo que ocurrió es una realización de un proceso estocástico. *Consecuencia:* el modelo no puede asignar probabilidad cercana a 1 al curso real; si lo hace, está sobreajustado o es teleológico (test de inevitabilidad, §12).
- **A2. Se predicen agregados, no anécdotas.** La señal predecible está en variables macro: población, producción, capacidad fiscal, número y tamaño de Estados, régimen, urbanización. *Consecuencia:* el vector de observables se define antes de simular; los sucesos son medios, no salidas.
- **A3. Las restricciones antes que los agentes.** Calorías, personas, dinero, energía y tiempo se conservan o se presupuestan. *Consecuencia:* toda dinámica respeta identidades contables cerradas, con un test unitario por identidad.
- **A4. Colas declaradas.** El azar de la historia no es todo gaussiano. *Consecuencia:* cada fuente de azar declara su familia y, si es de cola pesada, su índice de cola con intervalo (§3.4).

**Sobre la causalidad**

- **A5. Tres consultas causales.** «¿Qué habría pasado?» son tres preguntas distintas (§4.1). *Consecuencia:* toda salida declara si responde a la consulta I, II o III, y no hay POD sin inferencia previa del estado en t₀.
- **A6. El POD es un cambio de medida admisible.** Es la menor desviación local que el propio modelo considera posible. *Consecuencia:* su coste es una divergencia en nats; el catálogo de intervenciones es cerrado; un POD de coste infinito no existe (§5).
- **A7. Contabilidad de la información.** Un POD no puede dejar más rastro que lo que costó. *Consecuencia:* una eficiencia estimada mayor que 1 es un error, y hay un test que lo comprueba (§5.3).
- **A8. Horizonte de identidad.** El azar solo se comparte entre la línea real y la alternativa mientras sea físicamente insensible al POD. *Consecuencia:* cada fuente declara su tiempo de identidad. En particular, toda persona concebida más de un año después del POD es otra: ningún personaje histórico posterior existe en la línea alternativa. Los vivos en t₀ persisten con sus rasgos inferidos (§4.3).

**Sobre la incertidumbre**

- **A9. La incertidumbre estructural domina.** No sabemos qué teoría es la verdadera. *Consecuencia:* al menos tres modelos rivales por mecanismo crítico; toda respuesta interventiva se da como conjunto sobre los modelos admisibles, no como promedio (§11.4).
- **A10. Distribuciones, no relatos.** *Consecuencia:* ninguna salida sin cuantiles, horizonte, tres capas de incertidumbre separadas y grado de confianza. La prosa va al final, etiquetada como muestra.
- **A11. Honestidad sobre el horizonte.** Cuando la distribución con POD ya no se distingue de la climatológica, la predicción ha muerto. *Consecuencia:* toda salida incluye el horizonte por variable y deja de afirmar más allá.
- **A12. Tríada de validez.** Un hindcast valida predicciones, no intervenciones. *Consecuencia:* ningún resultado interventivo sin su evidencia de suficiencia causal, su índice de extrapolación y su calibración condicional (§13.1).

**Sobre el procedimiento**

- **A13. Trazabilidad total.** *Consecuencia:* cada parámetro declara procedencia (dato, estimado, prior-LLM-ciego, supuesto), prior con rango y referencia. Un parámetro sin procedencia no compila.
- **A14. El LLM compila, no simula.** *Consecuencia:* ninguna llamada a un LLM dentro del bucle de simulación ni del análisis numérico. El LLM propone estructura, elicita priores a ciegas, revisa código y redacta la narración final.
- **A15. Ceguera ante la retrospectiva.** El LLM conoce el final de la historia. *Consecuencia:* el protocolo anti-filtración (§12) es obligatorio, y la fuga se mide.
- **A16. Falsabilidad por módulo.** *Consecuencia:* cada mecanismo tiene al menos un test de hindcast que podría suspender, escrito antes de ajustarlo.
- **A17. Simetría cultural como prior.** *Consecuencia:* las mismas ecuaciones y la misma biblioteca de mecanismos para todas las civilizaciones. Las diferencias entran como parámetros con varianza regional estimada, nunca como reglas ad hoc (§13.6).

## 3. El objeto matemático

Clinamen modela la historia macro como un proceso de Markov híbrido, no homogéneo en el tiempo, con deriva, difusión y saltos. Esa clase es la que resulta de reducir un sistema de muchos individuos a sus variables agregadas.

### 3.1 Estado y observación

El estado x(t) tiene cuatro bloques. El paso es anual por defecto y mensual dentro de ventanas de crisis.

| Bloque | Contenido |
| --- | --- |
| M, macro | Por entidad política y región: población, superficie cultivada, rendimiento, excedente, ingresos fiscales, deuda, tamaño militar, élites aspirantes, urbanización, salario real, nivel técnico por familia de tecnología |
| G, meso | Grafo con pesos: entidades, rutas comerciales, alianzas, vasallajes, fronteras |
| A, actores | Conjunto pequeño de actores salientes (gobernantes, facciones, generales) con rasgos, edad, salud, legitimidad y creencias |
| E, forzamientos | Procesos exógenos: clima forzado, vulcanismo, actividad solar, patógenos que llegan de fuera |

Las observaciones y(t) son funciones ruidosas del estado: lo que registran las fuentes (censos, series de precios, crónicas codificadas), con error de medida explícito, huecos y, para variables codificadas por expertos, un modelo ordinal con desacuerdo entre codificadores.

### 3.2 Generador

La dinámica queda definida por su generador, que actúa sobre cualquier observable f. Para cada modelo rival m y parámetros θ:

```latex
\mathcal{L}_t f(x) = \underbrace{b(x,t)\cdot\nabla f(x)}_{\text{deriva}} + \underbrace{\tfrac12\,\mathrm{tr}\big[a(x,t)\,\nabla^2 f(x)\big]}_{\text{difusión}} + \underbrace{\sum_j \lambda_j(x,t)\int \big[f(x\oplus z)-f(x)\big]\,\nu_j(dz\mid x,t)}_{\text{saltos}}
```

- **Deriva b.** Los mecanismos deterministas: demografía, acumulación, fiscalidad, difusión técnica.
- **Difusión a = σσᵀ.** La contingencia agregada de muchos sucesos pequeños.
- **Saltos.** Sucesos discretos de la fuente j, con tasa λⱼ y marca z: una muerte, una batalla, una sucesión, la llegada de una epidemia, una invención, una decisión. El operador ⊕ incluye cambios de estructura: fusión o escisión de entidades.
- **Dependencia de t.** Entra por los forzamientos exógenos.

Desenrollado en el tiempo, el grafo causal es acíclico; los bucles (guerra, impuestos, guerra) existen entre pasos. Las identidades contables del axioma A3 son invariantes del generador: funciones c(x) cuya evolución es una fuente conocida.

### 3.3 De dónde sale el ruido: granularidad

El azar individual casi desaparece al agregar, y eso obliga a explicar por qué la historia es contingente. En un proceso de población con N individuos intercambiables, las densidades convergen a una ecuación diferencial y las fluctuaciones decaen como N^(−1/2) (Kurtz, 1970 y 1971). Un imperio de 60 millones no debería tener ruido demográfico apreciable.

Lo tiene porque los individuos no pesan igual. Si la variable macro es una suma ponderada de choques idiosincrásicos independientes:

```latex
M = \sum_{i=1}^{N} w_i\,\xi_i,\qquad \mathrm{Var}(M) = \sigma_\xi^2 \sum_i w_i^2 = \sigma_\xi^2\, H
```

H es el índice de Herfindahl de la influencia. Con pesos iguales H = 1/N y el ruido se desvanece. Con poder concentrado H no decae y el azar de pocas personas llega intacto a la escala macro. Es el argumento de Gabaix (2011) para las grandes empresas y el ciclo económico, trasladado al poder político.

Tesis estructural: **una sociedad es contingente en la medida en que es jerárquica, está expuesta a choques comunes o está cerca de una inestabilidad.** Las cuatro fuentes de ruido macro son:

1. Concentración de decisiones (H alto): monarcas, generales, cortes.
2. Choques comunes que no se promedian: clima, epidemias.
3. Interacciones de desenlace binario o de cola pesada: batallas, cascadas de revuelta.
4. Amplificación dinámica: cerca de una divisoria, un ruido pequeño basta.

La tesis es contrastable. Jones y Olken (2005) hallan que la muerte natural de un líder cambia el crecimiento en las autocracias y no en las democracias, como predice H.

### 3.4 Tres familias de ruido

Cada fuente de azar declara a qué familia pertenece, porque de ello depende cómo se cruza entre regímenes (§7.3).

| Familia | Ejemplos | Forma | Parámetro clave |
| --- | --- | --- | --- |
| Difusiva | Agregado de sucesos pequeños, cosechas ordinarias | Gaussiana, matriz a | Intensidad |
| Saltos de cola ligera | Sucesiones, batallas ordinarias, muertes, decisiones | Poisson con marcas acotadas | Tasa λⱼ |
| Saltos de cola pesada | Tamaño de guerras, mortalidad epidémica, cascadas | Marcas con cola de potencia | Índice de cola αⱼ |

El tamaño de las guerras sigue una ley de potencia (Richardson, 1948; Cirillo y Taleb, 2016; Clauset, 2018) y la mortalidad de las grandes epidemias también tiene cola pesada (Cirillo y Taleb, 2020). El índice αⱼ se estima con teoría de valores extremos sobre el panel y entra siempre en el análisis de sensibilidad.

### 3.5 De dónde sale la difusión: separación de escalas

Las variables rápidas no desaparecen: se integran como ruido rojo sobre las lentas. Es el programa de Hasselmann (1976) para el clima, donde el tiempo atmosférico actúa como ruido sobre el océano. Sea X lento e Y rápido, con cociente de escalas ε:

```latex
dX = F(X,Y)\,dt,\qquad dY = \tfrac{1}{\varepsilon}\,g(X,Y)\,dt + \tfrac{1}{\sqrt{\varepsilon}}\,\beta(X,Y)\,dW
```

Si Y mezcla rápido hacia una medida μₓ para cada X congelado, cuando ε es pequeño X obedece una ecuación cerrada (promediado y homogeneización; Pavliotis y Stuart, 2008):

```latex
dX = \bar F(X)\,dt + \sqrt{\varepsilon}\,\Sigma(X)\,dW,\qquad \bar F(x)=\int F(x,y)\,\mu_x(dy),\qquad \Sigma\Sigma^{\top}(x) = 2\int_0^\infty \mathrm{Cov}_{\mu_x}\!\big(F(x,Y_0),F(x,Y_s)\big)\,ds
```

Intrigas de corte, campañas y cosechas olvidan su pasado en años. Su efecto integrado sobre las variables lentas es una difusión cuya intensidad da la fórmula de Green y Kubo de la derecha.

Cuando ε no es pequeño, la reducción exacta (Mori y Zwanzig) deja un término de memoria y el estado macro deja de ser markoviano. Consecuencia operativa: el estado se amplía con variables de memoria (deuda, legitimidad acumulada, estructura de cohortes de élite, edad de las instituciones) hasta que los residuos sean blancos. El test de Chapman y Kolmogórov sobre el modelo ajustado es una puerta de aceptación.

### 3.6 De dónde salen los regímenes

Sin retroalimentación positiva no hay equilibrios alternativos, sea cual sea el valor de los parámetros. Es la conjetura de Thomas, demostrada por Soulé (2003): un sistema diferenciable solo admite varios equilibrios no degenerados si el grafo de signos de su jacobiano contiene un circuito positivo. Un circuito negativo es necesario para oscilaciones sostenidas, como los ciclos seculares.

Esto da una criba estructural previa a cualquier simulación. Se dibuja el grafo de signos de la biblioteca de mecanismos y se listan sus circuitos positivos: rendimientos crecientes fiscal-militares, aglomeración urbana, aprendizaje técnico, coordinación y legitimidad. Solo ahí pueden nacer regímenes alternativos, y solo ahí tiene sentido buscar divisorias.

## 4. Causalidad entre mundos

«¿Qué habría pasado?» son tres preguntas distintas con tres estatus epistemológicos distintos. Solo la primera es validable; las otras dos dependen de un supuesto sobre qué azar comparten la línea real y la alternativa, y se informan con cotas.

### 4.1 Las tres consultas

En forma estructural, el estado avanza con una función del estado previo, del forzamiento y de un azar exógeno U con una componente por fuente: x(t+1) = F(x(t), e(t), U(t)). Un POD sustituye el mecanismo de una componente en t₀.

| Consulta | Pregunta | Condiciona en | Supuesto entre mundos | Estatus |
| --- | --- | --- | --- | --- |
| I. Prospectiva interventiva | Visto desde t₀, ¿cómo cambia el abanico de futuros? | Estado en t₀ y leyes | Ninguno | Identificada dado el modelo; validable (§13) |
| II. Contrafactual retrospectiva | Sabiendo todo lo que ocurrió después, ¿qué habría ocurrido? | Historia completa hasta T | Qué azar persiste en el otro mundo | Depende del acoplamiento; se da con cotas |
| III. Causalidad singular | ¿Fue el suceso real necesario, o suficiente, para el desenlace real? | El suceso y el desenlace reales | El mismo | Cotas sobre la probabilidad de necesidad |

```latex
\text{I: } P\big(Y_T \mid do(a),\,x_{t_0},\theta\big)\ \text{frente a}\ P\big(Y_T \mid x_{t_0},\theta\big)
\qquad \text{II: } P\big(Y_T^{\,a} \mid y_{0:T}\big)
\qquad \text{III: } PN = P\big(Y^{a'}\neq y \mid A=a,\ Y=y\big)
```

Ejemplo con la crisis Song–Jin. Consulta I: desde 1120, ¿cómo cambia el abanico si Song no pacta con Jin contra Liao? Consulta II: sabiendo que Kaifeng cayó en 1127 y conociendo las sequías y erupciones posteriores, ¿qué habría sido del norte sin ese pacto? Consulta III: ¿fue el pacto necesario para la pérdida del norte?

La I es la que ordena PODs y la que se valida. La II es la que entiende un historiador. La III es la definición rigurosa de «POD jugoso»: un suceso con probabilidad de necesidad alta para un desenlace grande.

### 4.2 Qué depende del acoplamiento y qué no

**Proposición 1.** Sean Pᵃ y P las leyes del observable en el mundo con POD y sin él.

1. Todo funcional de las dos marginales es independiente del acoplamiento: medias, cuantiles, probabilidades de régimen, divergencia KL, distancia de energía, Wasserstein.
2. Todo funcional de la ley conjunta de (Yᵃ, Y) depende de él. Su rango sobre acoplamientos es un problema de transporte óptimo. En particular, la menor distancia pareada posible es la de Wasserstein:

```latex
\inf_{\text{acoplamientos}}\ \mathbb{E}\,\big\|Y^{a}-Y\big\| \;=\; W_1\big(P^{a},P\big)
```

3. Si el POD es un sorteo exógeno dado el estado, la probabilidad de necesidad queda acotada solo por las marginales (Tian y Pearl, 2000):

```latex
\max\Big\{0,\ 1-\frac{P(y\mid do(a'))}{P(y\mid do(a))}\Big\}\ \le\ PN\ \le\ \min\Big\{1,\ \frac{P(y'\mid do(a'))}{P(y\mid do(a))}\Big\}
```

Regla que se sigue: los efectos se informan con magnitudes marginales. Las magnitudes pareadas (diferencia entre gemelos de una misma partícula, fracción de mundos en que el desenlace cambia) se informan siempre con el acoplamiento bajo el que se calcularon.

### 4.3 Horizonte de identidad entre mundos

Una fuente de azar se comparte entre mundos mientras su realización sea físicamente insensible a las consecuencias del POD, y no más. Cada fuente j tiene un tiempo de identidad τⱼ: antes de t₀ + τⱼ ambos mundos usan el mismo sorteo; después, sorteos independientes.

| Fuente de azar | Qué la desacopla | Tiempo de identidad τⱼ | Tratamiento |
| --- | --- | --- | --- |
| Forzamiento volcánico, solar y orbital | Nada humano | Infinito | Compartido siempre; en la consulta II se fija a lo observado |
| Variabilidad interna de la atmósfera (tiempo, cosecha de cada año) | Caos atmosférico: cualquier perturbación se amplifica hasta la escala sinóptica | Semanas, en todo el planeta | Independiente desde la primera campaña agrícola; solo se comparte la parte forzada |
| Modos oceánicos lentos | Acoplamiento con la atmósfera | De uno a pocos años | Correlación decreciente |
| Lotería genética de los concebidos | Cualquier cambio en el instante de la concepción; el tiempo atmosférico basta | Alrededor de un año, en todo el planeta | Re-sorteo de identidad y rasgos |
| Muerte de los vivos en t₀ | Cambios de exposición: viajes, guerra, contagio | Años; se propaga por la red de contacto | Se comparte la fragilidad intrínseca; se re-sortea la exposición |
| Salto y evolución de patógenos | Redes de contacto humano y animal | Décadas, según el canal | Se comparte el reservorio; se re-sortea la fecha |
| Sorteo de decisión de un actor vivo | Cambio de su información o contexto | Hasta que el POD alcance su contexto | Ruido de Gumbel común (§9.4) |
| Invención | Cambios en la red de practicantes | Décadas para la tasa; un año para el inventor | Se comparte la tasa; se re-sortea la identidad |

**Fundamento físico.** La atmósfera es caótica con un tiempo de duplicación de errores de días (Lorenz, 1969). Cualquier POD con consecuencias físicas, por pequeñas que sean, cambia el tiempo atmosférico del planeta en semanas. De ahí salen a la vez dos reglas: las cosechas no se comparten entre mundos más allá del primer año, y las identidades de los concebidos se re-sortean en todo el mundo, también donde el POD no tiene influencia macro.

**Realización frente a ley.** Re-sortear identidades lejos del POD cambia las realizaciones, no las distribuciones. Con un POD en China en 1127, Colón no nace; la distribución de fechas del contacto transatlántico no cambia hasta que llegue una influencia macro. En la consulta I esto es invisible. En la II significa que las regiones lejanas son un sorteo fresco desde su estado en t₀, no su trayectoria real.

**Líderes posteriores.** Los que llegan al poder tras el horizonte de identidad se muestrean de la distribución de rasgos de su época, cultura y regla de selección (§9.7).

**Regla de informe.** Las consultas II y III se calculan bajo dos acoplamientos admisibles: el mínimo físico (la tabla) y el máximo (todo lo que no desciende causalmente del POD se comparte siempre). Se añaden las cotas de la Proposición 1. Si las conclusiones cambian entre ambos, el resultado es «dependiente de acoplamiento» y se dice.

### 4.4 Qué se infiere en cada consulta

| Consulta | Leyes θ | Estado en t₀ | Azar posterior a t₀ |
| --- | --- | --- | --- |
| I | Con toda la historia | Suavizado con toda la historia | Fresco en ambos brazos |
| I, variante de hindcast | Solo hasta t₀ | Filtrado hasta t₀ | Fresco |
| II y III | Con toda la historia | Suavizado | Posterior de las fuentes compartidas; fresco en las demás |

Usar la historia posterior a t₀ para el estado en t₀ es legítimo: un colapso fiscal en 1140 informa de una fragilidad oculta en 1125. Por la propiedad de Markov, dado el estado en t₀ el azar anterior es irrelevante. El brazo sin POD de la consulta I no reproduce la historia real: es el abanico de historias compatibles con el estado en t₀, y contra él se mide el efecto.

### 4.5 Gemelos: implementación

Cada partícula (un estado y unos parámetros compatibles con los datos) genera dos mundos desde t₀: uno sin intervención y otro con POD.

- **Generador por contador.** Números aleatorios con semilla indexada por (partícula, fuente, entidad, paso), del tipo Philox o Threefry. Nunca un flujo secuencial único: se desincroniza en cuanto un gemelo hace un sorteo que el otro no hace.
- **Azar compartido según la tabla.** Cada fuente usa el mismo índice en ambos gemelos hasta su tiempo de identidad y un índice distinto después.
- **Para qué sirve en la consulta I.** El azar compartido reduce la varianza de las diferencias de medias en uno o dos órdenes de magnitud, sin alterar su valor esperado.
- **Test obligatorio.** Un POD nulo produce efecto exactamente cero, bit a bit.

## 5. El POD: coste, rastro y eficiencia

Un POD no es un valor que se impone: es un cambio en la ley de probabilidad de un sorteo. Con esa definición, su coste y su efecto se miden en la misma unidad, el nat, y el efecto nunca puede superar al coste.

### 5.1 Catálogo tipado de intervenciones

Cada tipo de intervención es un operador con parámetros, dominio de aplicación y modelo de plausibilidad. El catálogo es cerrado: no hay PODs mágicos.

| Tipo | Ejemplo, enunciado como suceso | Modelo de plausibilidad |
| --- | --- | --- |
| Supervivencia o muerte de un actor | El gobernante no muere ese año | Tablas de vida de la época y salud inferida |
| Resultado de una batalla | Gana el bando que perdió | Combate de Lanchester estocástico y tasa base de sorpresas según la razón de fuerzas |
| Decisión dentro del conjunto factible | El actor elige su segunda estrategia | Probabilidad de elección (§9.3) |
| Clima puntual | Cosecha normal en lugar de mala | Climatología reconstruida de la región |
| Llegada de una epidemia | Llega al menos cinco años después | Difusión por la red comercial |
| Momento de una innovación | La técnica aparece al menos veinte años antes | Tasa de invención del módulo tecnológico |
| Sucesión | Sobrevive el heredero | Demografía dinástica |
| Información | Un mensaje llega antes, después o no llega | Tiempos y pérdidas de correo sobre el grafo de rutas |

### 5.2 Definición, admisibilidad y coste

Sea P la ley del modelo sobre trayectorias futuras desde el estado en t₀, y K el núcleo de transición en t₀ para un bloque de variables.

- **POD.** Una ley Q idéntica a P salvo en que K se sustituye por otro núcleo K′.
- **Admisible.** Si K′ es absolutamente continuo respecto a K: solo asigna probabilidad a lo que el propio modelo considera posible.
- **Coste.** La divergencia de Kullback y Leibler entre ambos núcleos:

```latex
c(Q) = \mathrm{KL}\big(K' \,\|\, K\big) = \int \log\frac{dK'}{dK}\,dK'
\qquad\text{y, para un POD-suceso } K'=K(\cdot\mid A):\quad c = -\log K(A)
```

Para un POD-suceso el coste es su sorpresa. La definición general tiene cuatro propiedades que la hacen la medida correcta:

- No depende de unidades ni de la parametrización.
- Es aditiva: los costes de PODs independientes o sucesivos se suman.
- Tiene lectura frecuentista (Sanov): la probabilidad de que N repeticiones del sorteo parezcan venir de K′ decae como exp(−N·c).
- Para un desplazamiento gaussiano v da c = ½ vᵀa⁻¹v, la acción de Onsager y Machlup.

Dos reglas de uso. En variables continuas el POD se enuncia como suceso o como inclinación de la ley con KL finita, nunca como un valor puntual: el −log de una densidad depende de las unidades y no es una sorpresa. Y con incertidumbre sobre el estado y los parámetros, el coste es la media posterior del coste por partícula, no el −log de la probabilidad media.

### 5.3 Teorema 1: cota de información

**Enunciado.** Sea Y cualquier observable del futuro: el vector macro en T, un indicador de régimen o una trayectoria entera. Para todo POD admisible:

```latex
0 \;\le\; e_Y(Q) := \mathrm{KL}\big(Q_Y \,\|\, P_Y\big) \;\le\; c(Q)
\qquad\Longrightarrow\qquad
\Lambda_Y(Q) := \frac{e_Y(Q)}{c(Q)} \in [0,1]
```

**Demostración.** Q y P comparten todos los núcleos salvo el de t₀. Por la regla de la cadena, su divergencia sobre trayectorias completas es exactamente c. Y es función de la trayectoria, y la divergencia KL no aumenta al aplicar una función (desigualdad de procesamiento de datos). Con incertidumbre sobre el estado, la convexidad conjunta de KL da la cota con el coste medio. ∎

**Lectura.** e es el **rastro** del POD: cuántos nats distinguen el futuro con POD del abanico sin él. Λ es la **eficiencia de palanca**: la fracción de la sorpresa invertida que sigue siendo legible en Y.

- Λ = 1: el POD se lee íntegro en el macroestado. Bifurcación limpia.
- Λ = 0: el atractor lo ha absorbido.
- Para el estado completo, Λ no puede crecer con T. Para un observable macro sí puede crecer al principio: la información migra de lo micro a lo macro (§8.2).

**Test contable.** Una estimación con Λ > 1 delata un error numérico o de muestreo. Es una identidad de conservación y se comprueba como las contables.

**Contra qué se compara.** P es el abanico desde t₀, que contiene la rama del POD con su peso natural. El contraste rama contra rama (murió frente a sobrevivió) se informa aparte. No tiene cota propia, pero cada rama la cumple frente al abanico.

### 5.4 El límite de POD pequeño

Para una familia de PODs que desplazan el sorteo en una dirección v, coste y rastro son cuadráticos en v:

```latex
c(v) \approx \tfrac12\, v^{\top} I_0\, v,\qquad e_Y(v) \approx \tfrac12\, v^{\top} I_Y\, v,\qquad I_Y \preceq I_0
\qquad\Longrightarrow\qquad
\Lambda(\hat v)=\frac{\hat v^{\top} I_Y\,\hat v}{\hat v^{\top} I_0\,\hat v}
```

I₀ es la información de Fisher del estado inmediato sobre v, e I\_Y la del observable futuro. La eficiencia es finita y solo depende de la dirección. Sus máximos son los vectores propios generalizados del par (I\_Y, I₀): las **direcciones de máxima palanca**, análogas a los vectores singulares con que se inicializan los ensembles de predicción meteorológica.

Advertencia de escala: para empujones pequeños, el cambio en una probabilidad crece como la raíz del coste, no como el coste. Un cociente «efecto bruto entre sorpresa» diverge cuando el POD tiende a cero y premiaría siempre al POD más insignificante. Por eso la palanca se mide con Λ, nats sobre nats.

### 5.5 Versión dirigida a un desenlace

Para un desenlace B («régimen unificado en +100») y un POD-suceso A con sorpresa s\_A, la ganancia en log-probabilidad es:

```latex
g(A;B) = \log P(B\mid A) - \log P(B) = s_A + \log P(A\mid B) \;\le\; s_A
```

Sale de la regla de Bayes en una línea. Tres consecuencias:

1. **Eficiencia dirigida.** Λ\_B = g / s\_A vale como máximo 1, y vale 1 solo si P(A | B) = 1: toda ruta hacia B pasa por A. Mide la necesidad prospectiva del POD. Si es negativa, el POD estorba.
2. **Factura mínima de milagro.** Ningún conjunto de PODs garantiza B por menos de −log P(B) nats en total. Una ucronía cuyo desenlace tiene probabilidad e⁻¹² vista desde t₀ exige al menos 12 nats, se repartan como se repartan.
3. **Retrodicción.** P(A | B) responde a la pregunta inversa: si B ocurrió, ¿con qué probabilidad fue por A?

### 5.6 Atribución por mediación interventiva

El reparto del efecto entre canales (Q4) se hace sin supuestos entre mundos. Para cortar el canal m en el mundo con POD, su entrada se sustituye por un sorteo de la distribución que esa entrada tiene en el mundo sin POD. Es el análogo interventivo de los efectos indirectos (VanderWeele, Vansteelandt y Robins, 2014).

Se mide cuánto cae el rastro y se reparte con valores de Shapley sobre los canales. Con k canales hay 2^k combinaciones; por encima de 8 se aproxima por muestreo de permutaciones. Como solo usa marginales, el resultado no depende del acoplamiento.

### 5.7 Estimación del rastro y efecto por observable

**Rastro.** El coste se conoce exacto por construcción. El rastro se acota por debajo con la fórmula variacional de Donsker y Varadhan, válida para cualquier función f:

```latex
e_Y \;\ge\; \mathbb{E}_Q\big[f(Y)\big] - \log \mathbb{E}_P\big[e^{f(Y)}\big]
```

Cualquier clasificador entrenado para distinguir los dos ensembles da una cota inferior certificada, y sus variables más influyentes dicen qué observables llevan el rastro. Así Λ queda encajada entre una cota inferior estimada y el techo exacto de 1.

**Efecto por observable.** Para lectura humana se informa además, por observable y horizonte, la diferencia de medias entre brazos normalizada por la dispersión climatológica (§8.4), y para observables categóricos la diferencia de probabilidad por categoría. Si la fuente dominante es de cola pesada, la normalización usa una escala de cuantiles, porque la varianza puede no existir.

## 6. Geometría de la contingencia

Un solo campo escalar, el committor de tiempo finito h, contiene las respuestas a Q1, Q2 y Q5: cuándo se decidió un desenlace, qué fuente de azar lo decidió, dónde habría que empujar para cambiarlo y cuánto cuesta la ruta alternativa. Dos teoremas lo descomponen de forma exacta.

### 6.1 Committor de tiempo finito

Para un desenlace B fijado en el horizonte T, h es la probabilidad de B vista desde cada estado y cada instante. Cumple la ecuación retrógrada de Kolmogórov con el generador de §3.2:

```latex
h(x,t) = P\big(B \mid X_t = x\big),\qquad \partial_t h + \mathcal{L}_t h = 0,\qquad h(\cdot,T) = \mathbf{1}_B
```

Depende del tiempo porque la dinámica tiene tendencia y forzamiento. La versión «B antes que A» usa la misma ecuación con condiciones de contorno en A y B. Con varios regímenes se usa un h por régimen: el vector de probabilidades de destino πⱼ.

### 6.2 Teorema 2: la martingala del destino

**Enunciado.** El proceso M(t) = h(X(t), t), la probabilidad de B dada la historia hasta t, es una martingala. Por tanto la incertidumbre inicial sobre B se reparte exactamente entre los instantes:

```latex
\underbrace{M_0\,(1-M_0)}_{\text{incertidumbre inicial sobre } B} \;=\; \sum_{t<T} \underbrace{\mathbb{E}\big[(M_{t+1}-M_t)^2\big]}_{\rho_t\ =\ \text{contingencia resuelta en } t}
```

**Demostración.** M es martingala por la propiedad de la torre, y termina en el indicador de B. Los incrementos de una martingala son ortogonales, así que la varianza del valor final es la suma de las varianzas de los incrementos. ∎

En tiempo continuo, la tasa de resolución en el estado x es aditiva por fuente de azar:

```latex
r(x,t) = \underbrace{\nabla h^{\top} a\,\nabla h}_{\text{difusión}} \;+\; \sum_j \underbrace{\lambda_j(x,t)\int \big[h(x\oplus z,t)-h(x,t)\big]^2\,\nu_j(dz)}_{\text{saltos de la fuente } j}
```

El resultado es el **presupuesto de contingencia** de B: una tabla, instante por fuente, cuyas celdas suman la incertidumbre inicial. Es la salida de Q1.

**Ambigüedad y resolución.** El índice de ambigüedad b(t) = 1 − Σπⱼ² mide lo que queda por decidir: vale 0 cuando el futuro está decidido y es máximo cuando todos los regímenes son igual de probables. Su caída esperada es la resolución:

```latex
\mathbb{E}\big[b_{t+1}\mid \mathcal{F}_t\big] = b_t - \sum_j \mathbb{E}\big[(\Delta\pi_j)^2 \mid \mathcal{F}_t\big]
```

| b (lo que queda por decidir) | r (lo que se decide ahora) | Lectura |
| --- | --- | --- |
| Alto | Bajo | Futuro abierto, nada lo está decidiendo: calma indecisa |
| Alto | Alto | Momento decisivo: aquí están los PODs |
| Bajo | Bajo | Decidido |

Un momento de bifurcación es un pico de r con b alto, no un pico de b a secas.

**Esperado frente a realizado.** r es lo que se esperaba resolver en t. El cuadrado del incremento real de M es lo que resolvió el sorteo que de verdad salió. «La historia tomó la rama improbable» significa que ese incremento cayó en la cola de su distribución condicional. Esos tramos son prioritarios para Q2.

**Individuo frente a estructura.** La fracción del presupuesto que aportan las fuentes de tipo actor (decisiones, muertes, sucesiones) es la respuesta cuantitativa al debate del gran hombre. Se calcula por desenlace y por época; no se fija a mano.

### 6.3 El mismo campo dice dónde empujar

Para un empujón pequeño v en el estado x, el cambio de probabilidad es ∇h·v y el coste es ½ vᵀa⁻¹v. El mejor empujón con presupuesto c va en la dirección a∇h y consigue:

```latex
\max_{v:\ c(v)\le c}\ \Delta h \;=\; \sqrt{2c\;\nabla h^{\top} a\,\nabla h} \;=\; \sqrt{2c\; r_{\text{dif}}(x,t)}
```

La tasa de resolución difusiva es el cuadrado de la máxima palanca por raíz de nat. El mapa de cuándo se decidió la historia y el mapa de dónde es más barato cambiarla son el mismo mapa. Para las fuentes de salto, los candidatos son las marcas alternativas z ordenadas por su cambio de h frente a su coste.

### 6.4 Teorema 3: la ruta más barata a un desenlace

**Enunciado.** Entre todas las leyes Q admisibles que garantizan B, la de menor coste total es el proceso condicionado a B. Su coste es −log P(B), y es un proceso de Markov con núcleos inclinados por h (transformada h de Doob):

```latex
\min_{Q \ll P,\ Q(B)=1} \mathrm{KL}(Q\,\|\,P) = -\log P(B),\qquad Q^{*}=P(\cdot\mid B),\qquad K^{h}_t(x,dx') = K_t(x,dx')\,\frac{h(x',t+1)}{h(x,t)}
```

El coste se reparte en el tiempo, y en tiempo continuo también por fuente:

```latex
-\log P(B) = \sum_{t<T}\kappa_t,\qquad \kappa_t = \mathbb{E}_{Q^{*}}\Big[\mathrm{KL}\big(K^{h}_t \,\|\, K_t\big)(X_t)\Big],\qquad
\text{tasa: } \tfrac12\,\nabla\!\log h^{\top} a\,\nabla\!\log h + \sum_j \lambda_j\!\int\! \varphi\!\Big(\tfrac{h(x\oplus z)}{h(x)}\Big)\nu_j(dz),\quad \varphi(u)=u\log u-u+1
```

**Demostración.** Para toda Q concentrada en B, KL(Q ‖ P) = KL(Q ‖ P(· | B)) − log P(B), y el primer término se anula solo en Q\*. La densidad de Q\* respecto a P es un producto telescópico de cocientes de h, lo que da los núcleos. El reparto es la regla de la cadena de KL. ∎

**Lectura.** El perfil κ dice dónde tendría que haberse desviado la historia para llegar a B, y cuántos nats cuesta cada desvío. Es la salida de Q5.

- **κ concentrado** en un instante y una fuente: existe un POD clásico para B, y es ese.
- **κ repartido** en décadas y fuentes: B exige una conjura de circunstancias. La respuesta honesta a «¿cuál es el POD para B?» es «ninguno», y el sistema lo dice con un índice de concentración.
- **Límite de ruido gaussiano pequeño:** Q\* se concentra en una sola trayectoria, el instantón, y su coste tiende a la acción de Freidlin y Wentzell. La altura de la barrera entre regímenes (el cuasi-potencial) es ese límite, y se calcula por acción mínima geométrica sobre un emulador diferenciable.

**Dualidad.** El Teorema 2 mira el ensemble real y dice cuándo se resolvió la incertidumbre. El Teorema 3 mira el ensemble condicionado a B y dice dónde habría que gastar la sorpresa. Para un desenlace que no ocurrió, el segundo es el mapa de su ucronía más barata.

### 6.5 Coordenada de reacción y cálculo de h

h es la mejor variable unidimensional para seguir la transición hacia B: toda la información del estado relevante para B está en ella. Una regresión dispersa del logit de h sobre las variables macro dice qué pocas variables deciden. Es la respuesta estructural a Q4.

Tres vías de cálculo, de más barata a más cara:

| Vía | Cómo | Cuándo |
| --- | --- | --- |
| Regresión sobre el ensemble | Clasificación probabilística: predecir el indicador de B desde el estado actual, con una regla de puntuación propia | Por defecto; su calibración se comprueba como la de cualquier pronóstico |
| Disparos | Desde cada estado de la trayectoria asimilada, unas 200 réplicas con azar fresco | Validación en los puntos clave |
| División multinivel adaptativa | Muestreo de sucesos raros; genera directamente muestras de Q\*, con h como función de importancia óptima | Desenlaces raros que los disparos no ven |

## 7. Regímenes y transiciones

Hay tres formas distintas de cambiar de régimen y dos formas distintas de cruzar una barrera. Solo algunas combinaciones dejan sitio a un POD, y cada una pide sus propias herramientas.

### 7.1 Regímenes descubiertos, no impuestos

Los regímenes salen de la dinámica del modelo, no de nuestras categorías. Así se evita la teleología.

1. **Ensemble largo.** Se simula desde la posterior de la historia real y desde la climatología (§8.4).
2. **Coordenadas intensivas.** Cada trayectoria se proyecta a cocientes y proporciones (per cápita, cuotas, razones), preferiblemente interpretables. La técnica y la población total actúan como parámetros lentos que deforman el paisaje.
3. **Microestados.** Discretización por k-medias, con k entre 100 y 500.
4. **Operador de transferencia.** Matriz de transición entre microestados con un retardo de 5 a 25 años, elegido donde los tiempos implícitos se estabilicen. Dependiente del tiempo si el forzamiento lo exige.
5. **Conjuntos metaestables.** Agrupación por vectores de Schur (GPCCA; Reuter y otros, 2018), que no exige reversibilidad. Con forzamiento fuerte, conjuntos coherentes de tiempo finito (Froyland, 2013) y teoría de caminos de transición de tiempo finito (Helfmann y otros, 2020).
6. **Nombre al final.** El sistema entrega conjuntos y centroides. «Imperio unificado», «fragmentación» o «Estado fiscal-militar» se ponen después.

Variables, retardo y número de regímenes se eligen maximizando la puntuación variacional VAMP (Wu y Noé, 2020). Cada modelo rival descubre sus propios regímenes: antes de comparar resultados entre modelos hay que emparejarlos, por transporte óptimo entre conjuntos.

### 7.2 Tres mecanismos de vuelco

La clasificación es de Ashwin, Wieczorek, Vitolo y Cox (2012) para el clima. Cada tipo tiene una firma distinta en el presupuesto de contingencia.

| Tipo | Qué ocurre | Ejemplo histórico | Señal temprana | Contingencia del desenlace | PODs |
| --- | --- | --- | --- | --- | --- |
| B, por bifurcación | Una variable lenta erosiona la cuenca hasta que desaparece | Presión demográfico-estructural, agotamiento de suelos, deuda | Sí: suben varianza y autocorrelación | Baja | Caros: hay que mover la variable lenta |
| N, por ruido | Un choque saca al sistema de una cuenca que sigue existiendo | Muerte de un gobernante, una batalla, una epidemia | No | Alta | Baratos: aquí viven los PODs clásicos |
| R, por velocidad | El entorno cambia más deprisa de lo que el sistema se adapta | Cambio climático abrupto, apertura súbita de un contacto | No | Media | Actúan sobre el ritmo, no sobre el nivel |

**Ventana de vulnerabilidad.** El caso histórico típico es mixto: B erosiona la barrera y N dispara el cruce. Entonces el qué está casi decidido y el cuándo es contingente. Es la forma rigurosa de la equifinalidad.

Una afirmación como «si César sobrevive, la República cae igual» nunca es un supuesto de entrada. Es una salida con dos números. Uno, la probabilidad de transición antes de T en cada brazo: si coinciden, hay equifinalidad. Dos, la distribución de la fecha de transición en cada brazo: su desplazamiento es el efecto real del POD.

**Señales tempranas como contraste.** A las series reales se les aplican los indicadores de desaceleración crítica: subida de la autocorrelación de retardo 1, de la varianza y de la asimetría en ventanas móviles. Solo preceden a los vuelcos de tipo B. Su presencia indica componente estructural y rebaja la jugosidad esperada. Su ausencia no refuta una divisoria: es lo esperado en un vuelco de tipo N.

### 7.3 Colas ligeras y colas pesadas

Con ruido de cola ligera se cruza una barrera sumando muchos empujones pequeños. Con ruido de cola pesada se cruza de un solo salto. Para un sistema en un pozo de profundidad ΔV, a distancia d del borde de la cuenca, con ruido de amplitud σ:

```latex
\text{cola ligera (Kramers):}\quad \log \mathbb{E}\,\tau \;\propto\; \frac{\Delta V}{\sigma^{2}}
\qquad\qquad
\text{cola pesada de índice } \alpha\ \text{(Imkeller y Pavlyukevich, 2006):}\quad \mathbb{E}\,\tau \;\propto\; \Big(\frac{d}{\sigma}\Big)^{\alpha}
```

|  | Cola ligera | Cola pesada |
| --- | --- | --- |
| Tiempo de salida | Exponencial en la barrera | Polinómico |
| Qué protege al régimen | La altura de la barrera | La anchura de la cuenca |
| Por dónde se sale | Por la silla, siguiendo el instantón | Por cualquier punto, de un salto |
| Perfil κ del Teorema 3 | Repartido en el tiempo | Concentrado en un suceso |
| ¿Existe un POD clásico? | Rara vez: hace falta una conjura | Sí: la presencia, ausencia o fecha del gran choque |
| Herramienta | Cuasi-potencial y acción mínima | División multinivel sobre el modelo completo |

La historia está en régimen mixto (§3.4). Tres consecuencias operativas:

- Cada régimen se caracteriza con dos números de resiliencia, profundidad y anchura.
- El cuasi-potencial solo se calcula para fuentes de cola ligera.
- Si α < 2 la varianza es infinita y las normalizaciones usan escalas de cuantiles. Los teoremas de §5 y §6 no se ven afectados: h está acotado.

### 7.4 Tres estructuras que dan memoria permanente

Un POD solo deja rastro permanente si el sistema tiene alguna estructura no ergódica. Hay tres, y cada mecanismo de la biblioteca declara cuáles contiene.

| Estructura | Modelo canónico | Ejemplos | Memoria del POD |
| --- | --- | --- | --- |
| Metaestabilidad | Doble pozo con ruido | Unificación frente a fragmentación | Larga, no eterna: dura el tiempo de salida |
| Refuerzo | Urna de Pólya; rendimientos crecientes (Arthur, 1989) | Estándares técnicos, lenguas francas, capitales, rutas | Permanente y continua: las primeras extracciones fijan el límite |
| Barrera absorbente | Extinción en un proceso de ramificación | Fin de una dinastía, de una lengua, de un Estado; saber que no se desaprende | Permanente y discreta |

En la urna de Pólya la proporción converge a un límite aleatorio que depende para siempre de las primeras bolas. Es el modelo más simple de un POD que nunca se borra. Sin ninguna de las tres estructuras, la eficiencia de todo POD tiende a cero (§8).

## 8. Memoria y predictibilidad

Un POD perdura si y solo si desplaza los modos lentos del sistema. La duración de su rastro la fija el espectro del operador de transferencia, que puede estimarse sin aplicar ningún POD.

### 8.1 Descomposición espectral

En un tramo aproximadamente autónomo, el operador de transferencia tiene escalas de tiempo t₁ > t₂ > … con funciones propias φₖ (observables) y ψₖ (densidades). El efecto de un POD sobre la media de cualquier observable g en el horizonte T es:

```latex
\mathbb{E}_Q\big[g(X_T)\big]-\mathbb{E}_P\big[g(X_T)\big] = \sum_{k\ge 1} e^{-(T-t_0)/t_k}\;\Delta\varphi_k\;\langle g,\psi_k\rangle,
\qquad \Delta\varphi_k = \mathbb{E}_{K'}[\varphi_k]-\mathbb{E}_{K}[\varphi_k]
```

**Proposición 2.** A horizontes mucho mayores que t(m+1), el efecto de un POD sobre cualquier observable queda determinado por m números: sus desplazamientos Δφ₁, …, Δφₘ sobre las m funciones propias lentas. Con dos regímenes metaestables, φ₁ es una función afín del committor.

Para PODs pequeños en dinámica reversible, el rastro tiene un **espectro de memoria**:

```latex
e_T \;\approx\; \tfrac12 \sum_{k\ge1} e^{-2(T-t_0)/t_k}\,(\Delta\varphi_k)^2
\qquad\Longrightarrow\qquad \text{semivida del rastro} \approx \tfrac{\ln 2}{2}\,t_1
```

Con forzamiento dependiente del tiempo, las funciones propias se sustituyen por las funciones singulares del operador entre t₀ y T, y la conclusión no cambia.

Uso práctico: antes de buscar PODs se estiman t₁, t₂, … y las φₖ sobre el ensemble sin perturbar. La jugosidad a horizonte T de cualquier candidato se predice entonces con un producto escalar, y el motor completo solo se lanza para confirmar (§10.1).

### 8.2 El efecto mariposa es migración de información

El Teorema 1 prohíbe que un POD cree información. Lo que el efecto mariposa hace es trasladarla de variables micro a variables macro, en tres fases:

| Fase | Duración típica | Dónde está la información del POD | Λ sobre observables macro |
| --- | --- | --- | --- |
| 1. Micro | De días a unos 5 años | En sucesos y personas; las diferencias entre brazos crecen casi exponencialmente y se saturan | Casi cero |
| 2. Transferencia | Años a décadas | Sube de escala, solo si el POD entra por un nodo granular (H alto) o cerca de una divisoria | Crece, con techo en 1 |
| 3. Destino | Décadas a siglos | Se disipa por mezcla o se congela en una estructura no ergódica (§7.4) | Decae con semivida ligada a t₁, o queda en meseta |

Que los sucesos individuales difieran al máximo (fase 1 saturada) no implica divergencia macro. La fase que importa es la 3.

### 8.3 Clases de efecto

| Clase | Firma | Interpretación |
| --- | --- | --- |
| Absorbido | Λ macro nunca supera el umbral prerregistrado | El atractor amortigua el POD |
| Transitorio | Λ sube y decae; igual probabilidad final de régimen; fecha de transición desplazada | Mismo desenlace, adelantado o retrasado |
| Persistente | Meseta de Λ por refuerzo | Mismo régimen, distinto nivel |
| Bifurcación | Meseta de Λ con Δφ₁ distinto de cero | Cambio duradero de las probabilidades de régimen |
| En transferencia | Λ macro sigue creciendo en el horizonte T | Fase 2 aún en curso: se amplía el horizonte o se marca como no clasificado, con revisión de posible artefacto |

La magnitud de la diferencia en unidades típicas puede seguir creciendo; la distinguibilidad no puede pasar de Λ = 1.

### 8.4 Climatología y dos horizontes

**Ensemble climatológico.** Trayectorias desde t₀ con condiciones iniciales tomadas de la distribución incondicional de estados plausibles para la época, no de la historia concreta. Es la referencia de «ya no sabemos nada», y su dispersión es la escala con que se normalizan los efectos.

- **Horizonte de predictibilidad del modelo.** Para cada observable, el primer instante en que la habilidad de la predicción desde t₀ frente a la climatología cae bajo un umbral prerregistrado (por ejemplo, habilidad CRPS inferior a 0,1). Se informa con intervalo por bootstrap sobre partículas. Su versión en nats es la entropía relativa respecto a la climatología, que se descompone en señal y dispersión (Kleeman, 2002).
- **Horizonte de memoria del POD.** Cuándo el rastro e cae bajo el umbral.

No son lo mismo. Un efecto puede ser real y duradero (la población media es mayor) aunque el estado ya no pueda predecirse en detalle. Se informan ambos. Los forzamientos compartidos (volcanes, órbita) dan predictibilidad a los dos brazos sin crear divergencia entre ellos.

**Entropía de regímenes.** La entropía de la distribución de regímenes en cada brazo marca dónde el futuro se abre. Hay equifinalidad cuando, tras un pico de divergencia, ambos brazos vuelven al mismo reparto.

### 8.5 Fluctuación y disipación

La respuesta media de un sistema estocástico a un empujón pequeño se puede leer en las correlaciones de sus fluctuaciones espontáneas. Es el teorema de fluctuación y disipación; Leith (1975) lo propuso para la respuesta del clima. En su forma cuasi-gaussiana:

```latex
\delta\,\mathbb{E}\big[X_{t_0+\tau}\big] \;\approx\; R(\tau)\,\delta x,\qquad R(\tau) = C(\tau)\,C(0)^{-1},\qquad C(\tau)=\mathrm{Cov}\big(X_{t+\tau},X_t\big)
```

Esto da una vía de validación independiente del modelo: comparar la respuesta que el modelo da a PODs pequeños con el operador R estimado de las covarianzas retardadas del panel histórico. La semivida del rastro se contrasta igual, con t₁ leído en la autocorrelación.

Condiciones: estacionariedad aproximada en coordenadas intensivas, empujón dentro del rango de la variabilidad natural y densidad invariante suave, que el ruido garantiza. Límite: vale dentro de un régimen y no dice nada de cruces de cuenca.

## 9. Agencia

Los actores deciden solo en nodos de decisión discretos, eligen entre estrategias compiladas de antemano y lo hacen con una racionalidad acotada que se estima con datos. Así la capa de agencia es barata, estimable y no inventa comportamientos anacrónicos.

### 9.1 Nodos de decisión

Se disparan por umbrales del estado (crisis fiscal, invasión, sucesión, revuelta), no en cada paso. Típicamente hay unas pocas decenas por siglo y entidad. Cada nodo es una fuente de salto del generador (§3.2).

### 9.2 Estrategias y pagos

- **Conjunto de estrategias.** Para cada tipo de nodo, el LLM compila una vez y a ciegas (§12) entre 3 y 8 estrategias factibles para la época y la cultura. Cada una se traduce a efectos paramétricos sobre el estado: subir impuestos en cierta proporción, movilizar, negociar, purgar una facción. Un agente auditor revisa la lista.
- **Pagos.** Funciones paramétricas del estado que el actor cree y de sus rasgos: aversión al riesgo, horizonte temporal, legitimidad, preferencia por la expansión. No se escriben pagos a mano caso por caso.

### 9.3 Elección aleatoria estructural

Cada actor maximiza su utilidad más un choque aleatorio de Gumbel por opción. Eso equivale a la respuesta cuántica logit y hace explícito el azar exógeno de cada decisión:

```latex
s^{*} = \arg\max_s\ \big[\lambda\,u(s;\hat x_i,\rho_i) + G_s\big],\quad G_s \sim \text{Gumbel i.i.d.}
\qquad\Longrightarrow\qquad P(s)=\frac{e^{\lambda u(s)}}{\sum_{s'}e^{\lambda u(s')}}
```

λ mide la racionalidad: perfecta cuando tiende a infinito, azar puro en cero. Se estima con decisiones codificadas de muchos casos. Las probabilidades P(s) son el modelo de plausibilidad de los PODs de decisión (§5.1). Dos requisitos de identificación:

- **Escala.** Solo el producto λ·u es identificable. Se ancla u a una unidad física (log-probabilidad de conservar el poder, o recursos) y λ pasa a ser comparable entre casos.
- **Invariancia a clones.** Partir una estrategia en dos variantes casi iguales no debe cambiar las probabilidades de las demás; de lo contrario la sorpresa de un POD dependería del estilo del compilador. Se usa un logit anidado por similitud de efectos, o una densidad de elección sobre el espacio de efectos:

```latex
P(ds) \;\propto\; e^{\lambda u(s)}\,\mu(ds)
```

**Juegos entre actores.** Con 2 a 4 actores en un nodo, el equilibrio de respuesta cuántica se resuelve por iteración de punto fijo. Con más, respuesta logit secuencial. Nada de equilibrios perfectos en subjuegos a lo largo de siglos.

### 9.4 Decisiones acopladas entre mundos

Observada la decisión real, se infiere la posterior de los choques de Gumbel que la hicieron ganar, y en el mundo alternativo se reutilizan con las utilidades nuevas. Es el modelo causal Gumbel-max de Oberst y Sontag (2019).

Cumple estabilidad contrafactual: un actor no abandona su decisión real salvo que el POD haya mejorado la utilidad relativa de otra opción. Un actor vivo en t₀ sigue decidiendo como él mismo hasta que el POD alcanza su contexto.

### 9.5 Creencias e información

Los actores deciden sobre lo que creen, y la información viaja a la velocidad de un correo. Cada actor lleva una estimación x̂ del estado, filtrada con señales ruidosas y con un retraso proporcional a la distancia en el grafo de rutas.

Muchos «errores» históricos pasan a ser decisiones razonables sobre información vieja, sin tocar λ. Y el catálogo gana el POD informativo, con plausibilidad bien definida.

### 9.6 Acción colectiva e instituciones

Revueltas, deserciones y colapsos de legitimidad son cascadas con umbral, y son la fuente microscópica de colas pesadas en lo político. Entran como variantes rivales del mecanismo de crisis interna, junto a las macroscópicas (demográfico-estructural, institucional-fiscal, climático-agraria):

| Variante | Idea | Referencia |
| --- | --- | --- |
| Umbrales heterogéneos | Cada persona se suma cuando ya lo han hecho suficientes | Granovetter (1978) |
| Falsificación de preferencias | El apoyo público oculta el privado hasta que un choque lo revela | Kuran (1989) |
| Juegos globales | Cada uno recibe una señal ruidosa de la fuerza del régimen; hay un umbral único | Morris y Shin (2003) |

**Dinámica institucional.** Las instituciones y doctrinas se difunden por el grafo G con dinámica del replicador: una institución se extiende si a las entidades que la tienen les va mejor, con una mutación pequeña que representa la innovación institucional.

### 9.7 Líderes: individuo frente a estructura

Para los vivos en t₀, los rasgos son una posterior inferida de su conducta registrada. Para los que llegan después del horizonte de identidad (§4.3), se muestrean de la distribución de rasgos de la época, la cultura y la regla de selección.

Cuánto pesa un individuo no se decreta: resulta de tres factores medibles, y el presupuesto de contingencia (§6.2) lo cuantifica para cada desenlace.

1. **Granularidad** H de la decisión (§3.3): cuánto poder concentra el puesto.
2. **Varianza de rasgos** entre quienes pueden ocupar el puesto. Depende de la regla de selección.
3. **Racionalidad** λ: con λ alta todos los ocupantes eligen parecido y la identidad importa menos.

Los tres se calibran con experimentos naturales (§13.4).

## 10. Búsqueda de PODs

Un POD jugoso es una intervención pequeña, plausible y local que deja un rastro macro grande, duradero y robusto entre modelos. Se busca en tres etapas: criba barata, optimización con emulador y certificación.

### 10.1 Etapa 1: criba

El espacio de búsqueda es tipo de intervención × entidad × año × magnitud. Se reduce con tres filtros que no exigen simular cada candidato:

1. **Ventanas decisivas.** Solo los tramos con tasa de resolución r alta y ambigüedad b alta (§6.2). Reduce el espacio en uno o dos órdenes de magnitud.
2. **Proyección espectral.** Para cada candidato se calcula su desplazamiento sobre las funciones propias lentas (§8.1) y su cambio de h (§6.3). Se descartan los que no mueven ningún modo lento.
3. **Sensibilidad global.** Método de Morris y después índices de Sobol con ensembles pequeños, de unas 50 partículas, sobre lo que quede.

### 10.2 Etapa 2: emulador y optimización bayesiana

- Se entrena un emulador que predice el rastro e y su varianza a partir de los parámetros de la intervención: proceso gaussiano en espacios pequeños, ensemble de redes neuronales en espacios grandes.
- Se optimiza el rastro con presupuesto de coste, con adquisición por mejora esperada. El motor completo solo se ejecuta en los puntos propuestos.
- El emulador diferenciable sirve también para el cálculo de acción mínima (§6.4).

### 10.3 Etapa 3: certificación

Con miles de candidatos, los mejores estarán inflados por azar y por artefactos del modelo (maldición del ganador). Un POD solo se certifica si cumple todo esto:

1. Repite su rastro con semillas nuevas y al menos 1.000 partículas, con la cota inferior de Λ lejos de cero.
2. Pasa el test contable: Λ ≤ 1.
3. Su índice de dependencia estructural (§11.4) está por debajo del umbral prerregistrado.
4. No depende de un único parámetro con prior débil: sensibilidad local sobre los 10 parámetros más influyentes.
5. Supera la auditoría de mecanismo: su camino causal (§5.6) es interpretable y no pasa por un fallo numérico (saturación, división casi por cero, salida del dominio).

Sobre los contrastes de esta etapa se controla la tasa de falsos descubrimientos (Benjamini y Hochberg).

### 10.4 Ranking

Un solo número no basta. Se informa la frontera de Pareto en el plano coste–rastro y tres listas:

| Lista | Criterio | Para qué sirve |
| --- | --- | --- |
| Mayor rastro con presupuesto | Máximo e con c ≤ 1, 3 y 6 nats (probabilidades 0,37, 0,05 y 0,0025) | El POD más potente que no sea un milagro |
| Mayor eficiencia | Máximo Λ con e por encima de un umbral | La bifurcación más limpia |
| Dirigida | Máxima ganancia g hacia un desenlace B | Banco de pruebas de una ucronía |

Los PODs célebres se evalúan, pero compiten con todos los demás.

## 11. Inferencia

Todos los modelos rivales son falsos, y la inferencia está diseñada para ese caso. El resultado de una pregunta interventiva es un conjunto de respuestas compatibles con los datos, no un promedio.

### 11.1 Estado

La posterior del estado oculto dada la historia observada se calcula por Monte Carlo secuencial: filtro de partículas, con suavizado cuando la consulta lo pide (§4.4). Cada partícula es un estado y un vector de parámetros, y es el punto de partida de un par de gemelos.

### 11.2 Parámetros

La verosimilitud no es tratable, así que se infiere por simulación, en dos tiempos:

1. **Descarte por oleadas (history matching).** Con un emulador barato se eliminan las regiones de parámetros implausibles. Un parámetro se descarta cuando su implausibilidad supera 3:

```latex
I(\theta) = \frac{\big|\,z - \mathbb{E}[f(\theta)]\,\big|}{\sqrt{V_{\text{obs}} + V_{\text{discrepancia}} + V_{\text{emulador}}}}
```

2. **Posterior dentro de lo no descartado.** ABC secuencial o estimación neuronal de la posterior (NPE).

Tres reglas acompañan a ambos pasos:

- **Jerarquía.** Los parámetros de mecanismo se estiman con un modelo jerárquico sobre muchas entidades. Cada caso toma prestada fuerza del conjunto y no puede ajustarse en solitario a su propio desenlace.
- **Momentos experimentales.** Los efectos medidos en experimentos naturales (§13.4) entran como condiciones que el modelo debe reproducir.
- **Priores.** Los del LLM entran como datos con su modelo de error (§12), atemperados para que nunca pesen más que el panel.

### 11.3 Contra la falsa confianza

Un posterior bayesiano corriente, aplicado a un modelo falso, se concentra con seguridad creciente en el parámetro menos malo. Tres herramientas lo evitan:

| Herramienta | Qué hace | Referencia |
| --- | --- | --- |
| Término de discrepancia | El dato es simulador más error estructural más ruido; el error estructural se modela y se estima | Kennedy y O'Hagan (2001) |
| Posterior generalizado | Sustituye la verosimilitud por una regla de puntuación con tasa de aprendizaje ajustada | Bissiri, Holmes y Walker (2016) |
| Descarte por oleadas | Devuelve un conjunto no descartado en lugar de un punto | Craig y otros (1997); Vernon, Goldstein y Bower (2010) |

### 11.4 Modelos rivales: apilar para predecir, acotar para intervenir

Cada mecanismo crítico tiene al menos tres variantes rivales. Para crisis internas, por ejemplo: demográfico-estructural, institucional-fiscal, climático-agraria y las de cascada de §9.6.

**Para predecir.** Los pesos se fijan por apilamiento (stacking) sobre la puntuación de hindcast fuera de muestra, no por verosimilitud marginal, que es frágil con modelos mal especificados.

**Para intervenir.** Dos modelos pueden empatar en hindcast y discrepar ante un POD, porque una regularidad observada no tiene por qué sobrevivir a una intervención (crítica de Lucas, 1976). Dos reglas:

1. **Invariancia declarada.** Cada mecanismo dice cuáles de sus parámetros supone invariantes ante un POD y cuáles son resultados de equilibrio. La tasa de cumplimiento fiscal, por ejemplo, es un resultado y no puede fijarse como parámetro.
2. **Salida como conjunto.** Toda respuesta interventiva se da como el intervalo entre el mínimo y el máximo sobre los modelos y parámetros no descartados (identificación parcial, en el sentido de Manski), con el posterior apilado dentro.

El **índice de dependencia estructural** es la anchura del conjunto identificado dividida por la anchura del intervalo dentro de un modelo. Cerca de 1, el resultado es robusto. Muy por encima, depende del modelo y se etiqueta así.

### 11.5 Tres capas de incertidumbre, nunca fundidas

| Capa | Origen | Cómo se reduce |
| --- | --- | --- |
| Monte Carlo | Número finito de partículas | Más cómputo |
| Paramétrica | Datos limitados, dentro de un modelo | Más datos |
| Estructural | Entre modelos rivales y entre acoplamientos | Mejores teorías o nuevos experimentos naturales |

Toda salida las da por separado. Fundirlas esconde lo que el usuario necesita saber: si más cómputo o más datos servirían de algo.

## 12. Protocolo anti-sesgo y anti-filtración

El riesgo principal del sistema no es numérico: es que el modelo «sepa» cómo acabó la historia y lo cuele en los priores, en las estrategias o en la elección de mecanismos. Estas diez reglas son obligatorias en cada caso.

1. **Los datos mandan sobre el LLM.** Los parámetros se estiman por asimilación (§11). El LLM solo propone estructura y priores amplios; un prior elicitado nunca es más estrecho que el que justificaría un experto que no conociera el desenlace.
2. **Elicitación ciega.** Al pedir priores o estrategias, el caso se seudonimiza: entidades P1, P2…; fechas relativas; sin nombres de lugares ni de personas; solo variables de estado («Estado agrario de 60 millones de habitantes, frontera esteparia al norte, ingresos fiscales del 8 % del producto…»).
3. **Test de filtración.** Antes de usar un prompt ciego, otro modelo intenta identificar el caso. Si acierta la época o el lugar con probabilidad notable, se reformula: se quitan detalles identificativos y se añaden señuelos.
4. **Casos señuelo.** Cada elicitación mezcla el caso objetivo con casos reales distintos de estado parecido y con casos sintéticos. Las respuestas al caso objetivo no deben diferir sistemáticamente de las de los señuelos sin una razón de estado.
5. **Medida de fuga.** Los mismos parámetros se elicitan dos veces sobre casos de reserva: a ciegas y con el caso nombrado. La diferencia, por tipo de parámetro, es la fuga medida. Los priores de ese tipo se ensanchan en esa cantidad, o se descartan si es grande.
6. **Medida de destreza.** Se describen al LLM sociedades sintéticas generadas por el simulador con parámetros conocidos. Ahí no hay retrospectiva posible, y su error da su curva de calibración como experto.
7. **Prerregistro.** Antes de correr un caso se congelan, en un fichero con hash, los observables, las ventanas, los desenlaces, los presupuestos de coste, los umbrales y el catálogo de PODs. Cambiarlos después obliga a declarar el análisis como exploratorio.
8. **Test de inevitabilidad.** En hindcast, la probabilidad que el modelo asigna al curso real debe parecer la de un sorteo típico: PIT aproximadamente uniforme sobre muchos casos. Si la historia real cae siempre en el centro, el modelo es teleológico; si cae siempre en las colas, está mal.
9. **Simetría cultural auditada.** Mismo catálogo de mecanismos para todas las regiones. Una auditoría automática lista los parámetros específicos de cada región y exige que los justifiquen datos.
10. **Agente auditor separado.** Un agente que no ha visto el desarrollo revisa cada caso con una lista fija: procedencia de parámetros, priores estrechos, mecanismos añadidos después de ver resultados, PODs elegidos por narrativa. Su informe acompaña a la salida.

## 13. Validación

El contrafactual no se observa nunca, así que la validez se construye por capas: cadena completa en mundos con verdad conocida, motor hacia delante, respuesta a intervenciones y contraste con experimentos naturales. Ningún módulo pasa de fase sin superar su capa.

### 13.1 La tríada de validez

Un hindcast calibrado valida predicciones, no intervenciones. Para que valide también la consulta I hacen falta tres condiciones.

**Proposición 3.** La respuesta interventiva del modelo, P(Y | do(a), x) = P(Y | x ⊕ a), queda validada por hindcasts hacia delante si se cumplen:

| Condición | Qué exige | Cómo falla | Test |
| --- | --- | --- | --- |
| S1. Suficiencia causal | El estado es markoviano y no falta ninguna causa común del POD y del futuro | Los líderes mueren cuando el reino ya se hunde; el modelo aprende la correlación como si fuera efecto | Experimentos naturales (§13.4); controles negativos; fluctuación y disipación (§8.5) |
| S2. Solapamiento | El estado perturbado x ⊕ a se parece a estados que el panel ha visto | El POD crea una situación sin precedentes y el modelo extrapola | Índice de extrapolación: distancia a los k estados de panel más próximos, junto a cada resultado |
| S3. Calibración condicional | El modelo está calibrado en el entorno de x ⊕ a, no solo en promedio | Acierta de media y falla donde importa | PIT estratificado por región del estado y por régimen |

**Argumento.** Con S1, el estado es un conjunto de ajuste válido: intervenir sobre una variable equivale a inicializar el modelo en el estado perturbado. Con S2 y S3, el núcleo de transición en ese estado es uno que los datos han puesto a prueba. ∎

Las consultas II y III no son validables: se informan con cotas (§4.2).

### 13.2 Mundos sintéticos y banco canónico

Es la única prueba directa de la cadena completa.

1. Se elige un «modelo verdadero» (una variante del ensemble con parámetros fijados) y se simula con él una historia sintética.
2. Se degrada como las fuentes reales: solo algunas variables, con ruido y huecos.
3. Se pasa la historia degradada por la cadena completa, con modelos rivales que no tienen por qué incluir el verdadero.
4. Se comparan los efectos de POD estimados con los verdaderos, que en el modelo verdadero se calculan exactamente.
5. Se plantan divisorias y PODs conocidos y se comprueba que el sistema los encuentra.

Métricas: cobertura de los intervalos (uno del 90 % debe contener el efecto verdadero cerca del 90 % de las veces), sesgo, tasa de recuperación de PODs plantados y falsos positivos.

**Experimentos cruzados.** Cada modelo rival hace de verdad para los demás. La matriz de errores resultante es una distribución empírica del error por mala especificación, con la que se ensanchan los intervalos del caso real.

**Banco canónico de juguetes.** Cinco sistemas con respuesta exacta para h, κ y Λ:

| Sistema | Qué pone a prueba |
| --- | --- |
| Doble pozo con ruido gaussiano | Committor, ley de Kramers, instantón |
| Doble pozo con ruido estable de índice α | Salida por salto único, κ concentrado |
| Urna de Pólya | Memoria permanente, meseta de Λ |
| Sistema lento-rápido con límite homogeneizado conocido | Reducción de escalas (§3.5) |
| Doble pozo con deriva de parámetro | Vuelcos de tipo B y R, señales tempranas |

### 13.3 Hindcast con origen móvil

Se inicializa el modelo en muchas fechas y regiones, con el futuro oculto, y se puntúan las predicciones a 10, 25, 50 y 100 años.

- **Reglas de puntuación propias.** CRPS para variables continuas, log-score para categóricas.
- **Calibración.** Histogramas PIT y cobertura de intervalos del 50 % y del 90 %, agregados y estratificados (S3).
- **Habilidad frente a referencias nulas.** Persistencia, tendencia lineal y climatología. Un modelo que no gana a la persistencia a 25 años no tiene licencia para opinar a 100.
- **Validación cruzada por bloques.** Entrenar sin una civilización entera y predecir esa civilización.

### 13.4 Experimentos naturales

La historia contiene casi-experimentos donde decidió el azar. Son la única evidencia directa sobre S1, y entran en la estimación como momentos que el modelo debe reproducir (§11.2).

| Experimento | Qué sortea el azar | Qué calibra | Muestra |
| --- | --- | --- | --- |
| [Jones y Olken (2009)](https://www.nber.org/papers/w13102) | Que un atentado contra un líder acierte o falle | Efecto de la muerte del líder sobre instituciones y guerra | Atentados contra líderes nacionales, 1875–2004 |
| [Jones y Olken (2005)](https://econpapers.repec.org/RePEc:oup:qjecon:v:120:y:2005:i:3:p:835-864) | La fecha de una muerte natural o accidental en el cargo | Varianza de rasgos y gradiente con la concentración de poder | Líderes nacionales, 1945–2000 |
| [Bai y Kung (2011)](https://econpapers.repec.org/RePEc:tpr:restat:v:93:y:2011:i:3:p:970-981) | Choques de lluvia | Canal clima, cosecha y conflicto entre China y la estepa | Historia china de largo plazo |
| Erupciones volcánicas | Fecha y magnitud del forzamiento | Respuesta agraria y fiscal a un choque fechado | Reconstrucciones de forzamiento |
| Controles sintéticos (Abadie y colaboradores) | Choques regionales concretos | Efectos a corto plazo | Casos publicados |

Antes de fijar cualquiera de ellos como blanco numérico, el constructor debe abrir el artículo y extraer los intervalos exactos. Los dos primeros son de época contemporánea: llevarlos a un Estado premoderno es un supuesto de transporte, que se contrasta con el gradiente de H.

### 13.5 Los casos de panel no son independientes

Las sociedades vecinas o emparentadas se parecen por difusión y por herencia común. Es el problema de Galton, y reduce el tamaño efectivo de la muestra:

```latex
N_{\text{ef}} \;=\; \frac{N}{1+(N-1)\,\bar\rho}
```

Con 300 casos y una correlación media de 0,05 entre ellos, el tamaño efectivo es 19. Remedios: validación cruzada por bloques de linaje cultural y de época, e intervalos de las puntuaciones por bootstrap de bloques.

### 13.6 La simetría cultural es una hipótesis contrastable

Mismas ecuaciones para todas las civilizaciones, como prior. Cada parámetro de mecanismo lleva un efecto aleatorio por región cuya varianza se estima.

Si esa varianza es pequeña, la simetría se confirma y los casos se prestan fuerza. Si es grande, la simetría falla para ese mecanismo y los intervalos del caso se ensanchan solos. Es el problema de transportabilidad (Pearl y Bareinboim, 2011), y su test directo es predecir una civilización entera sin haberla usado.

### 13.7 El límite de N = 1

La industrialización ocurrió una vez. Ningún hindcast puede calibrar su probabilidad, y S2 falla por definición. Eso obliga a cambiar de tipo de evidencia, no a callar.

| Herramienta | Qué aporta |
| --- | --- |
| Validación por mecanismo | Cada pieza se valida donde sí hay muchos casos: curvas de aprendizaje en decenas de técnicas (Nagy y otros, 2013), transición demográfica, relación entre energía y producto |
| Casi-aciertos como datos censurados | Las eflorescencias que no despegaron (Goldstone, 2002) son observaciones censuradas de un tiempo hasta el crecimiento sostenido |
| Cotas físicas | Energía por persona, techo fotosintético de la agricultura, densidad de potencia de los motores primarios: restricciones duras que podan el espacio |
| Factura mínima de milagro (§5.5) | Para cada modelo rival, cuántos nats cuesta el desenlace y cómo se reparten (§6.4) |

Para una premisa como «Song conserva el norte y se industrializa», la salida es: la factura en nats según cada modelo rival, si el perfil κ está concentrado o exige una conjura, y qué cotas físicas aprietan. Con grado de confianza D, y con todos los números a la vista.

### 13.8 Licencia de publicación

El sistema solo publica un resultado interventivo dentro de su licencia, que tiene tres ejes: el horizonte en que el hindcast tiene habilidad positiva demostrada para esa clase de variable, la región del estado donde se cumple S2, y el tipo de intervención con evidencia de S1. Fuera de la licencia la salida se marca como exploratoria y su confianza baja automáticamente (§15.2).

### 13.9 Qué puede saberse

| Magnitud | De qué depende | Se valida con |
| --- | --- | --- |
| Predicción hacia delante | Datos y modelo | Hindcast |
| Consulta I: efecto prospectivo de un POD | Además, S1 a S3 | Experimentos naturales, fluctuación y disipación, mundos sintéticos |
| Coste c de un POD | Modelo de plausibilidad | Tasas base: tablas de vida, frecuencia de sorpresas en batalla |
| Rastro e y eficiencia Λ | Marginales del modelo | Mundos sintéticos; la cota Λ ≤ 1 |
| Consultas II y III | El acoplamiento entre mundos | Nada: solo cotas |

## 14. Arquitectura de software

Once módulos con una frontera dura: el LLM vive solo en el compilador de escenarios. Simulación, asimilación y análisis son código numérico, determinista dada su semilla.

&#91;embedded content: arquitectura · 11 módulos, un solo punto con LLM\]

Un caso entra por los datos, se compila una vez y después todo corre sobre el motor numérico. La validación vigila a los módulos de los que depende todo lo demás.

### 14.1 Módulos

| Módulo | Responsabilidad | Tecnología sugerida | Test de aceptación |
| --- | --- | --- | --- |
| M1 Ontología | Esquema tipado de variables, unidades, rangos, identidades contables y fuentes de azar (familia, cola, tiempo de identidad) | YAML con Pydantic o serde | Toda variable con unidad y rango; identidades verificadas en cada paso; toda fuente declarada |
| M2 Ingesta | Carga y armoniza fuentes con su error de medida | Python, Polars, Parquet | Cada serie con procedencia y error |
| M3 Mecanismos | Ecuaciones modulares con priores; al menos 3 rivales en los críticos | Rust, Numba o JAX | Cada mecanismo reproduce sus hechos estilizados; grafo de signos generado |
| M4 Compilador | Caso en lenguaje natural a configuración y priores a ciegas | LLM con salida JSON validada por esquema | Test de filtración superado; fuga medida |
| M5 Motor | Simulación vectorizada sobre el eje del ensemble, generador por contador | Rust (SoA) o JAX/Numba | Determinismo bit a bit por semilla; rendimiento objetivo |
| M6 Asimilación | Posterior de estado y parámetros; descarte por oleadas | SMC, ABC-SMC, NPE (sbi) | Recupera parámetros en mundos sintéticos con cobertura nominal |
| M7 Gemelos | Operador de intervención, azar compartido según horizonte de identidad, coste en nats | Sobre M5 | POD nulo = efecto exactamente cero; Λ ≤ 1 |
| M8 Contingencia y regímenes | Committor, presupuesto de contingencia, perfil κ, regímenes, espectro lento | deeptime, SciPy, clasificadores calibrados | Recupera h, κ y regímenes en el banco canónico; las sumas de los Teoremas 2 y 3 cuadran |
| M9 PODs | Criba, emulador, optimización bayesiana, certificación | SALib, BoTorch | Encuentra el POD plantado en un mundo sintético |
| M10 Validación | Hindcast, puntuación, mundos sintéticos, experimentos naturales, tríada de validez | pytest, scoringrules | Informe de calibración por fase |
| M11 Informes | Contrato de salida, gráficos, narración etiquetada | Python; LLM solo al final | El informe valida contra el esquema de §15 |

### 14.2 Biblioteca de mecanismos

Cada mecanismo es un módulo pequeño con una ficha de declaración. Sin ficha completa no compila.

| Campo de la ficha | Contenido |
| --- | --- |
| Ecuación | Forma funcional, variables que lee y que escribe |
| Parámetros | Prior con rango, procedencia y marca de invariancia ante intervenciones (§11.4) |
| Fuentes de azar | Familia, índice de cola y tiempo de identidad de cada una (§3.4, §4.3) |
| Circuitos | Circuitos positivos y negativos en que participa (§3.6) |
| Estructura no ergódica | Metaestabilidad, refuerzo o barrera absorbente, si contiene alguna (§7.4) |
| Evidencia | Referencias, tests de hechos estilizados y test de hindcast |

Lote inicial razonable:

- Producción agraria malthusiano-ricardiana, con clima a rendimiento.
- Demografía con hambrunas y epidemias (SIR sobre la red comercial).
- Capacidad fiscal y deuda.
- Dinámica de élites y crisis interna, con sus variantes rivales macro y de cascada.
- Combate y desgaste: Lanchester estocástico con tamaño de cola pesada.
- Cohesión y frontera (la asabiya de Turchin como una variante entre otras).
- Comercio por modelo gravitatorio.
- Difusión tecnológica logística sobre red, con curvas de aprendizaje.
- Acoplamientos lentos con la capa biofísica: deforestación, salinización, irrigación. La capa biofísica es exógena a corto plazo y se acopla a largo plazo mediante estos mecanismos explícitos.

Si ya existe un motor en Rust con arquitectura SoA/ECS, M5 puede apoyarse en su núcleo. Clinamen añade el eje del ensemble vectorizado, el generador por contador, los gemelos y la salida a Parquet.

### 14.3 Presupuesto de cómputo

Objetivo de rendimiento: una trayectoria-año del modelo macro-meso (unas 30 entidades, 40 variables cada una, 15 mecanismos) en 20 µs o menos por núcleo. Con ese objetivo y 16 núcleos:

| Operación | Volumen | Tiempo estimado |
| --- | --- | --- |
| Propagación de un POD | 1.000 partículas × 2 gemelos × 200 años | Menos de 1 s |
| Ensemble base sin perturbar | 20.000 trayectorias × 200 años | Unos 5 s |
| Asimilación de parámetros | Unas 100.000 simulaciones × 300 años | Menos de 1 min |
| Committor por disparos | 300 estados × 200 réplicas × 100 años | Unos 10 s |
| Ruta más barata por división multinivel | 100 iteraciones × 2.000 réplicas × 200 años | Alrededor de 1 min |
| Criba de PODs | 5.000 candidatos × 50 partículas × 2 × 150 años | Unos 2 min |
| Certificación | 50 PODs × 1.000 × 2 × 150 años × 3 modelos | Alrededor de 1 min |

Todo el flujo de un caso cabe en minutos. Aunque el motor fuera 10 veces más lento, seguiría siendo un trabajo de una tarde. En GPU el eje del ensemble es el lote; cada script mide su rendimiento en un tramo corto antes de estimar la duración, en lugar de fiarse de esta tabla.

La memoria es el cuello de botella real: guardar trayectorias completas de 1.000 × 2 × 200 años × 1.200 variables ocupa unos 2 GB en precisión simple. Regla: se guardan solo los observables macro (unas 20 series) y estados completos en años ancla.

### 14.4 Precisión numérica

En precisión simple, que es lo habitual en GPU modesta, cuatro reglas evitan errores silenciosos:

- Probabilidades, costes y rastros se manejan en escala logarítmica, y sus sumas con log-sum-exp.
- h se almacena como logit; κ se calcula con diferencias de log h.
- Las identidades contables se verifican con tolerancia relativa y las acumulaciones largas con suma compensada.
- El determinismo bit a bit y el test de POD nulo se exigen en un mismo dispositivo; entre dispositivos se compara con tolerancia.

## 15. Contrato de salida y escala de confianza

Toda respuesta es un objeto estructurado que valida contra un esquema; la prosa es un campo más, el último. Si un campo obligatorio no se puede rellenar, el informe no se emite.

### 15.1 Esquema de un informe de POD

```json
{
  "caso": "id del caso prerregistrado + hash",
  "consulta": "I",
  "pod": {"tipo": "supervivencia_actor", "entidad": "P3", "t0": 0,
          "suceso": "sobrevive a la enfermedad"},
  "coste": {"p": 0.35, "nats": 1.05, "modelo": "tabla_vida+salud_inferida"},
  "rastro": [{"horizonte": 25, "observable": "regimen",
              "nats_min": 0.22, "eficiencia_min": 0.21}],
  "dirigido": {"desenlace": "estado_unificado", "horizonte": 25,
               "p_pod": 0.62, "p_abanico": 0.30, "p_rama_real": 0.13,
               "ganancia_nats": 0.73, "eficiencia": 0.69},
  "observables": [
    {"nombre": "poblacion", "unidad": "millones",
     "cuantiles": {"+10": [], "+25": [], "+50": [], "+100": []},
     "efecto_estandarizado": {},
     "horizonte_predictibilidad": {"mediana": 70, "ic90": [45, 95]},
     "confianza": {"+25": "B", "+100": "D"}}
  ],
  "regimenes": {"+25": {"pod": {}, "abanico": {}}, "+100": {"pod": {}, "abanico": {}}},
  "clase_efecto": "bifurcacion",
  "memoria": {"semivida_anios": 60,
              "modos_lentos": [{"escala_anios": 170, "desplazamiento": 0.4}]},
  "atribucion": [{"canal": "capacidad_fiscal", "shapley": 0.46}],
  "incertidumbre": {"monte_carlo": {}, "parametrica": {}, "estructural": {}},
  "dependencia_estructural": 1.6,
  "validez": {"s1_evidencia": ["muerte_natural_de_lider"],
              "indice_extrapolacion": 0.2,
              "calibracion_condicional": "superada"},
  "acoplamiento": null,
  "confianza_global": "C",
  "auditoria": {"agente": "auditor", "incidencias": []},
  "advertencias": [],
  "narrativa_muestras": [{"percentil": 50, "etiqueta": "una muestra posible", "texto": ""}]
}
```

Los valores son los del ejemplo ilustrativo de §1.4. Variantes del esquema según la pregunta:

| Informe | Campos propios |
| --- | --- |
| Mapa de contingencia (Q1) | Regímenes descubiertos; series b(t) y r(t); presupuesto de contingencia por instante y fuente; tramos donde la historia tomó la rama improbable |
| Ranking (Q2) | Frontera coste–rastro; las tres listas de §10.4; estado de certificación de cada POD |
| Ruta a un desenlace (Q5) | Factura en nats por modelo rival; perfil κ por instante y fuente; índice de concentración; cotas físicas activas |
| Consultas II y III | Campo «acoplamiento» con el resultado bajo acoplamiento mínimo y máximo y las cotas de necesidad |

### 15.2 Escala de confianza

La asigna el sistema con reglas fijas, nunca el LLM. Los umbrales numéricos se congelan en el prerregistro.

| Grado | Requisitos |
| --- | --- |
| A | Dentro de la licencia en sus tres ejes (§13.8); evidencia de S1 por experimento natural para los mecanismos implicados; dependencia estructural cercana a 1; baja sensibilidad a priores |
| B | Como A, pero con dependencia estructural moderada o algún mecanismo sin experimento natural |
| C | Dentro de la licencia de horizonte; robustez parcial; al menos un parámetro influyente con prior débil o índice de extrapolación medio |
| D | Fuera de algún eje de la licencia, o dependencia estructural alta, o conjunto identificado que incluye el efecto nulo |
| E | Exploratorio: más allá del horizonte de predictibilidad, auditoría con incidencias pendientes, o resultado dependiente de acoplamiento |

La confianza se da por observable y horizonte: un mismo POD puede ser B para la población a +25 años y E para el régimen político a +150.

## 16. Flujo completo de un caso

Un caso recorre catorce pasos, de la pregunta al informe. La mayoría son scripts que la persona ejecuta en su equipo y cuyo resultado analiza el modelo. Ejemplo de referencia: China del norte y la estepa entre 1100 y 1300, la crisis Song–Jin.

1. **Definir el caso.** Teatro (Song, Liao, Jin, Xi Xia, confederaciones esteparias), ventana (1100–1300), observables (población por región, ingresos fiscales, territorio por entidad, urbanización, régimen por entidad), desenlaces de interés y resolución (anual; mensual en 1125–1142).
2. **Prerregistrar** (§12, regla 7).
3. **Compilar el escenario (M4, a ciegas).** Mecanismos de la biblioteca, estrategias por tipo de nodo y priores amplios. Test de filtración y medida de fuga.
4. **Reunir datos (M2).** Población (HYDE y estimaciones demográficas chinas), reconstrucciones de sequía y temperatura de Asia oriental, forzamiento volcánico, cronología codificada de guerras y sucesiones, fiscalidad documentada. Cada serie con su error.
5. **Prueba de humo.** 10 partículas: identidades contables, rangos y POD nulo.
6. **Criba estructural.** Grafo de signos del caso y lista de circuitos positivos (§3.6).
7. **Hindcast del caso.** Asimilación solo hasta 1100 y predicción de 1100–1300 a ciegas. ¿Cae la historia real dentro de las bandas? PIT del caso.
8. **Asimilación completa (M6).** Parámetros con todo el periodo; estados suavizados en cada t₀ candidato.
9. **Ensemble base (M8).** Regímenes, espectro lento y climatología.
10. **Mapa de contingencia (Q1).** Committor por desenlace y presupuesto de contingencia a lo largo de 1100–1300. Salida: cuándo estuvo abierto el futuro y qué lo cerró.
11. **Búsqueda de PODs (Q2),** limitada a las ventanas decisivas.
12. **Certificación** de los 20 mejores con N completo y todos los modelos rivales.
13. **Propagación, atribución y rutas (Q3, Q4, Q5).** Abanicos, perfil de Λ, clase, semivida y reparto por canales de los certificados. Para los desenlaces que no ocurrieron, factura y perfil κ.
14. **Informe (M11)** con el contrato de §15, la auditoría separada y, al final, tres narraciones muestreadas.

**Reparto.** Los pasos 1 a 3 y el 14 los hace el modelo con la persona. Los pasos 5 a 13 son scripts que el modelo entrega y la persona ejecuta, devolviendo los Parquet de resultados para el análisis.

**Banco de pruebas de una ucronía.** Si una premisa como «Song conserva el norte» no aparece entre los PODs certificados, el paso 13 dice cuántos nats cuesta, si existe un POD único o hace falta una conjura, y qué canales la amortiguarían.

## 17. Hoja de ruta por fases

Seis fases, cada una cerrada por una puerta con criterio numérico. Se empieza por sistemas de juguete y por un mundo sintético antes de tocar historia real.

&#91;embedded content: hoja de ruta · 6 fases, cada una con su puerta\]

F0 y F1 son las que más protegen, porque todo lo posterior hereda sus errores.

### 17.1 Qué se construye y qué se exige

| Fase | Se construye | Módulos | Puerta |
| --- | --- | --- | --- |
| F0 Cimientos | Ontología con identidades y fuentes de azar; motor vectorizado; generador por contador; gemelos; salida a Parquet | M1, M5, M7 | Determinismo bit a bit por semilla; POD nulo con efecto exactamente cero; identidades contables en el 100 % de los pasos; rendimiento dentro de un factor 10 del objetivo |
| F1 Banco canónico y mundo sintético | Los cinco juguetes; committor, presupuesto, ruta y espectro; asimilación; un mundo sintético degradado como las fuentes reales | M6, M8, M10 | h, κ y Λ dentro de tolerancia en los cinco sistemas; Λ ≤ 1 en todos los PODs; las sumas de los Teoremas 2 y 3 cuadran dentro del error de Monte Carlo; cobertura de los intervalos del 90 % entre 85 y 95 %; POD plantado recuperado |
| F2 Mecanismos y hindcast | Biblioteca con rivales y fichas; ingesta del panel; estimación jerárquica; hindcast con origen móvil | M2, M3, M6, M10 | Habilidad mayor que la persistencia a 25 años; PIT agregado y estratificado sin desviación significativa; predicción de una civilización no usada; test de Chapman y Kolmogórov superado |
| F3 Validez interventiva | Experimentos naturales como momentos; contraste de fluctuación y disipación; experimentos cruzados entre modelos; compilador ciego con medida de fuga | M4, M10 | Efectos simulados dentro de los intervalos publicados; fuga medida y bajo el umbral; error por mala especificación cuantificado |
| F4 Caso piloto | El caso Song–Jin de extremo a extremo; búsqueda y certificación de PODs; informes | M9, M11 | Al menos un POD certificado, o un informe razonado de por qué no hay ninguno; informe válido contra el esquema; auditoría sin incidencias pendientes |
| F5 Generalización y prospectiva | Más casos; contraste de las conjeturas de §19; pronósticos prerregistrados | Todos | Puntuación prospectiva mejor que la línea base |

### 17.2 Reglas de la ruta

- Si una fase no supera su puerta tras dos iteraciones, se simplifica el modelo. La puerta no se relaja.
- Los umbrales numéricos exactos de cada puerta se congelan antes de empezar la fase.
- Cada fase termina con un informe de calibración y scripts reproducibles.
- No se trabaja en una fase posterior mientras la puerta actual siga cerrada.

## 18. Prospectiva

La prospectiva es la consulta I con t₀ = hoy. Es también el único modo en que el sistema puede validarse de verdad, porque el futuro, a diferencia del contrafactual, acaba llegando.

### 18.1 Qué se traslada sin cambios

| Pieza | Uso prospectivo |
| --- | --- |
| Presupuesto de contingencia (§6.2) | Qué fuentes concentran la incertidumbre aún no resuelta sobre un desenlace: dónde vigilar |
| Ruta más barata (§6.4) | La política de mínimo coste hacia un objetivo. La transformada h es la solución de un problema de control óptimo con coste KL (Todorov, 2009) |
| Eficiencia de palanca (§5.3) | Qué intervenciones pequeñas dejan rastro duradero y cuáles se absorben |
| Profundidad y anchura de cuenca (§7.3) | Resiliencia ante presión gradual y ante choques extremos, por separado |
| Tipos de vuelco (§7.2) | Qué riesgos avisan antes (tipo B) y cuáles no pueden avisar (tipos N y R) |

Buscar el POD de máxima palanca y diseñar la intervención de máxima palanca son el mismo cálculo.

### 18.2 Tres diferencias

1. **Reflexividad.** Un pronóstico publicado lo leen los actores y entra en sus creencias. Debe ser un punto fijo: seguir siendo correcto una vez conocido. Grunberg y Modigliani (1954) mostraron que ese punto fijo existe bajo continuidad.
2. **Solapamiento peor.** El régimen moderno (crecimiento industrial, armas nucleares, transición demográfica, red global) tiene pocos precedentes en el panel. El índice de extrapolación crece deprisa con el horizonte y la licencia se acorta a años o pocas décadas.
3. **Validación directa.** Pronósticos prerregistrados, puntuados con reglas propias cuando llega el desenlace.

### 18.3 Experimentos naturales en curso

El presente fabrica casi-experimentos continuamente: elecciones decididas por un margen mínimo, muertes súbitas de dirigentes, desastres naturales. Para cada uno, el modelo registra antes su respuesta interventiva y después se compara con lo ocurrido. Las elecciones reñidas ya se usan así en econometría, como discontinuidades (Lee, 2008).

Cada acierto prospectivo sobre una intervención es evidencia directa de S1, y esa evidencia es la que da crédito a los contrafactuales históricos.

## 19. Programa de investigación

La teoría hace seis predicciones que pueden fallar. Contrastarlas es el trabajo de la fase F5 y lo que convierte el motor en ciencia.

### 19.1 Conjeturas falsables

| # | Conjetura | Qué predice | Cómo se refuta |
| --- | --- | --- | --- |
| C1 | Granularidad | La parte del presupuesto de contingencia debida a individuos crece con la concentración de poder H | El efecto de las muertes de líderes no varía con las restricciones institucionales en el panel |
| C2 | Dicotomía de colas | Las transiciones disparadas por fuentes de cola pesada tienen κ concentrado y carecen de señal temprana; las de cola ligera, lo contrario | No hay relación entre el índice de cola de la fuente y la presencia de señales tempranas |
| C3 | Fluctuación y disipación histórica | La respuesta a choques exógenos pequeños (volcanes, sequías) se predice con las covarianzas retardadas de los periodos sin choque | La respuesta medida difiere del operador R más allá del error de estimación |
| C4 | Ventanas de vulnerabilidad | En transiciones con componente B, desplazar la fecha una generación cuesta muchos menos nats que evitar la transición | Ambos costes son del mismo orden |
| C5 | Coordenada de reacción de baja dimensión | El logit de h se aproxima con tres variables macro o menos, las mismas en casos distintos | Hacen falta muchas variables, o cambian de un caso a otro |
| C6 | Sucesión y varianza | Los PODs de identidad del líder son más eficientes bajo sucesión hereditaria que bajo selección competitiva, a igual H | Λ no depende de la regla de sucesión |

C5 es la de mayor alcance. Si se cumple, existen parámetros de orden de la dinámica histórica, y los candidatos naturales son capacidad fiscal, cohesión de élites y presión externa.

### 19.2 Resultados que decidirían el proyecto

1. Reproducir los efectos de los experimentos naturales sin haberlos usado para ajustar.
2. Habilidad de hindcast superior a la persistencia a 25 y 50 años, con calibración condicional, prediciendo civilizaciones no usadas en el ajuste.
3. Verificar C3 en al menos una familia de choques.
4. Recuperar efectos, divisorias y PODs plantados en mundos sintéticos con el modelo verdadero fuera de la clase rival.
5. Un año de pronósticos prospectivos prerregistrados con puntuación mejor que la línea base.

### 19.3 Si los resultados son negativos

Si el hindcast no gana a la persistencia a 25 años, o si la dependencia estructural es tan alta que casi todo intervalo de Λ cubre de 0 a 1, la conclusión es que la historia no es predecible a esta resolución con estos datos.

Ese resultado también tiene valor, porque viene con números: un horizonte de predictibilidad medido y una cota de cuánto puede saberse de un contrafactual. El sistema está diseñado para que tanto el éxito como el fracaso sean informativos.

## 20. Antipatrones

Son señales de que el sistema degenera en sobreingeniería recreativa o en ficción con decimales. Si aparece una, se para y se corrige.

**De planteamiento**

- **Relato primero.** Escribir la línea alternativa y después buscar números que la respalden.
- **Teleología.** El modelo da probabilidad casi 1 a la historia real, o los regímenes se definen con los nombres de lo que pasó.
- **PODs por fama.** Elegir PODs porque son célebres (Waterloo, César) en lugar de por resolución y eficiencia.
- **Personajes resucitados.** Napoleón en una línea con POD en 1700.
- **Gran hombre o determinismo por decreto.** Fijar a mano cuánto importan los individuos.

**De modelado**

- **LLM en el bucle.** Cualquier llamada a un LLM por paso o por partícula.
- **Modelo único.** Un solo mecanismo por canal crítico.
- **Estado sin límites.** Añadir variables porque son interesantes, no porque alimentan un observable. Cada variable nueva necesita un test que la use.
- **Silla sin circuito.** Informar de una bifurcación en un mecanismo cuyo grafo de signos no tiene retroalimentación positiva.
- **Barrera sin cola.** Calcular un cuasi-potencial para una fuente de cola pesada.
- **Mismo clima para siempre.** Compartir entre mundos un azar más allá de su tiempo de identidad.

**De medida**

- **Densidad por probabilidad.** Usar el −log de una densidad como sorpresa.
- **Efecto bruto entre sorpresa.** Ordenar PODs por un cociente que diverge cuando el POD tiende a cero.
- **Pares por efectos.** Presentar una magnitud pareada como efecto del POD sin decir bajo qué acoplamiento.
- **Promedio de rivales.** Dar la media ponderada de modelos como respuesta a una intervención.
- **Intervalo fundido.** Sumar en un solo intervalo la incertidumbre de muestreo, la paramétrica y la estructural.
- **Precisión falsa.** Tres decimales en la población de 1250; cuantiles sin horizonte; «probabilidad 0,734» a +200 años.

**De procedimiento**

- **Mover la puerta.** Relajar un criterio de paso porque el modelo no lo supera.
- **Hindcast por licencia.** Publicar un resultado interventivo con solo calibración predictiva, sin la tríada de validez.
- **Simulaciones largas sin aviso.** El modelo constructor no lanza ensembles de horas: entrega scripts con duración estimada y la persona los ejecuta.

## 21. Notación y referencias

### 21.1 Notación

| Símbolo | Significado | Unidad |
| --- | --- | --- |
| x, X(t) | Estado macro híbrido | — |
| b, a = σσᵀ, λⱼ, νⱼ | Deriva, difusión, tasa y ley de marcas de la fuente de salto j | — |
| H | Índice de Herfindahl de la influencia | Adimensional, entre 1/N y 1 |
| αⱼ | Índice de cola de la fuente j | Adimensional |
| τⱼ | Tiempo de identidad entre mundos de la fuente j | Años |
| P, Q | Ley del modelo sobre trayectorias sin POD y con POD | — |
| K, K′ | Núcleo de transición en t₀, original y modificado | — |
| c | Coste del POD: KL(K′ ‖ K) | Nats |
| e | Rastro del POD en un observable | Nats |
| Λ | Eficiencia de palanca: e / c | Entre 0 y 1 |
| h(x, t), πⱼ | Committor de tiempo finito; probabilidades de destino por régimen | Probabilidad |
| M(t) | Martingala del destino: h evaluado en la trayectoria | Probabilidad |
| b(t) | Índice de ambigüedad: 1 − Σπⱼ² | Entre 0 y 1 |
| ρ, r | Contingencia resuelta por paso y su tasa en tiempo continuo | Probabilidad², y por año |
| κ | Coste por paso de la ruta más barata hacia B | Nats |
| g(A; B) | Ganancia en log-probabilidad de B por el suceso A | Nats |
| PN | Probabilidad de necesidad | Probabilidad |
| tₖ, φₖ | Escalas de tiempo y funciones propias lentas | Años, — |
| λ | Racionalidad en la elección de los actores | Inversa de la unidad de utilidad |
| S1, S2, S3 | Suficiencia causal, solapamiento, calibración condicional | — |

Un nat equivale a un factor e en probabilidad: 1 nat es una probabilidad de 0,37; 3 nats, de 0,05; 7 nats, de una entre mil. En la tabla, b sin argumento es la deriva y b(t) el índice de ambigüedad.

### 21.2 Referencias con enlace

- [Ashwin, Wieczorek, Vitolo y Cox (2012)](https://arxiv.org/pdf/1103.0169). Tipping points in open systems: bifurcation, noise-induced and rate-dependent examples in the climate system. Phil. Trans. R. Soc. A 370, 1166–1184.
- [Bai y Kung (2011)](https://econpapers.repec.org/RePEc:tpr:restat:v:93:y:2011:i:3:p:970-981). Climate shocks and Sino-nomadic conflict. Review of Economics and Statistics 93(3), 970–981.
- [Gabaix (2011)](https://econometricsociety.org/publications/econometrica/2011/05/01/granular-origins-aggregate-fluctuations). The granular origins of aggregate fluctuations. Econometrica 79(3), 733–772.
- [Helfmann, Ribera Borrell, Schütte y Koltai (2020)](https://arxiv.org/abs/2002.07474). Extending transition path theory: periodically driven and finite-time dynamics. J. Nonlinear Science 30, 3321–3366.
- [Imkeller y Pavlyukevich (2006)](https://arxiv.org/abs/math/0409246v2). First exit times of SDEs driven by stable Lévy processes. Stochastic Processes and their Applications 116(4), 611–642.
- [Jones y Olken (2005)](https://econpapers.repec.org/RePEc:oup:qjecon:v:120:y:2005:i:3:p:835-864). Do leaders matter? National leadership and growth since World War II. Quarterly Journal of Economics 120(3), 835–864.
- [Jones y Olken (2009)](https://www.nber.org/papers/w13102). Hit or miss? The effect of assassinations on institutions and war. American Economic Journal: Macroeconomics 1(2), 55–87.
- [Oberst y Sontag (2019)](https://proceedings.mlr.press/v97/oberst19a.html). Counterfactual off-policy evaluation with Gumbel-max structural causal models. ICML, PMLR 97, 4881–4890.

### 21.3 Otras referencias

Obras estándar citadas por autor y año. Su ficha completa y cualquier valor numérico tomado de ellas deben comprobarse en la fuente antes de usarse como blanco.

| Tema | Referencias |
| --- | --- |
| Causalidad y contrafactuales | Pearl (2009), Causality; Balke y Pearl (1994), redes gemelas; Tian y Pearl (2000), cotas de las probabilidades de causación; Pearl y Bareinboim (2011), transportabilidad; VanderWeele, Vansteelandt y Robins (2014), efectos interventivos; Abadie y colaboradores, control sintético |
| Reducción de escalas | Kurtz (1970, 1971); Hasselmann (1976), modelos climáticos estocásticos; Pavliotis y Stuart (2008), Multiscale Methods; formalismo de Mori y Zwanzig |
| Multiestabilidad | Soulé (2003), requisitos gráficos de la multiestacionariedad; Arthur (1989), rendimientos crecientes y bloqueo |
| Grandes desviaciones y control | Freidlin y Wentzell (1984); Donsker y Varadhan; transformada h de Doob; Todorov (2009), control con coste KL |
| Caminos de transición y regímenes | E y Vanden-Eijnden (2006); Reuter y otros (2018), GPCCA; Froyland (2013), conjuntos coherentes; Wu y Noé (2020), VAMP |
| Predictibilidad y respuesta | Lorenz (1969); Leith (1975); Kleeman (2002) |
| Colas pesadas en la historia | Richardson (1948); Cirillo y Taleb (2016, 2020); Clauset (2018) |
| Agencia y acción colectiva | McKelvey y Palfrey (1995), equilibrio de respuesta cuántica; Granovetter (1978); Kuran (1989); Morris y Shin (2003) |
| Inferencia con modelos falsos | Kennedy y O'Hagan (2001); Bissiri, Holmes y Walker (2016); Craig y otros (1997); Vernon, Goldstein y Bower (2010); Yao y otros (2018), stacking; Manski (2003), identificación parcial; Lucas (1976); Benjamini y Hochberg (1995) |
| Dinámica histórica y datos | Turchin, teoría demográfico-estructural; Seshat: Global History Databank; HYDE; series de Maddison |
| Límite de N = 1 | Nagy, Farmer, Bui y Trancik (2013); Goldstone (2002), eflorescencias |
| Prospectiva | Grunberg y Modigliani (1954); Lee (2008), elecciones reñidas como experimento |
