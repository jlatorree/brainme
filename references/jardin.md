# Revisar el jardín (el sueño)

Cada nota se escribió con lo que su sesión vio en ese momento. El jardín la revisa después,
con calma y contra los originales, para que la memoria siga correcta, sin duplicados y
fácil de recorrer. Se hace cuando el usuario lo pide o cuando `BRAIN estado` dice "toca
revisar el jardín". Si el usuario prefiere una cadencia fija (cada viernes, al cerrar una
etapa), anótala en el `CLAUDE.md` del proyecto.

**Terminado cuando:** cada punto que listó `BRAIN jardin` quedó resuelto o el usuario
decidió dejarlo, el tablero refleja lo vigente, `BRAIN mapa` no muestra islas ni enlaces
rotos (salvo los que el usuario dejó), y corriste `BRAIN jardin --hecho`. Un jardín a
medias termina con la bitácora diciendo qué faltó, y sin `--hecho`: así lo pendiente
sigue en la lista del próximo.

## Decidir

1. **Lista de trabajo:** `BRAIN jardin`. Va de lo que cambia más rápido a lo estable:
   tablero, supuestos, lo nuevo o editado, duplicados, enlaces a notas archivadas, el mapa
   y los temas. Sigue ese orden. Con más de ~20 notas que verificar, reparte la
   verificación en tandas a subagentes que devuelven los cambios propuestos: cada nota
   tiene un solo escritor, la sesión principal.
2. **Verifica** cada supuesto y cada nota nueva o editada contra su original: la ruta que
   da `jardin`, la ficha de su fuente o la bitácora. Lee el original mismo, además de la
   nota.
   - Lo confirma: `certeza: confirmado`, y en `como_se_sabe`, qué lo confirmó y la fecha.
   - Lo contradice: la corrección, con fecha y porqué. Si choca con una decisión vigente,
     una pregunta abierta.
   - El original duda o no alcanza: `supuesto`, aunque la nota lo diga con seguridad.
   - Un dato crítico se compara palabra por palabra con su `## Texto exacto`.
   - Compárala también con las notas de su mismo tema que lista `jardin` (comparten tags
     o enlaces). Si cuentan distinto un mismo hecho, queda lo que confirma el original más
     reciente: la otra nota se corrige o se archiva con `--por`. Si ningún original zanja
     la diferencia, una pregunta abierta.
3. **Duplicados:** lee las dos notas de cada par. Si dicen lo mismo, la que tiene mejor
   nombre se queda y recibe cada dato que solo está en la otra. Si solo se tocan, se
   enlazan.
4. **Lo obsoleto:** una nota que ya no es cierta se archiva, con la nota que la reemplaza
   si la hay. Los enlaces a una nota archivada se quedan donde cuentan la historia (una
   decisión que se tomó con ese dato) y se reapuntan donde buscan lo vigente.
5. **Páginas de tema**, con `templates/tema.md` y el nombre `<prefijo>tema-<tema>`, solo
   donde varias notas responden juntas una pregunta que cruza documentos. Los tags que
   lista `jardin` son candidatos: decide tú cuáles lo valen. La página resume en pocas
   líneas y enlaza; si empieza a repetir sus notas, ya no resume nada.
6. **Tablero:** sube lo que el jardín confirmó y pesa en lo que sigue (una regla, un cambio
   de plan), con cómo se sabe; baja a su nota lo que ahí ya es detalle, dejando el enlace.
7. **Mapa:** para cada isla o nota sin enlaces de salida, de 1 a 3 notas con las que se
   relaciona de verdad, por su resumen y no por palabras sueltas. Cada enlace roto, a la
   nota a la que quiso apuntar, o a una pregunta abierta si la idea aún no tiene nota.

## Aplicar

8. **Un solo OK:** una tabla corta con cada cambio (nota, qué cambia, por qué). Lo que
   escribió el usuario se amplía en `## Actualizaciones`; para cambiar su texto,
   pregúntale.
9. **Con el OK**, en este orden:
   - correcciones y certezas, en `## Actualizaciones` con fecha y autor;
   - fusiones: pasa los datos a la nota que queda, vuelve a leerla para confirmar que
     llegó cada uno, y `BRAIN archivar <la-otra> --por <la-que-queda> --repuntar`;
   - obsoletas: en `## Actualizaciones`, desde cuándo y por qué quedó atrás, y
     `BRAIN archivar <nota>` (con `--por <nota>` si otra la reemplaza);
   - páginas de tema, tablero y enlaces del mapa.
10. **Cierra:** sincroniza, `BRAIN jardin --hecho` y la línea de la bitácora: qué se
    verificó, fusionó, archivó y creó. `BRAIN archivar --deshacer` revierte el último
    archivado.
