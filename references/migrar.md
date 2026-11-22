# Pasar un proyecto a la versión actual de brainme

Se sigue cuando `BRAIN estado` dice "Migración pendiente", o cuando el usuario lo pide.
Sirve para proyectos creados con una versión anterior: les agrega lo nuevo sin tocar el
texto de ninguna nota y se puede deshacer.

**Terminado cuando:** `BRAIN estado` ya no dice "Migración pendiente", "Notas sin
resumen" ni "Tablero por llenar", y el usuario recibió el resumen final con su tablero.

1. **Revisa:** `BRAIN migrar`. Muestra los cambios automáticos y lo que harán los
   ayudantes: resúmenes que faltan, entregables por ordenar y autor. Si hay entregables
   por ordenar, corre también `BRAIN versiones` para ver lo que hay que preguntar.
2. **Un solo OK.** Explícale al usuario en simple qué cambia, por ejemplo:

   ```
   Este proyecto es de una versión anterior de brainme. Para ponerlo al día:
   - Anoto la versión en CLAUDE.md y creo la bitácora (bitacora.md).
   - Creo tablero.md con lo vigente (objetivo, plan, próximos pasos y reglas
     aprendidas), armado con la ficha, la bitácora y el último handoff. Se carga en cada
     sesión.
   - Quito un aviso de Graphify pensado para código que gasta tokens en cada búsqueda.
   - Escribo un resumen corto en las 153 notas que no tienen. No cambio su texto.
   - Doy a cada entregable su carpeta: la versión vigente a la vista y las 12 anteriores
     en versiones/. Las carpetas vacías de 05_exports aparecen con su primer entregable.
   Antes hago un respaldo, y todo se puede deshacer. ¿Sigo?
   ```

   En el mismo mensaje van las preguntas de `BRAIN versiones` (a qué entregable va un
   archivo con nombre libre; si una carpeta propia guarda versiones viejas) y, si la
   ficha de `CLAUDE.md` mezcla estado (lo que está en curso, las próximas fechas), la
   propuesta de pasar esas líneas al tablero, citadas: la ficha es del usuario. Si dice
   que no, sigue con lo que pidió.
3. **Respaldo:** `BRAIN respaldo`.
4. **Cambios automáticos:** `BRAIN migrar --aplicar`.
5. **Autor:** si `BRAIN autor` dice "no definido", pregúntale su nombre y córrelo con el
   nombre: `BRAIN autor "Nombre"`.
6. **Tablero:** llena `tablero.md` con lo vigente que dicen la ficha de `CLAUDE.md`,
   `BRAIN bitacora --ultimas 10` y `BRAIN bitacora --handoff-ultimo`. Las reglas
   aprendidas salen de lo que el trabajo ya comprobó (el "Cuidado con" de los handoffs,
   notas con una trampa), cada una con cómo se sabe. Si el usuario aprobó pasar líneas
   de la ficha, quítalas de ahí.
7. **Entregables:** `BRAIN versiones --plan .brainme/plan-versiones.json` (con
   `--archivar <carpeta>` si el usuario lo aprobó), ajusta en el plan los destinos que
   respondió y `BRAIN mover --plan .brainme/plan-versiones.json`. Los enlaces se
   corrigen solos, también los que apuntan a una ficha que pasa a llamarse como su
   entregable. Después, actualiza en cada ficha `archivo` y `version` con la vigente.
8. **Resúmenes:** `BRAIN sin-resumen --lotes` escribe lotes de 25 notas en
   `.brainme/resumenes/`. Por cada lote, lanza el ayudante `brainme:resumidor` con la
   carpeta del proyecto y la ruta del lote, hasta 3 a la vez. Si el ayudante no existe
   (brainme instalado sin plugin), usa un subagente general con el modelo `haiku` y el
   esfuerzo `low`, y dale las instrucciones de `agents/resumidor.md`. Si se corta, se
   retoma igual: `sin-resumen` solo lista las notas que siguen sin resumen.
9. **Sincroniza** y anota en la bitácora: `BRAIN bitacora "Pasé el proyecto a brainme
   <versión>"`.
10. **Cuéntale en simple** qué cambió y muéstrale el tablero. Para deshacer: `BRAIN
    migrar --deshacer` (archivos de configuración, y el tablero si nadie lo llenó) y
    `BRAIN deshacer` (entregables movidos). Los resúmenes quedan, porque no cambian el
    texto.
