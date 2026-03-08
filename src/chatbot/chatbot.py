"""
Chatbot con Knowledge Base de Amazon Bedrock
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple
from llm.bedrock_client import BedrockClient
from config import ChatbotConfig


class RAGChatbot:
    """Chatbot RAG usando Amazon Bedrock Knowledge Bases"""

    def __init__(self, max_history: int = None, **kwargs):
        self.llm_client = BedrockClient()
        self.max_history = max_history or ChatbotConfig.MAX_HISTORY
        # Bedrock maneja el historial via sessionId;
        # esta lista es una copia local para mostrar en el frontend
        self.conversation_history: List[Tuple[str, str]] = []
        self._bedrock_session_id = None

    def chat(
        self,
        user_message: str,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """
        Procesa un mensaje del usuario y genera una respuesta con RAG

        Args:
            user_message: Mensaje del usuario
            temperature: Temperatura para generacion

        Returns:
            Diccionario con respuesta y metadatos
        """
        if not user_message or not user_message.strip():
            return {
                "answer": "Por favor, escribe un mensaje.",
                "error": "Empty message"
            }

        try:
            answer, self._bedrock_session_id = self.llm_client.chat(
                message=user_message,
                session_id=self._bedrock_session_id,
                temperature=temperature,
            )
            result = {"answer": answer, "error": None}

        except Exception as e:
            result = {
                "answer": f"Error al generar respuesta: {str(e)}",
                "error": str(e)
            }

        if not result.get("error"):
            self.conversation_history.append((user_message, result["answer"]))
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

        return result

    def clear_history(self):
        """Limpia el historial de conversacion"""
        self.conversation_history = []
        self._bedrock_session_id = None

    def get_history(self) -> List[Tuple[str, str]]:
        """Obtiene el historial de conversacion"""
        return self.conversation_history.copy()

    def get_stats(self) -> dict:
        """Obtiene estadisticas del chatbot"""
        return {
            "llm_model": self.llm_client.model,
            "llm_provider": "bedrock",
            "max_history": self.max_history,
            "current_history_length": len(self.conversation_history)
        }

    def close(self):
        pass


if __name__ == "__main__":
    try:
        chatbot = RAGChatbot(max_history=3)
        print("=== Test del Chatbot (Knowledge Base) ===\n")

        response = chatbot.chat("Hola, que servicios ofrece VOAE?")
        print(f"Chatbot: {response['answer']}\n")

        response2 = chatbot.chat("Puedes darme mas detalles?")
        print(f"Chatbot: {response2['answer']}\n")

        chatbot.close()
    except Exception as e:
        print(f"Error: {str(e)}")
