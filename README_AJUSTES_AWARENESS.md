# Ajustes de Awareness integrado

El flujo integrado calcula por separado **AWA Marca** y **AWA Publicitario**. Cada perfil permite configurar TOM, espontáneo y ayudado con sus propias preguntas.

## Reglas de columnas y respuestas

- Al elegir un código como `CE1`, también se incluyen columnas hijas delimitadas como `CE1_1`, `CE1_2` o `CE1.1`.
- La coincidencia respeta límites de código: `A1` no incluye `A10` ni `A12`.
- Para TOM, cada persona aporta la primera respuesta no vacía (ni `0`) del grupo; si la columna principal está vacía, se usa la siguiente. Las menciones repetidas en otras columnas hermanas no vuelven a sumar.
- En espontáneo y ayudado se agrupan las columnas hermanas y se combinan sus menciones sin duplicar a una persona dentro del mismo indicador.
- Si una pregunta ya tiene una clasificación de marcas guardada, Awareness usa sus etiquetas categorizadas y correcciones en vez del texto original. Las respuestas vacías permanecen vacías.
- El cargador independiente reutiliza el mismo motor de detección y cálculo.

## Verificación

Se añadieron pruebas para los límites entre códigos, el orden de prioridad en TOM, las columnas divididas, la ausencia de doble conteo y el uso de etiquetas guardadas. Para ejecutarlas desde `backend/`, instala las dependencias de `requirements.txt` y corre:

```bash
PYTHONPATH=. python tests/test_awareness.py
PYTHONPATH=. python tests/test_awareness_flex.py
```
