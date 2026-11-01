# Handoff: seguir en una sesión nueva

Se sigue cuando el usuario dice "ayúdame con un handoff", "haz un handoff" o usa
`/brainme:handoff`, normalmente porque el contexto de la sesión se está llenando. Una
sesión nueva arranca con ~25.000 tokens de contexto en vez de arrastrar cientos de miles.

**Terminado cuando:** lo que surgió en la sesión está en notas, el handoff está en
`bitacora.md` y la sesión nueva quedó abierta (o el usuario tiene la frase para abrirla).

1. **Guarda lo pendiente.** Revisa la conversación: lo que se decidió, se aprendió o
   quedó en duda y todavía no está en una nota va directo a su nota atómica (flujo 3).
   Lo que no está claro se guarda como pregunta abierta.
2. **Escribe el handoff** en `.brainme/handoff.md`, en menos de 300 palabras:

   ```markdown
   **Objetivo:** qué se buscaba, en una o dos frases.

   **Dónde quedamos:**
   - lo hecho, en 3 a 6 viñetas, con wikilinks a las notas

   **Siguiente paso:** uno solo, concreto.

   **Pendiente:** decisiones por tomar y preguntas abiertas, con wikilinks.

   **Leer primero:** hasta 5 notas o archivos, con su ruta.

   **Cuidado con:** lo que costó o se intentó sin éxito (solo si aplica).
   ```
3. **Guárdalo en la bitácora:** `BRAIN bitacora --handoff .brainme/handoff.md`. Anota la
   fecha y hora que imprime.
4. **Abre la sesión nueva.** El primer mensaje de la sesión nueva es:
   `brainme: retoma el handoff del <fecha y hora>`.
   - Si tienes una herramienta para iniciar una sesión nueva de Claude Code (la app de
     escritorio la tiene), créala en esta misma carpeta, con contexto nuevo y ese primer
     mensaje, y muéstrasela al usuario para que entre con un clic.
   - Si no la tienes, dale la frase y dile: "abre una sesión nueva en esta carpeta y
     pega esto".
5. **Confirma en dos líneas:** qué guardaste en notas y cómo seguir.

## Retomar ("retoma el handoff")

1. `BRAIN bitacora --handoff-ultimo` muestra el último handoff.
2. Lee solo los archivos de **Leer primero**.
3. Resume en hasta 6 líneas dónde quedamos y cuál es el siguiente paso, y sigue desde
   ahí.
