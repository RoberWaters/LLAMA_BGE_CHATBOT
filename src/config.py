"""
Configuracion centralizada del sistema - Amazon Bedrock
"""
import os
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# Amazon Bedrock Configuration (LLM)
# =============================================================================

class BedrockConfig:
    """Configuracion de Amazon Bedrock"""

    # Credenciales explicitas solo para desarrollo local.
    # En Lambda, dejar vacias — boto3 usa el IAM role automaticamente.
    AWS_ACCESS_KEY = os.getenv('APP_AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('APP_AWS_SECRET_ACCESS_KEY')
    AWS_REGION     = os.getenv('BEDROCK_REGION', os.getenv('AWS_REGION', 'us-east-1'))

    # Modelo LLM
    LLM_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-haiku-20241022-v1:0')

    # Knowledge Base
    KNOWLEDGE_BASE_ID = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')

    # Parametros de generacion
    DEFAULT_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))
    DEFAULT_MAX_TOKENS  = int(os.getenv('LLM_MAX_TOKENS', '2000'))


# =============================================================================
# Chatbot Configuration
# =============================================================================

class ChatbotConfig:
    """Configuracion del chatbot"""

    MAX_HISTORY = int(os.getenv('CHATBOT_MAX_HISTORY', '10'))


# =============================================================================
# API Configuration
# =============================================================================

class APIConfig:
    """Configuracion de la API FastAPI"""

    HOST = os.getenv('API_HOST', '127.0.0.1')
    PORT = int(os.getenv('API_PORT', '8000'))

    CORS_ORIGINS = os.getenv('API_CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')

    REQUEST_TIMEOUT = int(os.getenv('API_REQUEST_TIMEOUT', '30'))
    LOG_LEVEL = os.getenv('API_LOG_LEVEL', 'info')


# =============================================================================
# Amazon Polly TTS Configuration
# =============================================================================

class PollyConfig:
    """Configuracion de Amazon Polly TTS"""
    AWS_ACCESS_KEY = os.getenv('APP_AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('APP_AWS_SECRET_ACCESS_KEY')
    AWS_REGION     = os.getenv('POLLY_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    VOICE_ID       = os.getenv('POLLY_VOICE', 'Lupe')
    ENGINE         = os.getenv('POLLY_ENGINE', 'neural')
    LANGUAGE_CODE  = os.getenv('POLLY_LANGUAGE', 'es-US')


# =============================================================================
# Helper Functions
# =============================================================================

def get_config_summary() -> dict:
    """Retorna un resumen de la configuracion actual"""
    return {
        'bedrock': {
            'model': BedrockConfig.LLM_MODEL_ID,
            'knowledge_base': BedrockConfig.KNOWLEDGE_BASE_ID,
            'region': BedrockConfig.AWS_REGION,
            'max_tokens': BedrockConfig.DEFAULT_MAX_TOKENS,
        },
        'polly': {
            'voice': PollyConfig.VOICE_ID,
            'engine': PollyConfig.ENGINE,
            'language': PollyConfig.LANGUAGE_CODE,
        },
        'chatbot': {
            'max_history': ChatbotConfig.MAX_HISTORY,
        },
        'api': {
            'host': APIConfig.HOST,
            'port': APIConfig.PORT,
        }
    }


def validate_config():
    """Valida que la configuracion tenga valores validos"""
    errors = []

    if not BedrockConfig.KNOWLEDGE_BASE_ID:
        errors.append("BEDROCK_KNOWLEDGE_BASE_ID debe estar configurada")

    if errors:
        raise ValueError(f"Errores de configuracion:\n" + "\n".join(f"- {e}" for e in errors))

    return True


if __name__ == "__main__":
    print("=== Configuracion del Sistema ===\n")

    try:
        validate_config()
        print("Configuracion valida\n")

        import json
        config = get_config_summary()
        print(json.dumps(config, indent=2, ensure_ascii=False))

    except ValueError as e:
        print(f"Error: {e}")
