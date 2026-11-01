---
titulo: "<Título del paper>"
tipo: literatura
cita: "<Apellido, N., y Apellido, N. (AAAA). Título. Revista, vol(núm), pp-pp.>"
autores: "<Apellido, N.; Apellido, N.>"
anio: <AAAA>
venue: "<revista o conferencia>"
doi: "<10.xxxx/xxxxx o sin DOI>"
# source_url: Graphify copia este campo a cada concepto que extrae de la nota,
# así cada respuesta del grafo lleva su link de origen.
source_url: "<https://doi.org/10.xxxx/xxxxx o enlace canónico>"
pdf: "<apellido-anio-palabra-clave.pdf si está guardado junto a la ficha, o no>"
peer_reviewed: <sí | no | preprint>
tipo_trabajo: <empírico | revisión sistemática | meta-análisis | teórico | fundacional>
metodo: "<diseño en pocas palabras: encuesta, experimento, caso, etnografía...>"
muestra: "<n = ... / corpus / contexto y país>"
citas: <número de citas a la fecha de consulta>
citas_fuente: "<Google Scholar | Semantic Scholar | Crossref>"
consultado: <AAAA-MM-DD>
leido: <completo | solo abstract>
retracciones: <ninguna | corregido | retractado>
fiabilidad: <alta | media | baja>
proyecto: "<nombre del proyecto>"
resumen: "<qué sostiene el paper, en una o dos frases>"
tags: [literatura, <tema>]
relacionadas: ["[[pregunta-o-decision-que-ilumina]]", "[[informe-que-lo-cita]]"]
---

<!--
Instrucciones de la plantilla (bórralas al crear la nota):
- Nombre del archivo: apellido-anio-palabra-clave.md (ej. vaswani-2017-transformer.md).
- Se llena con lo que devolvió el deep research (o con lo que leíste del PDF). Un dato
  que no está queda como "no reportado"; en "leido", si fue completo o solo el abstract.
- Cada dato y cada cita textual salen de la fuente, y el DOI responde 302 en doi.org.
- Quita todos los placeholders <...>.
-->

# <Título del paper>

**Cita:** <cita completa, formato APA 7>
**Enlace:** [<doi.org/10.xxxx/xxxxx>](<https://doi.org/10.xxxx/xxxxx>)

## Resumen (qué sostiene)
Dos a cuatro frases con la tesis central y el aporte principal.

## Método
Diseño, muestra o datos, contexto (país, sector, período) y cómo llegaron a sus
conclusiones. Anota el tamaño de muestra y cualquier límite metodológico.

## Hallazgos clave
- <Hallazgo 1, con el dato concreto si lo hay: efecto, porcentaje, n> (p. <n>)
- <Hallazgo 2> (p. <n>)
- <Hallazgo 3> (p. <n>)

## Límites y advertencias
- <Sesgos, alcance, qué tan generalizable es, críticas conocidas, correcciones o retracciones>

## Por qué entró en la selección
- **Validez:** <peer-reviewed, fuente primaria, método claro>
- **Impacto y actualidad:** <N citas, año; "fundacional" si es un clásico anterior a los últimos ~5 años>
- **Relevancia:** <qué pregunta o decisión del proyecto responde>

## Relevancia para el proyecto
Qué pregunta o decisión ilumina y cómo. Enlaza con [[...]] las preguntas,
decisiones, notas de conocimiento o informes que se apoyan en este paper.

## Citas textuales verificadas
> "<cita textual, corta y verificada contra el texto original>" (<Apellido>, <año>, p. <n>), [<doi.org/...>](<https://doi.org/...>)
