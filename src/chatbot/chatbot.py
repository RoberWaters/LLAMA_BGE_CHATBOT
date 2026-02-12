"""
Módulo de chatbot con historial de conversación
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple, Optional
from rag.rag_pipeline import RAGPipeline


class RAGChatbot:
    """Chatbot con historial de conversación y sistema RAG"""

    def __init__(self, docs_folder: str = "data/docs", max_history: int = 5, llm_provider: str = "groq"):
        """
        Inicializa el chatbot con ChromaDB

        Args:
            docs_folder: Carpeta con documentos
            max_history: Número máximo de mensajes a recordar en el historial
            llm_provider: Proveedor de LLM ("groq" o "deepseek")
        """
        self.pipeline = RAGPipeline(docs_folder, llm_provider=llm_provider)
        self.max_history = max_history
        self.conversation_history = []

    def _format_history_for_llm(self) -> str:
        """
        Formatea el historial de conversación para el LLM

        Returns:
            String con el historial formateado
        """
        if not self.conversation_history:
            return ""

        history_text = "\n\n=== Historial de conversación ===\n"
        for user_msg, assistant_msg in self.conversation_history:
            history_text += f"\nUsuario: {user_msg}\nAsistente: {assistant_msg}\n"
        history_text += "=== Fin del historial ===\n\n"

        return history_text

    def chat(
        self,
        user_message: str,
        top_k: int = 4,
        temperature: float = 0.7,
        use_rag: bool = True
    ) -> dict:
        """
        Procesa un mensaje del usuario y genera una respuesta

        Args:
            user_message: Mensaje del usuario
            top_k: Número de documentos relevantes a recuperar
            temperature: Temperatura para DeepSeek
            use_rag: Si es True, usa RAG; si es False, solo usa el historial

        Returns:
            Diccionario con respuesta y metadatos
        """
        if not user_message or not user_message.strip():
            return {
                "answer": "Por favor, escribe un mensaje.",
                "relevant_documents": [],
                "error": "Empty message"
            }

        # Si usa RAG, hacer consulta con sistema FAQ híbrido
        if use_rag:
            result = self.pipeline.query_with_faq(
                question=user_message,
                top_k=top_k,
                temperature=temperature,
                enable_faq=True
            )
        else:
            # Sin RAG, solo conversación con historial
            history_context = self._format_history_for_llm()

            # Preparar el prompt con historial
            full_message = f"{history_context}Usuario: {user_message}"

            try:
                answer = self.pipeline.llm_client.simple_chat(
                    message=full_message,
                    temperature=temperature
                )

                result = {
                    "answer": answer,
                    "relevant_documents": [],
                    "error": None
                }
            except Exception as e:
                result = {
                    "answer": f"Error al generar respuesta: {str(e)}",
                    "relevant_documents": [],
                    "error": str(e)
                }

        # Agregar al historial (mantener solo los últimos max_history)
        self.conversation_history.append((user_message, result["answer"]))

        # Limitar el historial
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        return result

    def clear_history(self):
        """Limpia el historial de conversación"""
        self.conversation_history = []
        print("Historial de conversación limpiado")

    def get_history(self) -> List[Tuple[str, str]]:
        """
        Obtiene el historial de conversación

        Returns:
            Lista de tuplas (user_message, assistant_message)
        """
        return self.conversation_history.copy()

    def set_max_history(self, max_history: int):
        """
        Cambia el número máximo de mensajes en el historial

        Args:
            max_history: Nuevo límite de historial
        """
        self.max_history = max_history

        # Recortar historial actual si excede el nuevo límite
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]

    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del chatbot

        Returns:
            Diccionario con estadísticas
        """
        stats = self.pipeline.get_stats()
        stats.update({
            "max_history": self.max_history,
            "current_history_length": len(self.conversation_history)
        })
        return stats

    def close(self):
        """Cierra la conexión del pipeline"""
        self.pipeline.close()


if __name__ == "__main__":
    # Test del chatbot
    try:
        chatbot = RAGChatbot(max_history=3)

        print("=== Test del Chatbot ===\n")

        # Test 1: Pregunta con RAG
        response1 = chatbot.chat("¿Qué información tienes sobre becas?")
        print(f"Usuario: ¿Qué información tienes sobre becas?")
        print(f"Chatbot: {response1['answer'][:200]}...\n")

        # Test 2: Pregunta de seguimiento
        response2 = chatbot.chat("¿Puedes darme más detalles?")
        print(f"Usuario: ¿Puedes darme más detalles?")
        print(f"Chatbot: {response2['answer'][:200]}...\n")

        # Mostrar historial
        print(f"\nHistorial ({len(chatbot.get_history())} mensajes):")
        for i, (user, assistant) in enumerate(chatbot.get_history(), 1):
            print(f"{i}. U: {user[:50]}...")
            print(f"   A: {assistant[:50]}...\n")

        chatbot.close()

    except Exception as e:
        print(f"Error: {str(e)}")
