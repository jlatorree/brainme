# Procesar el inbox

**Terminado cuando:** `00_inbox/` queda vacío, cada original quedó archivado o en su
carpeta, y cada uno dejó lo que no se puede volver a leer en él en notas nuevas con su
`origen`, en `## Actualizaciones` de notas existentes o, si no aportó nada nuevo, en el
informe con su porqué.

1. `brainme inbox`: lo que hay, y el `origen` que llevará lo que salga de cada archivo. Vacío:
   dilo y termina.
2. `brainme nombres`, una vez para todo el lote. Cada documento largo va a
   `brainme:lector`. **Lote grande:** si trae más de 3 elementos, reparte los demás en
   tandas a subagentes generales. Cada uno empieza por `brainme guia inbox convenciones` y
   hace solo los pasos 3 a 5 con los archivos y orígenes que le das. Cada nota tiene un solo
   escritor: las tandas crean notas nuevas y devuelven una tabla con ellas y con lo que
   agregarían a las que ya existen. Eso, y los pasos 6 a 8, los hace la sesión principal.
3. Lee cada elemento y quédate con lo que no se puede volver a leer en él, y con qué
   cambia para el proyecto. El resto se queda en el original, que sigue a mano para buscar
   o verificar.
4. Cada idea va a su nota atómica: conocimiento a `01_knowledge/` (`tipo: conocimiento`),
   decisión a `02_decisions/` (`tipo: decision`, con alternativas descartadas), duda a
   `03_open_questions/` (`tipo: pregunta`, `estado: abierta`). Con las plantillas de `brainme guia
   fuentes`, un link web va a su ficha en `04_sources/web/`, y el PDF de un paper a la suya en
   `04_sources/literature/`. Si una nota ya habla de esa idea (lo dice el índice o, si el
   nombre no alcanza, `brainme buscar`), amplíala (Convenciones, "Ampliar y corregir").
5. **Origen**, tal como lo dio `brainme inbox`: así el jardín encuentra el original de cada cosa.
   La fecha de `origen` es la de hoy, no la del original: si él no dice cuándo fue, no se anota.
   En una nota nueva, en su campo `origen`; en una ampliación, al final de la línea:
   `- <hoy>: <qué cambió> · origen: <archivo.ext> (inbox, <hoy>)`.
6. Vacía el inbox:
   - Originales de texto (apuntes, notas de reunión): `brainme procesado <archivo> ...` los
     pasa a `.brainme/inbox-procesado/<hoy>/`, fuera de Obsidian y del mapa.
   - Archivos con valor propio: `brainme procesado <archivo> --a <carpeta>`. El PDF de un
     paper, a `04_sources/literature/`, junto a su ficha; un entregable, a `05_exports/`; los
     demás (un contrato, un brief, un Excel, una imagen), junto a la nota que los cita,
     enlazados desde ella con el nombre que dio `brainme inbox` (`[[contrato.pdf]]`).
7. Comprueba.
8. Informa con una tabla corta (nota, carpeta, enlazada a). Aparte: los originales que no
   dejaron notas y por qué, lo ambiguo, y lo que contradiga una decisión vigente, creado
   como pregunta abierta.
