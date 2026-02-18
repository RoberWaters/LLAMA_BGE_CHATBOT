"""
Cliente para síntesis de voz usando Amazon Polly
"""
import os
import json
import boto3
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()


# Mapeo de visemas de Polly a nombres de Oculus Viseme (para blend shapes del avatar)
# TalkingHead usa estos como 'viseme_' + nombre → e.g. 'viseme_PP', 'viseme_aa'
POLLY_TO_OCULUS_VISEME = {
    'sil': 'sil',
    'p': 'PP',
    'f': 'FF',
    'T': 'TH',
    't': 'DD',
    'k': 'kk',
    'S': 'CH',
    's': 'SS',
    'n': 'nn',
    'r': 'RR',
    'a': 'aa',
    'e': 'E',
    'i': 'I',
    'o': 'O',
    'u': 'U',
    '@': 'E',
    'E': 'E',
    'O': 'O',
}


class PollyClient:
    """Cliente para sintetizar voz usando Amazon Polly con datos de visemas"""

    def __init__(self):
        """
        Inicializa el cliente de Amazon Polly

        Raises:
            ValueError: Si no se encuentran las credenciales AWS
        """
        # Usar el nombre de variable con typo para compatibilidad con .env existente
        access_key = os.getenv('AWS_ACCES_KEY')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION', 'us-east-1')

        if not access_key or not secret_key:
            raise ValueError(
                "AWS_ACCES_KEY y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env "
                "para usar Amazon Polly TTS"
            )

        self.client = boto3.client(
            'polly',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        self.voice_id = os.getenv('POLLY_VOICE_ID', 'Lupe')
        self.language_code = os.getenv('POLLY_LANGUAGE_CODE', 'es-US')
        self.engine = os.getenv('POLLY_ENGINE', 'neural')
        self.max_text_length = int(os.getenv('POLLY_MAX_TEXT_LENGTH', '3000'))

    def synthesize(self, text: str) -> dict:
        """
        Sintetiza texto a voz y obtiene datos de speech marks (visemas y palabras)

        Args:
            text: Texto a sintetizar

        Returns:
            Diccionario con:
                - audio_bytes: bytes del audio MP3
                - words: lista de palabras
                - wtimes: tiempos de inicio de cada palabra (ms)
                - wdurations: duración de cada palabra (ms)
                - visemes: lista de IDs de visemas Oculus
                - vtimes: tiempos de inicio de cada visema (ms)
                - vdurations: duración de cada visema (ms)

        Raises:
            Exception: Si hay un error en la síntesis
        """
        # Truncar texto si excede el límite
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length]

        try:
            # Llamadas paralelas a Polly: audio MP3 + speech marks al mismo tiempo
            def fetch_audio():
                resp = self.client.synthesize_speech(
                    Text=text,
                    OutputFormat='mp3',
                    VoiceId=self.voice_id,
                    LanguageCode=self.language_code,
                    Engine=self.engine
                )
                return resp['AudioStream'].read()

            def fetch_marks():
                resp = self.client.synthesize_speech(
                    Text=text,
                    OutputFormat='json',
                    VoiceId=self.voice_id,
                    LanguageCode=self.language_code,
                    Engine=self.engine,
                    SpeechMarkTypes=['word', 'viseme']
                )
                return resp['AudioStream'].read().decode('utf-8')

            with ThreadPoolExecutor(max_workers=2) as executor:
                audio_future = executor.submit(fetch_audio)
                marks_future = executor.submit(fetch_marks)
                audio_bytes = audio_future.result()
                marks_raw = marks_future.result()

            # Parsear speech marks (una línea JSON por marca)
            words = []
            wtimes = []
            visemes = []
            vtimes = []

            for line in marks_raw.strip().split('\n'):
                if not line.strip():
                    continue
                mark = json.loads(line)

                if mark['type'] == 'word':
                    words.append(mark['value'])
                    wtimes.append(mark['time'])
                elif mark['type'] == 'viseme':
                    oculus_name = POLLY_TO_OCULUS_VISEME.get(mark['value'], 'sil')
                    visemes.append(oculus_name)
                    vtimes.append(mark['time'])

            # Calcular duraciones como delta entre timestamps consecutivos
            wdurations = self._compute_durations(wtimes)
            vdurations = self._compute_durations(vtimes)

            return {
                'audio_bytes': audio_bytes,
                'words': words,
                'wtimes': wtimes,
                'wdurations': wdurations,
                'visemes': visemes,
                'vtimes': vtimes,
                'vdurations': vdurations
            }

        except Exception as e:
            raise Exception(f"Error al sintetizar voz con Polly: {str(e)}")

    def _compute_durations(self, times: list) -> list:
        """Calcula duraciones como delta entre timestamps consecutivos"""
        if not times:
            return []

        durations = []
        for i in range(len(times) - 1):
            durations.append(times[i + 1] - times[i])

        # La última duración se estima como la duración promedio o un valor por defecto
        if durations:
            durations.append(sum(durations) // len(durations))
        else:
            durations.append(100)  # 100ms por defecto

        return durations


if __name__ == "__main__":
    # Test básico
    print("=== Test de PollyClient ===\n")

    try:
        client = PollyClient()
        print(f"✓ Cliente inicializado correctamente")
        print(f"  Voz: {client.voice_id}")
        print(f"  Idioma: {client.language_code}")
        print(f"  Engine: {client.engine}")

        # Test de síntesis
        print("\nSintetizando texto de prueba...")
        result = client.synthesize("Hola, bienvenido a la VOAE de la UNAH")

        print(f"\n✓ Síntesis exitosa:")
        print(f"  Audio: {len(result['audio_bytes'])} bytes")
        print(f"  Palabras: {result['words']}")
        print(f"  Tiempos palabras: {result['wtimes']}")
        print(f"  Duraciones palabras: {result['wdurations']}")
        print(f"  Visemas: {len(result['visemes'])} visemas")
        print(f"  Tiempos visemas: {result['vtimes'][:10]}...")
        print(f"  Duraciones visemas: {result['vdurations'][:10]}...")

    except ValueError as e:
        print(f"✗ Error de configuración: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
