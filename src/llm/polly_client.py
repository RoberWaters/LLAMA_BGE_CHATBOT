"""
Cliente Amazon Polly para síntesis de voz
"""
import json
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
        Sintetiza texto a audio MP3 con Amazon Polly.

        Args:
            text: Texto a sintetizar (ya preprocesado, sin markdown)

        Returns:
            Audio MP3 codificado en base64
        """
        response = self.client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=self.voice_id,
            Engine=self.engine,
            LanguageCode=self.language_code,
        )
        audio_bytes = response['AudioStream'].read()
        return base64.b64encode(audio_bytes).decode('utf-8')

    def synthesize_with_visemes(self, text: str) -> dict:
        """
        Sintetiza texto a audio MP3 y obtiene visemas de sincronización labial.

        Realiza dos llamadas a Polly: una para el audio MP3 y otra para los
        speech marks de tipo visema.

        Returns:
            {"audio_base64": str, "visemes": [{"time": int, "value": str}]}
        """
        # Llamada 1: audio MP3
        audio_resp = self.client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=self.voice_id,
            Engine=self.engine,
            LanguageCode=self.language_code,
        )
        audio_b64 = base64.b64encode(audio_resp['AudioStream'].read()).decode('utf-8')

        # Llamada 2: speech marks (visemas)
        marks_resp = self.client.synthesize_speech(
            Text=text,
            OutputFormat='json',
            SpeechMarkTypes=['viseme'],
            VoiceId=self.voice_id,
            Engine=self.engine,
            LanguageCode=self.language_code,
        )
        marks_raw = marks_resp['AudioStream'].read().decode('utf-8')
        visemes = []
        for line in marks_raw.strip().split('\n'):
            if line.strip():
                mark = json.loads(line)
                visemes.append({"time": mark["time"], "value": mark["value"]})

        return {"audio_base64": audio_b64, "visemes": visemes}
