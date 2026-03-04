"""
Configuración centralizada del sistema RAG
"""
import os
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# FAQ System Configuration
# =============================================================================

class FAQConfig:
    """Configuración del sistema FAQ híbrido"""

    # Umbrales de similitud para clasificación de queries
    HIGH_THRESHOLD = float(os.getenv('FAQ_HIGH_THRESHOLD', '0.75'))      # >= 75%: Match fuerte
    MEDIUM_THRESHOLD = float(os.getenv('FAQ_MEDIUM_THRESHOLD', '0.65'))  # >= 65%: Match medio

    # Número de FAQs a recuperar
    TOP_K_FAQS = int(os.getenv('FAQ_TOP_K', '5'))

    # Temperaturas según tipo de contexto
    TEMP_FAQ_ONLY = float(os.getenv('FAQ_TEMP_FAQ_ONLY', '0.1'))        # Muy determinista
    TEMP_FAQ_AND_DOCS = float(os.getenv('FAQ_TEMP_HYBRID', '0.2'))      # Poco creativo
    TEMP_DOCS_ONLY = float(os.getenv('FAQ_TEMP_DOCS_ONLY', '0.3'))      # Ligeramente flexible

    # Número de documentos por tipo de match
    NUM_FAQS_HIGH_MATCH = int(os.getenv('FAQ_NUM_HIGH', '3'))           # Top-3 FAQs para match fuerte
    NUM_FAQS_MEDIUM_MATCH = int(os.getenv('FAQ_NUM_MEDIUM', '2'))       # Top-2 FAQs para match medio
    NUM_DOCS_MEDIUM_MATCH = int(os.getenv('FAQ_DOCS_MEDIUM', '2'))      # Top-2 Docs para match medio


# =============================================================================
# Retrieval Configuration
# =============================================================================

class RetrievalConfig:
    """Configuración del sistema de recuperación de documentos"""

    # Número de documentos a recuperar por defecto
    DEFAULT_TOP_K = int(os.getenv('RETRIEVAL_TOP_K', '3'))

    # Umbral mínimo de similitud para considerar un documento relevante
    MIN_SIMILARITY_THRESHOLD = float(os.getenv('RETRIEVAL_MIN_SIMILARITY', '0.3'))

    # Máximo de documentos a recuperar con threshold
    MAX_DOCUMENTS_WITH_THRESHOLD = int(os.getenv('RETRIEVAL_MAX_DOCS', '10'))


# =============================================================================
# Embedding Configuration
# =============================================================================

class EmbeddingConfig:
    """Configuración del modelo de embeddings (Amazon Titan Embeddings V2)"""

    # Modelo de embeddings en Bedrock
    MODEL_NAME = os.getenv('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v2:0')

    # Dimensiones del embedding (Titan V2 soporta 256 / 512 / 1024)
    EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM', '1024'))


# =============================================================================
# ChromaDB Configuration
# =============================================================================

class ChromaDBConfig:
    """Configuración de ChromaDB"""

    # Path de almacenamiento
    STORAGE_PATH = os.getenv('CHROMA_STORAGE_PATH', 'data/chroma')

    # Nombre de la colección
    COLLECTION_NAME = os.getenv('CHROMA_COLLECTION', 'documents')

    # Métrica de similitud (cosine, l2, ip)
    SIMILARITY_METRIC = os.getenv('CHROMA_SIMILARITY', 'cosine')


# =============================================================================
# Amazon Bedrock Configuration (LLM + Embeddings + Transcribe)
# =============================================================================

class BedrockConfig:
    """Configuración de Amazon Bedrock y servicios AWS"""

    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION     = os.getenv('AWS_REGION', 'us-east-1')

    # Modelo LLM (Claude 3.5 Haiku — rápido y económico)
    LLM_MODEL_ID = os.getenv('BEDROCK_LLM_MODEL', 'us.anthropic.claude-3-5-haiku-20241022-v1:0')

    # Modelo de embeddings (Titan Embeddings V2 — 1024 dims, multilingüe)
    EMBEDDING_MODEL_ID = os.getenv('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v2:0')

    # Parámetros de generación
    DEFAULT_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))
    DEFAULT_MAX_TOKENS  = int(os.getenv('LLM_MAX_TOKENS', '2000'))


# Alias para compatibilidad con código existente
class LLMConfig:
    """Alias de BedrockConfig — mantenido para compatibilidad"""
    DEFAULT_PROVIDER = 'bedrock'


# =============================================================================
# Document Ingestion Configuration
# =============================================================================

class IngestionConfig:
    """Configuración de ingestion de documentos"""

    # Path de documentos
    DOCS_FOLDER = os.getenv('DOCS_FOLDER', 'data/docs')

    # FAQ subdirectory
    FAQ_FOLDER = os.getenv('FAQ_FOLDER', 'data/docs/faq')

    # Configuración de chunking
    ENABLE_CHUNKING = os.getenv('ENABLE_CHUNKING', 'false').lower() == 'true'
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '200'))

    # Extensiones de archivo permitidas
    ALLOWED_EXTENSIONS = ['.md', '.txt']


# =============================================================================
# Chatbot Configuration
# =============================================================================

class ChatbotConfig:
    """Configuración del chatbot"""

    # Tamaño del historial de conversación
    MAX_HISTORY = int(os.getenv('CHATBOT_MAX_HISTORY', '10'))

    # Habilitar/deshabilitar sistema FAQ
    ENABLE_FAQ = os.getenv('CHATBOT_ENABLE_FAQ', 'true').lower() == 'true'

    # Comandos especiales que no usan FAQ
    SPECIAL_COMMANDS = ['salir', 'exit', 'limpiar', 'stats', 'ayuda', 'help']


# =============================================================================
# API Configuration
# =============================================================================

class APIConfig:
    """Configuración de la API FastAPI"""

    # Host y puerto
    HOST = os.getenv('API_HOST', '127.0.0.1')
    PORT = int(os.getenv('API_PORT', '8000'))

    # CORS origins permitidos
    CORS_ORIGINS = os.getenv('API_CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')

    # Timeout para requests
    REQUEST_TIMEOUT = int(os.getenv('API_REQUEST_TIMEOUT', '30'))

    # Logging level
    LOG_LEVEL = os.getenv('API_LOG_LEVEL', 'info')


# =============================================================================
# Amazon S3 Configuration (docs + ChromaDB sync)
# =============================================================================

class S3Config:
    """Configuración de Amazon S3 para documentos y sincronización de ChromaDB"""
    BUCKET_NAME    = os.getenv('S3_BUCKET_NAME', '')
    DOCS_PREFIX    = os.getenv('S3_DOCS_PREFIX', 'docs/')
    CHROMA_PREFIX  = os.getenv('S3_CHROMA_PREFIX', 'chroma/')
    # Reutiliza credenciales de BedrockConfig
    AWS_REGION     = os.getenv('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')


# =============================================================================
# Amazon Polly TTS Configuration
# =============================================================================

class PollyConfig:
    """Configuración de Amazon Polly TTS"""
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION     = os.getenv('AWS_REGION', 'us-east-1')
    VOICE_ID       = os.getenv('POLLY_VOICE', 'Lupe')
    ENGINE         = os.getenv('POLLY_ENGINE', 'neural')
    LANGUAGE_CODE  = os.getenv('POLLY_LANGUAGE', 'es-US')


# =============================================================================
# Helper Functions
# =============================================================================

def get_config_summary() -> dict:
    """
    Retorna un resumen de la configuración actual

    Returns:
        Diccionario con configuración clave
    """
    return {
        'faq': {
            'high_threshold': FAQConfig.HIGH_THRESHOLD,
            'medium_threshold': FAQConfig.MEDIUM_THRESHOLD,
            'top_k_faqs': FAQConfig.TOP_K_FAQS,
        },
        'retrieval': {
            'default_top_k': RetrievalConfig.DEFAULT_TOP_K,
            'min_similarity': RetrievalConfig.MIN_SIMILARITY_THRESHOLD,
        },
        'embedding': {
            'model': EmbeddingConfig.MODEL_NAME,
            'dimensions': EmbeddingConfig.EMBEDDING_DIM,
            'device': EmbeddingConfig.DEVICE,
        },
        'llm': {
            'default_provider': LLMConfig.DEFAULT_PROVIDER,
            'model': BedrockConfig.LLM_MODEL_ID,
        },
        'chromadb': {
            'storage_path': ChromaDBConfig.STORAGE_PATH,
            'collection': ChromaDBConfig.COLLECTION_NAME,
            'similarity_metric': ChromaDBConfig.SIMILARITY_METRIC,
        },
        'chatbot': {
            'max_history': ChatbotConfig.MAX_HISTORY,
            'enable_faq': ChatbotConfig.ENABLE_FAQ,
        }
    }


def validate_config():
    """Valida que la configuración tenga valores válidos"""
    errors = []

    # Validar umbrales FAQ
    if not (0 <= FAQConfig.HIGH_THRESHOLD <= 1):
        errors.append(f"FAQ_HIGH_THRESHOLD debe estar entre 0 y 1, actual: {FAQConfig.HIGH_THRESHOLD}")

    if not (0 <= FAQConfig.MEDIUM_THRESHOLD <= 1):
        errors.append(f"FAQ_MEDIUM_THRESHOLD debe estar entre 0 y 1, actual: {FAQConfig.MEDIUM_THRESHOLD}")

    if FAQConfig.MEDIUM_THRESHOLD >= FAQConfig.HIGH_THRESHOLD:
        errors.append(f"FAQ_MEDIUM_THRESHOLD debe ser menor que FAQ_HIGH_THRESHOLD")

    # Validar credenciales AWS
    if not BedrockConfig.AWS_ACCESS_KEY or not BedrockConfig.AWS_SECRET_KEY:
        errors.append("AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben estar configuradas")

    if errors:
        raise ValueError(f"Errores de configuración:\n" + "\n".join(f"- {e}" for e in errors))

    return True


if __name__ == "__main__":
    # Test de configuración
    print("=== Configuración del Sistema RAG ===\n")

    try:
        validate_config()
        print("✓ Configuración válida\n")

        import json
        config = get_config_summary()
        print(json.dumps(config, indent=2, ensure_ascii=False))

    except ValueError as e:
        print(f"✗ {e}")
