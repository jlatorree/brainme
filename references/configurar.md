# Configurar un proyecto

**Terminado cuando:** la carpeta tiene la estructura, `CLAUDE.md` con la sección
`## brainme` y `tablero.md`; `brainme autor` tiene nombre; `CLAUDE.md` dice de qué trata el
proyecto y el tablero qué se busca ahora, con palabras del usuario.

1. **Carpeta:** el proyecto es la carpeta donde se abrió Claude Code. Si es la carpeta
   personal, el Escritorio o Documentos, pregunta en qué carpeta vive antes de crear nada.
2. **Python 3:** `xcode-select -p`. Si falla, corre `xcode-select --install` y pide al
   usuario que acepte el aviso de macOS y te avise cuando termine.
3. **¿Varios proyectos?** Si el usuario quiere llevar varios proyectos con un contexto
   general, sigue "Configurar" en `references/multiproyecto.md`. Si la carpeta está dentro
   de una carpeta multiproyecto, es un proyecto nuevo: sigue ahí "Nuevo proyecto".
4. **Pregunta en un solo mensaje** de qué trata el proyecto (una o dos frases), qué se
   busca ahora y, si `brainme autor` dice "no definido", cómo quiere firmar.
5. `brainme crear --trata "<de qué trata>"` y `brainme autor "<nombre>"`. En el tablero,
   el objetivo actual con sus palabras.
6. **Lo que ya había** en la carpeta se queda donde está hasta que el usuario decida. Si hay
   trabajo previo (notas, subcarpetas, documentos), ofrece ordenarlo con
   `references/ordenar.md`: queda en la estructura sin romper sus enlaces, con respaldo y
   deshacer. Si prefiere algo más chico, pasa al inbox lo que elija.
7. **Mensaje final**, en pocas líneas, por ejemplo:

   ```
   Listo, este proyecto ya funciona con brainme:
   - Creé las carpetas: inbox, conocimiento, decisiones, preguntas, fuentes y entregables.
   - CLAUDE.md hace que cada sesión nueva en esta carpeta use brainme.
   - tablero.md lleva el objetivo, el plan y los próximos pasos.
   Para empezar, deja apuntes o notas de reunión en 00_inbox y dime "procesa el inbox".
   ```
