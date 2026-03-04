"""
Módulo para cargar y procesar documentos markdown desde Amazon S3
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple

from config import S3Config
from database import s3_sync


class DocumentIngestion:
    """Clase para cargar y procesar documentos markdown desde S3"""

    def __init__(self, s3_bucket: str = None, s3_prefix: str = None):
        """
        Inicializa el módulo de ingestion.

        Args:
            s3_bucket: Nombre del bucket S3 (default: S3Config.BUCKET_NAME)
            s3_prefix: Prefijo en S3 donde viven los .md (default: S3Config.DOCS_PREFIX)
        """
        self.s3_bucket = s3_bucket if s3_bucket is not None else S3Config.BUCKET_NAME
        self.s3_prefix = s3_prefix if s3_prefix is not None else S3Config.DOCS_PREFIX

        if not self.s3_bucket:
            raise ValueError(
                "S3_BUCKET_NAME no está configurado. "
                "Defínelo en .env o pasa s3_bucket al constructor."
            )

    def load_markdown_files(self) -> List[Tuple[str, str]]:
        """
        Carga todos los archivos markdown desde S3.

        Returns:
            Lista de tuplas (filename, content) donde filename es relativo al prefix
        """
        keys = s3_sync.list_docs(self.s3_bucket, self.s3_prefix)

        if not keys:
            print(f"Advertencia: No se encontraron archivos .md en s3://{self.s3_bucket}/{self.s3_prefix}")
            return []

        markdown_files = []
        # Normalizar el prefijo para derivar el filename relativo
        prefix = self.s3_prefix.rstrip('/')

        for key in keys:
            try:
                content = s3_sync.read_doc(self.s3_bucket, key)
                # Derivar ruta relativa al prefix (ej: docs/faq/file.md → faq/file.md)
                filename = key[len(prefix):].lstrip('/')
                markdown_files.append((filename, content))
                print(f"Cargado: {filename}")
            except Exception as e:
                print(f"Error al cargar {key}: {str(e)}")
                continue

        print(f"Total de archivos cargados: {len(markdown_files)}")
        return markdown_files

    def clean_text(self, text: str) -> str:
        """
        Limpia y preprocesa el texto

        Args:
            text: Texto a limpiar

        Returns:
            Texto limpio
        """
        # Eliminar múltiples saltos de línea
        text = re.sub(r'\n\s*\n', '\n\n', text)

        # Eliminar espacios al inicio/final de cada línea
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Eliminar espacios múltiples
        text = re.sub(r' +', ' ', text)

        # Eliminar espacios antes de puntuación
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)

        return text.strip()

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Divide el texto en chunks para embeddings más efectivos

        Args:
            text: Texto a dividir
            chunk_size: Tamaño máximo de cada chunk en caracteres
            overlap: Solapamiento entre chunks

        Returns:
            Lista de chunks de texto
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Intentar cortar en un punto natural (punto, salto de línea)
            if end < len(text):
                # Buscar el último punto o salto de línea en el chunk
                chunk_text = text[start:end]
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')

                natural_break = max(last_period, last_newline)

                if natural_break > chunk_size // 2:  # Si encontramos un buen punto de corte
                    end = start + natural_break + 1

            chunks.append(text[start:end].strip())
            start = end - overlap if end < len(text) else end

        return chunks

    def process_documents(self, chunk_documents: bool = False) -> List[Tuple[str, str]]:
        """
        Procesa todos los documentos: carga, limpia y opcionalmente divide en chunks

        Args:
            chunk_documents: Si es True, divide los documentos en chunks

        Returns:
            Lista de tuplas (filename, processed_content)
        """
        documents = self.load_markdown_files()
        processed_docs = []

        for filename, content in documents:
            # Limpiar el texto
            cleaned_content = self.clean_text(content)

            if chunk_documents:
                # Dividir en chunks
                chunks = self.chunk_text(cleaned_content)
                for i, chunk in enumerate(chunks):
                    chunk_filename = f"{filename}_chunk_{i+1}"
                    processed_docs.append((chunk_filename, chunk))
            else:
                processed_docs.append((filename, cleaned_content))

        print(f"Documentos procesados: {len(processed_docs)}")
        return processed_docs


if __name__ == "__main__":
    # Test del módulo
    try:
        ingestion = DocumentIngestion()
        documents = ingestion.process_documents()


        for filename, content in documents[:2]:  # Mostrar primeros 2
            print(f"\n--- {filename} ---")
            print(f"Longitud: {len(content)} caracteres")
            print(f"Primeros 200 caracteres: {content[:200]}...")

    except Exception as e:
        print(f"Error: {str(e)}")
