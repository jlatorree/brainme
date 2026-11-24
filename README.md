# brainme

Un skill de Claude Code que convierte cada proyecto en un **segundo cerebro**: una
carpeta de notas markdown conectadas entre sí, que puedes abrir en Obsidian. Le sueltas
apuntes, actas y documentos, y después le preguntas qué sabe, qué decidiste y qué falta.

## Cómo funciona

- **Inbox:** sueltas ahí lo que llega (apuntes, reuniones, PDFs, Word). brainme lo
  convierte en notas y deja el original guardado.
- **Notas:** una idea por nota (lo que se sabe, lo que se decidió, lo que sigue abierto),
  con un resumen, de dónde salió, quién la escribió y enlaces a otras notas. Cada decisión
  dice quién la tomó y cuál reemplaza; cada pregunta, su prioridad y quién puede responderla.
- **Tablero:** el objetivo, el plan y los próximos pasos. Se carga en cada sesión.
- **Bitácora:** qué se hizo en cada sesión, quién y qué sigue.
- **Tú no programas:** Claude corre los comandos y te cuenta en simple qué hizo.

Con el **modo multiproyecto**, varios proyectos comparten un contexto general y sus
reglas.

## Qué le puedes pedir

| Dile | Qué hace |
| --- | --- |
| "brainme" | Te pone al día: dónde estamos y qué sigue. |
| "¿qué decidimos sobre…?" | Responde con enlaces a las notas de las que sale. |
| "procesa el inbox" | Convierte lo que hay en el inbox en notas. |
| "guarda esto" | Lo deja en su nota, enlazada a las demás. |
| "haz un informe de…" | Lo arma con las notas y dice qué es supuesto. |
| "revisa las notas" | Relee las notas contra sus originales, por tandas, y te propone cómo arreglar lo que cambió, lo suelto y lo duplicado. |
| "ordena esta carpeta" | Si ya tenías trabajo, lo pone en la estructura sin romper los enlaces, con respaldo y deshacer. |
| "ayúdame con un handoff" | Guarda lo pendiente y abre una sesión nueva que sigue desde ahí. |
| "nuevo proyecto: …" | En una carpeta multiproyecto, abre un proyecto con su ficha. |

## Requisitos

- Mac con Claude Code.
- Python 3, que viene con las herramientas de línea de comandos de Apple. Si faltan,
  brainme abre el instalador de macOS y tú aceptas. No hay que instalar nada más.
- Opcional: [Obsidian](https://obsidian.md), para ver y editar las notas.

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
00_inbox/            lo que llega; se vacía al procesarse
01_knowledge/        lo que se sabe
02_decisions/        lo que se decidió, por qué y qué se descartó
03_open_questions/   una pregunta por archivo (archive/: las resueltas)
04_sources/          originales con valor propio: contratos, PDFs, Excel
05_exports/          entregables
CLAUDE.md            hace que cada sesión arranque con brainme
tablero.md           lo vigente: objetivo, plan y próximos pasos
bitacora.md          qué se hizo en cada sesión, quién y qué sigue
.brainme/            originales ya procesados (oculto)
```

## Qué incluye

| Archivo | Rol |
| --- | --- |
| `SKILL.md` | El skill: flujos y cómo se escriben las notas. |
| `references/` | Configurar, inbox, jardín, ordenar, handoff, multiproyecto y redacción. |
| `templates/` | Nota, tablero y `CLAUDE.md` de proyecto y de carpeta multiproyecto. |
| `scripts/brainme.py` | Once comandos: estado, buscar, leer, inbox, procesado, comprueba, jardín, bitácora, autor, crear y ordenar. Python 3, sin dependencias. Lee el proyecto y no mueve ni reescribe notas. |
| `scripts/ordenar.py` | Lo único que mueve archivos o les escribe: ordena una carpeta con avance previo según un plan aprobado, corrige los enlaces, permite deshacer y pone los resúmenes que faltan. |
| `agents/lector.md` | Ayudante que lee documentos largos. |
| `agents/resumidor.md` | Ayudante que escribe los resúmenes que faltan, por lotes. |
| `commands/handoff.md` | El comando `/brainme:handoff`. |
| `tests/` | Pruebas del script, sin gastar tokens: `python3 -m unittest discover tests`. |
| `evals/` | Un proyecto de prueba con 10 preguntas de respuesta conocida, para comparar versiones. |
| `.claude-plugin/` | Manifiestos del plugin y del marketplace. |
