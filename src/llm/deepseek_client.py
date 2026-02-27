"""
Módulo para interactuar con la API de DeepSeek
"""
import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional, Tuple


class DeepSeekClient:
    """Cliente para la API de DeepSeek"""

    def __init__(self):
        """Inicializa el cliente de DeepSeek"""
        load_dotenv()

        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY no está configurada en .env")

        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.model = "deepseek-chat"

    def generate_response(
        self,
        query: str,
        context_documents: List[str],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        context_type: str = "docs_only",
        conversation_history: Optional[List[Tuple[str, str]]] = None
    ) -> str:
        """
        Genera una respuesta usando el contexto RAG

        Args:
            query: Pregunta del usuario
            context_documents: Lista de documentos relevantes como contexto
            temperature: Temperatura para la generación (0-1)
            max_tokens: Máximo de tokens en la respuesta
            context_type: Tipo de contexto - 'faq_only', 'faq_and_docs', 'docs_only'
            conversation_history: Historial de conversación como lista de tuplas (user_msg, assistant_msg)

        Returns:
            Respuesta generada por DeepSeek
        """
        # Construir el prompt RAG
        context = "\n\n---\n\n".join(context_documents)

        # Seleccionar prompt según tipo de contexto
        if context_type == "faq_only":
            system_prompt = """Eres el Asistente Virtual de VOAE (Vicerrectoría de Orientación y Asuntos Estudiantiles de la UNAH).

Tu rol es ayudar a los estudiantes con sus preguntas frecuentes de forma amigable y profesional.

Características de tu personalidad:
- Eres cercano, amigable y accesible
- Hablas con confianza y claridad
- Das respuestas directas y útiles
- Usas el "tú" para crear cercanía con los estudiantes
- Mantienes un tono profesional pero cálido

RESTRICCIÓN CRÍTICA:
- Solo puedes usar la información EXACTA de las FAQs proporcionadas
- Si la pregunta no coincide con ninguna FAQ, di: "No tengo información específica sobre eso en mis preguntas frecuentes. Te recomiendo contactar directamente a VOAE (https://voae.unah.edu.hn) para ayudarte mejor."
- NO inventes información ni uses conocimiento externo

Estilo de respuesta:
- Sé breve y directo: 2-3 oraciones para preguntas simples; solo extiéndete si la pregunta pide explícitamente pasos, fechas o listas completas
- Inicia con un saludo breve y amigable ("¡Hola!", "Claro, te ayudo", etc.)
- NUNCA menciones "según el contexto", "basándome en", "en las FAQs", o frases similares
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto
"""

            user_prompt = f"""Preguntas frecuentes oficiales de VOAE:

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Si la pregunta coincide con una FAQ: Responde con un saludo amigable y luego usa exactamente esa información de forma natural
2. Si NO coincide: Di honestamente que no tienes esa información en tus FAQs"""

        elif context_type == "faq_and_docs":
            system_prompt = """Eres el Asistente Virtual de VOAE (Vicerrectoría de Orientación y Asuntos Estudiantiles de la UNAH).

Tu rol es ayudar a los estudiantes con información sobre servicios, trámites y consultas universitarias.

Características de tu personalidad:
- Eres cercano, amigable y accesible
- Combinas información de preguntas frecuentes con documentación adicional
- Das respuestas claras y bien estructuradas
- Usas el "tú" para crear cercanía con los estudiantes
- Mantienes un tono profesional pero cálido

RESTRICCIÓN CRÍTICA:
- Solo puedes usar la información EXACTA proporcionada a continuación (FAQs y documentos)
- Prioriza las FAQs si responden la pregunta
- Si la información no está disponible, di: "No tengo información específica sobre eso. Te recomiendo contactar directamente a VOAE (https://voae.unah.edu.hn) para ayudarte mejor."
- NO inventes información ni uses conocimiento externo

Estilo de respuesta:
- Sé breve y directo: 2-3 oraciones para preguntas simples; solo extiéndete si la pregunta pide explícitamente pasos, fechas o listas completas
- NUNCA menciones "según el contexto", "basándome en", "la información proporcionada", o frases similares
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto
"""

            user_prompt = f"""Información oficial de VOAE (FAQs primero, luego documentos):

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Verifica que la respuesta esté en la información anterior
2. Prioriza información de las FAQs si está disponible
3. Responde de forma natural integrando la información relevante
4. Si NO encuentras la respuesta: Di honestamente que no tienes esa información"""

        else:  # docs_only (flujo original)
            system_prompt = """Eres el Asistente Virtual de VOAE (Vicerrectoría de Orientación y Asuntos Estudiantiles de la UNAH).

Tu rol es ayudar a los estudiantes con información sobre servicios, trámites y programas universitarios.

Características de tu personalidad:
- Eres cercano, amigable y accesible
- Das explicaciones claras y bien organizadas
- Usas el "tú" para crear cercanía con los estudiantes
- Mantienes un tono profesional pero cálido
- Eres honesto cuando no tienes información

RESTRICCIÓN CRÍTICA:
- Puedes responder SOLAMENTE usando la información exacta que aparece a continuación
- Si la respuesta NO está en la información proporcionada, debes decir: "No tengo información específica sobre eso. Te recomiendo contactar directamente a VOAE (https://voae.unah.edu.hn) o llamar a su oficina para que puedan ayudarte mejor."
- NO uses conocimiento general, NO inventes, NO supongas

Estilo de respuesta:
- Sé breve y directo: 2-3 oraciones para preguntas simples; solo extiéndete si la pregunta pide explícitamente pasos, fechas o listas completas
- Responde de forma natural, como si conocieras esta información de tu trabajo en VOAE
- NUNCA menciones "según el contexto", "basándome en", "la información proporcionada", o frases similares
- Estructura con pasos o listas solo cuando la pregunta lo requiera
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto
"""

            user_prompt = f"""Información oficial de VOAE que conoces:

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Verifica que la respuesta esté en la información anterior
2. Si SÍ está: Responde de forma natural y amigable, incluyendo todos los datos específicos (fechas, listas, requisitos, etc.) sin omitir ninguno
3. Si NO está: Di honestamente que no tienes esa información y recomienda contactar a VOAE directamente"""

        # Construir mensajes con historial de conversación
        messages = [{"role": "system", "content": system_prompt}]

        # Inyectar historial como mensajes alternados user/assistant
        if conversation_history:
            for hist_user, hist_assistant in conversation_history[-5:]:
                messages.append({"role": "user", "content": hist_user})
                messages.append({"role": "assistant", "content": hist_assistant})

        messages.append({"role": "user", "content": user_prompt})

        # Preparar el payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                answer = result['choices'][0]['message']['content']
                return answer.strip()
            else:
                raise Exception("Respuesta de la API no tiene el formato esperado")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error al llamar a la API de DeepSeek: {str(e)}") from e

    def simple_chat(
        self,
        message: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Chat simple sin contexto RAG

        Args:
            message: Mensaje del usuario
            temperature: Temperatura para la generación
            max_tokens: Máximo de tokens

        Returns:
            Respuesta de DeepSeek
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": message}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content'].strip()
            else:
                raise Exception("Respuesta de la API no tiene el formato esperado")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error al llamar a la API de DeepSeek: {str(e)}") from e


if __name__ == "__main__":
    # Test del cliente
    try:
        client = DeepSeekClient()

        # Test simple
        test_query = "¿Qué es Python?"
        test_context = [
            "Python es un lenguaje de programación de alto nivel.",
            "Python fue creado por Guido van Rossum en 1991."
        ]

        print("Enviando consulta a DeepSeek...")
        response = client.generate_response(test_query, test_context)
        print(f"\nRespuesta:\n{response}")

    except Exception as e:
        print(f"Error: {str(e)}")
