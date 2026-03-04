"""
Pipeline RAG completo: ingestion de documentos y generación de respuestas
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from typing import List, Optional
from embeddings.embedder import Embedder
from database.chroma_vector_store import ChromaVectorStore
from database.repository import DocumentRepository
from ingestion.ingest_docs import DocumentIngestion
from llm.bedrock_client import BedrockClient
from rag.retriever import DocumentRetriever
from rag.faq_handler import FAQHandler
from config import RetrievalConfig, S3Config, ChromaDBConfig
from database import s3_sync


class RAGPipeline:
    """Pipeline completo para el sistema RAG"""

    def __init__(self, s3_bucket: str = None, s3_prefix: str = None, llm_provider: str = "bedrock"):
        """
        Inicializa el pipeline RAG con ChromaDB.

        Args:
            s3_bucket: Nombre del bucket S3 (default: S3Config.BUCKET_NAME)
            s3_prefix: Prefijo S3 para documentos (default: S3Config.DOCS_PREFIX)
            llm_provider: Proveedor de LLM ("bedrock")
        """
        print("Inicializando pipeline RAG...")

        self.s3_bucket = s3_bucket if s3_bucket is not None else S3Config.BUCKET_NAME
        self.s3_prefix = s3_prefix if s3_prefix is not None else S3Config.DOCS_PREFIX

        # Descargar ChromaDB desde S3 si es necesario (antes de inicializar ChromaVectorStore)
        if self.s3_bucket:
            s3_sync.download_chroma(self.s3_bucket, S3Config.CHROMA_PREFIX, ChromaDBConfig.STORAGE_PATH)

        # Inicializar componentes
        self.embedder = Embedder()
        self.storage = ChromaVectorStore()
        self.storage_type = "chroma"
        print("[ChromaDB] Usando ChromaDB para almacenamiento vectorial")

        self.repository = DocumentRepository(self.storage)
        self.ingestion = DocumentIngestion(s3_bucket=self.s3_bucket, s3_prefix=self.s3_prefix)
        self.retriever = DocumentRetriever(self.repository, self.embedder, self.storage)
        self.faq_handler = FAQHandler(self.repository, self.embedder)

        # Inicializar LLM
        self.llm_provider = llm_provider.lower()
        if self.llm_provider == "bedrock":
            self.llm_client = BedrockClient()
            print("[Bedrock] Usando Amazon Bedrock (Claude 3.5 Haiku)")
        else:
            raise ValueError(f"LLM provider no soportado: {llm_provider}. Usa 'bedrock'")

        print("Pipeline RAG inicializado exitosamente\n")

    def ingest_documents(self, chunk_documents: bool = False, skip_existing: bool = True):
        """
        Procesa e ingiere documentos en la base de datos

        Args:
            chunk_documents: Si es True, divide los documentos en chunks
            skip_existing: Si es True, no vuelve a procesar documentos ya existentes
        """
        print("=" * 60)
        print("INICIANDO INGESTION DE DOCUMENTOS")
        print("=" * 60)

        # Cargar y procesar documentos
        documents = self.ingestion.process_documents(chunk_documents=chunk_documents)

        if not documents:
            print("No hay documentos para procesar")
            return

        # Procesar cada documento
        processed_count = 0
        skipped_count = 0

        for filename, content in documents:
            # Verificar si ya existe
            if skip_existing and self.repository.document_exists(filename):
                print(f"Saltando '{filename}' (ya existe)")
                skipped_count += 1
                continue

            try:
                # Generar embedding
                print(f"\nProcesando: {filename}")
                embedding = self.embedder.generate_embedding(content)

                # Convertir a bytes
                embedding_bytes = self.embedder.embedding_to_bytes(embedding)

                # Guardar en base de datos
                self.repository.insert_document(filename, content, embedding_bytes)
                processed_count += 1

            except Exception as e:
                print(f"ERROR: Error procesando {filename}: {str(e)}")
                continue

        print("\n" + "=" * 60)
        print(f"INGESTION COMPLETADA")
        print(f"Documentos procesados: {processed_count}")
        print(f"Documentos saltados: {skipped_count}")
        print(f"Total en base de datos: {self.repository.count_documents()}")
        print("=" * 60)

        # Subir ChromaDB actualizado a S3
        if self.s3_bucket:
            s3_sync.upload_chroma(ChromaDBConfig.STORAGE_PATH, self.s3_bucket, S3Config.CHROMA_PREFIX)

    def query_with_faq(
        self,
        question: str,
        top_k: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        enable_faq: bool = True,
        conversation_history: list = None
    ) -> dict:
        """
        Realiza una consulta con sistema FAQ híbrido (umbrales 75%/65%)

        Args:
            question: Pregunta del usuario
            top_k: Número de documentos relevantes a recuperar
            temperature: Temperatura base (se ajusta según contexto)
            max_tokens: Máximo de tokens en la respuesta
            enable_faq: Si es True, busca en FAQs primero
            conversation_history: Historial de conversación como lista de tuplas (user_msg, assistant_msg)

        Returns:
            Diccionario con la respuesta, metadatos y tipo de match
        """
        print("=" * 60)
        print("PROCESANDO CONSULTA CON SISTEMA FAQ HÍBRIDO")
        print("=" * 60)
        print(f"Pregunta: {question}\n")

        # Enriquecer la query solo si parece un seguimiento de la conversación anterior.
        # Enriquecer siempre añade ruido a preguntas independientes y perjudica la recuperación.
        # Indicadores de seguimiento: pregunta corta (≤6 palabras) o inicia con pronombre/preposición.
        _FOLLOW_UP_STARTERS = frozenset({
            "y", "pero", "entonces", "también", "además",
            "ese", "esa", "eso", "esto", "este", "estos", "estas",
            "aquel", "aquella", "aquello", "ahí", "allí", "allá",
            "cuándo", "cuando", "cómo", "como", "dónde", "donde",
            "en", "para", "a", "de", "con", "al", "del",
        })
        search_query = question
        if conversation_history:
            q_words = question.strip().split()
            first_word = q_words[0].lower().strip('¿?¡!') if q_words else ''
            is_follow_up = len(q_words) <= 6 or first_word in _FOLLOW_UP_STARTERS
            if is_follow_up:
                last_user_msg = conversation_history[-1][0]
                search_query = f"{last_user_msg} {question}"
                print(f"Query enriquecida para búsqueda: {search_query}\n")

        # Verificar que haya documentos
        doc_count = self.repository.count_documents()
        if doc_count == 0:
            return {
                "answer": "No hay documentos en la base de datos. Por favor, ejecuta primero la ingestion de documentos.",
                "relevant_documents": [],
                "match_type": "none",
                "error": "No documents in database"
            }

        print(f"Documentos en base de datos: {doc_count}")

        # PASO 1: Clasificar la consulta según FAQs
        if enable_faq and self.faq_handler.should_use_faq(question):
            print("\nBuscando en FAQs...")
            faq_classification = self.faq_handler.classify_query(search_query, top_k=5)
            match_type = faq_classification['match_type']
            faq_results = faq_classification['faq_results']
            best_similarity = faq_classification['best_similarity']

            print(f"Match type: {match_type.upper()}")
            print(f"Best FAQ similarity: {best_similarity:.2%}")
        else:
            match_type = 'low'
            faq_results = []
            best_similarity = 0.0
            print("\nSaltando búsqueda en FAQs (disabled o comando especial)")

        # PASO 2: Obtener documentos si es necesario (EXCLUIR FAQs)
        doc_results = []
        if match_type in ['medium', 'low']:
            print(f"\nBuscando en documentos generales (top-{top_k})...")
            all_docs = self.retriever.retrieve_relevant_documents(
                query=search_query,
                top_k=top_k * 2  # Buscar más para compensar filtrado
            )

            # Filtrar FAQs y documentos por debajo del umbral de similitud mínimo
            doc_results = [
                (filename, content, score)
                for filename, content, score in all_docs
                if not filename.startswith('faq/')
                and score >= RetrievalConfig.MIN_SIMILARITY_THRESHOLD
            ]

            # Limitar a top_k
            doc_results = doc_results[:top_k]

        # PASO 3: Preparar contexto para el LLM
        context_documents, context_type = self.faq_handler.get_context_for_llm(
            query=question,
            match_type=match_type,
            faq_results=faq_results,
            doc_results=doc_results
        )

        if not context_documents:
            return {
                "answer": "No se encontraron documentos relevantes para tu pregunta.",
                "relevant_documents": [],
                "match_type": match_type,
                "error": "No relevant documents found"
            }

        # PASO 4: Ajustar temperatura según contexto
        adjusted_temperature = self.faq_handler.get_temperature_for_context(context_type)

        print(f"\nTipo de contexto: {context_type}")
        print(f"Temperature ajustada: {adjusted_temperature}")
        print(f"\nGenerando respuesta con {self.llm_provider.upper()}...\n")

        # PASO 5: Generar respuesta con LLM
        try:
            answer = self.llm_client.generate_response(
                query=question,
                context_documents=context_documents,
                temperature=adjusted_temperature,
                max_tokens=max_tokens,
                context_type=context_type,
                conversation_history=conversation_history
            )

            print("=" * 60)
            print("RESPUESTA GENERADA")
            print("=" * 60)

            # Preparar metadata de documentos relevantes
            relevant_docs = []

            # Agregar FAQs si se usaron
            if faq_results:
                for filename, content, score in faq_results[:3]:
                    relevant_docs.append({
                        "filename": filename,
                        "similarity": score,
                        "type": "faq",
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    })

            # Agregar docs generales si se usaron
            if doc_results and match_type in ['medium', 'low']:
                for filename, content, score in doc_results[:3]:
                    relevant_docs.append({
                        "filename": filename,
                        "similarity": score,
                        "type": "document",
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    })

            return {
                "answer": answer,
                "relevant_documents": relevant_docs,
                "match_type": match_type,
                "context_type": context_type,
                "best_faq_similarity": best_similarity,
                "error": None
            }

        except Exception as e:
            error_msg = f"Error al generar respuesta: {str(e)}"
            print(f"ERROR: {error_msg}")

            return {
                "answer": "Ocurrió un error al generar la respuesta.",
                "relevant_documents": [],
                "match_type": match_type,
                "error": error_msg
            }

    def query(
        self,
        question: str,
        top_k: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> dict:
        """
        Realiza una consulta al sistema RAG

        Args:
            question: Pregunta del usuario
            top_k: Número de documentos relevantes a recuperar
            temperature: Temperatura para la generación de DeepSeek
            max_tokens: Máximo de tokens en la respuesta

        Returns:
            Diccionario con la respuesta y metadatos
        """
        print("=" * 60)
        print("PROCESANDO CONSULTA RAG")
        print("=" * 60)
        print(f"Pregunta: {question}\n")

        # Verificar que haya documentos
        doc_count = self.repository.count_documents()
        if doc_count == 0:
            return {
                "answer": "No hay documentos en la base de datos. Por favor, ejecuta primero la ingestion de documentos.",
                "relevant_documents": [],
                "error": "No documents in database"
            }

        print(f"Documentos en base de datos: {doc_count}\n")

        # Recuperar documentos relevantes
        relevant_docs = self.retriever.retrieve_relevant_documents(
            query=question,
            top_k=top_k
        )

        if not relevant_docs:
            return {
                "answer": "No se encontraron documentos relevantes para tu pregunta.",
                "relevant_documents": [],
                "error": "No relevant documents found"
            }

        # Extraer solo el contenido de los documentos para el contexto
        context_documents = [content for _, content, _ in relevant_docs]

        # Generar respuesta con DeepSeek
        print("\nGenerando respuesta con DeepSeek...\n")

        try:
            answer = self.llm_client.generate_response(
                query=question,
                context_documents=context_documents,
                temperature=temperature,
                max_tokens=max_tokens
            )

            print("=" * 60)
            print("RESPUESTA GENERADA")
            print("=" * 60)

            return {
                "answer": answer,
                "relevant_documents": [
                    {
                        "filename": filename,
                        "similarity": score,
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    }
                    for filename, content, score in relevant_docs
                ],
                "error": None
            }

        except Exception as e:
            error_msg = f"Error al generar respuesta: {str(e)}"
            print(f"ERROR: {error_msg}")

            return {
                "answer": "Ocurrió un error al generar la respuesta.",
                "relevant_documents": [
                    {
                        "filename": filename,
                        "similarity": score,
                        "preview": content[:200] + "..."
                    }
                    for filename, content, score in relevant_docs
                ],
                "error": error_msg
            }

    def reset_database(self):
        """Elimina todos los documentos de la base de datos"""
        count = self.repository.delete_all_documents()
        print(f"Base de datos limpiada. {count} documentos eliminados.")

    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del sistema

        Returns:
            Diccionario con estadísticas
        """
        stats = {
            "total_documents": self.repository.count_documents(),
            "storage_type": self.storage_type,
            "embedder_model": self.embedder.model_name,
            "llm_model": self.llm_client.model
        }

        if self.storage_type == "sql":
            stats["database"] = self.storage.database
        else:
            stats["storage_path"] = str(self.storage.storage_path)

        return stats

    def close(self):
        """Cierra recursos (ChromaDB no requiere cierre explícito)"""
        pass


if __name__ == "__main__":
    # Test del pipeline
    try:
        pipeline = RAGPipeline()

        # Mostrar estadísticas
        stats = pipeline.get_stats()
        print(f"Estadísticas: {stats}\n")

        # Test de consulta (asumiendo que ya hay documentos)
        if stats['total_documents'] > 0:
            test_question = "¿Qué información hay disponible?"
            result = pipeline.query(test_question)

            print(f"\nPregunta: {test_question}")
            print(f"Respuesta: {result['answer']}")

        pipeline.close()

    except Exception as e:
        print(f"Error: {str(e)}")
