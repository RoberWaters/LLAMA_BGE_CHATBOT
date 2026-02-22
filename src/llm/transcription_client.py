"""
Cliente para transcripción de audio usando Groq Whisper
"""
import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Frases que Whisper alucina cuando recibe audio silencioso o corrupto.
# Provienen del sesgo de entrenamiento con vídeos de YouTube.
_HALLUCINATION_PHRASES = {
    "gracias por ver el video",
    "gracias por ver",
    "gracias por ver este video",
    "gracias por ver el vídeo",
    "gracias por ver este vídeo",
    "gracias por el video",
    "gracias por el vídeo",
    "suscríbete al canal",
    "no olvides suscribirte",
    "subtítulos realizados por la comunidad de amara",
    "subtítulos por la comunidad de amara.org",
    "thanks for watching",
    "thank you for watching",
    "subscribe to my channel",
    "don't forget to subscribe",
    "subtitles by the amara.org community",
    "like and subscribe",
    "see you next time",
    "that's all for today",
}

# Tamaño mínimo de audio aceptable (~0.5 segundos de webm/opus a 128 kbps)
_MIN_AUDIO_BYTES = 6_000


class TranscriptionClient:
    """Cliente para transcribir audio usando Groq Whisper"""

    def __init__(self):
        """
        Inicializa el cliente de transcripción

        Raises:
            ValueError: Si no se encuentra la API key de Groq
        """
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY no está configurada. "
                "Por favor configura tu API key de Groq en el archivo .env"
            )

        self.client = Groq(api_key=api_key)
        # Groq's Whisper is already optimized for speed (LPU inference)
        # whisper-large-v3 is the best balance of speed and accuracy
        self.model = "whisper-large-v3"

        # Términos del dominio para guiar a Whisper con la ortografía correcta.
        # El prompt de Whisper espera texto ejemplo, NO notación fonética.
        self._domain_terms = [
            "VOAE", "UNAH", "UNAH-VS", "VRA", "DIPP", "PAC",
            "PASEE", "PROCAD", "PROSENE",
            "CIVU", "PAIE", "PAI-E", "PAPE", "PHUMA",
            "IAG",
            "Summa Cum Laude", "Magna Cum Laude", "Cum Laude",
        ]
        self._transcription_prompt = self._build_transcription_prompt()

    def _build_transcription_prompt(self) -> str:
        """Construye el prompt con los términos del dominio como texto ejemplo para Whisper"""
        terms = ", ".join(self._domain_terms)
        return f"Vocabulario específico: {terms}."

    def _is_hallucination(self, text: str) -> bool:
        """Detecta alucinaciones típicas de Whisper con audio corto o silencioso"""
        if not text or not text.strip():
            return True
        # Tokens especiales de Whisper que se filtran al output
        if re.search(r"<\|.*?\|>", text):
            return True
        # Frases conocidas que Whisper alucina con audio silencioso (sesgo YouTube)
        normalized = text.strip().lower().rstrip(".!¡¿?,;:")
        if normalized in _HALLUCINATION_PHRASES:
            return True
        for phrase in _HALLUCINATION_PHRASES:
            if phrase in normalized and len(normalized) < len(phrase) + 20:
                return True
        return False

    def transcribe_audio(self, audio_file_path: str, language: str = "es") -> str:
        """
        Transcribe un archivo de audio a texto

        Args:
            audio_file_path: Ruta al archivo de audio
            language: Código de idioma (default: "es" para español)

        Returns:
            Texto transcrito

        Raises:
            Exception: Si hay un error en la transcripción
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_file_path, audio_file.read()),
                    model=self.model,
                    language=language,
                    response_format="text",
                    prompt=self._transcription_prompt
                )

            if self._is_hallucination(transcription):
                return None

            return transcription

        except Exception as e:
            raise Exception(f"Error al transcribir audio: {str(e)}")

    def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.wav", language: str = "es") -> str:
        """
        Transcribe audio desde bytes

        Args:
            audio_bytes: Bytes del audio
            filename: Nombre del archivo (para el API)
            language: Código de idioma (default: "es" para español)

        Returns:
            Texto transcrito

        Raises:
            Exception: Si hay un error en la transcripción
        """
        # Rechazar blobs demasiado pequeños antes de llamar a Groq.
        # Audio < ~0.5s de webm/opus suele ser silencio y causa alucinaciones.
        if len(audio_bytes) < _MIN_AUDIO_BYTES:
            return None

        try:
            transcription = self.client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=self.model,
                language=language,
                response_format="text",
                prompt=self._transcription_prompt
            )

            print(f"[Whisper] raw result: {repr(transcription)}")

            if self._is_hallucination(transcription):
                print(f"[Whisper] detectado como alucinación, descartando")
                return None

            return transcription

        except Exception as e:
            raise Exception(f"Error al transcribir audio: {str(e)}")


if __name__ == "__main__":
    # Test básico
    print("=== Test de TranscriptionClient ===\n")

    try:
        client = TranscriptionClient()
        print(f"✓ Cliente inicializado correctamente")
        print(f"  Modelo: {client.model}")
        print(f"\nPara probar la transcripción, llama a:")
        print(f"  client.transcribe_audio('ruta/al/audio.wav')")
        print(f"  o")
        print(f"  client.transcribe_audio_bytes(audio_bytes, 'audio.wav')")

    except ValueError as e:
        print(f"✗ Error: {e}")
