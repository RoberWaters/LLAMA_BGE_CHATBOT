"""
Cliente Amazon Bedrock para LLM (Claude 3.5 Haiku)
"""
import json
import boto3
from typing import List, Tuple, Optional
from config import BedrockConfig


class BedrockClient:
    """Cliente para Amazon Bedrock usando Claude 3.5 Haiku"""

    def __init__(self, model_id: str = None):
        self.model_id = model_id or BedrockConfig.LLM_MODEL_ID
        self.model = self.model_id  # alias usado por rag_pipeline.get_stats()

        if not BedrockConfig.AWS_ACCESS_KEY or not BedrockConfig.AWS_SECRET_KEY:
            raise ValueError(
                "AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY deben estar configuradas en .env"
            )

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=BedrockConfig.AWS_REGION,
            aws_access_key_id=BedrockConfig.AWS_ACCESS_KEY,
            aws_secret_access_key=BedrockConfig.AWS_SECRET_KEY,
        )

    # ------------------------------------------------------------------
    # Prompts internos
    # ------------------------------------------------------------------

    def _build_prompts(
        self, query: str, context: str, context_type: str
    ) -> Tuple[str, str]:
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
- NUNCA omitas ni resumas fechas, listas o datos específicos que aparezcan en la información; inclúyelos completos

Estilo de respuesta:
- Inicia con un saludo breve y amigable ("¡Hola!", "Claro, te ayudo", etc.) SOLO en el primer mensaje de la conversación, luego responde de forma natural sin saludos repetidos
- Responde de forma natural, como si conocieras esta información de memoria
- NUNCA menciones "según el contexto", "basándome en", "en las FAQs", o frases similares
- Sé conciso pero completo y cálido
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto"""

            user_prompt = f"""Preguntas frecuentes oficiales de VOAE:

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Si la pregunta coincide con una FAQ: Responde de forma amigable y luego usa exactamente esa información de forma natural
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
- NUNCA omitas ni resumas fechas, listas o datos específicos que aparezcan en la información; inclúyelos completos

Estilo de respuesta:
- Responde de forma natural, integrando la información disponible
- NUNCA menciones "según el contexto", "basándome en", "la información proporcionada", o frases similares
- Sé claro y organizado en respuestas con múltiples pasos
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto"""

            user_prompt = f"""Información oficial de VOAE (FAQs primero, luego documentos):

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Verifica que la respuesta esté en la información anterior
2. Prioriza información de las FAQs si está disponible
3. Responde de forma natural integrando la información relevante
4. Si NO encuentras la respuesta: Di honestamente que no tienes esa información"""

        else:  # docs_only
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
- Verifica que cada dato en tu respuesta esté explícitamente en la información
- NUNCA omitas ni resumas fechas, listas o datos específicos que aparezcan en la información; siempre inclúyelos completos en tu respuesta
- Incluye TODA la información relacionada con la pregunta, no solo la que coincida con las palabras exactas

Estilo de respuesta:
- Responde de forma natural, como si conocieras esta información de tu trabajo en VOAE
- NUNCA menciones "según el contexto", "basándome en", "la información proporcionada", o frases similares
- Estructura tus respuestas con claridad cuando sea necesario (pasos numerados, listas, etc.)
- Siempre di "la VOAE", nunca "VOAE" sola como sujeto"""

            user_prompt = f"""Información oficial de VOAE que conoces:

{context}

Pregunta del estudiante:
{query}

Instrucciones:
1. Verifica que la respuesta esté en la información anterior
2. Si SÍ está: Responde de forma natural y amigable, incluyendo todos los datos específicos (fechas, listas, requisitos, etc.) sin omitir ninguno
3. Si NO está: Di honestamente que no tienes esa información y recomienda contactar a VOAE directamente"""

        return system_prompt, user_prompt

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generate_response(
        self,
        query: str,
        context_documents: List[str],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        context_type: str = "docs_only",
        conversation_history: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        context = "\n\n---\n\n".join(context_documents)
        system_prompt, user_prompt = self._build_prompts(query, context, context_type)

        messages = []
        if conversation_history:
            for hist_user, hist_assistant in conversation_history[-5:]:
                messages.append({"role": "user", "content": hist_user})
                messages.append({"role": "assistant", "content": hist_assistant})
        messages.append({"role": "user", "content": user_prompt})

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": messages,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"].strip()
        except Exception as e:
            raise Exception(f"Error al llamar a Amazon Bedrock: {str(e)}") from e

    def simple_chat(
        self,
        message: str,
        temperature: float = 0.3,
        max_tokens: int = 500,
        system_prompt: str = None,
    ) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": message}],
        }
        if system_prompt:
            body["system"] = system_prompt

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"].strip()
        except Exception as e:
            raise Exception(f"Error al llamar a Amazon Bedrock: {str(e)}") from e
