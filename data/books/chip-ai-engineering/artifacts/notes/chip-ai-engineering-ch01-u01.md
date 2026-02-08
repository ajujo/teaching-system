# Apuntes — AI Engineering — Ch1 — Introducción a la creación de (Parte 1/3)

## Resumen
- **Tokenización**: Proceso que divide textos en tokens para optimizar el vocabulario y mejorar la eficiencia computacional.  
- **Modelos lingüísticos**: Dos tipos principales: *enmascarados* (predicción de tokens faltantes con contexto bidireccional) y *autorregresivos* (generación secuencial basada en tokens anteriores).  
- **Salidas probabilísticas**: Los modelos generan combinaciones posibles según probabilidades, permitiendo tareas como traducción o resumen mediante completado.  
- **Autosupervisión**: Técnica que elimina la necesidad de datos etiquetados manualmente al usar el contexto del input como referente implícito (ej.: tokens en textos).  
- **Expansión multimodal**: Los LLMs evolucionan a modelos fundacionales que procesan múltiples modalidades (texto, imágenes, audio) con entrenamiento generalizado.  
- **Escala de parámetros**: El tamaño de los modelos ha crecido exponencialmente desde GPT-1 hasta 100 mil millones de parámetros en arquitecturas modernas.  
- **Ingeniería de prompts**: Técnica para personalizar salidas generativas mediante instrucciones detalladas y datos externos.

---

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| Tokenización | División del texto en unidades significativas (tokens) que reducen el vocabulario y optimizan la eficiencia. |
| Modelo lingüístico enmascarado | Predice tokens faltantes usando contexto bidireccional; usado para tareas no generativas como clasificación. |
| Modelo lingüístico autorregresivo | Genera texto secuencialmente, prediciendo el siguiente token basándose en los anteriores (ej.: GPT). |
| Autossupervisión | Técnica que infiere etiquetas desde el propio input sin necesidad de anotación manual. |
| Modelos fundacionales | Arquitecturas multimodales capaces de procesar múltiples tipos de datos y servir como base para aplicaciones específicas. |
| Incrustación conjunta | Representación vectorial que vincula semánticamente diferentes modalidades (ej.: texto e imágenes en CLIP). |

---

## Explicación paso a paso
### 1. Tokenización y vocabulario
- **Tokenización**: Los modelos dividen el texto en tokens para reducir la complejidad computacional.
- **Vocabulario**: El tamaño varía entre modelos (32k en *Mixtral* vs. 100k+ en *GPT-4*), afectando su capacidad de representación.

### 2. Tipos de modelos lingüísticos
- **Enmascarados**:
  - Procesan contextos bidireccionales (ej.: BERT).
  - Usados para tareas como clasificación o respuesta a preguntas.
- **Autorregresivos**:
  - Generan texto secuencialmente (ej.: GPT, Llama).
  - Predicen el siguiente token basándose en tokens previos.

### 3. Autossupervisión y entrenamiento
- **Autossupervisión**: Los modelos aprenden sin datos etiquetados mediante:
  - Inferencia de contexto implícito (ej.: predicción de tokens faltantes).
  - Uso de grandes corpora no anotados (ej.: Internet, imágenes no etiquetadas).

### 4. Expansión a multimodalidad
- **Modelos multimodales**:
  - Procesan múltiples modalidades (texto, imágenes, audio) con incrustaciones conjuntas.
  - Ejemplos: *CLIP* (400M duplas imagen-texto), *Flamingo*, *Gemini*.

### 5. Modelos fundacionales y usos generales
- **Modelos fundacionales**:
  - Reemplazan a modelos específicos al realizar múltiples tareas gracias a su entrenamiento generalizado.
  - Ejemplos: LLMs grandes con escala de parámetros (GPT-1 → 100T+).

---

## Mini-ejemplo
**CLIP y autosupervisión**:  
El modelo *CLIP* se entrena con 400M de duplas imagen-texto no anotadas manualmente. Al procesar una imagen, genera embeddings que capturan su relación semántica con textos asociados (ej.: "gato" + imagen de un gato). Esto permite tareas como búsqueda de imágenes mediante texto o clasificación multimodal sin supervisión explícita.

---

## Preguntas de repaso
1. ¿Cuál es la diferencia entre modelos lingüísticos enmascarados y autorregresivos?  
2. ¿Cómo reduce la tokenización la complejidad computacional en los LLMs?  
3. Explique el concepto de "incrustación conjunta" y su importancia en modelos multimodales.  
4. ¿Por qué la autosupervisión es una ventaja clave para entrenar modelos fundacionales?  
5. ¿Qué desafíos resuelve la expansión a modelos multimodales en IA?

---

## Fuentes
Páginas utilizadas: 26-61