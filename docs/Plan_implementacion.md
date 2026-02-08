# Plan de Implementación - Teaching System

## Visión General

Teaching System transforma libros digitales en experiencias de aprendizaje interactivas mediante un pipeline de procesamiento en 7 fases.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARQUITECTURA GENERAL                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PDF/EPUB  ──►  Extracción  ──►  Estructura  ──►  Material  ──►  Tutoría  │
│                                                                              │
│   ┌─────┐      ┌─────────┐      ┌─────────┐      ┌────────┐      ┌───────┐ │
│   │ F2  │ ──►  │   F2    │ ──►  │   F3    │ ──►  │ F4-F6  │ ──►  │  F7   │ │
│   │Book │      │Extract  │      │ Units   │      │Content │      │Tutor  │ │
│   └─────┘      └─────────┘      └─────────┘      └────────┘      └───────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Mapa de Archivos

### Estructura de Directorios

```
Teaching System/
│
├── src/teaching/                    # CÓDIGO FUENTE PRINCIPAL
│   │
│   ├── __init__.py                  # Versión del paquete
│   │
│   ├── cli/                         # INTERFAZ DE LÍNEA DE COMANDOS
│   │   ├── __init__.py
│   │   └── commands.py              # 24 comandos CLI (~3500 líneas)
│   │                                # - TeachingState enum
│   │                                # - Todas las funciones de comando
│   │                                # - Helpers internos (_run_*, _show_*)
│   │
│   ├── core/                        # LÓGICA DE NEGOCIO
│   │   ├── __init__.py
│   │   │
│   │   │  # ═══ FASE 2: Importación ═══
│   │   ├── book_importer.py         # Importación de libros
│   │   │                            # - import_book()
│   │   │                            # - Genera book_id, book.json
│   │   │                            # - Registra en SQLite
│   │   │
│   │   ├── pdf_extractor.py         # Extracción de PDF
│   │   │                            # - extract_pdf()
│   │   │                            # - Usa PyMuPDF
│   │   │
│   │   ├── epub_extractor.py        # Extracción de EPUB
│   │   │                            # - extract_epub()
│   │   │                            # - Usa ebooklib
│   │   │
│   │   ├── text_normalizer.py       # Normalización de texto
│   │   │                            # - normalize_book()
│   │   │                            # - Limpia encoding, espacios
│   │   │
│   │   ├── outline_extractor.py     # Detección de capítulos
│   │   │                            # - extract_outline()
│   │   │                            # - 4 métodos: auto, toc, headings, llm
│   │   │
│   │   ├── outline_validator.py     # Validación de outline
│   │   │                            # - validate_and_apply_yaml()
│   │   │
│   │   │  # ═══ FASE 3: Segmentación ═══
│   │   ├── unit_planner.py          # Planificación de unidades
│   │   │                            # - generate_units()
│   │   │                            # - Heurísticas de partición
│   │   │
│   │   │  # ═══ FASE 4: Apuntes ═══
│   │   ├── notes_generator.py       # Generación de apuntes
│   │   │                            # - generate_notes()
│   │   │                            # - Usa LLM con prompts/notes_prompt.md
│   │   │
│   │   │  # ═══ FASE 5: Ejercicios ═══
│   │   ├── exercise_generator.py    # Generación de ejercicios
│   │   │                            # - generate_exercises()
│   │   │
│   │   ├── attempt_repository.py    # Almacenamiento de intentos
│   │   │                            # - submit_attempt()
│   │   │                            # - Persistencia SQLite
│   │   │
│   │   ├── grader.py                # Calificación de ejercicios
│   │   │                            # - grade_attempt()
│   │   │                            # - LLM para evaluación
│   │   │
│   │   │  # ═══ FASE 6: Exámenes ═══
│   │   ├── chapter_exam_generator.py # Generación de exámenes
│   │   │                            # - generate_chapter_exam()
│   │   │
│   │   ├── exam_attempt_repository.py # Almacenamiento exámenes
│   │   │                            # - submit_exam_attempt()
│   │   │
│   │   ├── exam_grader.py           # Calificación de exámenes
│   │   │                            # - grade_exam_attempt()
│   │   │
│   │   │  # ═══ FASE 7: Tutoría ═══
│   │   └── tutor.py                 # ORQUESTACIÓN PRINCIPAL (~1250 líneas)
│   │                                #
│   │                                # Dataclasses:
│   │                                # - TutorState, BookProgress
│   │                                # - StudentProfile, StudentsState
│   │                                # - TeachingPoint, TeachingPlan
│   │                                #
│   │                                # Funciones de Estado:
│   │                                # - load_students_state()
│   │                                # - save_students_state()
│   │                                # - Migración de formato legacy
│   │                                #
│   │                                # Funciones de Contenido:
│   │                                # - list_available_books_with_metadata()
│   │                                # - get_chapter_info()
│   │                                # - load_chapter_notes()
│   │                                #
│   │                                # Funciones Teaching-First:
│   │                                # - generate_teaching_plan()
│   │                                # - explain_point()
│   │                                # - check_comprehension()
│   │                                # - reexplain_with_analogy()
│   │                                # - detect_more_examples_intent()
│   │                                # - generate_more_examples()
│   │                                #
│   │                                # Prompts del Sistema:
│   │                                # - SYSTEM_PROMPT_EXPLAIN_POINT
│   │                                # - SYSTEM_PROMPT_CHECK_COMPREHENSION
│   │                                # - SYSTEM_PROMPT_REEXPLAIN
│   │                                # - SYSTEM_PROMPT_MORE_EXAMPLES
│   │
│   ├── llm/                         # CLIENTE LLM
│   │   ├── __init__.py
│   │   └── client.py                # Cliente unificado
│   │                                # - LLMClient class
│   │                                # - simple_chat(), simple_json()
│   │                                # - chat_stream()
│   │                                # - Soporta: lmstudio, openai, anthropic
│   │
│   ├── db/                          # BASE DE DATOS
│   │   ├── __init__.py
│   │   ├── database.py              # Esquema SQLite
│   │   │                            # - init_db()
│   │   │                            # - Tabla: books
│   │   │
│   │   └── books_repository.py      # CRUD de libros
│   │                                # - insert_book()
│   │                                # - get_book_by_id()
│   │                                # - update_book_status()
│   │
│   └── utils/                       # UTILIDADES
│       ├── __init__.py
│       ├── validators.py            # Validación de IDs
│       │                            # - resolve_book_id()
│       │                            # - get_available_book_ids()
│       │
│       └── text_utils.py            # Utilidades de texto
│                                    # - strip_think()
│                                    # - strip_think_streaming()
│                                    # - ThrottledStreamer class
│
├── data/                            # DATOS DE USUARIO
│   │
│   ├── books/                       # Libros importados
│   │   └── {book_id}/               # Por cada libro:
│   │       ├── book.json            #   Metadatos
│   │       ├── source/              #   Archivo original
│   │       ├── raw/                 #   Texto extraído
│   │       │   ├── content.txt
│   │       │   └── pages/           #   (PDF) o chapters/ (EPUB)
│   │       ├── normalized/          #   Texto normalizado
│   │       │   └── content.txt
│   │       ├── outline/             #   Estructura
│   │       │   └── outline.json
│   │       └── artifacts/           #   Contenido generado
│   │           ├── units/
│   │           │   └── units.json
│   │           ├── notes/
│   │           │   └── {unit_id}.md
│   │           ├── exercises/
│   │           ├── exams/
│   │           ├── exam_attempts/
│   │           └── exam_grades/
│   │
│   └── state/                       # Estado de sesiones
│       └── students_v1.json         # Multi-estudiante
│
├── db/                              # Base de datos SQLite
│   └── teaching.db
│
├── prompts/                         # PROMPTS DEL SISTEMA
│   ├── outline_extractor_prompt.md  # Detección de capítulos con LLM
│   ├── notes_prompt.md              # Generación de apuntes
│   ├── exercise_generator_prompt.md # Generación de ejercicios
│   ├── grader_prompt_practice.md    # Calificación de ejercicios
│   ├── exam_generator_prompt.md     # Generación de exámenes
│   ├── grader_prompt_exam.md        # Calificación de exámenes
│   └── teacher_prompt.md            # Modo tutoría
│
├── configs/                         # CONFIGURACIÓN
│   └── models.yaml                  # Config de LLM y sistema
│
├── tests/                           # TESTS (603 tests, 12K+ líneas)
│   ├── conftest.py                  # CURRENT_PHASE = 7
│   ├── test_safety.py
│   ├── f2/                          # Tests Fase 2
│   ├── f3/                          # Tests Fase 3
│   ├── f4/                          # Tests Fase 4
│   ├── f5/                          # Tests Fase 5
│   ├── f6/                          # Tests Fase 6
│   └── f7/                          # Tests Fase 7 (212 tests)
│       ├── conftest.py              # Fixtures de F7
│       ├── test_cli_tutor.py
│       ├── test_tutor_state_persistence.py
│       ├── test_multi_student.py
│       ├── test_teaching_plan.py
│       ├── test_teaching_commands.py
│       ├── test_teaching_flow_bugs.py
│       ├── test_streaming.py
│       ├── test_throttled_streaming.py
│       └── ...
│
├── docs/                            # DOCUMENTACIÓN
│   ├── Plan_implementacion.md       # Este archivo
│   ├── Walkthrough.md               # Tutorial
│   ├── phase_guardrails.md          # Asignación de fases
│   ├── contracts_v1.md              # Esquemas de datos
│   └── cli_spec_v1.md               # Especificación CLI
│
├── pyproject.toml                   # Configuración del proyecto
├── uv.lock                          # Lock de dependencias
├── .env.example                     # Plantilla de variables
└── README.md                        # Documentación principal
```

---

## Esquema de Datos

### Flujo de Datos por Fase

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FLUJO DE DATOS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ENTRADA          PROCESAMIENTO              SALIDA                          │
│  ════════         ═════════════              ══════                          │
│                                                                              │
│  PDF/EPUB    ──►  book_importer     ──►     book.json                       │
│                   pdf_extractor              raw/content.txt                 │
│                   epub_extractor             raw/pages/*.txt                 │
│                                                                              │
│  raw/        ──►  text_normalizer   ──►     normalized/content.txt          │
│                                                                              │
│  normalized/ ──►  outline_extractor ──►     outline/outline.json            │
│                                                                              │
│  outline.json ─►  unit_planner      ──►     artifacts/units/units.json      │
│                                                                              │
│  units.json  ──►  notes_generator   ──►     artifacts/notes/{unit}.md       │
│                                                                              │
│  notes/*.md  ──►  exercise_generator ─►     artifacts/exercises/{unit}.json │
│                   grader                    attempts en SQLite               │
│                                                                              │
│  outline.json ─►  exam_generator    ──►     artifacts/exams/{chapter}.json  │
│                   exam_grader               exam_attempts, exam_grades       │
│                                                                              │
│  Todo lo     ──►  tutor.py          ──►     state/students_v1.json          │
│  anterior                                   (progreso multi-estudiante)      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Contratos de Datos (JSON Schemas)

#### book.json
```json
{
  "$schema": "book_v1",
  "book_id": "martin-2008-clean-code",
  "book_uuid": "uuid-v4",
  "title": "Clean Code",
  "authors": ["Robert Martin"],
  "language": "en",
  "source_format": "pdf",
  "total_pages": 464,
  "sha256": "hash-del-archivo"
}
```

#### outline.json
```json
{
  "$schema": "outline_v1",
  "book_id": "martin-2008-clean-code",
  "extraction_method": "headings",
  "chapters": [
    {
      "chapter_id": "martin-2008-clean-code:ch:01",
      "number": 1,
      "title": "Clean Code",
      "start_page": 1,
      "end_page": 25,
      "sections": [...]
    }
  ]
}
```

#### units.json
```json
{
  "$schema": "units_v2",
  "chapters": [
    {
      "chapter_number": 1,
      "units": [
        {
          "unit_id": "book-ch01-u01",
          "title": "Clean Code - Part 1",
          "pages": [1, 15],
          "estimated_time_min": 25
        }
      ]
    }
  ]
}
```

#### students_v1.json (Multi-estudiante)
```json
{
  "$schema": "students_v1",
  "active_student_id": "stu01",
  "students": [
    {
      "student_id": "stu01",
      "name": "Juan",
      "created_at": "2026-02-07T10:00:00Z",
      "updated_at": "2026-02-07T15:30:00Z",
      "tutor_state": {
        "active_book_id": "clean-code",
        "progress": {
          "clean-code": {
            "last_chapter_number": 3,
            "completed_chapters": [1, 2],
            "chapter_attempts": {}
          }
        },
        "user_name": "Juan"
      }
    }
  ]
}
```

---

## Máquina de Estados del Tutor

### Estados del Flujo Teaching-First

```python
class TeachingState(Enum):
    EXPLAINING = auto()      # Profesor explicando un punto
    WAITING_INPUT = auto()   # Esperando respuesta del estudiante
    CHECKING = auto()        # Evaluando comprensión
    AWAITING_RETRY = auto()  # Esperando segundo intento
    MORE_EXAMPLES = auto()   # Generando más ejemplos
    REMEDIATION = auto()     # Reexplicando con analogía
    NEXT_POINT = auto()      # Transición al siguiente punto
```

### Diagrama de Transiciones

```
                                    ┌──────────────────┐
                                    │                  │
                                    ▼                  │
┌────────────┐    explicación    ┌──────────────┐     │
│ EXPLAINING │ ─────────────────►│WAITING_INPUT │◄────┘
└────────────┘                   └──────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            "adelante"         respuesta normal      "más ejemplos"
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌────────────┐      ┌────────────┐      ┌─────────────┐
            │ NEXT_POINT │      │  CHECKING  │      │MORE_EXAMPLES│
            └────────────┘      └────────────┘      └─────────────┘
                    │                   │                   │
                    │           ┌───────┴───────┐           │
                    │           ▼               ▼           │
                    │      understood      NOT understood   │
                    │           │               │           │
                    │           ▼               ▼           │
                    │    ┌────────────┐  ┌──────────────┐   │
                    │    │ NEXT_POINT │  │AWAITING_RETRY│   │
                    │    └────────────┘  └──────────────┘   │
                    │                           │           │
                    │                    ┌──────┴──────┐    │
                    │                    ▼             ▼    │
                    │              understood    NOT again  │
                    │                    │             │    │
                    │                    ▼             ▼    │
                    │            ┌────────────┐ ┌───────────┐
                    │            │ NEXT_POINT │ │REMEDIATION│
                    │            └────────────┘ └───────────┘
                    │                                  │
                    │                                  │
                    ▼                                  ▼
               ┌─────────┐                     ┌──────────────┐
               │  break  │                     │WAITING_INPUT │
               │ (next)  │                     │  (reintentar)│
               └─────────┘                     └──────────────┘
```

### Flujo Detallado por Estado

```
1. EXPLAINING
   - Muestra título del punto
   - Llama a explain_point() con LLM
   - Extrae pregunta de verificación
   - Transición → WAITING_INPUT

2. WAITING_INPUT
   - typer.prompt() para leer input
   - Detecta comandos: stop, adelante, apuntes, control, examen
   - Detecta "más ejemplos" → MORE_EXAMPLES
   - Input normal → CHECKING

3. CHECKING
   - Llama a check_comprehension() con LLM
   - Si understood=True → "¡Perfecto!" → NEXT_POINT
   - Si understood=False → "Inténtalo de nuevo" → AWAITING_RETRY

4. AWAITING_RETRY (nuevo estado para evitar reexplicar sin input)
   - typer.prompt() para segundo intento
   - Misma lógica de comandos
   - Evalúa segundo intento
   - Si understood=True → NEXT_POINT
   - Si understood=False (2da vez) → REMEDIATION

5. MORE_EXAMPLES
   - Llama a generate_more_examples() con LLM
   - Actualiza pregunta de verificación
   - Transición → WAITING_INPUT (NO avanza)

6. REMEDIATION
   - Llama a reexplain_with_analogy() con LLM
   - Muestra analogía + pregunta reformulada
   - Transición → WAITING_INPUT

7. NEXT_POINT
   - break del while → siguiente punto en el for loop
```

---

## Dependencias Principales

### Runtime

| Paquete | Versión | Uso |
|---------|---------|-----|
| pymupdf | ≥1.23.0 | Extracción de PDF |
| ebooklib | ≥0.18 | Parsing de EPUB |
| beautifulsoup4 | ≥4.12 | Parsing HTML/XML |
| typer | ≥0.9.0 | Framework CLI |
| rich | ≥13.0 | Output formateado |
| pydantic | ≥2.0 | Validación de datos |
| openai | ≥1.0 | Cliente LLM |
| structlog | ≥23.0 | Logging estructurado |

### Desarrollo

| Paquete | Versión | Uso |
|---------|---------|-----|
| pytest | ≥7.0 | Testing |
| pytest-cov | ≥4.0 | Cobertura |
| ruff | ≥0.1.0 | Linter |
| mypy | ≥1.0 | Type checking |

---

## Fases de Implementación

### F2: Importación de Libros (Completado)
```
Módulos: book_importer, pdf_extractor, epub_extractor,
         text_normalizer, outline_extractor, outline_validator
Comandos: import-book, extract-raw, normalize, outline
Tests: tests/f2/ (4 archivos)
```

### F3: Segmentación en Unidades (Completado)
```
Módulos: unit_planner
Comandos: plan
Tests: tests/f3/ (2 archivos)
```

### F4: Generación de Apuntes (Completado)
```
Módulos: notes_generator, llm/client
Comandos: notes, start-unit
Tests: tests/f4/ (2 archivos)
```

### F5: Ejercicios y Calificación (Completado)
```
Módulos: exercise_generator, attempt_repository, grader
Comandos: exercise, quiz, submit, grade, review-grade
Tests: tests/f5/ (8 archivos)
```

### F6: Exámenes por Capítulo (Completado)
```
Módulos: chapter_exam_generator, exam_attempt_repository, exam_grader
Comandos: exam-quiz, exam-submit, exam-grade, exam-review
Tests: tests/f6/ (4 archivos)
```

### F7: Orquestación y Tutoría (Completado)
```
Módulos: tutor (principal)
Comandos: tutor, study, status, next
Features:
  - Multi-estudiante con Academia
  - Teaching-first mode
  - Máquina de estados robusta
  - Detección de "más ejemplos"
  - Soporte MCQ (a/b/c)
Tests: tests/f7/ (13 archivos, 212 tests)
```

### F8: Interfaz Gráfica (Planificado)
```
Estado: En backlog
Objetivo: UI web con AnythingLLM o similar
```

---

## Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Líneas de código (src/) | ~8,500 |
| Líneas de tests | ~12,500 |
| Total de tests | 603 |
| Comandos CLI | 24 |
| Archivos Python | 45+ |
| Fases completadas | 6/8 |

---

## Patrones de Diseño Utilizados

1. **Command Pattern**: Cada comando CLI es una función independiente
2. **State Machine**: Flujo de tutoría con estados explícitos
3. **Repository Pattern**: Separación de persistencia (db/, data/)
4. **Strategy Pattern**: Múltiples métodos de extracción de outline
5. **Factory Pattern**: LLMClient soporta múltiples providers
6. **Dataclass Pattern**: Estructuras de datos inmutables con validación

---

## Decisiones Técnicas Clave

### Por qué SQLite + JSON files?
- SQLite para datos relacionales (books, attempts)
- JSON files para datos jerárquicos (outline, units, state)
- Simplicidad y portabilidad sin servidor

### Por qué LM Studio como default?
- Gratuito y local
- Compatible con API de OpenAI
- No requiere internet
- Control total sobre el modelo

### Por qué máquina de estados para tutoría?
- Flujo predecible y testeable
- Evita bugs de "reexplicar sin esperar input"
- Fácil de extender con nuevos estados
- Claridad en transiciones

### Por qué prompts en archivos separados?
- Fácil iteración sin cambiar código
- Versionado independiente
- Documentación implícita
- Reutilización entre funciones
