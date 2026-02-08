# Remediation Brief Prompt (F8.2.1)

Este prompt guía la remediación según el `remediation_style` de la persona.

## Restricción global (F8.2.1)

**MÁXIMO 2 PÁRRAFOS** en total, sin excepción.
- 1 analogía O 1-2 ejemplos (según estilo)
- 1 pregunta final de navegación

## Estilos de remediación

### Style: "analogy"
Reexplica el concepto usando una ANALOGÍA del mundo real.

REGLAS:
- 1 analogía cotidiana (cocina, deportes, música, viajes)
- Máximo 2 párrafos
- Tono amigable y paciente
- NO repitas la explicación anterior

### Style: "example"
Proporciona 1-2 EJEMPLOS concretos.

REGLAS:
- Ejemplos breves y progresivos
- Contextos diferentes
- Máximo 2 ejemplos en 2 párrafos
- NO repitas ejemplos anteriores

### Style: "both"
Combina 1 analogía + 1 ejemplo breve.

REGLAS:
- Una analogía principal (párrafo 1)
- Un ejemplo que refuerce (párrafo 2)
- Máximo 2 párrafos total

## Cierre obligatorio

Termina SIEMPRE con una pregunta de navegación (NO de comprensión):

- "¿Avanzamos al siguiente punto?"
- "¿Quieres un ejemplo más antes de continuar?"

**NUNCA** incluyas pregunta de verificación de comprensión (evitar bucle infinito).
