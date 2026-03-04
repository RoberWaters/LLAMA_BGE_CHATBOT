"""
Chatbot RAG interactivo por consola
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatbot.chatbot import RAGChatbot


def print_separator():
    """Imprime una línea separadora"""
    print("\n" + "="*70 + "\n")


def main():
    """Función principal del chatbot"""
    # Parse argumentos
    parser = argparse.ArgumentParser(description="Chatbot RAG interactivo")
    parser.add_argument('--llm-provider', type=str, default='bedrock', choices=['bedrock'],
                        help='Proveedor de LLM (default: bedrock)')
    args = parser.parse_args()

    print_separator()
    print("🎓 CHATBOT VOAE - Vicerrectoría de Orientación y Asuntos Estudiantiles")
    print_separator()
    print("Inicializando chatbot...")

    try:
        # Inicializar chatbot con historial de 5 mensajes
        chatbot = RAGChatbot(max_history=5, llm_provider=args.llm_provider)

        print("✅ Chatbot listo!")
        print_separator()

        # Mostrar estadísticas
        stats = chatbot.get_stats()
        print("📊 Estadísticas del Sistema:")
        print(f"  • Documentos: {stats['total_documents']}")
        print(f"  • Almacenamiento: ChromaDB")
        print(f"  • Ruta: {stats['storage_path']}")
        print(f"  • Modelo embeddings: {stats['embedder_model']}")
        print(f"  • Modelo LLM: {stats['llm_model']}")
        print(f"  • Historial: últimos {stats['max_history']} mensajes")

        print_separator()
        print("💡 Instrucciones:")
        print("  • Escribe tus preguntas y presiona Enter")
        print("  • El sistema busca primero en FAQs (90%/80% umbral)")
        print("  • Si no hay match en FAQs, busca en documentos generales")
        print("  • Comandos especiales:")
        print("    - 'salir' o 'exit': Terminar el chat")
        print("    - 'limpiar': Borrar historial de conversación")
        print("    - 'stats': Ver estadísticas del sistema")
        print_separator()

        # Loop principal del chat
        while True:
            try:
                # Obtener pregunta del usuario
                user_input = input("🧑 Tú: ").strip()

                # Comandos especiales
                if user_input.lower() in ['salir', 'exit', 'quit', 'q']:
                    print("\n👋 ¡Hasta luego!\n")
                    break

                if user_input.lower() == 'limpiar':
                    chatbot.clear_history()
                    print("\n✅ Historial limpiado\n")
                    continue

                if user_input.lower() == 'stats':
                    stats = chatbot.get_stats()
                    print(f"\n📊 Documentos: {stats['total_documents']} | "
                          f"Historial: {stats['current_history_length']}/{stats['max_history']}\n")
                    continue

                if not user_input:
                    continue

                # Obtener respuesta del chatbot
                result = chatbot.chat(
                    user_message=user_input,
                    top_k=4,
                    temperature=0.7,
                    use_rag=True
                )

                # Mostrar respuesta
                print(f"\n🎓 VOAE: {result['answer']}\n")

                # Mostrar información de match (si disponible)
                if result.get("match_type"):
                    match_icons = {
                        'high': '🎯',
                        'medium': '🔶',
                        'low': '📄',
                        'none': '❌'
                    }
                    match_type = result.get("match_type", "low")
                    icon = match_icons.get(match_type, "📄")

                    if match_type == 'high':
                        print(f"{icon} Match: FAQ (similitud: {result.get('best_faq_similarity', 0):.1%})")
                    elif match_type == 'medium':
                        print(f"{icon} Match: FAQ + Documentos (similitud FAQ: {result.get('best_faq_similarity', 0):.1%})")
                    elif match_type == 'low':
                        print(f"{icon} Match: Solo documentos generales")

                # Mostrar fuentes si están disponibles
                if result.get("relevant_documents"):
                    print("\n📚 Fuentes consultadas:")
                    for i, doc in enumerate(result["relevant_documents"][:5], 1):
                        doc_type = doc.get('type', 'document')
                        type_icon = '❓' if doc_type == 'faq' else '📄'
                        print(f"  {i}. {type_icon} {doc['filename']} (similitud: {doc['similarity']:.1%})")
                    print()

            except KeyboardInterrupt:
                print("\n\n👋 ¡Hasta luego!\n")
                break

            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")
                continue

        # Cerrar conexión
        chatbot.close()

    except Exception as e:
        print(f"\n❌ Error al inicializar el chatbot: {str(e)}")
        print("\nVerifica que:")
        print("  1. El archivo .env esté configurado correctamente")
        print("  2. SQL Server esté accesible")
        print("  3. Hayas ejecutado la ingestion de documentos")
        sys.exit(1)


if __name__ == "__main__":
    main()
