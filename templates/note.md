---
titulo: "<Título corto y claro: la idea en una frase>"
tipo: <conocimiento | decision | pregunta>
fecha: <AAAA-MM-DD>
proyecto: "<nombre del proyecto>"
resumen: "<la idea en una o dos frases, unos 200 caracteres; si ayuda, la pregunta que alguien haría para encontrarla>"
autor: "<quién la escribe: BRAIN autor>"
tags: [<tema-1>, <tema-2>]
relacionadas: ["[[nota-existente-1]]", "[[nota-existente-2]]"]
origen: "<nombre-del-original (inbox, AAAA-MM-DD) o conversación AAAA-MM-DD>"
# estado: decisión = propuesta | tomada | revertida; pregunta = abierta | resuelta; conocimiento = borra el campo
estado: <según el tipo>
# Solo decisiones:
decidido_por: "<persona o instancia que decidió>"
reemplaza_a: "<[[decision-anterior]] si la hay>"
# Solo preguntas:
prioridad: <alta | media | baja>
quien_puede_responder: "<persona, equipo o fuente>"
resuelta_en: "<[[nota-con-la-respuesta]], al graduarla>"
fecha_resolucion: <AAAA-MM-DD, al graduarla>
# Solo conocimiento o decisión que nace de responder una pregunta:
responde_a: "<[[pregunta-...]]>"
---

<!--
Instrucciones de la plantilla (bórralas al crear la nota):
- Una idea por nota. Si hay varias ideas, crea varias notas y enlázalas.
- Borra los campos y secciones que no apliquen al tipo de nota.
- Quita todos los placeholders <...>.
- Enlaza por nombre, sin carpeta: [[decision-modelo-de-precio]].
-->

# <Título de la nota>

## Contexto
Qué situación, reunión o pregunta dio origen a esto. Una o dos frases.

## Contenido
La idea en sí: lo que se aprendió, decidió o se pregunta. Sé concreto (datos,
cifras, nombres). Enlaza conceptos y otras notas con [[wikilinks]]: eso alimenta
el grafo.

- En una **pregunta**: formúlala en una frase y resume qué se sabe hoy.

## Por qué importa / implicaciones
El razonamiento detrás y qué cambia en el proyecto a partir de esto.

## Alternativas descartadas
<!-- Solo decisiones -->
| Alternativa | Por qué se descartó |
|---|---|
| <opción B> | <razón> |

## Qué la resolvería
<!-- Solo preguntas -->
El dato, la persona, el experimento o la investigación que cerraría esta pregunta.

## Pendientes derivados
- [ ] <Tarea o duda que queda> → [[pregunta-...]] si aplica

## Actualizaciones
<!-- Brainme añade aquí los cambios con fecha en vez de reescribir la nota -->
- <AAAA-MM-DD>: <qué cambió y por qué>
