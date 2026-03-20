"""
Cliente Amazon Polly para síntesis de voz
"""
import boto3
import base64
import logging
from botocore.exceptions import ClientError, BotoCoreError
from config import PollyConfig

logger = logging.getLogger(__name__)


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
        try:
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='pcm',
                SampleRate='16000',
                VoiceId=self.voice_id,
                Engine=self.engine,
                LanguageCode=self.language_code,
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error("Polly API error [%s]: %s", error_code, e)
            if error_code == 'TextLengthExceededException':
                raise RuntimeError("El texto excede el limite de Polly (3000 caracteres).") from e
            raise RuntimeError(f"Error de Polly ({error_code}): {e.response['Error']['Message']}") from e
        except BotoCoreError as e:
            logger.error("Polly connection error: %s", e)
            raise RuntimeError("No se pudo conectar con Amazon Polly.") from e

        with response['AudioStream'] as stream:
            audio_bytes = stream.read()
        return base64.b64encode(audio_bytes).decode('utf-8')
