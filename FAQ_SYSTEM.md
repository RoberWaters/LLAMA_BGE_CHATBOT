# Sistema FAQ Híbrido - Opción A (Umbrales Dobles 90%/80%)

## 📋 Descripción

Sistema de FAQ con umbrales dobles que combina precisión y cobertura:
- **Umbral Alto (≥90%)**: Match fuerte - Solo FAQs con alta similitud
- **Umbral Medio (80-89%)**: Match medio - FAQs + documentos generales
- **Umbral Bajo (<80%)**: Sin match - Solo documentos generales (flujo original)

## 🎯 Ventajas de esta Implementación

### ✅ Precisión Máxima
- Respuestas exactas para preguntas con match ≥90%
- Temperature muy baja (0.1) para FAQs exactos
- Prompts especializados que evitan alucinaciones

### ✅ Cobertura Amplia
- No rechaza preguntas válidas con paráfrasis (80-89%)
- Fallback inteligente a documentos generales
- Sistema híbrido en zona gris (combina FAQs + docs)

### ✅ Cero Configuración Adicional
- Usa ChromaDB existente (no requiere base de datos separada)
- Embeddings BGE-M3 para similitud semántica
- Aprovecha infraestructura actual

## 🏗️ Arquitectura del Sistema

```
Usuario ingresa pregunta
       ↓
┌──────────────────┐
│  FAQ Handler     │
│  Clasifica query │
└────────┬─────────┘
         ↓
    Similitud?
         ↓
    ┌────┴────┬─────────────┬──────────┐
    ↓         ↓             ↓          ↓
  ≥90%    80-89%          <80%      Comando
  HIGH    MEDIUM           LOW       (skip FAQ)
    ↓         ↓             ↓          ↓
Top-3   Top-2 FAQs     Top-K docs   Flujo
FAQs    + Top-2 docs   (original)    normal
    ↓         ↓             ↓          ↓
Temp=0.1  Temp=0.2      Temp=0.3     -
    ↓         ↓             ↓          ↓
Prompt    Prompt        Prompt       -
FAQ-only  Hybrid        Docs-only    -
    ↓         ↓             ↓          ↓
    └─────────┴─────────────┴──────────┘
                ↓
          LLM (Groq/DeepSeek)
                ↓
            Respuesta
```

## 📁 Estructura de Archivos

### Módulos Nuevos
```
src/rag/faq_handler.py          # Lógica principal de clasificación
```

### Módulos Modificados
```
src/rag/rag_pipeline.py         # Agregado query_with_faq()
src/llm/groq_client.py          # Prompts especializados por context_type
src/llm/deepseek_client.py      # Prompts especializados por context_type
src/chatbot/chatbot.py          # Usa query_with_faq() en lugar de query()
src/chat.py                     # Visualización de match types
```

### Documentos FAQ
```
data/docs/faq/
  ├── faq_inscripciones.md      # 4 FAQs sobre inscripciones
  ├── faq_examenes.md           # 4 FAQs sobre exámenes
  └── faq_servicios.md          # 4 FAQs sobre servicios
```

## 🔧 Componentes Clave

### 1. FAQHandler (`src/rag/faq_handler.py`)

**Responsabilidades:**
- Clasificar queries según similitud con FAQs
- Determinar tipo de contexto apropiado
- Ajustar temperature según tipo de match

**Métodos principales:**
```python
classify_query(query, top_k=5) -> dict
    # Retorna: {'match_type': 'high'|'medium'|'low',
    #           'faq_results': [...],
    #           'best_similarity': 0.95}

get_context_for_llm(query, match_type, faq_results, doc_results) -> tuple
    # Retorna: (context_documents, context_type)

get_temperature_for_context(context_type) -> float
    # Retorna: 0.1 (faq_only), 0.2 (faq_and_docs), 0.3 (docs_only)
```

### 2. RAGPipeline - Método Nuevo

**`query_with_faq()`** - Flujo completo:
```python
def query_with_faq(question, top_k=3, temperature=0.7, enable_faq=True):
    """
    1. Clasificar query en FAQs
    2. Obtener documentos según match_type
    3. Preparar contexto apropiado
    4. Ajustar temperature
    5. Generar respuesta con LLM
    6. Retornar con metadata (match_type, best_similarity)
    """
```

### 3. Prompts Especializados

**FAQ Only (High Match ≥90%):**
```python
system_prompt = """Eres un asistente de FAQ universitario.
REGLAS ESTRICTAS:
1. Responde ÚNICAMENTE usando las FAQs proporcionadas
2. Si la pregunta coincide con una FAQ, usa EXACTAMENTE la respuesta
3. NO combines información de múltiples FAQs a menos que sea necesario
4. NO inventes información ni uses conocimiento externo
5. Sé conciso y directo
"""
```

**FAQ + Docs (Medium Match 80-89%):**
```python
system_prompt = """Eres un asistente universitario.
REGLAS:
1. Tienes FAQs y documentos adicionales
2. PRIORIZA las FAQs si responden la pregunta
3. Usa los documentos solo si las FAQs no son suficientes
4. NO inventes información
"""
```

**Docs Only (Low Match <80%):**
```python
system_prompt = """Eres un asistente útil que responde basándose
ÚNICAMENTE en el contexto proporcionado.
Si la información no está en el contexto, di claramente que no tienes esa información.
"""
```

## 📊 Configuración de Umbrales

En `src/rag/faq_handler.py`:
```python
class FAQHandler:
    HIGH_THRESHOLD = 0.90   # Match fuerte: Solo FAQs
    MEDIUM_THRESHOLD = 0.80 # Match medio: FAQs + Docs
```

**¿Cómo ajustar?**
- Aumentar HIGH_THRESHOLD (ej: 0.92) → Más estricto, menos matches fuertes
- Disminuir HIGH_THRESHOLD (ej: 0.88) → Más permisivo, más matches fuertes
- Igual para MEDIUM_THRESHOLD

## 🚀 Uso del Sistema

### Opción 1: Chatbot Interactivo (Recomendado)

```bash
# Activar entorno virtual
source venv/bin/activate

# Ingerir documentos (incluye FAQs)
python src/main.py --ingest

# Iniciar chatbot
python src/chat.py
```

**Salida esperada:**
```
🧑 Tú: ¿Cómo me inscribo a la universidad?

🤖 Chatbot: Para inscribirte a la universidad debes...

🎯 Match: FAQ (similitud: 94.2%)

📚 Fuentes consultadas:
  1. ❓ faq_inscripciones.md (similitud: 94.2%)
  2. ❓ faq_inscripciones.md (similitud: 87.3%)
```

### Opción 2: Consultas Directas

```bash
python src/main.py --query "¿Cuándo son los exámenes finales?"
```

### Opción 3: Desde Código

```python
from rag.rag_pipeline import RAGPipeline

# Inicializar pipeline
pipeline = RAGPipeline(llm_provider="groq")

# Consulta con FAQ
result = pipeline.query_with_faq(
    question="¿Cómo me inscribo?",
    top_k=3,
    enable_faq=True
)

print(f"Respuesta: {result['answer']}")
print(f"Match type: {result['match_type']}")  # 'high', 'medium', 'low'
print(f"Best FAQ similarity: {result['best_faq_similarity']:.2%}")
```

## 📝 Formato de FAQs

Los FAQs deben seguir este formato en archivos markdown:

```markdown
# FAQ - Título del Tema

## Pregunta 1: Título descriptivo

**Pregunta:** ¿Pregunta principal? / ¿Variante 1? / ¿Variante 2?

**Respuesta:** Respuesta clara y concisa a la pregunta.
Puede tener múltiples párrafos si es necesario.

---

## Pregunta 2: Otro título

**Pregunta:** ¿Otra pregunta?

**Respuesta:** Otra respuesta...
```

**Buenas prácticas:**
- Incluir variantes de la pregunta después de `/`
- Respuestas concisas pero completas
- Un tema por archivo (ej: `faq_inscripciones.md`)
- Separar preguntas con `---`

## 🧪 Casos de Prueba

### High Match (≥90% - Solo FAQs)

```python
test_queries_high = [
    "¿Cómo me inscribo a la universidad?",
    "¿Cuándo abren las inscripciones?",
    "¿Qué documentos necesito para inscribirme?",
    "¿Cuánto cuesta la matrícula?",
    "¿Cuándo son los exámenes finales?",
]
```

**Resultado esperado:**
- Match type: `high`
- Temperature: `0.1`
- Contexto: Top-3 FAQs solamente
- Similitud: ≥90%

### Medium Match (80-89% - FAQs + Docs)

```python
test_queries_medium = [
    "¿Cuál es el proceso de inscripción?",  # Paráfrasis de "¿Cómo me inscribo?"
    "¿En qué fecha inician las inscripciones?",  # Paráfrasis
    "¿Cuáles son los requisitos?",  # Más general
]
```

**Resultado esperado:**
- Match type: `medium`
- Temperature: `0.2`
- Contexto: Top-2 FAQs + Top-2 docs generales
- Similitud: 80-89%

### Low Match (<80% - Solo Docs)

```python
test_queries_low = [
    "¿Qué información tienes sobre becas?",
    "Háblame de las menciones honoríficas",
    "¿Qué programas académicos ofrecen?",
]
```

**Resultado esperado:**
- Match type: `low`
- Temperature: `0.3`
- Contexto: Solo documentos generales (flujo original)
- Similitud: <80%

## ⚙️ Configuración Avanzada

### Ajustar número de FAQs/Docs por match type

En `src/rag/faq_handler.py`, método `get_context_for_llm()`:

```python
# HIGH MATCH - Cambiar de top-3 a top-5 FAQs
context = [content for _, content, _ in faq_results[:5]]  # Era [:3]

# MEDIUM MATCH - Cambiar balance FAQs/Docs
faq_context = [content for _, content, _ in faq_results[:3]]  # Era [:2]
doc_context = [content for _, content, _ in doc_results[:1]]  # Era [:2]
```

### Cambiar temperatures

En `src/rag/faq_handler.py`, método `get_temperature_for_context()`:

```python
temperatures = {
    'faq_only': 0.05,      # Más determinista (era 0.1)
    'faq_and_docs': 0.3,   # Más creativo (era 0.2)
    'docs_only': 0.4       # Más flexible (era 0.3)
}
```

### Deshabilitar FAQs temporalmente

```python
result = pipeline.query_with_faq(
    question="Tu pregunta",
    enable_faq=False  # Fuerza uso de documentos generales
)
```

## 🐛 Troubleshooting

### Problema: Todas las queries son LOW match

**Causa:** Los FAQs no fueron ingeridos correctamente.

**Solución:**
```bash
# Verificar que los FAQs existen
ls data/docs/faq/

# Re-ingerir forzando actualización
python src/main.py --ingest --force
```

### Problema: Similitudes son muy bajas (<70%)

**Causa:** Modelo BGE-M3 no descargado o preguntas muy diferentes.

**Solución:**
- Verifica que BGE-M3 esté en `~/.cache/huggingface/`
- Revisa el formato de tus FAQs
- Agrega más variantes de preguntas en los FAQs

### Problema: Respuestas inventan información

**Causa:** Temperature muy alta o prompts no suficientemente estrictos.

**Solución:**
- Reduce temperature en `faq_handler.py`
- Verifica que `context_type` se pase correctamente al LLM
- Revisa los prompts en `groq_client.py` o `deepseek_client.py`

## 📈 Métricas y Monitoreo

El sistema retorna metadata útil para monitoreo:

```python
result = pipeline.query_with_faq(question)

# Métricas disponibles
match_type = result['match_type']  # 'high', 'medium', 'low'
best_similarity = result['best_faq_similarity']  # 0.0-1.0
context_type = result['context_type']  # 'faq_only', 'faq_and_docs', 'docs_only'
relevant_docs = result['relevant_documents']  # Lista con fuentes
```

**Ejemplo de logging:**
```python
print(f"Query: {question}")
print(f"Match: {match_type} ({best_similarity:.1%})")
print(f"Context: {context_type}")
print(f"Sources: {len(relevant_docs)}")
```

## 🔄 Actualizar FAQs

### Agregar nuevos FAQs

1. Crear archivo en `data/docs/faq/faq_nuevo_tema.md`
2. Seguir formato estándar (ver sección "Formato de FAQs")
3. Re-ingerir documentos:
   ```bash
   python src/main.py --ingest
   ```

### Modificar FAQs existentes

1. Editar archivo correspondiente
2. Re-ingerir forzando actualización:
   ```bash
   python src/main.py --ingest --force
   ```

### Eliminar FAQs

1. Borrar archivo de FAQ
2. Limpiar base de datos y re-ingerir:
   ```bash
   python src/main.py --reset
   python src/main.py --ingest
   ```

## 💡 Mejoras Futuras Sugeridas

### 1. Cache de FAQs frecuentes
```python
# Guardar en memoria los FAQs más consultados
faq_cache = {}  # {query_hash: (answer, similarity)}
```

### 2. Feedback de usuarios
```python
# Agregar sistema de "¿Te fue útil esta respuesta?"
result['useful'] = user_feedback()  # True/False
# Log para analizar qué FAQs necesitan mejora
```

### 3. Re-ranking con cross-encoder
```python
# Después de BGE-M3, re-rankear con modelo más preciso
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(query, faq) for faq in faq_results])
```

### 4. Detección de preguntas fuera de alcance
```python
# Si best_similarity < 60%, sugerir contactar soporte
if best_similarity < 0.60:
    return "Esta pregunta está fuera de mi alcance. Por favor contacta a..."
```

## 📞 Soporte

Si encuentras problemas o tienes sugerencias:

1. Revisa la sección Troubleshooting
2. Verifica los logs en consola
3. Prueba con `enable_faq=False` para verificar si es problema de FAQs
4. Revisa que ChromaDB tenga documentos: `python src/main.py --stats`

## 🎓 Conclusión

Este sistema FAQ híbrido con umbrales dobles (90%/80%) ofrece el **mejor balance entre precisión y cobertura**:

- ✅ **Alta precisión** en matches fuertes (≥90%)
- ✅ **Cobertura amplia** con zona media (80-89%)
- ✅ **Fallback robusto** a documentos generales (<80%)
- ✅ **Cero alucinaciones** con prompts estrictos
- ✅ **Fácil mantenimiento** de FAQs (archivos markdown)

**¡Tu sistema está listo para producción!** 🚀
