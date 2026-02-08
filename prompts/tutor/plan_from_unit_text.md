# Plan From Unit Text Prompt (F8.3)

Genera un plan de enseñanza a partir del texto de una unidad cuando no hay estructura clara.

## Input
Texto de la unidad (puede ser desestructurado)

## Output
JSON con estructura:
```json
{
  "objective": "Al terminar, el estudiante podrá...",
  "points": [
    {"number": 1, "title": "Título breve del punto", "summary": "1-2 frases de qué cubre"},
    {"number": 2, "title": "...", "summary": "..."}
  ]
}
```

## Reglas

- Genera entre 4 y 6 puntos (MÁXIMO 6)
- Cada título debe ser conciso (3-6 palabras)
- Ordena los puntos de forma pedagógica (de simple a complejo)
- El objetivo debe empezar con "Al terminar..." o "Después de esta unidad..."
- NO inventes contenido que no esté en el texto original
- Si el texto es muy corto, genera menos puntos

## Ejemplo

Input: "Los transformers usan atención para procesar secuencias. La atención permite ver todas las palabras a la vez. Los embeddings convierten palabras en números..."

Output:
```json
{
  "objective": "Al terminar, el estudiante comprenderá cómo los transformers procesan texto usando atención.",
  "points": [
    {"number": 1, "title": "Embeddings y representación", "summary": "Cómo se convierten las palabras en vectores numéricos"},
    {"number": 2, "title": "Mecanismo de atención", "summary": "Cómo el modelo relaciona todas las palabras entre sí"},
    {"number": 3, "title": "Arquitectura transformer", "summary": "Cómo se combinan estos componentes"}
  ]
}
```
