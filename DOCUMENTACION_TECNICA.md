# Documentación Técnica — Chatbot VOAE

> Chatbot de Recuperación Aumentada (RAG) para la Vicerrectoría de Orientación y Asuntos Estudiantiles (VOAE) de la UNAH. Ofrece respuestas contextualizadas a estudiantes sobre servicios, becas, trámites y más, con soporte de voz bidireccional y avatar animado.

---

## 1. Estructura del Proyecto

```
LLAMA_BGE_CHATBOT/
│
├── api/                            # Servidor FastAPI (backend HTTP)
│   └── main.py                     # Endpoints REST + WebSocket + SSE
│
├── src/                            # Lógica de negocio Python
│   ├── config.py                   # Clases de configuración + validación
│   ├── main.py                     # CLI: ingest, query, stats, reset
│   ├── chat.py                     # Modo consola interactivo
│   │
│   ├── chatbot/
│   │   └── chatbot.py              # RAGChatbot: historial + confianza por turno
│   │
│   ├── rag/
│   │   ├── rag_pipeline.py         # Pipeline principal: enriquecimiento + FAQ + retrieval + LLM
│   │   ├── faq_handler.py          # Clasificación FAQ y construcción de contexto
│   │   └── retriever.py            # Búsqueda semántica en ChromaDB
│   │
│   ├── llm/
│   │   ├── groq_client.py          # Cliente Groq (Llama-3.3-70B) — proveedor principal
│   │   ├── deepseek_client.py      # Cliente DeepSeek — proveedor alternativo
│   │   ├── transcription_client.py # Whisper via Groq (STT)
│   │   └── polly_client.py         # Amazon Polly (TTS → PCM 16 kHz)
│   │
│   ├── embeddings/
│   │   └── embedder.py             # BGE-M3 (1024 dims): generación y serialización
│   │
│   ├── database/
│   │   ├── chroma_vector_store.py  # Wrapper directo sobre ChromaDB
│   │   └── repository.py           # CRUD + conversión numpy ↔ bytes
│   │
│   └── ingestion/
│       └── ingest_docs.py          # Carga, limpieza y chunking de documentos
│
├── frontend/                       # SPA React 18 + Vite
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                 # Componente raíz: SSE reader, estado global, chat UI
│       ├── components/
│       │   ├── SimliAvatar.jsx     # Avatar WebRTC (forwardRef + mute/unmute/speak)
│       │   └── Microphone.jsx      # Grabación + Web Speech API (auto-stop)
│       └── services/
│           └── speechToText.mjs    # POST /transcribe desde el frontend
│
├── data/
│   ├── docs/                       # Fuente de documentos (Markdown)
│   │   ├── faq/                    # Preguntas frecuentes (identificadas por prefijo faq/)
│   │   ├── services/               # Servicios: becas, PROSENE, médica, honores, etc.
│   │   ├── areas/                  # Áreas de VOAE
│   │   └── about/                  # Info general, contacto, ubicaciones
│   └── chroma/                     # Base de datos vectorial persistente (SQLite)
│       └── chroma.sqlite3
│
├── .env                            # Variables de entorno (no versionado)
├── .env.example                    # Plantilla de configuración
├── requirements.txt                # Dependencias Python
└── CLAUDE.md                       # Guía para Claude Code (en .gitignore)
```

### Ramas activas

| Rama | Estado | Descripción |
|------|--------|-------------|
| `main` | Base estable | Polly TTS, sin avatar |
| `feature/simli` | **Activa** | Avatar Simli WebRTC + Polly PCM + SSE streaming |
| `feature/talking-avatar` | Mantenida | Avatar WebGL (`@met4citizen/talkinghead`) + MP3 + visemas |

---

## 2. Requerimientos y Estimaciones

### 2.1 Dependencias Python

| Paquete | Rol |
|---------|-----|
| `sentence-transformers` | Carga y ejecución del modelo BGE-M3 |
| `transformers` + `accelerate` | Backend de inferencia para embeddings |
| `chromadb` | Vector store persistente en disco |
| `numpy` | Serialización de embeddings (numpy ↔ bytes) |
| `groq` | Cliente oficial Groq API (LLM + Whisper) |
| `boto3` | AWS SDK para Amazon Polly (TTS) |
| `fastapi` ≥ 0.104 | Framework HTTP + WebSocket + SSE |
| `uvicorn[standard]` ≥ 0.24 | Servidor ASGI |
| `pydantic` ≥ 2.0 | Modelos de datos y validación |
| `python-multipart` | Soporte para upload de audio en `/transcribe` |
| `python-dotenv` | Carga de `.env` |
| `requests` | HTTP en clientes alternativos |

### 2.2 Dependencias Frontend

| Paquete | Rol |
|---------|-----|
| `react` 18 | Framework UI |
| `vite` | Bundler y dev server (puerto 3000) |
| `simli-client` | SDK WebRTC para el avatar Simli |
| `react-markdown` | Renderizado de respuestas en Markdown |
| `lucide-react` | Iconografía |
| `axios` | Cliente HTTP (secundario) |

### 2.3 Servicios externos requeridos

| Servicio | Variable de entorno | Uso | Límite gratuito |
|----------|---------------------|-----|-----------------|
| **Groq** | `GROQ_API_KEY` | LLM (Llama-3.3-70B) + Whisper STT | 14,400 req/día |
| **DeepSeek** | `DEEPSEEK_API_KEY` | LLM alternativo | Por créditos |
| **AWS Polly** | `AWS_ACCES_KEY` + `AWS_SECRET_ACCESS_KEY` | TTS PCM 16 kHz | 5M caracteres/mes (12 meses) |
| **Simli** | `VITE_SIMLI_API_KEY` + `VITE_SIMLI_FACE_ID` | Avatar WebRTC | Por plan |

> **Nota:** `AWS_ACCES_KEY` tiene un solo `s` intencionalmente — es un typo histórico mantenido por compatibilidad con deployments existentes.

### 2.4 Requerimientos de hardware (estimaciones)

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| RAM (backend) | 4 GB | 8 GB (BGE-M3 carga ~1.5 GB en CPU) |
| Almacenamiento | 2 GB | 5 GB (modelo + ChromaDB + docs) |
| CPU | 4 núcleos | 8 núcleos |
| GPU | No requerida | Opcional (`EMBEDDING_DEVICE=cuda`) |
| Python | 3.9+ | 3.11+ |
| Node.js | 18+ | 20+ |

### 2.5 Estimaciones de rendimiento (observadas en CPU)

| Operación | Tiempo estimado |
|-----------|----------------|
| Carga inicial del modelo BGE-M3 | 15–30 s (primera vez) |
| Generación de embedding (por doc) | 0.5–2 s |
| Ingesta completa (~21 documentos) | 2–5 min |
| Query RAG completa (Groq) | 1–3 s |
| Síntesis Polly por oración | 0.3–0.8 s |
| Transcripción Whisper (Groq) | 0.5–1.5 s |

---

## 3. Análisis y Procesos

### 3.1 Flujo principal de consulta (SSE `/chat-stream`)

```
Usuario escribe o habla
        │
        ▼
[Microphone.jsx]
  MediaRecorder (audio/webm) + SpeechRecognition (auto-stop)
  → mute avatar (srcObject = null) → 150 ms drain
        │
        ▼ audio blob
[POST /transcribe]
  TranscriptionClient → Groq Whisper large-v3
  → hallucination detection (audio corto/silencio)
        │
        ▼ texto transcrito
[App.jsx: sendMessageWithText()]
        │
        ▼
[POST /chat-stream]  ←── session_id, llm_provider
        │
        ▼
[RAGChatbot.chat()]
  - Filtra historial por confianza (_history_confidence ≠ 'none')
        │
        ▼
[RAGPipeline.query_with_faq()]

  1. ENRIQUECIMIENTO DE QUERY
     ¿Es follow-up? (≤6 palabras o empieza con "y/pero/en/para/dónde…")
     → Si sí: prepend última pregunta del usuario al query de búsqueda

  2. CLASIFICACIÓN FAQ
     FAQHandler.classify_query()
     → ChromaDB: busca docs con similitud ≥ 0.65 cuyo filename empieza con "faq/"
     → best_similarity determina match_type:
        ≥ 0.75 → "high"   (solo FAQs)
        ≥ 0.65 → "medium" (FAQs + docs)
        < 0.65 → "low"    (solo docs)

  3. RECUPERACIÓN DE DOCUMENTOS (si match_type ≠ "high")
     DocumentRetriever → ChromaDB top-k×2
     → Filtra: excluye FAQs (faq/ prefix) + excluye similitud < 0.3

  4. CONSTRUCCIÓN DE CONTEXTO
     FAQHandler.get_context_for_llm()
     high   → top-3 FAQs          → context_type = "faq_only"
     medium → top-2 FAQs + top-2 docs → context_type = "faq_and_docs"
     low    → top-k docs           → context_type = "docs_only"

  5. TEMPERATURA ADAPTATIVA
     faq_only    → 0.1  (muy determinístico)
     faq_and_docs → 0.2
     docs_only   → 0.3

  6. GENERACIÓN LLM
     GroqClient.generate_response(context_type, conversation_history)
     → System prompt seleccionado por context_type (3 prompts distintos)
     → Historial inyectado como mensajes nativos user/assistant (últimos 5)
     → Respuesta completa en texto
        │
        ▼
  7. STREAMING POR ORACIONES
     Para cada oración del texto:
       a. preprocess_text_for_tts() → limpia markdown, minúsculas en siglas
       b. PollyClient.synthesize() → PCM base64 (16 kHz, mono)
       c. yield SSE: { type:"chunk", text, audio_base64 }
        │
        ▼
[App.jsx: SSE reader]
  meta  → muestra match_type, similitud, fuentes
  chunk → acumula texto (ReactMarkdown) + avatarRef.current.speak(audio_b64)
  done  → finaliza loading
        │
        ▼
[SimliAvatar.speak(pcmBase64)]
  → SimliClient.sendAudioData() → WebRTC → video + audio lip-sync
```

### 3.2 Sistema de confianza del historial

`RAGChatbot` mantiene dos listas paralelas:
- `conversation_history`: tuplas `(user_msg, assistant_msg)`
- `_history_confidence`: `match_type` por cada turno (`"high"`, `"medium"`, `"low"`, `"none"`)

Al construir el contexto para el LLM, se excluyen los turnos con `match_type = "none"` (respuestas generadas sin documentos relevantes). Esto previene que respuestas poco confiables contaminen el contexto de las siguientes consultas.

### 3.3 Gestión de sesiones (API)

```python
chat_sessions = {}            # session_id → RAGChatbot
session_llm_providers = {}    # session_id → "groq" | "deepseek"
```

- Cada sesión crea su propio `RAGChatbot` en memoria
- Si el usuario cambia de proveedor LLM (`/change-model`), el chatbot se recrea para ese session_id
- No hay persistencia entre reinicios del servidor

### 3.4 Aislamiento de audio (fix interferencia Simli ↔ Micrófono)

El stream WebRTC de Simli, si permanece activo, filtra audio al micrófono incluso con AEC activo, causando que Whisper alucine. La solución implementada es:

1. `SimliAvatar.mute()`: `audioRef.srcObject = null` → desconecta completamente el stream del pipeline de audio del OS. Guarda el stream en `savedStreamRef`.
2. `Microphone.jsx`: espera 150 ms (`await setTimeout(150)`) entre el mute del avatar y el `mediaRecorder.start()`, drenando el buffer.
3. `SimliAvatar.unmute()`: restaura `srcObject` desde `savedStreamRef` y llama `.play()`.
4. `echoCancellation: true` como red de seguridad adicional en `getUserMedia`.

### 3.5 Fix React StrictMode (doble montaje)

En desarrollo, StrictMode monta/desmonta componentes dos veces. Esto creaba múltiples `SimliClient` donde `clientRef.current` apuntaba al último creado (que nunca se conectaba).

**Solución**: `isReadyRef` (ref booleano, no estado) se pone `true` únicamente cuando el evento `'connected'` dispara **y** `clientRef.current === client` en ese momento. Cualquier cliente desactualizado no puede marcar el sistema como listo.

---

## 4. Estructura de Carga de la Información

### 4.1 Organización de documentos fuente

```
data/docs/
├── faq/                        ← Preguntas frecuentes (alta prioridad en retrieval)
│   └── faq_servicios.md        ← Identificadas en ChromaDB por prefijo "faq/"
│
├── services/                   ← Documentos de servicios VOAE
│   ├── Becas_UNAH.md
│   ├── prosene.md
│   ├── Atención_Medica.MD
│   ├── Honores_Academicos.md
│   ├── Horas_VOAE.md
│   ├── proceso_readmision.md
│   ├── Prueba_de_Orientacion.MD
│   ├── Curso_de_Introducción_Vida_Universitaria.md
│   ├── Feria_vocacional.md
│   ├── Gobierno_y_grupos_Estudiantiles.MD
│   ├── Inducción_Nuevos_Estudiantes.MD
│   ├── Visitas_Guiadas_al_Campus.MD
│   ├── Unidad_Medico_Deportiva.md
│   ├── Area_investigacion.md
│   ├── Areas_de_VOAE.md
│   └── Fechas_Importantes_2026.md
│
├── areas/
│   └── areas.md
│
└── about/
    ├── about.md
    ├── contacto.md
    └── ubicaciones.md
```

**Formato soportado:** `.md` y `.MD` (Markdown). La búsqueda es recursiva en todo el árbol de `data/docs/`.

**Convención crítica:** Los archivos dentro de `faq/` se identifican en ChromaDB por su ruta relativa (`faq/faq_servicios.md`). El sistema detecta FAQs buscando el prefijo `faq/` en el `filename` almacenado — **no** por una colección separada.

### 4.2 Pipeline de ingesta

```
data/docs/**/*.md
        │
        ▼
DocumentIngestion.load_markdown_files()
  → glob recursivo (**/*.md + **/*.MD)
  → lee con encoding UTF-8
  → filename = ruta relativa desde docs_folder (ej: "faq/faq_servicios.md")

        │
        ▼
DocumentIngestion.clean_text()
  → colapsa múltiples saltos de línea (\n\n)
  → strip por línea
  → elimina espacios múltiples y antes de puntuación

        │ (opcional: --chunk flag)
        ▼
DocumentIngestion.chunk_text(chunk_size=1000, overlap=200)
  → corta en puntos naturales (punto o \n)
  → garantiza solapamiento de 200 chars entre chunks
  → filename se convierte en: "services/Becas_UNAH.md_chunk_1"

        │
        ▼
Embedder.generate_embedding(text)
  → modelo BAAI/bge-m3 (1024 dimensiones, coseno)
  → corre en CPU por defecto (configurable: cuda, mps)

        │
        ▼
Embedder.embedding_to_bytes(embedding)
  → numpy array → bytes (serialización para ChromaDB)

        │
        ▼
DocumentRepository.insert_document(filename, content, embedding_bytes)
  → ChromaVectorStore.add_document()
  → ChromaDB: almacena { id, embedding, document (texto), metadata: {filename} }
  → Skip si documento ya existe (skip_existing=True por defecto)
  → --force para re-ingestar sobreescribiendo
```

### 4.3 Almacenamiento vectorial (ChromaDB)

| Aspecto | Detalle |
|---------|---------|
| Motor | ChromaDB con backend SQLite (`data/chroma/chroma.sqlite3`) |
| Colección | `documents` (única — FAQs y docs generales conviven) |
| Métrica de similitud | Coseno |
| Dimensión de embedding | 1024 (BGE-M3) |
| Identificación de FAQs | Por prefijo `faq/` en el campo `metadata.filename` |
| Serialización | `numpy.ndarray` → `bytes` (repository.py maneja la conversión) |
| Persistencia | En disco, sobrevive reinicios del servidor |

### 4.4 Recuperación en tiempo de consulta

```
Query del usuario (enriquecida si es follow-up)
        │
        ▼
Embedder.generate_embedding(query)   ← mismo modelo que en ingesta

        │
        ▼
ChromaVectorStore.search(query_embedding, top_k, min_similarity)
  → ChromaDB devuelve documentos ordenados por similitud coseno
  → Filtra por min_similarity (defecto: 0.3)

        │
        ▼
FAQHandler.classify_query()
  → Filtra resultados con filename que empiece en "faq/"
  → Determina match_type por best_similarity

        │
        ▼ (si match_type ≠ "high")
DocumentRetriever.retrieve_relevant_documents()
  → Recupera top_k×2 documentos
  → Excluye FAQs (para no mezclarlos en el contexto de docs_only)
  → Excluye similitud < MIN_SIMILARITY_THRESHOLD (0.3)
  → Devuelve top_k documentos más relevantes
```

### 4.5 Comandos de gestión de documentos

```bash
# Ingestar todos los documentos (omite los ya existentes)
python src/main.py --ingest

# Ingestar con chunking (útil para documentos muy largos)
python src/main.py --ingest --chunk

# Reingestar forzando sobreescritura de documentos existentes
python src/main.py --ingest --force

# Ver estadísticas del sistema (total docs, modelo, rutas)
python src/main.py --stats

# Borrar toda la base de datos vectorial
python src/main.py --reset

# Prueba manual del módulo de ingesta
python src/ingestion/ingest_docs.py
```

### 4.6 Agregar nuevos documentos

1. Crear archivo `.md` o `.MD` en `data/docs/` (en la subcarpeta correspondiente)
2. Para contenido tipo FAQ: colocar en `data/docs/faq/` — será priorizado automáticamente en el retrieval
3. Ejecutar `python src/main.py --ingest` (skip automático de los ya ingestados)
4. Verificar con `python src/main.py --stats`

**No se requiere reiniciar el servidor** si los documentos se ingestan antes de arrancar la API. Si el servidor ya está corriendo, se recomienda reiniciarlo para que `RAGPipeline` vea los nuevos embeddings (ChromaDB los persiste en disco, pero las instancias en memoria se actualizan al arrancar).

---

*Generado para el proyecto VOAE UNAH-VS — rama `feature/simli`*
