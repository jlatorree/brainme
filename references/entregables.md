# Entregables e informes

Los entregables ricos (diagramas, presentaciones, exceles, HTML) los generan otros
skills; brainme decide dónde vive cada uno y lo conecta al mapa.

**Terminado cuando:** el entregable está en su carpeta, con la versión vigente a la
vista y las anteriores en `versiones/`; tiene ficha si no es `.md`, la ficha enlaza lo
que lo sustenta, y el proyecto está sincronizado.

Cada entregable tiene su carpeta, con su nombre sin versión:

```
05_exports/<tipo>/<entregable>/
  <entregable>-v3.html      la versión vigente, con su PDF o su versión protegida si los hay
  <entregable>.md           la ficha (si el entregable no es .md)
  versiones/                las versiones anteriores, fuera de las búsquedas y del mapa
```

La carpeta del tipo (`reports/`, `presentations/`...) se crea con su primer entregable
(`mkdir -p`).

**"Haz un informe de...":** reúne el contexto con consultas. Si basta un informe en
markdown, escríbelo en `05_exports/reports/<informe>/<informe>-v1.md` citando notas con
wikilinks (y fuentes con doble cita). Si piden un formato rico (HTML, diagrama,
presentación, excel), usa el skill que corresponda y guarda aquí el resultado.

| Entregable | Tipo | Lectura profunda (con Graphify) | Qué haces |
|---|---|---|---|
| Informe `.md` / `.html` | `reports/` | No hace falta: es nota | Frontmatter y wikilinks a sus fuentes (en `.html`, ficha) |
| Diagrama `.png` `.jpg` `.svg` | `diagrams/` | Como imagen | Ficha |
| Excel / Word `.xlsx` `.docx` | `data/` | Con el extra `office` | Ficha |
| Presentación `.key` `.pptx` | `presentations/` | Su PDF sí (extra `pdf`); el binario no | Ficha + PDF exportado |

- **Ficha:** con `templates/deliverable-card.md`, una por entregable, en su carpeta y
  con su nombre sin versión (`diagrama-journey/diagrama-journey.md`). Enlaza con
  wikilinks las decisiones, notas y fuentes que lo sustentan: así el output queda
  conectado a su razonamiento, y el mapa lo encuentra sin lectura profunda.
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
- **Versiones:** cada versión entregada se conserva y lleva su número en el nombre
  (`-v2`, `-v2-protegido`, `-v2.pdf`), para saber cuál se envió. Una versión nueva es un
  archivo nuevo en la carpeta del entregable; en la ficha, actualiza `archivo` y
  `version` y agrega una fila al historial. La que se envía es la misma de
  `05_exports/`: no hay copias aparte; en la ficha, `estado: final`.
- **Ordenar:** después de guardar una versión nueva, `BRAIN versiones --plan
  .brainme/plan-versiones.json` y `BRAIN mover --plan .brainme/plan-versiones.json`.
  Deja a la vista los archivos del número más alto y pasa los anteriores a
  `versiones/`. Agrupa por el nombre sin versión, así que también ordena entregables
  sueltos y los `_versiones/` de brainme 3.0. Lo que `versiones` lista aparte se
  decide con el usuario:
  - **Revisa con el usuario:** archivos sin número ni hermanos, como un PDF con nombre
    libre. Pregúntale si van con otro entregable y, si es así, cambia su destino en el
    plan.
  - **Carpetas propias:** subcarpetas que el usuario armó dentro de un entregable. Se
    quedan; si el usuario las usaba para versiones viejas, `--archivar <nombre>` pasa
    su contenido a `versiones/`.
- **Generadores:** los scripts o pipelines que producen un entregable van a `_taller/`
  en la raíz del proyecto, con un nombre que diga qué generan. Quedan fuera de las
  búsquedas y del mapa.
- Al terminar: sincroniza. Si hay imágenes, PDFs u Office nuevos, el proyecto usa
  Graphify y el usuario quiere que se lea su contenido, lectura profunda.
