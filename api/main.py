"""
FastAPI REST API para Chatbot VOAE - Amazon Bedrock
Compatible con AWS Lambda (via Mangum) y ejecucion local (uvicorn)
"""
import sys
import os
from pathlib import Path

# Agregar el directorio src al path
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)


from fastapi import FastAPI, HTTPException, UploadFile, File, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import asyncio
import json
import re
from datetime import datetime

from chatbot.chatbot import RAGChatbot
from llm.transcription_client import TranscriptionClient
from llm.polly_client import PollyClient
from config import APIConfig

# Inicializar FastAPI
app = FastAPI(
    title="Chatbot VOAE API",
    description="API REST para el Chatbot VOAE - Amazon Bedrock",
    version="3.0.0"
)

# Router con prefijo /api para CloudFront
router = APIRouter(prefix="/api")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=APIConfig.CORS_ORIGINS,
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


class ChatWithAudioResponse(BaseModel):
    answer: str
    sentences: List[Dict]
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


# Endpoints
@router.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "message": "Chatbot VOAE API - Bedrock",
        "version": "3.0.0",
        "docs": "/docs",
        "status": "running"
    }


@router.get("/health")
async def health_check():
    """Verifica el estado de la API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint de chat solo texto (sin audio)"""
    try:
        chatbot = get_chatbot(request.session_id)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(chatbot.chat, request.message, request.temperature),
                timeout=22.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail="El asistente tardó demasiado en responder. Por favor intenta de nuevo."
            )

        return ChatResponse(
            answer=result.get("answer", "No se pudo generar una respuesta"),
            session_id=request.session_id,
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el mensaje: {str(e)}")


@router.post("/chat-with-audio", response_model=ChatWithAudioResponse)
async def chat_with_audio(request: ChatRequest):
    """
    Endpoint principal: genera respuesta con Bedrock KB y sintetiza
    audio PCM por oracion con Polly para el avatar Simli.
    """
    try:
        chatbot = get_chatbot(request.session_id)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(chatbot.chat, request.message, request.temperature),
                timeout=22.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail="El asistente tardó demasiado en responder. Por favor intenta de nuevo."
            )

        answer = result.get("answer", "")
        polly = get_polly_client()
        sentences = []

        for sentence in split_sentences(answer):
            tts_text = preprocess_text_for_tts(sentence)
            if not tts_text:
                continue
            try:
                audio_b64 = await asyncio.wait_for(
                    asyncio.to_thread(polly.synthesize, tts_text),
                    timeout=4.0
                )
            except asyncio.TimeoutError:
                audio_b64 = ""
            sentences.append({"text": sentence, "audio_base64": audio_b64})

        return ChatWithAudioResponse(
            answer=answer,
            sentences=sentences,
            session_id=request.session_id,
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el mensaje: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
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


@router.get("/history", response_model=HistoryResponse)
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


@router.post("/clear-history")
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


@router.delete("/session/{session_id}")
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


@router.get("/sessions")
async def list_sessions():
    """Lista todas las sesiones activas"""
    return {
        "sessions": list(chat_sessions.keys()),
        "count": len(chat_sessions),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...), language: str = "es"):
    """Transcribe audio a texto usando Amazon Transcribe Streaming"""
    try:
        audio_bytes = await audio.read()

        if not audio_bytes or len(audio_bytes) < 500:
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

        return TranscriptionResponse(
            text=text,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al transcribir audio: {str(e)}")


@router.post("/synthesize", response_model=SynthesizeResponse)
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


# Registrar router con prefijo /api
app.include_router(router)

# Handler para AWS Lambda (Mangum)
from mangum import Mangum
handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    import uvicorn
    print("Iniciando API del Chatbot VOAE (Bedrock)...")
    print("URL: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
