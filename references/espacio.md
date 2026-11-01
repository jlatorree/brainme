# Espacio: un contexto general y varios proyectos

```
<espacio>/
  CLAUDE.md                     sección ## brainme · espacio: reglas y configuración
  <general>/                    contexto general: proyecto brainme con lo que sirve a todos
  proyectos/<año>/<proyecto>/   un proyecto brainme por carpeta, con su ficha y su prefijo
```

`<año>` es el año en que se abre el proyecto. Un proyecto cerrado se queda en su carpeta,
con `Estado: cerrado` en su ficha: lo que se aprendió sigue a mano.

## Los `CLAUDE.md` del espacio

- El texto del usuario fuera de la sección de brainme (quiénes son, documentos que
  importa con `@`, reglas de su oficio) es suyo: se cambia solo con su OK.
- Se cargan en cada respuesta de cada sesión de adentro: lo nuevo se integra en la
  sección de su tema, y cada archivo queda bajo 200 líneas.
- En la bitácora del contexto general, los proyectos van sin nombre ("abrí un proyecto
  nuevo").

## Configurar un espacio ("configura un espacio")

**Terminado cuando:** el `CLAUDE.md` de la carpeta tiene la sección `## brainme ·
espacio`, existe el contexto general y el usuario recibió el mensaje final.

1. **Carpeta y Python:** como en `references/configurar.md`.
2. **Pregunta en un solo mensaje**, con estas respuestas por defecto:
   - nombre del espacio y de qué trata;
   - nombre del contexto general (`general`);
   - campos de la ficha de cada proyecto, además de estado y prefijo (objetivo,
     alcance, personas a cargo, fechas clave);
   - revisión antes de entregar: ninguna, la de un archivo o la de un skill;
   - nota al cerrar un proyecto: la de brainme, la de un archivo o la de un skill;
   - de dónde llegan las notas de reunión: de ningún lado, de Granola o de una carpeta.
3. **`CLAUDE.md`:** créalo desde `templates/CLAUDE-espacio.md` con las respuestas y
   quita las viñetas que no aplican. Si ya existe, agrega la sección al final.
4. **Autor:** como en `references/configurar.md`.
5. **Contexto general:** `BRAIN crear <general> --trata "<de qué trata>"`.
6. **Mensaje final**, por ejemplo:

   ```
   Listo, este espacio ya funciona con brainme:
   - <general>/ guarda lo que sirve a todos los proyectos.
   - Cada proyecto vive en proyectos/<año>/, con su ficha y un prefijo en sus notas.
   - Las reglas del espacio se cargan en cada sesión que abras adentro.
   Para empezar, dime "nuevo proyecto: <nombre>".
   ```

## Nuevo proyecto ("nuevo proyecto: ...")

**Terminado cuando:** `proyectos/<año>/<carpeta>/` tiene `CLAUDE.md` con su ficha llena
con lo que se sabe hoy, y el usuario tiene abierta la sesión nueva en esa carpeta (o la
frase para abrirla).

1. Acuerda con el usuario el nombre de la carpeta (minúsculas, guiones, sin tildes) y un
   prefijo corto para sus notas. `BRAIN espacio` muestra los prefijos en uso.
2. `BRAIN crear proyectos/<año en curso>/<carpeta> --prefijo <prefijo> --trata "<de qué
   trata>"`. La ruta va desde la raíz del espacio, aunque la sesión esté en el contexto
   general.
3. Llena la ficha (`## Proyecto` de su `CLAUDE.md`) con lo que el usuario sabe hoy; lo
   demás queda `<por completar>`.
4. **Abre la sesión nueva** en esa carpeta, con el primer mensaje `brainme`: si tienes
   una herramienta para iniciar sesiones de Claude Code (la app de escritorio la tiene),
   créala con esa carpeta como directorio de trabajo; si no, dile al usuario que abra
   Claude Code en esa carpeta y escriba `brainme`.

## Panorama ("cómo van los proyectos")

1. `BRAIN espacio`.
2. Resume en hasta 10 líneas, solo con esa salida: una línea por proyecto abierto (en qué
   está y qué sigue, de su última sesión) y lo que pide atención: inbox con pendientes,
   proyectos sin sesiones hace más de dos semanas y fichas por completar.

## Llevar algo al contexto general ("lleva esto al contexto general")

**Terminado cuando:** el inbox del contexto general tiene una versión sin datos del
proyecto, aprobada por el usuario, y la nota de origen lo anota.

1. Escribe la versión general: la idea, el aprendizaje o el método, sin nombres de
   organizaciones ni personas, cifras, fechas o detalles que identifiquen al proyecto.
2. Muéstrala junto con lo que quitaste y pide un OK.
3. Con el OK, guárdala en `<general>/00_inbox/desde-un-proyecto-AAAA-MM-DD-<tema>.md`,
   con `autor` y sin wikilinks al proyecto.
4. En la nota de origen, anota en `## Actualizaciones`: "Llevada al contexto general
   (AAAA-MM-DD)", con autor.
5. En una sesión de proyecto, avisa que el contexto general la procesa en su próxima
   sesión.

## Cerrar un proyecto ("cierra el proyecto")

Se hace en la sesión del proyecto, que tiene su contexto. Si el pedido llega desde otra,
ofrece abrirla (paso 4 de "Nuevo proyecto").

**Terminado cuando:** el proyecto tiene su nota de cierre, lo que sirve a otros está en el
inbox del contexto general con OK, y su ficha dice `cerrado`.

1. `BRAIN estado`. Si hay inbox sin procesar o preguntas abiertas, muéstralo y pregunta
   si se procesan, se gradúan o quedan así.
2. **Nota de cierre:** la que diga "Al cerrar un proyecto" en el `CLAUDE.md` del espacio.
   La de brainme es `01_knowledge/<prefijo>cierre.md` (`tipo: conocimiento`): qué se
   logró, qué aprendimos, qué haríamos distinto y qué quedó abierto, enlazada a las
   decisiones clave.
3. Lo que sirve a otros proyectos va al contexto general con "Llevar", con un solo OK
   para toda la lista.
4. En la ficha, `Estado: cerrado AAAA-MM-DD`. El proyecto se queda en su carpeta; para
   reabrirlo, vuelve a `activo`.

## Convertir un espacio armado a mano

Se sigue cuando `BRAIN estado` o `BRAIN espacio` dice "Espacio armado a mano", o cuando
el usuario lo pide.

**Terminado cuando:** `BRAIN espacio` muestra todos los proyectos en
`proyectos/<año>/`, cada ficha tiene estado y prefijo, `BRAIN verificar` no muestra
enlaces rotos en los proyectos movidos y el usuario aprobó cada cambio a su texto.

1. `BRAIN espacio`: la carpeta y sus proyectos brainme.
2. Lee el `CLAUDE.md` de la raíz y, de cada proyecto, solo su `CLAUDE.md`. Identifica el
   contexto general, los campos de las fichas, la revisión antes de entregar, la nota al
   cerrar, de dónde llegan las reuniones, y las reglas que ya cubre la sección de brainme
   (aislamiento entre proyectos, qué manda, ciclo de un proyecto).
3. **Plan con un solo OK**, en una tabla corta:
   - la sección `## brainme · espacio`, llenada con lo que el archivo ya dice;
   - las líneas del usuario que esa sección vuelve repetidas, citadas, para quitarlas;
   - por proyecto: estado y prefijo en su ficha si faltan, y las secciones que repiten
     lo que ya dice el `CLAUDE.md` del espacio;
   - cada proyecto, salvo el contexto general, a `proyectos/<año>/`, con el año de su
     "Configurado con brainme".
4. **Respaldo:** copia cada `CLAUDE.md` que vas a cambiar a
   `.brainme/conversion-espacio/AAAA-MM-DD/`, en la raíz del espacio, con su ruta.
5. Aplica el plan. En cada proyecto movido, `BRAIN --raiz <proyecto> verificar`: los
   wikilinks siguen funcionando, pero un link markdown hacia fuera del proyecto puede
   romperse; corrígelo. Verifica con `BRAIN espacio`.
6. Cuenta en simple qué cambió. Para deshacer: copiar de vuelta los respaldos y mover
   los proyectos a su lugar anterior.
