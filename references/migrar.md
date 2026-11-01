# Pasar un proyecto a la versión actual de brainme

Se sigue cuando `BRAIN estado` dice "Migración pendiente", o cuando el usuario lo pide.
Sirve para proyectos creados con una versión anterior: les agrega lo nuevo sin tocar el
texto de ninguna nota y se puede deshacer.

**Terminado cuando:** `BRAIN estado` ya no dice "Migración pendiente" ni "Notas sin
resumen", y el usuario recibió el resumen final.

1. **Revisa:** `BRAIN migrar`. Muestra los cambios automáticos y lo que harán los
   ayudantes: resúmenes que faltan, versiones viejas de entregables y autor.
2. **Un solo OK.** Explícale al usuario en simple qué cambia, por ejemplo:

   ```
   Este proyecto es de una versión anterior de brainme. Para ponerlo al día:
   - Anoto la versión en CLAUDE.md y creo la bitácora (bitacora.md).
   - Quito un aviso de Graphify pensado para código que gasta tokens en cada búsqueda.
   - Escribo un resumen corto en las 153 notas que no tienen. No cambio su texto.
   - Muevo 12 versiones viejas de entregables a _versiones/, junto a la versión vigente.
   Antes hago un respaldo, y todo se puede deshacer. ¿Sigo?
   ```

   Si dice que no, sigue con lo que pidió.
3. **Respaldo:** `BRAIN respaldo`.
4. **Cambios automáticos:** `BRAIN migrar --aplicar`.
5. **Autor:** si `BRAIN autor` dice "no definido", pregúntale su nombre y córrelo con el
   nombre: `BRAIN autor "Nombre"`.
6. **Versiones viejas:** `BRAIN versiones --plan .brainme/plan-versiones.json` y después
   `BRAIN mover --plan .brainme/plan-versiones.json`. Los wikilinks siguen funcionando,
   porque van por nombre.
7. **Resúmenes:** `BRAIN sin-resumen --lotes` escribe lotes de 25 notas en
   `.brainme/resumenes/`. Por cada lote, lanza el ayudante `brainme:resumidor` con la
   carpeta del proyecto y la ruta del lote, hasta 3 a la vez. Si el ayudante no existe
   (brainme instalado sin plugin), usa un subagente general con el modelo `haiku` y el
   esfuerzo `low`, y dale las instrucciones de `agents/resumidor.md`. Si se corta, se
   retoma igual: `sin-resumen` solo lista las notas que siguen sin resumen.
8. **Sincroniza** y anota en la bitácora: `BRAIN bitacora "Pasé el proyecto a brainme
   <versión>"`.
9. **Cuéntale en simple** qué cambió. Para deshacer: `BRAIN migrar --deshacer` (archivos
   de configuración) y `BRAIN deshacer` (versiones movidas). Los resúmenes quedan, porque
   no cambian el texto.
