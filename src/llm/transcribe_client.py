"""
Cliente Amazon Transcribe Streaming para STT
Reemplaza Groq Whisper (whisper-large-v3)
"""
import asyncio
import io
import os
import re
import wave
from typing import Optional

from config import BedrockConfig


# Nombre del vocabulario personalizado en Amazon Transcribe
VOCABULARY_NAME = "voae-vocabulary"

# Términos de dominio extraídos de los documentos de VOAE/UNAH.
# Amazon Transcribe usa estas frases para mejorar el reconocimiento.
# Frases de varias palabras usan guion como separador (requisito de Transcribe).
_DOMAIN_TERMS = [
    # Siglas institucionales
    "VOAE", "UNAH", "UNAH-VS", "VRA", "DIPP", "CIVU", "IAG", "IAP",
    # Períodos académicos
    "PAC", "IPAC", "IIPAC", "IIIPAC",
    # Programas VOAE
    "PASEE", "PROCAD", "PROSENE", "PAIE", "PAI-E", "PAPE", "PHUMA",
    # Distinciones académicas (guion = separador de palabras en Transcribe)
    "Summa-Cum-Laude", "Magna-Cum-Laude", "Cum-Laude",
    "Alma-Mater", "Mencion-Honorofica",
    # Becas y financiamiento
    "Mi-Bienestar", "Credito-Educativo",
    # Índices y métricas
    "UV",
    # Procesos y trámites frecuentes
    "Readmision", "Horas-VOAE", "Cambio-de-Carrera",
    # Servicios y programas
    "Feria-Vocacional", "Vida-Universitaria", "Movilidad-Academica",
    "Unidad-Medico-Deportiva", "Escuela-de-Liderazgo",
    "Dispensarizacion",
    # Evaluaciones
    "Prueba-Vocacional", "Examen-de-Suficiencia",
    # Becas por nombre
    "Beca-Equidad", "Beca-Alma-Mater",
]

# Mapa de códigos de idioma
_LANG_MAP = {
    "es": "es-US",
    "en": "en-US",
}

# Tamaño de chunk para streaming (bytes de PCM)
_CHUNK_SIZE = 1024 * 8  # 8 KB


class TranscribeClient:
    """
    Cliente asíncrono para Amazon Transcribe Streaming.

    Los métodos de transcripción son corrutinas (async def) — en api/main.py
    deben llamarse con 'await'.

    Formatos de audio aceptados:
    - WAV PCM (mono, 16 kHz, 16-bit) — path del WebSocket
    - WebM/Opus (grabación del navegador) — path del endpoint HTTP
      Requiere ffmpeg instalado y la librería 'pydub'.
    """

    # ------------------------------------------------------------------
    # Frases que Whisper alucina con silencio/ruido; las mantenemos aquí
    # porque Amazon Transcribe también puede producirlas con audio corto.
    # ------------------------------------------------------------------
    _HALLUCINATION_PHRASES = frozenset({
        "gracias.", "de nada.", "sí.", "no.", "ok.", "hola.", "bye.",
        "hasta luego.", "buenas.", "claro.", "por favor.", "perdón.",
        "gracias por ver el video.", "gracias por su atención.",
        "suscríbete al canal.", "dale like y suscríbete.",
        "subtítulos realizados por la comunidad de amara.org",
        "subtítulos en español", "subtítulos por la comunidad",
        "transcripción automática", "transcripción",
        "thank you.", "thanks.", "you.", "yes.", "okay.",
        "obrigado.", "obrigada.", "sim.", "não.",
        "merci.", "oui.", "non.", "bonjour.",
        "♪", "♫", "...", ". . .", "…",
    })

    def __init__(self):
        self.region = BedrockConfig.AWS_REGION
        self.access_key = BedrockConfig.AWS_ACCESS_KEY
        self.secret_key = BedrockConfig.AWS_SECRET_KEY

        if not self.access_key or not self.secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env"
            )

        # Exportar credenciales al entorno para que el SDK de Transcribe las tome
        os.environ.setdefault("AWS_ACCESS_KEY_ID", self.access_key)
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", self.secret_key)
        os.environ.setdefault("AWS_DEFAULT_REGION", self.region)

    # ------------------------------------------------------------------
    # Detección de alucinaciones
    # ------------------------------------------------------------------

    def _is_hallucination(self, text: str) -> bool:
        if not text or not text.strip():
            return True
        clean = text.strip()
        if re.search(r"<\|.*?\|>", clean):
            return True
        if len(clean) < 4:
            return True
        if clean.lower() in self._HALLUCINATION_PHRASES:
            return True
        if re.fullmatch(r"[\W\s]+", clean):
            return True
        words = clean.split()
        if len(words) >= 3 and len(set(w.lower().strip(".,!?") for w in words)) == 1:
            return True
        return False

    # ------------------------------------------------------------------
    # Gestión del vocabulario personalizado
    # ------------------------------------------------------------------

    def create_vocabulary(self) -> str:
        """
        Crea o actualiza el vocabulario personalizado en Amazon Transcribe.

        Llama a este método UNA SOLA VEZ (o cuando añadas nuevos términos).
        El vocabulario tarda ~1 minuto en estar listo (estado READY).

        Returns:
            Estado final del vocabulario ("READY", "PENDING", etc.)
        """
        import boto3 as _boto3
        import time as _time

        client = _boto3.client(
            "transcribe",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

        # Verificar si ya existe para decidir entre create o update
        try:
            existing = client.get_vocabulary(VocabularyName=VOCABULARY_NAME)
            action = "update"
        except client.exceptions.BadRequestException:
            action = "create"

        params = {
            "VocabularyName": VOCABULARY_NAME,
            "LanguageCode": "es-US",
            "Phrases": _DOMAIN_TERMS,
        }

        if action == "create":
            client.create_vocabulary(**params)
            print(f"[Transcribe] Vocabulario '{VOCABULARY_NAME}' creado.")
        else:
            client.update_vocabulary(**params)
            print(f"[Transcribe] Vocabulario '{VOCABULARY_NAME}' actualizado.")

        # Esperar hasta que esté listo (máx. 3 minutos)
        print("[Transcribe] Esperando que el vocabulario quede READY", end="", flush=True)
        for _ in range(36):
            _time.sleep(5)
            info = client.get_vocabulary(VocabularyName=VOCABULARY_NAME)
            state = info["VocabularyState"]
            print(".", end="", flush=True)
            if state in ("READY", "FAILED"):
                break
        print(f" {state}")
        if state == "FAILED":
            raise RuntimeError(
                f"El vocabulario falló. Revisa la consola de Amazon Transcribe."
            )
        return state

    # ------------------------------------------------------------------
    # Conversión de audio
    # ------------------------------------------------------------------

    @staticmethod
    def _wav_to_pcm(wav_bytes: bytes) -> bytes:
        """Extrae muestras PCM raw de un archivo WAV (sin header)."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.readframes(w.getnframes())

    @staticmethod
    def _webm_to_pcm(webm_bytes: bytes) -> bytes:
        """
        Convierte cualquier formato de audio (WebM/Opus, MP3, etc.) a PCM mono 16 kHz 16-bit
        usando ffmpeg directamente vía subprocess. No depende de pydub ni audioop.
        Requiere ffmpeg instalado y accesible en PATH.
        """
        import subprocess
        import shutil

        ffmpeg_cmd = shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            # Ruta típica de instalación por winget en Windows
            winget_path = (
                r"C:\Users\Kevin Garcia\AppData\Local\Microsoft\WinGet\Packages"
                r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                r"\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
            )
            if __import__("os").path.exists(winget_path):
                ffmpeg_cmd = winget_path
            else:
                raise RuntimeError(
                    "ffmpeg no encontrado en PATH. "
                    "Reinicia la terminal o instala ffmpeg: winget install Gyan.FFmpeg"
                )

        cmd = [
            ffmpeg_cmd,
            "-i", "pipe:0",          # entrada desde stdin
            "-f", "s16le",           # PCM signed 16-bit little-endian (raw)
            "-ar", "16000",          # 16 kHz
            "-ac", "1",              # mono
            "-loglevel", "error",    # silenciar logs innecesarios
            "pipe:1",                # salida a stdout
        ]

        result = subprocess.run(
            cmd,
            input=webm_bytes,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg falló al convertir audio: {result.stderr.decode(errors='replace')}"
            )

        return result.stdout  # bytes PCM raw sin header

    # ------------------------------------------------------------------
    # Transcripción vía Amazon Transcribe Streaming
    # ------------------------------------------------------------------

    async def _stream_transcribe(self, pcm_bytes: bytes, language: str) -> str:
        """Envía PCM raw a Amazon Transcribe Streaming y devuelve el texto."""
        from amazon_transcribe.client import TranscribeStreamingClient
        from amazon_transcribe.handlers import TranscriptResultStreamHandler
        from amazon_transcribe.model import TranscriptEvent

        lang_code = _LANG_MAP.get(language, "es-US")

        client = TranscribeStreamingClient(region=self.region)
        stream = await client.start_stream_transcription(
            language_code=lang_code,
            media_sample_rate_hz=16000,
            media_encoding="pcm",
            vocabulary_name=VOCABULARY_NAME,
        )

        transcript_parts: list[str] = []

        class _Handler(TranscriptResultStreamHandler):
            async def handle_transcript_event(self, event: TranscriptEvent):
                for result in event.transcript.results:
                    if not result.is_partial:
                        for alt in result.alternatives:
                            transcript_parts.append(alt.transcript)

        handler = _Handler(stream.output_stream)

        async def _send_audio():
            for i in range(0, len(pcm_bytes), _CHUNK_SIZE):
                await stream.input_stream.send_audio_event(
                    audio_chunk=pcm_bytes[i : i + _CHUNK_SIZE]
                )
            await stream.input_stream.end_stream()

        await asyncio.gather(_send_audio(), handler.handle_events())
        return " ".join(transcript_parts).strip()

    # ------------------------------------------------------------------
    # API pública (async — usar con 'await' en FastAPI)
    # ------------------------------------------------------------------

    async def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "es",
    ) -> Optional[str]:
        """
        Transcribe audio a texto.

        Args:
            audio_bytes: Bytes del audio (WAV PCM o WebM/Opus)
            filename:    Nombre del archivo; se usa para detectar el formato
            language:    Código de idioma ('es', 'en')

        Returns:
            Texto transcrito, o None si el audio es inválido/alucinación.
        """
        if not audio_bytes or len(audio_bytes) < 500:
            return None

        try:
            # Detectar formato por magic bytes o extensión
            if audio_bytes[:4] == b"RIFF":
                pcm_bytes = self._wav_to_pcm(audio_bytes)
            else:
                # WebM/Opus (grabación del navegador)
                pcm_bytes = self._webm_to_pcm(audio_bytes)

            if not pcm_bytes:
                return None

            text = await self._stream_transcribe(pcm_bytes, language)

            if self._is_hallucination(text):
                return None

            return text or None

        except Exception as e:
            raise Exception(f"Error al transcribir audio: {str(e)}") from e
