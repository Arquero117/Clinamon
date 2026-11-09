# ADR-0005 — El mundo de banco F0

**Estado:** aceptada (F0).

## Decisión

F0 no construye mecanismos históricos (eso es F2). Para probar el motor con un tamaño realista se crea `banco_f0`: 30 entidades en rejilla 5×6, 53 variables por entidad, 15 mecanismos, 12 fuentes de azar (4 de cola pesada), 14 identidades contables y 139 parámetros, todos con procedencia `supuesto`.

## Por qué

- La puerta de rendimiento (§17.1) se define sobre la configuración de §14.3 (unas 30 entidades × 40 variables × 15 mecanismos). Un juguete más pequeño no la pondría a prueba.
- Las identidades contables, los gemelos y el determinismo solo se ponen a prueba de verdad con flujos entre entidades (comercio, migración, territorio), cotas, impagos y saltos de cola pesada.
- Ejercita todo el catálogo de intervenciones de F0: sucesos de supervivencia y muerte, resultado de batalla, brotes, invenciones, erupciones e inclinaciones gaussianas.

## Advertencias

- No es una afirmación histórica ni debe usarse como prior de nada. Su dinámica es deliberadamente simple: la población crece hasta la cota malthusiana en dos o tres siglos, las guerras rara vez cambian la concentración territorial y la deuda tiende a desaparecer.
- Sus fichas de mecanismo declaran circuitos y estructuras no ergódicas a título indicativo. El grafo de signos generado automáticamente es de F2.
- En F1 sus mecanismos pueden servir de «modelo verdadero» para un mundo sintético, pero los juguetes canónicos de §13.2 se construyen aparte.
