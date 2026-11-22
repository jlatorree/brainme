# Pasar un proyecto a la versión actual de brainme

Se sigue cuando `brainme estado` dice "Migración pendiente", o cuando el usuario lo pide.
Sirve para proyectos creados con una versión anterior: les agrega lo nuevo sin tocar el
texto de ninguna nota y se puede deshacer.

**Terminado cuando:** `brainme estado` ya no dice "Migración pendiente", "Notas sin
resumen", "Entregables por ordenar" ni "Tablero por llenar" (salvo lo que el usuario
decidió dejar), y el usuario recibió el resumen final con su tablero.

1. **Revisa:** `brainme migrar`. Muestra los cambios automáticos y lo que harán los
   ayudantes: resúmenes que faltan, entregables por ordenar y autor. Si hay entregables
   por ordenar, corre también `brainme versiones` para ver lo que hay que preguntar.
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
   Antes hago un respaldo. Todo se puede deshacer, salvo los resúmenes: se quedan, y no
   cambian el texto. ¿Sigo?
   ```

   En el mismo mensaje van las preguntas de `brainme versiones` (a qué entregable va un
   archivo con nombre libre; si una carpeta propia guarda versiones viejas) y, si la
   ficha de `CLAUDE.md` mezcla estado (lo que está en curso, las próximas fechas), la
   propuesta de pasar esas líneas al tablero, citadas: la ficha es del usuario. Si dice
   que no, sigue con lo que pidió.
3. **Respaldo:** `brainme respaldo`.
4. **Cambios automáticos:** `brainme migrar --aplicar`.
5. **Autor:** si `brainme autor` dice "no definido", pregúntale su nombre y córrelo con el
   nombre: `brainme autor "Nombre"`.
6. **Tablero:** llena `tablero.md` con lo vigente que dicen la ficha de `CLAUDE.md`,
   `brainme bitacora --ultimas 10` y `brainme bitacora --handoff-ultimo`. Las reglas
   aprendidas salen de lo que el trabajo ya comprobó (el "Cuidado con" de los handoffs,
   notas con una trampa), cada una con cómo se sabe. Si el usuario aprobó pasar líneas
   de la ficha, quítalas de ahí.
7. **Entregables:** `brainme versiones --plan .brainme/plan-versiones.json` (con
   `--archivar <carpeta>` si el usuario lo aprobó), ajusta en el plan los destinos que
   respondió y `brainme mover --plan .brainme/plan-versiones.json`. Los enlaces se
   corrigen solos, también los que apuntan a una ficha que pasa a llamarse como su
   entregable. Después, actualiza en cada ficha `archivo` y `version` con la vigente.
8. **Resúmenes:** `brainme sin-resumen --lotes` escribe lotes de 25 notas en
   `.brainme/resumenes/`. Por cada lote, lanza el ayudante `brainme:resumidor` con la
   carpeta del proyecto y la ruta del lote, hasta 3 a la vez. Si se corta, se retoma igual:
   `sin-resumen` solo lista las notas que siguen sin resumen.
9. **Comprueba** y anota en la bitácora: `brainme bitacora "Pasé el proyecto a brainme
   <versión>"`.
10. **Cuéntale en simple** qué cambió y muéstrale el tablero. Para deshacer: `brainme
    migrar --deshacer` (archivos de configuración, y el tablero si nadie lo llenó) y
    `brainme deshacer` (entregables movidos). Los resúmenes quedan, porque no cambian el
    texto.
