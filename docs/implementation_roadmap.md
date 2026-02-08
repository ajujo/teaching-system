# Plan de Implementación Ejecutable — Profesor LLM Personal

> **Versión:** 1.0  
> **Fecha:** 2026-01-28  
> **Estado:** Aprobado para ejecución

---

## Visión General de Fases

```
F1 ✅ ─► F2 ─► F3 ─► F4 ─► F5 ─► F6 ─► F7 ─► F8
         │
         └──► ESTAMOS AQUÍ
```

---

## Roadmap de Implementación

### F1: Contratos/CLI/estado/logs ✅

**Estado:** Completado (documentos de diseño)

---

### F2: Ingesta de Libro + Outline

**Objetivo:** Importar PDF/EPUB, extraer texto, normalizar y generar estructura de capítulos.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F2.1 | Setup proyecto Python | `pyproject.toml`, estructura carpetas, dependencias |
| F2.2 | Importador PDF | Extrae texto de PDF, genera `book.json` |
| F2.3 | Importador EPUB | Extrae texto de EPUB, genera `book.json` |
| F2.4 | Normalizador de texto | Limpia y normaliza texto extraído |
| F2.5 | Extractor de outline | Detecta capítulos/secciones, genera `outline.json` |
| F2.6 | Validador de outline | Permite corrección manual del outline |
| F2.7 | CLI `import-book` + `outline` | Comandos funcionan end-to-end |

**Definition of Done (DoD) F2:**

- [ ] `teach import-book libro.pdf` genera `book.json` válido
- [ ] `teach outline {book_id}` genera `outline.json` con capítulos detectados
- [ ] Tests 1.1-1.3, 2.1-2.2 del checklist E2E pasan
- [ ] Logging funciona según especificación

**Duración estimada:** 3-5 días

---

### F3: Segmentación Pedagógica (Units)

**Objetivo:** Segmentar capítulos en unidades de 20-40 minutos.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F3.1 | Planificador de unidades | Genera `units.json` desde outline |
| F3.2 | Estimador de tiempo | Calcula tiempo por unidad |
| F3.3 | Asignador de dificultad | Asigna nivel a cada unidad |
| F3.4 | CLI `plan` | Comando funciona end-to-end |

**DoD F3:**

- [ ] `teach plan {book_id}` genera `units.json` válido
- [ ] Cada unidad tiene tiempo entre 20-40 min
- [ ] Tests 3.1-3.2 del checklist pasan

**Duración estimada:** 2-3 días

---

### F4: Teacher + Notes + Start-Unit

**Objetivo:** Generar apuntes y permitir sesiones de estudio interactivas.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F4.1 | Generador de apuntes | Crea `notes.md` desde contenido de unidad |
| F4.2 | Cliente LLM | Conecta con LM Studio |
| F4.3 | Sesión de estudio | Modo interactivo Q&A |
| F4.4 | CLI `start-unit` + `study` | Comandos funcionan |

**DoD F4:**

- [ ] `teach start-unit {unit_id}` genera apuntes en español
- [ ] `teach study {unit_id}` permite interacción con el profesor
- [ ] Tests 4.1-4.3 del checklist pasan
- [ ] Apuntes siguen template exacto

**Duración estimada:** 4-6 días

---

### F5: Ejercicios + Corrección Diferida

**Objetivo:** Generar ejercicios, esperar respuesta, luego corregir.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F5.1 | Generador de ejercicios | Crea `exercises.json` |
| F5.2 | Corrector (práctica) | Evalúa respuestas con feedback |
| F5.3 | Repositorio SQLite | Guarda attempts/corrections |
| F5.4 | CLI `exercise` | Flujo completo funciona |

**DoD F5:**

- [ ] `teach exercise {unit_id}` muestra ejercicios uno a uno
- [ ] Respuestas se corrigen DESPUÉS de que el alumno responde
- [ ] Tests 5.1-5.3 del checklist pasan
- [ ] Skills se actualizan en `skills_by_tag`

**Duración estimada:** 4-5 días

---

### F6: Exámenes por Capítulo

**Objetivo:** Examen en modo estricto con evaluación al final.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F6.1 | Generador de exámenes | Crea `exam.json` por capítulo |
| F6.2 | Flujo de examen | Modo estricto (sin hints, temporizador) |
| F6.3 | Corrector (examen) | Evalúa todo al final |
| F6.4 | CLI `exam` | Comando funciona end-to-end |

**DoD F6:**

- [ ] `teach exam {chapter_id}` ejecuta examen completo
- [ ] No se muestran respuestas hasta enviar todo
- [ ] Tests 6.1-6.4 del checklist pasan

**Duración estimada:** 3-4 días

---

### F7: Orquestación LangGraph + API

**Objetivo:** Integrar todo con LangGraph, implementar `next`, API opcional.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F7.1 | Grafo principal | Implementar nodos y transiciones |
| F7.2 | Checkpoints | Persistencia de estado del grafo |
| F7.3 | CLI `next` + `status` | Comandos inteligentes |
| F7.4 | API REST (opcional) | Endpoints para integración |

**DoD F7:**

- [ ] `teach next` sugiere y ejecuta acción correcta
- [ ] Estado del grafo se persiste entre sesiones
- [ ] Tests 7.1-7.3, 8.1 del checklist pasan

**Duración estimada:** 5-7 días

---

### F8: AnythingLLM (UI Fase 2)

**Objetivo:** Integrar con AnythingLLM como frontend.

| Hito | Descripción | Criterio de Éxito |
|------|-------------|-------------------|
| F8.1 | Plugin AnythingLLM | Conecta con API del sistema |
| F8.2 | Comandos de slash | `/study`, `/next`, etc. |
| F8.3 | Visualización | Muestra progreso en UI |

**DoD F8:**

- [ ] Usuario puede estudiar desde AnythingLLM
- [ ] Progreso visible en interfaz
- [ ] Documentación de integración completa

**Duración estimada:** 5-7 días

---

## Diagrama de Dependencias

```
F2 (Ingesta)
 └──► F3 (Units)
       └──► F4 (Teacher/Notes)
             ├──► F5 (Ejercicios)
             │     └──► F6 (Exámenes)
             │           └──► F7 (LangGraph)
             │                 └──► F8 (UI)
             └──────────────────────┘
```

---

## Duración Total Estimada

| Fase | Días | Acumulado |
|------|------|-----------|
| F2 | 3-5 | 3-5 |
| F3 | 2-3 | 5-8 |
| F4 | 4-6 | 9-14 |
| F5 | 4-5 | 13-19 |
| F6 | 3-4 | 16-23 |
| F7 | 5-7 | 21-30 |
| F8 | 5-7 | 26-37 |

**Total: 4-6 semanas** (trabajando de forma consistente)

---

## Mitigación de Riesgos de Diseño (Actualizado)

| Riesgo | Mitigación Implementada |
|--------|------------------------|
| Extracción de outline varía según PDF | F2.6: Validador con modo `--review` para corrección manual |
| Grading de respuestas abiertas | Campo `grader_confidence` + flag para revisión humana |
| Contexto LLM insuficiente | Segmentación en F3 + resúmenes intermedios en F4 |
