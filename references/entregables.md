# Entregables e informes

Los entregables ricos (diagramas, presentaciones, exceles, HTML) los generan otros
skills; brainme decide dónde vive cada uno y lo conecta al grafo.

**Terminado cuando:** el archivo está en su carpeta, tiene ficha si no es `.md`, la
ficha enlaza lo que lo sustenta, y el grafo está sincronizado.

**"Haz un informe de...":** reúne el contexto con consultas. Si basta un informe en
markdown, escríbelo en `05_exports/reports/` citando notas con wikilinks (y
fuentes con doble cita). Si piden un formato rico (HTML, diagrama, presentación,
excel), usa el skill que corresponda y guarda aquí el resultado.

| Entregable | Carpeta | ¿Graphify lo lee? | Qué haces |
|---|---|---|---|
| Informe `.md` / `.html` | `05_exports/reports/` | Sí | Frontmatter y wikilinks a sus fuentes (en `.html`, ficha) |
| Diagrama `.png` `.jpg` `.svg` | `05_exports/diagrams/` | Sí, como imagen (lectura profunda) | Ficha |
| Excel / Word `.xlsx` `.docx` | `05_exports/data/` | Sí, con el extra `office` (lectura profunda) | Ficha |
| Presentación `.key` `.pptx` | `05_exports/presentations/` | Su PDF sí (extra `pdf`); el binario no | Ficha + PDF exportado |

- **Ficha:** con `templates/deliverable-card.md`, junto al archivo y con el mismo
  nombre en `.md` (`diagrama-journey-v2.png` tiene la ficha `diagrama-journey-v2.md`).
  Enlaza con wikilinks las decisiones, notas y fuentes que lo sustentan: así el output
  queda conectado a su razonamiento, y el grafo lo encuentra sin lectura profunda.
- **Presentaciones:** si el skill que la generó no dejó un PDF, expórtalo con Keynote
  (sirve para `.key` y `.pptx`; la primera vez macOS pide permiso para controlar
  Keynote):

  ```bash
  osascript <<'EOF'
  set origen to POSIX file "/ruta/absoluta/presentacion-v1.key"
  set destino to POSIX file "/ruta/absoluta/presentacion-v1.pdf"
  tell application "Keynote"
    set doc to open origen
    export doc to destino as PDF
    close doc saving no
  end tell
  EOF
  ```

  Si falla, pide al usuario que lo exporte a mano (Keynote: Archivo > Exportar a >
  PDF) en la misma carpeta.
- **Versiones:** cada versión entregada se conserva. Una versión nueva es un archivo
  nuevo (`-v2`) y una fila más en el historial de la ficha. La que se envía es la
  misma de `05_exports/`: no hay copias aparte; en la ficha, `estado: final`. Al crear
  la versión nueva, la anterior y su ficha pasan a `_versiones/` dentro de la misma
  carpeta (`BRAIN versiones --plan .brainme/plan-versiones.json` y `BRAIN mover --plan
  .brainme/plan-versiones.json`): así las búsquedas y el grafo ven solo la vigente.
- **Generadores:** los scripts o pipelines que producen un entregable van a `_taller/`
  en la raíz del proyecto, con un nombre que diga qué generan. Quedan fuera de las
  búsquedas y del grafo.
- Al terminar: sincroniza. Si hay imágenes, PDFs u Office nuevos y el usuario quiere
  que el grafo lea su contenido, lectura profunda.
