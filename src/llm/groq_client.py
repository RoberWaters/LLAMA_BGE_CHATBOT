"""
Módulo para interactuar con la API de Groq (ultra-rápida)
"""
import os
from dotenv import load_dotenv
from typing import List
from groq import Groq


class GroqClient:
    """Cliente para la API de Groq con modelos ultra-rápidos"""

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        """
        Inicializa el cliente de Groq

        Args:
            model: Modelo a usar. Opciones:
                - "llama-3.3-70b-versatile": Llama 3.3 70B (mejor calidad, recomendado)
                - "llama-3.1-8b-instant": Llama 3.1 8B (más rápido)
                - "llama-3.2-90b-text-preview": Llama 3.2 90B (experimental)
        """
        load_dotenv()

        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY no está configurada en .env")

        self.client = Groq(api_key=self.api_key)
        self.model = model

    def generate_response(
        self,
        query: str,
        context_documents: List[str],
        temperature: float = 0.3,
        max_tokens: int = 850
    ) -> str:
        """
        Genera una respuesta usando el contexto RAG

        Args:
            query: Pregunta del usuario
            context_documents: Lista de documentos relevantes como contexto
            temperature: Temperatura para la generación (0-1)
            max_tokens: Máximo de tokens en la respuesta

        Returns:
            Respuesta generada por Groq
        """
        # Construir el prompt RAG
        context = "\n\n---\n\n".join(context_documents)

        system_prompt = """Eres un asistente útil que responde preguntas basándose ÚNICAMENTE en el contexto proporcionado.
Si la información no está en el contexto, di claramente que no tienes esa información.
No inventes información ni uses conocimiento externo al contexto.
Sé conciso y directo en tus respuestas."""

        user_prompt = f"""Usa SOLO esta información de contexto para responder:

{context}

Pregunta del usuario:
{query}"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return chat_completion.choices[0].message.content.strip()

        except Exception as e:
            raise Exception(f"Error al llamar a la API de Groq: {str(e)}")

    def simple_chat(
        self,
        message: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> str:
        """
        Chat simple sin contexto RAG

        Args:
            message: Mensaje del usuario
            temperature: Temperatura para la generación
            max_tokens: Máximo de tokens

        Returns:
            Respuesta de Groq
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "user", "content": message}
                ],
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return chat_completion.choices[0].message.content.strip()

        except Exception as e:
            raise Exception(f"Error al llamar a la API de Groq: {str(e)}")


if __name__ == "__main__":
    # Test del cliente
    try:
        client = GroqClient()

        # Test simple
        test_query = "¿Qué es Python?"
        test_context = [
            "Python es un lenguaje de programación de alto nivel.",
            "Python fue creado por Guido van Rossum en 1991."
        ]

        print("Enviando consulta a Groq...")
        import time
        start = time.time()
        response = client.generate_response(test_query, test_context)
        end = time.time()

        print(f"\nRespuesta (en {(end-start)*1000:.0f}ms):\n{response}")

    except Exception as e:
        print(f"Error: {str(e)}")
