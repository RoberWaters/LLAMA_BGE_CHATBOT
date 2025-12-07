"""
Módulo para manejar el sistema FAQ híbrido con umbrales dobles (90%/80%)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple, Optional, Dict
from rag.retriever import DocumentRetriever
from database.repository import DocumentRepository
from embeddings.embedder import Embedder


class FAQHandler:
    """
    Maneja la lógica de FAQs con sistema de umbrales dobles:
    - >= 90%: Match fuerte (solo FAQs)
    - 80-89%: Match medio (FAQs + documentos)
    - < 80%: Sin match (solo documentos - flujo original)
    """

    # Umbrales de similitud
    HIGH_THRESHOLD = 0.75  # Match fuerte
    MEDIUM_THRESHOLD = 0.65  # Match medio

    def __init__(self, repository: DocumentRepository, embedder: Embedder):
        """
        Inicializa el handler de FAQs

        Args:
            repository: Repositorio de documentos
            embedder: Generador de embeddings
        """
        self.retriever = DocumentRetriever(repository, embedder)
        self.repository = repository

    def classify_query(self, query: str, top_k: int = 5) -> Dict:
        """
        Clasifica la consulta según similitud con FAQs

        Args:
            query: Pregunta del usuario
            top_k: Número máximo de FAQs a recuperar

        Returns:
            Diccionario con:
            - match_type: 'high' (>=90%), 'medium' (80-89%), 'low' (<80%)
            - faq_results: Lista de FAQs relevantes
            - best_similarity: Mejor score de similitud
        """
        # Buscar en TODOS los documentos primero
        all_results = self.retriever.retrieve_with_threshold(
            query=query,
            threshold=self.MEDIUM_THRESHOLD,
            max_documents=top_k * 2  # Buscar más para tener suficientes FAQs
        )

        # Filtrar SOLO los que están en carpeta faq/
        faq_results = [
            (filename, content, score)
            for filename, content, score in all_results
            if filename.startswith('faq/')
        ]

        # Limitar a top_k
        faq_results = faq_results[:top_k]

        if not faq_results:
            return {
                'match_type': 'low',
                'faq_results': [],
                'best_similarity': 0.0
            }

        best_similarity = faq_results[0][2]  # (filename, content, similarity)

        # Clasificar según umbral
        if best_similarity >= self.HIGH_THRESHOLD:
            match_type = 'high'
        elif best_similarity >= self.MEDIUM_THRESHOLD:
            match_type = 'medium'
        else:
            match_type = 'low'

        return {
            'match_type': match_type,
            'faq_results': faq_results,
            'best_similarity': best_similarity
        }

    def get_context_for_llm(
        self,
        query: str,
        match_type: str,
        faq_results: List[Tuple[str, str, float]],
        doc_results: Optional[List[Tuple[str, str, float]]] = None
    ) -> Tuple[List[str], str]:
        """
        Prepara el contexto apropiado para el LLM según el tipo de match

        Args:
            query: Pregunta del usuario
            match_type: Tipo de match ('high', 'medium', 'low')
            faq_results: Resultados de FAQs
            doc_results: Resultados de documentos (opcional)

        Returns:
            Tupla (context_documents, context_type)
            - context_documents: Lista de strings con el contexto
            - context_type: 'faq_only', 'faq_and_docs', 'docs_only'
        """
        if match_type == 'high':
            # Match fuerte: Solo top-3 FAQs
            context = [content for _, content, _ in faq_results[:3]]
            return context, 'faq_only'

        elif match_type == 'medium':
            # Match medio: Top-2 FAQs + Top-2 Docs
            faq_context = [content for _, content, _ in faq_results[:2]]

            if doc_results:
                doc_context = [content for _, content, _ in doc_results[:2]]
                context = faq_context + doc_context
            else:
                context = faq_context

            return context, 'faq_and_docs'

        else:
            # Match bajo: Solo documentos
            if doc_results:
                context = [content for _, content, _ in doc_results]
            else:
                context = []
            return context, 'docs_only'

    def format_faq_for_display(
        self,
        faq_results: List[Tuple[str, str, float]]
    ) -> str:
        """
        Formatea FAQs para mostrar al usuario (debugging)

        Args:
            faq_results: Lista de (filename, content, similarity)

        Returns:
            String formateado
        """
        if not faq_results:
            return "No se encontraron FAQs relevantes"

        output = "\n📚 FAQs consultadas:\n"
        for i, (filename, content, score) in enumerate(faq_results[:3], 1):
            output += f"  {i}. {filename} (similitud: {score:.2%})\n"

        return output

    def should_use_faq(self, query: str) -> bool:
        """
        Determina si se debe buscar en FAQs para esta consulta

        Args:
            query: Pregunta del usuario

        Returns:
            True si debe buscar en FAQs
        """
        # Por ahora, siempre busca en FAQs
        # Podrías agregar lógica para detectar preguntas vs comandos
        query_lower = query.lower().strip()

        # Ignorar comandos especiales
        if query_lower in ['salir', 'exit', 'limpiar', 'stats', 'ayuda']:
            return False

        return True

    def get_temperature_for_context(self, context_type: str) -> float:
        """
        Obtiene la temperatura apropiada según el tipo de contexto

        Args:
            context_type: 'faq_only', 'faq_and_docs', 'docs_only'

        Returns:
            Valor de temperature (0.0-1.0)
        """
        temperatures = {
            'faq_only': 0.1,      # Muy determinista para FAQs exactos
            'faq_and_docs': 0.2,  # Poco creativo para híbrido
            'docs_only': 0.3      # Ligeramente más flexible para docs
        }

        return temperatures.get(context_type, 0.3)


if __name__ == "__main__":
    # Test del FAQ handler
    try:
        from database.chroma_vector_store import ChromaVectorStore

        print("=== Test del FAQ Handler ===\n")

        # Inicializar componentes
        storage = ChromaVectorStore()
        repository = DocumentRepository(storage)
        embedder = Embedder()
        faq_handler = FAQHandler(repository, embedder)

        # Test de clasificación
        test_queries = [
            "¿Cómo solicito una beca?",
            "¿Cuál es el proceso de inscripción?",
            "¿Qué información general tienes?"
        ]

        for query in test_queries:
            print(f"Query: {query}")
            classification = faq_handler.classify_query(query)
            print(f"  Match type: {classification['match_type']}")
            print(f"  Best similarity: {classification['best_similarity']:.2%}")
            print()

    except Exception as e:
        print(f"Error en test: {str(e)}")
        import traceback
        traceback.print_exc()
