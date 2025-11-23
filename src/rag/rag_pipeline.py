"""
Pipeline RAG completo: ingestion de documentos y generación de respuestas
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from typing import List, Optional
from embeddings.embedder import Embedder
from database.connection import DatabaseConnection
from database.repository import DocumentRepository
from ingestion.ingest_docs import DocumentIngestion
from llm.deepseek_client import DeepSeekClient
from llm.groq_client import GroqClient
from rag.retriever import DocumentRetriever


class RAGPipeline:
    """Pipeline completo para el sistema RAG"""

    def __init__(self, docs_folder: str = "data/docs", llm_provider: str = "groq"):
        """
        Inicializa el pipeline RAG

        Args:
            docs_folder: Carpeta con los documentos markdown
            llm_provider: Proveedor de LLM ("groq" o "deepseek")
        """
        print("Inicializando pipeline RAG...")

        # Inicializar componentes
        self.embedder = Embedder()
        self.db_connection = DatabaseConnection()
        self.db_connection.connect()
        self.db_connection.create_table_if_not_exists()

        self.repository = DocumentRepository(self.db_connection)
        self.ingestion = DocumentIngestion(docs_folder)
        self.retriever = DocumentRetriever(self.repository, self.embedder)

        # Inicializar LLM según el proveedor
        self.llm_provider = llm_provider.lower()
        if self.llm_provider == "groq":
            self.llm_client = GroqClient(model="llama-3.3-70b-versatile")
            print("✨ Usando Groq API con Llama 3.3 70B (ultra-rápido)")
        elif self.llm_provider == "deepseek":
            self.llm_client = DeepSeekClient()
            print("🔷 Usando DeepSeek API")
        else:
            raise ValueError(f"LLM provider no soportado: {llm_provider}. Usa 'groq' o 'deepseek'")

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
                print(f"⏭️  Saltando '{filename}' (ya existe)")
                skipped_count += 1
                continue

            try:
                # Generar embedding
                print(f"\n📝 Procesando: {filename}")
                embedding = self.embedder.generate_embedding(content)

                # Convertir a bytes
                embedding_bytes = self.embedder.embedding_to_bytes(embedding)

                # Guardar en base de datos
                self.repository.insert_document(filename, content, embedding_bytes)
                processed_count += 1

            except Exception as e:
                print(f"❌ Error procesando {filename}: {str(e)}")
                continue

        print("\n" + "=" * 60)
        print(f"INGESTION COMPLETADA")
        print(f"Documentos procesados: {processed_count}")
        print(f"Documentos saltados: {skipped_count}")
        print(f"Total en base de datos: {self.repository.count_documents()}")
        print("=" * 60)

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
        print("\n🤖 Generando respuesta con DeepSeek...\n")

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
            print(f"❌ {error_msg}")

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
        return {
            "total_documents": self.repository.count_documents(),
            "database": self.db_connection.database,
            "embedder_model": "BAAI/bge-m3",
            "llm_model": self.llm_client.model
        }

    def close(self):
        """Cierra la conexión a la base de datos"""
        self.db_connection.disconnect()


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
