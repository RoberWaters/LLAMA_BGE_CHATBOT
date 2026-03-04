# Chatbot VOAE — Sistema RAG con Voz

Chatbot con inteligencia artificial para la **Vicerrectoría de Orientación y Asuntos Estudiantiles (VOAE)** de la UNAH. Combina recuperación semántica de documentos (RAG) con un sistema FAQ híbrido, transcripción de voz y síntesis de audio, todo sobre servicios AWS.

---

## Tabla de Contenidos

- [Stack Tecnológico](#stack-tecnológico)
- [Arquitectura General](#arquitectura-general)
- [Modelo de Embeddings: Titan V2](#modelo-de-embeddings-titan-v2)
- [Base de Datos Vectorial: ChromaDB](#base-de-datos-vectorial-chromadb)
- [Sistema FAQ Híbrido](#sistema-faq-híbrido)
- [Pipeline de Audio](#pipeline-de-audio)
- [Frontend](#frontend)
- [API REST](#api-rest)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Comandos de Desarrollo](#comandos-de-desarrollo)
- [Troubleshooting](#troubleshooting)

---

## Stack Tecnológico

| Capa | Tecnología | Función |
|---|---|---|
| **LLM** | Amazon Bedrock — Claude 3.5 Haiku | Generación de respuestas |
| **Embeddings** | Amazon Bedrock — Titan Embeddings V2 | Vectorización semántica |
| **Vector DB** | ChromaDB (local) | Almacenamiento y búsqueda HNSW |
| **STT** | Amazon Transcribe Streaming | Transcripción de voz a texto |
| **TTS** | Amazon Polly — Lupe (neural) | Síntesis de voz en MP3 |
| **Backend** | FastAPI + Uvicorn | API REST + SSE streaming |
| **Frontend** | React 18 + Vite | Interfaz de usuario |

Todos los servicios de IA (LLM, embeddings, STT, TTS) se consumen vía AWS. No se requieren modelos locales.

---

## Arquitectura General

### Flujo de una Consulta de Chat

```
Usuario escribe o habla
         │
         ▼
[Frontend React]
  • Texto → POST /chat-stream (SSE)
  • Audio → POST /transcribe → texto → POST /chat-stream
         │
         ▼
[FastAPI api/main.py]
  get_chatbot(session_id) → RAGChatbot (instancia por sesión)
         │
         ▼
[RAGChatbot.chat()]
  1. Filtra historial fiable (excluye turnos sin docs)
  2. → RAGPipeline.query_with_faq()
         │
         ▼
[RAGPipeline.query_with_faq()]
  1. Detecta si es pregunta de seguimiento → enriquece query
  2. FAQHandler.classify_query() → HIGH / MEDIUM / LOW
  3. DocumentRetriever.retrieve_relevant_documents() si LOW/MEDIUM
  4. FAQHandler.get_context_for_llm() → documentos de contexto
  5. BedrockClient.generate_response() con historial inyectado
         │
         ▼
[BedrockClient — Claude 3.5 Haiku via Bedrock]
  • System prompt seleccionado por context_type
  • Historial como mensajes alternados user/assistant
  • → respuesta de texto
         │
         ▼
[api/main.py — SSE Generator]
  Por cada oración de la respuesta:
    → preprocess_text_for_tts()
    → PollyClient.synthesize() → MP3 base64
    → SSE event: { type: "chunk", text, audio_base64 }
         │
         ▼
[Frontend]
  • Renderiza texto progresivamente (Markdown)
  • AudioPlayer encola y reproduce chunks MP3 secuencialmente
```

### Wiring de Componentes Python

```
api/main.py
└── RAGChatbot (por sesión, en memoria)
    ├── RAGPipeline
    │   ├── Embedder (Titan V2 via Bedrock, compartido)
    │   ├── ChromaVectorStore → ChromaDB (data/chroma/)
    │   ├── DocumentRepository (CRUD sobre ChromaVectorStore)
    │   ├── DocumentRetriever (búsqueda semántica HNSW)
    │   ├── FAQHandler (clasificación y routing)
    │   └── BedrockClient (Claude 3.5 Haiku)
    └── conversation_history + _history_confidence
```

---

## Modelo de Embeddings: Titan V2

### ¿Qué es Titan Embeddings V2?

**Amazon Titan Embeddings V2** es el modelo de embeddings de texto de AWS disponible en Amazon Bedrock. Está optimizado para búsqueda semántica y recuperación de información en múltiples idiomas, incluyendo español.

Identificador en Bedrock: `amazon.titan-embed-text-v2:0`

### Características Técnicas

| Propiedad | Valor |
|---|---|
| Dimensiones del vector | **1024** float32 (configurable: 256, 512, 1024) |
| Longitud máxima de entrada | **8192 tokens** |
| Idiomas | Multilingüe (incluye español) |
| Normalización | L2 automática |
| Acceso | Via AWS Bedrock (boto3) |

### Por Qué Titan V2 para VOAE

- **Sin modelo local**: no se descarga ni se carga en RAM. Cada embedding es una llamada a la API de Bedrock, eliminando el consumo de 2+ GB de RAM del modelo anterior (BGE-M3).
- **Multilingüe**: maneja español nativo, incluyendo términos técnicos institucionales (VOAE, UNAH, PASEE, PAC).
- **1024 dimensiones**: alta resolución semántica para distinguir matices en documentos del dominio universitario.

### Cómo Funciona la Vectorización

```python
# src/embeddings/embedder.py
response = bedrock.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
)
embedding = response["embedding"]  # → lista float de 1024 dims, norma L2 = 1
```

### Similitud Coseno

Dado que los vectores están normalizados (`|q| = |d| = 1`):

```
similitud(q, d) = q · d   (producto punto)
```

ChromaDB almacena la **distancia coseno** (`distance = 1 - similitud`) y la convierte:

```python
# src/database/chroma_vector_store.py
similarity = 1.0 - distance
```

Un valor de `1.0` es similitud perfecta, `0.0` es ortogonalidad (sin relación semántica).

> **Nota**: al cambiar el modelo de embeddings (ej. de BGE-M3 a Titan V2) es obligatorio re-ingerir todos los documentos con `--force`. Los vectores de distintos modelos son incompatibles.

---

## Base de Datos Vectorial: ChromaDB

### Descripción General

ChromaDB es una base de datos embebida (sin servidor separado) diseñada para almacenar y buscar embeddings. Se ejecuta en el mismo proceso Python y persiste en disco automáticamente.

**Ruta de datos**: `data/chroma/` (relativa a la raíz del proyecto)

### Estructura Física en Disco

```
data/chroma/
└── chroma.sqlite3    ← Metadata, IDs, documentos de texto y embeddings
```

### Esquema Lógico de la Colección

La aplicación usa una **única colección** llamada `documents` con métrica coseno:

```python
self.collection = self.client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"}
)
```

Cada documento almacenado tiene:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` | Identificador único derivado del filename |
| `document` | `string` | Contenido textual completo del archivo `.md` |
| `metadata.filename` | `string` | Ruta original (ej: `faq/faq_servicios.md`) |
| `embedding` | `float32[1024]` | Vector Titan V2 normalizado |

### Distinción FAQs vs. Documentos Generales

FAQs y documentos generales conviven en la misma colección. La separación es por convención de ruta:

- **FAQs**: archivos en `data/docs/faq/` → `filename` comienza con `faq/`
- **Docs generales**: archivos en otras subcarpetas de `data/docs/`

```python
# src/rag/rag_pipeline.py
faq_results = [r for r in all_docs if r[0].startswith('faq/')]
doc_results  = [r for r in all_docs if not r[0].startswith('faq/')]
```

### Documentos Actuales

```
data/docs/
├── about/
│   ├── about.md                      # Información institucional VOAE
│   ├── contacto.md                   # Datos de contacto
│   └── ubicaciones.md                # Ubicaciones físicas
├── areas/
│   └── areas.md                      # Áreas funcionales de VOAE
├── faq/
│   └── faq_servicios.md              # Preguntas frecuentes (FAQ)
└── services/
    ├── Areas_de_VOAE.md
    ├── Area_investigacion.md
    ├── Becas_UNAH.md
    ├── Curso_de_Introducción_Vida_Universitaria.md
    ├── Fechas_Importantes_2026.md
    ├── Feria_vocacional.md
    ├── Honores_Academicos.md
    ├── Horas_VOAE.md
    ├── proceso_readmision.md
    ├── prosene.md
    └── Unidad_Medico_Deportiva.md
```

---

## Sistema FAQ Híbrido

### Motivación

Un chatbot RAG sin FAQs responde con alta latencia y variabilidad en preguntas muy comunes. El sistema FAQ híbrido permite respuestas rápidas y deterministas para las consultas más frecuentes, mientras mantiene la capacidad RAG completa para consultas novedosas.

### Clasificación por Umbrales

Cada consulta es clasificada según la similitud coseno con los documentos FAQ:

```
Similitud FAQ    Tipo de Match    Contexto LLM              Temperature
────────────────────────────────────────────────────────────────────────
≥ 75%            HIGH             Solo top-3 FAQs            0.1
65% – 74%        MEDIUM           Top-2 FAQs + top-2 docs    0.2
< 65%            LOW              Top-K documentos            0.3
```

Los umbrales son configurables vía `.env`:
```env
FAQ_HIGH_THRESHOLD=0.75
FAQ_MEDIUM_THRESHOLD=0.65
```

### Flujo de Clasificación

```
query_with_faq(question, history)
       │
       ├── 1. ¿Es pregunta de seguimiento? (≤6 palabras o empieza con pronombre)
       │        SÍ → enriquecer search_query con último mensaje del historial
       │        NO → usar question directamente
       │
       ├── 2. FAQHandler.classify_query(search_query)
       │        → retrieve_with_threshold(threshold=0.65) en toda la colección
       │        → filtrar solo filename.startswith('faq/')
       │        → clasificar por umbral → HIGH / MEDIUM / LOW
       │
       ├── 3. Si MEDIUM o LOW → retrieve_relevant_documents() (solo no-FAQs)
       │        → filtrar por score >= MIN_SIMILARITY_THRESHOLD (0.3)
       │
       ├── 4. get_context_for_llm() → selecciona documentos y context_type
       │
       ├── 5. get_temperature_for_context() → 0.1 / 0.2 / 0.3
       │
       └── 6. BedrockClient.generate_response(context_type=..., history=...)
```

### Prompts del Sistema LLM

| `context_type` | Comportamiento del LLM |
|---|---|
| `faq_only` | Extremadamente estricto: solo información exacta del FAQ, sin conocimiento externo |
| `faq_and_docs` | Prioriza FAQs, complementa con docs, evita inventar lo que no está |
| `docs_only` | Usa los documentos como única fuente, admite no saber si la info no está |

Los tres prompts comparten restricciones:
- Nunca decir "según el contexto" o "basándome en"
- Persona VOAE: trato de "tú", cálido y profesional
- No omitir fechas, listas o datos específicos

---

## Pipeline de Audio

### Transcripción de Voz (STT)

```
Navegador (MediaRecorder → audio/webm;codecs=opus)
       │
       ▼ POST /transcribe (multipart/form-data)
       │
[TranscribeClient — src/llm/transcribe_client.py]
  • Detección de formato: WAV (magic bytes RIFF) o WebM/Opus
  • Conversión a PCM raw mono 16kHz 16-bit via ffmpeg
  • Streaming a Amazon Transcribe Streaming (amazon-transcribe SDK)
  • Vocabulario personalizado: "voae-vocabulary" (VOAE, UNAH, PASEE, PAC, ...)
  • Detección de alucinaciones:
      - Texto vacío o < 4 caracteres
      - Frases conocidas en silencio ("Gracias.", "Subtítulos...")
      - Solo puntuación o símbolos
      - Misma palabra repetida ≥ 3 veces
  • Validación previa de tamaño: blobs < 500 bytes → rechazados
       │
       ▼ texto transcrito (o null si alucinación)
```

**Vocabulario personalizado de dominio**: Amazon Transcribe usa una lista de términos institucionales para mejorar el reconocimiento de siglas y nombres propios (VOAE, PASEE, PROCAD, PROSENE, PHUMA, Mención-Honorífica, Horas-VOAE, etc.). Se crea una vez con:

```bash
cd src
python -c "from llm.transcribe_client import TranscribeClient; TranscribeClient().create_vocabulary()"
```

**Requisito**: `ffmpeg` instalado y accesible en PATH (o en la ruta estándar de winget).

### Síntesis de Voz (TTS)

```
Texto de respuesta LLM
       │
       ▼ split_sentences() — dividir en oraciones
       │
       ▼ preprocess_text_for_tts() por oración:
         • Elimina markdown (**bold**, *italic*, # headers, - listas)
         • Convierte acrónimos a minúsculas (VOAE→voae) para pronunciación Polly
       │
       ▼ PollyClient.synthesize(texto)
         • OutputFormat: mp3
         • VoiceId: Lupe (neural, es-US)
       │
       ▼ Audio MP3 → base64 → SSE chunk { type: "chunk", text, audio_base64 }
```

Los chunks MP3 llegan oración por oración. `AudioPlayer.jsx` los encola y reproduce secuencialmente con HTML5 Audio, sin solapamientos.

---

## Frontend

### Componentes React

| Componente | Archivo | Función |
|---|---|---|
| `App` | `App.jsx` | Estado global, SSE reader, routing de mensajes |
| `AudioPlayer` | `AudioPlayer.jsx` | Reproductor MP3 invisible, cola de chunks Polly |
| `Microphone` | `Microphone.jsx` | MediaRecorder + auto-stop por silencio |

### AudioPlayer: Cola de Audio

`AudioPlayer` es un componente invisible que gestiona la reproducción secuencial de chunks MP3:

```
avatarRef.current.speak(mp3Base64)  → encola chunk
avatarRef.current.stop()            → vacía la cola y detiene reproducción
```

Internamente mantiene una cola de objetos `Audio`. Al terminar cada chunk, inicia automáticamente el siguiente. Esto garantiza que el audio suene fluido y en orden, sin solapamientos entre oraciones.

### SSE Streaming en el Frontend

```javascript
// App.jsx — leer stream SSE del backend
const reader = response.body.getReader();
while (true) {
  const { done, value } = await reader.read();
  // Parsear eventos: meta | chunk | done | error
  if (data.type === 'chunk') {
    fullText += data.text;                        // texto acumulado → ReactMarkdown
    audioPlayerRef.current?.speak(data.audio_base64);  // MP3 → AudioPlayer
  }
}
```

El texto aparece progresivamente en la UI y el audio comienza desde la primera oración, sin esperar toda la respuesta.

---

## API REST

**Base URL**: `http://localhost:8000`
**Documentación interactiva**: `http://localhost:8000/docs` (Swagger UI)

### Endpoints

#### `POST /chat-stream` — Chat principal (SSE)

**Request:**
```json
{
  "message": "¿Cómo solicito una beca?",
  "session_id": "session-1234567890",
  "top_k": 4,
  "temperature": 0.7,
  "llm_provider": "bedrock"
}
```

**Eventos SSE:**
```
data: {"type":"meta","match_type":"high","best_faq_similarity":0.89,"context_type":"faq_only","relevant_documents":[...]}

data: {"type":"chunk","text":"Para solicitar una beca en la VOAE...","audio_base64":"//NExA..."}

data: {"type":"chunk","text":"Debes presentar los siguientes documentos...","audio_base64":"//NExA..."}

data: {"type":"done"}
```

#### `POST /chat` — Chat (sin streaming)

Mismo contrato que `/chat-stream` pero devuelve la respuesta completa en un solo JSON.

#### `POST /transcribe` — STT (multipart)

```bash
curl -X POST http://localhost:8000/transcribe \
  -F "audio=@recording.webm" \
  -F "language=es"
```

**Response:**
```json
{
  "text": "¿Cuáles son los requisitos para la beca?",
  "timestamp": "2026-03-04T10:30:01"
}
```

`text` es `null` si el audio está vacío, es muy corto (< 500 bytes) o se detecta una alucinación.

#### `POST /synthesize` — TTS

```json
{ "text": "Hola, soy el asistente de la VOAE." }
```

**Response:**
```json
{
  "audio_base64": "//NExA...",
  "timestamp": "2026-03-04T10:30:02"
}
```

Audio MP3 en base64. Compatible con HTML5 Audio directamente.

#### `POST /change-model` — Cambiar LLM en runtime

```json
{
  "session_id": "session-1234567890",
  "llm_provider": "bedrock"
}
```

#### `GET /stats?session_id={id}`

```json
{
  "total_documents": 16,
  "storage_path": "data/chroma",
  "embedder_model": "amazon.titan-embed-text-v2:0",
  "llm_model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
  "llm_provider": "bedrock",
  "max_history": 10,
  "current_history_length": 3
}
```

#### Otros Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/history?session_id={id}` | Historial de conversación |
| `POST` | `/clear-history?session_id={id}` | Borrar historial |
| `DELETE` | `/session/{session_id}` | Eliminar sesión y liberar memoria |
| `GET` | `/sessions` | Listar sesiones activas |
| `WebSocket` | `/ws/transcribe` | STT en tiempo real (chunks de audio) |

### Gestión de Sesiones

Cada sesión (`session_id`) tiene su propia instancia de `RAGChatbot` con historial independiente. Las sesiones son **en memoria**: se pierden al reiniciar el servidor.

El frontend genera `session-${Date.now()}` en cada carga de página, asegurando contexto fresco por pestaña.

---

## Instalación

### Requisitos del Sistema

- Python 3.10+
- Node.js 18+
- ffmpeg instalado en PATH (para conversión de audio WebM → PCM)
- Credenciales AWS con acceso a: Bedrock (LLM + Embeddings), Transcribe, Polly

### 1. Backend Python

```bash
# Clonar repositorio
git clone <url-del-repo>
cd VOAE_Chatbot

# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales AWS
```

### 2. Frontend React

```bash
cd frontend
npm install
```

### 3. Crear Vocabulario de Transcripción

Solo necesario la primera vez (o al agregar nuevos términos al dominio):

```bash
cd src
python -c "from llm.transcribe_client import TranscribeClient; TranscribeClient().create_vocabulary()"
```

Tarda ~1 minuto mientras AWS procesa el vocabulario.

### 4. Ingerir Documentos

```bash
# Primera ingesta
python src/main.py --ingest

# Forzar re-ingesta (ej. tras cambio de modelo de embeddings)
python src/main.py --ingest --force
```

### 5. Iniciar Servicios

```bash
# Terminal 1 — Backend
cd api && python main.py
# → http://localhost:8000

# Terminal 2 — Frontend
cd frontend && npm run dev
# → http://localhost:5173
```

---

## Configuración

Todas las variables se definen en `.env` (basado en `.env.example`). Los valores por defecto están en `src/config.py`.

### Variables AWS (Requeridas)

```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### Variables de LLM y Embeddings (Bedrock)

```env
BEDROCK_LLM_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIM=1024
```

### Variables de TTS (Polly)

```env
POLLY_VOICE=Lupe
POLLY_ENGINE=neural
POLLY_LANGUAGE=es-US
```

### Frontend

En `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000
```

### Configuración del Sistema RAG

```env
# FAQ
FAQ_HIGH_THRESHOLD=0.75        # Similitud mínima para match alto
FAQ_MEDIUM_THRESHOLD=0.65      # Similitud mínima para match medio

# Retrieval
RETRIEVAL_TOP_K=3              # Documentos por defecto
RETRIEVAL_MIN_SIMILARITY=0.3   # Umbral mínimo para incluir un doc

# Chatbot
CHATBOT_MAX_HISTORY=10         # Turnos máximos en historial
```

---

## Estructura del Proyecto

```
VOAE_Chatbot/
│
├── api/
│   └── main.py                      # FastAPI: endpoints, SSE, sesiones
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Componente raíz, SSE reader
│   │   ├── App.css                  # Estilos
│   │   └── components/
│   │       ├── AudioPlayer.jsx      # Cola de reproducción MP3 (Polly)
│   │       └── Microphone.jsx       # Grabación + auto-stop por silencio
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
│
├── src/
│   ├── config.py                    # Configuración centralizada
│   ├── main.py                      # CLI: --ingest, --query, --stats, --reset
│   ├── chat.py                      # Chatbot interactivo de consola
│   │
│   ├── embeddings/
│   │   └── embedder.py              # Titan V2 via Bedrock (boto3)
│   │
│   ├── database/
│   │   ├── chroma_vector_store.py   # ChromaDB: CRUD + búsqueda HNSW
│   │   └── repository.py            # Abstracción CRUD sobre ChromaVectorStore
│   │
│   ├── ingestion/
│   │   └── ingest_docs.py           # Carga .md, preprocesamiento, chunking
│   │
│   ├── rag/
│   │   ├── retriever.py             # Búsqueda semántica (usa ChromaDB HNSW)
│   │   ├── faq_handler.py           # Clasificación HIGH/MEDIUM/LOW + contexto LLM
│   │   └── rag_pipeline.py          # Orquestador principal del pipeline RAG
│   │
│   ├── llm/
│   │   ├── bedrock_client.py        # Claude 3.5 Haiku via Bedrock: 3 system prompts
│   │   ├── transcribe_client.py     # Amazon Transcribe STT + vocabulario personalizado
│   │   └── polly_client.py          # Amazon Polly TTS → MP3 base64
│   │
│   └── chatbot/
│       └── chatbot.py               # RAGChatbot: historial + filtrado por confianza
│
├── data/
│   ├── docs/                        # Documentos fuente (.md)
│   │   └── faq/                     # FAQs (identificados por ruta)
│   └── chroma/                      # ChromaDB (auto-generado)
│       └── chroma.sqlite3
│
├── .env.example                     # Template de configuración
├── requirements.txt                 # Dependencias Python
└── README.md
```

---

## Comandos de Desarrollo

### Backend

```bash
# Servidor de desarrollo
cd api && python main.py

# Operaciones de base de datos
python src/main.py --ingest              # Ingerir documentos nuevos
python src/main.py --ingest --force      # Re-ingerir todos (sobrescribir)
python src/main.py --ingest --chunk      # Ingerir con chunking
python src/main.py --query "pregunta"    # Consulta directa
python src/main.py --stats               # Ver estadísticas
python src/main.py --reset               # Borrar toda la BD

# Consola interactiva
python src/chat.py

# Crear/actualizar vocabulario de Amazon Transcribe
cd src && python -c "from llm.transcribe_client import TranscribeClient; TranscribeClient().create_vocabulary()"

# Testing de módulos individuales
python src/config.py
python src/embeddings/embedder.py
python src/database/chroma_vector_store.py
python src/rag/retriever.py
python src/rag/faq_handler.py
python src/rag/rag_pipeline.py
python src/chatbot/chatbot.py
python src/llm/bedrock_client.py
python src/llm/polly_client.py
```

### Frontend

```bash
cd frontend
npm run dev       # Servidor de desarrollo (http://localhost:5173)
npm run build     # Build de producción (output: dist/)
npm run preview   # Preview del build de producción
```

---

## Troubleshooting

### Error al transcribir: "ffmpeg no encontrado en PATH"

Instala ffmpeg y reinicia la terminal:
```bash
winget install Gyan.FFmpeg    # Windows
brew install ffmpeg           # macOS
sudo apt install ffmpeg       # Ubuntu/Debian
```

### El vocabulario de Transcribe no reconoce los términos VOAE

El vocabulario debe crearse/actualizarse manualmente cuando se modifican los términos en `_DOMAIN_TERMS`:
```bash
cd src && python -c "from llm.transcribe_client import TranscribeClient; TranscribeClient().create_vocabulary()"
```

### Similitudes FAQ siempre bajas (< 60%)

1. Verifica que los FAQs estén en `data/docs/faq/` y hayan sido ingeridos:
   ```bash
   python src/main.py --stats
   ```
2. Si se modificaron FAQs, re-ingerir con `--force`.
3. Añade más variantes de pregunta en los archivos FAQ.

### Error "No hay documentos en la base de datos"

```bash
python src/main.py --ingest
```

### ChromaDB corrompido o vectores de modelo anterior

```bash
rm -rf data/chroma/
python src/main.py --ingest
```

### Error CORS

El backend permite `localhost:3000` y `localhost:5173`. Para otros orígenes, editar `api/main.py`:
```python
allow_origins=["http://localhost:3000", "http://localhost:5173", "http://tu-origen"]
```

### Puerto 8000 ocupado

```bash
# Linux/macOS
lsof -i :8000
kill -9 $(lsof -ti:8000)

# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

---

## Notas de Producción

```bash
# Backend con múltiples workers
gunicorn api.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Frontend — build estático
cd frontend && npm run build
# Servir dist/ con nginx o un CDN
```

**Consideraciones importantes:**
- Las sesiones son **en memoria**: al reiniciar el proceso se pierden todos los historiales.
- Con `gunicorn -w N`, cada worker tiene su propio cliente boto3. Las conexiones a AWS son ligeras (no se carga ningún modelo en memoria).
- Para alta concurrencia, 2-4 workers son suficientes. El cuello de botella es la latencia de los servicios AWS, no el procesamiento local.

---

## Recursos

- [Amazon Bedrock Docs](https://docs.aws.amazon.com/bedrock/)
- [Amazon Transcribe Streaming Docs](https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html)
- [Amazon Polly Docs](https://docs.aws.amazon.com/polly/)
- [Titan Embeddings V2](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
