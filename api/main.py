"""
FastAPI REST API para Chatbot VOAE
"""
import sys
import os
from pathlib import Path

# Agregar el directorio src al path
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

# Cambiar al directorio base para que las rutas relativas funcionen
os.chdir(BASE_DIR)


from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
import asyncio
import json
import re
import struct
from datetime import datetime

from chatbot.chatbot import RAGChatbot

from llm.transcription_client import TranscriptionClient
from llm.polly_client import PollyClient

# Inicializar FastAPI
app = FastAPI(
    title="Chatbot VOAE API",
    description="API REST para el Chatbot de la Vicerrectoría de Orientación y Asuntos Estudiantiles",
    version="1.0.0"
)

# Configurar CORS para permitir requests desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global del chatbot
chatbot_instance = None
chat_sessions = {}  # {session_id: chatbot_instance}
session_llm_providers = {}  # {session_id: llm_provider}


transcription_client = None

def get_transcription_client():
    """Obtiene o crea el cliente de transcripción"""
    global transcription_client
    if transcription_client is None:
        transcription_client = TranscriptionClient()
    return transcription_client


polly_client = None

def get_polly_client():
    """Obtiene o crea el cliente de Amazon Polly"""
    global polly_client
    if polly_client is None:
        polly_client = PollyClient()
    return polly_client


# Modelos Pydantic
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    top_k: Optional[int] = 4
    temperature: Optional[float] = 0.7
    llm_provider: Optional[str] = None  # "groq" o "deepseek"


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    match_type: Optional[str] = None
    best_faq_similarity: Optional[float] = None
    context_type: Optional[str] = None
    relevant_documents: List[Dict] = []
    timestamp: str


class StatsResponse(BaseModel):
    total_documents: int
    storage_path: str
    embedder_model: str
    llm_model: str
    llm_provider: str
    max_history: int
    current_history_length: int


class HistoryResponse(BaseModel):
    session_id: str
    history: List[Dict]


class ModelChangeRequest(BaseModel):
    session_id: Optional[str] = "default"
    llm_provider: str  # "groq" o "deepseek"

class TranscriptionResponse(BaseModel):
    text: Optional[str] = None
    timestamp: str


class SynthesizeRequest(BaseModel):
    text: str

class SynthesizeResponse(BaseModel):
    audio_base64: str
    timestamp: str


# Funciones auxiliares
def get_chatbot(session_id: str = "default", llm_provider: str = None) -> RAGChatbot:
    """Obtiene o crea una instancia del chatbot para la sesión"""
    # Si no se especifica proveedor, usar el guardado o default
    if llm_provider is None:
        llm_provider = session_llm_providers.get(session_id, "groq")

    # Si no existe el chatbot o cambió el proveedor, recrear
    if session_id not in chat_sessions or session_llm_providers.get(session_id) != llm_provider:
        # Cerrar chatbot anterior si existe
        if session_id in chat_sessions:
            chat_sessions[session_id].close()

        # Crear nuevo chatbot con el proveedor especificado
        chat_sessions[session_id] = RAGChatbot(max_history=10, llm_provider=llm_provider)
        session_llm_providers[session_id] = llm_provider

    return chat_sessions[session_id]


# Endpoints
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Chatbot VOAE API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Verifica el estado de la API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal para interactuar con el chatbot

    Args:
        request: ChatRequest con el mensaje del usuario

    Returns:
        ChatResponse con la respuesta del chatbot y metadata
    """
    try:
        # Obtener chatbot de la sesión (con proveedor LLM si se especifica)
        chatbot = get_chatbot(request.session_id, request.llm_provider)

        # Procesar mensaje
        result = chatbot.chat(
            user_message=request.message,
            top_k=request.top_k,
            temperature=request.temperature,
            use_rag=True
        )

        # Construir respuesta
        return ChatResponse(
            answer=result.get("answer", "No se pudo generar una respuesta"),
            session_id=request.session_id,
            match_type=result.get("match_type"),
            best_faq_similarity=result.get("best_faq_similarity"),
            context_type=result.get("context_type"),
            relevant_documents=result.get("relevant_documents", []),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el mensaje: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(session_id: str = "default"):
    """
    Obtiene estadísticas del sistema

    Args:
        session_id: ID de la sesión

    Returns:
        StatsResponse con estadísticas del sistema
    """
    try:
        chatbot = get_chatbot(session_id)
        stats = chatbot.get_stats()

        # Obtener el proveedor actual de la sesión
        current_provider = session_llm_providers.get(session_id, "groq")

        return StatsResponse(
            total_documents=stats["total_documents"],
            storage_path=stats["storage_path"],
            embedder_model=stats["embedder_model"],
            llm_model=stats["llm_model"],
            llm_provider=current_provider,
            max_history=stats["max_history"],
            current_history_length=stats["current_history_length"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")


@app.get("/history", response_model=HistoryResponse)
async def get_history(session_id: str = "default"):
    """
    Obtiene el historial de conversación de una sesión

    Args:
        session_id: ID de la sesión

    Returns:
        HistoryResponse con el historial de la sesión
    """
    try:
        chatbot = get_chatbot(session_id)
        history = chatbot.get_history()

        # Formatear historial
        formatted_history = [
            {
                "user_message": user_msg,
                "assistant_message": assistant_msg,
                "index": i
            }
            for i, (user_msg, assistant_msg) in enumerate(history)
        ]

        return HistoryResponse(
            session_id=session_id,
            history=formatted_history
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener historial: {str(e)}")


@app.post("/clear-history")
async def clear_history(session_id: str = "default"):
    """
    Limpia el historial de conversación de una sesión

    Args:
        session_id: ID de la sesión

    Returns:
        Mensaje de confirmación
    """
    try:
        chatbot = get_chatbot(session_id)
        chatbot.clear_history()

        return {
            "message": "Historial limpiado exitosamente",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al limpiar historial: {str(e)}")


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Elimina una sesión de chat

    Args:
        session_id: ID de la sesión a eliminar

    Returns:
        Mensaje de confirmación
    """
    if session_id in chat_sessions:
        chat_sessions[session_id].close()
        del chat_sessions[session_id]
        return {
            "message": f"Sesión {session_id} eliminada",
            "timestamp": datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")


@app.get("/sessions")
async def list_sessions():
    """
    Lista todas las sesiones activas

    Returns:
        Lista de IDs de sesiones activas
    """
    return {
        "sessions": list(chat_sessions.keys()),
        "count": len(chat_sessions),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...), language: str = "es"):
    """
    Transcribe audio a texto usando Groq Whisper

    Optimizations:
    - Pre-initialized transcription client (no cold start)
    - Async file reading
    - Direct bytes processing (no temp file)

    Args:
        audio: Archivo de audio (wav, mp3, webm, etc.)
        language: Código de idioma (default: "es" para español)

    Returns:
        TranscriptionResponse con el texto transcrito
    """
    
    try:
        # Read audio bytes asynchronously (faster)
        audio_bytes = await audio.read()

        # Get pre-initialized transcription client (no initialization delay)
        client = get_transcription_client()

        # Transcribe audio - Groq's LPU makes this very fast
        text = client.transcribe_audio_bytes(
            audio_bytes=audio_bytes,
            filename=audio.filename or "audio.webm",
            language=language,
        )

        if text is None:
            return TranscriptionResponse(
                text=None,
                timestamp=datetime.now().isoformat()
            )

        return TranscriptionResponse(
            text=text,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al transcribir audio: {str(e)}")


@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(request: SynthesizeRequest):
    """Sintetiza texto a audio MP3 usando Amazon Polly"""
    try:
        client = get_polly_client()
        audio_base64 = client.synthesize(request.text)
        return SynthesizeResponse(
            audio_base64=audio_base64,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sintetizar audio: {str(e)}")


_ACRONYMS_PATTERN = re.compile(
    r'\b(VOAE|UNAH|UNAH-VS|VRA|DIPP|PAC|PASEE|PROCAD|PROSENE|CIVU|PAIE|PAI-E|PAPE|PHUMA|IAG)\b'
)

def preprocess_text_for_tts(text: str) -> str:
    """Elimina markdown y convierte acrónimos a minúsculas para Polly."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
    text = _ACRONYMS_PATTERN.sub(lambda m: m.group().lower(), text)
    return text.strip()


def split_sentences(text: str) -> list:
    """Divide el texto en oraciones para síntesis progresiva."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


@app.post("/chat-stream")
async def chat_stream(request: ChatRequest):
    """
    Endpoint SSE: procesa el mensaje RAG y devuelve oraciones con audio PCM
    para animación en tiempo real con Simli.

    Eventos SSE:
      - type: "meta"  → metadata de la respuesta (match_type, sources, etc.)
      - type: "chunk" → { text, audio_base64 } por cada oración
      - type: "done"  → fin del stream
      - type: "error" → mensaje de error
    """
    async def generate():
        try:
            chatbot = get_chatbot(request.session_id, request.llm_provider)
            result = chatbot.chat(
                user_message=request.message,
                top_k=request.top_k,
                temperature=request.temperature,
                use_rag=True
            )

            # Enviar metadata primero
            meta = {
                "type": "meta",
                "match_type": result.get("match_type"),
                "best_faq_similarity": result.get("best_faq_similarity"),
                "context_type": result.get("context_type"),
                "relevant_documents": result.get("relevant_documents", []),
                "timestamp": datetime.now().isoformat(),
            }
            yield f"data: {json.dumps(meta)}\n\n"
            await asyncio.sleep(0)

            # Sintetizar y enviar oración por oración
            polly = get_polly_client()
            answer = result.get("answer", "")
            sentences = split_sentences(answer)

            for sentence in sentences:
                tts_text = preprocess_text_for_tts(sentence)
                if not tts_text:
                    continue
                audio_b64 = polly.synthesize(tts_text)
                chunk = {
                    "type": "chunk",
                    "text": sentence,
                    "audio_base64": audio_b64,
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            print(f"❌ Error en /chat-stream: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/change-model")
async def change_model(request: ModelChangeRequest):
    """
    Cambia el proveedor de LLM para una sesión

    Args:
        request: ModelChangeRequest con session_id y llm_provider

    Returns:
        Confirmación del cambio con el nuevo modelo
    """
    try:
        # Validar proveedor
        if request.llm_provider not in ["groq", "deepseek"]:
            raise HTTPException(
                status_code=400,
                detail="Proveedor inválido. Usa 'groq' o 'deepseek'"
            )

        # Forzar recreación del chatbot con nuevo proveedor
        if request.session_id in chat_sessions:
            chat_sessions[request.session_id].close()
            del chat_sessions[request.session_id]

        # Actualizar el proveedor guardado
        session_llm_providers[request.session_id] = request.llm_provider

        # Crear nuevo chatbot con el proveedor especificado
        chatbot = get_chatbot(request.session_id, request.llm_provider)

        # Obtener stats del nuevo chatbot
        stats = chatbot.get_stats()

        return {
            "message": f"Modelo cambiado exitosamente a {request.llm_provider}",
            "session_id": request.session_id,
            "llm_provider": request.llm_provider,
            "llm_model": stats["llm_model"],
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cambiar modelo: {str(e)}")


def _float32_to_wav(float32_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Convierte muestras Float32 (little-endian) a WAV PCM Int16 mono."""
    n_samples = len(float32_bytes) // 4
    samples = struct.unpack(f'<{n_samples}f', float32_bytes)
    pcm_int16 = bytearray()
    for s in samples:
        val = max(-32768, min(32767, int(s * 32767)))
        pcm_int16.extend(struct.pack('<h', val))

    data_size = len(pcm_int16)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1,                      # PCM, mono
        sample_rate, sample_rate * 2,            # sample rate, byte rate
        2, 16,                                   # block align, bits per sample
        b'data', data_size
    )
    return bytes(header) + bytes(pcm_int16)


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    """
    WebSocket para transcripción de audio PCM en tiempo real.
    El cliente envía chunks Float32 (binario) y una señal JSON {type:'done'} al terminar.
    El servidor responde con {text: '...'} vía WebSocket.
    """
    await websocket.accept()
    client = get_transcription_client()
    pcm_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if 'bytes' in message:
                # Chunk de audio PCM Float32
                pcm_buffer.extend(message['bytes'])

            elif 'text' in message:
                msg = json.loads(message['text'])
                if msg.get('type') == 'done':
                    text = None
                    if pcm_buffer:
                        wav_data = _float32_to_wav(bytes(pcm_buffer))
                        text = client.transcribe_audio_bytes(wav_data, 'audio.wav', 'es')
                    await websocket.send_text(json.dumps({'text': text or ''}))
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error en transcripción: {e}")
        try:
            await websocket.send_text(json.dumps({'text': ''}))
        except Exception:
            pass


if __name__ == "__main__":
    # Ejecutar servidor
    print("🚀 Iniciando API del Chatbot VOAE...")
    print("📍 URL: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
