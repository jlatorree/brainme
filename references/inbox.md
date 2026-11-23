# Procesar el inbox

**Terminado cuando:** `00_inbox/` quedó vacío y cada archivo dejó en notas lo que no se
puede volver a leer en él, o el informe dice por qué no dejó nada.

1. `brainme inbox`: lo que hay y el `origen` de cada archivo. Cada uno marcado "al
   lector" (largo, PDF, imagen) va al ayudante `brainme:lector`, todos a la vez. Si quedan
   más de 3 archivos, repártelos en subagentes generales que leen y devuelven las notas
   propuestas; las escribes tú, para que cada nota tenga un solo escritor.
2. Lee cada archivo (`brainme leer <archivo>`) y quédate con lo que cambia algo para el
   proyecto: datos, acuerdos, dudas.
3. Cada idea va a su nota (flujo Guardar), con el `origen` que dio `brainme inbox`. Si ya
   tiene nota, amplíala con una línea en `## Actualizaciones` que termina en
   `· origen: <origen>`. Lo que alguien propuso y nadie decidió es una pregunta abierta o
   un supuesto.
4. Saca cada archivo del inbox: `brainme procesado <archivo> ...` guarda los de texto con
   los originales. Uno con valor propio (un contrato, un Excel, un PDF) va con
   `--a 04_sources`, y su nota lo enlaza: `[[contrato.pdf]]`.
5. `brainme comprueba`.
6. Informa con una tabla corta (nota, carpeta, enlazada a) y, aparte, lo ambiguo y lo
   que no dejó notas.
