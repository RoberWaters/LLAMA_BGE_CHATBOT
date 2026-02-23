"""
Módulo para gestionar almacenamiento de embeddings usando ChromaDB
"""
import chromadb
from chromadb.config import Settings
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional


class ChromaVectorStore:
    """Clase para manejar almacenamiento de vectores con ChromaDB"""

    def __init__(self, storage_path: str = "data/chroma"):
        """
        Inicializa el almacenamiento con ChromaDB

        Args:
            storage_path: Ruta donde se guardarán los datos de ChromaDB
        """
        self.storage_path = Path(storage_path)

        # Crear directorio si no existe
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Inicializar cliente ChromaDB con persistencia
        self.client = chromadb.PersistentClient(path=str(self.storage_path))

        # Obtener o crear colección
        # ChromaDB usa cosine similarity por defecto
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}  # Cosine similarity
        )

        print(f"ChromaDB inicializado en: {self.storage_path}")
        print(f"Documentos en colección: {self.collection.count()}")

    def add_document(self, filename: str, content: str, embedding: np.ndarray) -> str:
        """
        Añade un documento con su embedding a ChromaDB

        Args:
            filename: Nombre del archivo
            content: Contenido del documento
            embedding: Embedding numpy array (1024 dimensiones)

        Returns:
            ID del documento insertado (string)
        """
        # ChromaDB genera IDs automáticamente, pero usaremos el filename como ID
        # Convertir filename a un ID válido (sin espacios ni caracteres especiales)
        doc_id = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")

        # Convertir embedding a lista (ChromaDB requiere list, no numpy array)
        embedding_list = embedding.astype('float32').tolist()

        # Añadir a ChromaDB
        self.collection.add(
            embeddings=[embedding_list],
            documents=[content],
            metadatas=[{"filename": filename}],
            ids=[doc_id]
        )

        print(f"Documento '{filename}' añadido con ID: {doc_id}")
        return doc_id

    def get_all_documents(self) -> List[Tuple[str, str, str, np.ndarray]]:
        """
        Obtiene todos los documentos con sus embeddings

        Returns:
            Lista de tuplas (id, filename, content, embedding)
        """
        # Obtener todos los documentos
        results = self.collection.get(
            include=["embeddings", "documents", "metadatas"]
        )

        documents = []

        if results['ids']:
            for i, doc_id in enumerate(results['ids']):
                filename = results['metadatas'][i]['filename']
                content = results['documents'][i]
                embedding = np.array(results['embeddings'][i], dtype='float32')

                documents.append((
                    doc_id,
                    filename,
                    content,
                    embedding
                ))

        return documents

    def get_document_by_id(self, doc_id: str) -> Optional[Tuple[str, str, str, np.ndarray]]:
        """
        Obtiene un documento por su ID

        Args:
            doc_id: ID del documento (string)

        Returns:
            Tupla (id, filename, content, embedding) o None si no existe
        """
        # En ChromaDB no tenemos búsqueda por hash, así que buscamos todos
        all_docs = self.get_all_documents()

        for doc in all_docs:
            if doc[0] == doc_id:
                return doc

        return None

    def document_exists(self, filename: str) -> bool:
        """
        Verifica si un documento ya existe

        Args:
            filename: Nombre del archivo a verificar

        Returns:
            True si existe, False si no
        """
        doc_id = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")

        try:
            result = self.collection.get(ids=[doc_id])
            return len(result['ids']) > 0
        except Exception:
            return False

    def count_documents(self) -> int:
        """
        Cuenta el número total de documentos

        Returns:
            Número de documentos
        """
        return self.collection.count()

    def delete_document(self, doc_id: str) -> bool:
        """
        Elimina un documento por su ID

        Args:
            doc_id: ID del documento (string)

        Returns:
            True si se eliminó, False si no existía
        """
        # Buscar el documento por hash
        all_docs = self.get_all_documents()

        for doc in all_docs:
            if doc[0] == doc_id:
                # doc[1] es el filename
                chroma_id = doc[1].replace(" ", "_").replace("/", "_").replace("\\", "_")
                try:
                    self.collection.delete(ids=[chroma_id])
                    print(f"Documento {doc_id} eliminado")
                    return True
                except Exception:
                    return False

        return False

    def delete_all_documents(self) -> int:
        """
        Elimina todos los documentos

        Returns:
            Número de documentos eliminados
        """
        count = self.collection.count()

        # Eliminar la colección y recrearla
        self.client.delete_collection(name="documents")
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

        print(f"Se eliminaron {count} documentos")
        return count

    def search_similar(self, query_embedding: np.ndarray, top_k: int = 3) -> List[Tuple[int, str, str, float]]:
        """
        Busca los documentos más similares usando ChromaDB

        Args:
            query_embedding: Embedding de la consulta
            top_k: Número de resultados a retornar

        Returns:
            Lista de tuplas (id, filename, content, similarity_score)
        """
        if self.collection.count() == 0:
            return []

        # Convertir embedding a lista
        query_list = query_embedding.astype('float32').tolist()

        # Buscar en ChromaDB
        results = self.collection.query(
            query_embeddings=[query_list],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        # Construir resultados
        similar_docs = []

        if results['ids'] and len(results['ids'][0]) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                filename = results['metadatas'][0][i]['filename']
                content = results['documents'][0][i]

                # ChromaDB retorna distancia, convertir a similitud
                # Para cosine distance: similarity = 1 - distance
                distance = results['distances'][0][i]
                similarity = 1.0 - distance

                similar_docs.append((
                    doc_id,
                    filename,
                    content,
                    float(similarity)
                ))

        return similar_docs


if __name__ == "__main__":
    # Test del almacenamiento ChromaDB
    try:
        store = ChromaVectorStore()

        # Test: crear embedding dummy
        test_embedding = np.random.rand(1024).astype('float32')

        # Test: añadir documento
        doc_id = store.add_document("test.md", "Contenido de prueba", test_embedding)
        print(f"\nDocumento añadido con ID: {doc_id}")

        # Test: contar documentos
        count = store.count_documents()
        print(f"Total de documentos: {count}")

        # Test: buscar similar
        results = store.search_similar(test_embedding, top_k=1)
        print(f"\nBúsqueda similar encontró {len(results)} resultados")

        if results:
            print(f"Mejor resultado: {results[0][1]} con similitud {results[0][3]:.4f}")

        print("\nTest de ChromaDB exitoso")

    except Exception as e:
        print(f"Error en test: {str(e)}")
        import traceback
        traceback.print_exc()
