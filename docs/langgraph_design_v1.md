# Diseño del Grafo LangGraph v1 — Profesor LLM Personal

> **Versión:** 1.0  
> **Fecha:** 2026-01-28  
> **Estado:** Draft para revisión

---

## 1. Visión General

El sistema de enseñanza se orquesta mediante un **grafo de estados LangGraph** que gestiona el flujo pedagógico completo: desde la importación del libro hasta la certificación por capítulo.

### Principios de Diseño

1. **Determinismo primero**: Las transiciones críticas se basan en reglas, no en LLM
2. **LLM como herramienta**: El LLM genera contenido, no decide el flujo
3. **Estado persistente**: Todo cambio se refleja en SQLite/JSON
4. **Recuperabilidad**: Cualquier estado puede resumirse tras interrupción

---

## 2. Diagrama del Grafo Principal

```
                              ┌─────────────┐
                              │   START     │
                              └──────┬──────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │    IMPORT_BOOK        │
                         │  (Importar PDF/EPUB)  │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │   EXTRACT_OUTLINE     │
                         │  (Detectar capítulos) │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │     PLAN_UNITS        │
                         │  (Crear unidades)     │
                         └───────────┬───────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │                                │
                    ▼                                │
          ┌─────────────────┐                        │
          │  SELECT_UNIT    │◄───────────────────────┤
          │ (Elegir unidad) │                        │
          └────────┬────────┘                        │
                   │                                 │
                   ▼                                 │
          ┌─────────────────┐                        │
          │  GENERATE_NOTES │                        │
          │ (Crear apuntes) │                        │
          └────────┬────────┘                        │
                   │                                 │
                   ▼                                 │
          ┌─────────────────┐                        │
          │  STUDY_SESSION  │                        │
          │  (Explicación)  │◄──────┐                │
          └────────┬────────┘       │                │
                   │                │ (dudas)        │
                   ▼                │                │
          ┌─────────────────┐       │                │
          │GENERATE_EXERCISES│      │                │
          │ (Crear ejerc.)  │       │                │
          └────────┬────────┘       │                │
                   │                │                │
                   ▼                │                │
          ┌─────────────────┐       │                │
          │ EXERCISE_LOOP   │───────┘                │
          │(Ejercitar+Corr.)│                        │
          └────────┬────────┘                        │
                   │                                 │
                   ▼                                 │
          ┌─────────────────┐                        │
          │  EVALUATE_UNIT  │                        │
          │ (Decidir next)  │                        │
          └────────┬────────┘                        │
                   │                                 │
       ┌───────────┼───────────┬───────────┐         │
       ▼           ▼           ▼           ▼         │
   [refuerzo]  [siguiente]  [examen?]   [skip]       │
       │           │           │           │         │
       │           └───────────┼───────────┘         │
       │                       │                     │
       │                       ▼                     │
       │            ┌─────────────────┐              │
       │            │ CHECK_EXAM_READY│              │
       │            │(¿Listo p/examen)│              │
       │            └────────┬────────┘              │
       │                     │                       │
       │         ┌───────────┴───────────┐           │
       │         ▼                       ▼           │
       │  ┌─────────────┐         ┌─────────────┐    │
       │  │GENERATE_EXAM│         │ NEXT_UNIT   │────┘
       │  │(Crear exam.)│         └─────────────┘
       │  └──────┬──────┘
       │         │
       │         ▼
       │  ┌─────────────┐
       │  │  EXAM_LOOP  │
       │  │(Rendir exam)│
       │  └──────┬──────┘
       │         │
       │         ▼
       │  ┌─────────────┐
       │  │ GRADE_EXAM  │
       │  │(Corregir)   │
       │  └──────┬──────┘
       │         │
       │         ▼
       │  ┌─────────────┐
       │  │EVALUATE_EXAM│
       │  │(¿Aprobado?) │
       │  └──────┬──────┘
       │         │
       │    ┌────┴────┐
       │    ▼         ▼
       │ [pasó]    [falló]
       │    │         │
       │    │         └──────────────────────────┐
       │    ▼                                    │
       │ ┌─────────────┐                         │
       └─┤ NEXT_CHAPTER│                         │
         │(Sig. capít.)│◄────────────────────────┘
         └──────┬──────┘
                │
        ┌───────┴───────┐
        ▼               ▼
   [más caps.]     [completado]
        │               │
        │               ▼
        │        ┌─────────────┐
        │        │   FINISH    │
        │        │(Certificar) │
        │        └─────────────┘
        │
        └──────────► (vuelve a SELECT_UNIT)
```

---

## 3. Definición de Estados

### 3.1 Estado Global (GraphState)

```python
from typing import TypedDict, Literal, Optional
from datetime import datetime

class StudentContext(TypedDict):
    student_id: str
    name: str
    preferences: dict
    current_book_id: Optional[str]
    current_unit_id: Optional[str]
    current_chapter_id: Optional[str]

class UnitProgress(TypedDict):
    unit_id: str
    notes_generated: bool
    notes_viewed: bool
    exercises_generated: bool
    exercises_completed: int
    exercises_total: int
    score: Optional[float]
    status: Literal["pending", "in_progress", "completed", "needs_review"]

class ChapterProgress(TypedDict):
    chapter_id: str
    units_total: int
    units_completed: int
    exam_generated: bool
    exam_attempts: int
    exam_passed: bool
    best_score: Optional[float]

class GraphState(TypedDict):
    # Contexto del estudiante
    student: StudentContext
    
    # Libro activo
    book_id: Optional[str]
    book_title: Optional[str]
    
    # Progreso actual
    current_unit: Optional[UnitProgress]
    current_chapter: Optional[ChapterProgress]
    
    # Datos de sesión
    session_start: datetime
    last_action: str
    messages: list[dict]  # Historial de interacción
    
    # Artefactos generados en esta sesión
    pending_notes: Optional[str]
    pending_exercises: Optional[list]
    pending_exam: Optional[dict]
    
    # Decisiones del sistema
    next_action: Optional[str]
    recommendation: Optional[str]
    
    # Control de flujo
    error: Optional[str]
    should_continue: bool
```

---

## 4. Nodos del Grafo

### 4.1 Tabla de Nodos

| Nodo | Tipo | Entrada | Salida | Lee | Escribe |
|------|------|---------|--------|-----|---------|
| `import_book` | Función | archivo path | book.json | filesystem | data/books/{id}/, DB:books |
| `extract_outline` | LLM + Reglas | book.json, raw text | outline.json | book.json | outline.json |
| `plan_units` | LLM + Reglas | outline.json | units.json | outline.json | units.json |
| `select_unit` | Reglas | student progress | unit_id | DB:progress | state |
| `generate_notes` | LLM | unit content | notes.md | raw text, outline | artifacts/notes/ |
| `study_session` | LLM (chat) | notes, student query | response | notes.md | messages |
| `generate_exercises` | LLM | unit content, notes | exercises.json | raw text, notes | artifacts/exercises/ |
| `exercise_loop` | LLM + IO | exercise, student response | feedback | exercises.json | DB:attempts, corrections |
| `evaluate_unit` | Reglas | unit progress | decision | DB:attempts | DB:progress |
| `check_exam_ready` | Reglas | chapter progress | ready: bool | DB:progress | state |
| `generate_exam` | LLM | chapter content | exam.json | units, exercises | artifacts/exams/ |
| `exam_loop` | IO | exam, responses | completed exam | exam.json | state |
| `grade_exam` | LLM + Reglas | exam responses | scores | exam.json | DB:exam_results |
| `evaluate_exam` | Reglas | exam score | passed: bool | DB:exam_results | DB:progress, skills |
| `next_chapter` | Reglas | chapter list | next chapter_id | outline.json | state |

---

## 5. Transiciones y Políticas

### 5.1 Políticas Deterministas (Umbrales)

```python
# Umbrales de evaluación
THRESHOLDS = {
    # Ejercicios
    "exercise_pass_score": 0.7,       # 70% para aprobar unidad
    "exercise_retry_threshold": 0.5,   # <50% requiere refuerzo
    
    # Exámenes
    "exam_pass_score": 0.6,           # 60% para aprobar examen
    "exam_retry_delay_hours": 24,     # Espera mínima para reintentar
    
    # Proactividad
    "weak_tag_threshold": 0.6,        # Tag débil si <60%
    "suggest_review_after_days": 7,   # Sugerir repaso tras 7 días
    
    # Progresión
    "min_units_for_exam": 0.8,        # 80% unidades para habilitar examen
    "skip_unit_penalty": 0.1,         # Penalización por skip
}
```

### 5.2 Tabla de Transiciones

| Desde | Condición | Hacia | Acción |
|-------|-----------|-------|--------|
| `import_book` | success | `extract_outline` | - |
| `import_book` | error | `END` | Log error |
| `extract_outline` | success | `plan_units` | - |
| `plan_units` | success | `select_unit` | - |
| `select_unit` | unit available | `generate_notes` | Set current_unit |
| `select_unit` | all completed | `check_exam_ready` | - |
| `generate_notes` | success | `study_session` | Save notes |
| `study_session` | user: "continuar" | `generate_exercises` | - |
| `study_session` | user: pregunta | `study_session` | Answer + loop |
| `study_session` | user: "salir" | `evaluate_unit` | - |
| `generate_exercises` | success | `exercise_loop` | - |
| `exercise_loop` | all answered | `evaluate_unit` | Save attempts |
| `exercise_loop` | user: "saltar" | `evaluate_unit` | Mark skipped |
| `evaluate_unit` | score >= 0.7 | `select_unit` (next) | Mark completed |
| `evaluate_unit` | score < 0.5 | `generate_notes` (repeat) | Flag needs_review |
| `evaluate_unit` | 0.5 <= score < 0.7 | `exercise_loop` (retry weak) | - |
| `check_exam_ready` | >= 80% units done | `generate_exam` | - |
| `check_exam_ready` | < 80% units done | `select_unit` | Notify |
| `generate_exam` | success | `exam_loop` | - |
| `exam_loop` | completed | `grade_exam` | - |
| `exam_loop` | timeout | `grade_exam` | Mark incomplete |
| `grade_exam` | done | `evaluate_exam` | Save scores |
| `evaluate_exam` | passed | `next_chapter` | Update skills |
| `evaluate_exam` | failed | `select_unit` (weak units) | Recommend review |
| `next_chapter` | more chapters | `select_unit` | Reset chapter |
| `next_chapter` | book complete | `FINISH` | Generate certificate |

---

## 6. Lógica de Cada Nodo (Pseudocódigo)

### 6.1 `select_unit`

```python
def select_unit(state: GraphState) -> GraphState:
    """Selecciona la siguiente unidad a estudiar."""
    
    # 1. Cargar progreso del estudiante
    progress = db.get_progress(state["student"]["student_id"], state["book_id"])
    
    # 2. Filtrar unidades disponibles
    units = load_json(f"data/books/{state['book_id']}/units.json")
    
    # 3. Priorizar:
    #    a) Unidades marcadas como needs_review
    #    b) Unidades in_progress
    #    c) Siguiente unidad pendiente en orden
    
    for unit in units["units"]:
        unit_progress = progress.get(unit["unit_id"])
        
        if unit_progress and unit_progress["status"] == "needs_review":
            return {**state, "current_unit": unit, "recommendation": "Repaso recomendado"}
        
        if unit_progress and unit_progress["status"] == "in_progress":
            return {**state, "current_unit": unit}
        
        if not unit_progress or unit_progress["status"] == "pending":
            return {**state, "current_unit": unit}
    
    # Todas completas
    return {**state, "current_unit": None, "next_action": "check_exam_ready"}
```

### 6.2 `evaluate_unit`

```python
def evaluate_unit(state: GraphState) -> GraphState:
    """Evalúa el rendimiento en la unidad y decide siguiente acción."""
    
    unit_id = state["current_unit"]["unit_id"]
    
    # Obtener intentos de esta sesión
    attempts = db.get_attempts(state["student"]["student_id"], unit_id)
    
    if not attempts:
        # No hizo ejercicios
        return {**state, "next_action": "select_unit", "recommendation": "Continúa cuando quieras"}
    
    # Calcular score
    correct = sum(1 for a in attempts if a["is_correct"])
    total = len(attempts)
    score = correct / total if total > 0 else 0
    
    # Identificar tags débiles
    weak_tags = identify_weak_tags(attempts, threshold=0.6)
    
    # Actualizar progreso
    if score >= THRESHOLDS["exercise_pass_score"]:
        db.update_progress(unit_id, status="completed", score=score)
        next_action = "select_unit"
        recommendation = f"¡Excelente! Unidad completada con {score*100:.0f}%"
        
    elif score < THRESHOLDS["exercise_retry_threshold"]:
        db.update_progress(unit_id, status="needs_review", score=score)
        next_action = "generate_notes"  # Volver a estudiar
        recommendation = f"Score {score*100:.0f}%. Te recomiendo repasar el material."
        
    else:
        # Entre 50% y 70%: retry solo ejercicios fallados
        db.update_progress(unit_id, status="in_progress", score=score)
        next_action = "exercise_loop"
        recommendation = f"Score {score*100:.0f}%. Practiquemos los conceptos débiles: {weak_tags}"
    
    # Actualizar skills por tag
    update_skills_by_tag(state["student"]["student_id"], attempts)
    
    return {
        **state,
        "next_action": next_action,
        "recommendation": recommendation,
        "current_unit": {**state["current_unit"], "score": score}
    }
```

### 6.3 `check_exam_ready`

```python
def check_exam_ready(state: GraphState) -> GraphState:
    """Verifica si el estudiante puede rendir examen del capítulo."""
    
    chapter_id = state["current_chapter"]["chapter_id"]
    
    # Obtener unidades del capítulo
    units = get_units_for_chapter(state["book_id"], chapter_id)
    progress = db.get_progress_for_units(state["student"]["student_id"], units)
    
    completed = sum(1 for p in progress.values() if p["status"] == "completed")
    total = len(units)
    ratio = completed / total if total > 0 else 0
    
    if ratio >= THRESHOLDS["min_units_for_exam"]:
        # Verificar exámenes previos
        last_exam = db.get_last_exam_attempt(state["student"]["student_id"], chapter_id)
        
        if last_exam and not last_exam["passed"]:
            hours_since = hours_since_attempt(last_exam["created_at"])
            if hours_since < THRESHOLDS["exam_retry_delay_hours"]:
                return {
                    **state,
                    "next_action": "select_unit",
                    "recommendation": f"Espera {24-hours_since:.0f}h antes de reintentar el examen."
                }
        
        return {**state, "next_action": "generate_exam"}
    
    else:
        pending = total - completed
        return {
            **state,
            "next_action": "select_unit",
            "recommendation": f"Completa {pending} unidades más para habilitar el examen."
        }
```

---

## 7. Subgrafos

### 7.1 Subgrafo: Exercise Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXERCISE_LOOP SUBGRAPH                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│   │ SELECT   │────►│ PRESENT  │────►│  WAIT    │                │
│   │ EXERCISE │     │ QUESTION │     │ RESPONSE │                │
│   └──────────┘     └──────────┘     └────┬─────┘                │
│        ▲                                  │                      │
│        │                                  ▼                      │
│        │                           ┌──────────┐                  │
│        │                           │  GRADE   │                  │
│        │                           │ RESPONSE │                  │
│        │                           └────┬─────┘                  │
│        │                                │                        │
│        │           ┌────────────────────┼────────────────┐       │
│        │           ▼                    ▼                ▼       │
│        │     [más ejerc.]         [hint usado]      [correcto]   │
│        │           │                    │                │       │
│        │           │                    ▼                │       │
│        └───────────┤             ┌──────────┐            │       │
│                    │             │ SHOW_HINT│            │       │
│                    │             └────┬─────┘            │       │
│                    │                  │                  │       │
│                    └──────────────────┴──────────────────┘       │
│                                       │                          │
│                                       ▼                          │
│                                 ┌──────────┐                     │
│                                 │ SHOW_    │                     │
│                                 │ FEEDBACK │                     │
│                                 └────┬─────┘                     │
│                                      │                           │
│                              [todos hechos]                      │
│                                      │                           │
│                                      ▼                           │
│                                   (EXIT)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Subgrafo: Exam Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                       EXAM_LOOP SUBGRAPH                         │
│                       (MODO ESTRICTO)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐                                                   │
│   │  START   │─────► Timer iniciado                              │
│   │  TIMER   │                                                   │
│   └────┬─────┘                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│   │ PRESENT  │────►│  WAIT    │────►│  STORE   │                │
│   │ QUESTION │     │ RESPONSE │     │ RESPONSE │                │
│   └──────────┘     └────┬─────┘     └────┬─────┘                │
│        ▲                │                │                       │
│        │                │ (sin feedback) │                       │
│        │                ▼                │                       │
│        │         [timeout parcial]       │                       │
│        │                │                │                       │
│        └────────────────┴────────────────┘                       │
│                         │                                        │
│                 [¿más preguntas?]                                │
│                    │         │                                   │
│                   Sí        No / Timeout                         │
│                    │         │                                   │
│                    │         ▼                                   │
│                    │   ┌──────────┐                              │
│                    │   │ FINALIZE │                              │
│                    │   │   EXAM   │                              │
│                    │   └────┬─────┘                              │
│                    │        │                                    │
│                    │        ▼                                    │
│                    │     (EXIT)                                  │
│                    │                                             │
│                    └──────► (loop)                               │
│                                                                  │
│   REGLAS ESTRICTAS:                                              │
│   - NO feedback entre preguntas                                  │
│   - NO hints disponibles                                         │
│   - NO volver a preguntas anteriores                             │
│   - Timer global visible                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Integración con LLM y DB

### 8.1 Llamadas al LLM por Nodo

| Nodo | Prompt | Max Tokens | Temp | Structured? |
|------|--------|------------|------|-------------|
| `extract_outline` | `outline_extractor_prompt` | 4096 | 0.3 | JSON |
| `plan_units` | `unit_planner_prompt` | 4096 | 0.5 | JSON |
| `generate_notes` | `notes_prompt` | 8192 | 0.7 | Markdown |
| `study_session` | `teacher_prompt` | 2048 | 0.8 | Text |
| `generate_exercises` | `exercise_generator_prompt` | 4096 | 0.6 | JSON |
| `grade_response` | `grader_prompt_practice` | 1024 | 0.3 | JSON |
| `generate_exam` | `exam_generator_prompt` | 4096 | 0.5 | JSON |
| `grade_exam` | `grader_prompt_exam` | 2048 | 0.2 | JSON |

### 8.2 Operaciones DB por Nodo

| Nodo | Reads | Writes |
|------|-------|--------|
| `import_book` | - | books |
| `select_unit` | progress, books | - |
| `generate_notes` | - | progress (status=in_progress) |
| `exercise_loop` | - | attempts |
| `evaluate_unit` | attempts | progress, corrections, skills_by_tag |
| `exam_loop` | - | (state only) |
| `grade_exam` | - | exam_results |
| `evaluate_exam` | exam_results | progress, skills_by_tag |

---

## 9. Configuración del Grafo

```python
from langgraph.graph import StateGraph, END

def build_teaching_graph() -> StateGraph:
    """Construye el grafo principal de enseñanza."""
    
    graph = StateGraph(GraphState)
    
    # Añadir nodos
    graph.add_node("import_book", import_book_node)
    graph.add_node("extract_outline", extract_outline_node)
    graph.add_node("plan_units", plan_units_node)
    graph.add_node("select_unit", select_unit_node)
    graph.add_node("generate_notes", generate_notes_node)
    graph.add_node("study_session", study_session_node)
    graph.add_node("generate_exercises", generate_exercises_node)
    graph.add_node("exercise_loop", exercise_loop_node)
    graph.add_node("evaluate_unit", evaluate_unit_node)
    graph.add_node("check_exam_ready", check_exam_ready_node)
    graph.add_node("generate_exam", generate_exam_node)
    graph.add_node("exam_loop", exam_loop_node)
    graph.add_node("grade_exam", grade_exam_node)
    graph.add_node("evaluate_exam", evaluate_exam_node)
    graph.add_node("next_chapter", next_chapter_node)
    graph.add_node("finish", finish_node)
    
    # Definir transiciones
    graph.add_edge("import_book", "extract_outline")
    graph.add_edge("extract_outline", "plan_units")
    graph.add_edge("plan_units", "select_unit")
    
    # Transiciones condicionales
    graph.add_conditional_edges(
        "select_unit",
        route_after_select_unit,
        {
            "generate_notes": "generate_notes",
            "check_exam_ready": "check_exam_ready",
            "finish": "finish"
        }
    )
    
    graph.add_edge("generate_notes", "study_session")
    
    graph.add_conditional_edges(
        "study_session",
        route_after_study,
        {
            "continue": "study_session",  # Más preguntas
            "exercises": "generate_exercises",
            "exit": "evaluate_unit"
        }
    )
    
    graph.add_edge("generate_exercises", "exercise_loop")
    graph.add_edge("exercise_loop", "evaluate_unit")
    
    graph.add_conditional_edges(
        "evaluate_unit",
        route_after_evaluate_unit,
        {
            "next_unit": "select_unit",
            "retry_notes": "generate_notes",
            "retry_exercises": "exercise_loop"
        }
    )
    
    graph.add_conditional_edges(
        "check_exam_ready",
        route_exam_ready,
        {
            "ready": "generate_exam",
            "not_ready": "select_unit"
        }
    )
    
    graph.add_edge("generate_exam", "exam_loop")
    graph.add_edge("exam_loop", "grade_exam")
    graph.add_edge("grade_exam", "evaluate_exam")
    
    graph.add_conditional_edges(
        "evaluate_exam",
        route_after_exam,
        {
            "passed": "next_chapter",
            "failed": "select_unit"
        }
    )
    
    graph.add_conditional_edges(
        "next_chapter",
        route_next_chapter,
        {
            "more": "select_unit",
            "complete": "finish"
        }
    )
    
    graph.add_edge("finish", END)
    
    # Punto de entrada
    graph.set_entry_point("import_book")
    
    return graph.compile()
```

---

## 10. Resumen de Iteración

### ✅ Qué se ha definido

1. **Grafo principal** con 16 nodos y transiciones
2. **Estado global** (GraphState) con tipos
3. **Políticas deterministas** con umbrales configurables
4. **Subgrafos** para exercise loop y exam loop
5. **Pseudocódigo** de nodos clave
6. **Integración LLM/DB** por nodo

### ⚠️ Qué falta

- Prompts completos (entregable 4)
- Checklist de pruebas E2E (entregable 5)

### 🚨 Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Complejidad del grafo dificulta debug | Logging detallado + visualización |
| Latencia por múltiples llamadas LLM | Caching de respuestas + batch |
| Estado inconsistente tras crash | Checkpoints en cada transición |

### ➡️ Siguientes Pasos

1. Crear prompts v1 (6 archivos)
2. Checklist de pruebas E2E
