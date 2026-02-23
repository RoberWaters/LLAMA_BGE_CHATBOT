"""
Módulo para operaciones CRUD en la base de datos
Soporta ChromaDB como almacenamiento vectorial
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import List, Tuple, Optional
from database.chroma_vector_store import ChromaVectorStore


class DocumentRepository:
    """Repositorio para operaciones con documentos usando ChromaDB"""

    def __init__(self, storage: ChromaVectorStore = None):
        """
        Inicializa el repositorio

        Args:
            storage: ChromaVectorStore instance (opcional, se crea uno por defecto)
        """
        if storage is None:
            # Por defecto usar ChromaDB
            storage = ChromaVectorStore()

        self.storage = storage
        self.storage_type = "chroma"

    def insert_document(self, filename: str, content: str, embedding_bytes: bytes) -> str:
        """
        Inserta un documento con su embedding en ChromaDB

        Args:
            filename: Nombre del archivo
            content: Contenido del documento
            embedding_bytes: Embedding en formato bytes

        Returns:
            ID del documento insertado
        """
        try:
            # Convertir bytes a numpy array
            embedding = np.frombuffer(embedding_bytes, dtype='float32')
            return self.storage.add_document(filename, content, embedding)
        except Exception as e:
            raise Exception(f"Error al insertar documento: {str(e)}") from e

    def get_all_documents(self) -> List[Tuple[str, str, str, bytes]]:
        """
        Obtiene todos los documentos desde ChromaDB

        Returns:
            Lista de tuplas (id, filename, content, embedding_bytes)
        """
        try:
            # Obtener documentos de ChromaDB
            docs = self.storage.get_all_documents()
            # Convertir numpy arrays a bytes
            result = []
            for doc_id, filename, content, embedding in docs:
                embedding_bytes = embedding.astype('float32').tobytes()
                result.append((doc_id, filename, content, embedding_bytes))
            print(f"Se recuperaron {len(result)} documentos")
            return result
        except Exception as e:
            raise Exception(f"Error al obtener documentos: {str(e)}") from e

    def get_document_by_id(self, doc_id: str) -> Optional[Tuple[str, str, str, bytes]]:
        """
        Obtiene un documento por su ID desde ChromaDB

        Args:
            doc_id: ID del documento

        Returns:
            Tupla (id, filename, content, embedding_bytes) o None si no existe
        """
        try:
            doc = self.storage.get_document_by_id(doc_id)
            if doc:
                doc_id, filename, content, embedding = doc
                embedding_bytes = embedding.astype('float32').tobytes()
                return (doc_id, filename, content, embedding_bytes)
            return None
        except Exception as e:
            raise Exception(f"Error al obtener documento: {str(e)}") from e

    def delete_document(self, doc_id: str) -> bool:
        """
        Elimina un documento por su ID de ChromaDB

        Args:
            doc_id: ID del documento a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        try:
            return self.storage.delete_document(doc_id)
        except Exception as e:
            raise Exception(f"Error al eliminar documento: {str(e)}") from e

    def delete_all_documents(self) -> int:
        """
        Elimina todos los documentos de ChromaDB

        Returns:
            Número de documentos eliminados
        """
        try:
            return self.storage.delete_all_documents()
        except Exception as e:
            raise Exception(f"Error al eliminar documentos: {str(e)}") from e

    def count_documents(self) -> int:
        """
        Cuenta el número total de documentos en ChromaDB

        Returns:
            Número de documentos
        """
        try:
            return self.storage.count_documents()
        except Exception as e:
            raise Exception(f"Error al contar documentos: {str(e)}") from e

    def document_exists(self, filename: str) -> bool:
        """
        Verifica si un documento ya existe en ChromaDB

        Args:
            filename: Nombre del archivo a verificar

        Returns:
            True si existe, False si no
        """
        try:
            return self.storage.document_exists(filename)
        except Exception as e:
            raise Exception(f"Error al verificar documento: {str(e)}") from e
