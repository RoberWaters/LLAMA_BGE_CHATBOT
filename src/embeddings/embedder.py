"""
Módulo para generar embeddings con Amazon Bedrock Titan Embeddings V2
Reemplaza BAAI/bge-m3 (sentence-transformers local)
"""
import sys
import json
import boto3
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BedrockConfig, EmbeddingConfig


class Embedder:
    """
    Genera embeddings usando Amazon Titan Embeddings V2 (1024 dims, multilingüe).
    Mantiene la misma interfaz que la versión local con BGE-M3.
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or EmbeddingConfig.MODEL_NAME
        self._dim = EmbeddingConfig.EMBEDDING_DIM

        if not BedrockConfig.AWS_ACCESS_KEY or not BedrockConfig.AWS_SECRET_KEY:
            raise ValueError(
                "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env"
            )

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=BedrockConfig.AWS_REGION,
            aws_access_key_id=BedrockConfig.AWS_ACCESS_KEY,
            aws_secret_access_key=BedrockConfig.AWS_SECRET_KEY,
        )

        print(f"Embedder inicializado: {self.model_name} ({self._dim} dims) via Amazon Bedrock")

    def _embed(self, text: str) -> np.ndarray:
        """Llama a Titan Embeddings V2 y retorna un numpy array normalizado."""
        body = {
            "inputText": text,
            "dimensions": self._dim,
            "normalize": True,
        }
        response = self.client.invoke_model(
            modelId=self.model_name,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return np.array(result["embedding"], dtype="float32")

    def generate_embedding(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            raise ValueError("El texto no puede estar vacío")
        return self._embed(text)

    def generate_embeddings_batch(self, texts: list) -> np.ndarray:
        if not texts:
            raise ValueError("La lista de textos no puede estar vacía")
        return np.vstack([self._embed(t) for t in texts])

    def embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        return embedding.astype("float32").tobytes()

    @staticmethod
    def bytes_to_embedding(embedding_bytes: bytes) -> np.ndarray:
        return np.frombuffer(embedding_bytes, dtype="float32")

    def get_embedding_dimension(self) -> int:
        return self._dim

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "embedding_dimension": self._dim,
            "provider": "Amazon Bedrock",
        }


if __name__ == "__main__":
    print("=== Test del Embedder (Titan V2) ===\n")
    embedder = Embedder()

    info = embedder.get_model_info()
    print(f"Modelo: {info['model_name']}")
    print(f"Dimensiones: {info['embedding_dimension']}")
    print(f"Proveedor: {info['provider']}")

    test_text = "Este es un texto de prueba para generar embeddings"
    print(f"\nGenerando embedding para: '{test_text}'")
    embedding = embedder.generate_embedding(test_text)

    print(f"Dimensión: {embedding.shape}")
    print(f"Tipo: {embedding.dtype}")
    print(f"Primeros 5 valores: {embedding[:5]}")

    embedding_bytes = embedder.embedding_to_bytes(embedding)
    recovered = embedder.bytes_to_embedding(embedding_bytes)
    print(f"\nRecuperado correctamente: {np.allclose(embedding, recovered)}")

    print("\n=== Test batch ===")
    texts = ["Texto 1", "Texto 2", "Texto 3"]
    batch = embedder.generate_embeddings_batch(texts)
    print(f"Shape batch: {batch.shape}")

    print("\n✓ Test completado exitosamente")
