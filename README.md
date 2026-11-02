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

1. **Enlazar es construir:** cada nota se conecta; Claude responde consultando el mapa.
2. **Tú no programas:** brainme corre todo y te explica qué hizo.
3. **Toda afirmación con su fuente:** doble cita, el link real y la ficha en el mapa.
4. **Nada se pierde:** se mueve, no se borra; todo orden tiene respaldo y se deshace.
5. **Pocos tokens:** cada nota tiene un resumen, lo pesado lo hacen ayudantes con el
   modelo justo y, cuando la sesión se llena, un handoff sigue en una sesión nueva.

## Cómo se usa

Abre Claude Code en la carpeta del proyecto, escribe **brainme** y habla normal:

| Dices | brainme |
| --- | --- |
| "ponme al día" | resume estado, decisiones, preguntas abiertas e inbox |
| "procesa el inbox" | convierte apuntes y reuniones en notas conectadas |
| "guarda esto" | guarda lo que surgió como nota conectada |
| "qué preguntas siguen abiertas" | las lista por prioridad y gradúa las resueltas |
| "investiga la literatura sobre..." | deep research con fichas e informe con doble cita |
| "haz un informe de..." | lo arma o lo ubica en exports, con su ficha |
| "ordena esta carpeta" | reparte archivos sueltos sin romper enlaces |
| "añadí notas nuevas" | pone el mapa al día |
| "revisa el jardín" | enlaza las notas sueltas y arregla enlaces rotos |
| "ayúdame con un handoff" o `/brainme:handoff` | guarda lo pendiente y sigue en una sesión nueva |
| "configura un espacio" | arma una carpeta para varios proyectos con un contexto general |
| "nuevo proyecto: ..." · "cierra el proyecto" | abre un proyecto del espacio, o lo cierra con su nota de cierre (se queda en su carpeta) |
| "cómo van los proyectos" | panorama de todos, sin abrir sus notas |
| "lleva esto al contexto general" | lo pasa sin datos del proyecto, con tu OK |

Al terminar cada tarea, brainme anota en `bitacora.md` qué hizo, quién y qué sigue.

Según la carpeta, brainme la configura (si está vacía), la ordena (si tiene avance
previo, con un solo OK y reversible) o te pone al día (si ya usa brainme).

## Varios proyectos: el modo espacio

Si trabajas varios proyectos que comparten reglas y conocimiento (una consultora con sus
clientes, una tesis con sus estudios), brainme arma un espacio:

```
mi-espacio/
  CLAUDE.md                     reglas del espacio: se cargan en cada sesión de adentro
  general/                      contexto general: lo que sirve a todos los proyectos
  proyectos/2026/acme-precios/  un brainme por proyecto, con su ficha y un prefijo en sus notas
```

Los proyectos se ordenan por el año en que se abren. Al cerrarse, se quedan en su
carpeta: lo aprendido sigue a mano.

- Cada sesión trabaja un proyecto y el contexto general; otro proyecto, solo si lo pides.
- Lo que sirve a otros pasa al contexto general sin datos del proyecto y con tu OK.
- Al configurar eliges los campos de la ficha, la revisión antes de entregar (un archivo
  o un skill tuyo), la nota al cerrar y de dónde llegan las reuniones.
- Si ya armaste uno a mano, brainme lo detecta y te ofrece convertirlo, sin tocar lo
  propio de tu espacio.

## Requisitos

- Mac con Claude Code.
- [Homebrew](https://brew.sh): instálalo tú antes, porque pide tu contraseña. Trae de
  paso Python 3, que brainme también usa. [Guía paso a paso](https://claude.ai/artifact/D9QNftYYdY1QW4huHFPPGi).

Opcional: [Graphify](https://github.com/Graphify-Labs/graphify), para la lectura
profunda de PDF, imágenes, Word y Excel. Si tu proyecto los tiene, brainme te lo ofrece
y lo instala con tu OK. Sin Graphify, brainme funciona igual.

También opcionales: [Obsidian](https://obsidian.md), para ver y editar las notas, y
Keynote, para exportar presentaciones a PDF.

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
bitacora.md               qué se hizo en cada sesión, quién y qué sigue
_taller/                  generadores de entregables (fuera de búsquedas y del mapa)
.brainme/                respaldos, inbox procesado y registros (oculto)
```

Cada entregable muestra su versión vigente y su ficha; las anteriores quedan en su
carpeta `versiones/`.

- **Nota** (`01`–`03`): lo que *sabes*. Viva, se amplía.
- **Fuente** (`04`): lo que *leíste*, con su cita y hallazgos.
- **Export** (`05`): lo que *produjiste*, con una ficha que dice de qué nació.

El mapa es gratis (sin IA) y se calcula al instante; la lectura profunda de PDFs e
imágenes, con Graphify, se usa solo cuando hace falta.

## Qué incluye

| Archivo | Rol |
| --- | --- |
| `SKILL.md` | El skill: vocabulario, estructura y flujos. |
| `references/` | Configurar, espacio, redacción, ordenar, investigar, entregables, handoff, migrar y problemas con Graphify. |
| `templates/` | Nota, ficha de paper, web y entregable, `CLAUDE.md` de proyecto y de espacio, y `.graphifyignore`. |
| `scripts/brainme.py` | Estado, mapa de enlaces, índice, orden sin romper enlaces, bitácora, espacio y proyectos, migración y consumo. Python 3, sin dependencias. |
| `agents/` | Ayudantes con modelo fijo: resúmenes (Haiku), documentos largos (Sonnet) e investigación (Opus en esfuerzo xhigh). |
| `commands/handoff.md` | El comando `/brainme:handoff`. |
| `tests/` | Pruebas del script, sin gastar tokens: `python3 -m unittest discover tests`. |
| `.claude-plugin/` | Manifiestos del plugin y del marketplace. |
