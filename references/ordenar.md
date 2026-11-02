# Ordenar una carpeta con avance previo

Para cuando la carpeta ya tiene trabajo: notas sueltas, subcarpetas propias
(`Reuniones/`, `Cliente A/`, `Ideas/`...), PDFs, imágenes, exceles o canvas. Todo
queda en su lugar, sin perder nada y con cada enlace de Obsidian funcionando.

**Terminado cuando:** `BRAIN inventario` marca 0 archivos por ordenar (salvo los que
el usuario decidió dejar), la salida de `mover` dice "Enlaces rotos: X antes, Y
después" con Y igual o menor que X, y no quedan nombres repetidos.

**Herramienta:** `BRAIN` (ver SKILL.md). Mover archivos a mano rompe los wikilinks
con ruta (`[[carpeta/nota]]`), los links relativos (`[texto](../nota.md)`) y los
canvas; `BRAIN mover` los corrige todos: re-resuelve cada enlace como Obsidian
(también si el vault está por encima del proyecto), deja por nombre los que pueden ir
por nombre, respeta los bloques de código y los saltos de línea. Lo que genera queda
en `.brainme/`, fuera del mapa.

1. **Inventario:** `BRAIN inventario --tabla`. Imprime un resumen y una línea compacta
   por archivo por ordenar: ruta, tipo, título, palabras, cuántas notas lo usan y una
   vista previa. Clasifica con eso; abre una nota completa solo si la vista previa no
   alcanza. Si avisa de archivos no descargados de iCloud, pide al usuario que los
   abra antes de seguir.
2. **Clasifica** cada archivo por ordenar:

   | Qué es | Destino |
   |---|---|
   | Nota clara de un solo tipo (una idea, una decisión o una pregunta) | `01_knowledge/`, `02_decisions/` o `03_open_questions/`, con `tipo` (y `estado` si aplica) |
   | Notas de reunión, notas largas con varias ideas, borradores, apuntes | `00_inbox/` (después se procesan con el flujo 2) |
   | Resumen de un paper o PDF académico | `04_sources/literature/` (a un PDF sin ficha, ofrécele crearla: la ficha es lo que entra al mapa) |
   | Recorte o ficha de una página web | `04_sources/web/` |
   | Informe, documento de trabajo o entregable (también versiones finales ya enviadas) | `05_exports/<reports, diagrams, data o presentations>/<entregable>/`, una carpeta por entregable con su nombre sin versión |
   | Canvas de Obsidian (`.canvas`) | `05_exports/diagrams/<canvas>/` |
   | Adjunto: imagen o PDF que una nota incrusta ("usado por" mayor que 0) | La misma carpeta que la nota que lo usa |
      | Algo que no sabes qué es (código, zips, formatos raros) | Se queda donde está; pregunta |

   Reglas:
   - Los archivos conservan su nombre. Excepción: dos archivos con el mismo nombre
     (el inventario los lista) reciben un sufijo que los distinga (`ideas-cliente-a.md`).
   - La carpeta de origen se conserva como tag (`Cliente A/` agrega `cliente-a`), para
     no perder la agrupación que tenía el usuario.
   - `docs/`, y el `CLAUDE.md` y `README.md` de la raíz, se quedan (salen como `se_queda`).
3. **Plan con un solo OK:** muestra una tabla por destino (cuántos archivos y
   ejemplos), la lista de dudosos y los renombres por nombre repetido. Es el único
   momento en que pides confirmación.
4. **Respaldo:** `BRAIN respaldo` (zip en `.brainme/respaldos/`).
5. **Mover:** escribe el plan en `.brainme/plan-orden.json` y corre
   `BRAIN mover --plan .brainme/plan-orden.json`. Un `a` que termina en `/` conserva
   el nombre del archivo:

   ```json
   {
     "frontmatter_comun": {"proyecto": "<nombre del proyecto>"},
     "movimientos": [
       {"de": "Reuniones/2024-05-02 Kickoff.md", "a": "00_inbox/", "tags": ["reuniones"]},
       {"de": "Ideas/precio por uso.md", "a": "01_knowledge/", "frontmatter": {"tipo": "conocimiento"}, "tags": ["ideas"]},
       {"de": "Cliente A/ideas.md", "a": "00_inbox/ideas-cliente-a.md", "tags": ["cliente-a"]},
       {"de": "diagrama journey.png", "a": "05_exports/diagrams/diagrama-journey/"}
     ]
   }
   ```

   El frontmatter solo agrega campos y tags que falten; lo que el usuario tenía se
   conserva intacto. Si el plan tiene un error (origen inexistente, destino ocupado,
   dos archivos al mismo destino), `mover` no mueve nada y dice qué corregir. Al
   terminar borra las carpetas que quedaron vacías y deja un registro en
   `.brainme/registros/`.
6. **Wikilinks:** `BRAIN a-wikilinks` convierte los links markdown internos entre notas
   en wikilinks. En Obsidian funcionan igual, y un wikilink no se rompe cuando
   la nota cambia de carpeta.
7. **Verifica** con la línea "Enlaces rotos" de `mover` (los rotos previos suelen ser
   notas que el usuario aún no creó; se dejan como están) y resuelve los nombres
   repetidos que reporte. `BRAIN verificar` repite el chequeo cuando quieras. Si
   llegaron varias versiones de un entregable, ordénalas como en
   `references/entregables.md` («Ordenar»).
8. **Sincroniza.** Si es la primera vez y hay PDFs, imágenes u Office, ofrece la
   lectura profunda (o Graphify, si el proyecto no lo usa) diciendo cuántos archivos son.
9. **Cuéntale en simple:** cuántos archivos ordenó y dónde, cuántos enlaces corrigió,
   qué quedó en `00_inbox/` para procesar y qué dejó sin tocar. Ofrece procesar el
   inbox (flujo 2), por tandas si son muchos.
10. **Deshacer:** si algo no le gusta, `BRAIN deshacer` devuelve cada archivo a su
    lugar y vuelve a corregir los enlaces (el frontmatter agregado se conserva).
    Último recurso: el zip de `.brainme/respaldos/`.
