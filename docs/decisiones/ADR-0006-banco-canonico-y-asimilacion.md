# ADR-0006 — Banco canónico, estimadores de contingencia y asimilación (F1)

**Estado:** aceptada (F1). **Afecta a:** §6, §8, §11, §13.2 (M6, M8, M10).

## 1. Los juguetes son cadenas finitas

Cada sistema continuo de §13.2 se discretiza en una rejilla; la cadena de Markov resultante **es** el juguete:
se simula con Philox y se calcula exactamente con los mismos núcleos. Así h, ρ (Teorema 2), κ (Teorema 3,
transformada h de Doob), coste, rastro y Λ (Teorema 1) y el espectro son exactos por álgebra lineal para el
mismo modelo que se simula, y la comparación con los estimadores no mezcla error de discretización con error
de estimación. El límite homogeneizado del juguete lento-rápido (Green-Kubo) se valida aparte: su committor
coincide con el del sistema completo con error < 0.006.

## 2. Estimadores de M8: solo ven trayectorias

- **Committor**: regresión logística por instante sobre B-splines cúbicos (12 nodos) en rasgos continuos e
  indicadores en rasgos con ≤ 5 valores. Una base polinómica de grado 6 se probó primero y fallaba en
  transiciones bruscas (saltos de cola pesada, escalón final de la urna).
- **Presupuesto (Teorema 2)**: Σ(Δĥ)² está sesgado al alza por el ruido de ĥ. Se usa el producto cruzado
  Δĥ¹·Δĥ² de dos ajustes independientes evaluados en trayectorias ajenas a ambos, que no hereda ese sesgo.
  Su error típico se estima con **lotes independientes** (16 repeticiones completas): el bootstrap sobre
  trayectorias de prueba lo subestimaba porque ignora el ruido del ajuste.
- **Perfil κ (Teorema 3)**: κ̂_t = media sobre trayectorias que acaban en B de log ĥ_{t+1} − log ĥ_t (la
  densidad de la transformada h). Su suma telescopa a −log ĥ_0; el contraste con −log P̂(B) suma ambas
  fuentes de error.
- **Rastro**: cota de Donsker-Varadhan con el log-cociente ajustado en una mitad y evaluado en la otra.

### 2.1 Committor de la puerta: estimador saturado (iteración 3)

La puerta F1 falló dos veces en el criterio del committor con la regresión logística por B-splines (12 nodos,
luego 12/32 por validación cruzada). Causa raíz: tamaños de Monte Carlo que incumplían la regla prerregistrada
(error típico ≤ 1/5 del umbral) y un error típico de modelo que no recoge el sesgo de suavizado. Tras dos
iteraciones, §17.2 manda simplificar el modelo: el criterio usa ahora el estimador **saturado** (frecuencia de B
por estado e instante, error típico binomial), acumulado por tramos con 16 millones de trayectorias por juguete.
La regresión con B-splines sigue siendo el estimador para los Teoremas 2 y 3 (validados) y para estados
continuos, donde el saturado exige discretizar; en el motor completo habrá que validarla de nuevo (F2).

## 3. Asimilación (M6)

- Filtro de partículas bootstrap sobre el propio motor: columnas = M valores de θ × K partículas, remuestreo
  sistemático por bloque, log p̂(y|θ) insesgado en escala natural.
- Muestreo por importancia adaptativo y pseudo-marginal sobre θ (3 etapas: prior, luego t de Student ajustada
  más 10 % de prior). Las muestras conjuntas (θ, x_t0) salen de la posterior de filtrado.
- **Sucesos observados** (crónica de sucesiones, §16 paso 4) entran por condicionamiento con la propuesta
  óptima K(·|A), y su probabilidad K(A) se suma al peso de la partícula: la misma maquinaria que un POD-suceso.
- **Lección registrada**: observar con precisión un integrador sin ruido propio (la población) degenera el
  filtro (desviación de log p̂ ≈ 10 nats). El mundo sintético observa, como las fuentes reales, solo una
  codificación ruidosa de la capacidad (σ = 0.8, 60 % de huecos) y la crónica completa de sucesiones. Cuando
  F2 asimile series demográficas reales habrá que dar ruido de proceso a la población o usar propuestas guiadas.

## 4. Mundo sintético y POD plantado

`sintetico_f1`: seis entidades en dos componentes desconectadas; los PODs sobre la componente 3–5 tienen efecto
nulo en ley sobre `capacidad_0` y sirven para medir la tasa de falsos descubrimientos. El POD plantado es la
muerte del gobernante de la entidad 0 en t0 (choque de sucesión). El horizonte es H = 5: a H = 10 el choque ya
se ha absorbido (efecto transitorio, §8.3) y el plantado no destacaba. La decisión se tomó con semillas de
desarrollo, antes de usar las de puerta.

## 5. Límites conocidos

- La cobertura se mide con el modelo bien especificado. La mala especificación es puerta de F3.
- Con ESS de θ en torno a 60, la posterior de θ está representada de forma gruesa. Para θ de más dimensión
  harán falta más etapas o SMC² completo.
- Faltan: división multinivel adaptativa para desenlaces raros, GPCCA para más de dos regímenes y
  presupuesto por fuente en el motor completo. Se construirán cuando un caso los necesite (F2–F4).
