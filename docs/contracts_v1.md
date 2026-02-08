# Documento de Contratos v1 — Profesor LLM Personal

> **Versión:** 1.0  
> **Fecha:** 2026-01-28  
> **Estado:** Draft para revisión

---

## 1. Estructura de Carpetas del Proyecto

```
teaching-system/
├── .agent/
│   └── workflows/           # Workflows de desarrollo
├── src/
│   ├── __init__.py
│   ├── cli/                 # Comandos CLI
│   │   ├── __init__.py
│   │   └── commands.py
│   ├── core/                # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── book_importer.py
│   │   ├── outline_extractor.py
│   │   ├── unit_planner.py
│   │   ├── teacher.py
│   │   ├── exercise_generator.py
│   │   ├── grader.py
│   │   └── exam_generator.py
│   ├── graph/               # LangGraph orchestration
│   │   ├── __init__.py
│   │   ├── states.py
│   │   ├── nodes.py
│   │   └── graph.py
│   ├── db/                  # Persistencia SQLite
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── repository.py
│   ├── llm/                 # Integración con LLM
│   │   ├── __init__.py
│   │   ├── client.py        # LM Studio / Cloud
│   │   └── prompts.py       # Carga de prompts
│   └── utils/
│       ├── __init__.py
│       ├── text_utils.py
│       └── validators.py
├── prompts/                 # Prompts del sistema
│   ├── teacher_prompt.md
│   ├── notes_prompt.md
│   ├── exercise_generator_prompt.md
│   ├── grader_prompt_practice.md
│   ├── exam_generator_prompt.md
│   └── grader_prompt_exam.md
├── data/                    # Datos de libros importados
│   └── books/
│       └── {book_id}/
│           ├── book.json
│           ├── outline.json
│           ├── units.json
│           ├── raw/         # Texto extraído
│           └── artifacts/   # Apuntes, ejercicios generados
│               ├── notes/
│               ├── exercises/
│               └── exams/
├── db/
│   └── teaching.db          # SQLite principal
├── logs/
│   └── teaching.log
├── tests/
│   ├── __init__.py
│   ├── test_importer.py
│   ├── test_outline.py
│   ├── test_units.py
│   └── test_integration.py
├── pyproject.toml
├── requirements.txt
├── README.md
└── .env.example
```

---

## 2. Schemas JSON

### 2.1 `book.json` — Metadatos del libro importado

```json
{
  "$schema": "book_v1",
  "book_id": "string (slug: author-year-title)",
  "book_uuid": "string (UUID v4, interno)",
  "title": "string",
  "authors": ["string"],
  "language": "string (ISO 639-1: en, es, ...)",
  "source_file": "string (nombre archivo original)",
  "source_format": "pdf | epub",
  "import_date": "string (ISO 8601)",
  "total_pages": "integer | null",
  "total_chapters": "integer | null",
  "sha256": "string (hash del archivo original)",
  "metadata": {
    "publisher": "string | null",
    "year": "integer | null",
    "isbn": "string | null",
    "edition": "string | null"
  }
}
```

**Convención de `book_id` (slug):**

- Formato: `{author_apellido}-{year}-{title_slug}`
- Normalización: lowercase, solo alfanuméricos y guiones, sin acentos
- Ejemplos:
  - "Clean Code" de Robert Martin (2008) → `martin-2008-clean-code`
  - "DDIA" de Martin Kleppmann (2017) → `kleppmann-2017-designing-data-intensive`
- Si no hay año: `{author}-{title_slug}` (ej: `fowler-refactoring`)
- El slug es el nombre de la carpeta en `data/books/`

**Ejemplo:**

```json
{
  "book_id": "kleppmann-2017-designing-data-intensive",
  "book_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Designing Data-Intensive Applications",
  "authors": ["Martin Kleppmann"],
  "language": "en",
  "source_file": "ddia.pdf",
  "source_format": "pdf",
  "import_date": "2026-01-28T19:00:00Z",
  "total_pages": 562,
  "total_chapters": null,
  "sha256": "abc123def456...",
  "metadata": {
    "publisher": "O'Reilly",
    "year": 2017,
    "isbn": "978-1449373320",
    "edition": "1st"
  }
}
```

---

### 2.2 `outline.json` — Estructura de capítulos/secciones

```json
{
  "$schema": "outline_v1",
  "book_id": "string (ref → book.json)",
  "generated_date": "string (ISO 8601)",
  "chapters": [
    {
      "chapter_id": "string (book_id:ch:N)",
      "number": "integer",
      "title": "string",
      "start_page": "integer | null",
      "end_page": "integer | null",
      "sections": [
        {
          "section_id": "string (chapter_id:sec:M)",
          "number": "string (e.g., '1.2')",
          "title": "string",
          "start_page": "integer | null",
          "end_page": "integer | null",
          "subsections": [
            {
              "subsection_id": "string (section_id:sub:K)",
              "number": "string (e.g., '1.2.3')",
              "title": "string"
            }
          ]
        }
      ]
    }
  ]
}
```

**Convención de IDs jerárquicos:**

- Capítulo: `{book_id}:ch:1`
- Sección: `{book_id}:ch:1:sec:2`
- Subsección: `{book_id}:ch:1:sec:2:sub:3`

---

### 2.3 `units.json` — Unidades formativas planificadas

```json
{
  "$schema": "units_v1",
  "book_id": "string (ref → book.json)",
  "generated_date": "string (ISO 8601)",
  "total_units": "integer",
  "estimated_total_time_minutes": "integer",
  "units": [
    {
      "unit_id": "string ({book_id}:unit:N)",
      "number": "integer",
      "title": "string",
      "estimated_time_minutes": "integer (20-40)",
      "difficulty": "beginner | intermediate | advanced",
      "covers": {
        "chapters": ["string (chapter_id)"],
        "sections": ["string (section_id)"],
        "page_range": [start, end]
      },
      "prerequisites": ["string (unit_id)"],
      "learning_objectives": ["string"],
      "tags": ["string"],
      "status": "pending | in_progress | completed | skipped"
    }
  ]
}
```

**Reglas de segmentación:**

- Cada unidad: 20-40 minutos de estudio
- Una unidad puede cubrir partes de un capítulo o secciones completas
- Las unidades son secuenciales pero pueden tener dependencias explícitas

---

### 2.4 `notes.md` — Template fijo para apuntes

```markdown
# {unit_title}

> **Unidad:** {unit_number} de {total_units}  
> **Libro:** {book_title}  
> **Capítulo(s):** {chapters_covered}  
> **Tiempo estimado:** {estimated_time} min  
> **Generado:** {timestamp}

---

## 🎯 Objetivos de Aprendizaje

{learning_objectives_list}

---

## 📖 Contenido Principal

{main_content}

---

## 💡 Puntos Clave

{key_points_bullet_list}

---

## 🔗 Conexiones con Unidades Anteriores

{connections_or_none}

---

## 📝 Notas Auxiliares del Profesor

> ⚠️ Las siguientes explicaciones no provienen directamente del libro, sino que son aclaraciones adicionales.

{auxiliary_notes_if_any}

---

## ❓ Preguntas de Autoevaluación

{self_assessment_questions}
```

### 2.4.1 `notes_meta.json` — Metadatos del apunte (opcional, para indexación)

```json
{
  "$schema": "notes_meta_v1",
  "unit_id": "string",
  "generated_date": "string (ISO 8601)",
  "word_count": "integer",
  "reading_time_minutes": "integer",
  "key_concepts": ["string"],
  "auxiliary_content_percentage": "float (0.0-1.0)",
  "source_fidelity": "high | medium | low"
}
```

---

### 2.5 `exercise_set_v1` — Set de ejercicios por unidad (F5)

**Path:** `data/books/{book_id}/artifacts/exercises/{exercise_set_id}.json`

```json
{
  "$schema": "exercise_set_v1",
  "exercise_set_id": "string ({unit_id}-ex{NN})",
  "unit_id": "string (ref → units.json)",
  "book_id": "string",
  "created_at": "string (ISO 8601)",
  "provider": "lmstudio | openai | anthropic",
  "model": "string",
  "difficulty": "intro | mid | adv",
  "types": ["quiz", "practical", "mixed"],
  "generation_time_ms": "integer",
  "mode": "json | text_fallback | error",
  "pages_used": ["integer"],
  "exercises": [
    {
      "exercise_id": "string ({exercise_set_id}-q{NN})",
      "type": "multiple_choice | true_false | short_answer",
      "difficulty": "easy | medium | hard",
      "question": "string",
      "options": ["string"] | null,
      "correct_answer": "string | integer (0-3 for MC) | boolean (for TF)",
      "explanation": "string (mostrar SOLO después de calificación)",
      "points": "integer (default: 1)",
      "tags": ["string"]
    }
  ],
  "total_points": "integer",
  "passing_threshold": "float (0.0-1.0, default: 0.7)"
}
```

**ID determinístico:** `{unit_id}-ex{NN}` donde NN es el número secuencial.

Ejemplo: `paul-llm-engineer-s-handbook-ch01-u01-ex01`

**Tipos de ejercicio:**

| Tipo | Descripción | correct_answer |
|------|-------------|----------------|
| `multiple_choice` | Selección múltiple (4 opciones) | integer 0-3 |
| `true_false` | Verdadero/Falso | boolean |
| `short_answer` | Respuesta corta (texto libre) | string |

---

### 2.5.1 `attempt_v1` — Intento de respuesta (F5)

**Path:** `data/books/{book_id}/artifacts/attempts/{attempt_id}.json`

```json
{
  "$schema": "attempt_v1",
  "attempt_id": "string ({exercise_set_id}-a{NN})",
  "exercise_set_id": "string",
  "unit_id": "string",
  "book_id": "string",
  "created_at": "string (ISO 8601)",
  "status": "pending | graded",
  "answers": [
    {
      "exercise_id": "string",
      "response": "string | integer | boolean",
      "time_taken_seconds": "integer | null"
    }
  ],
  "total_questions": "integer"
}
```

**ID determinístico:** `{exercise_set_id}-a{NN}` donde NN es el número secuencial.

Ejemplo: `paul-llm-engineer-s-handbook-ch01-u01-ex01-a01`

---

### 2.5.2 `grade_report_v1` — Reporte de calificación (F5)

**Path:** `data/books/{book_id}/artifacts/grades/{attempt_id}.json`

```json
{
  "$schema": "grade_report_v1",
  "attempt_id": "string",
  "exercise_set_id": "string",
  "unit_id": "string",
  "book_id": "string",
  "graded_at": "string (ISO 8601)",
  "provider": "string",
  "model": "string",
  "mode": "auto | llm | mixed",
  "strict": "boolean",
  "grading_time_ms": "integer",
  "results": [
    {
      "exercise_id": "string",
      "is_correct": "boolean | null",
      "score": "float (0.0-1.0)",
      "feedback": "string",
      "expected_answer": "string",
      "given_answer": "string | null (opcional, respuesta del estudiante)",
      "correct_option_text": "string | null (opcional, solo MCQ)",
      "grading_path": "auto | llm",
      "confidence": "float (0.0-1.0) | null"
    }
  ],
  "summary": {
    "total_questions": "integer",
    "correct_count": "integer",
    "total_score": "float",
    "max_score": "float",
    "percentage": "float (0.0-1.0)",
    "passed": "boolean"
  }
}
```

**Modos de calificación:**

| Modo | Descripción |
|------|-------------|
| `auto` | Solo preguntas objetivas (MC, TF) |
| `llm` | Solo preguntas subjetivas (short_answer) |
| `mixed` | Combinación de auto y LLM |

---

### 2.6 `chapter_exam_set_v1` — Examen por capítulo (F6)

**Path:** `data/books/{book_id}/artifacts/exams/{exam_set_id}.json`

```json
{
  "$schema": "chapter_exam_set_v1",
  "exam_set_id": "string ({book_id}-ch{NN}-exam{XX})",
  "book_id": "string",
  "chapter_id": "string ({book_id}:ch:{N})",
  "chapter_number": "integer",
  "chapter_title": "string",
  "units_included": ["string (unit_id)"],
  "provider": "lmstudio | openai | anthropic",
  "model": "string",
  "created_at": "string (ISO 8601)",
  "generation_time_ms": "integer",
  "mode": "json | text_fallback",
  "difficulty": "intro | mid | adv",
  "total_points": "integer",
  "passing_threshold": "float (default: 0.6)",
  "pages_used": ["integer (sorted unique)"],
  "questions": [
    {
      "question_id": "string ({exam_set_id}-q{NN})",
      "type": "multiple_choice | true_false | short_answer",
      "difficulty": "easy | medium | hard",
      "question": "string",
      "options": ["string"] | null,
      "correct_answer": "integer (0-3 for MC) | boolean (for TF) | string (for SA)",
      "explanation": "string",
      "points": "integer",
      "tags": ["string"],
      "source": {
        "unit_id": "string",
        "pages": ["integer"],
        "section_ids": ["string"] | null,
        "rationale": "string (1 sentence explaining source)"
      }
    }
  ]
}
```

**ID determinístico:** `{book_id}-ch{NN}-exam{XX}` donde NN es el número de capítulo y XX es secuencial.

Ejemplo: `paul-llm-engineer-s-handbook-ch01-exam01`

**Diferencias con exercise_set_v1:**

| Aspecto | exercise_set_v1 | chapter_exam_set_v1 |
|---------|-----------------|---------------------|
| Alcance | Una unidad | Todo el capítulo |
| Umbral aprobación | 0.7 (70%) | 0.6 (60%) |
| Modo por defecto | Flexible | Estricto |
| Source tracking | No | Sí (unit_id + pages) |

---

### 2.6.1 `exam_attempt_v1` — Intento de examen (F6)

**Path:** `data/books/{book_id}/artifacts/exam_attempts/{exam_attempt_id}.json`

```json
{
  "$schema": "exam_attempt_v1",
  "exam_attempt_id": "string ({exam_set_id}-a{NN})",
  "exam_set_id": "string",
  "book_id": "string",
  "chapter_id": "string",
  "created_at": "string (ISO 8601)",
  "status": "submitted | graded",
  "answers": [
    {
      "question_id": "string",
      "response": "integer | boolean | string"
    }
  ],
  "total_questions": "integer"
}
```

**ID determinístico:** `{exam_set_id}-a{NN}` donde NN es el número secuencial.

Ejemplo: `paul-llm-engineer-s-handbook-ch01-exam01-a01`

---

### 2.6.2 `exam_grade_report_v1` — Reporte de calificación de examen (F6)

**Path:** `data/books/{book_id}/artifacts/exam_grades/{exam_attempt_id}.json`

```json
{
  "$schema": "exam_grade_report_v1",
  "exam_attempt_id": "string",
  "exam_set_id": "string",
  "book_id": "string",
  "chapter_id": "string",
  "graded_at": "string (ISO 8601)",
  "provider": "string",
  "model": "string",
  "mode": "auto | llm | mixed",
  "strict": "boolean (default: true)",
  "grading_time_ms": "integer",
  "results": [
    {
      "question_id": "string",
      "is_correct": "boolean | null",
      "score": "float (0.0-1.0)",
      "feedback": "string",
      "expected_answer": "string",
      "given_answer": "string | null",
      "correct_option_text": "string | null",
      "grading_path": "auto | llm",
      "confidence": "float | null",
      "source_unit_id": "string"
    }
  ],
  "summary": {
    "total_questions": "integer",
    "correct_count": "integer",
    "total_score": "float",
    "max_score": "float",
    "percentage": "float",
    "passed": "boolean",
    "by_unit": {
      "{unit_id}": {"score": "float", "max": "float"}
    },
    "by_type": {
      "multiple_choice": {"correct": "integer", "total": "integer"},
      "true_false": {"correct": "integer", "total": "integer"},
      "short_answer": {"correct": "integer", "total": "integer"}
    }
  }
}
```

**Diferencias con grade_report_v1:**

| Aspecto | grade_report_v1 | exam_grade_report_v1 |
|---------|-----------------|----------------------|
| Strict default | false | true |
| by_unit breakdown | No | Sí |
| by_type breakdown | No | Sí |
| source_unit_id | No | Sí |

---

### 2.7 `exam.json` — Examen por capítulo (LEGACY)

```json
{
  "$schema": "exam_v1",
  "exam_id": "string ({book_id}:exam:ch:N)",
  "chapter_id": "string (ref → outline.json)",
  "generated_date": "string (ISO 8601)",
  "mode": "strict",
  "time_limit_minutes": "integer",
  "questions": [
    {
      "question_id": "string ({exam_id}:q:M)",
      "type": "multiple_choice | true_false | short_answer | code | practical",
      "difficulty": "easy | medium | hard",
      "question": "string",
      "options": ["string"] | null,
      "correct_answer": "string | integer | object (NUNCA mostrar antes)",
      "points": "integer",
      "source_units": ["string (unit_id)"],
      "tags": ["string"]
    }
  ],
  "total_points": "integer",
  "passing_score": "float (0.0-1.0, default: 0.6)",
  "grading_rubric": {
    "partial_credit": "boolean (default: false)",
    "penalty_wrong": "float (0.0-1.0, default: 0.0)"
  }
}
```

**Reglas de examen (modo estricto):**

- No se muestran respuestas correctas hasta enviar todo el examen
- No hay pistas disponibles
- Tiempo límite obligatorio
- Penalización opcional por respuestas incorrectas

---

## 3. Tablas SQLite

### 3.1 Diagrama de Relaciones

```
┌──────────────────┐     ┌──────────────────┐
│  student_profile │     │      books       │
├──────────────────┤     ├──────────────────┤
│ student_id (PK)  │     │ book_id (PK)     │
│ name             │     │ book_uuid (UQ)   │
│ created_at       │     │ title, authors   │
│ preferences      │     │ sha256 (UQ)      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         │    ┌───────────────────┼───────────────────┐
         │    │                   │                   │
         ▼    ▼                   ▼                   ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│     progress     │   │     attempts     │   │   exam_results   │
├──────────────────┤   ├──────────────────┤   ├──────────────────┤
│ id (PK)          │   │ id (PK)          │   │ id (PK)          │
│ student_id (FK)  │   │ student_id (FK)  │   │ student_id (FK)  │
│ unit_id          │   │ exercise_id      │   │ exam_id          │
│ book_id (FK)     │   │ unit_id          │   │ chapter_id       │
│ status           │   │ response         │   │ score            │
│ score            │   │ is_correct       │   │ passed           │
│ completed_at     │   │ created_at       │   │ time_taken_sec   │
└──────────────────┘   └──────────────────┘   │ created_at       │
                                              └──────────────────┘
         │
         ▼
┌──────────────────┐   ┌──────────────────┐
│   corrections    │   │  skills_by_tag   │
├──────────────────┤   ├──────────────────┤
│ id (PK)          │   │ id (PK)          │
│ attempt_id (FK)  │   │ student_id (FK)  │
│ feedback         │   │ tag              │
│ score            │   │ proficiency      │
│ grader_mode      │   │ total_attempts   │
│ created_at       │   │ correct_attempts │
└──────────────────┘   │ last_updated     │
                       └──────────────────┘
```

### 3.2 DDL Completo

```sql
-- Tabla: student_profile
CREATE TABLE IF NOT EXISTS student_profile (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    preferences TEXT DEFAULT '{}',  -- JSON: {language, difficulty_preference, study_time_preference}
    notes TEXT
);

-- Tabla: books (registro local de libros importados)
-- sha256 es UNIQUE: un archivo solo puede tener un book_id
CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY,              -- Slug: author-year-title
    book_uuid TEXT UNIQUE,                 -- UUID v4 para trazabilidad interna
    title TEXT NOT NULL,
    authors TEXT,                          -- JSON array
    language TEXT NOT NULL DEFAULT 'en',   -- ISO 639-1
    source_format TEXT NOT NULL CHECK(source_format IN ('pdf', 'epub')),
    source_file TEXT NOT NULL,             -- Nombre archivo original
    source_path TEXT NOT NULL,             -- Ruta relativa a source/ dentro del book
    sha256 TEXT NOT NULL UNIQUE,           -- Hash para deduplicación
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    book_json_path TEXT NOT NULL,          -- Ruta al book.json
    status TEXT DEFAULT 'imported' CHECK(status IN ('imported', 'extracted', 'outlined', 'planned', 'active', 'completed'))
);

-- Tabla: progress (progreso por unidad)
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'skipped', 'needs_review')),
    score REAL,  -- 0.0 - 1.0
    time_spent_seconds INTEGER DEFAULT 0,
    notes_viewed_at TEXT,
    exercises_completed_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES student_profile(student_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id),
    UNIQUE(student_id, unit_id)
);

-- Tabla: attempts (intentos de ejercicios)
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    exercise_type TEXT NOT NULL,
    response TEXT NOT NULL,  -- JSON: respuesta del alumno
    is_correct INTEGER,  -- 0, 1, o NULL si pendiente de corrección
    score REAL,  -- Para ejercicios con puntuación parcial
    time_taken_seconds INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES student_profile(student_id)
);

-- Tabla: corrections (correcciones de ejercicios)
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    feedback TEXT NOT NULL,  -- Feedback del grader
    score REAL NOT NULL,  -- 0.0 - 1.0
    grader_mode TEXT NOT NULL CHECK(grader_mode IN ('auto', 'llm', 'manual')),
    rubric_scores TEXT,  -- JSON: puntuación por criterio (para practical/code)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (attempt_id) REFERENCES attempts(id)
);

-- Tabla: exam_results (resultados de exámenes por capítulo)
CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    exam_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    score REAL NOT NULL,  -- 0.0 - 1.0
    passed INTEGER NOT NULL,  -- 0 o 1
    time_taken_seconds INTEGER,
    responses TEXT NOT NULL,  -- JSON: {question_id: response}
    feedback TEXT,  -- Feedback general del examen
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES student_profile(student_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

-- Tabla: skills_by_tag (nivel de competencia por tag/concepto)
CREATE TABLE IF NOT EXISTS skills_by_tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    book_id TEXT,  -- NULL = global skill
    tag TEXT NOT NULL,
    proficiency REAL NOT NULL DEFAULT 0.0,  -- 0.0 - 1.0
    total_attempts INTEGER NOT NULL DEFAULT 0,
    correct_attempts INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT,
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES student_profile(student_id),
    UNIQUE(student_id, book_id, tag)
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_progress_student_book ON progress(student_id, book_id);
CREATE INDEX IF NOT EXISTS idx_attempts_student_unit ON attempts(student_id, unit_id);
CREATE INDEX IF NOT EXISTS idx_skills_student_tag ON skills_by_tag(student_id, tag);
CREATE INDEX IF NOT EXISTS idx_exam_results_student ON exam_results(student_id, book_id);
```

---

## 4. Convenciones de IDs

### 4.1 Formato General

| Entidad | Formato | Ejemplo |
|---------|---------|---------|
| Book | slug: `author-year-title` | `kleppmann-2017-designing-data-intensive` |
| Chapter | `{book_id}:ch:{N}` | `kleppmann-2017-designing-data-intensive:ch:1` |
| Section | `{chapter_id}:sec:{M}` | `kleppmann-2017-...:ch:1:sec:2` |
| Subsection | `{section_id}:sub:{K}` | `kleppmann-2017-...:ch:1:sec:2:sub:3` |
| Unit | `{book_id}:unit:{N}` | `kleppmann-2017-...:unit:5` |
| Exercise | `{unit_id}:ex:{N}` | `kleppmann-2017-...:unit:5:ex:3` |
| Exam | `{book_id}:exam:ch:{N}` | `kleppmann-2017-...:exam:ch:1` |
| Exam Question | `{exam_id}:q:{M}` | `kleppmann-2017-...:exam:ch:1:q:5` |
| Student | UUID v4 | `b2c3d4e5-f6a7-8901-bcde-f12345678901` |

### 4.2 Reglas

1. **Separador:** Usar `:` para jerarquía
2. **Numeración:** Comenzar en 1 (no 0)
3. **book_id:** Slug humano legible (`author-year-title`), usado como nombre de carpeta y PRIMARY KEY
4. **book_uuid:** UUID v4 interno para trazabilidad (no expuesto en CLI)
5. **student_id:** UUID v4 para entidad estudiante
6. **Inmutabilidad:** Los IDs no cambian una vez asignados
7. **Parseable:** Cualquier ID jerárquico puede descomponerse para obtener sus ancestros
8. **Resolución de prefijos:** El CLI acepta prefijos únicos (ej: `kleppmann` → `kleppmann-2017-designing-data-intensive`)

### 4.3 Funciones de Utilidad Requeridas

```python
def parse_id(entity_id: str) -> dict:
    """Descompone un ID jerárquico en sus componentes."""
    
def get_parent_id(entity_id: str) -> str | None:
    """Devuelve el ID del padre inmediato."""
    
def get_book_id(entity_id: str) -> str:
    """Extrae el book_id de cualquier ID jerárquico."""
```

---

## 5. Reglas de Logging

### 5.1 Configuración

```python
# Niveles de log
LOG_LEVELS = {
    "DEBUG": 10,    # Desarrollo, traza detallada
    "INFO": 20,     # Operaciones normales
    "WARNING": 30,  # Situaciones inesperadas pero manejables
    "ERROR": 40,    # Errores recuperables
    "CRITICAL": 50  # Errores fatales
}

# Formato estándar
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
```

### 5.2 Loggers por Módulo

| Logger | Descripción | Nivel Default |
|--------|-------------|---------------|
| `teaching.cli` | Comandos CLI | INFO |
| `teaching.core.importer` | Importación de libros | INFO |
| `teaching.core.outline` | Extracción de outline | INFO |
| `teaching.core.units` | Planificación de unidades | INFO |
| `teaching.core.teacher` | Generación de apuntes | INFO |
| `teaching.core.exercises` | Generación de ejercicios | INFO |
| `teaching.core.grader` | Corrección | INFO |
| `teaching.core.exam` | Exámenes | INFO |
| `teaching.graph` | Orquestación LangGraph | DEBUG |
| `teaching.llm` | Llamadas a LLM | DEBUG |
| `teaching.db` | Operaciones SQLite | WARNING |

### 5.3 Qué Loggear

**INFO:**

- Inicio/fin de operaciones principales
- Archivos importados/generados
- Cambios de estado del estudiante

**DEBUG:**

- Prompts enviados al LLM (truncados a 500 chars)
- Respuestas del LLM (truncadas)
- Decisiones del grafo LangGraph
- Queries SQL

**WARNING:**

- Fallback a comportamiento por defecto
- Datos faltantes o incompletos
- Reintentos de operaciones

**ERROR:**

- Fallos de parsing
- Errores de LLM
- Violaciones de constraints

**CRITICAL:**

- Base de datos corrupta
- Archivos esenciales faltantes

### 5.4 Rotación de Logs

```python
# Configuración de rotación
MAX_LOG_SIZE_MB = 10
BACKUP_COUNT = 5
LOG_RETENTION_DAYS = 30
```

---

## 6. Resumen de Iteración

### ✅ Qué se ha definido

1. **Estructura de carpetas** completa con separación clara de responsabilidades
2. **6 schemas JSON** con ejemplos y validación de tipos
3. **6 tablas SQLite** con DDL, constraints, índices y diagrama ER
4. **Convenciones de IDs** jerárquicas y parseables
5. **Reglas de logging** con niveles, formatos y rotación

### ⚠️ Qué falta

1. Especificación CLI (entregable 2)
2. Diseño del grafo LangGraph (entregable 3)
3. Prompts completos (entregable 4)
4. Checklist de pruebas E2E (entregable 5)

### 🚨 Riesgos Identificados

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Extracción de outline de PDF varía mucho según formato | Alto | Ofrecer corrección manual + heurísticas múltiples |
| Estimación de tiempo por unidad puede ser imprecisa | Medio | Ajustar con feedback del estudiante |
| Grading de respuestas abiertas depende de calidad del LLM | Alto | Definir rúbricas claras + opción de revisión manual |
| Tamaño de contexto del LLM puede no alcanzar para secciones largas | Medio | Segmentación + resúmenes intermedios |

### ➡️ Siguientes Pasos

1. **Revisar este documento** — ¿Cambios en schemas o estructura?
2. **Especificación CLI v1** — Definir comandos, argumentos y outputs
3. **Diseño LangGraph v1** — Estados, transiciones y políticas
