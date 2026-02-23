# Chatbot VOAE — Sistema RAG con Avatar Conversacional

Chatbot con inteligencia artificial para la **Vicerrectoría de Orientación y Asuntos Estudiantiles (VOAE)** de la UNAH-VS. Combina recuperación semántica de documentos (RAG) con un sistema FAQ híbrido, síntesis de voz y un avatar animado con lip-sync en tiempo real.

---

## Tabla de Contenidos

- [Stack Tecnológico](#stack-tecnológico)
- [Arquitectura General](#arquitectura-general)
- [Modelo de Embeddings: BGE-M3](#modelo-de-embeddings-bge-m3)
- [Base de Datos Vectorial: ChromaDB](#base-de-datos-vectorial-chromadb)
- [Sistema FAQ Híbrido](#sistema-faq-híbrido)
- [Pipeline de Audio](#pipeline-de-audio)
- [Frontend y Avatar Simli](#frontend-y-avatar-simli)
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
| **Embeddings** | BGE-M3 (BAAI) | Vectorización semántica de documentos y consultas |
| **Vector DB** | ChromaDB + HNSW | Almacenamiento y búsqueda aproximada de vecinos |
| **LLM** | Groq / Llama-3.3-70B | Generación de respuestas (principal) |
| **LLM alt.** | DeepSeek | Proveedor alternativo intercambiable en runtime |
| **STT** | Groq Whisper large-v3 | Transcripción de voz a texto |
| **TTS** | Amazon Polly (neural) | Síntesis de voz (PCM 16kHz mono) |
| **Avatar** | Simli WebRTC | Animación facial lip-sync en tiempo real |
| **Backend** | FastAPI + Uvicorn | API REST + SSE streaming |
| **Frontend** | React 18 + Vite | Interfaz de usuario |

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
  5. LLMClient.generate_response() con historial inyectado
         │
         ▼
[LLM Client (Groq o DeepSeek)]
  • System prompt seleccionado por context_type
  • Historial como mensajes alternados user/assistant
  • → respuesta de texto
         │
         ▼
[api/main.py — SSE Generator]
  Por cada oración de la respuesta:
    → preprocess_text_for_tts()
    → PollyClient.synthesize() → PCM base64
    → SSE event: { type: "chunk", text, audio_base64 }
         │
         ▼
[Frontend]
  • Renderiza texto progresivamente (Markdown)
  • avatarRef.speak(audio_base64) → SimliAvatar
         │
         ▼
[SimliAvatar — WebRTC]
  • Envía PCM a Simli via sendAudioData()
  • Video renderizado con lip-sync
```

### Wiring de Componentes Python

```
api/main.py
└── RAGChatbot (por sesión, en memoria)
    ├── RAGPipeline
    │   ├── Embedder (BGE-M3, compartido)
    │   ├── ChromaVectorStore → ChromaDB (data/chroma/)
    │   ├── DocumentRepository (CRUD sobre ChromaVectorStore)
    │   ├── DocumentRetriever (búsqueda semántica HNSW)
    │   ├── FAQHandler (clasificación y routing)
    │   └── LLMClient (GroqClient | DeepSeekClient)
    └── conversation_history + _history_confidence
```

---

## Modelo de Embeddings: BGE-M3

### ¿Qué es BGE-M3?

**BGE-M3** (BAAI General Embedding - Multi-Functionality, Multi-Linguality, Multi-Granularity) es un modelo de embeddings de texto desarrollado por el **Beijing Academy of Artificial Intelligence (BAAI)**. Es el estado del arte en tareas de recuperación semántica densa.

Identificador en Hugging Face: `BAAI/bge-m3`

### Características Técnicas

| Propiedad | Valor |
|---|---|
| Dimensiones del vector | **1024** float32 |
| Longitud máxima de secuencia | **8192 tokens** |
| Tamaño del modelo | ~570 MB |
| Arquitectura base | XLM-RoBERTa large |
| Parámetros | 568M |
| Idiomas soportados | **100+ idiomas** (multilingüe) |
| Licencia | MIT |

### Por Qué BGE-M3 para VOAE

- **Multilingüe nativo**: maneja español, mezclas español/inglés y términos técnicos universitarios (VOAE, UNAH, CIVU, PAC) sin degradación de calidad.
- **Contexto largo (8192 tokens)**: documentos completos se pueden vectorizar sin chunking obligatorio. Los documentos de VOAE (reglamentos, guías) caben íntegros.
- **Similitud coseno**: optimizado para búsqueda por similitud coseno, que es agnóstica a la magnitud del vector (solo mide orientación), ideal para comparar semántica.
- **Embeddings normalizados**: `generate_embedding()` usa `normalize_embeddings=True`, lo que garantiza que todos los vectores tienen norma L2 = 1. En este caso, la similitud coseno es equivalente al producto punto, y ChromaDB la calcula eficientemente.

### Cómo Funciona la Vectorización

```python
# src/embeddings/embedder.py
embedding = self.model.encode(text, normalize_embeddings=True)
# → numpy float32 de forma (1024,)
# → norma L2 = 1.0 (por normalización)
```

Un documento de texto pasa por:

```
Texto crudo → Tokenización (WordPiece, vocab XLM-RoBERTa)
           → Transformer (24 capas, 16 cabezas de atención)
           → Pooling del token [CLS]
           → Normalización L2
           → Vector float32 de 1024 dimensiones
```

### Similitud Coseno

La similitud entre una consulta `q` y un documento `d` se calcula como:

```
similitud(q, d) = cos(θ) = (q · d) / (|q| × |d|)
```

Dado que los vectores están normalizados (`|q| = |d| = 1`), esto reduce a:

```
similitud(q, d) = q · d   (producto punto)
```

ChromaDB almacena la **distancia coseno** (`distance = 1 - similitud`) y la convierte en el código:

```python
# src/database/chroma_vector_store.py
similarity = 1.0 - distance
```

Un valor de `1.0` es similitud perfecta, `0.0` es ortogonalidad (sin relación semántica).

### Descarga y Cache

El modelo se descarga automáticamente en la primera ejecución desde Hugging Face Hub:

```
~/.cache/huggingface/hub/models--BAAI--bge-m3/
```

Peso aproximado: **~2 GB**. Solo se descarga una vez; las ejecuciones posteriores lo cargan desde disco.

---

## Base de Datos Vectorial: ChromaDB

### Descripción General

ChromaDB es una base de datos embebida (sin servidor separado) diseñada específicamente para almacenar y buscar embeddings. Se ejecuta en el mismo proceso Python y persiste en disco automáticamente.

**Ruta de datos**: `data/chroma/` (relativa a la raíz del proyecto)

### Estructura Física en Disco

```
data/chroma/
└── chroma.sqlite3          ← Metadata, IDs, documentos de texto
                              (los embeddings también se almacenan aquí
                               en formato SQLite BLOB para la colección pequeña)
```

ChromaDB usa SQLite como backend de persistencia. Para colecciones pequeñas a medianas (< ~100k documentos), todo queda en un único archivo `chroma.sqlite3`. Para colecciones grandes activaría un backend HNSW separado en archivos binarios.

### Esquema Lógico de la Colección

La aplicación usa una **única colección** llamada `documents` con métrica coseno:

```python
self.collection = self.client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"}
)
```

Cada documento almacenado tiene tres partes:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` | Identificador único derivado del filename (`filename.replace(" ", "_").replace("/", "_")`) |
| `document` | `string` | Contenido textual completo del documento `.md` |
| `metadata.filename` | `string` | Ruta original del archivo (ej: `faq/faq_servicios.md`) |
| `embedding` | `float32[1024]` | Vector BGE-M3 normalizado |

### Identificación de Documentos

El ID en ChromaDB se deriva directamente del nombre de archivo:

```python
# Ejemplo de mapeo filename → ID
"faq/faq_servicios.md"        →  "faq_faq_servicios.md"
"services/Becas_UNAH.md"      →  "services_Becas_UNAH.md"
"about/contacto.md"           →  "about_contacto.md"
```

Este esquema es **determinístico**: el mismo archivo siempre produce el mismo ID, lo que permite detectar duplicados (`document_exists()`) sin consultas costosas.

### Distinción FAQs vs. Documentos Generales

**FAQs y documentos generales conviven en la misma colección**. La separación no es estructural en ChromaDB, sino por convención de ruta:

- **FAQs**: archivos en `data/docs/faq/` → `filename` comienza con `faq/`
- **Docs generales**: archivos en `data/docs/` (otras subcarpetas)

El sistema los separa en tiempo de consulta:

```python
# src/rag/rag_pipeline.py
faq_results = [r for r in all_docs if r[0].startswith('faq/')]
doc_results  = [r for r in all_docs if not r[0].startswith('faq/')]
```

### Algoritmo HNSW (Búsqueda Vectorial)

ChromaDB usa **HNSW (Hierarchical Navigable Small World)** para búsqueda aproximada de vecinos más cercanos (ANN). Esto permite encontrar los `top_k` vectores más similares en tiempo **O(log n)** en lugar de la fuerza bruta **O(n)**.

HNSW construye un grafo multicapa donde:
- Las capas superiores tienen pocos nodos y permiten saltos largos (navegación rápida global)
- Las capas inferiores tienen todos los nodos con conexiones cortas (refinamiento local)

Una búsqueda empieza en la capa más alta, navega hacia el vecino más cercano y desciende de capa en capa hasta encontrar los `top_k` resultados en la capa base.

**Parámetros HNSW por defecto de ChromaDB:**
- `M = 16` (conexiones por nodo)
- `ef_construction = 100` (candidatos durante construcción)
- `ef_search = 10` (candidatos durante búsqueda)

### Operaciones Disponibles

```python
# Añadir documento
store.add_document(filename, content, embedding_np_array) → str (doc_id)

# Verificar existencia (O(1) via ChromaDB get by ID)
store.document_exists(filename) → bool

# Búsqueda semántica HNSW
store.search_similar(query_embedding, top_k=3) → List[(id, filename, content, similarity)]

# Contar documentos
store.count_documents() → int

# Eliminar todo (recrea la colección)
store.delete_all_documents() → int
```

### Documentos Actuales

```
data/docs/
├── about/
│   ├── about.md                    # Información institucional VOAE
│   ├── contacto.md                 # Datos de contacto
│   └── ubicaciones.md              # Ubicaciones físicas
├── areas/
│   └── areas.md                    # Áreas funcionales de VOAE
├── faq/
│   └── faq_servicios.md            # Preguntas frecuentes (FAQ)
└── services/
    ├── Atención_Medica.MD
    ├── Area_investigacion.md
    ├── Becas_UNAH.md
    ├── Curso_de_Introducción_Vida_Universitaria.md
    ├── Fechas_Importantes_2026.md
    ├── Feria_vocacional.md
    ├── Gobierno_y_grupos_Estudiantiles.MD
    ├── Honores_Academicos.md
    ├── Horas_VOAE.md
    ├── Inducción_Nuevos_Estudiantes.MD
    ├── Prueba_de_Orientacion.MD
    ├── Unidad_Medico_Deportiva.md
    ├── Visitas_Guiadas_al_Campus.MD
    ├── Areas_de_VOAE.md
    ├── proceso_readmision.md
    └── prosene.md
```

---

## Sistema FAQ Híbrido

### Motivación

Un chatbot RAG sin FAQs puede responder con alta latencia y variabilidad en preguntas muy comunes. El sistema FAQ híbrido permite respuestas rápidas, deterministas y sin alucinaciones para las consultas más frecuentes, mientras mantiene la capacidad RAG completa para consultas novedosas.

### Clasificación por Umbrales

Cada consulta es clasificada según la similitud coseno con los documentos FAQ:

```
Similitud FAQ    Tipo de Match    Contexto LLM           Temperature
─────────────────────────────────────────────────────────────────────
≥ 75%            HIGH             Solo top-3 FAQs         0.1
65% – 74%        MEDIUM           Top-2 FAQs + top-2 docs 0.2
< 65%            LOW              Top-K documentos         0.3
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
       └── 6. LLMClient.generate_response(context_type=..., history=...)
```

### Prompts del Sistema LLM

Cada `context_type` activa un system prompt distinto:

| `context_type` | Comportamiento del LLM |
|---|---|
| `faq_only` | Extremadamente estricto: solo información exacta del FAQ, sin conocimiento externo, sin elaborar |
| `faq_and_docs` | Prioriza FAQs, complementa con docs, evita inventar lo que no está |
| `docs_only` | Usa los documentos como única fuente, admite no saber si la info no está |

Los tres prompts comparten restricciones:
- Nunca decir "según el contexto" o "basándome en"
- Persona VOAE: trato de "tú", cálido y profesional
- No omitir fechas, listas o datos específicos

### Enriquecimiento de Query para Seguimiento

Las preguntas de seguimiento como *"¿Y en qué horario?"* no tienen suficiente contexto para una buena búsqueda semántica. El sistema detecta automáticamente seguimientos y enriquece la query:

```python
# Detectado como seguimiento si:
# - ≤ 6 palabras, O
# - Primera palabra es pronombre/preposición ("eso", "en", "cuándo", "para"...)

search_query = f"{último_mensaje_usuario} {question}"
# Ejemplo: "¿Qué es PROSENE? ¿Y en qué horario atienden?"
```

---

## Pipeline de Audio

### Transcripción de Voz (STT)

```
Navegador (MediaRecorder → audio/webm;codecs=opus)
       │
       ▼ POST /transcribe (multipart/form-data)
       │
[TranscriptionClient — src/llm/transcription_client.py]
  • Modelo: whisper-large-v3 via Groq API
  • Prompt de dominio: "Vocabulario específico: VOAE, UNAH, UNAH-VS, ..."
  • Detección de alucinaciones:
      - Texto vacío o < 4 caracteres
      - Frases conocidas de Whisper en silencio ("Gracias.", "Subtítulos...")
      - Solo puntuación o símbolos
      - Misma palabra repetida ≥ 3 veces
  • Validación previa de tamaño: blobs < 500 bytes → rechazados
       │
       ▼ texto transcrito (o null si alucinación)
```

**Coordinación micrófono ↔ avatar:**
Cuando el usuario activa el micrófono, `mute()` desconecta el `srcObject` WebRTC del `<audio>` de Simli (no solo `muted=true`, sino `srcObject=null`), cortando el stream de audio del OS completamente para evitar feedback al micrófono. Al terminar la grabación, `unmute()` restaura el stream.

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
         • OutputFormat: pcm
         • SampleRate: 16000 Hz
         • VoiceId: Lupe (neural, es-US)
       │
       ▼ Audio PCM → base64 → SSE chunk { type: "chunk", text, audio_base64 }
```

**Por qué PCM 16kHz mono**: Simli requiere exactamente este formato para la animación facial. Polly neural con `SampleRate='16000'` produce el stream correcto directamente, sin conversión.

---

## Frontend y Avatar Simli

### Componentes React

| Componente | Archivo | Función |
|---|---|---|
| `App` | `App.jsx` | Estado global, SSE reader, routing de mensajes |
| `SimliAvatar` | `SimliAvatar.jsx` | WebRTC con Simli, lip-sync, mute/unmute |
| `Microphone` | `Microphone.jsx` | MediaRecorder + SpeechRecognition auto-stop |

### SimliAvatar: Diseño Técnico

`SimliAvatar` está implementado con `forwardRef` + `useImperativeHandle` para que `App` pueda controlar el avatar imperativamente:

```
avatarRef.current.speak(pcmBase64)  → envía audio PCM al avatar
avatarRef.current.stop()            → limpia buffer (ClearBuffer)
avatarRef.current.mute()            → srcObject=null (corta WebRTC del OS)
avatarRef.current.unmute()          → restaura srcObject + play()
```

**Problema de React StrictMode (doble montaje)**: En desarrollo, React monta los componentes dos veces. Esto creaba dos instancias de `SimliClient`, donde `clientRef.current` apuntaba al segundo cliente (que nunca conectaba), dejando `isConnected()` siempre en `false`.

**Solución**: `isReadyRef` es un ref booleano (no estado) que solo se pone `true` cuando el evento `'connected'` dispara **y** el cliente que dispara el evento ES `clientRef.current` (`isCurrent === true`). El segundo cliente del StrictMode dispara `connected`, pero `isCurrent=false`, así que `isReadyRef` no se activa.

**Auto-activación por política de autoplay**: El `AudioContext` de WebRTC requiere un gesto de usuario. `SimliAvatar` muestra un overlay "▶" hasta que el usuario hace clic o envía un mensaje. `activate()` se llama en esos gestos, iniciando `startNewClient()` dentro del contexto del gesto.

### SSE Streaming en el Frontend

```javascript
// App.jsx — leer stream SSE del backend
const reader = response.body.getReader();
while (true) {
  const { done, value } = await reader.read();
  // Parsear eventos: meta | chunk | done | error
  if (data.type === 'chunk') {
    fullText += data.text;          // texto acumulado → ReactMarkdown
    avatarRef.current?.speak(data.audio_base64);  // PCM → Simli
  }
}
```

Los chunks llegan oración por oración: el texto aparece progresivamente en la UI y el avatar comienza a hablar desde la primera oración, sin esperar toda la respuesta.

---

## API REST

**Base URL**: `http://localhost:8000`
**Documentación interactiva**: `http://localhost:8000/docs` (Swagger UI)

### Endpoints

#### `POST /chat-stream` — Chat principal (SSE)

Procesa un mensaje y devuelve la respuesta como stream de eventos SSE con audio PCM sincronizado.

**Request:**
```json
{
  "message": "¿Cómo solicito una beca?",
  "session_id": "session-1234567890",
  "top_k": 4,
  "temperature": 0.7,
  "llm_provider": "groq"
}
```

**Eventos SSE:**
```
data: {"type":"meta","match_type":"high","best_faq_similarity":0.89,"context_type":"faq_only","relevant_documents":[...]}

data: {"type":"chunk","text":"Para solicitar una beca en la VOAE...","audio_base64":"UklGRi..."}

data: {"type":"chunk","text":"Debes presentar los siguientes documentos...","audio_base64":"UklGRi..."}

data: {"type":"done"}
```

#### `POST /chat` — Chat (sin streaming)

Mismo contrato que `/chat-stream` pero devuelve la respuesta completa en un solo JSON. Útil para integraciones que no soporten SSE.

**Response:**
```json
{
  "answer": "Para solicitar una beca...",
  "session_id": "session-1234567890",
  "match_type": "high",
  "best_faq_similarity": 0.89,
  "context_type": "faq_only",
  "relevant_documents": [
    {
      "filename": "faq/faq_servicios.md",
      "similarity": 0.89,
      "type": "faq",
      "preview": "..."
    }
  ],
  "timestamp": "2026-02-22T10:30:00"
}
```

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
  "timestamp": "2026-02-22T10:30:01"
}
```
`text` es `null` si el audio está vacío, es demasiado corto (< 500 bytes), o Whisper detecta una alucinación.

#### `POST /synthesize` — TTS

```json
{ "text": "Hola, soy el asistente de la VOAE." }
```

**Response:**
```json
{
  "audio_base64": "UklGRi...",
  "timestamp": "2026-02-22T10:30:02"
}
```
Audio PCM 16kHz mono en base64. Formato requerido por Simli.

#### `POST /change-model` — Cambiar LLM en runtime

```json
{
  "session_id": "session-1234567890",
  "llm_provider": "deepseek"
}
```
Cambia el proveedor LLM para la sesión. El historial de conversación se preserva.

#### `GET /stats?session_id={id}`

```json
{
  "total_documents": 16,
  "storage_path": "data/chroma",
  "embedder_model": "BAAI/bge-m3",
  "llm_model": "llama-3.3-70b-versatile",
  "llm_provider": "groq",
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
| `WebSocket` | `/ws/transcribe` | STT en tiempo real (chunks Float32 PCM) |

### Gestión de Sesiones

Cada sesión (`session_id`) tiene su propia instancia de `RAGChatbot` con historial independiente. Las sesiones son **en memoria**: se pierden al reiniciar el servidor.

El frontend genera `session-${Date.now()}` en cada carga de página, asegurando contexto fresco por pestaña/sesión.

---

## Instalación

### Requisitos del Sistema

- Python 3.10+
- Node.js 18+
- RAM mínima: 4 GB (recomendado 8 GB para BGE-M3 en CPU)
- Espacio en disco: ~2 GB para el modelo BGE-M3
- Conectividad a internet para APIs (Groq, AWS Polly, Simli)

### 1. Backend Python

```bash
# Clonar repositorio
git clone <url-del-repo>
cd LLAMA_BGE_CHATBOT

# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Frontend React

```bash
cd frontend
npm install
```

### 3. Ingerir Documentos

```bash
# Primera ingesta (descarga BGE-M3 ~2GB si no existe)
python src/main.py --ingest

# Forzar re-ingesta de documentos modificados
python src/main.py --ingest --force

# Con chunking para documentos muy largos
python src/main.py --ingest --chunk
```

### 4. Iniciar Servicios

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

### Variables Requeridas

```env
# Al menos una de estas dos es requerida
GROQ_API_KEY=gsk_...
DEEPSEEK_API_KEY=sk-...
```

### Variables de Amazon Polly (TTS)

```env
AWS_ACCES_KEY=AKIA...          # Nota: typo intencional (una 's'), compatibilidad legacy
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
POLLY_VOICE=Lupe               # Voz neural en español
POLLY_ENGINE=neural
POLLY_LANGUAGE=es-US
```

### Variables de Simli (Avatar)

En `frontend/.env`:
```env
VITE_SIMLI_API_KEY=...
VITE_SIMLI_FACE_ID=...
VITE_API_URL=http://localhost:8000
```

### Configuración del Sistema RAG

```env
# LLM
LLM_PROVIDER=groq                    # groq | deepseek
LLM_MAX_TOKENS=2000
LLM_MAX_TOKENS_GROQ=850

# FAQ
FAQ_HIGH_THRESHOLD=0.75              # Similitud mínima para match alto
FAQ_MEDIUM_THRESHOLD=0.65            # Similitud mínima para match medio

# Retrieval
RETRIEVAL_TOP_K=3                    # Documentos por defecto
RETRIEVAL_MIN_SIMILARITY=0.3         # Umbral mínimo para incluir un doc

# Chatbot
CHATBOT_MAX_HISTORY=10               # Turnos máximos en historial

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu                 # cpu | cuda | mps
```

---

## Estructura del Proyecto

```
LLAMA_BGE_CHATBOT/
│
├── api/
│   └── main.py                      # FastAPI: endpoints, SSE, sesiones
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Componente raíz, SSE reader
│   │   ├── App.css                  # Estilos
│   │   ├── components/
│   │   │   ├── SimliAvatar.jsx      # Avatar WebRTC con lip-sync
│   │   │   └── Microphone.jsx       # Grabación + auto-stop por voz
│   │   └── services/
│   │       └── speechToText.mjs     # Cliente HTTP /transcribe
│   ├── public/
│   │   └── voae-logo.png
│   ├── package.json
│   └── vite.config.js
│
├── src/
│   ├── config.py                    # Configuración centralizada (todas las clases Config)
│   ├── main.py                      # CLI: --ingest, --query, --stats, --reset
│   ├── chat.py                      # Chatbot interactivo de consola
│   │
│   ├── embeddings/
│   │   └── embedder.py              # Wrapper SentenceTransformer (BGE-M3)
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
│   │   ├── groq_client.py           # API Groq: Llama-3.3-70B, 3 system prompts
│   │   ├── deepseek_client.py       # API DeepSeek: deepseek-chat, 3 system prompts
│   │   ├── transcription_client.py  # Groq Whisper STT + detección alucinaciones
│   │   └── polly_client.py          # Amazon Polly TTS → PCM base64
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

# Testing de módulos individuales
python src/config.py                     # Validar configuración
python src/embeddings/embedder.py        # Test de embeddings
python src/database/chroma_vector_store.py
python src/rag/retriever.py
python src/rag/faq_handler.py
python src/rag/rag_pipeline.py
python src/chatbot/chatbot.py
python src/llm/groq_client.py
python src/llm/deepseek_client.py
python src/llm/transcription_client.py
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

### BGE-M3 tarda mucho en cargar

El modelo (~2 GB) se descarga una vez desde Hugging Face y queda en `~/.cache/huggingface/`. Las siguientes cargas toman 5-15 segundos en CPU. Si el entorno tiene GPU, configura `EMBEDDING_DEVICE=cuda` para acelerar.

### Similitudes FAQ siempre bajas (< 60%)

1. Verifica que los FAQs estén en `data/docs/faq/` y hayan sido ingeridos:
   ```bash
   python src/main.py --stats
   # Debería mostrar total_documents > 0
   ```
2. Si se modificaron FAQs, re-ingerir con `--force`.
3. Añade más variantes de pregunta en los archivos FAQ.

### El avatar Simli no habla

1. Verifica que `VITE_SIMLI_API_KEY` y `VITE_SIMLI_FACE_ID` estén en `frontend/.env`.
2. El avatar requiere un **gesto de usuario** (clic en el overlay "▶") para cumplir la política de autoplay del navegador.
3. Revisa la consola del navegador para errores de WebRTC o de conexión a Simli.

### Whisper transcribe texto incorrecto (alucinaciones)

El sistema ya filtra las alucinaciones más comunes. Si aparecen nuevas, agrégalas a `_HALLUCINATION_PHRASES` en `src/llm/transcription_client.py`. Si el audio es muy corto, asegúrate de que el blob tiene más de 500 bytes.

### Error CORS

El backend permite `localhost:3000` y `localhost:5173`. Para otros orígenes, editar `api/main.py`:
```python
allow_origins=["http://localhost:3000", "http://localhost:5173", "http://tu-origen"]
```

### Puerto 8000 ocupado

```bash
# Identificar proceso
lsof -i :8000
# Terminar proceso
kill -9 $(lsof -ti:8000)
```

### Error "No hay documentos en la base de datos"

```bash
python src/main.py --ingest
```

### ChromaDB corrompido

```bash
rm -rf data/chroma/
python src/main.py --ingest
```

---

## Notas de Producción

Para despliegue en producción:

```bash
# Backend con múltiples workers
gunicorn api.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Frontend — build estático
cd frontend && npm run build
# Servir dist/ con nginx o un CDN
```

**Consideraciones importantes:**
- Las sesiones son **en memoria**: al reiniciar el proceso se pierden todos los historiales.
- El modelo BGE-M3 se carga **una vez por proceso**. Con `gunicorn -w N`, cada worker carga su propia copia del modelo (~2 GB × N de RAM).
- Para alta concurrencia, usar 1-2 workers y confiar en el event loop async de uvicorn para paralelizar las llamadas a las APIs externas (Groq, Polly, Simli).

---

## Recursos

- [BGE-M3 en Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [Groq Console](https://console.groq.com/)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [Simli Docs](https://docs.simli.com/)
- [Amazon Polly Docs](https://docs.aws.amazon.com/polly/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
