# Sistema RAG - Chatbot VOAE

Sistema completo de Recuperación Aumentada por Generación (RAG) para la Vicerrectoría de Orientación y Asuntos Estudiantiles (VOAE).

**Tecnologías:**
- BGE-M3 para generar embeddings semánticos (1024 dimensiones)
- ChromaDB para almacenamiento vectorial con HNSW
- Groq API (ultra-rápido, Llama 3.3 70B) o DeepSeek API como modelo de lenguaje
- Sistema FAQ híbrido con umbrales dobles para respuestas precisas
- Interfaz web moderna con FastAPI y React

## Tabla de Contenidos

- [Características](#características)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Instalación](#instalación)
- [Uso](#uso)
  - [Interfaz Web](#interfaz-web)
  - [Chatbot de Consola](#chatbot-de-consola)
  - [CLI](#cli)
- [Sistema FAQ Híbrido](#sistema-faq-híbrido)
- [Arquitectura Técnica](#arquitectura-técnica)
- [API REST](#api-rest)
- [Troubleshooting](#troubleshooting)
- [Deployment](#deployment)

## Características

- Procesamiento de documentos Markdown (.md)
- Generación de embeddings con BGE-M3
- Almacenamiento vectorial en ChromaDB (sin configuración, persistencia automática)
- Búsqueda semántica con similitud coseno y HNSW
- **Sistema FAQ híbrido** con clasificación automática de consultas
- **Groq API con Llama 3.3 70B** (ultra-rápido, 10-20x más rápido que alternativas)
- Alternativa DeepSeek API
- **Interfaz web moderna** con FastAPI (backend) y React (frontend)
- **Chatbot interactivo por consola** con historial de conversación
- Modo de consultas únicas CLI
- División opcional de documentos en chunks
- Manejo robusto de errores

## Estructura del Proyecto

```
LLAMA_BGE_CHATBOT/
│
├── api/                      # Backend FastAPI
│   ├── __init__.py
│   └── main.py              # API REST con endpoints
│
├── frontend/                 # Frontend React
│   ├── src/
│   │   ├── App.jsx          # Componente principal
│   │   ├── App.css          # Estilos modernos
│   │   ├── main.jsx         # Entry point
│   │   └── index.css        # Estilos globales
│   ├── index.html
│   ├── package.json
│   └── vite.config.js       # Configuración Vite
│
├── data/
│   ├── docs/                # Archivos .md para ingestion
│   │   └── faq/             # FAQs (subcarpeta especial)
│   └── chroma/              # Base de datos ChromaDB (auto-generado)
│
├── src/
│   ├── embeddings/
│   │   └── embedder.py      # Generación de embeddings BGE-M3
│   ├── database/
│   │   ├── chroma_vector_store.py  # ChromaDB storage
│   │   └── repository.py    # Operaciones CRUD
│   ├── ingestion/
│   │   └── ingest_docs.py   # Carga y preprocesamiento
│   ├── rag/
│   │   ├── retriever.py     # Búsqueda semántica
│   │   ├── rag_pipeline.py  # Pipeline completo
│   │   └── faq_handler.py   # Sistema FAQ híbrido
│   ├── llm/
│   │   ├── groq_client.py      # Cliente Groq API (recomendado)
│   │   └── deepseek_client.py  # Cliente DeepSeek API
│   ├── chatbot/
│   │   └── chatbot.py       # Chatbot con historial
│   ├── chat.py              # Chatbot interactivo de consola
│   └── main.py              # Punto de entrada CLI
│
├── .env.example             # Template de variables de entorno
├── requirements.txt         # Dependencias
├── README.md                # Esta documentación
└── CLAUDE.md                # Guía para Claude Code
```

## Instalación

### 1. Clonar o descargar el proyecto

```bash
git clone <tu-repo>
cd LLAMA_BGE_CHATBOT
```

### 2. Crear entorno virtual

```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y configura tu API key:

```bash
cp .env.example .env
```

Edita `.env` con tu API key (solo necesitas una):

```env
# Groq API (ultra-rápido, 14,400 requests/día gratis) - RECOMENDADO
GROQ_API_KEY=tu_groq_api_key_aqui

# DeepSeek API (alternativa más lenta pero buena calidad)
DEEPSEEK_API_KEY=tu_deepseek_api_key_aqui
```

**Obtener API Key de Groq** (Recomendado - Ultra Rápido):
1. Visita [https://console.groq.com/](https://console.groq.com/)
2. Crea una cuenta gratuita
3. Ve a API Keys
4. Genera una nueva API key
5. Cópiala en el archivo `.env` como `GROQ_API_KEY`

**Obtener API Key de DeepSeek** (Alternativa):
1. Visita [https://platform.deepseek.com/](https://platform.deepseek.com/)
2. Crea una cuenta o inicia sesión
3. Ve a la sección de API Keys
4. Genera una nueva API key
5. Cópiala en el archivo `.env` como `DEEPSEEK_API_KEY`

**Comparación de LLMs:**

| Característica | Groq (Recomendado) | DeepSeek |
|----------------|---------|----------|
| **Velocidad** | ~200-500ms | ~1-3 segundos |
| **Gratis/día** | 14,400 requests | Según plan |
| **Modelo** | Llama 3.3 70B | DeepSeek-Chat |
| **Calidad** | Excelente | Muy buena |

### 5. Preparar documentos

Coloca tus archivos `.md` en la carpeta `data/docs/`:

```bash
mkdir -p data/docs
mkdir -p data/docs/faq
# Copia tus archivos .md a data/docs/
# Copia tus FAQs a data/docs/faq/
```

### 6. Ingerir documentos

```bash
# Ingestion básica
python src/main.py --ingest

# O con chunks para documentos grandes
python src/main.py --ingest --chunk
```

## Uso

### Interfaz Web

La forma más moderna y recomendada de usar el sistema es a través de la interfaz web.

#### Requisitos Adicionales
- Node.js 16+ (para frontend)
- npm o yarn

#### Iniciar Backend (FastAPI)

```bash
# Activar entorno virtual
source venv/bin/activate

# Iniciar servidor FastAPI
cd api
python main.py
```

El backend estará disponible en:
- API: http://localhost:8000
- Documentación interactiva: http://localhost:8000/docs

#### Iniciar Frontend (React)

En otra terminal:

```bash
# Ir al directorio frontend
cd frontend

# Instalar dependencias (solo primera vez)
npm install

# Iniciar servidor de desarrollo
npm run dev
```

El frontend estará disponible en: http://localhost:5173 o http://localhost:3000

#### Características de la Interfaz Web

**Backend (FastAPI):**
- API REST completa
- Endpoints documentados automáticamente (Swagger)
- Manejo de sesiones múltiples
- CORS configurado
- Manejo de errores robusto

**Frontend (React + Vite):**
- Diseño moderno y responsivo
- Tema gradiente morado (VOAE branding)
- Mensajes en tiempo real
- Indicador de escritura
- Visualización de match type (FAQ/Docs)
- Fuentes de información mostradas
- Panel de estadísticas
- Historial de conversación
- Preguntas de ejemplo clickeables
- Auto-scroll suave
- Teclado shortcuts (Enter/Shift+Enter)

#### Flujo de Uso Web

1. Usuario abre la web y ve mensaje de bienvenida
2. Hace una pregunta que se envía al backend FastAPI
3. Backend procesa usando RAGPipeline con sistema FAQ
4. Respuesta generada se muestra con match type y fuentes
5. Historial guardado (últimos 10 mensajes por sesión)

### Chatbot de Consola

Inicia el chatbot interactivo por consola:

```bash
python src/chat.py
```

**Características:**
- Interfaz de chat por consola limpia e intuitiva
- Mantiene historial de los últimos 5 mensajes
- Sistema RAG con búsqueda semántica en documentos
- Sistema FAQ híbrido integrado
- Muestra fuentes consultadas con scores de similitud
- Respuestas ultra-rápidas con Groq (200-500ms)

**Comandos especiales:**
- `salir` o `exit`: Terminar el chat
- `limpiar`: Borrar historial de conversación
- `stats`: Ver estadísticas del sistema

**Ejemplo de uso:**
```
Tú: ¿Qué información tienes sobre becas?

Chatbot VOAE: [Respuesta basada en documentos...]

Match: FAQ (similitud: 84.5%)

Fuentes consultadas:
  1. faq/faq_servicios.md (similitud: 0.845)
  2. becas.md (similitud: 0.234)

Tiempo: 350ms
```

### CLI

#### Consulta única

```bash
python src/main.py --query "¿Qué es Python?"
```

#### Consulta con fuentes

```bash
python src/main.py --query "¿Cómo funciona el sistema?" --show-sources
```

#### Modo interactivo simple

```bash
python src/main.py
```

#### Opciones avanzadas

```bash
# Recuperar más documentos relevantes
python src/main.py --query "tu pregunta" --top-k 5

# Ajustar temperatura del LLM (0.0 = más determinista, 1.0 = más creativo)
python src/main.py --query "tu pregunta" --temperature 0.5

# Combinación de opciones
python src/main.py --query "tu pregunta" --top-k 5 --temperature 0.7 --show-sources

# Usar DeepSeek en lugar de Groq
python src/main.py --query "tu pregunta" --llm-provider deepseek
python src/chat.py --llm-provider deepseek
```

#### Estadísticas

Ver información del sistema:

```bash
python src/main.py --stats
```

#### Limpiar base de datos

Eliminar todos los documentos:

```bash
python src/main.py --reset
```

## Sistema FAQ Híbrido

El sistema utiliza un enfoque híbrido con umbrales dobles para clasificar automáticamente las consultas y proporcionar las mejores respuestas.

### Descripción

Sistema de FAQ con umbrales dobles que combina precisión y cobertura:
- **Umbral Alto (≥75%)**: Match fuerte - Solo FAQs con alta similitud
- **Umbral Medio (65-74%)**: Match medio - FAQs + documentos generales
- **Umbral Bajo (<65%)**: Sin match - Solo documentos generales (flujo original)

### Ventajas

**Precisión Máxima:**
- Respuestas exactas para preguntas con match ≥75%
- Temperature muy baja (0.1) para FAQs exactos
- Prompts especializados que evitan alucinaciones

**Cobertura Amplia:**
- No rechaza preguntas válidas con paráfrasis (65-74%)
- Fallback inteligente a documentos generales
- Sistema híbrido en zona gris (combina FAQs + docs)

**Cero Configuración Adicional:**
- Usa ChromaDB existente (no requiere base de datos separada)
- Embeddings BGE-M3 para similitud semántica
- Aprovecha infraestructura actual

### Arquitectura FAQ

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
  ≥75%    65-74%          <65%      Comando
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

### Componentes FAQ

**FAQHandler (src/rag/faq_handler.py):**

Responsabilidades:
- Clasificar queries según similitud con FAQs
- Determinar tipo de contexto apropiado
- Ajustar temperature según tipo de match

Métodos principales:
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

**Configuración de Umbrales:**

En `src/rag/faq_handler.py`:
```python
class FAQHandler:
    HIGH_THRESHOLD = 0.75   # Match fuerte: Solo FAQs
    MEDIUM_THRESHOLD = 0.65 # Match medio: FAQs + Docs
```

**Cómo ajustar:**
- Aumentar HIGH_THRESHOLD (ej: 0.80) → Más estricto, menos matches fuertes
- Disminuir HIGH_THRESHOLD (ej: 0.70) → Más permisivo, más matches fuertes
- Igual para MEDIUM_THRESHOLD

### Formato de FAQs

Los FAQs deben seguir este formato en archivos markdown dentro de `data/docs/faq/`:

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
- Guardar en subdirectorio `data/docs/faq/`

### Actualizar FAQs

**Agregar nuevos FAQs:**

1. Crear archivo en `data/docs/faq/faq_nuevo_tema.md`
2. Seguir formato estándar
3. Re-ingerir documentos:
   ```bash
   python src/main.py --ingest
   ```

**Modificar FAQs existentes:**

1. Editar archivo correspondiente
2. Re-ingerir forzando actualización:
   ```bash
   python src/main.py --ingest --force
   ```

**Eliminar FAQs:**

1. Borrar archivo de FAQ
2. Limpiar base de datos y re-ingerir:
   ```bash
   python src/main.py --reset
   python src/main.py --ingest
   ```

## Arquitectura Técnica

### Pipeline de Ingestion

1. **Carga de archivos**: Lee archivos `.md` desde `data/docs/` (incluyendo `data/docs/faq/`)
2. **Preprocesamiento**: Limpia el texto (espacios, saltos de línea)
3. **Chunking** (opcional): Divide documentos largos en segmentos
4. **Generación de embeddings**: BGE-M3 crea vectores de 1024 dimensiones (float32)
5. **Almacenamiento**: Guarda en ChromaDB con persistencia automática

### Pipeline de Consulta

1. **Embedding de consulta**: Convierte la pregunta en vector (1024-dim)
2. **Clasificación FAQ**: FAQHandler determina tipo de match (high/medium/low)
3. **Búsqueda contextual**: Recupera FAQs y/o documentos según match type
4. **Ajuste de temperatura**: Selecciona temperatura apropiada (0.1-0.3)
5. **Generación RAG**: Envía contexto + pregunta a Groq/DeepSeek con prompt especializado
6. **Respuesta**: Retorna respuesta basada en contexto con metadata

### ChromaDB - Vector Database

**Por qué ChromaDB:**
- Zero configuración requerida - no necesita servidor
- Diseñado específicamente para embeddings
- Algoritmo HNSW (Hierarchical Navigable Small World) para búsqueda rápida
- Persistencia automática a disco
- Metadata integrada con vectores
- Excelente para desarrollo y producción
- Base de datos embebida - sin procesos externos

**Detalles técnicos:**
- **Ubicación**: `data/chroma/` (creado automáticamente)
- **Colección**: `documents`
- **Métrica**: Cosine similarity
- **Índice**: HNSW
- **Dimensiones**: 1024 (BGE-M3)

## API REST

### Endpoints Disponibles

**POST /chat**
Envía mensaje al chatbot y recibe respuesta.

Request:
```json
{
  "message": "¿Cómo solicito una beca?",
  "session_id": "session-123",
  "top_k": 4,
  "temperature": 0.7
}
```

Response:
```json
{
  "answer": "Para solicitar una beca, debes seguir estos pasos...",
  "session_id": "session-123",
  "match_type": "high",
  "best_faq_similarity": 0.89,
  "context_type": "faq_only",
  "relevant_documents": [
    {
      "filename": "faq/faq_servicios.md",
      "similarity": 0.89,
      "type": "faq"
    }
  ],
  "timestamp": "2024-01-15T10:30:00"
}
```

**GET /stats**
Obtiene estadísticas del sistema.

Response:
```json
{
  "total_documents": 10,
  "storage_path": "data/chroma",
  "embedder_model": "BAAI/bge-m3",
  "llm_model": "llama-3.3-70b-versatile",
  "max_history": 10,
  "current_history_length": 3
}
```

**GET /history?session_id={id}**
Ver historial de conversación de una sesión.

**POST /clear-history?session_id={id}**
Limpiar historial de una sesión.

**DELETE /session/{id}**
Eliminar una sesión.

**GET /sessions**
Listar sesiones activas.

### Probar API con curl

```bash
# Enviar mensaje
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Cómo solicito una beca?", "session_id": "test"}'

# Ver estadísticas
curl "http://localhost:8000/stats?session_id=test"

# Limpiar historial
curl -X POST "http://localhost:8000/clear-history?session_id=test"
```

### Integrar con JavaScript

```javascript
// Enviar mensaje al chatbot
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: '¿Cómo solicito una beca?',
    session_id: 'mi-sesion'
  })
});

const data = await response.json();
console.log(data.answer);
```

### Configuración Avanzada API

**Cambiar Puerto del Backend:**

Edita `api/main.py`:
```python
uvicorn.run(
    app,
    host="127.0.0.1",
    port=8080,  # Cambiar aquí
    log_level="info"
)
```

**Cambiar Puerto del Frontend:**

Edita `frontend/vite.config.js`:
```javascript
server: {
  port: 5173,  // Cambiar aquí
}
```

## Troubleshooting

### Error: "GROQ_API_KEY no está configurada"

- Asegúrate de tener el archivo `.env` en la raíz del proyecto
- Verifica que la API key sea válida
- Copia `.env.example` a `.env` si no existe

### Error: "No hay documentos en la base de datos"

- Ejecuta primero `python src/main.py --ingest`
- Verifica que haya archivos `.md` en `data/docs/`

### El modelo BGE-M3 se descarga muy lento

- El modelo pesa ~2GB, la primera vez tomará tiempo
- Se descarga automáticamente en `~/.cache/huggingface/`
- Solo se descarga una vez

### Errores de memoria con BGE-M3

- Cierra otras aplicaciones
- Reduce el tamaño de los documentos usando `--chunk`

### ChromaDB: Error de persistencia

- Elimina la carpeta `data/chroma/` y vuelve a ejecutar `--ingest`
- Verifica permisos de escritura en `data/`

### Backend no inicia

```bash
# Verificar que FastAPI esté instalado
pip install fastapi uvicorn

# Verificar que el puerto 8000 esté libre
lsof -i :8000

# Matar proceso en puerto 8000
lsof -ti:8000 | xargs kill -9
```

### Frontend no conecta al backend

1. Verifica que el backend esté corriendo en http://localhost:8000
2. Revisa la consola del navegador para errores CORS
3. Confirma que CORS esté configurado en `api/main.py`

### Error de CORS

El backend ya tiene CORS configurado para `localhost:3000` y `localhost:5173`.
Si usas otro puerto, agrégalo en `api/main.py`:

```python
allow_origins=["http://localhost:3000", "http://localhost:TU_PUERTO"]
```

### Todas las queries son LOW match

**Causa:** Los FAQs no fueron ingeridos correctamente.

**Solución:**
```bash
# Verificar que los FAQs existen
ls data/docs/faq/

# Re-ingerir forzando actualización
python src/main.py --ingest --force
```

### Similitudes FAQ son muy bajas (<70%)

**Causa:** Modelo BGE-M3 no descargado o preguntas muy diferentes.

**Solución:**
- Verifica que BGE-M3 esté en `~/.cache/huggingface/`
- Revisa el formato de tus FAQs
- Agrega más variantes de preguntas en los FAQs

## Deployment

### Producción - Backend (FastAPI)

```bash
# Instalar gunicorn
pip install gunicorn

# Ejecutar en producción
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Producción - Frontend (React)

```bash
# Build para producción
cd frontend
npm run build

# Preview del build
npm run preview

# O servir con nginx/apache
```

### Heroku (Backend)

```bash
# Crear Procfile
echo "web: gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker" > Procfile

# Deploy
heroku create tu-app-voae
git push heroku main
```

### Vercel/Netlify (Frontend)

```bash
# Build command
npm run build

# Output directory
dist

# Deploy
vercel deploy
# o
netlify deploy --prod
```

## Testing de Módulos Individuales

Cada módulo puede ejecutarse de forma independiente para testing:

```bash
# Test de embeddings
python src/embeddings/embedder.py

# Test de ChromaDB
python src/database/chroma_vector_store.py

# Test de ingestion
python src/ingestion/ingest_docs.py

# Test de Groq client
python src/llm/groq_client.py

# Test de DeepSeek client
python src/llm/deepseek_client.py

# Test de retriever
python src/rag/retriever.py

# Test de chatbot
python src/chatbot/chatbot.py

# Test de FAQ handler
python src/rag/faq_handler.py
```

## Requisitos del Sistema

- **Python**: 3.8 o superior
- **Node.js**: 16+ (solo para interfaz web)
- **RAM**: Mínimo 4GB (recomendado 8GB para BGE-M3)
- **Espacio en disco**: ~2GB para el modelo BGE-M3
- **Internet**: Solo para primera descarga del modelo y llamadas API

## Ejemplo de Uso Completo

```bash
# 1. Configurar entorno
cp .env.example .env
# Editar .env con tu GROQ_API_KEY

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Agregar documentos
echo "# Python\nPython es un lenguaje de programación." > data/docs/python.md
echo "# SQL\nSQL es un lenguaje de consultas." > data/docs/sql.md

# 4. Agregar FAQs
mkdir -p data/docs/faq
cat > data/docs/faq/faq_ejemplo.md << 'EOF'
# FAQ - Ejemplo

## Pregunta 1: ¿Qué es Python?

**Pregunta:** ¿Qué es Python? / ¿Para qué sirve Python?

**Respuesta:** Python es un lenguaje de programación de alto nivel, interpretado y de propósito general.
EOF

# 5. Ingerir documentos
python src/main.py --ingest

# 6. Opción A: Iniciar interfaz web
# Terminal 1:
cd api && python main.py
# Terminal 2:
cd frontend && npm install && npm run dev

# 6. Opción B: Iniciar chatbot de consola
python src/chat.py

# 6. Opción C: Hacer consultas directas
python src/main.py --query "¿Qué es Python?" --show-sources
```

## Ventajas de esta Implementación

**Groq API:**
- 10-20x más rápido que alternativas
- Modelo Llama 3.3 70B de alta calidad
- Fácil cambio a DeepSeek si lo necesitas

**BGE-M3:**
- Modelo multilingüe (español, inglés, etc.)
- 1024 dimensiones (buen balance)
- Estado del arte en embeddings
- Completamente gratuito

**Sistema FAQ Híbrido:**
- Alta precisión en matches fuertes (≥75%)
- Cobertura amplia con zona media (65-74%)
- Fallback robusto a documentos generales (<65%)
- Cero alucinaciones con prompts estrictos
- Fácil mantenimiento de FAQs (archivos markdown)

**Interfaz Web:**
- Moderna y responsiva
- Experiencia de usuario superior
- Manejo de sesiones múltiples
- Visualización clara de fuentes y match types

## Licencia

MIT License - Siéntete libre de usar este código.

## Enlaces Útiles

- [BGE-M3 en Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [Groq Console](https://console.groq.com/)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
