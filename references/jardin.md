# Revisar el jardín

Cada nota se escribió con lo que su sesión vio en ese momento, y las sesiones siguientes la
creen. El jardín la vuelve a leer contra su original para que siga siendo cierta, y después
junta lo duplicado y cierra lo suelto.

**Terminado cuando:** `brainme jardin` dice "Por revisar: 0 notas" y cada cosa que listó
`brainme comprueba --todo` quedó resuelta o el usuario decidió dejarla así. Se puede parar
después de cualquier tanda: lo marcado queda hecho; anota en la bitácora cuántas faltan.

## Verificar, por tandas

1. `brainme jardin` da la próxima tanda.
2. `brainme leer --original <las notas de la tanda>` y compara cada nota con su original:
   - **Dice lo mismo:** queda como está.
   - **Dice otra cosa:** corrige la nota, con una línea en `## Actualizaciones` que dice qué
     decía. Un dato crítico se compara palabra por palabra con su `## Texto exacto`.
   - **El original duda o no alcanza:** `certeza: supuesto`; en una decisión, una pregunta
     abierta.
   - **Sin archivo** (salió de una conversación): vale el `origen` si dice quién y cuándo; si
     no lo dice, pregúntale al usuario.
3. **Un OK por tanda:** una tabla corta con cada cambio (nota, qué cambia, por qué). Con el
   OK, aplícalo y marca la tanda entera, también las que quedaron igual:
   `brainme jardin --hecho <las notas de la tanda>`. Sigue con la próxima.

## Consolidar

4. `brainme comprueba --todo`, y lee las notas que nombra. En cada duplicado, y entre las
   notas de un mismo tema, mira si cuentan distinto un mismo hecho: rige lo más reciente que
   alguien sostiene, y la otra nota se corrige con una línea en `## Actualizaciones`; si no se
   sabe cuál rige, una pregunta abierta.
5. **Un OK para todo:** una tabla corta con qué harás con cada cosa que listó. Un par de
   duplicados se fusiona: la que queda recibe en `## Actualizaciones` cada dato de la otra,
   que pasa al `archive/` de su carpeta. El resumen y el enlace que faltan salen de la nota
   (si faltan más de 10 resúmenes, `brainme ordenar resumenes` y el ayudante, como en
   `references/ordenar.md`); quién decidió o cuánto pesa una pregunta, de la nota, su
   original o el usuario.
6. Con el OK, aplícalo y corre otra vez `brainme comprueba --todo`. Las notas que cambiaste
   vuelven a `brainme jardin`: reléelas y márcalas.
