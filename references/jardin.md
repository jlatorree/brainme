# Revisar el jardín (el sueño)

Cada nota se escribió con lo que su sesión vio en ese momento. El jardín la revisa después,
contra los originales, para que la memoria siga correcta, sin duplicados y fácil de
recorrer. Se hace cuando el usuario lo pide o cuando `brainme estado` dice "toca revisar el
jardín". Si el usuario prefiere una cadencia fija (cada viernes, al cerrar una etapa),
anótala en el `CLAUDE.md` del proyecto.

**Terminado cuando:** `brainme jardin --hecho` lo cerró (solo lo hace sin notas por revisar),
cada duplicado, isla, enlace roto y enlace a una nota archivada que listó `brainme jardin`
quedó resuelto o el usuario decidió dejarlo, y el tablero refleja lo vigente.

Se puede parar después de cualquier tanda: lo anotado queda hecho, lo demás sigue en la
lista, y la bitácora dice cuántas notas faltan.

## Verificar, por tandas

1. **Tanda:** `brainme jardin` da hasta 20 notas nuevas o cambiadas desde su última revisión,
   con su original y las notas de su mismo tema. La verificación se puede repartir entre
   subagentes que devuelven los cambios propuestos: cada nota tiene un solo escritor, la
   sesión principal. Cada uno empieza por `brainme guia jardin convenciones`.
2. **Verifica** cada nota de la tanda contra todos sus originales: `brainme leer --tanda` da
   las notas con el texto de los suyos; si falta uno, la ficha de su fuente o la bitácora. Un
   dato
   crítico se compara palabra por palabra con su `## Texto exacto`.
   - Dice lo mismo: la nota es fiel, y su certeza sale de cómo lo dice el original
     (Convenciones, "Cómo se sabe"): una corazonada escrita en un acta sigue en `supuesto`. Las
     decisiones,
     preguntas y fuentes conservan sus campos (`estado`, `decidido_por`, `fiabilidad`), al día.
   - Dice otra cosa: la corrección, con fecha y porqué. Si choca con una decisión vigente,
     una pregunta abierta.
   - El original duda o no alcanza: en conocimiento, `supuesto`, aunque la nota lo diga con
     seguridad; en lo demás, una pregunta abierta.
   - Sin original porque salió de una conversación: vale lo que dice la nota sobre quién lo
     dijo y cuándo (`como_se_sabe` o `decidido_por`). Si no lo dice, pregúntale al usuario.
   - El original ya no está: se queda como estaba, y va en el informe.
3. **Compara** cada nota con las de su mismo tema. Si cuentan distinto un mismo hecho,
   queda lo más reciente que alguien sostiene, en un original o en una conversación anotada
   con quién y cuándo, y la otra nota se corrige o se archiva (paso 7). Si no se puede saber
   cuál rige, una pregunta abierta.
4. **Un OK por tanda:** una tabla corta con cada cambio (nota, qué cambia, por qué). Con
   el OK, aplícalos (Convenciones, "Ampliar y corregir").
5. **Anota** las notas de la tanda, también las que quedaron igual: `brainme jardin --hecho
   --tanda`. Sigue con la próxima hasta "Por revisar: 0 notas". Si el usuario decide saltarse
   las que faltan, `brainme jardin --hecho --sin-revisar`.

## Consolidar

6. **Duplicados:** lee las dos notas de cada par. Si dicen lo mismo, la que tiene mejor
   nombre se queda y recibe cada dato que solo está en la otra. Si solo se tocan, se
   enlazan. Cuando el usuario decide dejar un par así, `brainme jardin --dejar <una> <otra>`;
   una isla, una archivada con enlaces o un enlace roto, `--dejar <nota>`: el jardín no vuelve
   a listarlos.
7. **Lo obsoleto:** una nota que ya no es cierta se archiva, con la nota que la reemplaza
   si la hay. Los enlaces a una nota archivada se quedan donde cuentan la historia (una
   decisión que se tomó con ese dato) y se reapuntan donde buscan lo vigente.
8. **Páginas de tema**, con `templates/tema.md` y el nombre `<prefijo>tema-<tema>`, solo
   donde varias notas responden juntas una pregunta que cruza documentos. Los tags que
   lista `jardin` son candidatos: decide tú cuáles lo valen. La página resume en pocas
   líneas y enlaza; si empieza a repetir sus notas, ya no resume nada.
9. **Tablero:** sube lo que el jardín confirmó y pesa en lo que sigue (una regla, un cambio
   de plan), con cómo se sabe; baja a su nota lo que ahí ya es detalle, dejando el enlace.
10. **Mapa:** para cada isla o nota sin enlaces de salida, de 1 a 3 notas con las que se
    relaciona de verdad, por su resumen y no por palabras sueltas. Cada enlace roto, a la
    nota a la que quiso apuntar, o a una pregunta abierta si la idea aún no tiene nota.
11. **Un solo OK** para todo lo anterior, con la misma tabla. Con el OK, en este orden:
    - fusiones: pasa los datos a la nota que queda, vuelve a leerla para confirmar que
      llegó cada uno, y `brainme archivar <la-otra> --por <la-que-queda> --repuntar`;
    - obsoletas: en `## Actualizaciones`, desde cuándo y por qué quedó atrás, y
      `brainme archivar <nota>` (con `--por <nota>` si otra la reemplaza);
    - páginas de tema, tablero y enlaces del mapa.

`brainme archivar` pasa la nota al `archive/` de su carpeta, con `archivada` y, con `--por`,
`reemplazada_por`. Sus enlaces siguen llegando a ella; con `--repuntar`, pasan a la que la
reemplaza. `--deshacer` revierte el último archivado.

## Cerrar

12. `brainme jardin`: las notas que cambió la consolidación vuelven a la lista. Reléelas y
    anótalas (`--hecho --tanda`). Después, `brainme jardin --hecho` y la línea de la bitácora: qué se verificó,
    fusionó, archivó y creó.
