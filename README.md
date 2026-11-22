# brainme

Un skill de Claude Code que convierte cada proyecto en un **segundo cerebro**: una
carpeta de notas markdown conectadas entre sí, que puedes abrir en Obsidian. Sirve para
dejar de acumular archivos sueltos y preguntarle a tu proyecto qué sabe, qué decidiste y
qué falta.

## La idea en 30 segundos

Cada proyecto tiene seis partes:

- **Inbox:** donde sueltas todo (apuntes, reuniones, PDFs). Se vacía al procesarse.
- **Conocimiento:** notas atómicas y conectadas, incluidas decisiones y preguntas abiertas.
- **Fuentes:** una ficha por paper o web, con su cita lista.
- **Exports:** tus entregables, cada uno con las notas y fuentes de las que nació.
- **Mapa:** las conexiones entre notas, que Claude consulta en vez de releerlo todo.
- **Guía** (Claude): corre cada comando y te cuenta en simple qué hizo.

> Sueltas algo o conversas → se vuelve notas conectadas → las preguntas se gradúan en
> conocimiento o decisiones → los entregables citan sus fuentes → el mapa se actualiza.

## La filosofía

Cada idea queda en su propia nota, enlazada a las que ya existen. Para responder,
Claude sigue esos enlaces en vez de releer documentos completos.

1. **Enlazar es construir:** cada nota se conecta; Claude responde buscando en ellas y siguiendo sus enlaces.
2. **Tú no programas:** brainme corre todo y te explica qué hizo.
3. **Toda afirmación con su fuente:** doble cita, el link real y la ficha en el mapa.
4. **Nada se pierde:** se mueve, no se borra; todo orden tiene respaldo y se deshace.
5. **Pocos tokens:** cada nota tiene un resumen, lo pesado lo hacen ayudantes con el
   modelo justo y, cuando la sesión se llena, un handoff sigue en una sesión nueva.
6. **Memoria que se cuida:** las notas guardan lo que no se puede volver a leer en los
   originales, dicen cómo se sabe cada cosa, y un tablero corto lleva lo vigente a cada
   sesión. Revisar el jardín las verifica contra los originales y las consolida.

## Cómo se usa

Abre Claude Code en la carpeta del proyecto, escribe **brainme** y habla normal:

| Dices | brainme |
| --- | --- |
| "qué sabemos de...", "qué decidimos sobre..." | responde con las notas, enlaza de dónde sale cada cosa y dice qué es supuesto |
| "ponme al día" | resume estado, decisiones, preguntas abiertas e inbox |
| "procesa el inbox" | convierte apuntes y reuniones en notas conectadas |
| "guarda esto" | guarda lo que surgió como nota conectada |
| "qué preguntas siguen abiertas" | las lista por prioridad y gradúa las resueltas |
| "haz un informe de..." | lo arma o lo ubica en exports, con su ficha |
| "ordena esta carpeta" | reparte archivos sueltos sin romper enlaces |
| "añadí notas nuevas" | pone el mapa al día |
| "revisa el jardín" | verifica las notas por tandas contra sus originales, fusiona duplicados, archiva lo viejo, pone al día el tablero y enlaza las sueltas |
| "ayúdame con un handoff" o `/brainme:handoff` | guarda lo pendiente y sigue en una sesión nueva |
| "quiero llevar varios proyectos" | arma una carpeta multiproyecto, con un contexto general |
| "nuevo proyecto: ..." · "cierra el proyecto" | abre un proyecto de la carpeta multiproyecto, o lo cierra con su nota de cierre (se queda en su carpeta) |
| "cómo van los proyectos" | panorama de todos, sin abrir sus notas |
| "lleva esto al contexto general" | lo pasa sin datos del proyecto, con tu OK |

Al terminar cada tarea, brainme anota en `bitacora.md` qué hizo, quién y qué sigue, y
pone al día el tablero (`tablero.md`), que cada sesión carga al empezar.

Según la carpeta, brainme la configura (si está vacía), la ordena (si tiene avance
previo, con un solo OK y reversible) o te pone al día (si ya usa brainme).

## Varios proyectos: el modo multiproyecto

Si trabajas varios proyectos que comparten reglas y conocimiento (una consultora con sus
clientes, una tesis con sus estudios), brainme arma una carpeta multiproyecto:

```
mis-proyectos/
  CLAUDE.md                     reglas comunes: se cargan en cada sesión de adentro
  general/                      contexto general: lo que sirve a todos los proyectos
  proyectos/2026/acme-precios/  un brainme por proyecto, con su ficha y un prefijo en sus notas
```

Los proyectos se ordenan por el año en que se abren. Al cerrarse, se quedan en su
carpeta: lo aprendido sigue a mano.

- Cada sesión trabaja un proyecto y el contexto general; otro proyecto, solo si lo pides.
- Lo que sirve a otros pasa al contexto general sin datos del proyecto y con tu OK.
- Al configurar eliges los campos de la ficha, la revisión antes de entregar (un archivo
  o un skill tuyo), la nota al cerrar y de dónde llegan las reuniones.
- Si ya armaste una a mano, brainme la detecta y te ofrece convertirla, sin tocar lo
  propio de tu carpeta.

## De la misma familia

[discoverme](https://github.com/jlatorree/discoverme) es otro skill del mismo autor, para
investigar. Cada uno funciona solo; si los usas juntos, las fichas y los informes de
discoverme quedan en las carpetas de tu proyecto brainme.

## Requisitos

- Mac con Claude Code.
- Python 3, que viene con las herramientas de línea de comandos de Apple. Si faltan,
  brainme abre el instalador de macOS y tú aceptas. No hay que instalar nada más.

Opcionales: [Obsidian](https://obsidian.md), para ver y editar las notas, y Keynote,
para exportar presentaciones a PDF.

Desde la 3.2, brainme no usa Graphify: lee PDFs, imágenes y Office con su propio
ayudante. En los proyectos que ya lo usaban, sus archivos quedan como estaban.

## Instalación

En el **chat** de Claude Code (no en la terminal):

    /plugin marketplace add jlatorree/brainme
    /plugin install brainme@brainme

Luego **abre una sesión nueva**: el plugin recién instalado aparece como skill desde ahí.

## Actualizar

Activa el auto-update una vez: `/plugin` → **Marketplaces** → **brainme**. O a mano:

    /plugin marketplace update brainme
    /plugin update brainme@brainme
    /reload-plugins

## La estructura

```
00_inbox/                 lo que sueltas: se vacía al procesarse
01_knowledge/             una idea por nota
02_decisions/             decisiones, su porqué y alternativas descartadas
03_open_questions/        una pregunta por archivo (archive/ para las graduadas)
04_sources/               literature/ (fichas de papers + PDFs) y web/
05_exports/               entregables: una carpeta por cada uno, dentro de reports/,
                          presentations/, diagrams/ o data/ (aparecen con el primero)
CLAUDE.md                 hace que cada sesión arranque con brainme
tablero.md                lo vigente: objetivo, plan, próximos pasos y reglas aprendidas
bitacora.md               qué se hizo en cada sesión, quién y qué sigue
_taller/                  generadores de entregables (fuera de búsquedas y del mapa)
.brainme/                respaldos, inbox procesado y registros (oculto)
```

Cada entregable muestra su versión vigente y su ficha; las anteriores quedan en su
carpeta `versiones/`.

- **Nota** (`01`–`03`): lo que *sabes*. Viva, se amplía.
- **Fuente** (`04`): lo que *leíste*, con su cita y hallazgos.
- **Export** (`05`): lo que *produjiste*, con una ficha que dice de qué nació.

El mapa es gratis (sin IA): se calcula al instante desde los enlaces de tus notas, así
que nunca queda desactualizado.

## Qué incluye

| Archivo | Rol |
| --- | --- |
| `SKILL.md` | El skill: vocabulario, estructura y flujos. |
| `references/` | Configurar, inbox, multiproyecto, redacción, ordenar, entregables, jardín, handoff y migrar. |
| `templates/` | Nota, página de tema, tablero, ficha de paper, web y entregable, y `CLAUDE.md` de proyecto y de carpeta multiproyecto. |
| `scripts/brainme.py` | Estado, tablero, mapa de enlaces, búsqueda, índice, jardín y archivo de notas, texto de Office, orden sin romper enlaces, bitácora, multiproyecto, migración y consumo. Python 3, sin dependencias. |
| `agents/` | Ayudantes con modelo fijo: resúmenes (Haiku) y documentos largos (Sonnet). |
| `commands/handoff.md` | El comando `/brainme:handoff`. |
| `tests/` | Pruebas del script, sin gastar tokens: `python3 -m unittest discover tests`. |
| `.claude-plugin/` | Manifiestos del plugin y del marketplace. |
