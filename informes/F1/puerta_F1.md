# Informe de la puerta F1 (Banco canónico y mundo sintético)

- Prerregistro `prerregistro/F1_puerta.yaml`, sha256 `7f9e9e3fcccb3f028b6226951c37c3507aa0d717c558fe5c01a74e102d48cafc` (verificado, sin cambios).
- Código: versión 0.1.0, commit `8b46f42da2a69c35c8f492d50b8dbad53bb2beb4`. Semillas de puerta usadas por primera vez en esta evaluación.
- Cómputo: 1.58 h de CPU en total (0.20 h con 8 núcleos); 18 min de reloj con 4 procesos.

## Resultado: PUERTA NO SUPERADA

## Juguetes (semilla 910001)

| Juguete | P(B) | ĥ: error máx. / e.t. máx. | Teorema 2: Σρ̂ − M₀(1−M₀) | Teorema 3: Σκ̂ + log P̂(B) ; L1 | Λ̂ ± e.t. (exacto) |
| --- | --- | --- | --- | --- | --- |
| doble_pozo_gaussiano | 0.284 | 0.0341 / 0.0120 ❌ | +0.0003 ± 0.0010 ✅ | -0.0040 ± 0.0087 ; 0.017 ✅ | 0.0189 ± 0.0004 (0.0193) ✅ |
| doble_pozo_estable | 0.060 | 0.0410 / 0.0184 ❌ | -0.0006 ± 0.0005 ✅ | +0.0188 ± 0.0227 ; 0.043 ✅ | 0.2742 ± 0.0017 (0.2755) ✅ |
| urna_polya | 0.494 | 0.0221 / 0.0082 ✅ | +0.0019 ± 0.0008 ✅ | -0.0024 ± 0.0059 ; 0.016 ✅ | 0.2876 ± 0.0035 (0.2878) ✅ |
| lento_rapido | 0.130 | 0.0301 / 0.0195 ✅ | -0.0005 ± 0.0007 ✅ | -0.0208 ± 0.0145 ; 0.041 ✅ | 0.0082 ± 0.0004 (0.0082) ✅ |
| doble_pozo_deriva | 0.444 | 0.0116 / 0.0098 ✅ | -0.0007 ± 0.0010 ✅ | -0.0091 ± 0.0062 ; 0.027 ✅ | 0.0058 ± 0.0002 (0.0059) ✅ |

Umbrales: ĥ ≤ 0.02 o ≤ 3 e.t.; Teoremas 2 y 3 ≤ 3 e.t.; L1 del perfil κ ≤ 0.10; Λ̂ ∈ [0.8 Λ, Λ + 3 e.t.] y Λ̂ − 2 e.t. ≤ 1.

## Mundos sintéticos

| Criterio | Medida | Umbral | |
| --- | --- | --- | --- |
| Cobertura del IC 90 % del efecto del POD plantado (200 mundos, semilla 910002) | 0.925 | [0.85, 0.95] | ✅ |
| POD plantado entre los 3 primeros (50 mundos, semilla 910003) | 0.940 | ≥ 0.80 | ✅ |
| FDR (Benjamini-Hochberg, q = 0.05; 6 nulos de 12 candidatos) | 0.023 | ≤ 0.05 | ✅ |
| Λ̂ − 2 e.t. ≤ 1 en todos los PODs (juguetes y candidatos) | 1.000 | 1.0 | ✅ |
| Cómputo con 8 núcleos | 0.20 h | ≤ 1 h | ✅ |
| ESS mediana de θ en la asimilación | 58 | (informativo) | |

## Qué no valida esta puerta

- Nada histórico: los juguetes y el mundo sintético no describen ninguna sociedad.
- La cobertura se mide en el caso bien especificado (el modelo verdadero pertenece a la clase). La mala especificación (experimentos cruzados entre rivales) es puerta de F3.
- La consulta evaluada es la I (variante de hindcast). Las consultas II y III no son validables (§13.1).
- Los juguetes y el mundo sintético son discretizaciones y modelos pequeños; el rendimiento en el motor completo se mide en cada caso.
