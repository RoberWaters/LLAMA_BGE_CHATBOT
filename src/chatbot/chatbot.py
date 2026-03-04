"""
Módulo de chatbot con historial de conversación
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import unicodedata
from typing import List, Tuple, Optional
from rag.rag_pipeline import RAGPipeline
from config import S3Config

# Frases conversacionales que NO requieren RAG (normalizadas sin acentos)
_GREETINGS = {
    "hola", "buenos dias", "buenas tardes", "buenas noches", "buenas",
    "hey", "ey", "hi", "hello", "que tal", "como estas", "como te va",
}
_FAREWELLS = {
    "adios", "hasta luego", "hasta pronto", "hasta manana", "chao", "chau",
    "bye", "nos vemos", "que te vaya bien",
}
_THANKS = {
    "gracias", "muchas gracias", "mil gracias", "te lo agradezco",
    "muy amable", "gracias por todo", "ok gracias", "perfecto gracias",
}
_ACKS = {
    "ok", "okay", "de acuerdo", "entendido", "perfecto", "genial",
    "listo", "esta bien", "muy bien", "excelente", "claro", "bien",
}


def _normalize(text: str) -> str:
    """Lowercase, elimina puntuación y normaliza acentos."""
    text = text.strip().lower()
    text = re.sub(r"[.!¡¿?,;:]+", "", text).strip()
    # Quitar diacríticos (acentos)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text

_CONVERSATIONAL_SYSTEM_PROMPT = """Eres el Asistente Virtual de VOAE (Vicerrectoría de Orientación y Asuntos Estudiantiles de la UNAH).

Eres cercano, cálido y natural. Respondes de forma breve y humana a mensajes conversacionales como saludos, despedidas y agradecimientos.

Reglas:
- Responde de forma corta y amigable (1-2 oraciones máximo)
- Usa el "tú" para crear cercanía
- Si es un saludo, saluda de vuelta y ofrece ayuda con los servicios de la VOAE
- Si es una despedida, despídete amablemente
- Si es un agradecimiento, responde con calidez
- Si es un simple "ok" o "entendido", reconócelo brevemente
- NO menciones que eres un bot o asistente virtual de manera robótica
- NO incluyas listas ni información técnica"""


class RAGChatbot:
    """Chatbot con historial de conversación y sistema RAG"""

    def __init__(
        self,
        s3_bucket: str = None,
        s3_prefix: str = None,
        max_history: int = 5,
        llm_provider: str = "bedrock"
    ):
        """
        Inicializa el chatbot con ChromaDB.

        Args:
            s3_bucket: Nombre del bucket S3 (default: S3Config.BUCKET_NAME)
            s3_prefix: Prefijo S3 para documentos (default: S3Config.DOCS_PREFIX)
            max_history: Número máximo de mensajes a recordar en el historial
            llm_provider: Proveedor de LLM ("bedrock")
        """
        if s3_bucket is None:
            s3_bucket = S3Config.BUCKET_NAME
        if s3_prefix is None:
            s3_prefix = S3Config.DOCS_PREFIX

        self.pipeline = RAGPipeline(s3_bucket=s3_bucket, s3_prefix=s3_prefix, llm_provider=llm_provider)
        self.max_history = max_history
        self.conversation_history: List[Tuple[str, str]] = []
        # Tipo de match por turno ('high'|'medium'|'low'|'none').
        # Los turnos con match_type=='none' indican que no hubo docs relevantes
        # y la respuesta puede ser una alucinación; se excluyen del contexto LLM.
        self._history_confidence: List[str] = []

    def _detect_conversational_type(self, message: str) -> Optional[str]:
        """Detecta si el mensaje es conversacional. Retorna 'greeting', 'farewell', 'thanks', 'ack' o None."""
        msg = _normalize(message)
        if msg in _GREETINGS:
            return "greeting"
        if msg in _FAREWELLS:
            return "farewell"
        if msg in _THANKS:
            return "thanks"
        if msg in _ACKS:
            return "ack"
        return None

    def _handle_conversational(self, message: str, conv_type: str, temperature: float) -> dict:
        """Genera una respuesta humana para mensajes conversacionales sin RAG."""
        try:
            answer = self.pipeline.llm_client.simple_chat(
                message=message,
                temperature=max(temperature, 0.7),  # más natural con temperatura alta
                max_tokens=150,
                system_prompt=_CONVERSATIONAL_SYSTEM_PROMPT,
            )
            return {
                "answer": answer,
                "relevant_documents": [],
                "match_type": "conversational",
                "error": None,
            }
        except Exception as e:
            return {
                "answer": "¡Hola! ¿En qué puedo ayudarte hoy?",
                "relevant_documents": [],
                "match_type": "conversational",
                "error": str(e),
            }

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

        # Detectar mensajes conversacionales (saludos, despedidas, agradecimientos)
        conv_type = self._detect_conversational_type(user_message)
        if conv_type:
            result = self._handle_conversational(user_message, conv_type, temperature)
            if not result.get("error"):
                self.conversation_history.append((user_message, result["answer"]))
                self._history_confidence.append("conversational")
                if len(self.conversation_history) > self.max_history:
                    self.conversation_history = self.conversation_history[-self.max_history:]
                    self._history_confidence = self._history_confidence[-self.max_history:]
            return result

        # Si usa RAG, hacer consulta con sistema FAQ híbrido
        if use_rag:
            # Excluir del contexto LLM los turnos sin documentos relevantes ('none'),
            # ya que esas respuestas pueden ser alucinaciones que contaminarían el contexto.
            recent = list(zip(
                self.conversation_history[-self.max_history:],
                self._history_confidence[-self.max_history:]
            ))
            reliable_history = [turn for turn, conf in recent if conf != 'none']

            result = self.pipeline.query_with_faq(
                question=user_message,
                top_k=top_k,
                temperature=temperature,
                enable_faq=True,
                conversation_history=reliable_history
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

        # Solo agregar al historial si la respuesta no es un error
        if not result.get("error"):
            self.conversation_history.append((user_message, result["answer"]))
            self._history_confidence.append(result.get("match_type", "low"))
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]
                self._history_confidence = self._history_confidence[-self.max_history:]

        return result

    def clear_history(self):
        """Limpia el historial de conversación"""
        self.conversation_history = []
        self._history_confidence = []
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
            self._history_confidence = self._history_confidence[-max_history:]

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
