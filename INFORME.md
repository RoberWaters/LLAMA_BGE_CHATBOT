# Informe Técnico del Proyecto VOAE Chatbot
**Fecha:** 2026-02-24
---

## Propuesta

La VOAE (Vicerrectoría de Orientación y Asuntos Estudiantiles) de la UNAH atiende diariamente una gran cantidad de consultas por parte de los estudiantes, muchas de las cuales son repetitivas y podrían resolverse de manera automatizada: información sobre becas, programas de apoyo, requisitos de inscripción, fechas importantes, entre otras. Esta carga de consultas presenciales y por otros canales representa un costo operativo significativo para el personal de la VOAE, que invierte tiempo en responder preguntas que en su mayoría tienen respuestas estándar ya documentadas.

Ante esta situación, se nos solicitó apoyo para el desarrollo de un **chatbot institucional** destinado a la VOAE, con el objetivo de atender y resolver de manera ágil las dudas más frecuentes de los estudiantes, contribuyendo así a reducir la carga operativa y el volumen de consultas presenciales en las oficinas. La idea central es que el chatbot sea capaz de consultar la documentación oficial de la VOAE y generar respuestas claras, precisas y en lenguaje natural, sin necesidad de intervención humana para las preguntas frecuentes.

Adicionalmente, se planteó como parte de la propuesta incorporar un **avatar animado** dentro del chatbot, con el fin de brindar una interacción más amigable, cercana e intuitiva para el usuario final, especialmente pensando en una experiencia visual que humanice la comunicación y motive al estudiante a utilizar el sistema. Este avatar sería capaz de hablar en tiempo real sincronizando el audio generado con el movimiento de labios, haciendo la experiencia más natural.

---

## Solución

Como propuesta de implementación para el ChatBot de la VOAE, se plantea una arquitectura basada en **Retrieval-Augmented Generation (RAG)**, una técnica que combina búsqueda semántica de documentos con generación de texto por inteligencia artificial. A diferencia de un chatbot basado únicamente en un modelo de lenguaje, el enfoque RAG garantiza que las respuestas estén fundamentadas en la documentación oficial de la VOAE, minimizando las respuestas incorrectas o inventadas (conocidas como "alucinaciones" en el ámbito de la IA).

También se identificó la necesidad de contar con una **herramienta de gestión de documentos** que permita al personal de la VOAE actualizar el contenido del chatbot —agregar nuevas preguntas frecuentes, modificar servicios, actualizar fechas— sin depender de conocimientos técnicos ni del equipo de desarrollo.

### Componentes de la solución propuesta

**Vectorización y búsqueda semántica**
Para convertir los documentos y las consultas de los estudiantes en representaciones matemáticas comparables (vectores), se propone utilizar el modelo **BGE-M3** de BAAI (Beijing Academy of Artificial Intelligence). Este modelo genera vectores de 1024 dimensiones optimizados para búsqueda semántica en más de 100 idiomas, incluyendo español con terminología técnica y académica. Para almacenar y consultar estos vectores de forma eficiente, se utiliza **ChromaDB** con índice HNSW (Hierarchical Navigable Small World), que permite búsquedas aproximadas de alta velocidad incluso con grandes volúmenes de documentos.

**Generación de respuestas (LLM)**
La alternativa principal para la generación de respuestas es **Groq con el modelo Llama 3.3 70B**, elegida por su excepcional velocidad de inferencia mediante hardware LPU (Language Processing Unit), lo que garantiza respuestas casi instantáneas. Se mantiene **DeepSeek** como opción secundaria intercambiable, permitiendo cambiar de proveedor según disponibilidad, costos o preferencias institucionales sin modificar la arquitectura del sistema.

**Interacción por voz (opcional)**
Si se decide habilitar la interacción por voz, el sistema contempla:
- **Groq Whisper large-v3** para la transcripción de voz a texto (STT), con soporte nativo para español y un sistema de filtrado de alucinaciones que descarta transcripciones incorrectas.
- **Amazon Polly (voz Lupe, neural, es-US)** para la síntesis de voz a partir del texto de respuesta (TTS), generando audio de alta calidad en formato PCM16 a 16kHz.
- **Simli WebRTC** para animar un avatar en tiempo real, sincronizando el movimiento de labios con el audio generado por Polly.

**Plataforma tecnológica**
El backend se desarrolla con **FastAPI + Uvicorn**, exponiendo una API REST completa con soporte de streaming progresivo mediante Server-Sent Events (SSE), permitiendo que el frontend reciba texto y audio oración por oración en lugar de esperar la respuesta completa. El frontend se implementa con **React 18 + Vite**, ofreciendo una interfaz moderna, responsiva y fácil de usar.

**Gestión de documentos**
Se contempla el desarrollo de una aplicación paralela que permita al personal de la VOAE gestionar los documentos del chatbot —subir archivos, eliminarlos, visualizar el contenido indexado— sin necesidad de acceder al código ni a la terminal, haciendo el sistema autónomo y sostenible a largo plazo.

---

## 1. Estructura del Proyecto

### 1.1 Visión General

El proyecto implementa un chatbot RAG completo para la VOAE de la UNAH. Está organizado en tres grandes bloques:

- **`src/`**: Toda la lógica de negocio del sistema RAG, independiente de cualquier interfaz. Incluye el motor de embeddings, la base de datos vectorial, el pipeline RAG, los clientes de LLM y los módulos de voz.
- **`api/`**: Servidor FastAPI que expone los servicios del sistema como una API REST consumible por cualquier frontend o cliente externo.
- **`frontend/`**: Interfaz web en React que consume la API, gestiona el estado de la conversación, renderiza respuestas en Markdown y controla el avatar Simli.

Todo el código, comentarios, prompts del sistema y la interfaz de usuario están en **español**, dado que el sistema está diseñado exclusivamente para estudiantes hispanohablantes de la UNAH.

---

### 1.2 Árbol de Directorios

```
LLAMA_BGE_CHATBOT/
│
├── api/                            # Servidor REST (FastAPI)
│   ├── main.py                     # Endpoints, gestión de sesiones, TTS/SSE, CORS
│   └── __init__.py
│
├── src/                            # Núcleo RAG — lógica de negocio pura
│   ├── config.py                   # Configuración centralizada: lee .env y expone clases
│   ├── main.py                     # CLI: ingesta, consultas, estadísticas, reset
│   ├── chat.py                     # Chatbot interactivo en consola (debug/desarrollo)
│   │
│   ├── chatbot/
│   │   └── chatbot.py              # RAGChatbot: historial, filtrado por sesión, confianza
│   │
│   ├── database/
│   │   ├── chroma_vector_store.py  # Wrapper ChromaDB: HNSW, cosine, CRUD vectorial
│   │   └── repository.py           # Capa de repositorio: bytes↔numpy, abstracción CRUD
│   │
│   ├── embeddings/
│   │   └── embedder.py             # BGE-M3: genera vectores 1024D normalizados
│   │
│   ├── ingestion/
│   │   └── ingest_docs.py          # Carga, limpieza, chunking e indexación de documentos
│   │
│   ├── llm/
│   │   ├── groq_client.py          # Cliente Groq: Llama 3.3 70B, prompts VOAE, historial
│   │   ├── deepseek_client.py      # Cliente DeepSeek: mismo prompt que Groq, API REST
│   │   ├── polly_client.py         # Amazon Polly: síntesis PCM16 a 16kHz, voz Lupe
│   │   └── transcription_client.py # Whisper STT: transcripción con filtro de alucinaciones
│   │
│   └── rag/
│       ├── rag_pipeline.py         # Orquestador RAG: ingesta + query_with_faq + stats
│       ├── faq_handler.py          # Sistema híbrido FAQ: umbrales 75%/65%, enriquecimiento
│       └── retriever.py            # Recuperador semántico: HNSW con filtro por umbral
│
├── frontend/                       # Interfaz de usuario — React 18 + Vite
│   ├── src/
│   │   ├── App.jsx                 # Componente raíz: estado, SSE, streaming progresivo
│   │   ├── App.css                 # Estilos de la interfaz
│   │   ├── components/
│   │   │   ├── Microphone.jsx      # Grabación de audio webm/opus, detección de silencio
│   │   │   └── SimliAvatar.jsx     # Cliente WebRTC Simli: speak(), mute(), unmute()
│   │   └── services/
│   │       └── speechToText.mjs   # Servicio STT: POST /transcribe, retorna {text}
│   ├── package.json                # Dependencias npm: React, Axios, Simli, etc.
│   ├── vite.config.js              # Configuración Vite (bundler)
│   └── .env.example                # Variables requeridas: VITE_API_URL, SIMLI_*
│
├── data/
│   ├── docs/                       # Documentos fuente para indexar (solo .md y .txt)
│   │   ├── faq/                    # Preguntas frecuentes — detección automática por prefijo
│   │   │   └── faq_servicios.md
│   │   ├── about/                  # Info institucional: misión, contactos, ubicaciones
│   │   ├── areas/                  # Descripción de cada área y departamento de la VOAE
│   │   └── services/               # Programas, becas, requisitos, fechas importantes
│   └── chroma/                     # Base de datos vectorial persistente (archivos HNSW)
│
├── requirements.txt                # Dependencias Python del backend
├── .env.example                    # Plantilla de todas las variables de entorno
├── README.md                       # Documentación general del proyecto

```

---

### 1.3 Stack Tecnológico

| Capa | Tecnología | Rol en el sistema |
|------|-----------|-------------------|
| **LLM principal** | Groq — Llama 3.3 70B | Genera las respuestas en lenguaje natural a partir del contexto recuperado. Se elige por su velocidad de inferencia (LPU hardware) |
| **LLM alternativo** | DeepSeek — deepseek-chat | Opción secundaria intercambiable sin cambiar arquitectura. Útil si Groq no está disponible |
| **Embeddings** | BGE-M3 (BAAI/bge-m3) | Convierte texto a vectores de 1024 dimensiones para búsqueda semántica. Soporta 100+ idiomas y textos de hasta 8192 tokens |
| **Base de datos vectorial** | ChromaDB + HNSW | Almacena y busca vectores de forma eficiente usando similitud coseno. Persiste en disco automáticamente |
| **STT (voz → texto)** | Groq Whisper large-v3 | Transcribe el audio del estudiante a texto en español. Siempre usa Groq independiente del LLM seleccionado |
| **TTS (texto → voz)** | Amazon Polly — Lupe (neural) | Sintetiza las respuestas en audio PCM16 a 16kHz, formato requerido por Simli |
| **Avatar animado** | Simli WebRTC | Recibe el audio PCM y anima un avatar en tiempo real sincronizando labios con el habla |
| **Backend** | FastAPI + Uvicorn | Servidor web asíncrono. Expone REST + WebSocket + SSE. Maneja sesiones, CORS y streaming |
| **Frontend** | React 18 + Vite | Interfaz de usuario de página única (SPA). Consume SSE para streaming progresivo de texto y audio |

---

### 1.4 Dependencias Principales

**Python (`requirements.txt`)**

| Paquete | Propósito |
|---------|-----------|
| `sentence-transformers` | Carga y ejecuta el modelo BGE-M3 para generar embeddings |
| `chromadb` | Base de datos vectorial embebida con índice HNSW |
| `fastapi` + `uvicorn` | Servidor web asíncrono con soporte SSE y WebSocket |
| `groq` | SDK oficial para acceder a Groq API (Llama + Whisper) |
| `boto3` | SDK de AWS para Amazon Polly (TTS) |
| `pydantic` | Validación de modelos de datos en los endpoints de la API |
| `python-multipart` | Soporte para subida de archivos de audio en `/transcribe` |
| `python-dotenv` | Carga automática de variables desde `.env` |
| `numpy` | Operaciones numéricas sobre vectores de embeddings |

**JavaScript (`frontend/package.json`)**

| Paquete | Propósito |
|---------|-----------|
| `react` + `react-dom` | Framework de interfaz de usuario |
| `axios` | Cliente HTTP para llamadas a la API |
| `simli-client` | SDK para integrar el avatar WebRTC de Simli |
| `react-markdown` | Renderiza las respuestas del LLM como Markdown formateado |
| `lucide-react` | Iconos de interfaz (micrófono, envío, etc.) |
| `vite` | Bundler de desarrollo y producción ultrarrápido |

---

## 2. Análisis y Procesos

### 2.1 Flujo Completo de una Consulta de Voz

Este es el recorrido completo de una interacción cuando el estudiante usa la entrada de voz. Cada etapa transforma la información de una forma hasta llegar a la respuesta final hablada por el avatar:

```
┌─────────────────────────────────────────────────────────────┐
│  ENTRADA: Estudiante habla frente al micrófono              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │      Microphone.jsx       │
            │  - Solicita permiso mic   │
            │  - Graba audio webm/opus  │
            │    (MediaRecorder API)    │
            │  - Web Speech API detecta │
            │    fin del habla          │
            └───────────────────────────┘
                            │
                     Audio blob (webm)
                            │
                            ▼
            ┌───────────────────────────┐
            │   POST /transcribe        │
            │   {audio_blob}            │
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │   TranscriptionClient     │
            │  - Groq Whisper large-v3  │
            │  - Idioma forzado: es     │
            │  - Pista de vocabulario:  │
            │    VOAE, UNAH, PAC,       │
            │    PROSENE, PASEE...      │
            │  - Filtro alucinaciones:  │
            │    ├ Descarta genéricos   │
            │    ├ Descarta silencios   │
            │    └ Valida longitud      │
            └───────────────────────────┘
                            │
             { text: "¿Requisitos beca?" }
                            │
                            ▼
            ┌───────────────────────────┐
            │  POST /chat-stream        │
            │  {message, session_id,    │
            │   llm_provider}           │
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │     RAGChatbot.chat()     │
            │  - Recupera historial     │
            │  - Filtra turnos sin      │
            │    contexto (match='none')│
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │ RAGPipeline.query_with_   │
            │ faq()                     │
            │                           │
            │  1. FAQHandler.classify() │
            │     ├ Embedder: vector    │
            │     │  1024D de consulta  │
            │     ├ ChromaDB: busca en  │
            │     │  faq/ únicamente    │
            │     └ Evalúa similitud:   │
            │       ≥0.75 → HIGH        │
            │       ≥0.65 → MEDIUM      │
            │       <0.65 → LOW         │
            │                           │
            │  2. DocumentRetriever     │
            │     (si LOW o MEDIUM)     │
            │     ├ HNSW en docs generales│
            │     └ Filtra por umbral   │
            │                           │
            │  3. Arma contexto según   │
            │     match_type            │
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │  GroqClient /             │
            │  DeepSeekClient           │
            │  - System prompt VOAE     │
            │    (1 de 3 variantes)     │
            │  - Historial últimas 5    │
            │    rondas filtradas       │
            │  - Contexto recuperado    │
            │  - Temperatura ajustada   │
            └───────────────────────────┘
                            │
                    Respuesta completa en texto
                            │
                            ▼
            ┌───────────────────────────┐
            │   split_sentences()       │
            │   Divide en oraciones     │
            │   usando [.!?]\s+         │
            └───────────────────────────┘
                            │
                 Por cada oración (streaming):
                            │
                            ▼
            ┌───────────────────────────┐
            │ preprocess_text_for_tts() │
            │  - Elimina markdown       │
            │  - Acrónimos → minúsculas │
            │    (VOAE→voae, UNAH→unah) │
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │   PollyClient.synthesize()│
            │  - Voz: Lupe (neural)     │
            │  - Formato: PCM16 16kHz   │
            │  - Resultado: base64      │
            └───────────────────────────┘
                            │
            SSE event: { type:"chunk",
                         text:"...",
                         audio_base64:"..." }
                            │
                            ▼
            ┌───────────────────────────┐
            │        App.jsx            │
            │  - Acumula texto          │
            │  - Renderiza Markdown     │
            │    progresivamente        │
            │  - Pasa audio a avatar    │
            └───────────────────────────┘
                            │
                            ▼
            ┌───────────────────────────┐
            │     SimliAvatar.jsx       │
            │  - WebRTC con Simli       │
            │  - speak(pcmBase64)       │
            │  - Sincroniza labios con  │
            │    el audio recibido      │
            └───────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  SALIDA: Avatar habla la respuesta en tiempo real           │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.2 Sistema Híbrido de FAQs — El Corazón del Sistema

El proposito del módulo `FAQHandler` (`src/rag/faq_handler.py`) es lograr un equilibrio entre **precisión** (respuestas exactas para preguntas conocidas) y **cobertura** (respuestas razonadas para preguntas abiertas).

#### ¿Por qué un sistema híbrido?

Un chatbot RAG simple siempre busca en todos los documentos y deja que el LLM razone. El problema es que para preguntas frecuentes bien documentadas, esto introduce variabilidad innecesaria y riesgo de que el LLM "improvise". Por otro lado, un chatbot de FAQs puro no puede responder preguntas que no están exactamente en la base de datos. El sistema híbrido combina ambos mundos.

#### Lógica de tres niveles

```
                    Consulta del estudiante
                             │
                  Embedder convierte a vector 1024D
                             │
              ChromaDB busca SOLO en documentos faq/
              (los documentos generales se ignoran aquí)
                             │
                  ┌──────────────────────┐
                  │ Score de similitud   │
                  │   coseno más alto    │
                  └──────────────────────┘
                        │         │         │
                     ≥ 0.75    0.65-0.74   < 0.65
                        │         │         │
                      HIGH      MEDIUM      LOW
                        │         │         │
                   ┌────┴──┐ ┌───┴───┐ ┌───┴────┐
                   │Contexto│ │Context│ │Contexto│
                   │solo de │ │híbrido│ │solo de │
                   │FAQs    │ │FAQ+Doc│ │docs    │
                   │(top-3) │ │(2+2)  │ │(top-3) │
                   └────┬──┘ └───┬───┘ └───┬────┘
                        │         │         │
                   temp=0.1  temp=0.2  temp=0.3
```

**HIGH (≥75% similitud):** La pregunta tiene una respuesta directa en las FAQs. Se usa solo ese contexto con temperatura muy baja (0.1), logrando respuestas deterministas y precisas.

**MEDIUM (65-74%):** La pregunta es similar a una FAQ pero puede necesitar contexto adicional. Se combinan las 2 FAQs más relevantes con los 2 documentos más relevantes, con temperatura moderada (0.2).

**LOW (<65%):** La pregunta no tiene correlato en las FAQs. Se busca en los documentos generales con temperatura más alta (0.3), permitiendo al LLM razonar con más libertad sobre información que puede ser más variada.

#### Detección automática de FAQs

No hay configuración manual. Cualquier archivo cuya ruta relativa comience con `faq/` (dentro de `data/docs/`) es automáticamente tratado como FAQ. Esto significa que agregar nuevas FAQs es tan simple como colocar un archivo en esa carpeta y re-ingestar.

#### Enriquecimiento de consultas de seguimiento

El sistema detecta cuando una pregunta es demasiado corta o comienza con un pronombre ("¿Y eso?", "¿Cuándo es?", "¿Dónde?") e internamente la enriquece concatenando el mensaje anterior del usuario. Esto mejora significativamente la búsqueda semántica para conversaciones de múltiples turnos.

---

### 2.3 Gestión del Historial de Conversación

Cada instancia de `RAGChatbot` mantiene su propio historial de conversación, permitiendo que el LLM tenga contexto de intercambios previos y pueda responder preguntas de seguimiento con coherencia.

#### Estructura interna

```
RAGChatbot (por sesión)
├── conversation_history: List[Tuple[str, str]]
│     └─ Cada elemento: (mensaje_usuario, respuesta_asistente)
│        Máximo: 10 entradas (configurable)
│
└── confidence_history: List[str]
      └─ match_type por cada turno: 'high', 'medium', 'low', 'none'
         Permite saber qué tan confiable fue cada respuesta
```

#### Filtrado inteligente por calidad

Antes de enviar el historial al LLM, se aplica un filtro crítico: se excluyen los turnos donde `match_type = 'none'` (respuestas sin contexto recuperado). Esto evita que una respuesta improvisada o incorrecta del LLM "contamine" el contexto de futuras consultas, reduciendo el riesgo de alucinaciones acumuladas.

```
Historial completo (10 turnos):
  [turno 1: high] ✓ se incluye
  [turno 2: none] ✗ se excluye (sin contexto)
  [turno 3: medium] ✓ se incluye
  [turno 4: none] ✗ se excluye
  [turno 5: low] ✓ se incluye
  ...

→ Al LLM se envían las últimas 5 rondas del historial filtrado,
  inyectadas como mensajes alternos user/assistant antes del prompt actual
```

#### Limitación de diseño

Cambiar el proveedor LLM (Groq ↔ DeepSeek) durante una sesión destruye la instancia del chatbot para esa sesión, perdiendo el historial. Esto es una decisión de diseño consciente para evitar inconsistencias entre modelos.

---

### 2.4 Gestión de Sesiones en la API

La API gestiona múltiples usuarios simultáneos mediante un sistema de sesiones basado en identificadores únicos.

```
Frontend genera: session_id = "session-" + Date.now()
                        │
                        │ Se incluye en cada request:
                        │   POST /chat      { session_id, message, ... }
                        │   POST /chat-stream { session_id, message, ... }
                        │   GET  /history?session_id=...
                        ▼
                 api/main.py (en memoria)
                 ┌────────────────────────────────┐
                 │ chat_sessions: dict            │
                 │   "session-1708..." → RAGChatbot│
                 │   "session-1708..." → RAGChatbot│
                 │                                │
                 │ session_llm_providers: dict    │
                 │   "session-1708..." → "groq"  │
                 │   "session-1708..." → "deepseek"│
                 └────────────────────────────────┘
```

**Consideración importante:** Las sesiones viven solo en memoria RAM. Si el servidor se reinicia, todas las sesiones y sus historiales se pierden. 
---

### 2.5 Endpoints de la API

La API expone los siguientes endpoints, todos en `api/main.py`:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/chat` | Envía un mensaje y recibe la respuesta completa en JSON. Incluye metadata: `match_type`, `sources`, `temperature` usada |
| `POST` | `/chat-stream` | SSE: ejecuta el pipeline RAG y envía texto + audio PCM oración por oración para el avatar Simli |
| `GET` | `/stats` | Estadísticas del sistema: documentos indexados, colecciones, tamaño de la base vectorial |
| `POST` | `/transcribe` | Recibe un archivo de audio (multipart) y devuelve la transcripción en texto |
| `WS` | `/ws/transcribe` | WebSocket para transcripción en tiempo real: recibe chunks Float32 PCM y devuelve texto |
| `POST` | `/synthesize` | Recibe texto y devuelve audio PCM base64 generado por Amazon Polly |
| `POST` | `/change-model` | Cambia el proveedor LLM de la sesión (recrea el chatbot, borra historial) |
| `GET` | `/history` | Retorna el historial de conversación de una sesión |
| `POST` | `/clear-history` | Borra el historial de una sesión sin eliminarla |
| `DELETE` | `/session/{id}` | Elimina completamente una sesión |
| `GET` | `/sessions` | Lista todas las sesiones activas |
| `GET` | `/health` | Health check: verifica que el servidor está respondiendo |

---

### 2.6 Sistema de Prompts del LLM

Ambos clientes LLM (`groq_client.py` y `deepseek_client.py`) contienen prompts del sistema idénticos que definen la personalidad y restricciones del chatbot. Existen tres variantes que se seleccionan automáticamente según el `match_type`:

| Variante | Contexto incluido | Temperatura | Comportamiento esperado |
|----------|------------------|-------------|------------------------|
| `faq_only` | Solo FAQs relevantes | 0.1 | Muy determinista. Responde exactamente lo que dice la FAQ |
| `faq_and_docs` | FAQs + documentos | 0.2 | Balanceado. Combina precisión de FAQ con contexto adicional |
| `docs_only` | Solo documentos generales | 0.3 | Más flexible. El LLM razona sobre documentación más amplia |

Los prompts instruyen al LLM para: responder siempre en español, mantener la personalidad de asistente de la VOAE, no inventar información que no esté en el contexto, y no hacer referencias meta al sistema de contexto o a los documentos de forma explícita.

> **Punto crítico de mantenimiento:** los prompts están duplicados en ambos archivos de clientes. Cualquier modificación debe replicarse manualmente en los dos archivos para mantener coherencia.

---

### 2.7 Preprocesamiento de Texto para TTS

Antes de enviar cada oración a Amazon Polly, se aplica una función de limpieza que garantiza que el audio generado suene natural:

**Paso 1 — Eliminación de marcado Markdown**
El LLM puede responder con formato Markdown (negritas, listas, encabezados). Polly leería literalmente los asteriscos y almohadillas si no se procesan. La función elimina: `**negritas**`, `*cursivas*`, `## encabezados`, `- listas`, `1. listas numeradas`.

**Paso 2 — Normalización de acrónimos institucionales**
Polly no sabe cómo pronunciar siglas como "VOAE" o "UNAH" correctamente en español. Al convertirlas a minúsculas (`voae`, `unah`), Polly las pronuncia letra por letra de forma natural. Los acrónimos normalizados incluyen: VOAE, UNAH, UNAH-VS, VRA, DIPP, PAC, PASEE, PROCAD, PROSENE, CIVU, PAIE, PAI-E, PAPE, PHUMA, IAG.

---

## 3. Estructura de Carga de la Información

### 3.1 ¿Qué es la "carga de información"?

En un sistema RAG, la información que el chatbot puede utilizar para responder no está en el modelo de lenguaje — está en una base de datos vectorial que se construye a partir de documentos. El proceso de "carga" o "ingesta" convierte archivos de texto en vectores matemáticos que el sistema puede buscar y comparar por similitud semántica.

Este proceso es **offline** (se ejecuta una vez o cuando hay nuevos documentos) y separado del proceso de consulta en línea.

---

### 3.2 Organización de los Documentos Fuente

Los documentos que alimentan el chatbot se organizan en `data/docs/` con una estructura de carpetas que refleja el tipo de contenido:

```
data/docs/
│
├── faq/                    ← PREGUNTAS FRECUENTES
│   └── faq_servicios.md    │  Detección automática: cualquier archivo
│                           │  en esta carpeta es tratado como FAQ.
│                           │  Formato sugerido: pregunta + respuesta directa.
│
├── about/                  ← INFORMACIÓN INSTITUCIONAL
│   │                       │  Misión, visión, historia de la VOAE.
│   └── ...                 │  Datos de contacto, ubicaciones, horarios.
│
├── areas/                  ← ÁREAS Y DEPARTAMENTOS
│   │                       │  Descripción de cada área dentro de la VOAE.
│   └── ...                 │  Funciones, responsables, servicios que ofrece.
│
└── services/               ← SERVICIOS Y PROGRAMAS
    │                       │  Becas, programas de apoyo, requisitos,
    └── ...                 │  procesos de solicitud, fechas importantes.
```

**Formatos aceptados:** únicamente `.md` (Markdown) y `.txt` (texto plano). Se recomienda Markdown por su estructura clara y legible.

**Regla de detección de FAQs:** es completamente automática. El sistema verifica si el `filename` del documento (relativo a `data/docs/`) comienza con `"faq/"`. No es necesario configurar nada ni modificar código para agregar nuevas FAQs.

---

### 3.3 Pipeline de Ingesta — Paso a Paso

El pipeline de ingesta transforma cada documento de texto en un vector almacenado en ChromaDB:

```
Comando de inicio:
python src/main.py --ingest [--chunk] [--force]
        │
        │  --chunk : activa la fragmentación de documentos largos
        │  --force : re-procesa aunque el doc ya exista en la BD
        ▼
DocumentIngestion.process_documents()
        │
        ├─── PASO 1: Descubrimiento
        │    ├─ Escanea data/docs/ recursivamente
        │    ├─ Incluye: .md, .txt
        │    └─ Para cada archivo:
        │         Si no existe --force y ya está indexado → omite
        │         Si no existe o hay --force → procesa
        │
        ├─── PASO 2: Lectura y limpieza
        │    ├─ Lee el contenido completo del archivo
        │    ├─ Normaliza espacios múltiples → espacio simple
        │    ├─ Normaliza saltos de línea excesivos
        │    └─ Elimina caracteres especiales problemáticos
        │
        ├─── PASO 3: Fragmentación (opcional, con --chunk)
        │    ├─ Divide el documento en chunks de 1000 caracteres
        │    ├─ Overlap de 200 caracteres entre chunks consecutivos
        │    │    (evita perder contexto en los bordes de cada chunk)
        │    └─ Intenta quebrar en puntos naturales (. \n)
        │         para no cortar oraciones a la mitad
        │
        ├─── PASO 4: Generación de embeddings
        │    ├─ Por cada documento (o chunk):
        │    │    Embedder.generate_embedding(texto)
        │    ├─ Modelo: BAAI/bge-m3 (descarga automática ~2GB)
        │    ├─ Salida: vector float32 de 1024 dimensiones
        │    └─ Normalización L2 automática (prepara para coseno)
        │
        └─── PASO 5: Almacenamiento en ChromaDB
             ├─ ChromaVectorStore.add_document(
             │       id=hash_del_archivo,
             │       embedding=vector_1024D,
             │       document=texto_original,
             │       metadata={filename, source, chunk_index}
             │  )
             └─ ChromaDB persiste automáticamente en data/chroma/
```

---

### 3.4 El Modelo de Embeddings: BGE-M3

**BGE-M3** (BAAI General Embedding, versión M3) es el modelo de vectorización elegido. Su selección se basa en:

- **Multilingüe:** soporta más de 100 idiomas. Maneja el español académico con términos técnicos como "VOAE", "PAC", "PROSENE" sin perder calidad semántica.
- **Alta dimensionalidad:** genera vectores de 1024 dimensiones, capturando matices semánticos sutiles que modelos más pequeños pierden.
- **Contexto largo:** procesa hasta 8192 tokens por documento, lo que significa que la mayoría de los documentos de la VOAE caben íntegros sin necesidad de chunking.
- **Normalización automática:** los vectores salen L2-normalizados, lo que hace que la similitud coseno sea equivalente al producto punto — más eficiente computacionalmente.

```python
# Uso en src/embeddings/embedder.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")
embedding = model.encode(texto, normalize_embeddings=True)
# Resultado: numpy array float32, shape (1024,)
# Rango de cada dimensión: aproximadamente [-1, 1]
```

El modelo se descarga automáticamente desde Hugging Face la primera vez que se ejecuta (~2 GB). Luego queda en caché local.

---

### 3.5 Almacenamiento Vectorial: ChromaDB con HNSW

ChromaDB es la base de datos vectorial que almacena todos los documentos indexados. Sus características en este sistema:

| Aspecto | Configuración / Detalle |
|---------|------------------------|
| **Índice** | HNSW — permite búsquedas aproximadas de vecinos cercanos con complejidad O(log n) |
| **Métrica** | Distancia coseno. Se convierte a similitud: `similitud = 1 - distancia` |
| **Colección** | Una sola colección llamada `"documents"`. FAQs y docs generales coexisten |
| **Diferenciación** | No hay colecciones separadas. Los FAQs se identifican por el prefijo `faq/` en el campo `filename` de los metadatos |
| **Filtrado en búsqueda** | ChromaDB filtra por metadatos en tiempo de búsqueda. Para buscar solo FAQs: `where={"filename": {"$startswith": "faq/"}}` |
| **Persistencia** | Automática. Los datos se guardan en `data/chroma/` sin necesidad de comandos explícitos |
| **Dimensiones** | Fijas en 1024 (deben coincidir con la salida del modelo BGE-M3) |

**¿Cómo funciona la similitud coseno?**

La similitud coseno mide qué tan parecidos son dos vectores observando el **ángulo** entre ellos, sin importar su magnitud. Cuanto menor es el ángulo, mayor es la similitud semántica entre los textos que representan.

```
                     B₁ (FAQ "requisitos beca Honor")
                    /
                   / θ₁ ≈ 10°  →  sim ≈ 0.98  →  HIGH ✓
                  /
origen ───────────────────────────────►  A (consulta: "¿requisitos beca Honor?")
                  \
                   \ θ₂ ≈ 75°  →  sim ≈ 0.26  →  LOW ✗
                    \
                     B₂ (doc "horarios de la VOAE")
```

**Fórmula:**

```
            A · B            Σ (Aᵢ × Bᵢ)
sim(A,B) = ────────────  =  ─────────────────────
           ‖A‖ × ‖B‖        √Σ(Aᵢ²) × √Σ(Bᵢ²)
```

Como BGE-M3 entrega vectores L2-normalizados (`‖A‖ = ‖B‖ = 1`), el denominador siempre vale 1, reduciendo el cálculo a un simple producto punto: `sim(A, B) = Σ (Aᵢ × Bᵢ)`. El resultado va de **0** (sin relación semántica) a **1** (vectores idénticos). ChromaDB reporta distancia coseno internamente, por lo que el sistema convierte: `similitud = 1 − distancia`.

**¿Por qué HNSW?**
HNSW (Hierarchical Navigable Small World) es un algoritmo de grafos que organiza los vectores en capas jerárquicas. Permite encontrar los N vecinos más cercanos a una consulta sin comparar contra todos los documentos (fuerza bruta), lo que escala eficientemente a medida que crece la base documental.

---

### 3.6 Ciclo de Vida Completo de un Documento

```
┌────────────────────────────────────────────────────────────────┐
│  1. CREACIÓN                                                   │
│     Personal de VOAE escribe o actualiza un .md en data/docs/ │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  2. INGESTA                                                    │
│     python src/main.py --ingest                               │
│     → Texto → Embedding 1024D → ChromaDB (HNSW)               │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  3. RECUPERACIÓN (en tiempo real, por cada consulta)          │
│     FAQHandler: busca en faq/ → similitud coseno              │
│     DocumentRetriever: busca en docs generales → similitud     │
│     → Selecciona top-K documentos más relevantes              │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  4. CONTEXTUALIZACIÓN                                          │
│     El contenido recuperado se incluye en el prompt del LLM   │
│     junto con el historial de conversación                    │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  5. RESPUESTA                                                  │
│     LLM genera respuesta basada en el contexto recuperado     │
│     TTS convierte a audio → Avatar lo habla                   │
└────────────────────────────────────────────────────────────────┘
```

---

### 3.7 Proceso de Consulta Semántica en Detalle

Cuando llega una pregunta del estudiante, el sistema ejecuta la búsqueda de la siguiente forma:

```
Consulta: "¿Cuáles son los requisitos para la beca Honor?"
                    │
                    ▼
        Embedder genera vector_consulta (1024D)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   Búsqueda en faq/      Búsqueda en docs generales
   (ChromaDB filtra       (todos los demás documentos)
    por metadata)
         │                     │
         ▼                     ▼
  Similitud coseno:       Similitud coseno:
  faq_beca.md → 0.82     servicios.md → 0.71
  faq_prog.md → 0.61     areas.md     → 0.58
  faq_proc.md → 0.54     about.md     → 0.43
         │
         ▼
  Score más alto en FAQ: 0.82 → HIGH match
         │
         ▼
  Contexto: solo FAQs top-3
  Temperatura: 0.1
         │
         ▼
  LLM recibe:
  [System prompt faq_only]
  [Historial filtrado]
  [Contexto: top-3 FAQs]
  [Pregunta del usuario]
```

---

### 3.8 Actualización y Mantenimiento de Documentos

| Operación | Comando | Cuándo usar |
|-----------|---------|-------------|
| Ingesta inicial | `python src/main.py --ingest` | Primera vez, o al agregar documentos nuevos |
| Re-ingestar con chunking | `python src/main.py --ingest --chunk` | Documentos largos (>2000 palabras) que necesitan fragmentarse |
| Forzar re-procesado | `python src/main.py --ingest --force` | Cuando se modifica el contenido de un documento ya indexado |
| Ver estadísticas | `python src/main.py --stats` | Verificar cuántos documentos están indexados y el estado del sistema |
| Resetear base de datos | `python src/main.py --reset` | Borrar toda la base vectorial y empezar desde cero |

**Flujo recomendado para actualizar contenido:**
1. Editar o agregar el archivo `.md`/`.txt` en la carpeta correspondiente de `data/docs/`
2. Ejecutar `python src/main.py --ingest --force` para re-indexar documentos modificados
3. Los cambios son inmediatos en las siguientes consultas (no requiere reiniciar el servidor)

---

## 4. Configuración del Entorno

### 4.1 Variables de Entorno

Toda la configuración del sistema vive en un archivo `.env` en la raíz del proyecto. `src/config.py` lee estas variables y las expone como clases tipadas a todos los módulos:

```env
# ─── Proveedores LLM ───────────────────────────────────────────
GROQ_API_KEY=gsk_...          # Requerido siempre (Whisper STT usa Groq)
DEEPSEEK_API_KEY=sk-...       # Solo si se usa DeepSeek como LLM

# ─── Amazon Polly (síntesis de voz) ───────────────────────────
AWS_ACCES_KEY=...              # Nota: una sola 'S' — typo intencional
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# ─── Sistema de FAQs ───────────────────────────────────────────
FAQ_HIGH_THRESHOLD=0.75        # ≥ 75%: solo FAQs
FAQ_MEDIUM_THRESHOLD=0.65      # ≥ 65%: FAQs + docs

# ─── Temperaturas del LLM ──────────────────────────────────────
TEMPERATURE_FAQ_ONLY=0.1
TEMPERATURE_HYBRID=0.2
TEMPERATURE_DOCS_ONLY=0.3

# ─── ChromaDB ──────────────────────────────────────────────────
CHROMA_PATH=data/chroma
COLLECTION_NAME=documents

# ─── Recuperación ──────────────────────────────────────────────
TOP_K=3                        # Documentos a recuperar por consulta
MIN_SIMILARITY=0.50            # Umbral mínimo para incluir un doc

# ─── Frontend (.env dentro de frontend/) ───────────────────────
VITE_API_URL=http://localhost:8000
SIMLI_API_KEY=...              # Credenciales del avatar Simli
SIMLI_FACE_ID=...
```

### 4.2 Flujo de Configuración

```
.env (archivo en raíz del proyecto)
      │
      ▼
src/config.py
  ├─ FAQConfig        → FAQ_HIGH_THRESHOLD, FAQ_MEDIUM_THRESHOLD
  ├─ RetrievalConfig  → TOP_K, MIN_SIMILARITY
  ├─ EmbeddingConfig  → modelo BGE-M3, dimensiones
  ├─ ChromaDBConfig   → CHROMA_PATH, COLLECTION_NAME
  ├─ LLMConfig        → GROQ_API_KEY, DEEPSEEK_API_KEY, temperaturas
  ├─ IngestionConfig  → extensiones permitidas, chunk size, overlap
  ├─ ChatbotConfig    → max_history (default=10)
  ├─ APIConfig        → host, puerto, CORS origins
  └─ PollyConfig      → AWS_ACCES_KEY, voz, región, formato audio
      │
      ▼
Todos los módulos importan desde config.py:
  ├─ Embedder           ← EmbeddingConfig
  ├─ ChromaVectorStore  ← ChromaDBConfig
  ├─ RAGPipeline        ← RetrievalConfig + FAQConfig
  ├─ GroqClient         ← LLMConfig
  ├─ DeepSeekClient     ← LLMConfig
  └─ PollyClient        ← PollyConfig
```

---

## 5. Resumen Ejecutivo

El sistema implementa un chatbot institucional completo para la VOAE-UNAH con las siguientes características clave:

**1. RAG híbrido con detección de FAQs por similitud semántica**
En lugar de un enfoque único, el sistema adapta dinámicamente su estrategia de respuesta según qué tan similar es la pregunta a las FAQs conocidas. Las preguntas frecuentes reciben respuestas precisas y deterministas (temperatura 0.1); las preguntas abiertas reciben respuestas más flexibles con mayor contexto (temperatura 0.3). Esto reduce alucinaciones sin sacrificar cobertura.

**2. Voz bidireccional con avatar animado**
El estudiante puede hablar directamente al chatbot. Groq Whisper transcribe el audio con un filtro de alucinaciones especializado en vocabulario de la UNAH. La respuesta se sintetiza en voz mediante Amazon Polly y se reproduce sincronizada con el movimiento de labios del avatar Simli vía WebRTC, creando una experiencia de conversación natural.

**3. Ingesta modular y autónoma**
Los documentos se organizan en carpetas temáticas simples. La carpeta `faq/` tiene tratamiento especial automático. Agregar o actualizar contenido es tan simple como editar un archivo `.md` y ejecutar un comando de ingesta, sin necesidad de conocimientos técnicos profundos.

**4. Historial de conversación con filtrado por calidad**
Cada sesión mantiene un historial filtrado que excluye las respuestas sin contexto confiable. Esto garantiza que el LLM siempre trabaje con antecedentes de calidad, reduciendo la acumulación de errores en conversaciones largas.

**5. Arquitectura extensible y configurable**
Todos los parámetros críticos (umbrales FAQ, temperaturas, modelo LLM, voz TTS) son configurables via `.env` sin modificar código. El sistema soporta dos proveedores LLM intercambiables por sesión, facilitando pruebas y migración entre servicios según disponibilidad o costos.

**6. Gestión de documentos sin intervención técnica (planificada)**
Se contempla una aplicación paralela que permita al personal de la VOAE gestionar el contenido del chatbot mediante una interfaz visual, sin necesidad de acceder a la terminal ni al código fuente, asegurando la sostenibilidad del sistema a largo plazo.
