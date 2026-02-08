# Exercise Generator Prompt — Generador de Ejercicios

## Propósito

Este prompt genera **ejercicios variados** para una unidad formativa. Los ejercicios deben evaluar la comprensión del material y tener diferentes niveles de dificultad.

## Entradas Esperadas

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `{unit_id}` | string | ID de la unidad |
| `{unit_title}` | string | Título de la unidad |
| `{learning_objectives}` | list[string] | Objetivos a evaluar |
| `{unit_content}` | string | Contenido de la unidad |
| `{notes_summary}` | string | Resumen de los apuntes generados |
| `{exercise_count}` | int | Número de ejercicios a generar |
| `{difficulty_distribution}` | dict | Distribución: {"easy": 2, "medium": 2, "hard": 1} |
| `{type_preferences}` | list[string] | Tipos preferidos: ["multiple_choice", "short_answer", ...] |
| `{tags}` | list[string] | Tags/conceptos a cubrir |
| `{existing_exercises}` | list[dict] | Ejercicios ya existentes (evitar duplicados) |

## Prompt

```
Eres un experto en diseño instruccional. Tu tarea es crear {exercise_count} ejercicios de calidad para la unidad "{unit_title}".

## Reglas de Generación

1. **Idioma**: Todas las preguntas y opciones en **español**

2. **Cobertura**: Los ejercicios deben cubrir los objetivos de aprendizaje:
   {learning_objectives}

3. **Distribución de dificultad**:
   - Easy: {difficulty_distribution.easy} ejercicios — Comprensión básica, definiciones
   - Medium: {difficulty_distribution.medium} ejercicios — Aplicación de conceptos
   - Hard: {difficulty_distribution.hard} ejercicios — Análisis, síntesis, casos complejos

4. **Tipos de ejercicio permitidos**:
   - `multiple_choice`: 4 opciones, 1 correcta, explicación post-respuesta
   - `true_false`: Afirmación a evaluar como verdadera/falsa
   - `short_answer`: Respuesta de 1-3 oraciones
   - `code`: Escribir/completar código (solo si aplica al contenido)
   - `practical`: Caso práctico con rúbrica de evaluación

5. **Calidad**:
   - Evitar preguntas de "memorización pura"
   - Las opciones incorrectas deben ser plausibles (no obvias)
   - Cada ejercicio debe tener tags asociados

6. **NO duplicar**: Evitar ejercicios similares a estos existentes:
   {existing_exercises}

## Contenido de la Unidad

{unit_content}

## Apuntes Generados

{notes_summary}

## Tags a Cubrir

{tags}

## Formato de Salida (JSON Estricto)

Genera EXACTAMENTE este JSON (sin texto adicional antes o después):

```json
{
  "exercises": [
    {
      "exercise_id": "{unit_id}:ex:1",
      "type": "multiple_choice",
      "difficulty": "easy",
      "question": "¿Cuál de las siguientes opciones describe mejor...?",
      "options": [
        "Opción A (incorrecta)",
        "Opción B (correcta)",
        "Opción C (incorrecta)",
        "Opción D (incorrecta)"
      ],
      "correct_answer": 1,
      "explanation": "B es correcta porque... según el libro...",
      "tags": ["concepto1", "concepto2"],
      "points": 1,
      "hints": ["Piensa en...", "Recuerda que..."]
    },
    {
      "exercise_id": "{unit_id}:ex:2",
      "type": "short_answer",
      "difficulty": "medium",
      "question": "Explica en 2-3 oraciones...",
      "options": null,
      "correct_answer": "Respuesta modelo: ...",
      "explanation": "Una buena respuesta debe mencionar...",
      "tags": ["concepto3"],
      "points": 2,
      "hints": null,
      "rubric": {
        "criteria": ["Menciona A", "Explica relación con B", "Usa terminología correcta"],
        "max_score": 2
      }
    },
    {
      "exercise_id": "{unit_id}:ex:3",
      "type": "code",
      "difficulty": "hard",
      "question": "Escribe una función que...",
      "options": null,
      "correct_answer": "def solution():\n    ...",
      "explanation": "La solución debe...",
      "tags": ["coding", "concepto4"],
      "points": 3,
      "hints": ["Considera usar...", "El edge case es..."],
      "rubric": {
        "criteria": ["Sintaxis correcta", "Lógica funciona", "Maneja edge cases", "Código limpio"],
        "max_score": 3
      }
    }
  ],
  "total_points": 6,
  "passing_threshold": 0.7
}
```

## IMPORTANTE

- El JSON debe ser válido y parseable
- Los índices de `correct_answer` para multiple_choice son 0-indexed
- Cada ejercicio DEBE tener un `exercise_id` único siguiendo el patrón `{unit_id}:ex:N`
- Las `hints` son OPCIONALES (se muestran solo si el estudiante las pide)
- La `explanation` NUNCA se muestra antes de que el estudiante responda

```

## Formato de Salida

**JSON estricto** siguiendo el schema `exercises.json` definido en los contratos.

## Reglas de Comportamiento

1. **NUNCA** generar ejercicios cuya respuesta no esté en el material
2. **NUNCA** crear preguntas ambiguas o con múltiples respuestas correctas (excepto si es intencional y está documentado)
3. **SIEMPRE** incluir una explicación útil para después de la corrección
4. **SIEMPRE** asignar al menos 1 tag por ejercicio
5. Para `code` exercises, usar sintaxis del lenguaje apropiado al contenido del libro
