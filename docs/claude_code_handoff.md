# Tabla de Handoff a Claude Code

> **Propósito:** Definir exactamente cuándo pasar de Antigravity Opus 4.5 a Claude Code, qué tipo de trabajo corresponde a cada uno, y qué input dar a Claude Code.

---

## Regla General

| Herramienta | Usar Para |
|-------------|-----------|
| **Antigravity Opus 4.5** | Diseño, arquitectura, prompts, contratos, especificaciones, revisión de código |
| **Claude Code** | Implementación de módulos, tests, refactoring, debugging, código repetitivo |

---

## Tabla de Handoff por Tarea

### Fase F2: Ingesta de Libro + Outline

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| Setup proyecto (pyproject.toml, estructura) | F2.1 | **Claude Code** | Creación de archivos de configuración y estructura | *Ver instrucciones abajo* |
| `pdf_extractor.py` | F2.2 | **Claude Code** | Implementación de módulo con pymupdf | *Ver instrucciones abajo* |
| `epub_extractor.py` | F2.3 | **Claude Code** | Implementación de módulo con ebooklib | *Ver instrucciones abajo* |
| `text_normalizer.py` | F2.4 | **Claude Code** | Implementación de funciones de limpieza | *Ver instrucciones abajo* |
| `book_importer.py` | F2.5 | **Claude Code** | Integración de extractores | *Ver instrucciones abajo* |
| `outline_extractor.py` (heurísticas) | F2.5 | **Claude Code** | Implementación de detección por patrones | *Ver instrucciones abajo* |
| `outline_extractor.py` (prompt LLM) | F2.5 | **Opus 4.5** | Diseño de prompt para detección de estructura | Crear `prompts/outline_extractor_prompt.md` |
| `outline_validator.py` | F2.6 | **Claude Code** | Implementación de edición interactiva | *Ver instrucciones abajo* |
| CLI commands F2 | F2.7 | **Claude Code** | Implementación de comandos typer | *Ver instrucciones abajo* |
| Tests unitarios F2 | F2.7 | **Claude Code** | Implementación de tests pytest | *Ver instrucciones abajo* |

---

### Fase F3: Segmentación Pedagógica

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| `unit_planner.py` | F3.1 | **Claude Code** | Implementación de segmentación | Spec de módulo + schema `units.json` |
| Prompt para planificación | F3.1 | **Opus 4.5** | Diseño de prompt pedagógico | Crear `prompts/unit_planner_prompt.md` |
| CLI `plan` | F3.4 | **Claude Code** | Implementación de comando | CLI spec + módulo |

---

### Fase F4: Teacher + Notes

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| `llm_client.py` | F4.2 | **Claude Code** | Implementación cliente LM Studio | Configuración de conexión |
| Revisión de prompts teacher/notes | F4.x | **Opus 4.5** | Ajuste fino de prompts pedagógicos | Prompts existentes + feedback de tests |
| `notes_generator.py` | F4.1 | **Claude Code** | Implementación de generación | Prompt + template + schema |
| `study_session.py` | F4.3 | **Claude Code** | Implementación de chat interactivo | Prompt teacher + flujo CLI |

---

### Fase F5: Ejercicios

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| `exercise_generator.py` | F5.1 | **Claude Code** | Implementación de generación | Prompt + schema |
| `grader.py` (práctica) | F5.2 | **Claude Code** | Implementación de corrección | Prompt + schema |
| Ajuste de prompts grader | F5.x | **Opus 4.5** | Refinamiento de evaluación | Ejemplos de respuestas + feedback |
| Repositorio SQLite | F5.3 | **Claude Code** | Implementación de persistencia | DDL de contratos |

---

### Fase F6: Exámenes

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| `exam_generator.py` | F6.1 | **Claude Code** | Implementación de generación | Prompt + schema |
| `exam_grader.py` | F6.3 | **Claude Code** | Implementación de corrección estricta | Prompt + schema |
| Flujo de examen (temporizador) | F6.2 | **Claude Code** | Implementación de modo estricto | CLI spec + flujo |
| Revisión prompts de examen | F6.x | **Opus 4.5** | Ajuste de rigor | Prompts + ejemplos |

---

### Fase F7: LangGraph + API

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| Implementación de nodos | F7.1 | **Claude Code** | Código de cada nodo del grafo | LangGraph design doc |
| Configuración de grafo | F7.1 | **Claude Code** | Wiring de transiciones | LangGraph design doc |
| Checkpoints/persistencia | F7.2 | **Claude Code** | Implementación de estado | LangGraph docs oficiales |
| API REST (FastAPI) | F7.4 | **Claude Code** | Implementación de endpoints | CLI spec (mismos comandos) |
| Revisión de lógica de `next` | F7.x | **Opus 4.5** | Validación de políticas | Grafo + tests manuales |

---

### Fase F8: AnythingLLM

| Tarea | Fase | Herramienta | Motivo | Input para Claude Code |
|-------|------|-------------|--------|------------------------|
| Plugin AnythingLLM | F8.1 | **Claude Code** | Implementación de integración | API spec + docs AnythingLLM |
| Documentación de integración | F8.x | **Opus 4.5** | Creación de guía de usuario | Sistema funcionando |

---

## Instrucciones Específicas para Claude Code (F2)

### F2.1: Setup Proyecto

```
TAREA: Crear estructura base del proyecto Python para el sistema de enseñanza.

INPUT:
- Leer: docs/contracts_v1.md (estructura de carpetas)
- Leer: docs/f2_spec.md (dependencias)
- Entorno conda: sistema_ensenianza

CREAR:
1. pyproject.toml con dependencias de F2
2. Estructura de carpetas según contracts_v1.md
3. __init__.py en todos los paquetes
4. src/core/__init__.py con imports
5. .env.example con configuración LLM

VERIFICAR:
- pip install -e . funciona sin errores
- import teaching no falla

NO IMPLEMENTAR: ningún módulo aún, solo estructura
```

---

### F2.2: pdf_extractor.py

```
TAREA: Implementar módulo de extracción de texto de PDFs.

INPUT:
- Leer: docs/f2_spec.md → sección pdf_extractor.py
- Leer: docs/contracts_v1.md → schema book.json

IMPLEMENTAR:
1. Función extract_pdf() según spec
2. Función _extract_page_text()
3. Función _detect_language()
4. Función _extract_pdf_metadata()
5. Dataclass ExtractionResult

DEPENDENCIAS: pymupdf, langdetect

CRITERIOS DE ACEPTACIÓN:
- Extrae texto de PDF con texto seleccionable
- Genera 1 archivo por página en pages/
- Detecta idioma con >90% confianza
- Retorna error claro para PDFs sin texto
- Retorna error claro para PDFs protegidos

TEST MANUAL:
- Usar un PDF de prueba con texto
- Verificar que se genera content.txt y pages/*.txt
```

---

### F2.3: epub_extractor.py

```
TAREA: Implementar módulo de extracción de texto de EPUBs.

INPUT:
- Leer: docs/f2_spec.md → sección epub_extractor.py
- Leer: docs/contracts_v1.md → schema book.json

IMPLEMENTAR:
1. Función extract_epub() según spec
2. Función _extract_chapter_text()
3. Función _parse_epub_toc()
4. Función _html_to_text()
5. Dataclass ExtractionResult (compartida con pdf)

DEPENDENCIAS: ebooklib, beautifulsoup4, lxml

CRITERIOS DE ACEPTACIÓN:
- Extrae texto de EPUB válido
- Preserva orden de lectura (spine)
- Limpia HTML correctamente
- Extrae TOC nativo si existe

TEST MANUAL:
- Usar un EPUB de prueba
- Verificar que se genera content.txt y chapters/*.txt
- Verificar toc.json si el EPUB tiene TOC
```

---

### F2.4: text_normalizer.py

```
TAREA: Implementar módulo de normalización de texto.

INPUT:
- Leer: docs/f2_spec.md → sección text_normalizer.py

IMPLEMENTAR:
1. Función normalize_text() según spec
2. Función _fix_hyphenation()
3. Función _detect_code_blocks()
4. Función _remove_pagination()
5. Dataclass NormalizerOptions
6. Dataclass NormalizedResult

CRITERIOS DE ACEPTACIÓN:
- Remueve múltiples espacios/líneas vacías
- Une palabras separadas por guión
- Detecta y preserva bloques de código
- Normaliza encoding a UTF-8
- Remueve números de página aislados

TEST MANUAL:
- Pasar texto con guiones de fin de línea
- Verificar que palabras se unen correctamente
```

---

### F2.5: book_importer.py + outline_extractor.py

```
TAREA: Implementar coordinador de importación y extractor de outline.

INPUT:
- Leer: docs/f2_spec.md → secciones book_importer y outline_extractor
- Leer: docs/contracts_v1.md → schemas book.json, outline.json
- Leer: prompts/outline_extractor_prompt.md (cuando exista)

IMPLEMENTAR book_importer.py:
1. Función import_book() como coordinador
2. Función _detect_format()
3. Función _check_duplicate() (requiere SQLite)
4. Función _create_book_structure()
5. Generar book.json según schema
6. Registrar en tabla books

IMPLEMENTAR outline_extractor.py:
1. Función extract_outline()
2. Función _extract_from_toc() (para EPUB)
3. Función _extract_from_headings() (heurísticas)
4. Función _extract_with_llm() (llamada a LM Studio)
5. Generar outline.json según schema

DEPENDENCIA: Módulos pdf_extractor, epub_extractor, text_normalizer ya implementados

CRITERIOS DE ACEPTACIÓN:
- import_book genera book.json válido
- Detecta duplicados por SHA256
- outline genera IDs jerárquicos correctos
- Métodos de detección funcionan: toc, headings, llm

TEST MANUAL:
- teach import-book test.pdf --title "Test"
- teach outline {book_id}
- Verificar archivos generados y registro SQLite
```

---

### F2.6: outline_validator.py

```
TAREA: Implementar validador interactivo de outline.

INPUT:
- Leer: docs/f2_spec.md → sección outline_validator
- Leer: docs/contracts_v1.md → schema outline.json

IMPLEMENTAR:
1. Función validate_outline()
2. Función _to_editable_yaml()
3. Función _from_yaml()
4. Función _validate_schema()
5. Función _open_editor()

CRITERIOS DE ACEPTACIÓN:
- Genera YAML legible
- Abre editor del sistema ($EDITOR o nano)
- Valida contra schema tras edición
- Reporta errores claramente
- Permite cancelar (Ctrl+C)

TEST MANUAL:
- teach outline {book_id} --review
- Editar algo, guardar
- Verificar que outline.json se actualiza
```

---

### F2.7: CLI Commands + Tests

```
TAREA: Implementar comandos CLI de F2 y tests.

INPUT:
- Leer: docs/cli_spec_v1.md → comandos import-book, outline
- Leer: docs/e2e_test_checklist_v1.md → tests 1.1-2.2

IMPLEMENTAR CLI:
1. Comando import-book con todos los argumentos
2. Comando outline con todos los argumentos
3. Manejo de errores con mensajes claros
4. Output formateado con rich

IMPLEMENTAR TESTS (pytest):
1. test_import_pdf.py
2. test_import_epub.py
3. test_outline_extractor.py
4. test_text_normalizer.py

CRITERIOS DE ACEPTACIÓN:
- Tests 1.1, 1.2, 1.3, 2.1, 2.2 del checklist pasan
- CLI muestra ayuda correcta con --help
- Errores tienen exit codes correctos
```

---

## Resumen de Distribución

| Herramienta | Tareas Totales | Porcentaje |
|-------------|----------------|------------|
| Claude Code | ~35 | 80% |
| Opus 4.5 | ~9 | 20% |

**Opus 4.5 se usa para:**

- Diseño inicial (ya hecho)
- Creación/ajuste de prompts
- Revisión de lógica compleja
- Validación de arquitectura
- Debugging de problemas de diseño

**Claude Code se usa para:**

- Implementación de módulos
- Tests unitarios e integración
- Configuración de proyecto
- Código repetitivo
- Refactoring
