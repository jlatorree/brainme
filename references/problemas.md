# Graphify: problemas y lo que su --help no dice

Referencia: repo oficial <https://github.com/Graphify-Labs/graphify> (paquete PyPI
`graphifyy`, con doble y; el comando es `graphify`). Ante una duda sobre un flag, la
fuente de verdad es `graphify --help` o ese README. Brainme se validó con
graphify 0.9.65.

| Síntoma | Qué hacer |
|---|---|
| `graphify: command not found` | Si existe `~/.local/bin/graphify`, falta agregarlo a la ruta: `uv tool update-shell` y usa `~/.local/bin/graphify` en esta sesión. Si no existe, instálalo como indica `references/configurar.md` (con el OK del usuario). |
| Los PDFs, `.xlsx` o `.docx` no aparecen | Faltan extras (sin ellos quedan fuera sin aviso): `uv tool install --reinstall "graphifyy[pdf,office]"` y `graphify install`. |
| Una nota nueva no sale en las consultas | Sincroniza y repite. Si el vault está en iCloud, puede que el archivo no esté descargado: que el usuario lo abra en Obsidian. |
| Tras reorganizar carpetas, el grafo tiene menos notas | `graphify update . --force`. |
| `graphify path` dice que no hay camino | Repite con `--undirected`. |
| Aviso "skill is from graphify X, package is Y" | `uv tool upgrade graphifyy` y luego `graphify install`. |
| Aparecen avisos "MANDATORY" en cada búsqueda o lectura de nota | Alguien corrió `graphify claude install`: `BRAIN migrar --aplicar` quita los avisos y la sección `## graphify` para código. |
| El grafo se ve incoherente | Reconstrucción completa: invoca el skill `graphify` con `.` (usa la IA de la sesión). |

Datos que conviene saber:

- `graphify update .` no lee el contenido de notas, PDFs ni imágenes: solo estructura.
  El contenido lo lee la lectura profunda.
- `graphify extract . --force` exige una clave de API y falla sin ella en un vault de
  notas. En Claude Code, el equivalente es invocar el skill `graphify` con `.`.
- `graphify add <url>` sin `--dir` guarda en `./raw`, fuera de la estructura.
- Los links markdown a archivos con espacios en el nombre no crean conexiones; los
  wikilinks sí (`BRAIN a-wikilinks` los convierte).
- `graphify save-result` guarda en `graphify-out/memory/`, y esas memorias sí entran
  al grafo aunque `graphify-out/` esté ignorado (así aprende de las consultas).
