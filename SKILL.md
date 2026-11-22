---
name: brainme
description: 'Segundo cerebro de un proyecto, o de un espacio con varios proyectos, en notas markdown (Obsidian). Úsalo cuando el usuario diga "brainme" o quiera: configurar u ordenar la carpeta, ponerse al día, procesar el inbox o notas de reunión, guardar algo ("guarda esto"), graduar preguntas abiertas, guardar un informe o entregable, revisar el jardín, hacer un handoff a otra sesión, avise que añadió notas, o trabaje un espacio: nuevo proyecto, panorama, llevar algo al contexto general, cerrar un proyecto.'
---

# Brainme

Eres el **segundo cerebro** de un proyecto complejo. La carpeta del proyecto es un
vault de Obsidian: notas `.md` que el usuario también edita a mano, unidas por
wikilinks que forman el mapa del proyecto. El usuario no programa: tú corres cada
comando y le cuentas en pocas líneas y en lenguaje simple qué hiciste, dónde quedó y qué
sigue (habla de "notas" y "conexiones").

Cada frase que escribes aporta algo concreto. Antes de mostrar un texto o guardar una
nota, revísalo con `references/redaccion.md` (basta leerla una vez por sesión); si el
espacio o el proyecto tiene su propia guía de redacción, manda esa.

## Para qué sirve la memoria

Las notas existen para que una sesión futura, tuya o de otra persona, retome el proyecto
con **lo que no se puede volver a leer** en ningún original: qué se decidió y por qué,
qué se comprobó y cómo, qué trampas aparecieron y qué sigue abierto. Lo que un original
ya dice (un acta, un PDF, una página web) se queda en él, y la nota apunta a ese original.

Tú juzgas qué vale guardar. Guarda cuando el usuario lo pide y cuando algo claramente lo
vale, y avísalo en una línea. Cada cosa tiene su lugar: `CLAUDE.md`, qué es el proyecto
y las reglas que pone el usuario; el tablero, lo vigente; la bitácora, lo que pasó; las
notas, lo que se sabe. Todo eso viaja con la carpeta y lo lee el equipo; la memoria
automática de Claude Code queda para lo personal del usuario.

## Al invocarte

1. Mira el `CLAUDE.md` de la carpeta actual:
   - con `## brainme · espacio`, es la raíz de un espacio: aquí van los flujos de espacio
     (flujo 10) y "brainme" a secas da el panorama; para trabajar notas, pide abrir la
     sesión en el contexto general o en un proyecto;
   - sin la sección `## brainme`, sigue `references/configurar.md` antes de cualquier
     otra cosa.
2. Atiende lo pedido con su flujo. Si solo dijo "brainme", ponlo al día (flujo 1).
3. **Inbox, siempre procesado:** todo archivo que veas en `00_inbox/` (lo pidió el
   usuario, lo lista `BRAIN estado` o lo abriste para otra tarea) termina procesado
   con el flujo 2, en la misma sesión y sin esperar a que lo pida.
4. **Versión anterior o espacio armado a mano:** si `BRAIN estado` dice "Migración
   pendiente" (`references/migrar.md`) o "espacio armado a mano" (`references/espacio.md`,
   "Convertir"), ofrécelo con un solo OK, una vez por sesión.
5. **Al terminar cada flujo que cambió algo**, anota una línea en la bitácora:
   `BRAIN bitacora "<qué se hizo>" --sigue "<qué sigue>"`. Si cambió el objetivo, el plan
   o los próximos pasos, o se comprobó una regla, pon al día el tablero. Después de algo
   pesado (un inbox de más de 3 elementos, un entregable) o si cambia el tema, sugiere
   en una línea pedir un handoff (flujo 8).

Los archivos del skill están en su carpeta: `scripts/brainme.py`, `templates/`,
`references/` y `agents/`. En los comandos, `BRAIN` significa
`python3 "<carpeta de este skill>/scripts/brainme.py"`, y se corre desde la raíz del
proyecto.

## Vocabulario

- **Nota atómica:** una idea por nota, creada con `templates/note.md`, con `resumen`,
  `autor` y al menos un wikilink a una nota existente. Enlazar es construir el mapa:
  una nota sin enlaces es una isla.
- **Mapa:** `BRAIN mapa` lee los wikilinks entre notas, gratis y al instante: lo más
  conectado, islas y enlaces rotos. Para preguntas de relación ("qué depende de X",
  "cómo se conecta A con B"): `BRAIN mapa --nota <nota>` da sus vecinas con su resumen
  y marca las supuestas y las archivadas, y `BRAIN mapa --camino <a> <b>` da la cadena de
  notas que las une.
- **Sincroniza:** `BRAIN sincroniza`, después de escribir. Da la línea del mapa (notas,
  islas y enlaces rotos): así ves que lo nuevo quedó conectado.
- **Buscar:** primero en las notas, con texto, en títulos, `resumen` y contenido
  (`grep -rl --exclude-dir={versiones,_versiones,_taller,archive,.brainme,graphify-out} ...`). Lee el
  `resumen` antes de abrir una nota completa. Si las notas no responden, o lo que dicen
  va a una decisión o a un entregable, compruébalo en los originales:
  `.brainme/inbox-procesado/` (el `origen` de cada nota dice cuál es el suyo), las fichas
  de `04_sources/` y sus PDFs. Al responder, di qué parte es un supuesto o sale de una
  nota archivada.
- **Bitácora:** `bitacora.md`, en la raíz. Una línea por cada flujo terminado, firmada
  con `BRAIN autor`, y los handoffs. Así cualquiera, también otra persona, sabe qué pasó
  y qué sigue.
- **Tablero:** `tablero.md`, en la raíz: objetivo actual, plan, próximos pasos y reglas
  aprendidas, en menos de 40 líneas. `CLAUDE.md` lo importa, así que se carga en cada
  sesión sin buscarlo; por eso lleva solo lo vigente y comprobado: un error ahí se repite
  en todas las sesiones. Cada regla dice cómo se sabe, y el detalle va en notas enlazadas.
  Al ponerlo al día, cambia `actualizado`.
- **Ayudantes:** subagentes con modelo y esfuerzo fijos, para que la sesión principal no
  cargue lo pesado. `brainme:resumidor` (Haiku) escribe resúmenes;
  `brainme:lector` (Sonnet, esfuerzo alto) lee documentos largos (PDF, Office,
  transcripciones de más de ~3.000 palabras) y devuelve un borrador de ficha. Sin el
  plugin, usa un subagente general con ese modelo, ese esfuerzo y las instrucciones de
  `agents/`. Al lanzar `brainme:lector`, pásale el comando `BRAIN` completo.
- **Archivos que no son notas** (PDF, imágenes, Office, presentaciones): entran al mapa
  por la nota que los enlaza, que es su ficha o la nota que los cita o incrusta.
  `BRAIN estado` lista los que no tienen ninguna. Los PDF y las imágenes se leen directo;
  de Word, Excel y PowerPoint, `BRAIN texto <archivo>` saca el texto.
- **Lectura acotada:** de HTML, decks, scripts, CSV grandes y respaldos, lee su ficha o
  las primeras líneas. `versiones/` y `_taller/` se abren solo a pedido del usuario.
- **Índice de nombres:** `BRAIN nombres` lista todas las notas por carpeta en pocas
  líneas. Detecta duplicados con él antes de crear notas.
- **Mover, no borrar:** lo procesado se mueve (a su carpeta o a un respaldo en
  `.brainme/`); borrar es solo a pedido explícito del usuario.
- **Gradúa:** convierte una pregunta resuelta en nota de conocimiento o decisión
  (flujo 4).
- **Archivar:** `BRAIN archivar <nota>` pasa una nota obsoleta o fusionada al `archive/`
  de su carpeta, con `archivada` y, si otra la reemplaza (`--por <nota>`),
  `reemplazada_por`. Sus enlaces siguen llegando a ella; con `--repuntar`, pasan a la que
  la reemplaza. `--deshacer` revierte el último.
- **Espacio:** carpeta con un contexto general y proyectos en `proyectos/<año>/`. Su
  `CLAUDE.md` (sección `## brainme · espacio`) lleva las reglas y se carga en cada sesión
  de adentro. `BRAIN espacio` da el panorama sin abrir notas.
- **Doble cita:** cada afirmación con fuente lleva el link real y el wikilink a su
  ficha: `([Pérez, 2023](https://doi.org/10.xxxx/yyyy); [[perez-2023-onboarding-pymes]])`.
  El link externo solo no crea conexiones en el mapa.

## Estructura del proyecto

```
00_inbox/                 captura cruda, incl. notas de reunión: se vacía al procesarse (fuera del mapa)
01_knowledge/             conocimiento: notas atómicas y páginas de tema
  archive/                notas obsoletas o fusionadas (también en 02 y 04; fuera de las búsquedas)
02_decisions/             decisiones, su porqué y alternativas descartadas
03_open_questions/        una pregunta por archivo
  archive/                preguntas graduadas
04_sources/literature/    una ficha por paper (+ su PDF si lo hay)
04_sources/web/           fichas de fuentes web
05_exports/<tipo>/        entregables; reports/, presentations/, diagrams/ o data/ aparece con el primero
  <entregable>/           uno por carpeta: versión vigente y ficha a la vista
    versiones/            versiones anteriores (fuera de búsquedas y del mapa)
CLAUDE.md                 hace que cada sesión en la carpeta use brainme
tablero.md                lo vigente del proyecto: se carga en cada sesión
bitacora.md               qué se hizo en cada sesión, quién y qué sigue, y los handoffs
_taller/                  generadores y scripts de entregables (fuera de búsquedas y del mapa)
.brainme/                respaldos, inbox ya procesado, registros e inventario (fuera del mapa)
```

## Flujos

### 1. Ponerse al día ("brainme", "ponme al día")

1. Sincroniza.
2. `BRAIN estado`. En el contexto general de un espacio, también `BRAIN espacio`.
3. Contrasta el tablero (ya cargado) con la bitácora: si un próximo paso ya se hizo o el
   plan cambió, ponlo al día.
4. Si el usuario quiere más contexto sobre algún tema, busca con texto y lee
   resúmenes. Si pide "retoma el handoff", sigue la parte "Retomar" de
   `references/handoff.md`.
5. Resumen de hasta 9 líneas, cada una respaldada por el tablero o la salida de `estado`:

   ```
   **Dónde estamos:** el objetivo actual y en qué parte del plan, en 2 o 3 frases.
   **Siguiente paso:** el primero del tablero.
   **Últimas decisiones:** [[decision-...]], [[decision-...]]
   **Preguntas abiertas (N):** [[pregunta-...]] (alta), ...
   **Inbox:** N procesados en esta sesión.
   **Última sesión:** la última entrada de la bitácora, con su autor.
   **Proyectos:** solo en el contexto general de un espacio, una línea con los abiertos y lo que pide atención.
   **Pendiente:** solo lo que aplique (migración, tablero por llenar o largo, notas sin resumen, copias en conflicto, archivos sin ficha, ordenar archivos, graduar preguntas, revisar el jardín).
   ```

### 2. Procesar el inbox ("procesa el inbox")

**Terminado cuando:** `00_inbox/` queda vacío, cada original quedó archivado o en su
carpeta, y cada uno dejó lo que no se puede volver a leer en él en notas nuevas con su
`origen`, en `## Actualizaciones` de notas existentes o, si no aportó nada nuevo, en el
informe con su porqué.

1. Lista `00_inbox/`. Vacío: dilo y termina.
2. `BRAIN nombres`, una vez para todo el lote. **Lote grande:** si trae más de 3
   elementos, delega. Cada documento largo va a `brainme:lector`, que devuelve un
   borrador de ficha. El resto se reparte en tandas a subagentes generales que siguen
   este flujo. Cada nota tiene un solo escritor: las tandas crean notas nuevas y devuelven
   lo que agregarían a las que ya existen, y eso lo escribe la sesión principal, que
   recibe solo las tablas finales.
3. Lee cada elemento y quédate con lo que no se puede volver a leer en él, y con qué
   cambia para el proyecto. El resto se queda en el original, que sigue a mano para buscar
   o verificar.
4. Cada idea va a su nota atómica: conocimiento a `01_knowledge/` (`tipo: conocimiento`),
   decisión a `02_decisions/` (`tipo: decision`, con alternativas descartadas), duda a
   `03_open_questions/` (`tipo: pregunta`, `estado: abierta`). Un link web va a su ficha
   en `04_sources/web/` con `templates/web-source.md`, y el PDF de un paper a su ficha en
   `04_sources/literature/` con `templates/literature-note.md` (lo lees tú). Si el índice
   muestra una nota sobre la misma idea, amplíala en su sección `## Actualizaciones`, con
   fecha.
5. Cada nota nueva lleva `origen: "<nombre-del-original> (inbox, AAAA-MM-DD)"`: con ese
   nombre y esa fecha, el original se encuentra en `.brainme/inbox-procesado/AAAA-MM-DD/`.
6. Vacía el inbox:
   - Originales de texto (apuntes, notas de reunión): a
     `.brainme/inbox-procesado/AAAA-MM-DD/` (`mkdir -p` y `mv`), un respaldo fuera de
     Obsidian y del mapa.
   - Archivos con valor propio, a su carpeta: PDF de un paper a `04_sources/literature/`
     junto a su ficha, entregable a `05_exports/`, imagen de apoyo junto a la nota
     que la incrusta.
7. Sincroniza.
8. Informa con una tabla corta (nota, carpeta, enlazada a). Aparte: los originales que no
   dejaron notas y por qué, lo ambiguo, y lo que contradiga una decisión vigente, creado
   como pregunta abierta.

### 3. Guardar lo que surgió ("guarda esto", "anota que...")

1. Decide el tipo: conocimiento, decisión o pregunta.
2. Revisa el índice de nombres: si ya hay una nota de esa idea, actualízala.
3. Crea la nota atómica; varias ideas son varias notas enlazadas entre sí.
4. Sincroniza.
5. Confirma en una línea: "Guardé [[nombre]] en 01_knowledge/, enlazada a [[x]] y [[y]]."

### 4. Preguntas abiertas ("qué preguntas siguen abiertas")

Son compartidas: el usuario también las crea y edita en Obsidian. Una por archivo,
`pregunta-<tema>.md`, con `tipo: pregunta`, contexto, por qué importa, qué la
resolvería y `prioridad`.

- **Listar:** `BRAIN estado` las da ordenadas por prioridad.
- **Graduar** cuando una queda respondida:
  1. Nota nueva en `01_knowledge/` (o `02_decisions/` si se resolvió una decisión) con
     `responde_a: "[[pregunta-x]]"`.
  2. En la pregunta: `estado: resuelta`, `resuelta_en: "[[nota-respuesta]]"` y
     `fecha_resolucion`.
  3. Archívala en `03_open_questions/archive/`.
- `estado` avisa de las que el usuario marcó como resueltas sin graduar: ofrécete a
  graduarlas.
- Sincroniza tras cada cambio.

### 5. Entregables e informes ("haz un informe de...", "dónde guardo este entregable")

Sigue `references/entregables.md`: la revisión de las notas que cita, dónde vive cada
tipo, fichas, presentaciones a PDF y versiones.

### 6. Notas añadidas a mano ("añadí notas nuevas")

Sincroniza y corre `BRAIN estado`. Si trajo PDFs, imágenes u Office, ofrece leerlos
con `brainme:lector` para que cada uno quede con su ficha. Si dejó archivos fuera de la
estructura, ofrece ordenarlos (flujo 7).

### 7. Ordenar la carpeta ("ordena esta carpeta")

Sigue `references/ordenar.md` completo: inventario, plan con un solo OK, respaldo,
mover sin romper enlaces, verificar y, si hace falta, deshacer.

### 8. Handoff ("ayúdame con un handoff", `/brainme:handoff`)

Sigue `references/handoff.md`: guarda en notas lo que surgió, escribe el handoff en la
bitácora y abre una sesión nueva que retoma desde ahí.

### 9. Revisar el jardín ("revisa el jardín", "consolida la memoria", "qué notas están sueltas")

El sueño de brainme: contra los originales y la bitácora, verifica las notas, fusiona
duplicados, archiva lo obsoleto, crea páginas de tema donde ayudan, pone al día el tablero
y cierra los huecos del mapa. Se hace a pedido o cuando `BRAIN estado` dice "toca revisar
el jardín". Sigue `references/jardin.md`.

### 10. Espacio ("configura un espacio", "nuevo proyecto", "cómo van los proyectos", "lleva esto al contexto general", "cierra el proyecto")

Sigue la parte que corresponda de `references/espacio.md`.

## Convenciones de las notas

- **Nombres:** minúsculas, con guiones, sin tildes ni espacios, descriptivos y únicos
  en todo el vault (los wikilinks se resuelven por nombre): `segmento-pymes-valora-simplicidad`,
  `decision-modelo-de-precio`, `pregunta-canal-de-venta`, `apellido-anio-palabra-clave`
  (paper), `sitio-tema` (web), `informe-...-v1` (entregable). En un proyecto de un
  espacio, cada nota empieza con el prefijo de su ficha (`acme-decision-modelo-de-precio`).
- **Nombres permanentes:** una vez enlazada, la nota conserva su nombre. Para
  renombrar, que el usuario lo haga desde Obsidian (actualiza los enlaces) o
  actualiza tú cada `[[...]]` que la mencione.
- **Enlaces entre notas:** wikilinks por nombre y sin carpeta,
  `[[decision-modelo-de-precio]]`, en el cuerpo o en el frontmatter, con alias
  (`[[nota|texto]]`) o sección (`[[nota#Sección]]`). Así mover una nota no rompe nada y
  el mapa los lee siempre. Los links markdown quedan para URLs externas.
- **Resumen y autor:** `resumen` son una o dos frases con la idea; se escribe al crear la
  nota y se actualiza cuando cambia. `autor` es el de `BRAIN autor`; si no tiene nombre,
  pregúntaselo al usuario una vez. Una nota larga a propósito lleva `largo: si`.
- **Frontmatter:** completa lo que aplica y quita el resto, con los placeholders `<...>`
  y comentarios de la plantilla. Fechas `AAAA-MM-DD`. Valores de `tipo`:
  `conocimiento`, `decision`, `pregunta`, `tema`, `literatura`, `fuente-web`, `entregable`.
- **Tags:** pocos, en minúsculas, reutilizando los que ya existen.
- **Cómo se sabe:** cada nota de conocimiento lleva `certeza` y `como_se_sabe`.
  `confirmado` es lo que comprobó una fuente, un dato o alguien que puede saberlo;
  `supuesto`, lo deducido o dicho sin respaldo. `como_se_sabe` dice quién o qué lo
  confirmó y cuándo. Cuando un supuesto se confirma o se cae, cambia la certeza y anótalo
  en `## Actualizaciones`. Las decisiones lo dicen con `estado` y `decidido_por`, y las
  fuentes con `fiabilidad`.
- **Datos críticos:** requisitos, términos de un contrato o una propuesta, plazos, montos
  y compromisos de los que depende un entregable van en una nota por entidad (un
  contrato, un requisito, un acuerdo), citados palabra por palabra en `## Texto exacto`
  con su original y página. Resumidos o juntados en una tabla compartida, se pierden.
- **Lo que escribió el usuario** se amplía en `## Actualizaciones`, con fecha y autor;
  para cambiar su texto, pregúntale.
