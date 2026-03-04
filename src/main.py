"""
Punto de entrada principal del sistema RAG
"""
import argparse
import sys
from pathlib import Path

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent))

from rag.rag_pipeline import RAGPipeline
from config import S3Config


def print_banner():
    """Imprime el banner del sistema"""
    print("\n" + "=" * 60)
    print("  SISTEMA RAG - Amazon Bedrock (Claude + Titan)")
    print("=" * 60 + "\n")


def ingest_mode(pipeline: RAGPipeline, args):
    """
    Modo de ingestion de documentos

    Args:
        pipeline: Pipeline RAG
        args: Argumentos de línea de comandos
    """
    print("Modo: INGESTION DE DOCUMENTOS\n")

    try:
        pipeline.ingest_documents(
            chunk_documents=args.chunk,
            skip_existing=not args.force
        )
    except Exception as e:
        print(f"\nERROR: Error durante la ingestion: {str(e)}")
        sys.exit(1)


def query_mode(pipeline: RAGPipeline, args):
    """
    Modo de consulta

    Args:
        pipeline: Pipeline RAG
        args: Argumentos de línea de comandos
    """
    if args.query:
        # Consulta única desde argumentos
        question = args.query
        result = pipeline.query(
            question=question,
            top_k=args.top_k,
            temperature=args.temperature
        )

        print(f"\n{'=' * 60}")
        print("RESPUESTA:")
        print(f"{'=' * 60}\n")
        print(result['answer'])

        if args.show_sources and result['relevant_documents']:
            print(f"\n{'=' * 60}")
            print("FUENTES CONSULTADAS:")
            print(f"{'=' * 60}\n")

            for i, doc in enumerate(result['relevant_documents'], 1):
                print(f"{i}. {doc['filename']} (similitud: {doc['similarity']:.4f})")

    else:
        # Modo interactivo
        print("Modo: CONSULTA INTERACTIVA")
        print("Escribe 'salir' o 'exit' para terminar\n")

        while True:
            try:
                question = input("\n💬 Tu pregunta: ").strip()

                if question.lower() in ['salir', 'exit', 'quit', 'q']:
                    print("\n¡Hasta luego!")
                    break

                if not question:
                    continue

                result = pipeline.query(
                    question=question,
                    top_k=args.top_k,
                    temperature=args.temperature
                )

                print(f"\n🤖 Respuesta:\n{result['answer']}")

                if args.show_sources and result['relevant_documents']:
                    print(f"\n📚 Fuentes:")
                    for i, doc in enumerate(result['relevant_documents'], 1):
                        print(f"  {i}. {doc['filename']} ({doc['similarity']:.4f})")

            except KeyboardInterrupt:
                print("\n\n¡Hasta luego!")
                break
            except Exception as e:
                print(f"\nERROR: Error: {str(e)}")


def stats_mode(pipeline: RAGPipeline):
    """
    Muestra estadísticas del sistema

    Args:
        pipeline: Pipeline RAG
    """
    print("Modo: ESTADÍSTICAS DEL SISTEMA\n")

    stats = pipeline.get_stats()

    print(f"Documentos totales: {stats['total_documents']}")
    print(f"Almacenamiento: ChromaDB")
    print(f"Ruta: {stats['storage_path']}")
    print(f"Modelo de embeddings: {stats['embedder_model']}")
    print(f"Modelo LLM: {stats['llm_model']}")


def reset_mode(pipeline: RAGPipeline):
    """
    Limpia la base de datos

    Args:
        pipeline: Pipeline RAG
    """
    print("Modo: LIMPIAR BASE DE DATOS\n")

    confirm = input("⚠️  ¿Estás seguro de eliminar todos los documentos? (s/n): ")

    if confirm.lower() in ['s', 'si', 'yes', 'y']:
        pipeline.reset_database()
        print("✅ Base de datos limpiada exitosamente")
    else:
        print("Operación cancelada")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Sistema RAG con BGE-M3, SQL Server y DeepSeek",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Ingerir documentos
  python src/main.py --ingest

  # Ingerir documentos dividiéndolos en chunks
  python src/main.py --ingest --chunk

  # Hacer una consulta
  python src/main.py --query "¿Qué es Python?"

  # Modo interactivo
  python src/main.py

  # Mostrar estadísticas
  python src/main.py --stats

  # Limpiar base de datos
  python src/main.py --reset
        """
    )

    # Modos de operación
    parser.add_argument('--ingest', action='store_true',
                        help='Modo ingestion: procesa y guarda documentos')
    parser.add_argument('--query', type=str,
                        help='Consulta al sistema RAG')
    parser.add_argument('--stats', action='store_true',
                        help='Muestra estadísticas del sistema')
    parser.add_argument('--reset', action='store_true',
                        help='Limpia la base de datos')

    # Opciones de ingestion
    parser.add_argument('--chunk', action='store_true',
                        help='Divide documentos en chunks durante ingestion')
    parser.add_argument('--force', action='store_true',
                        help='Fuerza re-procesamiento de documentos existentes')

    # Opciones de consulta
    parser.add_argument('--top-k', type=int, default=3,
                        help='Número de documentos relevantes a recuperar (default: 3)')
    parser.add_argument('--temperature', type=float, default=0.7,
                        help='Temperatura para el LLM (default: 0.7)')
    parser.add_argument('--show-sources', action='store_true',
                        help='Muestra las fuentes consultadas')

    # Opciones de sistema
    parser.add_argument('--llm-provider', type=str, default='bedrock', choices=['bedrock'],
                        help='Proveedor de LLM (default: bedrock)')
    parser.add_argument('--s3-bucket', type=str, default=None,
                        help=f'Bucket S3 con documentos y ChromaDB (default: S3Config.BUCKET_NAME)')
    parser.add_argument('--s3-prefix', type=str, default=None,
                        help=f'Prefijo S3 para documentos .md (default: S3Config.DOCS_PREFIX)')

    args = parser.parse_args()

    # Banner
    print_banner()

    # Inicializar pipeline
    try:
        pipeline = RAGPipeline(
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix,
            llm_provider=args.llm_provider,
        )
    except Exception as e:
        print(f"ERROR: Error al inicializar el pipeline: {str(e)}")
        print("\nVerifica que:")
        print("  1. El archivo .env existe y tiene todas las variables")
        print("  2. SQL Server está accesible")
        print("  3. Las dependencias están instaladas (pip install -r requirements.txt)")
        sys.exit(1)

    try:
        # Ejecutar según el modo
        if args.ingest:
            ingest_mode(pipeline, args)

        elif args.stats:
            stats_mode(pipeline)

        elif args.reset:
            reset_mode(pipeline)

        else:
            # Modo consulta (interactivo o única)
            query_mode(pipeline, args)

    except Exception as e:
        print(f"\nERROR: Error: {str(e)}")
        sys.exit(1)

    finally:
        # Cerrar conexión
        pipeline.close()


if __name__ == "__main__":
    main()
