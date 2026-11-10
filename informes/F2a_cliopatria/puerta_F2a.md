# Validación de la iteración 2 de F2a con datos nuevos (Cliopatria)

- Prerregistro `prerregistro/F2a_cliopatria.yaml`, congelado ANTES de escribir las correcciones del modelo y
  antes de construir el panel de Cliopatria; umbrales de F2a (aprobados por la persona) sobre el territorio.
- Datos que ningún modelo había visto: áreas de las polities según los mapas de Cliopatria v0.2.1 en las 35
  coordenadas de las NGA de Seshat, por siglos (−3400…1900). 556 siglos-región; 275 predicciones fuera de
  muestra en el origen móvil y 504 en las grandes regiones dejadas fuera. Semilla 930001, evaluada una vez.
- Modelo de la iteración 2: los tres rivales de F2a con probabilidad de continuidad q(y) y escala del cambio
  dependientes del nivel. Código: commit 9f5ef98.

## Resultado: NO SUPERADA

| Criterio | Resultado | Umbral | |
| --- | --- | --- | --- |
| Habilidad frente a la persistencia, territorio a 100 años | −2.1 % (cota inferior 90 %: −7.2 %) | cota > 0 | ❌ |
| Habilidad frente a la persistencia, territorio a 200 años | −5.0 % (cota inferior 90 %: −10.6 %) | cota > 0 | ❌ |
| Cobertura del 90 % (100, 200, 300 años) | 0.925 / 0.857 / 0.890 | [0.85, 0.95] | ✅ |
| Cobertura del 50 % (100, 200, 300 años) | 0.613 / 0.418 / 0.440 | [0.43, 0.57] | ❌ (2 de 3) |
| Cobertura del 90 % por gran región (≥ 30 predicciones) | 0.84 – 0.97 | [0.75, 0.98] | ✅ |
| Inevitabilidad: PIT medio por gran región | 0.48 – 0.64 | [0.2, 0.8] | ✅ |
| Civilización no usada: grandes regiones con habilidad > 0 | 6 de 10 (dos con 1 y 11 predicciones) | ≥ 7 | ❌ |
| Chapman-Kolmogorov (territorio en 5 tramos) | 88 % | ≥ 80 % | ✅ |
| Cómputo | 62 s | ≤ 1 h con 8 núcleos | ✅ |

CRPS medio del territorio (menor es mejor): a 100 años apilado 0.234 frente a persistencia 0.229; a 300 años
0.417 frente a 0.391. El modelo sigue ganando con holgura a la tendencia y a la climatología.

## Cautelas

- La regla prerregistrada toma, en cada punto, la polity de mayor área que lo contiene, que a veces es una
  relación de vasallaje de Cliopatria (p. ej. «Allegiance of Seleucid Empire to Roman Republic»). Eso mete
  saltos que no son conquistas; no se tocó la regla.
- Los mapas no cubren todos los lugares en todas las épocas: muchas series tienen huecos y los orígenes
  antiguos casi no tienen historia previa (regla MIN_CAMBIOS, fijada antes de evaluar).
