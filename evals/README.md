# Proyecto de prueba

`huerto/` es un proyecto brainme inventado: un huerto comunitario con dos actas procesadas,
diez notas, una decisión reemplazada, un supuesto, un dato exacto y un error sembrado (una
nota dice que el local abre a las 8; el acta dice 9). `preguntas.json` trae diez preguntas con
su respuesta conocida y cómo calificarla.

Sirve para comparar versiones de brainme con datos y no solo con opinión.

## Sin gastar tokens

```bash
python3 -m unittest tests.test_eval
```

Mide lo que hace el script: que `buscar` traiga las notas de cada pregunta entre las 3
primeras, que lo vigente salga antes que lo reemplazado y que el jardín encuentre el error
sembrado.

## Con Claude

1. Copia `huerto/` a una carpeta fuera del repo y abre Claude Code ahí, con brainme instalado.
2. Haz las preguntas 1 a 10 de `preguntas.json`, una por sesión nueva, sin dar pistas.
3. Califica cada respuesta con su `criterio`: 1 si cumple, 0 si no.
4. Para la pregunta 9: di "revisa el jardín", acepta los cambios y vuelve a preguntar en una
   sesión nueva. Cuenta el punto solo si ahora responde 9.
5. Anota el resultado abajo, con la versión y el modelo.

| Fecha | Versión | Modelo | Puntos (de 10) | Notas |
|---|---|---|---|---|
