"""
FastAPI REST API para Chatbot VOAE - Amazon Bedrock
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

from llm.transcription_client import TranscriptionClient  # async (Amazon Transcribe)
from llm.polly_client import PollyClient

# Inicializar FastAPI
app = FastAPI(
    title="Chatbot VOAE API",
    description="API REST para el Chatbot VOAE - Amazon Bedrock",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
chat_sessions = {}


transcription_client = None

def get_transcription_client():
    """Obtiene o crea el cliente de transcripcion"""
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
    temperature: Optional[float] = 0.7


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    timestamp: str


class StatsResponse(BaseModel):
    llm_model: str
    llm_provider: str
    max_history: int
    current_history_length: int


class HistoryResponse(BaseModel):
    session_id: str
    history: List[Dict]


class TranscriptionResponse(BaseModel):
    text: Optional[str] = None
    timestamp: str


class SynthesizeRequest(BaseModel):
    text: str

class SynthesizeResponse(BaseModel):
    audio_base64: str
    timestamp: str


# Funciones auxiliares
def get_chatbot(session_id: str = "default") -> RAGChatbot:
    """Obtiene o crea una instancia del chatbot para la sesion"""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = RAGChatbot()
    return chat_sessions[session_id]


# Endpoints
@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "message": "Chatbot VOAE API - Bedrock",
        "version": "2.0.0",
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
    """Endpoint principal para interactuar con el chatbot"""
    try:
        chatbot = get_chatbot(request.session_id)

        result = chatbot.chat(
            user_message=request.message,
            temperature=request.temperature
        )

        return ChatResponse(
            answer=result.get("answer", "No se pudo generar una respuesta"),
            session_id=request.session_id,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el mensaje: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(session_id: str = "default"):
    """Obtiene estadisticas del sistema"""
    try:
        chatbot = get_chatbot(session_id)
        stats = chatbot.get_stats()

        return StatsResponse(
            llm_model=stats["llm_model"],
            llm_provider=stats["llm_provider"],
            max_history=stats["max_history"],
            current_history_length=stats["current_history_length"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadisticas: {str(e)}")


@app.get("/history", response_model=HistoryResponse)
async def get_history(session_id: str = "default"):
    """Obtiene el historial de conversacion de una sesion"""
    try:
        chatbot = get_chatbot(session_id)
        history = chatbot.get_history()

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
    """Limpia el historial de conversacion de una sesion"""
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
    """Elimina una sesion de chat"""
    if session_id in chat_sessions:
        chat_sessions[session_id].close()
        del chat_sessions[session_id]
        return {
            "message": f"Sesion {session_id} eliminada",
            "timestamp": datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=404, detail=f"Sesion {session_id} no encontrada")


@app.get("/sessions")
async def list_sessions():
    """Lista todas las sesiones activas"""
    return {
        "sessions": list(chat_sessions.keys()),
        "count": len(chat_sessions),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...), language: str = "es"):
    """Transcribe audio a texto usando Amazon Transcribe Streaming"""
    try:
        audio_bytes = await audio.read()
        print(f"[Transcribe] Recibido: {len(audio_bytes)} bytes, filename={audio.filename}")
        print(f"[Transcribe] Header: {audio_bytes[:4]}")

        if not audio_bytes or len(audio_bytes) < 500:
            print(f"[Transcribe] Audio muy corto ({len(audio_bytes)} bytes), ignorando")
            return TranscriptionResponse(
                text=None,
                timestamp=datetime.now().isoformat()
            )

        client = get_transcription_client()

        text = await client.transcribe_audio_bytes(
            audio_bytes=audio_bytes,
            filename=audio.filename or "audio.wav",
            language=language,
        )
        print(f"[Transcribe] Resultado: '{text}'")

        return TranscriptionResponse(
            text=text,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        import traceback
        print(f"[Transcribe] ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al transcribir audio: {str(e)}")


@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(request: SynthesizeRequest):
    """Sintetiza texto a audio PCM usando Amazon Polly"""
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
    """Elimina markdown y convierte acronimos a minusculas para Polly."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
    text = _ACRONYMS_PATTERN.sub(lambda m: m.group().lower(), text)
    return text.strip()


def split_sentences(text: str) -> list:
    """Divide el texto en oraciones para sintesis progresiva."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


@app.post("/chat-stream")
async def chat_stream(request: ChatRequest):
    """
    Endpoint SSE: procesa el mensaje y devuelve oraciones con audio PCM
    para animacion en tiempo real con Simli.

    Eventos SSE:
      - type: "chunk" -> { text, audio_base64 } por cada oracion
      - type: "done"  -> fin del stream
      - type: "error" -> mensaje de error
    """
    async def generate():
        try:
            chatbot = get_chatbot(request.session_id)
            result = chatbot.chat(
                user_message=request.message,
                temperature=request.temperature
            )

            # Sintetizar y enviar oracion por oracion
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
            print(f"Error en /chat-stream: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
        b'fmt ', 16, 1, 1,
        sample_rate, sample_rate * 2,
        2, 16,
        b'data', data_size
    )
    return bytes(header) + bytes(pcm_int16)


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    """
    WebSocket para transcripcion de audio PCM en tiempo real.
    El cliente envia chunks Float32 (binario) y una senal JSON {type:'done'} al terminar.
    El servidor responde con {text: '...'} via WebSocket.
    """
    await websocket.accept()
    client = get_transcription_client()
    pcm_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if 'bytes' in message:
                pcm_buffer.extend(message['bytes'])

            elif 'text' in message:
                msg = json.loads(message['text'])
                if msg.get('type') == 'done':
                    text = None
                    if pcm_buffer:
                        wav_data = _float32_to_wav(bytes(pcm_buffer))
                        text = await client.transcribe_audio_bytes(wav_data, 'audio.wav', 'es')
                    await websocket.send_text(json.dumps({'text': text or ''}))
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error en transcripcion: {e}")
        try:
            await websocket.send_text(json.dumps({'text': ''}))
        except Exception:
            pass


if __name__ == "__main__":
    print("Iniciando API del Chatbot VOAE (Bedrock)...")
    print("URL: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
