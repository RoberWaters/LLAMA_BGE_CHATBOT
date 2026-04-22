"""
Cliente Amazon Polly para síntesis de voz
"""
import boto3
import base64
from config import PollyConfig


class PollyClient:
    def __init__(self):
        client_kwargs = {'region_name': PollyConfig.AWS_REGION}
        if PollyConfig.AWS_ACCESS_KEY and PollyConfig.AWS_SECRET_KEY:
            client_kwargs['aws_access_key_id'] = PollyConfig.AWS_ACCESS_KEY
            client_kwargs['aws_secret_access_key'] = PollyConfig.AWS_SECRET_KEY
        self.client = boto3.client('polly', **client_kwargs)
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
