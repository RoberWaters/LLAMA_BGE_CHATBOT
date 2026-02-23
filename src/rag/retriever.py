"""
Módulo para recuperación de documentos relevantes usando ChromaDB HNSW
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple
from database.repository import DocumentRepository
from database.chroma_vector_store import ChromaVectorStore
from embeddings.embedder import Embedder
from config import RetrievalConfig


class DocumentRetriever:
    """
    Clase para recuperar documentos relevantes usando búsqueda semántica

    Utiliza ChromaDB con HNSW (Hierarchical Navigable Small World) para
    búsqueda aproximada de vecinos más cercanos, mucho más eficiente que
    búsqueda manual exhaustiva.
    """

    def __init__(self, repository: DocumentRepository = None, embedder: Embedder = None, storage: ChromaVectorStore = None):
        """
        Inicializa el retriever

        Args:
            repository: Repositorio de documentos (opcional)
            embedder: Generador de embeddings (opcional)
            storage: ChromaVectorStore para búsqueda directa (opcional)
        """
        self.repository = repository if repository else DocumentRepository()
        self.embedder = embedder if embedder else Embedder()
        self.storage = storage if storage else (repository.storage if repository else ChromaVectorStore())

    def retrieve_relevant_documents(
        self,
        query: str,
        top_k: int = None
    ) -> List[Tuple[str, str, float]]:
        """
        Recupera los documentos más relevantes para una consulta usando ChromaDB HNSW

        Este método usa el índice HNSW de ChromaDB para búsqueda aproximada
        de vecinos más cercanos, lo cual es mucho más eficiente que calcular
        similitud manualmente con todos los documentos.

        Args:
            query: Pregunta del usuario
            top_k: Número de documentos a recuperar (None = usar config default)

        Returns:
            Lista de tuplas (filename, content, similarity_score)
            ordenadas por relevancia (mayor a menor)
        """
        if top_k is None:
            top_k = RetrievalConfig.DEFAULT_TOP_K

        # Generar embedding de la consulta
        print(f"Generando embedding para la consulta...")
        query_embedding = self.embedder.generate_embedding(query)

        # Buscar usando ChromaDB HNSW (mucho más eficiente)
        print(f"Buscando top-{top_k} documentos usando ChromaDB HNSW...")
        results = self.storage.search_similar(query_embedding, top_k=top_k)

        if not results:
            print("Advertencia: No hay documentos en la base de datos")
            return []

        # Convertir formato de ChromaDB a formato esperado
        # ChromaDB retorna: (id, filename, content, similarity)
        # Nosotros retornamos: (filename, content, similarity)
        top_documents = [
            (filename, content, similarity)
            for _, filename, content, similarity in results
        ]

        print(f"\nTop {top_k} documentos más relevantes:")
        for i, (filename, _, score) in enumerate(top_documents, 1):
            print(f"{i}. {filename} (similitud: {score:.4f})")

        return top_documents

    def retrieve_with_threshold(
        self,
        query: str,
        threshold: float = None,
        max_documents: int = None
    ) -> List[Tuple[str, str, float]]:
        """
        Recupera documentos que superen un umbral de similitud usando ChromaDB HNSW

        Este método primero recupera más documentos de los necesarios usando HNSW,
        luego filtra por umbral. Más eficiente que calcular similitud con todos.

        Args:
            query: Pregunta del usuario
            threshold: Umbral mínimo de similitud (None = usar config default)
            max_documents: Máximo número de documentos a retornar (None = usar config default)

        Returns:
            Lista de tuplas (filename, content, similarity_score)
        """
        if threshold is None:
            threshold = RetrievalConfig.MIN_SIMILARITY_THRESHOLD

        if max_documents is None:
            max_documents = RetrievalConfig.MAX_DOCUMENTS_WITH_THRESHOLD

        # Generar embedding de la consulta
        query_embedding = self.embedder.generate_embedding(query)

        # Recuperar más documentos de los necesarios para compensar filtrado
        # (recuperamos el doble del máximo para tener suficientes después del filtro)
        initial_k = min(max_documents * 2, self.storage.count_documents())

        if initial_k == 0:
            return []

        # Usar ChromaDB HNSW para búsqueda inicial
        results = self.storage.search_similar(query_embedding, top_k=initial_k)

        # Filtrar por umbral
        relevant_documents = [
            (filename, content, similarity)
            for _, filename, content, similarity in results
            if similarity >= threshold
        ]

        # Limitar a max_documents
        return relevant_documents[:max_documents]


if __name__ == "__main__":
    # Test del retriever
    try:
        retriever = DocumentRetriever()

        test_query = "¿Cómo funciona el sistema?"

        print(f"Buscando documentos relevantes para: '{test_query}'\n")
        results = retriever.retrieve_relevant_documents(test_query, top_k=3)

        print("\n--- Resultados ---")
        for filename, content, score in results:
            print(f"\nDocumento: {filename}")
            print(f"Similitud: {score:.4f}")
            print(f"Contenido (primeros 200 chars): {content[:200]}...")

    except Exception as e:
        print(f"Error: {str(e)}")
