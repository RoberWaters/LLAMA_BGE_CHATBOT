# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG (Retrieval-Augmented Generation) system that uses BGE-M3 embeddings, SQL Server for vector storage, and either Groq API or DeepSeek API as the LLM. The system processes markdown documents, generates embeddings, stores them in SQL Server, and enables semantic search to answer user queries.

**Key features:**
- Document ingestion from markdown files
- BGE-M3 embeddings (1024 dimensions)
- SQL Server vector storage (VARBINARY format)
- Groq API (ultra-fast, recommended) or DeepSeek API for LLM
- Interactive chatbot with conversation history
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

# Configure environment variables (copy .env.example to .env)
cp .env.example .env
# Then edit .env with your credentials
```

### Document Ingestion
```bash
# Basic ingestion (processes .md files from data/docs/)
python src/main.py --ingest

# Ingestion with chunking (splits large documents)
python src/main.py --ingest --chunk

# Force re-processing of existing documents
python src/main.py --ingest --force
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
```

### System Management
```bash
# View system statistics
python src/main.py --stats

# Clear database
python src/main.py --reset

# Test individual components
python src/embeddings/embedder.py
python src/database/connection.py
python src/llm/deepseek_client.py
python src/llm/groq_client.py
python src/rag/retriever.py
```

## Architecture

### Core Components

**RAGPipeline** (`src/rag/rag_pipeline.py`)
- Main orchestrator for the entire RAG system
- Initializes all components (embedder, database, LLM)
- Handles both ingestion and query workflows
- LLM provider can be switched between "groq" and "deepseek"

**Embedder** (`src/embeddings/embedder.py`)
- Uses BGE-M3 model from sentence-transformers
- Generates 1024-dimensional float32 embeddings
- Critical methods:
  - `generate_embedding(text)`: Creates embedding for single text
  - `embedding_to_bytes()`: Converts numpy array to VARBINARY for SQL Server
  - `bytes_to_embedding()`: Converts VARBINARY back to numpy array

**DatabaseConnection** (`src/database/connection.py`)
- Manages SQL Server connection via pyodbc
- Automatically creates Documents table if not exists
- Table schema:
  ```sql
  CREATE TABLE Documents (
      id INT PRIMARY KEY IDENTITY(1,1),
      filename NVARCHAR(255),
      content NVARCHAR(MAX),
      embedding VARBINARY(MAX)
  )
  ```

**DocumentRepository** (`src/database/repository.py`)
- CRUD operations for documents
- Key methods: `insert_document()`, `get_all_documents()`, `document_exists()`, `count_documents()`

**DocumentRetriever** (`src/rag/retriever.py`)
- Semantic search using cosine similarity
- Retrieves ALL documents from DB, calculates similarity in Python (not SQL)
- Returns top-k most relevant documents with similarity scores

**LLM Clients**
- `GroqClient` (`src/llm/groq_client.py`): Ultra-fast responses using Llama 3.3 70B
- `DeepSeekClient` (`src/llm/deepseek_client.py`): Alternative with good quality
- Both implement `generate_response()` for RAG and `simple_chat()` for basic chat

**RAGChatbot** (`src/chatbot/chatbot.py`)
- Wraps RAGPipeline with conversation history
- Maintains last N messages (default: 5)
- Supports both RAG-based and history-only chat modes

### Data Flow

**Ingestion Pipeline:**
1. Load .md files from `data/docs/`
2. Clean/preprocess text
3. Generate BGE-M3 embeddings (1024-dim float32)
4. Convert embeddings to bytes: `embedding.astype('float32').tobytes()`
5. Store in SQL Server with filename and content

**Query Pipeline:**
1. Convert user question to embedding
2. Fetch ALL documents from SQL Server
3. Convert VARBINARY embeddings back to numpy arrays
4. Calculate cosine similarity for each document in Python
5. Sort by similarity, select top-k
6. Build RAG prompt with context documents
7. Send to Groq/DeepSeek API
8. Return response with sources

### Critical Implementation Details

**Embedding Storage/Retrieval:**
```python
# Store
embedding_bytes = embedding.astype('float32').tobytes()

# Retrieve
embedding_array = np.frombuffer(embedding_bytes, dtype='float32')
```

**RAG Prompt Pattern:**
Both LLM clients use strict instructions to only answer from context:
```python
system_prompt = "Answer ONLY based on provided context. Don't use external knowledge."
user_prompt = f"Context:\n{documents}\n\nQuestion:\n{query}"
```

**LLM Provider Selection:**
The system defaults to Groq for speed but can use DeepSeek:
```python
# In RAGPipeline.__init__() or RAGChatbot.__init__()
RAGPipeline(llm_provider="groq")   # Default, ultra-fast
RAGPipeline(llm_provider="deepseek")  # Alternative
```

**Conversation History:**
RAGChatbot maintains history as list of tuples:
```python
conversation_history = [(user_msg1, bot_msg1), (user_msg2, bot_msg2), ...]
# Automatically limited to max_history entries
```

## Environment Variables

Required in `.env`:
```
# SQL Server
DB_HOST=localhost
DB_PORT=1433
DB_NAME=RAG_Database
DB_USER=sa
DB_PASSWORD=YourPassword123

# LLM (choose one or both)
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## Key Files

- `src/main.py`: CLI entry point for ingestion/queries
- `src/chat.py`: Interactive chatbot entry point
- `src/rag/rag_pipeline.py`: Main orchestrator
- `src/chatbot/chatbot.py`: Chatbot with conversation history
- `src/embeddings/embedder.py`: BGE-M3 embedding generation
- `src/database/repository.py`: Database CRUD operations
- `src/llm/groq_client.py`: Groq API client (recommended)
- `src/llm/deepseek_client.py`: DeepSeek API client
- `src/rag/retriever.py`: Semantic search with cosine similarity

## Error Handling Notes

All modules handle common errors:
- Database connection failures (check SQL Server is running, credentials correct)
- Missing API keys (verify `.env` file exists and has correct keys)
- Empty database (run `--ingest` first before queries)
- Model download (BGE-M3 is ~2GB, downloads to `~/.cache/huggingface/` on first run)
