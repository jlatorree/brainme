# Ordenar una carpeta con avance previo

Para cuando alguien activa brainme en una carpeta que ya tiene trabajo: notas sueltas,
subcarpetas propias (`Reuniones/`, `Cliente A/`, `Ideas/`...), PDFs, imágenes, Excel o canvas.
Todo queda en la estructura de brainme, sin perder nada y con cada enlace de Obsidian
funcionando.

**Terminado cuando:** `brainme ordenar inventario` marca 0 archivos por ordenar (salvo los que
el usuario decidió dejar), la salida de `mover` dice "Enlaces rotos: X antes, Y después" con
Y igual o menor que X, no quedan nombres repetidos y `brainme comprueba --todo` no lista nada
de lo que se movió a `01_knowledge/` a `05_exports/`.

Cada archivo se mueve con `brainme ordenar mover`, que corrige lo que apunta a él: los
wikilinks con ruta (`[[carpeta/nota]]`), los links relativos (`[texto](../nota.md)`) y los
canvas. Resuelve cada enlace como Obsidian, deja por nombre los que pueden ir por nombre y
deja intactos los bloques de código. A una nota solo le agrega el frontmatter que le falta.

1. **Inventario:** `brainme ordenar inventario --tabla`. Imprime un resumen y una línea por
   archivo por ordenar: ruta, tipo, título, palabras, cuántas notas lo usan y una vista
   previa. Clasifica con eso; abre una nota completa (`brainme leer`) solo si la vista previa
   no alcanza. Si avisa de archivos no descargados de iCloud, pide al usuario que los abra
   antes de seguir.
2. **Clasifica** cada archivo:

   | Qué es | Destino |
   |---|---|
   | Nota clara de un solo tipo (una idea, una decisión o una pregunta) | `01_knowledge/`, `02_decisions/` o `03_open_questions/`, con `tipo` (y `estado` si aplica) |
   | Notas de reunión, notas largas con varias ideas, borradores, apuntes | `00_inbox/`: después se procesan |
   | Informe, presentación u otro entregable que hizo el equipo, también ya enviado | `05_exports/` |
   | Canvas de Obsidian (`.canvas`) | `05_exports/` |
   | Adjunto que una nota incrusta o enlaza ("usado por" mayor que 0) | La misma carpeta que la nota que lo usa |
   | Documento que mandó otro (contrato, brief, Excel, PDF) que ninguna nota usa | `00_inbox/`: al procesarlo, va a `04_sources/` si tiene valor propio |
   | Algo que no sabes qué es (código, zips, formatos raros) | Se queda donde está; pregunta |

   - Los archivos conservan su nombre. Si dos se llaman igual (el inventario los lista), uno
     recibe un sufijo que los distinga (`ideas-cliente-a.md`).
   - La carpeta de origen se conserva como tag (`Cliente A/` agrega `cliente-a`), para no
     perder la agrupación que tenía el usuario.
   - `docs/`, y `CLAUDE.md`, `README.md`, `tablero.md` y `bitacora.md` de la raíz, se quedan.
3. **Plan con un solo OK:** muestra una tabla por destino (cuántos archivos y ejemplos), los
   dudosos y los renombres por nombre repetido. Es la única confirmación que pides para mover.
4. **Respaldo:** `brainme ordenar respaldo` (un zip en `.brainme/respaldos/`).
5. **Mover:** escribe el plan en `.brainme/plan-orden.json` y corre
   `brainme ordenar mover --plan .brainme/plan-orden.json`. Un `a` que termina en `/`
   conserva el nombre del archivo:

   ```json
   {
     "movimientos": [
       {"de": "Reuniones/2024-05-02 Kickoff.md", "a": "00_inbox/", "tags": ["reuniones"]},
       {"de": "Ideas/precio por uso.md", "a": "01_knowledge/", "frontmatter": {"tipo": "conocimiento"}, "tags": ["ideas"]},
       {"de": "Cliente A/ideas.md", "a": "00_inbox/ideas-cliente-a.md", "tags": ["cliente-a"]},
       {"de": "diagrama journey.png", "a": "00_inbox/"}
     ]
   }
   ```

   Si el plan tiene un error (origen que no existe, destino ocupado, dos archivos al mismo
   destino), `mover` no mueve nada y dice qué corregir. Al terminar borra las carpetas que
   quedaron vacías y deja un registro en `.brainme/registros/`.
6. **Wikilinks:** `brainme ordenar wikilinks` convierte los links markdown internos entre
   notas en wikilinks. En Obsidian funcionan igual, y un wikilink no se rompe cuando la nota
   cambia de carpeta.
7. **Completa las notas que quedaron en 01 a 05:** `brainme comprueba --todo` dice cuáles no
   tienen resumen, enlace a otra nota o los campos de su tipo.
   - **Resúmenes:** hasta 10, escríbelos tú con lo que dice cada nota (`brainme leer`). Más
     de 10: `brainme ordenar resumenes` los reparte en lotes, y lanzas un ayudante
     `brainme:resumidor` por lote, todos a la vez (sin el plugin, un subagente general con
     `agents/resumidor.md`). Después lee 5 resúmenes al azar contra su nota; si alguno no
     dice la idea, reescribe los de su lote.
   - **Campos:** si una tenía otro `tipo` (`idea`, `nota`), corrígelo. `autor`, solo si
     consta quién la escribió. Lo deducido va con `certeza: supuesto`.
8. **Cuéntale en simple:** cuántos archivos ordenó y dónde, cuántos enlaces corrigió, qué
   quedó en `00_inbox/` para procesar y qué dejó sin tocar. Ofrece procesar el inbox, por
   tandas si son muchos.
9. **Deshacer:** si algo no le gusta, `brainme ordenar deshacer` devuelve cada archivo a su
   lugar y vuelve a corregir los enlaces (el frontmatter agregado se conserva). Último
   recurso: el zip de `.brainme/respaldos/`.
