#!/usr/bin/env python
"""Script de prueba para el chatbot con Groq"""
import sys
sys.path.insert(0, 'src')

from chatbot.chatbot import RAGChatbot
import time

print("="*70)
print("🧪 TEST: Chatbot RAG con Groq API")
print("="*70)

# Inicializar chatbot con Groq
chatbot = RAGChatbot(llm_provider="groq")

# Hacer una consulta
pregunta = "¿Qué información tienes sobre becas?"
print(f"\n💬 Pregunta: {pregunta}\n")

start = time.time()
resultado = chatbot.chat(pregunta)
end = time.time()

print(f"🤖 Respuesta:\n{resultado['answer']}\n")

if resultado.get('relevant_documents'):
    print("📚 Fuentes:")
    for i, doc in enumerate(resultado['relevant_documents'], 1):
        print(f"  {i}. {doc['filename']} (similitud: {doc['similarity']:.3f})")

print(f"\n⚡ Tiempo total: {(end-start)*1000:.0f}ms")
print("\n✅ Test completado exitosamente!")

chatbot.close()
