"""
Cliente Groq Whisper Large V3 para STT
"""
import asyncio
import io
import re
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from groq import Groq
from config import GroqConfig


# Palabras clave de dominio para guiar a Whisper (prompt conditioning).
# Whisper usa este texto como contexto previo para mejorar el reconocimiento.
_DOMAIN_KEYWORDS = (
    "VOAE, UNAH, UNAH-VS, VRA, DIPP, CIVU, IAG, IAP, "
    "PAC, IPAC, IIPAC, IIIPAC, "
    "PASEE, PROCAD, PROSENE, PAIE, PAI-E, PAPE, PHUMA, "
    "Summa Cum Laude, Magna Cum Laude, Cum Laude, "
    "Alma Mater, Mención Honorífica, "
    "Mi Bienestar, Crédito Educativo, "
    "Readmisión, Horas VOAE, Cambio de Carrera, "
    "Feria Vocacional, Vida Universitaria, Movilidad Académica, "
    "Unidad Médico Deportiva, Escuela de Liderazgo, "
    "Dispensarización, "
    "Prueba Vocacional, Examen de Suficiencia, "
    "Beca Equidad, Beca Alma Mater"
)


class TranscriptionClient:
    """
    Cliente para Groq Whisper Large V3.

    Formato de audio aceptado:
    - WAV, MP3, MP4, MPEG, MPGA, M4A, WEBM, OGG, FLAC
    - Maximo 25 MB
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
        self.client = Groq(api_key=GroqConfig.API_KEY)
        self.model = GroqConfig.WHISPER_MODEL

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

    async def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "es",
    ) -> Optional[str]:
        """
        Transcribe audio a texto usando Groq Whisper Large V3.

        Args:
            audio_bytes: Bytes del audio (WAV, MP3, WEBM, etc.)
            filename:    Nombre del archivo (usado para detectar formato)
            language:    Codigo de idioma ('es', 'en')

        Returns:
            Texto transcrito, o None si el audio es invalido/alucinacion.
        """
        if not audio_bytes or len(audio_bytes) < 500:
            return None

        # Detectar silencio en WAV antes de enviar a Groq
        if audio_bytes[:4] == b"RIFF":
            try:
                import wave, struct
                with wave.open(io.BytesIO(audio_bytes), "rb") as w:
                    frames = w.readframes(w.getnframes())
                n_samples = len(frames) // 2
                if n_samples > 0:
                    samples = struct.unpack(f"<{n_samples}h", frames)
                    max_amp = max(abs(s) for s in samples)
                    if max_amp < 200:
                        print(f"[Whisper] Audio silencioso (max_amp={max_amp}), ignorando")
                        return None
            except Exception:
                pass

        try:
            transcription = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                model=self.model,
                file=(filename, io.BytesIO(audio_bytes)),
                language=language,
                prompt=_DOMAIN_KEYWORDS,
            )

            text = transcription.text.strip()
            print(f"[Whisper] Raw text: '{text}' ({len(text)} chars)")

            if self._is_hallucination(text):
                print(f"[Whisper] Filtrado como alucinacion")
                return None

            return text or None

        except Exception as e:
            raise Exception(f"Error al transcribir audio: {str(e)}") from e


if __name__ == "__main__":
    print("=== Test de TranscriptionClient (Groq Whisper) ===\n")
    try:
        client = TranscriptionClient()
        print(f"Cliente inicializado: modelo={client.model}")
        print(f"\nPara transcribir (async):")
        print(f"  await client.transcribe_audio_bytes(audio_bytes, 'audio.wav')")
    except Exception as e:
        print(f"Error: {e}")
