# Especificación CLI v1 — Profesor LLM Personal

> **Versión:** 1.0  
> **Fecha:** 2026-01-28  
> **Estado:** Draft para revisión

---

## Convenciones Generales

### Invocación

```bash
# Nombre del CLI
teach <comando> [subcomando] [opciones] [argumentos]

# Alternativa como módulo Python
python -m teaching <comando> [subcomando] [opciones] [argumentos]
```

### Opciones Globales

| Opción | Descripción |
|--------|-------------|
| `--help`, `-h` | Muestra ayuda del comando |
| `--version`, `-v` | Muestra versión del sistema |
| `--verbose` | Activa logging DEBUG |
| `--quiet`, `-q` | Solo errores críticos |
| `--config <path>` | Archivo de configuración alternativo |
| `--db <path>` | Base de datos SQLite alternativa |

### Códigos de Salida

| Código | Significado |
|--------|-------------|
| 0 | Éxito |
| 1 | Error general |
| 2 | Error de argumentos |
| 3 | Archivo no encontrado |
| 4 | Error de parsing |
| 5 | Error de LLM |
| 10 | Operación cancelada por usuario |

---

## Comandos

### 1. `import-book` — Importar un libro

**Descripción:** Importa un libro PDF o EPUB, extrae el texto y genera `book.json`.

```bash
teach import-book <archivo> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<archivo>` | path | Sí | Ruta al archivo PDF o EPUB |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--title` | string | (del archivo) | Título del libro |
| `--author` | string | (detectado) | Autor(es) separados por coma |
| `--language` | string | `auto` | Idioma: `en`, `es`, `auto` |
| `--force`, `-f` | flag | false | Reimportar si ya existe (por hash) |

**Output (success):**

```
✓ Libro importado: "Designing Data-Intensive Applications"
  ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Páginas: 562
  Idioma detectado: en
  Ruta: data/books/a1b2c3d4.../book.json

Siguiente paso: teach outline a1b2c3d4...
```

**Output (error):**

```
✗ Error: No se pudo extraer texto del PDF
  Detalle: Archivo protegido o escaneado sin OCR
  Sugerencia: Usa un PDF con texto seleccionable
```

---

### 2. `outline` — Extraer estructura del libro

**Descripción:** Detecta capítulos y secciones, genera `outline.json`.

```bash
teach outline <book_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<book_id>` | string | Sí | ID del libro (UUID o prefijo único) |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--method` | string | `auto` | Método: `auto`, `toc`, `headings`, `llm` |
| `--review` | flag | false | Mostrar outline para edición manual |
| `--min-sections` | int | 3 | Mínimo de secciones por capítulo |

**Output (success):**

```
✓ Outline generado para "Designing Data-Intensive Applications"

Capítulos detectados: 12
  1. Reliable, Scalable, and Maintainable Applications (4 secciones)
  2. Data Models and Query Languages (6 secciones)
  3. Storage and Retrieval (5 secciones)
  ...

Ruta: data/books/a1b2c3d4.../outline.json

Siguiente paso: teach plan a1b2c3d4...
```

**Output (--review):**

```yaml
# Edita este outline y guarda para confirmar
# Elimina capítulos/secciones incorrectos, ajusta títulos

chapters:
  - number: 1
    title: "Reliable, Scalable, and Maintainable Applications"
    sections:
      - "1.1 Thinking About Data Systems"
      - "1.2 Reliability"
      ...
```

---

### 3. `plan` — Generar plan de unidades formativas

**Descripción:** Segmenta el libro en unidades de 20-40 minutos, genera `units.json`.

```bash
teach plan <book_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<book_id>` | string | Sí | ID del libro |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--target-time` | int | 30 | Tiempo objetivo por unidad (minutos) |
| `--difficulty` | string | `auto` | Nivel base: `beginner`, `intermediate`, `advanced`, `auto` |
| `--preview` | flag | false | Mostrar plan sin guardar |

**Output (success):**

```
✓ Plan generado para "Designing Data-Intensive Applications"

Total unidades: 45
Tiempo estimado total: 22.5 horas
Dificultad base: intermediate

Resumen por capítulo:
  Cap 1: 4 unidades (~2h)
  Cap 2: 5 unidades (~2.5h)
  ...

Ruta: data/books/a1b2c3d4.../units.json

Siguiente paso: teach start-unit a1b2c3d4...:unit:1
```

---

### 4. `start-unit` — Iniciar una unidad (generar apuntes)

**Descripción:** Genera apuntes para una unidad específica y marca como iniciada.

```bash
teach start-unit <unit_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<unit_id>` | string | Sí | ID de la unidad (ej: `book_id:unit:5`) |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--regenerate` | flag | false | Regenerar apuntes existentes |
| `--format` | string | `terminal` | Output: `terminal`, `markdown`, `json` |
| `--no-save` | flag | false | No guardar en disco |

**Output (success — terminal):**

```
═══════════════════════════════════════════════════════════════════
  UNIDAD 5: Storage Engines - Part 1
  Capítulo 3 | Tiempo estimado: 25 min | Dificultad: intermediate
═══════════════════════════════════════════════════════════════════

🎯 OBJETIVOS DE APRENDIZAJE
  • Comprender la diferencia entre log-structured y page-oriented storage
  • Explicar cómo funcionan los LSM-Trees
  • Identificar las ventajas y desventajas de cada enfoque

───────────────────────────────────────────────────────────────────

📖 CONTENIDO
  [Contenido principal del apunte...]

───────────────────────────────────────────────────────────────────

💡 PUNTOS CLAVE
  • Los storage engines se dividen en dos familias principales
  • LSM-Trees optimizan escrituras secuenciales
  • B-Trees son el estándar para bases de datos relacionales

───────────────────────────────────────────────────────────────────

📝 Apuntes guardados en: data/books/.../artifacts/notes/unit_5.md

Siguientes opciones:
  teach exercise a1b2c3d4...:unit:5  — Hacer ejercicios
  teach next                          — Siguiente unidad
  teach status                        — Ver progreso
```

---

### 5. `exercise` — Realizar ejercicios de una unidad

**Descripción:** Presenta ejercicios uno a uno, espera respuesta, luego corrige.

```bash
teach exercise <unit_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<unit_id>` | string | Sí | ID de la unidad |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--count` | int | `all` | Número de ejercicios a mostrar |
| `--type` | string | `all` | Filtrar: `test`, `practice`, `code` |
| `--difficulty` | string | `all` | Filtrar: `easy`, `medium`, `hard` |
| `--retry-wrong` | flag | false | Solo ejercicios fallados previamente |

**Flujo Interactivo:**

```
═══════════════════════════════════════════════════════════════════
  EJERCICIO 1/5 — Unidad 5: Storage Engines - Part 1
  Tipo: multiple_choice | Dificultad: easy | Puntos: 1
═══════════════════════════════════════════════════════════════════

¿Cuál de las siguientes es una característica principal de los LSM-Trees?

  A) Mantienen los datos ordenados en disco en estructura de árbol B
  B) Optimizan las escrituras mediante append-only logs
  C) Requieren actualizaciones in-place para cada escritura
  D) No soportan compactación de datos

Tu respuesta (A/B/C/D): B

───────────────────────────────────────────────────────────────────

✓ ¡CORRECTO!

Explicación: Los LSM-Trees (Log-Structured Merge-Trees) escriben todos
los datos nuevos de forma secuencial en un log, lo que optimiza las
escrituras al evitar seeks aleatorios en disco.

Referencia: Capítulo 3, Sección 3.1 (página 72)

───────────────────────────────────────────────────────────────────

Presiona ENTER para continuar al siguiente ejercicio...
```

**Output (resumen final):**

```
═══════════════════════════════════════════════════════════════════
  RESUMEN DE EJERCICIOS — Unidad 5
═══════════════════════════════════════════════════════════════════

Resultado: 4/5 correctas (80%)
Tiempo total: 8 min 32 seg

Por tipo:
  • Multiple choice: 3/3 ✓
  • Short answer: 1/2

Tags débiles detectados:
  ⚠️ "compaction" — 0/1 correcto
  
Recomendación: Repasar sección 3.2 sobre compactación

Siguiente paso: teach next
```

---

### 6. `exam` — Realizar examen de capítulo

**Descripción:** Modo estricto — todas las preguntas, tiempo límite, sin pistas.

```bash
teach exam <chapter_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<chapter_id>` | string | Sí | ID del capítulo (ej: `book_id:ch:3`) |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--time-limit` | int | (del exam.json) | Límite en minutos |
| `--retake` | flag | false | Repetir examen ya aprobado |

**Comportamiento modo estricto:**

1. No se muestran respuestas correctas hasta enviar todo
2. No hay pistas
3. Temporizador visible
4. No se puede volver a preguntas anteriores (opcional, configurable)

**Flujo:**

```
═══════════════════════════════════════════════════════════════════
  📝 EXAMEN — Capítulo 3: Storage and Retrieval
  Preguntas: 15 | Tiempo límite: 30 min | Nota mínima: 60%
═══════════════════════════════════════════════════════════════════

⏱️ Tiempo restante: 29:45

Pregunta 1/15 [easy, 1 punto]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Describe brevemente la diferencia entre un storage engine basado en
log-structured y uno page-oriented.

Tu respuesta (texto, termina con línea vacía):
> ...

[ENTER para siguiente pregunta]
```

**Output (resultado):**

```
═══════════════════════════════════════════════════════════════════
  RESULTADO EXAMEN — Capítulo 3
═══════════════════════════════════════════════════════════════════

Nota: 12/15 puntos (80%) ✅ APROBADO

Tiempo utilizado: 24 min 15 seg

Desglose:
  • Multiple choice: 8/10
  • Short answer: 4/5

Feedback del profesor:
  Buen dominio de los conceptos de LSM-Trees y B-Trees. 
  Revisar la sección sobre WAL (Write-Ahead Logging) donde
  hubo errores conceptuales.

Preguntas falladas (con explicación):
  #4: [explicación]
  #11: [explicación]

Próximo examen disponible: Capítulo 4
```

---

### 7. `status` — Ver estado actual

**Descripción:** Muestra progreso del estudiante en libros activos.

```bash
teach status [opciones]
```

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--book` | string | (todos) | Filtrar por book_id |
| `--detailed` | flag | false | Mostrar desglose por unidad |
| `--skills` | flag | false | Mostrar skills/tags |

**Output:**

```
═══════════════════════════════════════════════════════════════════
  📊 ESTADO DEL ESTUDIANTE: Alex
═══════════════════════════════════════════════════════════════════

📚 Libros activos: 2

1. Designing Data-Intensive Applications
   ████████████░░░░░░░░ 12/45 unidades (27%)
   Último acceso: hace 2 horas
   Próxima unidad: 13 - "Replication - Part 1"
   Exámenes: Cap 1 ✅ (85%), Cap 2 ✅ (72%), Cap 3 ⏳
   
2. Clean Code
   ████░░░░░░░░░░░░░░░░ 5/32 unidades (16%)
   Último acceso: hace 3 días
   Próxima unidad: 6 - "Functions - Part 2"
   Exámenes: Cap 1 ✅ (90%)

───────────────────────────────────────────────────────────────────

🏷️ Skills destacados (top 5):
  • data_modeling: 85% (28 intentos)
  • storage_engines: 78% (15 intentos)
  • consistency: 72% (12 intentos)
  • transactions: 65% (8 intentos)
  • replication: -- (sin datos)

───────────────────────────────────────────────────────────────────

💡 Recomendación del profesor:
  "Has completado bien el Cap 3. Te sugiero hacer el examen antes
   de pasar al Cap 4 sobre replicación."
```

---

### 8. `study` — Sesión de estudio guiada

**Descripción:** Inicia una sesión interactiva donde el profesor explica, el alumno pregunta.

```bash
teach study <unit_id> [opciones]
```

**Argumentos:**

| Argumento | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `<unit_id>` | string | Sí | ID de la unidad a estudiar |

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--mode` | string | `interactive` | Modo: `interactive`, `lecture`, `qa` |

**Flujo interactivo:**

```
═══════════════════════════════════════════════════════════════════
  📖 SESIÓN DE ESTUDIO — Unidad 5: Storage Engines - Part 1
  Modo: interactivo | Escribe 'salir' para terminar
═══════════════════════════════════════════════════════════════════

Profesor: Hola, vamos a estudiar los motores de almacenamiento.
Empezaré explicándote los dos grandes tipos que existen...

[Explicación inicial]

¿Tienes alguna pregunta sobre esto?

Tú> ¿Por qué los LSM-Trees son mejores para escrituras?

Profesor: Excelente pregunta. Los LSM-Trees optimizan escrituras
porque... [explicación detallada con referencia al libro]

Tú> salir

───────────────────────────────────────────────────────────────────
Sesión guardada. Duración: 15 min
Siguiente: teach exercise a1b2c3d4...:unit:5
```

---

### 9. `next` — Avanzar a la siguiente actividad

**Descripción:** El profesor sugiere y ejecuta la siguiente acción lógica.

```bash
teach next [opciones]
```

**Opciones:**

| Opción | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `--book` | string | (último activo) | Libro específico |
| `--auto` | flag | false | Ejecutar sin confirmar |

**Output (ejemplo):**

```
📍 Estado actual: Unidad 5 completada (apuntes + ejercicios)

El profesor sugiere: Comenzar Unidad 6 "Storage Engines - Part 2"
Razón: Continúa directamente con el contenido de la unidad anterior

¿Proceder? [S/n]: s

[Se ejecuta: teach start-unit a1b2c3d4...:unit:6]
```

**Lógica de decisión:**

1. Si unidad no tiene apuntes → `start-unit`
2. Si unidad tiene apuntes pero no ejercicios → `exercise`
3. Si unidad completa y hay siguiente → `start-unit` (siguiente)
4. Si todas las unidades de un capítulo completas → `exam`
5. Si examen fallado → `exercise --retry-wrong` en unidades débiles
6. Si todo completo → mensaje de felicitación + siguiente capítulo

---

## Ejemplos de Flujo Completo

```bash
# 1. Importar libro
teach import-book ~/Books/ddia.pdf --title "DDIA" --language en

# 2. Generar outline
teach outline a1b2c3d4...

# 3. Planificar unidades
teach plan a1b2c3d4... --target-time 25

# 4. Estudiar primera unidad
teach start-unit a1b2c3d4...:unit:1

# 5. Hacer ejercicios
teach exercise a1b2c3d4...:unit:1

# 6. Ver progreso
teach status

# 7. Continuar (el profesor decide)
teach next --auto

# 8. Examen de capítulo
teach exam a1b2c3d4...:ch:1
```

---

## Configuración (`~/.teach/config.yaml`)

```yaml
# Configuración del profesor LLM
llm:
  provider: lmstudio  # o "openai", "anthropic"
  base_url: http://localhost:1234/v1
  model: default
  temperature: 0.7
  max_tokens: 4096

# Base de datos
database:
  path: ~/.teach/teaching.db

# Datos
data_dir: ~/.teach/data

# Preferencias de estudio
study:
  default_unit_time: 30  # minutos
  exercises_per_unit: 5
  exam_time_multiplier: 2  # minutos por pregunta

# Logging
logging:
  level: INFO
  file: ~/.teach/logs/teaching.log
```

---

## Resumen de Iteración

### ✅ Qué se ha definido

1. **9 comandos CLI** con argumentos, opciones y outputs detallados
2. **Flujos interactivos** para ejercicios, exámenes y estudio
3. **Códigos de salida** estandarizados
4. **Formato de configuración** YAML
5. **Ejemplos de uso** end-to-end

### ⚠️ Qué falta

- Diseño del grafo LangGraph (entregable 3)
- Prompts completos (entregable 4)
- Checklist de pruebas E2E (entregable 5)

### ➡️ Siguientes Pasos

1. Diseño LangGraph v1 — Estados, transiciones y políticas
