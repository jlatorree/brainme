# Deep research de literatura

La sigue el ayudante `brainme:investigador` (Opus, esfuerzo xhigh). Si lanzas subagentes
para buscar o leer, pídeles el mismo modelo y esfuerzo.

La investigación y la lectura de papers las hace Claude Code con su deep research, como
siempre. Brainme le da el encargo y después almacena y procesa el resultado: fichas,
informe con doble cita y conexiones con el proyecto.

**Regla de oro:** cada afirmación del informe lleva **doble cita**, y cada referencia es
una fuente que la investigación abrió de verdad. Si no hay evidencia, se dice ("no
encontré evidencia sólida sobre...").

**Terminado cuando:** cada fuente usada tiene su ficha, cada DOI respondió 302, cada
afirmación del informe tiene doble cita, el informe está en `05_exports/reports/`
y el proyecto está sincronizado.

## 1. Encargo

1. Aclara la pregunta de investigación y a qué pregunta o decisión del proyecto sirve.
2. Revisa qué ya existe con `BRAIN nombres` (fichas en `04_sources/`) y, si hace falta,
   una consulta. Lo ya fichado se reutiliza.
3. Lanza la investigación con el deep research de Claude Code: el skill de deep research
   si está disponible (por ejemplo `deep-research`); si no, tus herramientas de búsqueda
   y lectura web, como lo harías siempre. El encargo lleva:
   - La pregunta, el contexto del proyecto en dos frases y lo que ya está fichado.
   - Criterios de fuentes: peer-reviewed o venue reputado (preprints marcados como
     tales), fuente primaria, sin journals predatorios ni trabajos retractados; lo más
     citado y lo más reciente (~5 años), más los clásicos clave marcados como
     fundacionales; evidencia en contra si existe.
   - Cada afirmación con el link a su fuente.
   - Por cada paper usado: cita completa, DOI o URL, año, venue, citas (y dónde las
     vio), tipo de trabajo, método y muestra, 3 hallazgos clave, límites, y si lo leyó
     completo o solo el abstract.

## 2. Almacenar y procesar

1. **Verifica cada DOI** (302 = válido, 404 = no existe):
   `curl -s -o /dev/null -w "%{http_code}" https://doi.org/<DOI>`. Lo que no verifica
   se corrige o sale del informe.
2. **Fichas:** una por paper en `04_sources/literature/apellido-anio-palabra-clave.md`
   con `templates/literature-note.md`, llenada con lo que devolvió la investigación (sin
   volver a leer el paper). Un dato que la investigación no trajo queda como
   "no reportado". Fuentes web no académicas: `04_sources/web/sitio-tema.md` con
   `templates/web-source.md`. Si la ficha ya existía, se amplía.
3. **PDFs:** si el usuario tiene el PDF de un paper, va junto a su ficha con el mismo
   nombre base. Queda a mano para él y fuera del mapa, donde lo representa su ficha.
4. **Informe** en `05_exports/reports/informe-<tema>-<AAAA-MM-DD>.md`: pregunta,
   resumen ejecutivo, hallazgos, evidencia en contra o debates, implicaciones para el
   proyecto (con wikilinks a decisiones y preguntas), límites de la revisión y lista de
   fuentes. Cada afirmación con doble cita:

   ```
   Las pymes abandonan los procesos de alta largos ([Pérez, 2023](https://doi.org/10.xxxx/yyyy); [[perez-2023-onboarding-pymes]]).
   ```
5. **Conecta con el proyecto:** si la investigación responde una pregunta abierta,
   gradúala (flujo 4); si contradice una decisión vigente, créalo como pregunta abierta
   y avísale.
6. **Sincroniza.** Las fichas y el informe son notas: entran al mapa sin lectura
   profunda.
7. **Entrega:** resumen en el chat (máximo 5 viñetas), ruta del informe y lista de
   fichas creadas.
