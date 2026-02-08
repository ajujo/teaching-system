# Especificación Detallada F2 — Ingesta de Libro + Outline

> **Fase:** F2
> **Objetivo:** Importar PDF/EPUB, extraer texto, normalizar y generar estructura de capítulos
> **Duración estimada:** 3-5 días

---

## Hitos de F2

| Hito | Descripción | Entregables |
|------|-------------|-------------|
| **Hito1** | Scaffolding del proyecto | Estructura carpetas, pyproject.toml, módulos vacíos |
| **Hito2** | Import básico + DB | `import-book` CLI, `book.json`, copia a `source/`, registro SQLite |
| **Hito3** | Extracción de texto | `pdf_extractor`, `epub_extractor`, `raw/content.txt`, `raw/pages/` |
| **Hito4** | Normalización | `text_normalizer`, `normalized/content.txt` |
| **Hito5** | Outline extraction | `outline_extractor`, `outline.json` |
| **Hito6** | Outline validation | `outline_validator`, edición manual con `--review` |

---

## Estructura de Carpetas por Libro

```
data/books/{book_id}/
├── book.json              # Metadatos del libro
├── source/                # Archivo original copiado
│   └── {filename}.pdf
├── raw/                   # Texto extraído sin procesar (Hito3)
│   ├── content.txt        # Texto completo
│   └── pages/             # 1 archivo por página
│       ├── page_001.txt
│       └── ...
├── normalized/            # Texto normalizado (Hito4)
│   └── content.txt
├── outline/               # Estructura detectada (Hito5)
│   └── outline.json
└── artifacts/             # Generados en fases posteriores
    ├── notes/
    ├── exercises/
    └── exams/
```

---

## Módulos de F2

```
src/core/
├── book_importer.py      # Coordinador de importación
├── pdf_extractor.py      # Extracción de PDF
├── epub_extractor.py     # Extracción de EPUB
├── text_normalizer.py    # Limpieza y normalización
├── outline_extractor.py  # Detección de estructura
└── outline_validator.py  # Corrección manual
```

---

## 1. `book_importer.py` — Coordinador de Importación

### Responsabilidades

- Detectar formato del archivo (PDF/EPUB)
- Orquestar extracción según formato
- Calcular hash SHA256 para deduplicación
- Generar `book.json` con metadatos
- Crear estructura de carpetas en `data/books/{book_id}/`
- Registrar libro en SQLite (`books` table)

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `file_path` | `Path` | Argumento CLI |
| `title` | `str \| None` | Argumento CLI opcional |
| `author` | `str \| None` | Argumento CLI opcional |
| `language` | `str` | Argumento CLI (`en`, `es`, `auto`) |
| `force` | `bool` | Flag para reimportación |

### Outputs (Hito2)

| Output | Tipo | Destino |
|--------|------|---------|
| `book.json` | JSON | `data/books/{book_id}/book.json` |
| `source/{file}` | Copia | `data/books/{book_id}/source/` |
| Registro DB | SQLite | Tabla `books` con status `imported` |

> **Nota:** La extracción de texto (`raw/content.txt`, `raw/pages/`) se realiza en Hito3.

### Criterios de Aceptación (Hito2)

- [ ] Detecta correctamente PDF vs EPUB
- [ ] Genera `book_id` como slug (`author-year-title`)
- [ ] Genera `book_uuid` (UUID v4) para trazabilidad interna
- [ ] Calcula SHA256 del archivo original
- [ ] Si `force=False` y SHA256 existe en DB, retorna error con book_id existente
- [ ] Copia archivo original a `data/books/{book_id}/source/`
- [ ] Crea estructura de carpetas completa
- [ ] `book.json` válido según schema de contratos
- [ ] Registro creado en SQLite con todos los campos requeridos

### Funciones Principales

```python
def import_book(
    file_path: Path,
    title: str | None = None,
    author: str | None = None,
    language: str = "auto",
    force: bool = False
) -> BookResult:
    """Importa un libro y retorna resultado con book_id."""

def _detect_format(file_path: Path) -> Literal["pdf", "epub"]:
    """Detecta formato por extensión y magic bytes."""

def _check_duplicate(sha256: str) -> str | None:
    """Retorna book_id si ya existe, None si es nuevo."""

def _generate_book_id(author: str, year: int | None, title: str) -> str:
    """Genera slug: author-year-title (lowercase, sin acentos, solo alphanum y guiones)."""

def _create_book_structure(book_id: str) -> Path:
    """Crea carpetas en data/books/{book_id}/"""
```

---

## 2. `pdf_extractor.py` — Extracción de PDF

### Responsabilidades

- Extraer texto de PDFs con texto seleccionable
- Extraer por página (para trazabilidad)
- Detectar idioma del contenido
- Extraer metadatos del PDF (título, autor si existen)
- Manejar PDFs protegidos o escaneados (error informativo)

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `file_path` | `Path` | Desde `book_importer` |
| `output_dir` | `Path` | Directorio `raw/` |

### Outputs

| Output | Tipo | Destino |
|--------|------|---------|
| `content.txt` | TXT | Texto completo concatenado |
| `pages/page_{N}.txt` | TXT | Texto por página |
| `metadata` | dict | Título, autor, páginas del PDF |

### Criterios de Aceptación

- [ ] Extrae texto de PDF con texto seleccionable
- [ ] Genera 1 archivo por página en `pages/`
- [ ] Detecta idioma con >90% confianza (usando langdetect)
- [ ] Retorna error claro para PDFs sin texto (escaneados)
- [ ] Retorna error claro para PDFs protegidos
- [ ] Extrae metadatos embebidos si existen

### Dependencias

```
pymupdf (fitz)  # Extracción de PDF - mejor que PyPDF2
langdetect      # Detección de idioma
```

### Funciones Principales

```python
def extract_pdf(
    file_path: Path,
    output_dir: Path
) -> ExtractionResult:
    """Extrae texto de PDF, retorna resultado con metadatos."""

def _extract_page_text(doc: fitz.Document, page_num: int) -> str:
    """Extrae texto de una página específica."""

def _detect_language(text: str) -> str:
    """Detecta idioma del texto (ISO 639-1)."""

def _extract_pdf_metadata(doc: fitz.Document) -> dict:
    """Extrae metadatos embebidos del PDF."""
```

---

## 3. `epub_extractor.py` — Extracción de EPUB

### Responsabilidades

- Extraer texto de EPUB preservando estructura
- Mapear capítulos EPUB a archivos separados
- Extraer metadatos OPF (título, autor, etc.)
- Limpiar HTML a texto plano

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `file_path` | `Path` | Desde `book_importer` |
| `output_dir` | `Path` | Directorio `raw/` |

### Outputs

| Output | Tipo | Destino |
|--------|------|---------|
| `content.txt` | TXT | Texto completo |
| `chapters/ch_{N}.txt` | TXT | Texto por capítulo EPUB |
| `metadata` | dict | Título, autor, etc. |
| `toc.json` | JSON | Tabla de contenidos del EPUB |

### Criterios de Aceptación

- [ ] Extrae texto de EPUB válido
- [ ] Preserva orden de lectura (spine)
- [ ] Limpia HTML correctamente (sin tags residuales)
- [ ] Extrae TOC nativo si existe
- [ ] Detecta idioma del contenido

### Dependencias

```
ebooklib        # Lectura de EPUB
beautifulsoup4  # Limpieza de HTML
lxml            # Parser HTML
```

### Funciones Principales

```python
def extract_epub(
    file_path: Path,
    output_dir: Path
) -> ExtractionResult:
    """Extrae texto de EPUB, retorna resultado con metadatos."""

def _extract_chapter_text(item: epub.EpubItem) -> str:
    """Extrae texto limpio de un capítulo EPUB."""

def _parse_epub_toc(book: epub.EpubBook) -> list[dict]:
    """Extrae tabla de contenidos estructurada."""

def _html_to_text(html: str) -> str:
    """Convierte HTML a texto plano."""
```

---

## 4. `text_normalizer.py` — Limpieza y Normalización

### Responsabilidades

- Normalizar espacios en blanco y saltos de línea
- Corregir guiones de separación de palabras
- Detectar y marcar bloques de código
- Normalizar caracteres especiales
- Eliminar headers/footers repetitivos (paginación)

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `raw_text` | `str` | Desde extractores |
| `pages` | `list[str]` | Textos por página |
| `options` | `NormalizerOptions` | Configuración |

### Outputs

| Output | Tipo | Destino |
|--------|------|---------|
| `normalized_text` | `str` | Texto limpio |
| `normalized_pages` | `list[str]` | Páginas limpias |
| `stats` | dict | Estadísticas (chars removidos, etc.) |

### Criterios de Aceptación

- [ ] Remueve múltiples espacios/líneas vacías
- [ ] Une palabras separadas por guión al final de línea
- [ ] Detecta bloques de código y los preserva
- [ ] Normaliza encoding a UTF-8
- [ ] Remueve números de página aislados
- [ ] Preserva estructura de párrafos

### Funciones Principales

```python
def normalize_text(
    raw_text: str,
    options: NormalizerOptions = None
) -> NormalizedResult:
    """Aplica normalización completa al texto."""

def _fix_hyphenation(text: str) -> str:
    """Une palabras separadas por guión de fin de línea."""

def _detect_code_blocks(text: str) -> list[CodeBlock]:
    """Detecta bloques de código en el texto."""

def _remove_pagination(pages: list[str]) -> list[str]:
    """Detecta y remueve headers/footers repetitivos."""
```

---

## 5. `outline_extractor.py` — Detección de Estructura

### Responsabilidades

- Detectar capítulos y secciones del libro
- Usar heurísticas + LLM para detección
- Generar `outline.json` según schema
- Mapear páginas/posiciones a cada sección

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `book_id` | `str` | Desde `book_importer` |
| `content` | `str` | Texto normalizado |
| `pages` | `list[str]` | Páginas normalizadas |
| `toc` | `list[dict] \| None` | TOC de EPUB (si existe) |
| `method` | `str` | `auto`, `toc`, `headings`, `llm` |

### Outputs

| Output | Tipo | Destino |
|--------|------|---------|
| `outline.json` | JSON | `data/books/{book_id}/outline.json` |
| `confidence` | float | Confianza en la detección (0-1) |

### Criterios de Aceptación

- [ ] Detecta al menos 80% de capítulos correctamente en libros bien estructurados
- [ ] Usa TOC de EPUB cuando existe (alta confianza)
- [ ] Usa heurísticas de headings para PDF
- [ ] Fallback a LLM cuando heurísticas fallan
- [ ] Genera IDs jerárquicos según convención
- [ ] Mapea rangos de página a cada sección
- [ ] Retorna `confidence` para decidir si necesita revisión

### Métodos de Detección

1. **TOC (EPUB):** Usar tabla de contenidos nativa → confianza: 0.95
2. **Headings:** Detectar patrones ("Chapter X", "1.", "1.1") → confianza: 0.7-0.9
3. **LLM:** Enviar primeras páginas para que identifique estructura → confianza: 0.5-0.8

### Dependencias

```
# Para LLM
openai  # Cliente compatible con LM Studio
```

### Funciones Principales

```python
def extract_outline(
    book_id: str,
    content: str,
    pages: list[str],
    toc: list[dict] | None = None,
    method: str = "auto"
) -> OutlineResult:
    """Extrae estructura del libro y genera outline.json."""

def _extract_from_toc(toc: list[dict], book_id: str) -> Outline:
    """Convierte TOC de EPUB a outline."""

def _extract_from_headings(pages: list[str], book_id: str) -> Outline:
    """Detecta estructura por patrones de encabezados."""

def _extract_with_llm(content: str, book_id: str) -> Outline:
    """Usa LLM para detectar estructura."""

def _merge_methods(results: list[Outline]) -> Outline:
    """Combina resultados de múltiples métodos."""
```

---

## 6. `outline_validator.py` — Corrección Manual

### Responsabilidades

- Presentar outline en formato editable (YAML)
- Permitir corrección manual
- Validar outline editado contra schema
- Guardar outline corregido

### Inputs

| Input | Tipo | Fuente |
|-------|------|--------|
| `book_id` | `str` | Argumento CLI |
| `outline` | `Outline` | Desde `outline_extractor` |
| `interactive` | `bool` | Flag `--review` |

### Outputs

| Output | Tipo | Destino |
|--------|------|---------|
| `outline.json` | JSON | Actualizado tras edición |
| `validated` | bool | Si pasó validación |

### Criterios de Aceptación

- [ ] Genera YAML legible para edición
- [ ] Abre editor del sistema (`$EDITOR` o `nano`)
- [ ] Valida YAML editado contra schema
- [ ] Reporta errores de validación claramente
- [ ] Permite cancelar sin guardar (Ctrl+C)
- [ ] Actualiza `outline.json` solo si válido

### Funciones Principales

```python
def validate_outline(
    book_id: str,
    outline: Outline,
    interactive: bool = False
) -> ValidationResult:
    """Valida y opcionalmente permite edición del outline."""

def _to_editable_yaml(outline: Outline) -> str:
    """Convierte outline a YAML editable."""

def _from_yaml(yaml_str: str, book_id: str) -> Outline:
    """Parsea YAML editado a Outline."""

def _validate_schema(outline: Outline) -> list[str]:
    """Valida outline contra schema, retorna errores."""

def _open_editor(content: str) -> str:
    """Abre editor del sistema y retorna contenido editado."""
```

---

## 7. CLI Commands (F2)

### `import-book`

```python
# src/cli/commands.py

@app.command()
def import_book(
    file: Path = typer.Argument(..., help="Ruta al PDF o EPUB"),
    title: str = typer.Option(None, help="Título del libro"),
    author: str = typer.Option(None, help="Autor(es)"),
    language: str = typer.Option("auto", help="Idioma: en, es, auto"),
    force: bool = typer.Option(False, "--force", "-f", help="Reimportar")
):
    """Importa un libro PDF o EPUB al sistema."""
```

### `outline`

```python
@app.command()
def outline(
    book_id: str = typer.Argument(..., help="ID del libro"),
    method: str = typer.Option("auto", help="Método: auto, toc, headings, llm"),
    review: bool = typer.Option(False, help="Abrir para edición manual"),
    min_sections: int = typer.Option(3, help="Mínimo secciones por capítulo")
):
    """Extrae estructura de capítulos del libro."""
```

---

## Tests Manuales (Referencia Checklist E2E)

| Test ID | Descripción | Módulo Principal |
|---------|-------------|-----------------|
| 1.1 | Importar PDF válido | `book_importer`, `pdf_extractor` |
| 1.2 | Reimportar sin --force | `book_importer` |
| 1.3 | Reimportar con --force | `book_importer` |
| 2.1 | Extraer outline automático | `outline_extractor` |
| 2.2 | Outline con review manual | `outline_validator` |

### Comandos de Test

```bash
# Test 1.1
teach import-book ~/Books/test.pdf --title "Test" --language en
# Verificar: book.json existe, SQLite tiene registro

# Test 1.2
teach import-book ~/Books/test.pdf
# Verificar: Error "libro ya existe"

# Test 1.3
teach import-book ~/Books/test.pdf --title "Test v2" --force
# Verificar: Nuevo book_id generado

# Test 2.1
teach outline {book_id}
# Verificar: outline.json con capítulos

# Test 2.2
teach outline {book_id} --review
# Verificar: Se abre editor, cambios se guardan
```

---

## Dependencias de F2

```toml
# pyproject.toml - dependencies para F2

[project]
dependencies = [
    "pymupdf>=1.23.0",      # Extracción PDF
    "ebooklib>=0.18",       # Extracción EPUB
    "beautifulsoup4>=4.12", # Limpieza HTML
    "lxml>=4.9",            # Parser HTML
    "langdetect>=1.0.9",    # Detección idioma
    "typer>=0.9.0",         # CLI framework
    "rich>=13.0",           # Output formateado
    "pyyaml>=6.0",          # Edición de outline
    "pydantic>=2.0",        # Validación de schemas
    "openai>=1.0",          # Cliente LLM (LM Studio compatible)
]
```

---

## Orden de Implementación Recomendado

```
1. Setup proyecto (pyproject.toml, estructura)
     └──► 2. pdf_extractor.py
           └──► 3. epub_extractor.py
                 └──► 4. text_normalizer.py
                       └──► 5. book_importer.py (integra 2,3,4)
                             └──► 6. outline_extractor.py
                                   └──► 7. outline_validator.py
                                         └──► 8. CLI commands
                                               └──► 9. Tests E2E
```
