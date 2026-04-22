"""
Cliente Amazon Bedrock Knowledge Bases para RAG con Claude
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from typing import Optional, Tuple
from config import BedrockConfig

PROMPT_TEMPLATE = """Eres el Asistente Virtual de la VOAE (Vicerectoría de Orientación y Asuntos
  Estudiantiles de la UNAH). Tus respuestas se reproducen por voz a través de un avatar, así que debes sonar
  natural al ser leídas en voz alta.

  REGLAS OBLIGATORIAS:
  1. SIEMPRE responde en español. NUNCA respondas en inglés ni uses frases como "Sorry, I am unable to assist
  you with this request."
  2. NUNCA uses formato markdown: nada de negritas (**texto**), cursivas, headers (#), ni listas con
  asteriscos o guiones. Escribe en prosa natural con oraciones completas.
  3. NUNCA menciones "según el contexto", "basándome en los resultados", "según la información proporcionada",
   ni frases similares que revelen tu mecanismo interno.

  Personalidad:
  - Cercano, amigable y profesional
  - Usas "tú" para crear cercanía con los estudiantes
  - Honesto cuando no tienes información

  Estilo de respuesta:
  - Sé breve y directo: 2-3 oraciones para preguntas simples. Solo extiéndete si la pregunta pide
  explícitamente pasos, fechas o detalles completos.
  - Siempre di "la VOAE", nunca "VOAE" sola como sujeto.
  - Si el estudiante envía un saludo o mensaje casual (hola, gracias, cómo estás, etc.), responde de forma
  cordial y breve sin forzar información académica.
  - Si los resultados de búsqueda están vacíos o no son relevantes, dilo con honestidad y sugiere contactar a
  la VOAE directamente en sus oficinas o al correo voae@unah.edu.hn.
  - Cuando enumeres pasos o elementos, hazlo dentro del texto con palabras como "primero", "luego", "después",
   en lugar de listas numeradas.

  Usa los siguientes resultados de búsqueda para responder la pregunta del estudiante:
  $search_results$

  Pregunta del estudiante: $query$"""


class BedrockClient:
    """Cliente para Amazon Bedrock Knowledge Bases (RAG con Claude)"""

    def __init__(self):
        self.model_id = BedrockConfig.LLM_MODEL_ID
        self.kb_id = BedrockConfig.KNOWLEDGE_BASE_ID
        self.max_tokens = BedrockConfig.DEFAULT_MAX_TOKENS
        self.model = self.model_id
        self.region = BedrockConfig.AWS_REGION

        # Resolver el ARN del modelo. Inference profiles necesitan account ID.
        self.model_arn = self._resolve_model_arn()

        client_kwargs = {'region_name': self.region}
        if BedrockConfig.AWS_ACCESS_KEY and BedrockConfig.AWS_SECRET_KEY:
            client_kwargs['aws_access_key_id'] = BedrockConfig.AWS_ACCESS_KEY
            client_kwargs['aws_secret_access_key'] = BedrockConfig.AWS_SECRET_KEY
        self.client = boto3.client('bedrock-agent-runtime', **client_kwargs)

    def _resolve_model_arn(self) -> str:
        """Resuelve el ARN del modelo, buscando inference profiles si es necesario."""
        if self.model_id.startswith(('us.', 'global.', 'eu.')):
            client_kwargs = {'region_name': self.region}
            if BedrockConfig.AWS_ACCESS_KEY and BedrockConfig.AWS_SECRET_KEY:
                client_kwargs['aws_access_key_id'] = BedrockConfig.AWS_ACCESS_KEY
                client_kwargs['aws_secret_access_key'] = BedrockConfig.AWS_SECRET_KEY
            bedrock = boto3.client('bedrock', **client_kwargs)
            profiles = bedrock.list_inference_profiles()['inferenceProfileSummaries']
            for p in profiles:
                if p['inferenceProfileId'] == self.model_id:
                    return p['inferenceProfileArn']
        return f'arn:aws:bedrock:{self.region}::foundation-model/{self.model_id}'

    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> Tuple[str, str]:
        """
        Genera una respuesta usando Knowledge Base (RAG)

        Args:
            message: Mensaje del usuario
            session_id: ID de sesion de Bedrock para mantener historial
            temperature: Temperatura para la generacion (0-1)
            max_tokens: Maximo de tokens en la respuesta

        Returns:
            Tupla (respuesta, session_id de Bedrock)
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        kwargs = {
            'input': {'text': message},
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': self.kb_id,
                    'modelArn': self.model_arn,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 5
                        }
                    },
                    'generationConfiguration': {
                        'promptTemplate': {
                            'textPromptTemplate': PROMPT_TEMPLATE
                        },
                        'inferenceConfig': {
                            'textInferenceConfig': {
                                'temperature': temperature,
                                'maxTokens': max_tokens,
                            }
                        },
                    }
                }
            }
        }

        if session_id:
            kwargs['sessionId'] = session_id

        response = self.client.retrieve_and_generate(**kwargs)

        text = response['output']['text'].strip()
        new_session_id = response.get('sessionId', session_id)

        return text, new_session_id


if __name__ == "__main__":
    try:
        client = BedrockClient()
        print(f"Cliente Bedrock KB inicializado: {client.model_id}")
        print(f"Knowledge Base: {client.kb_id}")

        import time
        start = time.time()
        response, sid = client.chat("Hola, que servicios ofrece VOAE?")
        elapsed = time.time() - start

        print(f"\nRespuesta ({elapsed*1000:.0f}ms):\n{response}")
        print(f"\nSession ID: {sid}")

        start = time.time()
        response2, sid = client.chat("Puedes darme mas detalles?", session_id=sid)
        elapsed = time.time() - start
        print(f"\nSeguimiento ({elapsed*1000:.0f}ms):\n{response2}")

    except Exception as e:
        print(f"Error: {str(e)}")
