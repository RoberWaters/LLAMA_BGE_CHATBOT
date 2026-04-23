# Análisis técnico: Lambda `voae-chatbot`

Fecha de análisis: 2026-04-16
Cuenta AWS: `824333136555` (usuario IAM `valerio`)
Región: `us-east-2` (Ohio)

---

## 1. Infraestructura

| Campo | Valor |
|---|---|
| ARN | `arn:aws:lambda:us-east-2:824333136555:function:voae-chatbot` |
| Runtime | Python 3.10 |
| Handler | `api.main.handler` (FastAPI + Mangum) |
| Memoria | 512 MB |
| Timeout | 40 s |
| Código (zip) | 11.84 MB |
| Arquitectura | x86_64 |
| Ephemeral storage | 512 MB |
| Última actualización | 2026-04-14 |
| Última invocación | 2026-04-16 |
| Package type | Zip |
| Log group | `/aws/lambda/voae-chatbot` |

### Variables de entorno

```
BEDROCK_KNOWLEDGE_BASE_ID = ATRGGUJIS9
BEDROCK_MODEL_ID          = us.anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_REGION            = us-east-2
POLLY_REGION              = us-east-1
POLLY_VOICE               = Lupe
POLLY_LANGUAGE            = es-US
POLLY_ENGINE              = neural
API_CORS_ORIGINS          = https://d1jjhwm5s0qx67.cloudfront.net,
                            https://d2oef8cfr2hc98.cloudfront.net
```

### Trigger

- **API Gateway REST:** `voae-chatbot-api` (id `v00a3eciv1`)
- **Stage:** `$default`
- **Ruta:** `ANY /{proxy+}` → integración `yb5i4em` → Lambda
- **URL base:** `https://v00a3eciv1.execute-api.us-east-2.amazonaws.com`
- Sin Function URL configurada
- Sin event source mappings
- Resource policy: solo `apigateway.amazonaws.com` puede invocar (condición `SourceArn` scoped al API ID)

---

## 2. Métricas CloudWatch (últimas 24h)

| Métrica | Valor |
|---|---|
| Invocaciones | 5 |
| Errores | 0 |
| Duración media | 3021 ms |
| Duración máxima | **8569 ms** ⚠ |

---

## 3. Arquitectura de la aplicación

```
API Gateway REST /{proxy+}
        │
        ▼
Lambda (Mangum → FastAPI)
        │
        ├── Router /api
        │     ├── GET  /              → root
        │     ├── GET  /health        → health check
        │     ├── POST /chat          → texto plano
        │     ├── POST /chat-with-audio → texto + audio PCM por oración
        │     ├── POST /transcribe    → Amazon Transcribe streaming
        │     ├── POST /synthesize    → Amazon Polly PCM
        │     ├── GET  /stats
        │     ├── GET  /history
        │     ├── POST /clear-history
        │     ├── GET  /sessions
        │     └── DELETE /session/{id}
        │
        └── RAGChatbot (por session_id en memoria)
              └── BedrockClient.retrieve_and_generate
                    └── Knowledge Base `ATRGGUJIS9`
                         + Claude 3.5 Haiku (us.anthropic.claude-3-5-haiku-20241022-v1:0)
                         + promptTemplate custom (persona VOAE)
                         + numberOfResults = 5
```

### Componentes principales

| Archivo | Responsabilidad |
|---|---|
| `api/main.py` | FastAPI app, endpoints, `Mangum` handler en línea 356 |
| `src/chatbot/chatbot.py` | `RAGChatbot` — wrapper que mantiene `_bedrock_session_id` para historial multi-turn server-side |
| `src/llm/bedrock_client.py` | `retrieve_and_generate` contra KB, resuelve ARN de inference profile (`us.`/`global.`/`eu.` prefix) |
| `src/llm/polly_client.py` | TTS Polly (Lupe, neural, es-US) — PCM para avatar Simli |
| `src/llm/transcription_client.py` | Amazon Transcribe Streaming (español) |
| `src/config.py` | `BedrockConfig`, `PollyConfig`, `APIConfig`, `ChatbotConfig` (vía `.env` o env vars de Lambda) |

### Prompt template (Bedrock KB)

Persona del asistente VOAE con reglas:
- Siempre responde en español
- Nunca usa markdown (el texto se lee por voz en avatar)
- Nunca dice "según el contexto" / "basándome en los resultados"
- Usa "tú", nunca "usted"
- 2-3 oraciones para preguntas simples
- Siempre "la VOAE", nunca "VOAE" solo
- Si no hay resultados: sugiere `voae@unah.edu.hn`

---

## 4. IAM Role `voae-chatbot-lambda-role`

**ARN:** `arn:aws:iam::824333136555:role/voae-chatbot-lambda-role`
**Creado:** 2026-03-08

### Políticas adjuntas (todas `*FullAccess`)

| Política | Scope |
|---|---|
| `AmazonBedrockFullAccess` | Bedrock KB + modelos |
| `AmazonTranscribeFullAccess` | Transcribe |
| `AmazonPollyFullAccess` | Polly |
| `AWSLambdaBasicExecutionRole` | CloudWatch Logs |
| `AWSLambdaBasicDurableExecutionRolePolicy` | Logs duraderos |
| `AWSLambda_FullAccess` ⚠ | **Excesiva** — permite invocar/crear/borrar cualquier Lambda |

Sin políticas inline.

---

## 5. Problemas detectados

### 🔴 Críticos

1. **Timeout Lambda (40 s) > Timeout API Gateway REST (29 s)**
   API Gateway REST corta la conexión a los 29 s. Las respuestas largas se cortarán aunque Lambda siga procesando. Alinear el timeout, o migrar a HTTP API v2 + response streaming.

2. **`AWSLambda_FullAccess` en el rol**
   Viola el principio de mínimo privilegio. Esta función no necesita gestionar otras Lambdas. Quitarla.

3. **Sin endpoint `/chat-stream` (SSE)**
   La rama local `feature/simli` depende de Server-Sent Events para reproducir audio por oración. El código desplegado solo tiene `/chat-with-audio`, que bloquea hasta generar todas las oraciones. API Gateway REST **no soporta streaming**; para SSE real se requiere HTTP API v2 + `RESPONSE_STREAM` invoke mode, o Function URL con streaming.

### 🟡 Importantes

4. **`chat_sessions` es un dict en memoria global** (`api/main.py:51`)
   - Los cold starts pierden sesiones
   - Cada contenedor Lambda tiene su propio dict: las sesiones "saltan" entre instancias
   - El `_bedrock_session_id` persiste en Bedrock, pero el `conversation_history` local no es confiable
   - Recomendación: mover a DynamoDB con `session_id` como PK

5. **Sin tags** en la función
   No hay `environment`, `owner`, `project`. Dificulta facturación, gobierno y auditoría.

6. **Memoria 512 MB podría ser baja**
   Cold start de FastAPI + boto3 (~12 MB de código + dependencias). Probar 1024 MB para reducir latencia inicial.

7. **`os.chdir(BASE_DIR)` en `api/main.py:15`**
   Innecesario en Lambda. `/var/task` es read-only en algunos contextos; puede causar fallos espurios.

### 🟢 Aspectos bien hechos

- **`promptTemplate` custom** en Bedrock KB (evita el prompt genérico de Anthropic)
- **Sesión Bedrock nativa** para historial (mejor que serializar historial en cada prompt)
- **Lazy init** de clientes Polly/Transcribe (aprovecha contenedor warm)
- **Credenciales AWS via IAM role** (no hardcodeadas)
- **Preprocesamiento de acrónimos** antes de Polly (evita que deletree "UNAH" letra por letra)
- **CORS restringido** a los 2 CloudFront específicos, no `*`
- **Resource policy** de Lambda con condición `SourceArn` al API Gateway exacto

---

## 6. URL pública

```
https://v00a3eciv1.execute-api.us-east-2.amazonaws.com/api/health
```

---

## 7. Resumen ejecutivo

Lambda funcional en producción con arquitectura Bedrock KB + Polly + Transcribe. Código limpio y bien estructurado, pero tres gaps críticos:

1. El **timeout del API Gateway REST (29 s)** limita respuestas largas — incompatible con SSE.
2. El **rol IAM tiene `AWSLambda_FullAccess`** — riesgo de escalada.
3. **Las sesiones en memoria** no sobreviven cold starts ni escalado horizontal.

Para desplegar la experiencia SSE de `feature/simli` hay que migrar a HTTP API v2 o Function URL con response streaming.
