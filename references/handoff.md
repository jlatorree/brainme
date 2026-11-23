# Handoff: seguir en una sesión nueva

Se sigue cuando el usuario pide un handoff o usa `/brainme:handoff`, normalmente porque
el contexto de la sesión se está llenando: una sesión nueva arranca liviana.

**Terminado cuando:** lo que surgió en la sesión está en notas, el tablero está al día, el
handoff está en la bitácora y la sesión nueva quedó abierta (o el usuario tiene la frase
para abrirla).

1. **Guarda lo pendiente:** lo que se decidió, se supo o quedó en duda en esta
   conversación y aún no tiene nota va a su nota (flujo Guardar); lo que no está claro,
   como pregunta abierta.
2. **Pon al día el tablero:** plan y próximos pasos como quedan.
3. **Escribe el handoff** en `.brainme/handoff.md`, en menos de 300 palabras:

   ```markdown
   **Objetivo:** qué buscaba esta sesión, en una o dos frases.
   **Dónde quedamos:** lo hecho, en 3 a 6 viñetas, con wikilinks a las notas.
   **Siguiente paso:** uno solo, concreto.
   **Pendiente:** decisiones por tomar y preguntas abiertas, con wikilinks.
   **Leer primero:** hasta 5 notas o archivos.
   **Cuidado con:** lo que costó o no funcionó en esta sesión, si hubo.
   ```
4. `brainme bitacora --handoff .brainme/handoff.md`. Anota la fecha y hora que imprime.
5. **Abre la sesión nueva** en esta carpeta, con el primer mensaje
   `brainme: retoma el handoff del <fecha y hora>`. Si tienes una herramienta para iniciar
   sesiones de Claude Code, úsala; si no, dale al usuario la frase para pegar en una sesión
   nueva.
6. Confirma en dos líneas qué guardaste y cómo seguir.

## Retomar ("retoma el handoff")

1. `brainme bitacora --handoff-ultimo`; el tablero ya está cargado.
2. `brainme leer` lo de **Leer primero**.
3. Resume en hasta 6 líneas dónde quedamos y cuál es el siguiente paso, y sigue desde ahí.
