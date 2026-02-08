# Post-Failure Choice Prompt (F8.2.1)

Este prompt se usa cuando el estudiante agota sus intentos en una pregunta de comprensión.

## Contexto

El estudiante ha intentado {attempts} veces responder a una pregunta de verificación sin éxito.
La política de enseñanza permite {allow_advance_on_failure ? "avanzar sin entender completamente" : "requerir comprensión antes de continuar"}.

## Mensaje al estudiante

No pasa nada, este concepto es complejo. Puedes:

- **Avanzar**: Continuamos al siguiente punto. Volveremos a este concepto más adelante.
- **Repasar**: Te lo explico de otra manera.

{default_after_failure == "advance" ? "Recomendación: Avanzar y volver después." : "Recomendación: Repasar antes de continuar."}

## Respuestas aceptadas (F8.2.1)

El estudiante puede usar **lenguaje natural**, no solo A/R:

### Para avanzar:
- `a`, `avanzar`, `adelante`
- `avancemos`, `siguiente`, `continuar`, `sigamos`, `pasemos`
- `sí`, `vale`, `ok` (si default_after_failure == "advance")

### Para repasar:
- `r`, `repasar`, `repaso`
- `repite`, `explica mejor`, `más ejemplos`, `más lento`
- `no`, `espera`, `aún no`
- `sí`, `vale`, `ok` (si default_after_failure == "stay")

### Comandos globales:
- `apuntes`, `control`, `examen`, `stop` - funcionan siempre

### Enter vacío:
- Usa `default_after_failure` de la policy

## Notas de implementación

- **NUNCA** llama a `check_comprehension()` - es decisión de flujo, no evaluación conceptual.
- Usa `parse_post_failure_choice_response()` para interpretar la respuesta.
