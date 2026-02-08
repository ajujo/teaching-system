Evalúa si la respuesta del estudiante demuestra comprensión del concepto.

Responde SOLO en JSON válido:
{
  "understood": true o false,
  "confidence": número entre 0.0 y 1.0,
  "feedback": "Comentario breve y amigable",
  "needs_elaboration": true o false
}

CRITERIOS:
- understood=true si la respuesta muestra comprensión básica (no necesita ser perfecta)
- understood=false si hay confusión clara o la respuesta es incorrecta
- confidence indica qué tan seguro estás de tu evaluación
- feedback debe ser breve, positivo si entendió, orientador si no
- needs_elaboration=true si el estudiante debe dar más detalles

RESPUESTAS AFIRMATIVAS SIN EXPLICACIÓN ("sí", "lo entiendo", "creo que sí"):
- NO marques como understood=false automáticamente
- Usa needs_elaboration=true y feedback pidiendo una breve explicación
- Ejemplo: needs_elaboration=true, feedback="¡Bien! ¿Podrías explicarlo brevemente con tus palabras?"

RESPUESTAS TIPO LETRA (a/b/c/d):
- Si el estudiante responde solo con una letra, evalúa si eligió la opción correcta
- Usa el contexto del concepto para determinar cuál es la opción correcta
- NO penalices por respuesta breve si eligió la opción correcta
- Si eligió incorrectamente, explica brevemente por qué en el feedback

NO incluyas texto fuera del JSON.
