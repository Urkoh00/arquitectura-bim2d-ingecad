# Entrada revisada en LINEASAMURO

Contrato adoptado para el intercambio de geometría revisada con el laboratorio,
según las decisiones del propietario y Claude del 18-11-2026. Esquema único:
`arq.entrada-revisada/v1`. Integrado en la v1.32.0-dev (propuesta sobre v1.31.0-dev,
`2a2b4a0060ca52bdadabb5b0177cf3d091c4c9b6`).

El plugin recibe **geometría DXF y su revisión**, no código, XDATA, registros BIM
ni un plan interno de conversión. La lectura geométrica y la creación BIM siguen
siendo las funciones del plugin. El laboratorio no se modifica en esta entrega.

## 1. Nombre y ubicación

Para `plano.dxf`, el fichero obligatorio es **`plano.dxf.procedencia.json`**, en
la misma carpeta. El nombre incluye la extensión `.dxf`; no se usa otro sufijo.
El laboratorio debe calcular el SHA-256 **después de escribir el DXF definitivo**.
Si vuelve a guardarlo, incluso sin cambios geométricos, debe recalcular ese hash.

LINEASAMURO busca ese fichero al iniciarse sobre un dibujo guardado. También
puede cargarse desde «Cargar procedencia de entrada revisada…» en el cuadro o
escribiendo `Procedencia` en la orden y después la ruta al JSON. Cargar el fichero
no modifica el dibujo ni añade un paso de Deshacer.

## 2. Esquema mínimo

```json
{
  "schema": "arq.entrada-revisada/v1",
  "dxf": {
    "name": "plano.dxf",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "source": {
    "name": "croquis.pdf",
    "sha256": "1111111111111111111111111111111111111111111111111111111111111111"
  },
  "units": "m",
  "scale_checked": true,
  "review": {
    "state": "revisado",
    "date": "2026-11-18",
    "reviewer": "Revisor del ejemplo"
  },
  "layers": {
    "REV-MURO-CARA": {"role": "muro-cara", "state": "confirmado"},
    "REV-MURO-EJE": {"role": "muro-eje", "state": "confirmado"},
    "REV-PUERTA": {"role": "puerta", "state": "confirmado"},
    "REV-VENTANA": {"role": "ventana", "state": "pendiente"},
    "REV-HUECO-CANDIDATO": {"role": "hueco", "state": "candidato"}
  },
  "entities": {
    "2A": {"state": "rechazado"},
    "2B": {"state": "confirmado"}
  }
}
```

Los hashes anteriores son **ilustrativos**. Los handles deben existir en el DXF;
el ejemplo no es un manifiesto válido para cualquier dibujo. El juego sintético
de la entrega incluye un par DXF/JSON con hashes y handles reales.

| Campo | Regla |
|---|---|
| `schema` | Cadena exacta `arq.entrada-revisada/v1`; obligatorio. |
| `dxf.name` | Nombre local terminado en `.dxf`, sin ruta. El fichero debe estar junto al JSON. |
| `dxf.sha256` | 64 caracteres hexadecimales en minúsculas; debe coincidir con los bytes del DXF. |
| `source.name`, `source.sha256` | Nombre no vacío y SHA-256 con formato válido de la fuente original. **Solo informativos**: el plugin no busca, abre ni verifica ese original. |
| `units` | Cadena exacta `m`. No se convierte ninguna unidad. |
| `scale_checked` | Booleano JSON `true`. `false`, `1`, `"sí"` o su ausencia no autorizan. Es la declaración del revisor, no una certificación automática de escala. |
| `review.state` | Cadena exacta `revisado`. |
| `review.date` | Fecha existente en formato `AAAA-MM-DD`. |
| `review.reviewer` | Opcional; cadena no vacía. No se exige nombre personal. |
| `layers` | Objeto con **todas y solo** las capas `REV-*` definidas en el DXF, incluidas las vacías. Los nombres se comparan sin distinguir mayúsculas; no se admiten duplicados con distinta capitalización. |
| `layers.<capa>.role` | `muro-cara`, `muro-eje`, `puerta`, `ventana` o `hueco`. |
| `layers.<capa>.state` | `confirmado`, `pendiente`, `rechazado` o `candidato`. |
| `entities` | Opcional. Objeto por handle original del espacio modelo, con **solo** `state`. Debe identificar una entidad de capa `REV-*`. |

Las excepciones por entidad **sustituyen el estado**, conservando el papel de la
capa. Así puede confirmarse una cara en una capa pendiente, o excluirse una cara
en una capa confirmada. Una excepción no convierte un eje en cara de muro.
No se admiten campos desconocidos ni claves JSON duplicadas. El límite del JSON
es 4 MiB y el de excepciones, 200 000 entidades. No se admiten varios esquemas ni
se preparan migraciones.

El DXF puede declarar `$INSUNITS=6` (metros) o `0` (sin unidad declarada, que aquí
queda documentada mediante `units: "m"` y `scale_checked: true`). Otra unidad no
activa el modo. El plugin conserva además sus comprobaciones geométricas de
escala, espesores y carpinterías; la declaración no las anula.

## 3. Qué se propone

| Papel | Estado efectivo | Propuesta |
|---|---|---|
| `muro-cara` | `confirmado` | Cara para el emparejamiento y lectura de muro existentes. |
| `puerta` | `confirmado` | Puerta, con comprobación geométrica existente. |
| `ventana` | `confirmado` | Ventana, con comprobación geométrica existente. |
| Cualquiera | `pendiente`, `rechazado` o `candidato` | No convertir. |
| `muro-eje` | Cualquiera, incluso `confirmado` | No convertir: sigue siendo auxiliar. |
| `hueco` | Cualquiera, incluso `confirmado` | No convertir automáticamente: R22 autoriza puertas y ventanas confirmadas como tales, no vanos genéricos sin definición. |

El nombre de la capa no determina su papel: lo determina el contrato. Una
asignación gráfica o una categoría seleccionada manualmente no puede saltarse
la revisión. Durante el modo revisado solo se leen las entidades autorizadas;
los trazos no incluidos no sirven como evidencia de puertas, ventanas ni segunda
cara de un muro. Las capas comunes mantienen el comportamiento habitual cuando
el modo no está activo.

Se admiten primitivas del espacio modelo: LINE, LWPOLYLINE, ARC y los contornos
HATCH/SOLID/TRACE que ya admite el lector. Los bloques de la entrada revisada se
conservan para revisión: no se atribuyen estados a hojas virtuales sin identidad
estable. Los bloques de planos normales conservan su lectura habitual.

Si las caras tienen una interrupción que el lector interpreta como vano, pero
no hay puerta o ventana confirmada que lo respalde, **el muro afectado permanece
como dibujo para revisión**. Se informa en la vista previa. No se crea un vano
no confirmado ni un muro continuo que rellene el hueco. Los demás muros válidos
pueden convertirse. La clasificación no garantiza que toda cara pueda emparejarse.

## 4. Rechazo y vigencia de la vista previa

Sin fichero, con esquema desconocido/ausente, hash distinto, escala sin comprobar
o cualquier incumplimiento, **no se activa** la entrada revisada. LINEASAMURO
informa del motivo y continúa como plano normal, con `REV-*` en No convertir.
Se protege tanto la ruta con cuadro como el lector directo sin cuadro; REV-*
tampoco se usa como contexto auxiliar en esa ruta.

Al cargar se compara también la geometría y los handles del DXF guardado con el
dibujo activo. Los cambios no guardados no heredan la revisión del fichero viejo.
Antes de analizar y antes de confirmar se vuelven a comprobar el hash del DXF,
el del JSON y la huella del dibujo. Si cambia cualquiera, se rechaza la vista
previa y hay que revisar/cargar/analizar de nuevo. No se modifica parcialmente.
La revisión describe una instantánea completa: después de convertir una zona,
el dibujo ya ha cambiado y esa revisión no se reutiliza para otra conversión
sin actualizar el DXF y su procedencia. Deshacer restaura la instantánea previa.

Confirmar utiliza las órdenes existentes del plugin y su transacción: creación
de muros y carpinterías, tratamiento del dibujo de origen y regeneración son
**un solo Deshacer**. Las entidades excluidas se conservan.

## 5. Pruebas y alcance

`tests/test_entrada_revisada.py` cubre aceptación, prioridad por entidad, ejes,
candidatos, huecos, rangos, carga contigua, vista previa, Deshacer/Rehacer y los
motivos de rechazo por separado. La suite existente comprueba que los planos
normales conservan su comportamiento.

Solo se ensayan las últimas publicaciones: IngeCAD 0.8.0 e IngeTrazo 0.6.2.1.
No se añade compatibilidad con archivos ni versiones anteriores. La carpeta
`ingetrazo_ext/arq_shared/` sigue generándose con el script y no se versiona.
No se desarrolla ni modifica aquí el laboratorio ni se incorpora código suyo.
