# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG (Retrieval-Augmented Generation) system using BGE-M3 embeddings with ChromaDB vector storage and Groq/DeepSeek LLMs. The system processes markdown documents, generates embeddings, stores them in ChromaDB, and enables semantic search to answer user queries.

**Key features:**
- Document ingestion from markdown files
- BGE-M3 embeddings (1024 dimensions, float32)
- ChromaDB vector database with HNSW indexing
- Groq API (ultra-fast, recommended, uses Llama 3.3 70B) or DeepSeek API for LLM
- Interactive chatbot with conversation history (last 5 messages)
- CLI for queries and document management

## Common Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (only LLM API key needed)
cp .env.example .env
# Then edit .env with your Groq or DeepSeek API key
```

### Document Ingestion
```bash
# Basic ingestion (processes .md files from data/docs/)
python src/main.py --ingest

# Ingestion with chunking (splits large documents)
python src/main.py --ingest --chunk

# Force re-processing of existing documents
python src/main.py --ingest --force

# Use DeepSeek instead of Groq
python src/main.py --ingest --llm-provider deepseek
```

### Querying
```bash
# Single query
python src/main.py --query "your question"

# Query with sources displayed
python src/main.py --query "your question" --show-sources

# Interactive mode (default when no flags provided)
python src/main.py

# Interactive chatbot with history (recommended)
python src/chat.py

# Advanced query options
python src/main.py --query "your question" --top-k 5 --temperature 0.7

# Use DeepSeek instead of Groq
python src/main.py --query "your question" --llm-provider deepseek
python src/chat.py --llm-provider deepseek
```

### System Management
```bash
# View system statistics
python src/main.py --stats

# Clear database
python src/main.py --reset

# Test individual components
python src/embeddings/embedder.py
python src/llm/groq_client.py
python src/llm/deepseek_client.py
python src/rag/retriever.py
```

## Architecture

### Core Components

**RAGPipeline** (`src/rag/rag_pipeline.py`)
- Main orchestrator for the entire RAG system
- Initializes all components: embedder, ChromaDB storage, document repository, ingestion, retriever, and LLM client
- Handles both ingestion and query workflows
- LLM provider switchable via constructor parameter: `llm_provider="groq"` (default) or `llm_provider="deepseek"`
- Key methods:
  - `ingest_documents(chunk_documents, skip_existing)`: Processes and stores documents
  - `query(question, top_k, temperature, max_tokens)`: Runs full RAG pipeline for a query
  - `get_stats()`: Returns system statistics
  - `reset_database()`: Clears all documents

**Embedder** (`src/embeddings/embedder.py`)
- Uses BGE-M3 model from sentence-transformers
- Generates 1024-dimensional float32 embeddings
- Model downloads to `~/.cache/huggingface/` (~2GB) on first run
- Critical methods:
  - `generate_embedding(text)`: Creates embedding for single text
  - `embedding_to_bytes()`: Converts numpy array to bytes (for legacy compatibility)
  - `bytes_to_embedding()`: Converts bytes back to numpy array (for legacy compatibility)

**ChromaVectorStore** (`src/database/chroma_vector_store.py`)
- Vector database implementation using ChromaDB
- Automatic persistence to disk at `data/chroma/`
- Uses HNSW algorithm with cosine similarity metric
- Stores embeddings as lists (converted from numpy float32 arrays)
- Uses filename-based IDs (sanitized by replacing special characters)
- Zero configuration required
- Key methods:
  - `add_document(filename, content, embedding)`: Adds document with embedding to collection
  - `get_all_documents()`: Retrieves all documents with embeddings
  - `search_similar(query_embedding, top_k)`: Finds similar documents using HNSW, returns (id, filename, content, similarity_score)
  - `document_exists(filename)`: Checks if document already exists
  - `count_documents()`: Returns total document count
  - `delete_all_documents()`: Clears collection by deleting and recreating it

**DocumentRepository** (`src/database/repository.py`)
- CRUD operations abstraction layer over ChromaVectorStore
- Provides cleaner interface for document operations
- Key methods: `insert_document()`, `get_all_documents()`, `document_exists()`, `count_documents()`, `delete_all_documents()`

**DocumentIngestion** (`src/ingestion/ingest_docs.py`)
- Loads markdown files from `data/docs/` directory
- Cleans and preprocesses text
- Optionally chunks large documents if `chunk_documents=True`
- Returns list of (filename, content) tuples

**DocumentRetriever** (`src/rag/retriever.py`)
- Semantic search implementation
- Retrieves all documents from repository and calculates cosine similarity against query embedding
- Returns top-k most relevant documents with cosine similarity scores
- Method: `retrieve_relevant_documents(query, top_k)` returns list of (filename, content, similarity_score) tuples
- Note: Currently implements manual similarity calculation rather than using ChromaDB's built-in search

**LLM Clients**
- `GroqClient` (`src/llm/groq_client.py`): Ultra-fast responses using Llama 3.3 70B (model: "llama-3.3-70b-versatile")
- `DeepSeekClient` (`src/llm/deepseek_client.py`): Alternative with good quality (model: "deepseek-chat")
- Both implement:
  - `generate_response(query, context_documents, temperature, max_tokens)`: RAG-based response generation with strict context-only instructions
  - `simple_chat(message, temperature)`: Basic chat without RAG context

**RAGChatbot** (`src/chatbot/chatbot.py`)
- Wraps RAGPipeline with conversation history management
- Maintains last N messages as list of (user_message, assistant_message) tuples (default: 5)
- Automatically truncates history when exceeding max_history
- Supports both RAG-based (`use_rag=True`) and history-only (`use_rag=False`) chat modes
- Key methods:
  - `chat(user_message, top_k, temperature, use_rag)`: Process message and generate response
  - `clear_history()`: Clears conversation history
  - `get_history()`: Returns copy of conversation history
  - `set_max_history(max_history)`: Updates max history size

### Data Flow

**Ingestion Pipeline:**
1. Load .md files from `data/docs/`
2. Clean/preprocess text (remove extra whitespace, normalize line breaks)
3. Generate BGE-M3 embeddings (1024-dim float32)
4. Convert embedding to list for ChromaDB
5. Add to ChromaDB collection with metadata (filename, content)

**Query Pipeline:**
1. Convert user question to embedding
2. Retrieve all documents with their embeddings from ChromaDB
3. Calculate cosine similarity between query embedding and each document embedding
4. Sort by similarity and select top-k documents
5. Build RAG prompt with context documents
6. Send to Groq/DeepSeek API
7. Return response with sources

### Critical Implementation Details

**Embedding Storage/Retrieval (ChromaDB):**
```python
# Store - converts numpy float32 array to list
embedding_list = embedding.astype('float32').tolist()
doc_id = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")  # Sanitize ID
collection.add(embeddings=[embedding_list], documents=[content],
               metadatas=[{"filename": filename}], ids=[doc_id])

# Retrieve all documents
results = collection.get(include=["embeddings", "documents", "metadatas"])
# Returns: results['embeddings'][i] is embedding as list
#          results['documents'][i] is document content
#          results['metadatas'][i] is metadata dict with 'filename' key

# Direct search with ChromaDB (available but not currently used by retriever)
results = collection.query(query_embeddings=[query_list], n_results=top_k,
                          include=["documents", "metadatas", "distances"])
# Returns: results['distances'][0][i] is cosine distance (convert to similarity: 1 - distance)
```

**RAG Prompt Pattern:**
Both LLM clients use strict instructions to only answer from context:
```python
system_prompt = "Answer ONLY based on provided context. Don't use external knowledge."
user_prompt = f"Context:\n{documents}\n\nQuestion:\n{query}"
```

**LLM Provider Selection:**
The system defaults to Groq but can use DeepSeek:
```python
# In RAGPipeline.__init__() or RAGChatbot.__init__()
RAGPipeline(llm_provider="groq")    # Default: ultra-fast, Llama 3.3 70B
RAGPipeline(llm_provider="deepseek")  # Alternative

# CLI flags
python src/main.py --llm-provider deepseek
python src/chat.py --llm-provider groq
```

**Conversation History:**
RAGChatbot maintains history as list of tuples:
```python
conversation_history = [(user_msg1, bot_msg1), (user_msg2, bot_msg2), ...]
# Automatically limited to max_history entries
# When limit exceeded: conversation_history = conversation_history[-max_history:]
```

**Document ID Generation:**
ChromaDB requires string IDs, generated by sanitizing filenames:
```python
doc_id = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
# Used for both storage and retrieval operations
```

## Environment Variables

Required in `.env` (create from `.env.example`):
```
# LLM API (at least one required, both can be configured)
GROQ_API_KEY=your_groq_api_key_here        # Recommended: ultra-fast, 14,400 requests/day free
DEEPSEEK_API_KEY=your_deepseek_api_key_here  # Alternative

# Legacy SQL Server vars (not used - system uses ChromaDB)
# DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD are ignored
```

**Notes**:
- **ChromaDB**: No database credentials needed. Data automatically stored in `data/chroma/`
- **No SQL Server, ODBC drivers, or database setup required** - system uses ChromaDB
- `.env.example` contains SQL Server config but these are legacy remnants - they are not used
- Only API key for chosen LLM provider is required

## Key Files

- `src/main.py`: CLI entry point for ingestion/queries
- `src/chat.py`: Interactive chatbot entry point
- `src/rag/rag_pipeline.py`: Main orchestrator
- `src/chatbot/chatbot.py`: Chatbot with conversation history
- `src/embeddings/embedder.py`: BGE-M3 embedding generation
- `src/database/repository.py`: CRUD operations abstraction
- `src/database/chroma_vector_store.py`: ChromaDB backend
- `src/llm/groq_client.py`: Groq API client (recommended, ultra-fast)
- `src/llm/deepseek_client.py`: DeepSeek API client
- `src/rag/retriever.py`: Semantic search with cosine similarity
- `src/ingestion/ingest_docs.py`: Document loading and preprocessing

## Error Handling Notes

All modules handle common errors:
- **ChromaDB issues**: Delete `data/chroma/` and re-run ingestion if corruption occurs
- **Missing API keys**: Verify `.env` file exists and has correct keys for chosen LLM provider
- **Empty storage**: Run `--ingest` first before queries
- **Model download**: BGE-M3 is ~2GB, downloads to `~/.cache/huggingface/` on first run

## ChromaDB Details

**Storage Location**: `data/chroma/` (created automatically)
**Collection Name**: `documents`
**Similarity Metric**: Cosine similarity (configured via `metadata={"hnsw:space": "cosine"}`)
**Index Type**: HNSW (Hierarchical Navigable Small World)
**Persistence**: Automatic to disk via `PersistentClient`
**Distance to Similarity Conversion**: `similarity = 1.0 - distance`

**Why ChromaDB?**
- Zero configuration required - no database setup
- Designed specifically for embeddings
- Fast approximate nearest neighbor search with HNSW algorithm
- Automatic persistence to disk
- Metadata integrated with vectors (stored together)
- Excellent for both development and production
- No server process needed - embedded database

**Important ChromaDB Behaviors:**
- `.query()` returns results in format: `{'ids': [[...]], 'distances': [[...]], 'documents': [[...]], 'metadatas': [[...]]}`
- Results are double-nested lists (first index is query number, second is result number)
- Distance values are cosine distances (0 = identical, 2 = opposite)
- Collection persistence is automatic - no explicit save/commit needed
- Deleting collection and recreating is the fastest way to clear all documents

## Implementation Notes

**Retriever Architecture:**
The current retriever implementation (src/rag/retriever.py) retrieves all documents and manually calculates cosine similarity. For better performance with large document collections, consider using ChromaDB's built-in `.query()` method in `ChromaVectorStore.search_similar()`.

**Text Chunking:**
When using `--chunk` flag during ingestion, documents are split into overlapping chunks (default: 1000 chars with 200 char overlap). Chunks are named as `filename_chunk_N`. This improves retrieval quality for large documents.
