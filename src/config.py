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
    """Configuración del modelo de embeddings"""

    # Modelo de embeddings
    MODEL_NAME = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')

    # Dimensiones del embedding (BGE-M3)
    EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM', '1024'))

    # Device para el modelo (cpu, cuda, mps)
    DEVICE = os.getenv('EMBEDDING_DEVICE', 'cpu')


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
# LLM Configuration
# =============================================================================

class LLMConfig:
    """Configuración de LLMs"""

    # Proveedor por defecto (groq, deepseek)
    DEFAULT_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')

    # Groq Configuration
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

    # DeepSeek Configuration
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

    # Parámetros de generación
    DEFAULT_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))
    DEFAULT_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '2000'))
    MAX_TOKENS_GROQ = int(os.getenv('LLM_MAX_TOKENS_GROQ', '850'))  # Groq tiene límite más bajo


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
# Amazon Polly TTS Configuration
# =============================================================================

class PollyConfig:
    """Configuración de Amazon Polly TTS"""
    AWS_ACCESS_KEY = os.getenv('AWS_ACCES_KEY')        # Typo intencional para compatibilidad
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION     = os.getenv('AWS_REGION', 'us-east-1')
    VOICE_ID       = os.getenv('POLLY_VOICE', 'Lupe')
    ENGINE         = os.getenv('POLLY_ENGINE', 'neural')
    LANGUAGE_CODE  = os.getenv('POLLY_LANGUAGE', 'es-US')


# =============================================================================
# Simli Avatar Configuration
# =============================================================================

class SimliConfig:
    """Configuración del avatar en tiempo real con Simli"""
    API_KEY = os.getenv("SIMLI_API", "")
    FACE_ID  = os.getenv("FACE_ID_SIMLI", "")


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
            'groq_model': LLMConfig.GROQ_MODEL,
            'deepseek_model': LLMConfig.DEEPSEEK_MODEL,
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

    # Validar API keys (al menos una debe existir)
    if not LLMConfig.GROQ_API_KEY and not LLMConfig.DEEPSEEK_API_KEY:
        errors.append("Al menos GROQ_API_KEY o DEEPSEEK_API_KEY debe estar configurada")

    # Validar proveedor por defecto
    if LLMConfig.DEFAULT_PROVIDER not in ['groq', 'deepseek']:
        errors.append(f"LLM_PROVIDER debe ser 'groq' o 'deepseek', actual: {LLMConfig.DEFAULT_PROVIDER}")

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
