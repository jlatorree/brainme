# Configurar un proyecto

Se sigue cuando la carpeta actual no tiene `CLAUDE.md` con la sección `## brainme`.
Todo lo haces tú; pides permiso solo donde se indica.

**Terminado cuando:** existen las carpetas de la estructura, `tablero.md` y `CLAUDE.md`
con la sección `## brainme`; `brainme autor` tiene nombre; `brainme inventario` marca 0 archivos
por ordenar (o solo los que el usuario decidió dejar); con las palabras del usuario,
`CLAUDE.md` dice de qué trata el proyecto, y el tablero, qué se busca ahora; y el usuario
recibió el mensaje final.

1. **Carpeta.** El proyecto es la carpeta donde se abrió Claude Code (`pwd`). Si es la
   carpeta personal (`~`), el Escritorio, Documentos a secas o una carpeta del
   sistema, pregunta en qué carpeta vive el proyecto antes de crear nada.
2. **Python 3.** Corre `xcode-select -p`. Si falla, faltan las herramientas de línea de
   comandos de Apple (traen Python 3): corre `xcode-select --install`, pide al usuario
   que acepte el aviso de macOS y que te avise cuando termine.
3. **¿Multiproyecto?** `brainme multiproyecto`. Si dice "armada a mano", o el usuario quiere
   varios proyectos con un contexto general, sigue `brainme guia multiproyecto`. Si la
   carpeta está dentro de una multiproyecto, es uno de sus proyectos: sigue ahí "Nuevo
   proyecto".
4. **Carpetas, `CLAUDE.md` y tablero:** `brainme crear`. Crea las carpetas de la
   estructura, `tablero.md` y `CLAUDE.md` desde `templates/CLAUDE.md`; si ya existía, le
   agrega la sección `## brainme` (que importa el tablero) y conserva todo lo demás.
5. **Autor:** `brainme autor`. Si dice "no definido", pregúntale al usuario cómo quiere
   firmar (por ejemplo, "Jonathan L.") y corre `brainme autor "Nombre"`. Se guarda en
   este computador, no en la carpeta: en una carpeta compartida, cada persona firma con
   su nombre.
6. **Avance previo:** `brainme inventario`. Si hay archivos por ordenar, sigue
   `brainme guia ordenar` ahora.
7. **Pregunta en un solo mensaje** de qué trata el proyecto (una o dos frases, para
   `CLAUDE.md`) y qué se busca ahora (para el objetivo del tablero), y escríbelo.
8. **Mensaje final**, en pocas líneas, por ejemplo:

   ```
   Listo, este proyecto ya funciona con brainme:
   - Creé las carpetas: inbox, conocimiento, decisiones, preguntas, fuentes y exports.
   - Creé CLAUDE.md: cada sesión nueva en esta carpeta arrancará usando brainme.
   - Creé tablero.md: el objetivo, el plan y los próximos pasos, a mano en cada sesión.
   - Cada nota quedará enlazada con otras; yo llevo el mapa de esas conexiones.
   Para empezar, deja apuntes o notas de reunión en 00_inbox y dime "procesa el inbox".
   ```
