# Registro de desviaciones locales de walldetect

Origen conservado: cad2ingetrazo, `cad2ingetrazo/engine/walldetect.py`, revisión de vendorización de4ba88, GPL-3.0-or-later. Se mantienen la cabecera de procedencia y sus autores. La cabecera ya no dice «sin cambios»: enumera los cambios locales R14-b.

| Zona | Desviación | Protección/prueba |
|---|---|---|
| Preparación de caras | Nueva `_contiguous`, conserva trazos continuos antes de aplicar MIN_LEN | Tabiques fragmentados y hueco que mantiene 0,90 m; no puenteo indiscriminado |
| `_pairs` | Excepción acotada para solapes cortos de tabiques ≤0,125 m | Espesores y ruido: no se reduce globalmente el tamaño mínimo de un muro |
| `_gap_kind` | Tolerancia angular de giro respecto a pivote de marco; evidencia doble fuerte sin exigir hojas dibujadas | Marcos abiertos, pivotes retranqueados, giros en lados opuestos |
| `_gap_kind` | Cobertura de vidrio y evidencia múltiple, en lugar de suma bruta de longitudes cercanas | Machones con trazo próximo; vidrio fragmentado/retranqueado y alféizar |
| `walls_from` | Separación por discontinuidad; nuevo `_recess_front` con dos retornos y puerta posterior | Evitar frente duplicado y conservar puertas realmente respaldadas |

La comparación AST de `_pairs`, `_runs`, `_gap_kind` y `walls_from` de nuestra base con la instantánea upstream e3592e61100580368fd4943579c1ac4a9944348e dio igualdad en las cuatro funciones. Es una comparación contra la instantánea ya conservada, no una comprobación de la rama remota actual ni un consentimiento del autor.

Valoración: la unión de trazos contiguos y los casos de giro/vidrio podrían ser útiles upstream tras revisión; la detección de retranqueo es más dependiente de convenciones y debe mantenerse experimental. No se recomienda enviar ahora un bloque de cambios sin confirmar primero la versión actual y las conversaciones del autor. No se crea issue, PR, comentario ni mensaje, y nunca se enviaría un plano privado como reproducción.

La declaración literal exigida para una comunicación futura es: «He revisado los antecedentes del repositorio, las intervenciones de Urkoh00 y el historial de cambios. La propuesta no duplica ninguna comunicación anterior sin resolver o ya resuelta». No se emite aquí como certificación de una comunicación nueva: no se propone ninguna ni se ha realizado esa revisión remota específica completa.
