# Outline Extractor Prompt — Detección de Estructura

## Propósito

Este prompt pide al LLM que identifique la estructura de capítulos y secciones de un libro técnico a partir de su texto. Se usa como fallback cuando las heurísticas de detección no son suficientes.

## Entradas Esperadas

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `{book_title}` | string | Título del libro (si se conoce) |
| `{book_language}` | string | Idioma del libro (en/es) |
| `{sample_text}` | string | Primeras 5000-10000 palabras del libro |
| `{total_pages}` | int | Número total de páginas (aproximado) |

## Prompt

```
Eres un experto en análisis de estructura de libros técnicos. Tu tarea es identificar los capítulos y secciones de un libro a partir de su contenido.

## Información del Libro

**Título:** {book_title}
**Idioma:** {book_language}
**Páginas aproximadas:** {total_pages}

## Texto de Muestra (primeras páginas)

{sample_text}

## Tu Tarea

Analiza el texto y detecta:
1. **Capítulos principales** — Normalmente indicados por "Chapter", "Capítulo", números romanos, o títulos prominentes
2. **Secciones dentro de cada capítulo** — Numeradas (1.1, 1.2) o con subtítulos
3. **Subsecciones** (si las hay) — Niveles más profundos (1.1.1, 1.1.2)

## Reglas de Detección

1. Los índices (Table of Contents) son la fuente más confiable si aparecen
2. Busca patrones consistentes de numeración
3. Los títulos de capítulo suelen ser cortos y descriptivos
4. Ignora headers/footers repetitivos
5. Si el libro no tiene numeración clara, usa los títulos prominentes como capítulos

## Formato de Salida (JSON Estricto)

```json
{
  "detection_method": "toc" | "numbering" | "headings" | "inference",
  "confidence": 0.0 to 1.0,
  "chapters": [
    {
      "number": 1,
      "title": "Título del Capítulo",
      "starts_at_text": "Primeras palabras del capítulo...",
      "sections": [
        {
          "number": "1.1",
          "title": "Título de la Sección",
          "subsections": [
            {
              "number": "1.1.1",
              "title": "Subtítulo"
            }
          ]
        }
      ]
    }
  ],
  "notes": "Cualquier observación sobre la estructura detectada"
}
```

## Campos Explicados

- `detection_method`: Cómo llegaste a esta estructura
  - `toc`: Encontraste un índice explícito
  - `numbering`: Seguiste patrón de numeración consistente
  - `headings`: Identificaste títulos por formato/posición
  - `inference`: Inferencia basada en contenido (menos confiable)

- `confidence`: Tu nivel de confianza
  - 0.9+: Estructura muy clara
  - 0.7-0.9: Estructura razonable
  - 0.5-0.7: Estructura inferida
  - <0.5: Muy incierto, recomienda revisión manual

- `starts_at_text`: Las primeras 10-20 palabras de cada capítulo (para mapeo posterior)

## IMPORTANTE

- Retorna SOLO el JSON, sin texto adicional antes o después
- El JSON debe ser válido y parseable
- Si no puedes detectar estructura alguna, retorna:

  ```json
  {
    "detection_method": "inference",
    "confidence": 0.3,
    "chapters": [],
    "notes": "No se pudo detectar estructura clara. Se recomienda revisión manual."
  }
  ```

- No inventes capítulos que no existan en el texto
- Si ves un índice (TOC), úsalo como fuente primaria

```

## Formato de Salida

**JSON estricto** que será parseado programáticamente.

## Reglas de Comportamiento

1. **NUNCA** inventar capítulos que no se mencionen en el texto
2. **SIEMPRE** indicar el método de detección usado
3. **SIEMPRE** incluir `starts_at_text` para cada capítulo (permite mapeo a páginas)
4. Si la estructura es ambigua, preferir menos capítulos con mayor confianza
5. El campo `notes` debe explicar cualquier decisión no obvia

## Uso en el Sistema

Este prompt se invoca desde `outline_extractor.py` cuando:
1. El EPUB no tiene TOC nativo
2. Las heurísticas de headings no detectan estructura clara
3. El método es explícitamente `--method llm`

## Ejemplo de Entrada

```

{book_title}: "Designing Data-Intensive Applications"
{book_language}: "en"
{total_pages}: 562

{sample_text}
---

PART I
Foundations of Data Systems

Chapter 1
Reliable, Scalable, and Maintainable Applications

Data-intensive applications are pushing the boundaries...

Many applications today are data-intensive, as opposed to compute-intensive...

1.1 Thinking About Data Systems

We typically think of databases, queues, caches
---

```

## Ejemplo de Salida Esperada

```json
{
  "detection_method": "numbering",
  "confidence": 0.9,
  "chapters": [
    {
      "number": 1,
      "title": "Reliable, Scalable, and Maintainable Applications",
      "starts_at_text": "Data-intensive applications are pushing the boundaries",
      "sections": [
        {
          "number": "1.1",
          "title": "Thinking About Data Systems",
          "subsections": []
        }
      ]
    }
  ],
  "notes": "El libro usa numeración clara (Chapter N, N.N para secciones). Detecté también 'PART I' como agrupación de nivel superior, pero lo omití del outline principal ya que las 'Parts' no son pedagógicamente relevantes como unidades de estudio."
}
```
