# Informe de la puerta F0 (Cimientos)

- Prerregistro: `prerregistro/F0_puerta.yaml`, sha256 `3743341b7e43585b1645294483ccef7af98e10cc95cf49997c90120abaa30bf3` (verificado, sin cambios).
- Código: versión 0.1.0, commit `a9d598dcd0269567415f6ea1722df228007dbfe9`.
- Ontología `banco_f0`: huella `6357d1099bb93957…`.
- Entorno: Python 3.13.18, NumPy 2.5.3, x86_64.
- Duración del ensayo: 43 s.

## Resultado: PUERTA SUPERADA

| Criterio | Medida | Umbral prerregistrado | Resultado |
| --- | --- | --- | --- |
| Determinismo: repetición idéntica (sha256) | True | sí | ✅ supera |
| Determinismo: invariancia al tamaño de bloque | True | sí | ✅ supera |
| Determinismo: invariancia al nº de procesos | True | sí | ✅ supera |
| Determinismo: reanudación idéntica | True | sí | ✅ supera |
| Determinismo: brazo base = ensemble | True | sí | ✅ supera |
| POD nulo: máx. diferencia absoluta (18 combinaciones variante × acoplamiento × semilla) | 0.0 | 0.0 | ✅ supera |
| POD nulo: control positivo (inclinación v = 1e-6, coste 5e-13 nats; el detector la ve) | 3.38e+06 | > 0 | ✅ supera |
| Identidades contables: fracción de pasos superados (960 pasos, 14 identidades) | 1.0 | 1.0 | ✅ supera |
| Rangos declarados: fracción de pasos superados | 1.0 | 1.0 | ✅ supera |
| Rendimiento (µs por trayectoria-año, 1 núcleo, Philox Numba) | 27.7 | ≤ 200 | ✅ supera |
| Rendimiento (µs por trayectoria-año, 1 núcleo, NumPy puro) | 45.6 | ≤ 200 | ✅ supera |
| Configuración del ensayo de rendimiento | 30 entidades, 53 variables/entidad, 15 mecanismos | ≥ 30, 40, 15 | ✅ supera |

## Qué no valida esta puerta

- Nada sobre la historia: el mundo `banco_f0` es de prueba y sus parámetros son supuestos.
- Ni Λ ≤ 1 ni el estimador del rastro: son puerta de F1.
- El rendimiento se mide en la máquina donde se ejecuta el ensayo; en otra máquina hay que repetirlo (`clinamen puerta-f0`).
