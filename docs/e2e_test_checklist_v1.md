# Checklist de Pruebas Manuales End-to-End — v1

> **Versión:** 1.0  
> **Fecha:** 2026-01-28  
> **Objetivo:** Validar el flujo completo del sistema de enseñanza

---

## Prerrequisitos

- [ ] Entorno conda `sistema_ensenianza` activado
- [ ] LM Studio corriendo con modelo cargado (<http://localhost:1234>)
- [ ] Archivo PDF de prueba disponible (ej: libro técnico de 100+ páginas)
- [ ] Base de datos limpia (eliminar `db/teaching.db` si existe)

---

## 1. Importación de Libro

### Test 1.1: Importar PDF válido

**Comando:**

```bash
teach import-book ~/Books/test_book.pdf --title "Test Book" --language en
```

**Verificaciones:**

- [ ] Comando termina sin errores (exit code 0)
- [ ] Se genera `data/books/{uuid}/book.json` con estructura correcta
- [ ] `book.json` contiene: `book_id`, `title`, `authors`, `source_format`, `sha256`
- [ ] Se extrae texto en `data/books/{uuid}/raw/`
- [ ] Se registra en SQLite: `SELECT * FROM books WHERE title = 'Test Book'`
- [ ] Mensaje indica "Siguiente paso: teach outline {book_id}"

### Test 1.2: Reimportar libro existente (sin --force)

**Comando:**

```bash
teach import-book ~/Books/test_book.pdf --title "Test Book"
```

**Verificaciones:**

- [ ] Error indicando que el libro ya existe (por hash)
- [ ] Exit code != 0
- [ ] No se duplica en DB

### Test 1.3: Reimportar con --force

**Comando:**

```bash
teach import-book ~/Books/test_book.pdf --title "Test Book v2" --force
```

**Verificaciones:**

- [ ] Éxito, nuevo book_id generado
- [ ] Libro anterior no se borra (solo se añade nuevo)

---

## 2. Extracción de Outline

### Test 2.1: Extraer outline automático

**Comando:**

```bash
teach outline {book_id}
```

**Verificaciones:**

- [ ] Se genera `data/books/{book_id}/outline.json`
- [ ] Outline contiene al menos 3 capítulos
- [ ] Cada capítulo tiene: `chapter_id`, `number`, `title`, `sections`
- [ ] IDs siguen convención: `{book_id}:ch:1`, `{book_id}:ch:1:sec:1`
- [ ] Log muestra llamada al LLM (si aplica)

### Test 2.2: Outline con review manual

**Comando:**

```bash
teach outline {book_id} --review
```

**Verificaciones:**

- [ ] Se abre YAML editable en terminal/editor
- [ ] Cambios guardados se reflejan en `outline.json`
- [ ] Si se cancela (Ctrl+C), no se guarda

---

## 3. Planificación de Unidades

### Test 3.1: Generar plan de unidades

**Comando:**

```bash
teach plan {book_id} --target-time 25
```

**Verificaciones:**

- [ ] Se genera `data/books/{book_id}/units.json`
- [ ] Cada unidad tiene tiempo estimado entre 20-40 minutos
- [ ] Unidades cubren todos los capítulos del outline
- [ ] IDs: `{book_id}:unit:1`, `{book_id}:unit:2`, etc.
- [ ] Campo `learning_objectives` poblado para cada unidad
- [ ] Estado de libro en DB cambia a `planned`

### Test 3.2: Preview sin guardar

**Comando:**

```bash
teach plan {book_id} --preview
```

**Verificaciones:**

- [ ] Muestra plan en terminal
- [ ] NO genera archivo `units.json`

---

## 4. Sesión de Estudio (Start-Unit + Apuntes)

### Test 4.1: Iniciar primera unidad

**Comando:**

```bash
teach start-unit {book_id}:unit:1
```

**Verificaciones:**

- [ ] Se genera `data/books/{book_id}/artifacts/notes/unit_1.md`
- [ ] Apuntes siguen el template definido (todas las secciones)
- [ ] Apuntes están en **español**
- [ ] Estado de unidad en DB: `in_progress`
- [ ] Se registra `notes_viewed_at` en tabla `progress`
- [ ] Output muestra apuntes formateados en terminal

### Test 4.2: Regenerar apuntes existentes

**Comando:**

```bash
teach start-unit {book_id}:unit:1 --regenerate
```

**Verificaciones:**

- [ ] Archivo de apuntes se sobrescribe
- [ ] Backup del anterior se crea (opcional: verificar)

### Test 4.3: Verificar contenido de apuntes

**Manual:**

- [ ] Abrir `unit_1.md` y verificar:
  - [ ] Título correcto
  - [ ] Objetivos de aprendizaje presentes
  - [ ] Contenido principal coherente con el libro
  - [ ] Puntos clave son útiles
  - [ ] Preguntas de autoevaluación NO tienen respuestas

---

## 5. Ejercicios (Respuesta Primero)

### Test 5.1: Realizar ejercicios de unidad

**Comando:**

```bash
teach exercise {book_id}:unit:1
```

**Flujo:**

1. [ ] Se muestra primer ejercicio SIN respuesta correcta
2. [ ] Se espera input del usuario
3. [ ] Tras responder, se muestra corrección + explicación
4. [ ] Se pasa al siguiente ejercicio

**Verificaciones:**

- [ ] Se genera `data/books/{book_id}/artifacts/exercises/unit_1.json` (si no existía)
- [ ] Cada intento se registra en `attempts` table
- [ ] Correcciones se registran en `corrections` table
- [ ] Tags se actualizan en `skills_by_tag`
- [ ] Al final se muestra resumen con score

### Test 5.2: Ejercicio incorrecto

**Manual:**

- [ ] Responder intencionalmente mal a un ejercicio
- [ ] Verificar que feedback explica el error
- [ ] Verificar que `is_correct = 0` en DB

### Test 5.3: Retry de ejercicios fallados

**Comando:**

```bash
teach exercise {book_id}:unit:1 --retry-wrong
```

**Verificaciones:**

- [ ] Solo muestra ejercicios donde `is_correct = 0` en intentos previos
- [ ] Nuevo intento se registra como attempt adicional

---

## 6. Examen de Capítulo (Modo Estricto)

### Test 6.1: Prerrequisitos de examen

**Comando (con <80% unidades completas):**

```bash
teach exam {book_id}:ch:1
```

**Verificaciones:**

- [ ] Error: "Completa X unidades más para habilitar el examen"
- [ ] No se genera examen

### Test 6.2: Examen con unidades completas

**Setup:** Completar >=80% de unidades del capítulo 1

**Comando:**

```bash
teach exam {book_id}:ch:1
```

**Flujo:**

1. [ ] Se muestra temporizador
2. [ ] Preguntas se presentan una a una
3. [ ] NO se muestra feedback entre preguntas
4. [ ] NO hay opción de hints
5. [ ] Al finalizar todas, se muestra resultado completo

**Verificaciones:**

- [ ] Se genera `data/books/{book_id}/artifacts/exams/ch_1.json`
- [ ] Resultado en `exam_results` table
- [ ] `passed` = 1 si score >= 60%
- [ ] Feedback muestra respuestas correctas SOLO al final
- [ ] Skills actualizados en `skills_by_tag`

### Test 6.3: Examen timeout

**Manual:**

- [ ] Iniciar examen con --time-limit 1 (1 minuto)
- [ ] Dejar que expire el tiempo
- [ ] Verificar que se fuerza envío y se califica lo respondido

### Test 6.4: Reintentar examen fallado

**Setup:** Fallar examen intencionalmente

**Comando inmediato:**

```bash
teach exam {book_id}:ch:1 --retake
```

**Verificaciones:**

- [ ] Error: "Espera X horas antes de reintentar"

---

## 7. Estado y Progreso

### Test 7.1: Ver estado general

**Comando:**

```bash
teach status
```

**Verificaciones:**

- [ ] Muestra libros activos con progreso
- [ ] Porcentaje de unidades completas correcto
- [ ] Muestra próxima unidad sugerida
- [ ] Muestra estado de exámenes por capítulo

### Test 7.2: Ver skills

**Comando:**

```bash
teach status --skills
```

**Verificaciones:**

- [ ] Lista tags con proficiency scores
- [ ] Scores calculados correctamente (correct/total)
- [ ] Tags débiles (<60%) resaltados

### Test 7.3: Estado detallado por libro

**Comando:**

```bash
teach status --book {book_id} --detailed
```

**Verificaciones:**

- [ ] Muestra cada unidad con estado
- [ ] Incluye scores de ejercicios/exámenes

---

## 8. Recomendaciones (Proactividad del Profesor)

### Test 8.1: Comando next sugiere correctamente

**Escenarios a probar:**

| Estado Actual | Esperado |
|---------------|----------|
| Unidad sin apuntes | `start-unit` sugerido |
| Unidad con apuntes, sin ejercicios | `exercise` sugerido |
| Unidad completa, hay siguiente | `start-unit` (siguiente) |
| Todas unidades de cap completas | `exam` sugerido |
| Examen fallado | `exercise --retry-wrong` en unidades débiles |

**Comando:**

```bash
teach next
```

**Verificaciones:**

- [ ] Sugerencia coincide con tabla anterior
- [ ] Razón explicada es coherente
- [ ] Con `--auto`, ejecuta sin confirmar

---

## 9. Integridad de Datos SQLite

### Test 9.1: Verificar constraints

**Queries de validación:**

```sql
-- No hay huérfanos en progress
SELECT COUNT(*) FROM progress 
WHERE student_id NOT IN (SELECT student_id FROM student_profile);

-- No hay huérfanos en attempts
SELECT COUNT(*) FROM attempts 
WHERE student_id NOT IN (SELECT student_id FROM student_profile);

-- Scores están en rango válido
SELECT COUNT(*) FROM progress WHERE score < 0 OR score > 1;
SELECT COUNT(*) FROM skills_by_tag WHERE proficiency < 0 OR proficiency > 1;
```

**Verificaciones:**

- [ ] Todas las queries retornan 0

### Test 9.2: Verificar índices

```sql
.indices progress
.indices attempts
.indices skills_by_tag
```

**Verificaciones:**

- [ ] Índices existen según DDL

---

## 10. Logging

### Test 10.1: Verificar logs se generan

**Comando:**

```bash
tail -f logs/teaching.log
```

**Mientras ejecutas cualquier comando, verificar:**

- [ ] Formato correcto: `timestamp | LEVEL | logger | message`
- [ ] Operaciones principales loggeadas (INFO)
- [ ] Con `--verbose`, se ven DEBUG (prompts LLM truncados)

### Test 10.2: Rotación de logs

**Manual (si aplica):**

- [ ] Generar >10MB de logs
- [ ] Verificar rotación automática

---

## Resumen de Resultados

| Categoría | Tests | Pasados | Fallidos |
|-----------|-------|---------|----------|
| Importación | 3 | | |
| Outline | 2 | | |
| Plan | 2 | | |
| Apuntes | 3 | | |
| Ejercicios | 3 | | |
| Exámenes | 4 | | |
| Estado | 3 | | |
| Next | 1 | | |
| SQLite | 2 | | |
| Logging | 2 | | |
| **TOTAL** | **25** | | |

---

## Notas del Tester

_Espacio para documentar hallazgos, bugs encontrados, sugerencias..._

```
Fecha: _______________
Tester: _______________

Bugs encontrados:
1. 
2.

Sugerencias:
1.
2.
```

---

## Qué se ha definido

- 25 tests manuales organizados en 10 categorías
- Verificaciones específicas para cada test
- Queries SQL para validación de integridad
- Tabla de resumen de resultados

## Siguientes pasos

1. Ejecutar esta checklist tras implementar MVP
2. Automatizar tests críticos (import, outline, exercises)
3. Añadir tests de edge cases (PDF corrupto, LLM timeout, etc.)
