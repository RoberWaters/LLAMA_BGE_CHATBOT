"""
Cliente Amazon Transcribe Streaming para STT
"""
import asyncio
import io
import os
import re
import wave
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BedrockConfig


# Nombre del vocabulario personalizado en Amazon Transcribe
VOCABULARY_NAME = "voae-vocabulary"

# Terminos de dominio para mejorar el reconocimiento.
# Frases de varias palabras usan guion como separador (requisito de Transcribe).
_DOMAIN_TERMS = [
    "VOAE", "UNAH", "UNAH-VS", "VRA", "DIPP", "CIVU", "IAG", "IAP",
    "PAC", "IPAC", "IIPAC", "IIIPAC",
    "PASEE", "PROCAD", "PROSENE", "PAIE", "PAI-E", "PAPE", "PHUMA",
    "Summa-Cum-Laude", "Magna-Cum-Laude", "Cum-Laude",
    "Alma-Mater", "Mencion-Honorifica",
    "Mi-Bienestar", "Credito-Educativo",
    "UV", "Readmision", "Horas-VOAE", "Cambio-de-Carrera",
    "Feria-Vocacional", "Vida-Universitaria", "Movilidad-Academica",
    "Unidad-Medico-Deportiva", "Escuela-de-Liderazgo",
    "Dispensarizacion",
    "Prueba-Vocacional", "Examen-de-Suficiencia",
    "Beca-Equidad", "Beca-Alma-Mater",
]

_LANG_MAP = {
    "es": "es-US",
    "en": "en-US",
}

_CHUNK_SIZE = 1024 * 8  # 8 KB


class TranscriptionClient:
    """
    Cliente asincrono para Amazon Transcribe Streaming.

    Los metodos de transcripcion son async — usar con 'await' en FastAPI.

    Formato de audio aceptado:
    - WAV PCM (mono, 16 kHz, 16-bit)
    """

    _HALLUCINATION_PHRASES = frozenset({
        "gracias.", "de nada.", "si.", "no.", "ok.", "hola.", "bye.",
        "hasta luego.", "buenas.", "claro.", "por favor.", "perdon.",
        "gracias por ver el video.", "gracias por su atencion.",
        "suscribete al canal.", "dale like y suscribete.",
        "subtitulos realizados por la comunidad de amara.org",
        "subtitulos en espanol", "subtitulos por la comunidad",
        "transcripcion automatica", "transcripcion",
        "thank you.", "thanks.", "you.", "yes.", "okay.",
        "obrigado.", "obrigada.", "sim.", "nao.",
        "merci.", "oui.", "non.", "bonjour.",
        "...", ". . .",
    })

    def __init__(self):
        self.region = BedrockConfig.AWS_REGION
        self.access_key = BedrockConfig.AWS_ACCESS_KEY
        self.secret_key = BedrockConfig.AWS_SECRET_KEY

        if not self.access_key or not self.secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env"
            )

        # Exportar credenciales para que el SDK de Transcribe las tome
        os.environ.setdefault("AWS_ACCESS_KEY_ID", self.access_key)
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", self.secret_key)
        os.environ.setdefault("AWS_DEFAULT_REGION", self.region)

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

    @staticmethod
    def _wav_to_pcm(wav_bytes: bytes) -> bytes:
        """Extrae muestras PCM raw de un archivo WAV (sin header)."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.readframes(w.getnframes())

    async def _stream_transcribe(self, pcm_bytes: bytes, language: str) -> str:
        """Envia PCM raw a Amazon Transcribe Streaming y devuelve el texto."""
        from amazon_transcribe.client import TranscribeStreamingClient
        from amazon_transcribe.handlers import TranscriptResultStreamHandler
        from amazon_transcribe.model import TranscriptEvent

        lang_code = _LANG_MAP.get(language, "es-US")

        client = TranscribeStreamingClient(region=self.region)

        stream_kwargs = {
            "language_code": lang_code,
            "media_sample_rate_hz": 16000,
            "media_encoding": "pcm",
        }

        # Usar vocabulario personalizado solo si existe
        try:
            import boto3
            tc = boto3.client(
                "transcribe",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
            info = tc.get_vocabulary(VocabularyName=VOCABULARY_NAME)
            if info.get("VocabularyState") == "READY":
                stream_kwargs["vocabulary_name"] = VOCABULARY_NAME
        except Exception:
            pass

        stream = await client.start_stream_transcription(**stream_kwargs)

        # Verificar que el audio no sea silencio
        import struct as _struct
        n_samples = len(pcm_bytes) // 2
        samples = _struct.unpack(f'<{n_samples}h', pcm_bytes)
        max_amp = max(abs(s) for s in samples)
        print(f"[Transcribe] PCM stats: {n_samples} samples, max_amplitude={max_amp}")

        transcript_parts: list[str] = []

        class _Handler(TranscriptResultStreamHandler):
            async def handle_transcript_event(self, event: TranscriptEvent):
                for result in event.transcript.results:
                    print(f"[Transcribe] Event: partial={result.is_partial}, "
                          f"alts={[a.transcript for a in result.alternatives]}")
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
            print(f"[Transcribe] Audio enviado ({len(pcm_bytes)} bytes en chunks de {_CHUNK_SIZE})")

        await asyncio.gather(_send_audio(), handler.handle_events())
        print(f"[Transcribe] transcript_parts: {transcript_parts}")
        return " ".join(transcript_parts).strip()

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
            language:    Codigo de idioma ('es', 'en')

        Returns:
            Texto transcrito, o None si el audio es invalido/alucinacion.
        """
        if not audio_bytes or len(audio_bytes) < 500:
            return None

        try:
            if audio_bytes[:4] != b"RIFF":
                raise ValueError("Formato de audio no soportado. Se espera WAV (RIFF).")

            # Log propiedades del WAV
            import wave as _wave
            _w = _wave.open(io.BytesIO(audio_bytes), "rb")
            print(f"[Transcribe] WAV: channels={_w.getnchannels()}, rate={_w.getframerate()}, "
                  f"sampwidth={_w.getsampwidth()}, frames={_w.getnframes()}, "
                  f"duration={_w.getnframes()/_w.getframerate():.2f}s")
            _w.close()

            pcm_bytes = self._wav_to_pcm(audio_bytes)
            print(f"[Transcribe] PCM bytes: {len(pcm_bytes)}")

            if not pcm_bytes:
                return None

            text = await self._stream_transcribe(pcm_bytes, language)
            print(f"[Transcribe] Raw text: '{text}' ({len(text)} chars)")

            if self._is_hallucination(text):
                print(f"[Transcribe] Filtrado como alucinacion")
                return None

            return text or None

        except Exception as e:
            raise Exception(f"Error al transcribir audio: {str(e)}") from e

    def create_vocabulary(self) -> str:
        """
        Crea o actualiza el vocabulario personalizado en Amazon Transcribe.
        Llamar UNA SOLA VEZ (o cuando se anadan nuevos terminos).
        """
        import boto3
        import time

        client = boto3.client(
            "transcribe",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

        try:
            client.get_vocabulary(VocabularyName=VOCABULARY_NAME)
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

        print("[Transcribe] Esperando que el vocabulario quede READY", end="", flush=True)
        for _ in range(36):
            time.sleep(5)
            info = client.get_vocabulary(VocabularyName=VOCABULARY_NAME)
            state = info["VocabularyState"]
            print(".", end="", flush=True)
            if state in ("READY", "FAILED"):
                break
        print(f" {state}")
        if state == "FAILED":
            raise RuntimeError("El vocabulario fallo. Revisa la consola de Amazon Transcribe.")
        return state


if __name__ == "__main__":
    print("=== Test de TranscriptionClient (Amazon Transcribe) ===\n")
    try:
        client = TranscriptionClient()
        print(f"Cliente inicializado correctamente")
        print(f"Region: {client.region}")
        print(f"\nPara crear el vocabulario personalizado:")
        print(f"  client.create_vocabulary()")
        print(f"\nPara transcribir (async):")
        print(f"  await client.transcribe_audio_bytes(audio_bytes, 'audio.webm')")
    except ValueError as e:
        print(f"Error: {e}")
