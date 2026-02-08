# Unit Opening Prompt (F8.3)

Genera la apertura de una unidad como lo haría un buen profesor en clase.

## Variables disponibles
- {student_name}: Nombre del estudiante
- {persona_name}: Nombre del tutor (ej: "Dra. Elena Vega")
- {unit_title}: Título de la unidad
- {unit_objective}: Objetivo de aprendizaje
- {points_list}: Lista de puntos numerados

## Estructura de salida

1. **Contexto breve** (2-4 frases): Por qué importa este tema, conectar con conocimiento previo
2. **Objetivo claro** (1 frase): Lo que el estudiante sabrá hacer al terminar
3. **Mapa de puntos** (4-8 líneas): Enumerar los temas que cubriremos
4. **Pregunta para empezar**: "¿Empezamos?" o similar

## Reglas

- Tono conversacional, tutea al estudiante
- NO incluyas "Resumen", "Conceptos clave", ni listas de definiciones
- NO muestres apuntes ni material de referencia al inicio
- Escribe en PÁRRAFOS, no en listas (excepto el mapa de puntos)
- Máximo 150 palabras total
- Termina con pregunta simple que invite a empezar

## Ejemplo de salida

Hoy vamos a explorar cómo funcionan los modelos de lenguaje por dentro. Es fundamental entender esto para poder usarlos de forma efectiva y saber cuándo confiar en ellos.

Al terminar, serás capaz de explicar cómo un modelo procesa texto y genera respuestas.

Veremos estos puntos:
1. Tokenización y vocabulario
2. Embeddings y representación
3. Mecanismo de atención
4. Generación de texto

¿Empezamos?
