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


import base64

from fastapi import FastAPI, HTTPException, UploadFile, File

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
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
    audio: str  # base64-encoded MP3
    words: List[str]
    wtimes: List[int]
    wdurations: List[int]
    visemes: List[str]  # Oculus viseme names (e.g. 'PP', 'aa', 'sil')
    vtimes: List[int]
    vdurations: List[int]


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
    """
    Sintetiza texto a voz usando Amazon Polly con datos de visemas para lip-sync

    Args:
        request: SynthesizeRequest con el texto a sintetizar

    Returns:
        SynthesizeResponse con audio base64 y datos de timing
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="El texto no puede estar vacío")

        # Truncar texto al límite de Polly
        text = request.text[:3000]

        client = get_polly_client()
        result = client.synthesize(text)

        # Codificar audio a base64
        audio_base64 = base64.b64encode(result['audio_bytes']).decode('utf-8')

        return SynthesizeResponse(
            audio=audio_base64,
            words=result['words'],
            wtimes=result['wtimes'],
            wdurations=result['wdurations'],
            visemes=result['visemes'],
            vtimes=result['vtimes'],
            vdurations=result['vdurations']
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sintetizar voz: {str(e)}")


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
