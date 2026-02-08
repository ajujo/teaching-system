# Phase Guardrails

> **Regla principal:** No se implementa ningún módulo antes de su fase asignada.

Este documento define qué módulos pertenecen a cada fase de implementación. Los módulos futuros están en `src/teaching/future/` como placeholders sin lógica.

---

## Asignación de Módulos por Fase

| Fase | Módulo | Ubicación | Estado |
|------|--------|-----------|--------|
| **F2** | `book_importer.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | `pdf_extractor.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | `epub_extractor.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | `text_normalizer.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | `outline_extractor.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | `outline_validator.py` | `src/teaching/core/` | ✅ Completado |
| **F2** | CLI: `import-book`, `outline` | `src/teaching/cli/` | ✅ Completado |
| **F3** | `unit_planner.py` | `src/teaching/core/` | ✅ Completado |
| **F3** | CLI: `plan` | `src/teaching/cli/` | ✅ Completado |
| **F4** | `notes_generator.py` | `src/teaching/core/` | ✅ Completado |
| **F4** | CLI: `notes` | `src/teaching/cli/` | ✅ Completado |
| **F5** | `exercise_generator.py` | `src/teaching/core/` | ✅ Completado |
| **F5** | `attempt_repository.py` | `src/teaching/core/` | ✅ Completado |
| **F5** | `grader.py` | `src/teaching/core/` | ✅ Completado |
| **F5** | CLI: `exercise`, `submit`, `grade` | `src/teaching/cli/` | ✅ Completado |
| F6 | `exam_generator.py` | `src/teaching/future/core/` | ⏳ Pendiente |
| F6 | CLI: `exam` | stub en cli | ⏳ Pendiente |
| F7 | `graph.py` | `src/teaching/future/graph/` | ⏳ Pendiente |
| F7 | `nodes.py` | `src/teaching/future/graph/` | ⏳ Pendiente |
| F7 | `states.py` | `src/teaching/future/graph/` | ⏳ Pendiente |
| F8 | `models.py` (DB) | `src/teaching/future/db/` | ⏳ Pendiente |
| F8 | `repository.py` | `src/teaching/future/db/` | ⏳ Pendiente |

---

## Componentes Compartidos (Disponibles desde F2)

| Componente | Ubicación | Descripción |
|------------|-----------|-------------|
| `cli/commands.py` | `src/teaching/cli/` | Entry point CLI (stubs futuros incluidos) |
| `llm/client.py` | `src/teaching/llm/` | Cliente LLM genérico |
| `utils/validators.py` | `src/teaching/utils/` | Validadores de ID |
| `utils/text_utils.py` | `src/teaching/utils/` | Utilidades de texto |
| `configs/models.yaml` | `configs/` | Configuración de modelos |
| `prompts/*` | `prompts/` | Prompts del sistema |

---

## Reglas de No-Contaminación

1. **No importar `future/`**: El paquete `src/teaching/future/` NO debe ser importado por ningún módulo activo.

2. **CLI stubs sin lógica**: Los comandos de fases futuras en el CLI solo imprimen un mensaje y salen con código 1.

3. **Tests por fase**: Los tests están organizados en `tests/f2/`, `tests/f3/`, etc. El archivo `tests/conftest.py` salta automáticamente los tests de fases no implementadas (variable `CURRENT_PHASE`).

4. **Dependencias mínimas**: Solo las dependencias necesarias para la fase actual están activas en `pyproject.toml`.

---

## Checklist de Promoción de Fase

Antes de promover un módulo de `future/` a `core/`:

- [ ] La fase anterior está completada y probada
- [ ] El módulo tiene tests escritos
- [ ] El módulo sigue los contratos de `contracts_v1.md`
- [ ] Los prompts necesarios existen en `prompts/`
- [ ] El CLI command está actualizado con parámetros completos
- [ ] La documentación está actualizada

---

## Estructura Actual del Proyecto

```
src/teaching/
├── __init__.py
├── cli/
│   ├── __init__.py
│   └── commands.py          # F2-F5 activos, stubs F6-F8
├── core/                     # F2-F5 módulos activos
│   ├── __init__.py
│   ├── book_importer.py      # F2
│   ├── pdf_extractor.py      # F2
│   ├── epub_extractor.py     # F2
│   ├── text_normalizer.py    # F2
│   ├── outline_extractor.py  # F2
│   ├── outline_validator.py  # F2
│   ├── unit_planner.py       # F3
│   ├── notes_generator.py    # F4
│   ├── exercise_generator.py # F5
│   ├── attempt_repository.py # F5
│   └── grader.py             # F5
├── llm/                      # Compartido
│   ├── __init__.py
│   └── client.py
├── db/                       # F2+ básico
│   ├── __init__.py
│   └── books_repository.py
├── utils/                    # Compartido
│   ├── __init__.py
│   ├── validators.py
│   └── text_utils.py
└── future/                   # NO TOCAR hasta fase correspondiente
    ├── __init__.py
    ├── core/
    │   └── exam_generator.py # F6
    ├── graph/
    │   ├── graph.py          # F7
    │   ├── nodes.py          # F7
    │   └── states.py         # F7
    └── db/
        ├── models.py         # F8
        └── repository.py     # F8
```
