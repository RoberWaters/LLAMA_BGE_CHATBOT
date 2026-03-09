# Guia de Despliegue - Chatbot VOAE (AWS)

Esta guia explica como esta configurado el despliegue del Chatbot VOAE en AWS, usando Lambda, API Gateway y S3.

---

## Tabla de Contenidos

1. [Vision General](#1-vision-general)
2. [Como Funciona Todo (El Flujo Completo)](#2-como-funciona-todo-el-flujo-completo)
3. [Servicios AWS Utilizados](#3-servicios-aws-utilizados)
4. [El Backend (FastAPI en Lambda)](#4-el-backend-fastapi-en-lambda)
5. [El Frontend (React en S3)](#5-el-frontend-react-en-s3)
6. [El Avatar (Simli)](#6-el-avatar-simli)
7. [La Transcripcion de Voz (Amazon Transcribe)](#7-la-transcripcion-de-voz-amazon-transcribe)
8. [La Sintesis de Voz (Amazon Polly)](#8-la-sintesis-de-voz-amazon-polly)
9. [La Inteligencia Artificial (Amazon Bedrock)](#9-la-inteligencia-artificial-amazon-bedrock)
10. [Estructura de Archivos](#10-estructura-de-archivos)
11. [Variables de Entorno](#11-variables-de-entorno)
12. [Como Se Empaqueta Lambda](#12-como-se-empaqueta-lambda)
13. [Endpoints de la API](#13-endpoints-de-la-api)
14. [Manejo de Sesiones](#14-manejo-de-sesiones)
15. [Seguridad y Credenciales](#15-seguridad-y-credenciales)
16. [Paso a Paso: Desplegar Desde Cero](#16-paso-a-paso-desplegar-desde-cero)
17. [Problemas Conocidos y Soluciones](#17-problemas-conocidos-y-soluciones)
18. [Desarrollo Local](#18-desarrollo-local)

---

## 1. Vision General

El Chatbot VOAE es una aplicacion web que permite a los estudiantes de la UNAH hacer preguntas sobre servicios de la Vicerrectoria de Orientacion y Asuntos Estudiantiles (VOAE). La aplicacion tiene:

- **Un chatbot con IA** que responde preguntas usando documentos reales de la VOAE
- **Un avatar virtual** (Simli) que habla las respuestas con movimiento de labios
- **Reconocimiento de voz** para que el estudiante pueda hablar en vez de escribir

### Arquitectura en la Nube

```
Estudiante (navegador)
    |
    |--- https://d1jjhwm5s0qx67.cloudfront.net (CloudFront)
    |       |
    |       |--- /* (pagina web) -----> S3 bucket -----> HTML, CSS, JS
    |       |
    |       |--- /api/* (backend) -----> API Gateway -----> Lambda
    |                                                          |---> Bedrock KB (IA + documentos)
    |                                                          |---> Polly (texto a voz)
    |                                                          |---> Transcribe (voz a texto)
    |
    |--- Simli (WebRTC directo) -----> Avatar con lip-sync
```

**Idea clave**: Todo lo que ves (la pagina web) esta en S3. Todo lo que piensa (la IA, la voz) pasa en Lambda. El avatar es una conexion directa entre el navegador y los servidores de Simli — Lambda nunca interviene ahi.

---

## 2. Como Funciona Todo (El Flujo Completo)

### Cuando el estudiante ESCRIBE una pregunta:

```
1. El estudiante escribe "Como solicito una beca?" y presiona Enter

2. El frontend (React) envia un POST a /api/chat-with-audio con el mensaje

3. CloudFront recibe el request, ve que empieza con /api/ y lo reenvia a API Gateway → Lambda

4. Lambda ejecuta FastAPI (via Mangum):
   a. El chatbot llama a Bedrock Knowledge Base
   b. Bedrock busca en los documentos de VOAE (busqueda semantica, top 5 resultados)
   c. Bedrock le pasa los documentos + la pregunta a Claude (el modelo de IA)
   d. Claude genera una respuesta basada en los documentos

5. La respuesta se divide en oraciones:
   - "Para solicitar una beca, debes ir a la VOAE."
   - "Necesitas llevar tu certificacion de notas y una carta de solicitud."
   - "El periodo de solicitud es en enero y junio."

6. Cada oracion se envia a Amazon Polly:
   - Polly convierte el texto a audio PCM (16kHz, mono, 16-bit)
   - El audio se codifica en base64

7. Lambda devuelve al frontend:
   {
     "answer": "Para solicitar una beca... (texto completo)",
     "sentences": [
       {"text": "Para solicitar una beca...", "audio_base64": "AQID..."},
       {"text": "Necesitas llevar tu...",     "audio_base64": "BAUG..."},
       {"text": "El periodo de solicitud...", "audio_base64": "CAIH..."}
     ]
   }

8. El frontend:
   a. Muestra el texto completo en la burbuja del chat
   b. Envia cada audio al avatar de Simli, oracion por oracion
   c. Simli mueve los labios del avatar sincronizado con el audio
```

### Cuando el estudiante HABLA:

```
1. El estudiante presiona el boton del microfono

2. El frontend:
   a. Detiene al avatar si estaba hablando
   b. Silencia el audio de Simli (para que no se capture su voz)
   c. Espera 150ms para que el silenciamiento surta efecto
   d. Comienza a grabar audio via AudioContext (PCM a 16kHz)

3. El navegador detecta cuando el estudiante deja de hablar
   (usa Web Speech API para deteccion de silencio)

4. El audio grabado se convierte a formato WAV y se envia al backend:
   POST /api/transcribe (archivo WAV)

5. Lambda recibe el WAV y lo procesa con Amazon Transcribe:
   a. Extrae los bytes PCM del archivo WAV
   b. Los envia en chunks de 8KB a Transcribe Streaming
   c. Transcribe devuelve el texto reconocido
   d. Se aplica un filtro de alucinaciones (textos falsos como "gracias.", "ok.", etc.)

6. El texto transcrito vuelve al frontend

7. El frontend lo usa como si el estudiante lo hubiera escrito
   → Sigue el mismo flujo de "cuando escribe"
```

---

## 3. Servicios AWS Utilizados

### Amazon Bedrock Knowledge Bases (la IA)

**Que hace**: Es el cerebro del chatbot. Combina dos cosas:
- **Busqueda de documentos**: Cuando el estudiante pregunta algo, Bedrock busca en los documentos de VOAE los mas relevantes (como un buscador inteligente)
- **Generacion de respuesta**: Le pasa los documentos encontrados a Claude (el modelo de IA) junto con la pregunta, y Claude genera una respuesta natural

**Por que es importante**: Sin esto, el chatbot inventaria respuestas. Con la Knowledge Base, solo responde con informacion real de los documentos de VOAE.

**Configuracion clave**:
- Modelo: Claude 3.5 Haiku (rapido y economico)
- Top K: 5 documentos por consulta
- Historial: Bedrock mantiene la conversacion con un `sessionId`

### Amazon Polly (texto a voz)

**Que hace**: Convierte el texto de la respuesta en audio hablado.

**Por que PCM y no MP3**: El avatar de Simli necesita audio en formato PCM crudo (sin comprimir) a exactamente 16kHz para sincronizar los labios. MP3 no sirve porque tiene compresion que desincroniza el lip-sync.

**Configuracion clave**:
- Voz: Lupe (voz femenina en espanol)
- Motor: Neural (calidad alta, suena natural)
- Formato: PCM 16-bit, 16kHz, mono
- Region: `us-east-1` (la voz neural de Lupe no esta disponible en todas las regiones)

### Amazon Transcribe Streaming (voz a texto)

**Que hace**: Convierte lo que dice el estudiante (audio) en texto.

**Caracteristicas**:
- Streaming: Envia el audio en pedazos de 8KB mientras transcribe (baja latencia)
- Vocabulario personalizado: Tiene 44 terminos de VOAE (VOAE, UNAH, Cum Laude, PROSENE, etc.) para que los reconozca correctamente
- Filtro de alucinaciones: Si Transcribe devuelve textos falsos como "gracias.", "suscribete al canal" o texto muy corto, los descarta

### AWS Lambda (el servidor)

**Que hace**: Ejecuta el codigo del backend (FastAPI) sin necesidad de mantener un servidor.

**Como funciona con FastAPI**: Lambda no sabe hablar FastAPI directamente. Para eso usamos **Mangum**, un adaptador que traduce:
```
Evento de Lambda → Mangum → FastAPI → procesa → FastAPI → Mangum → Respuesta de Lambda
```

**Configuracion**:
- Runtime: Python 3.10
- Memoria: 512 MB
- Timeout: 30 segundos
- Handler: `api.main.handler`

### API Gateway (la puerta de entrada)

**Que hace**: Es la URL publica que recibe los requests del frontend y los envia a Lambda.

**Tipo**: HTTP API (mas barato y rapido que REST API)

**Ruta**: `/{proxy+}` — esto significa que CUALQUIER ruta que llegue (ej: `/chat`, `/transcribe`, `/stats`) se reenvia a Lambda. FastAPI decide que hacer con cada una.

### Amazon S3 (la pagina web)

**Que hace**: Almacena los archivos estaticos del frontend (HTML, CSS, JS, imagenes).

**Configuracion**:
- Hosting de sitio web estatico habilitado
- Index document: `index.html`
- Error document: `index.html` (para que React Router funcione)
- Bucket policy: publico para lectura (`s3:GetObject`)

### CloudFront (HTTPS, CDN y enrutamiento)

**Que hace**: Se pone delante de S3 y API Gateway para:
- Dar **HTTPS** (necesario para el microfono del navegador — `getUserMedia` requiere contexto seguro)
- **Cachear** archivos estaticos cerca del usuario (CDN global)
- **Redirigir** HTTP a HTTPS automaticamente
- **Unificar** frontend y backend bajo un solo dominio (evita problemas de CORS cross-domain)

**Como enruta**:
```
https://d1jjhwm5s0qx67.cloudfront.net/
    ├── /api/*  → API Gateway → Lambda (backend)
    └── /* (todo lo demas)  → S3 (frontend)
```

CloudFront usa **behaviors** para decidir a donde enviar cada request:
- Si la ruta empieza con `/api/`, lo envia al origen de API Gateway
- Si es cualquier otra ruta, lo envia al origen de S3 (el frontend)

**Error pages configuradas**: 403 y 404 redirigen a `/index.html` con response 200. Esto es necesario para que React Router funcione — si el usuario entra a una ruta directa (ej: `/about`), S3 no tiene ese archivo y devuelve 404, pero CloudFront lo redirige al `index.html` y React toma el control.

**Configuracion**:
- Distribucion: `d1jjhwm5s0qx67.cloudfront.net`
- Origen 1: `voae-chatbot-frontend.s3-website.us-east-2.amazonaws.com` (website endpoint, HTTP only)
- Origen 2: `v00a3eciv1.execute-api.us-east-2.amazonaws.com` (API Gateway, HTTPS only)
- Behavior default: S3 (frontend)
- Behavior `/api/*`: API Gateway, cache deshabilitado, todos los metodos HTTP permitidos

---

## 4. El Backend (FastAPI en Lambda)

### Archivo principal: `api/main.py`

Este archivo contiene toda la API. Es una aplicacion FastAPI normal que tambien funciona en Lambda gracias a Mangum.

### Prefijo `/api` (APIRouter):

Todos los endpoints estan registrados en un `APIRouter(prefix="/api")` en vez de directamente en `app`. Esto hace que todas las rutas tengan el prefijo `/api/` automaticamente (ej: `/api/chat-with-audio`, `/api/transcribe`). Se hizo asi para que CloudFront pueda distinguir requests del frontend vs backend usando un solo behavior: todo lo que empieza con `/api/*` va al API Gateway, todo lo demas va a S3.

### Flujo de un request:

```
Navegador → CloudFront (/api/*) → API Gateway → Lambda → Mangum → FastAPI (APIRouter /api) → Endpoint → Respuesta
```

### Componentes internos:

```
api/main.py (FastAPI, endpoints, CORS)
    ↓ usa
src/chatbot/chatbot.py (RAGChatbot — orquesta todo)
    ↓ usa
src/llm/bedrock_client.py (BedrockClient — habla con Bedrock KB)
src/llm/polly_client.py (PollyClient — texto a voz)
src/llm/transcription_client.py (TranscriptionClient — voz a texto)
src/config.py (configuracion centralizada)
```

### Procesamiento de texto para Polly:

Antes de enviar texto a Polly, se preprocesa:

1. **Se quita el markdown**: `**negritas**` → `negritas`, `# Titulo` → `Titulo`
2. **Se convierten acronimos a minusculas**: `VOAE` → `voae`
   - Razon: Si Polly ve "VOAE" en mayusculas, lo deletrea letra por letra ("ve-o-a-e"). En minusculas lo pronuncia como palabra.

### Division en oraciones:

La respuesta se divide por signos de puntuacion (`.`, `!`, `?`) para sintetizar audio por partes. Esto permite que el avatar empiece a hablar la primera oracion mientras Polly sintetiza las siguientes.

---

## 5. El Frontend (React en S3)

### Componentes principales:

**App.jsx** — El componente principal:
- Maneja el estado de los mensajes
- Controla el flujo de envio/recepcion
- Conecta el microfono con la transcripcion
- Conecta las respuestas con el avatar

**SimliAvatar.jsx** — El avatar:
- Usa `forwardRef` + `useImperativeHandle` para exponer metodos: `speak()`, `stop()`, `mute()`, `unmute()`
- Maneja la conexion WebRTC con Simli
- Tiene fix para React StrictMode (double-mount)
- Tiene timeout de 8 segundos para reconexion

**Microphone.jsx** — El microfono:
- Captura audio PCM via `AudioContext` + `ScriptProcessor`
- Downsamplea de 48kHz (nativo del navegador) a 16kHz (requerido por Transcribe)
- Codifica a WAV (header RIFF + datos PCM int16)
- Usa Web Speech API para detectar fin de habla
- Requiere HTTPS para funcionar (`navigator.mediaDevices.getUserMedia`)

### Flujo del frontend:

```
[Escribir mensaje]        [Hablar por microfono]
       ↓                          ↓
sendMessageWithText()     Microphone → WAV → POST /api/transcribe
       ↓                          ↓
POST /api/chat-with-audio texto transcrito → sendMessageWithText()
       ↓
Recibe {answer, sentences[]}
       ↓
Muestra texto en burbuja
       ↓
Para cada oracion:
  avatarRef.current.speak(audio_base64)
       ↓
Simli reproduce audio + lip-sync
```

---

## 6. El Avatar (Simli)

### Que es Simli:

Simli es un servicio externo que proporciona un avatar virtual con lip-sync en tiempo real. Funciona via WebRTC — una conexion directa entre el navegador del estudiante y los servidores de Simli. **Lambda nunca toca el video ni el audio de Simli**.

### Como funciona:

1. Al cargar la pagina, `SimliAvatar.jsx` crea un `SimliClient` con API key y face ID
2. El cliente establece una conexion WebRTC con Simli
3. Cuando llega audio PCM (de Polly, via el backend), se envia con `sendAudioData(bytes)`
4. Simli analiza el audio, genera movimiento de labios, y devuelve video + audio via WebRTC
5. El componente `<video>` y `<audio>` reproducen el stream

### Fix critico — StrictMode double-mount:

React StrictMode monta y desmonta los componentes dos veces (para detectar side effects). Esto creaba DOS clientes Simli, pero solo el primero conectaba. La solucion:

- Se usa `isReadyRef` (una ref, no estado) que solo se pone en `true` cuando el evento `'connected'` dispara en el cliente que ES `clientRef.current`
- Un timeout de 8 segundos reintenta la conexion si no conecta

### Fix critico — Aislamiento del microfono:

Cuando el avatar habla y el usuario graba audio, la voz del avatar se filtraba al microfono (incluso con echo cancellation). La solucion:

- `mute()` hace `audioRef.srcObject = null` (no solo `muted = true`)
- `muted = true` solo baja el volumen, pero el stream WebRTC sigue activo en el pipeline de audio del sistema operativo
- `srcObject = null` desconecta completamente el stream
- `unmute()` restaura el `srcObject` guardado y llama `.play()`

---

## 7. La Transcripcion de Voz (Amazon Transcribe)

### Flujo completo:

```
Microfono del navegador
    ↓
AudioContext + ScriptProcessor (captura Float32 PCM)
    ↓
Downsample 48kHz → 16kHz
    ↓
Encode WAV (RIFF header + Int16 PCM)
    ↓
POST /api/transcribe (FormData: recording.wav)
    ↓
Backend: TranscriptionClient
    ↓
Verifica header RIFF (es un WAV valido?)
    ↓
Extrae PCM raw (sin header WAV)
    ↓
Verifica nivel de audio (no es silencio?)
    ↓
Envia a Transcribe Streaming en chunks de 8KB
    ↓
Recibe eventos de transcripcion:
    - Resultados parciales (se ignoran)
    - Resultados finales (se acumulan)
    ↓
Filtro de alucinaciones:
    - Texto < 4 caracteres → descartado
    - Texto comun falso ("gracias.", "ok.") → descartado
    - Solo signos de puntuacion → descartado
    - Palabra repetida 3+ veces → descartado
    ↓
Texto final o None
```

### Vocabulario personalizado:

El archivo `voae-vocabulary.csv` contiene 44 terminos con:
- **Phrase**: Como se escribe (con guiones para frases: `Summa-Cum-Laude`)
- **SoundsLike**: Pronunciacion fonetica en espanol (`suma-kum-laude`)
- **DisplayAs**: Como aparece en el texto final (`Summa Cum Laude`)

El vocabulario se crea UNA VEZ en la consola de Amazon Transcribe. El codigo lo detecta automaticamente si existe.

---

## 8. La Sintesis de Voz (Amazon Polly)

### Flujo:

```
Texto de la respuesta
    ↓
split_sentences() → ["oracion 1", "oracion 2", ...]
    ↓
Para cada oracion:
    preprocess_text_for_tts():
        - Quita **markdown** y *cursivas*
        - Quita # titulos y - listas
        - VOAE → voae, UNAH → unah (evita deletreo)
    ↓
    Polly.synthesize_speech():
        Text: "oracion preprocesada"
        OutputFormat: pcm
        SampleRate: 16000
        VoiceId: Lupe
        Engine: neural
    ↓
    audio_bytes → base64 string
```

### Por que Polly puede estar en otra region:

El motor `neural` no esta disponible en todas las regiones. Por ejemplo, en `us-east-2` solo hay motor `standard` para espanol. La voz Lupe neural esta en `us-east-1`. Por eso existe la variable `POLLY_REGION` separada de `BEDROCK_REGION`.

---

## 9. La Inteligencia Artificial (Amazon Bedrock)

### Knowledge Base:

Una Knowledge Base de Bedrock es una base de datos de documentos inteligente:

1. **Subes documentos** a S3 (archivos .md, .txt, .pdf, etc.)
2. Bedrock los **procesa automaticamente**: los divide en fragmentos, genera embeddings (representaciones numericas del significado), y los almacena en un vector store
3. Cuando alguien pregunta algo, Bedrock **busca los fragmentos mas relevantes** por similaridad semantica
4. Bedrock **inyecta** esos fragmentos en el prompt de Claude junto con la pregunta
5. Claude **genera una respuesta** basada en los documentos

### API `retrieve_and_generate`:

Esta es la API que usamos. Hace TODO en una sola llamada:
- Busca documentos relevantes (retrieve)
- Genera respuesta con el modelo (generate)
- Mantiene historial de conversacion (via sessionId)

```python
response = client.retrieve_and_generate(
    input={'text': 'Como solicito una beca?'},
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': 'ATRGGUJIS9',
            'modelArn': 'arn:aws:bedrock:...',
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {'numberOfResults': 5}
            },
            'generationConfiguration': {
                'promptTemplate': {'textPromptTemplate': PROMPT_TEMPLATE},
                'inferenceConfig': {
                    'textInferenceConfig': {
                        'temperature': 0.7,
                        'maxTokens': 2000
                    }
                }
            }
        }
    },
    sessionId='session-123'  # Bedrock mantiene el historial
)
```

### Prompt Template:

El prompt le dice a Claude como comportarse:

```
Eres el Asistente Virtual de VOAE...
- Usa "tu" para crear cercania
- Se breve y directo
- NUNCA menciones "segun el contexto"
- Si no sabes, di que no tienes esa informacion

Usa los siguientes resultados de busqueda:
$search_results$     ← Bedrock inyecta los documentos aqui

Pregunta del estudiante: $query$     ← La pregunta va aqui
```

### Inference Profiles:

Los modelos con prefijo `us.` (como `us.anthropic.claude-3-5-haiku-20241022-v1:0`) son "inference profiles" — perfiles de inferencia que distribuyen las requests entre multiples regiones. Necesitan un ARN especial que incluye el account ID de AWS. El codigo resuelve esto automaticamente llamando a `list_inference_profiles()`.

---

## 10. Estructura de Archivos

```
LLAMA_BGE_CHATBOT/
│
├── api/
│   └── main.py                    ← FastAPI: todos los endpoints + Mangum handler
│
├── src/
│   ├── config.py                  ← Configuracion centralizada (lee variables de entorno)
│   ├── chatbot/
│   │   └── chatbot.py             ← RAGChatbot: orquesta Bedrock + historial
│   └── llm/
│       ├── bedrock_client.py      ← Cliente para Bedrock Knowledge Bases
│       ├── polly_client.py        ← Cliente para Amazon Polly (TTS)
│       └── transcription_client.py ← Cliente para Amazon Transcribe (STT)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                ← Componente principal (chat, mensajes, estado)
│   │   ├── App.css                ← Estilos (layout, chat, avatar)
│   │   ├── main.jsx               ← Punto de entrada React
│   │   ├── components/
│   │   │   ├── SimliAvatar.jsx    ← Avatar Simli (WebRTC, lip-sync)
│   │   │   └── Microphone.jsx     ← Captura de audio (PCM, WAV)
│   │   └── services/
│   │       ├── speechToText.mjs   ← POST /api/transcribe
│   │       └── textToSpeech.mjs   ← POST /api/synthesize
│   ├── dist/                      ← Build de produccion (se sube a S3)
│   └── package.json               ← Dependencias del frontend
│
├── .env                           ← Credenciales y configuracion (NO se sube a git)
├── .env.example                   ← Plantilla de variables de entorno
├── requirements.txt               ← Dependencias Python
├── build_lambda.sh                ← Script para crear lambda_function.zip
├── voae-vocabulary.csv            ← Vocabulario para Amazon Transcribe
└── lambda_function.zip            ← Paquete de deployment (generado)
```

---

## 11. Variables de Entorno

### En Lambda (configuradas en la consola de AWS):

| Variable | Valor | Descripcion |
|----------|-------|-------------|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-3-5-haiku-20241022-v1:0` | Modelo de IA a usar |
| `BEDROCK_KNOWLEDGE_BASE_ID` | `ATRGGUJIS9` | ID de la Knowledge Base |
| `BEDROCK_REGION` | `us-east-2` | Region de Bedrock y Transcribe |
| `POLLY_REGION` | `us-east-1` | Region de Polly (puede diferir) |
| `POLLY_VOICE` | `Lupe` | Voz de Polly |
| `POLLY_ENGINE` | `neural` | Motor de Polly |
| `POLLY_LANGUAGE` | `es-US` | Idioma de Polly |
| `API_CORS_ORIGINS` | `https://tu-dominio.cloudfront.net` | Origenes CORS permitidos |

**Nota**: NO se necesitan `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en Lambda. Las credenciales vienen del IAM role automaticamente.

### En desarrollo local (archivo `.env`):

```bash
# Credenciales (solo para desarrollo local)
APP_AWS_ACCESS_KEY_ID=AKIA...
APP_AWS_SECRET_ACCESS_KEY=t6xT...

# Bedrock
BEDROCK_REGION=us-east-2
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_KNOWLEDGE_BASE_ID=ATRGGUJIS9

# Polly
POLLY_REGION=us-east-1
POLLY_VOICE=Lupe
POLLY_ENGINE=neural
POLLY_LANGUAGE=es-US
```

### En el frontend (archivo `frontend/.env`):

```bash
VITE_API_URL=https://d1jjhwm5s0qx67.cloudfront.net/api
VITE_SIMLI_API_KEY=tu_api_key_de_simli
VITE_SIMLI_FACE_ID=tu_face_id_de_simli
```

**Nota**: `VITE_API_URL` apunta a CloudFront con el sufijo `/api`. El frontend hace requests a `${VITE_API_URL}/chat-with-audio`, que se traduce a `https://d1jjhwm5s0qx67.cloudfront.net/api/chat-with-audio`. CloudFront ve que la ruta empieza con `/api/` y la envia al API Gateway.

### Por que `APP_AWS_ACCESS_KEY_ID` en vez de `AWS_ACCESS_KEY_ID`?

Lambda define `AWS_ACCESS_KEY_ID` internamente para el IAM role. Si el codigo tambien la lee y la pasa a boto3 explicitamente, entra en conflicto con el `AWS_SESSION_TOKEN` que Lambda usa. Resultado: "security token invalid".

Solucion: en desarrollo local usamos `APP_AWS_ACCESS_KEY_ID` (nombre custom). En Lambda, esa variable no existe, asi que boto3 usa las credenciales del IAM role automaticamente.

---

## 12. Como Se Empaqueta Lambda

### El script `build_lambda.sh`:

```bash
#!/bin/bash
# 1. Limpia builds anteriores
rm -rf lambda_package lambda_function.zip

# 2. Instala dependencias en una carpeta
pip install fastapi mangum pydantic python-multipart python-dotenv amazon-transcribe \
    -t lambda_package

# 3. Copia el codigo fuente
cp -r src/ lambda_package/src/
cp -r api/ lambda_package/api/

# 4. Limpia archivos innecesarios (reduce tamano)
# - __pycache__/, *.dist-info/, tests/, *.pyc
# - boto3, botocore (ya vienen en Lambda runtime)

# 5. Crea el ZIP
cd lambda_package && zip -r ../lambda_function.zip .
```

### Resultado: `lambda_function.zip` (~12MB)

Este ZIP se sube a Lambda. Contiene:
- Todo el codigo (`api/`, `src/`)
- Todas las dependencias Python (excepto boto3 que Lambda ya tiene)

### Por que se elimina boto3 del ZIP:

Lambda ya incluye boto3 en su runtime. Si lo incluimos, el ZIP pesa mas sin razon. Ademas, la version de Lambda puede ser mas reciente.

### El handler:

```python
# api/main.py (al final del archivo)
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

Lambda busca `api.main.handler` — que es la funcion `handler` dentro de `api/main.py`. Mangum recibe el evento de Lambda, lo convierte a un request ASGI, se lo pasa a FastAPI, y devuelve la respuesta en formato Lambda.

---

## 13. Endpoints de la API

Todas las rutas tienen el prefijo `/api` (ej: `/api/chat-with-audio`). Esto permite que CloudFront distinga requests del frontend vs del backend usando un solo behavior `/api/*`.

| Endpoint | Metodo | Que hace | Quien lo usa |
|----------|--------|----------|--------------|
| `/api/chat-with-audio` | POST | Genera respuesta + audio por oracion | Frontend (endpoint principal) |
| `/api/chat` | POST | Solo texto, sin audio | Testing / clientes ligeros |
| `/api/transcribe` | POST | Convierte audio WAV a texto | Frontend (microfono) |
| `/api/synthesize` | POST | Convierte texto a audio PCM | Frontend (TTS standalone) |
| `/api/stats` | GET | Modelo, historial, proveedor | Frontend (panel de stats) |
| `/api/history` | GET | Historial de conversacion | Frontend |
| `/api/clear-history` | POST | Borra historial de una sesion | Frontend (boton basura) |
| `/api/session/{id}` | DELETE | Elimina una sesion | Limpieza |
| `/api/sessions` | GET | Lista sesiones activas | Admin |
| `/api/health` | GET | Verificar que Lambda funciona | Monitoreo |
| `/api/` | GET | Info basica de la API | Verificacion rapida |

### Payload del endpoint principal `/api/chat-with-audio`:

**Request**:
```json
{
  "message": "Como solicito una beca?",
  "session_id": "session-1234567890",
  "temperature": 0.7
}
```

**Response**:
```json
{
  "answer": "Para solicitar una beca, debes ir a la VOAE. Necesitas tu certificacion de notas.",
  "sentences": [
    {
      "text": "Para solicitar una beca, debes ir a la VOAE.",
      "audio_base64": "AQIDBA..."
    },
    {
      "text": "Necesitas tu certificacion de notas.",
      "audio_base64": "BQYHCA..."
    }
  ],
  "session_id": "session-1234567890",
  "timestamp": "2026-03-08T05:30:51.556791"
}
```

---

## 14. Manejo de Sesiones

### Dos niveles de sesion:

1. **Sesion del frontend**: El `session_id` que genera React (`session-{timestamp}`). Identifica al usuario.

2. **Sesion de Bedrock**: Un `sessionId` interno que Bedrock genera y mantiene. Bedrock usa esto para recordar la conversacion (no necesitamos enviarle el historial manualmente).

### Flujo:

```
Primera pregunta:
  Frontend envia session_id="session-123"
  → RAGChatbot se crea (sin _bedrock_session_id)
  → Bedrock genera respuesta + nuevo sessionId="abc-xyz"
  → RAGChatbot guarda _bedrock_session_id="abc-xyz"

Segunda pregunta:
  Frontend envia session_id="session-123"
  → RAGChatbot ya existe
  → Bedrock recibe sessionId="abc-xyz" → recuerda la conversacion anterior
  → Genera respuesta contextual
```

### Limitacion en Lambda:

Las sesiones estan en memoria (`chat_sessions = {}`). Si Lambda crea un nuevo contenedor (cold start o escalamiento), se pierde el estado local. Sin embargo, **Bedrock mantiene su propio historial server-side**, asi que las respuestas siguen siendo contextuales. Lo unico que se pierde es el historial visual en `/history`.

Para produccion, se podria usar DynamoDB para persistir las sesiones, pero para el uso actual no es necesario.

---

## 15. Seguridad y Credenciales

### En Lambda (produccion):

- **Sin credenciales hardcodeadas**: Lambda usa un IAM role (`voae-chatbot-lambda-role`)
- **Permisos del role**:
  - `AmazonBedrockFullAccess` — acceso a Bedrock y Knowledge Bases
  - `AmazonPollyFullAccess` — sintesis de voz
  - `AmazonTranscribeFullAccess` — transcripcion de audio
  - `AWSLambda_FullAccess` — ejecucion de Lambda
- boto3 toma las credenciales automaticamente del role (via `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` que Lambda inyecta)

### En desarrollo local:

- Credenciales explicitas en `.env` como `APP_AWS_ACCESS_KEY_ID`
- El `.env` esta en `.gitignore` — nunca se sube a git
- El codigo solo pasa credenciales a boto3 cuando `APP_AWS_ACCESS_KEY_ID` existe

### CORS:

- En Lambda: `API_CORS_ORIGINS` limita que dominios pueden llamar a la API
- En desarrollo: permite `localhost:3000` y `localhost:5173`
- En produccion: solo el dominio de CloudFront

---

## 16. Paso a Paso: Desplegar Desde Cero

### Prerequisitos:

- Cuenta de AWS con acceso a Bedrock, Polly, Transcribe, Lambda, API Gateway, S3
- Knowledge Base creada en Bedrock con documentos de VOAE
- Node.js y Python 3.10+ instalados localmente
- Credenciales de Simli (API key y face ID)

### Paso 1: IAM Role

1. IAM → Roles → Create role
2. Trusted entity: AWS service → Lambda
3. Adjuntar policies: `AmazonBedrockFullAccess`, `AmazonPollyFullAccess`, `AmazonTranscribeFullAccess`
4. Nombre: `voae-chatbot-lambda-role`

### Paso 2: Lambda

1. Lambda → Create function → Author from scratch
2. Nombre: `voae-chatbot`
3. Runtime: Python 3.10
4. Role: `voae-chatbot-lambda-role`
5. Crear → Upload .zip → subir `lambda_function.zip`
6. Configuration → General → Timeout: 30s, Memory: 512MB
7. Configuration → Environment variables (ver seccion 11)
8. Runtime settings → Handler: `api.main.handler`

### Paso 3: API Gateway

1. API Gateway → Create API → HTTP API
2. Add integration: Lambda → `voae-chatbot`
3. Nombre: `voae-chatbot-api`
4. Ruta: ANY `/{proxy+}` → `voae-chatbot`
5. Stage: `$default` con auto-deploy
6. Copiar Invoke URL

### Paso 4: Build del Frontend

```bash
cd frontend
# Configurar frontend/.env con:
#   VITE_API_URL=https://TU-DOMINIO-CLOUDFRONT.cloudfront.net/api
#   VITE_SIMLI_API_KEY=tu_api_key
#   VITE_SIMLI_FACE_ID=tu_face_id
npm run build
```

### Paso 5: S3

1. S3 → Create bucket → nombre unico
2. Desmarcar "Block all public access"
3. Properties → Static website hosting → Enable
   - Index document: `index.html`
   - Error document: `index.html`
4. Permissions → Bucket policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::NOMBRE-BUCKET/*"
    }]
}
```
5. Subir archivos de `frontend/dist/`:
   - `index.html`, `voae-logo.png`, `pcm-processor.js` → raiz
   - `assets/index-*.css`, `assets/index-*.js` → carpeta `assets/`

### Paso 6: CloudFront (HTTPS)

CloudFront unifica frontend y backend bajo un solo dominio HTTPS, lo cual:
- Habilita el microfono (requiere HTTPS)
- Evita problemas de CORS cross-domain
- Cachea archivos estaticos globalmente

#### 6a. Crear distribucion

1. CloudFront → Create distribution
2. **Distribution name**: `voae-chatbot`
3. **Distribution type**: Single website or app
4. **Domain (Route 53)**: dejarlo vacio (no tenemos dominio propio)

#### 6b. Origen del frontend (S3)

1. **Origin domain**: escribir manualmente el website endpoint de S3:
   ```
   voae-chatbot-frontend.s3-website.us-east-2.amazonaws.com
   ```
   **Importante**: NO seleccionar el bucket del dropdown. Si aparece un aviso "Use website endpoint", darle clic.
2. **Protocol**: HTTP only (los endpoints de S3 website solo soportan HTTP)
3. Lo demas por defecto

#### 6c. Seguridad (WAF)

1. Seleccionar **"Do not enable security protections"** (para ahorrar costos)

#### 6d. Crear la distribucion

1. Dar clic en **Create Distribution**
2. Anotar el **Distribution domain name** (ej: `d1jjhwm5s0qx67.cloudfront.net`)
3. Esperar ~3-5 minutos a que el status cambie de "Deploying" a "Enabled"

#### 6e. Configurar error pages (SPA routing)

En la distribucion → pestaña **Error pages** → crear dos custom error responses:

| HTTP error code | Customize response | Response page path | HTTP response code |
|-----------------|-------------------|-------------------|-------------------|
| 403 | Yes | `/index.html` | 200 |
| 404 | Yes | `/index.html` | 200 |

Esto es necesario para que React Router funcione — cuando el usuario refresca la pagina o entra a una ruta directa, S3 no tiene ese archivo y devuelve 403/404. CloudFront lo redirige a `index.html` y React toma el control del enrutamiento.

#### 6f. Agregar origen del API Gateway

En la distribucion → pestaña **Origins** → **Create origin**:

1. **Origin domain**: `v00a3eciv1.execute-api.us-east-2.amazonaws.com`
2. **Protocol**: HTTPS only
3. Lo demas por defecto

#### 6g. Crear behavior para el API

En la distribucion → pestaña **Behaviors** → **Create behavior**:

| Campo | Valor |
|-------|-------|
| **Path pattern** | `/api/*` |
| **Origin** | `v00a3eciv1.execute-api.us-east-2.amazonaws.com` |
| **Viewer protocol policy** | Redirect HTTP to HTTPS |
| **Allowed HTTP methods** | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| **Cache policy** | CachingDisabled |
| **Origin request policy** | AllViewerExceptHostHeader |

**Por que `CachingDisabled`**: Las respuestas del API son dinamicas (cada pregunta genera una respuesta diferente). No queremos que CloudFront cachee respuestas viejas.

**Por que `AllViewerExceptHostHeader`**: Reenviar todos los headers del navegador al API Gateway EXCEPTO `Host` (porque API Gateway necesita recibir su propio hostname, no el de CloudFront).

#### 6h. Actualizar CORS en Lambda

Ir a Lambda → `voae-chatbot` → Configuration → Environment variables:
- Cambiar `API_CORS_ORIGINS` a: `https://d1jjhwm5s0qx67.cloudfront.net`

#### 6i. Actualizar el frontend

El frontend necesita apuntar a CloudFront en vez de directamente al API Gateway:

1. En `frontend/.env`, cambiar:
   ```
   VITE_API_URL=https://d1jjhwm5s0qx67.cloudfront.net/api
   ```
2. Reconstruir: `cd frontend && npm run build`
3. Subir el contenido de `frontend/dist/` al bucket S3 (reemplazar archivos existentes)

#### 6j. Actualizar Lambda con prefijo /api

El backend necesita que todas sus rutas tengan el prefijo `/api` para que CloudFront las identifique:

- En `api/main.py`, los endpoints estan en un `APIRouter(prefix="/api")` en vez de directamente en `app`
- Reconstruir el zip: `bash build_lambda.sh`
- Subir el nuevo `lambda_function.zip` a Lambda

#### 6k. Invalidar cache de CloudFront

Despues de subir archivos nuevos a S3:

1. CloudFront → tu distribucion → pestaña **Invalidations**
2. **Create invalidation** → Path: `/*`
3. Esto fuerza a CloudFront a servir los archivos actualizados en vez de versiones cacheadas

#### 6l. Verificar

Abrir `https://d1jjhwm5s0qx67.cloudfront.net` en el navegador:
- La pagina del chatbot debe cargar
- El candado HTTPS debe aparecer en la barra de direcciones
- El microfono debe estar habilitado (icono de microfono activo)
- El chat debe funcionar (texto y voz)

---

## 17. Problemas Conocidos y Soluciones

### "getUserMedia is not a function"
**Causa**: El microfono requiere HTTPS. S3 hosting es HTTP.
**Solucion**: Usar CloudFront (HTTPS) o ignorar — el chat por texto funciona sin microfono.

### "security token invalid" en Lambda
**Causa**: El codigo lee `AWS_ACCESS_KEY_ID` del entorno (que Lambda define internamente) y la pasa explicitamente a boto3, conflictuando con el session token.
**Solucion**: Usar `APP_AWS_ACCESS_KEY_ID` como nombre custom. En Lambda esa variable no existe → boto3 usa el IAM role.

### "The selected engine is not supported in this region"
**Causa**: Motor `neural` de Polly no disponible en la region de Lambda.
**Solucion**: Configurar `POLLY_REGION` apuntando a una region con soporte neural (ej: `us-east-1`).

### "Knowledge Base with id X does not exist"
**Causa**: La Knowledge Base esta en una region diferente a la configurada.
**Solucion**: Verificar que `BEDROCK_REGION` coincida con la region donde se creo la KB.

### Simli no conecta (StrictMode)
**Causa**: React StrictMode crea dos clientes Simli; solo el primero conecta pero ya no es el "current".
**Solucion**: `isReadyRef` solo se pone `true` cuando `clientRef.current === client` en el evento `'connected'`. Timeout de 8s para reconexion.

### Transcribe devuelve texto vacio
**Causa**: Audio silencioso, microfono desactivado, o audio demasiado corto.
**Solucion**: Verificar que el microfono este activo. El filtro de alucinaciones descarta texto < 4 caracteres.

### Inference profile ARN invalido
**Causa**: Modelos con prefijo `us.` necesitan un ARN que incluye el account ID.
**Solucion**: El codigo llama a `list_inference_profiles()` para resolver el ARN correcto automaticamente.

---

## 18. Desarrollo Local

### Levantar el backend:

```bash
cd /ruta/al/proyecto
source venv/bin/activate
pip install -r requirements.txt
cd api && python main.py
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

### Levantar el frontend:

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Variables necesarias:

Backend: archivo `.env` en la raiz del proyecto
Frontend: archivo `frontend/.env`

### Reconstruir el paquete Lambda:

```bash
bash build_lambda.sh
# → lambda_function.zip (12MB)
# Subir a Lambda via consola de AWS
```

### Reconstruir y resubir el frontend a S3:

```bash
cd frontend
# Asegurarse que frontend/.env tiene:
#   VITE_API_URL=https://d1jjhwm5s0qx67.cloudfront.net/api
npm run build
# Subir contenido de dist/ al bucket S3
# Luego invalidar cache en CloudFront: Invalidations → /*
```

### Para desarrollo local:

En `frontend/.env`, cambiar temporalmente:
```bash
VITE_API_URL=http://localhost:8000/api
```
El backend local ya sirve en `/api/*` gracias al `APIRouter(prefix="/api")`.
