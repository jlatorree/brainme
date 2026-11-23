# Multiproyecto: un contexto general y varios proyectos

```
<carpeta multiproyecto>/
  CLAUDE.md                     sección ## brainme · multiproyecto: reglas comunes
  general/                      contexto general: un proyecto brainme con lo que sirve a todos
  proyectos/<año>/<proyecto>/   un proyecto brainme por carpeta, con su ficha y su prefijo
```

El `CLAUDE.md` de la raíz se carga en cada sesión de adentro: lo nuevo se integra en la
sección de su tema y el archivo queda bajo 200 líneas. El texto del usuario fuera de la
sección de brainme se cambia solo con su OK.

## Configurar ("quiero llevar varios proyectos")

**Terminado cuando:** el `CLAUDE.md` de la carpeta tiene la sección
`## brainme · multiproyecto`, existe el contexto general y `brainme autor` tiene nombre.

1. Carpeta y Python, como en `references/configurar.md`.
2. Pregunta en un solo mensaje de qué trata la carpeta, si el contexto general se llama
   `general` y qué campos quiere en la ficha de cada proyecto además de estado y prefijo
   (por ejemplo objetivo, personas a cargo, fechas clave). Si tiene reglas propias (una
   revisión antes de entregar, de dónde llegan las notas de reunión), anótalas.
3. `brainme crear --multiproyecto --trata "<de qué trata>"` (con `--general <nombre>` si
   no es `general`). Agrega a la ficha de la raíz los campos y reglas que pidió.
4. Autor, como en `references/configurar.md`.
5. Cuéntale en pocas líneas cómo queda, y que para empezar diga "nuevo proyecto: <nombre>".

## Nuevo proyecto ("nuevo proyecto: ...")

**Terminado cuando:** `proyectos/<año>/<carpeta>/` tiene su `CLAUDE.md` con la ficha llena
con lo que se sabe hoy, y la sesión nueva en esa carpeta quedó abierta (o el usuario tiene
la frase para abrirla).

1. Acuerda con el usuario el nombre de la carpeta (minúsculas, guiones, sin tildes) y un
   prefijo corto para sus notas, distinto de los que ya se usan (`brainme estado` en la
   raíz los muestra).
2. `brainme crear proyectos/<año en curso>/<carpeta> --prefijo <prefijo> --trata "<de qué
   trata>"`, con la ruta desde la raíz de la carpeta multiproyecto.
3. Llena la ficha (`## Proyecto` de su `CLAUDE.md`) con lo que el usuario sabe hoy, y en
   su tablero el objetivo y el primer paso.
4. Abre una sesión nueva en esa carpeta con el primer mensaje `brainme`: con la
   herramienta para iniciar sesiones si la tienes, o dile al usuario que abra Claude Code
   ahí y escriba `brainme`.

## Panorama ("cómo van los proyectos")

`brainme estado` en la raíz. Resume en hasta 10 líneas, solo con esa salida: una por
proyecto abierto (en qué está y qué sigue) y lo que pide atención (inbox pendiente,
proyectos sin sesiones hace más de dos semanas).

## Llevar algo al contexto general ("lleva esto al contexto general")

**Terminado cuando:** el inbox del contexto general tiene una versión sin datos del
proyecto, aprobada por el usuario.

1. Escribe la versión general: la idea, el aprendizaje o el método, sin nombres de
   organizaciones ni personas, cifras, fechas ni detalles que identifiquen al proyecto.
2. Muéstrasela junto con lo que quitaste y pide un OK.
3. Con el OK, guárdala como archivo `.md` en el `00_inbox/` del contexto general, y anota
   en la nota de origen que se llevó. Se procesa en la próxima sesión del contexto general.

## Cerrar un proyecto ("cierra el proyecto")

**Terminado cuando:** el proyecto tiene su nota de cierre, lo que sirve a otros quedó en el
inbox del contexto general con OK y su ficha dice `cerrado`.

1. `brainme estado`. Si hay inbox sin procesar o preguntas abiertas, muéstralo; el usuario
   decide qué queda así.
2. **Nota de cierre** en `01_knowledge/<prefijo>cierre.md`: qué se logró, qué aprendimos,
   qué haríamos distinto y qué quedó abierto, solo con lo que consta, enlazada a las
   decisiones clave. Si la raíz pide otra nota de cierre, esa.
3. Lo que sirve a otros proyectos va al contexto general ("Llevar"), con un solo OK para
   toda la lista.
4. En la ficha, `Estado: cerrado AAAA-MM-DD`. El proyecto se queda en su carpeta; para
   reabrirlo, vuelve a `activo`.
