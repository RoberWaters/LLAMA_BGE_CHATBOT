"""
Cliente Amazon Polly para síntesis de voz
"""
import boto3
import base64
from config import PollyConfig


class PollyClient:
    def __init__(self):
        if not PollyConfig.AWS_ACCESS_KEY or not PollyConfig.AWS_SECRET_KEY:
            raise ValueError(
                "AWS_ACCES_KEY y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env"
            )
        self.client = boto3.client(
            'polly',
            region_name=PollyConfig.AWS_REGION,
            aws_access_key_id=PollyConfig.AWS_ACCESS_KEY,
            aws_secret_access_key=PollyConfig.AWS_SECRET_KEY,
        )
        self.voice_id      = PollyConfig.VOICE_ID
        self.engine        = PollyConfig.ENGINE
        self.language_code = PollyConfig.LANGUAGE_CODE

    def synthesize(self, text: str) -> str:
        """
        Sintetiza texto a audio PCM con Amazon Polly.
        Formato requerido por Simli: PCM16, 16000 Hz, mono.

        Args:
            text: Texto a sintetizar (ya preprocesado, sin markdown)

        Returns:
            Audio PCM codificado en base64
        """
        response = self.client.synthesize_speech(
            Text=text,
            OutputFormat='pcm',
            SampleRate='16000',
            VoiceId=self.voice_id,
            Engine=self.engine,
            LanguageCode=self.language_code,
        )
        audio_bytes = response['AudioStream'].read()
        return base64.b64encode(audio_bytes).decode('utf-8')
