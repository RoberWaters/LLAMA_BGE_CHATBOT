"""
Módulo para cargar y procesar documentos markdown
"""
import os
import re
from pathlib import Path
from typing import List, Tuple


class DocumentIngestion:
    """Clase para cargar y procesar documentos markdown"""

    def __init__(self, docs_folder: str = "data/docs"):
        """
        Inicializa el módulo de ingestion

        Args:
            docs_folder: Ruta a la carpeta con archivos .md
        """
        self.docs_folder = docs_folder
        self._validate_folder()

    def _validate_folder(self):
        """Valida que la carpeta de documentos exista"""
        if not os.path.exists(self.docs_folder):
            raise FileNotFoundError(
                f"La carpeta {self.docs_folder} no existe. "
                f"Por favor créala y coloca archivos .md en ella."
            )

    def load_markdown_files(self) -> List[Tuple[str, str]]:
        """
        Carga todos los archivos markdown de la carpeta

        Returns:
            Lista de tuplas (filename, content)
        """
        markdown_files = []
        docs_path = Path(self.docs_folder)

        # Buscar archivos .md y .MD recursivamente (incluye subdirectorios)
        md_files = list(docs_path.glob("**/*.md")) + list(docs_path.glob("**/*.MD"))

        if not md_files:
            print(f"Advertencia: No se encontraron archivos .md o .MD en {self.docs_folder}")
            return []

        for file_path in md_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Usar ruta relativa desde docs_folder para preservar estructura
                filename = str(file_path.relative_to(docs_path))
                markdown_files.append((filename, content))
                print(f"Cargado: {filename}")

            except Exception as e:
                print(f"Error al cargar {file_path.name}: {str(e)}")
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
