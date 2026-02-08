# Exam Generator Prompt — Generador de Exámenes

## Propósito

Este prompt genera **exámenes por capítulo** en modo estricto. Los exámenes evalúan la comprensión completa del capítulo y tienen mayor rigor que los ejercicios de práctica.

## Entradas Esperadas

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `{book_id}` | string | ID del libro |
| `{chapter_id}` | string | ID del capítulo |
| `{chapter_number}` | int | Número del capítulo |
| `{chapter_title}` | string | Título del capítulo |
| `{units_covered}` | list[dict] | Unidades del capítulo con sus objetivos |
| `{chapter_content}` | string | Contenido completo del capítulo |
| `{student_weak_tags}` | list[string] | Tags donde el estudiante falló en ejercicios |
| `{question_count}` | int | Número de preguntas (típicamente 10-20) |
| `{time_limit_minutes}` | int | Tiempo límite del examen |
| `{previous_exam_questions}` | list[string] | Preguntas de exámenes anteriores (evitar repetir) |

## Prompt

```
Eres un experto en evaluación educativa. Tu tarea es crear un examen riguroso pero justo para el capítulo "{chapter_title}" del libro.

## Contexto del Capítulo

**Número:** {chapter_number}
**Título:** {chapter_title}
**Unidades cubiertas:**
{units_covered}

## Reglas de Generación

1. **Cobertura completa**: El examen debe evaluar TODOS los objetivos de aprendizaje del capítulo

2. **Distribución de dificultad**:
   - 30% Easy: Comprensión básica, definiciones
   - 50% Medium: Aplicación, análisis
   - 20% Hard: Síntesis, evaluación crítica

3. **Distribución de tipos**:
   - 50-60% multiple_choice / true_false (corrección automática)
   - 30-40% short_answer (evaluación con LLM)
   - 10-20% code/practical si el contenido lo amerita

4. **Modo estricto**:
   - NO incluir hints en las preguntas
   - Las preguntas deben ser autoexplicativas
   - Evitar ambigüedades

5. **Énfasis en debilidades**: Incluir al menos 2 preguntas sobre estos tags débiles del estudiante:
   {student_weak_tags}

6. **NO repetir**: Evitar preguntas similares a exámenes anteriores:
   {previous_exam_questions}

7. **Tiempo**: El examen debe poder completarse en {time_limit_minutes} minutos
   - Regla: ~2 min por multiple_choice, ~4 min por short_answer, ~6 min por practical

## Contenido del Capítulo

{chapter_content}

## Formato de Salida (JSON Estricto)

```json
{
  "exam_id": "{book_id}:exam:ch:{chapter_number}",
  "chapter_id": "{chapter_id}",
  "generated_date": "[ISO 8601]",
  "mode": "strict",
  "time_limit_minutes": {time_limit_minutes},
  "questions": [
    {
      "question_id": "{exam_id}:q:1",
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "¿Cuál es la principal característica de...?",
      "options": [
        "Opción A",
        "Opción B",
        "Opción C",
        "Opción D"
      ],
      "correct_answer": 2,
      "points": 1,
      "source_units": ["{book_id}:unit:5"],
      "tags": ["concepto1"]
    },
    {
      "question_id": "{exam_id}:q:2",
      "type": "short_answer",
      "difficulty": "medium",
      "question": "Explica la diferencia entre X e Y en el contexto de...",
      "options": null,
      "correct_answer": "Respuesta modelo: X se caracteriza por... mientras que Y...",
      "points": 2,
      "source_units": ["{book_id}:unit:6", "{book_id}:unit:7"],
      "tags": ["concepto2", "concepto3"]
    },
    {
      "question_id": "{exam_id}:q:3",
      "type": "practical",
      "difficulty": "hard",
      "question": "Dado el siguiente escenario... diseña una solución que...",
      "options": null,
      "correct_answer": {
        "key_elements": ["elemento1", "elemento2", "elemento3"],
        "rubric": ["Identifica el problema", "Propone solución viable", "Justifica decisiones"]
      },
      "points": 3,
      "source_units": ["{book_id}:unit:8"],
      "tags": ["concepto4", "aplicacion"]
    }
  ],
  "total_points": 15,
  "passing_score": 0.6,
  "grading_rubric": {
    "partial_credit": false,
    "penalty_wrong": 0.0
  }
}
```

## Verificación

Antes de generar, verifica:

- [ ] Todas las unidades del capítulo tienen al menos 1 pregunta
- [ ] Los puntos suman correctamente
- [ ] La distribución de dificultad es aproximadamente 30/50/20
- [ ] El tiempo estimado no excede el límite
- [ ] Las preguntas son claras y no ambiguas

```

## Formato de Salida

**JSON estricto** siguiendo el schema `exam.json` de los contratos.

## Reglas de Comportamiento

1. **NUNCA** crear preguntas cuya respuesta no esté en el material del capítulo
2. **NUNCA** incluir hints o pistas dentro de las preguntas
3. **SIEMPRE** cubrir todos los objetivos de aprendizaje del capítulo
4. **SIEMPRE** incluir `source_units` para trazabilidad
5. **IMPORTANTE**: Las preguntas difíciles deben ser desafiantes pero justas
6. El `correct_answer` para practical/code debe incluir la rúbrica de evaluación
