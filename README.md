# Sistema RAG - BGE-M3 + SQL Server + Groq/DeepSeek

Sistema completo de Recuperación Aumentada por Generación (RAG) que utiliza:
- **BGE-M3** para generar embeddings semánticos
- **SQL Server** para almacenar documentos y vectores
- **Groq API** (ultra-rápido, 10x más rápido) o **DeepSeek API** como modelo de lenguaje

## 📋 Características

- ✅ Procesamiento de documentos Markdown (.md)
- ✅ Generación de embeddings con BGE-M3
- ✅ Almacenamiento vectorial en SQL Server
- ✅ Búsqueda semántica con similitud coseno
- ✅ Generación de respuestas contextuales con DeepSeek
- ✅ **Chatbot interactivo por consola** 🆕
- ✅ **Historial de conversación (últimos 5 mensajes)** 🆕
- ✅ Modo de consultas únicas CLI
- ✅ División opcional de documentos en chunks
- ✅ Manejo robusto de errores

## 🏗️ Estructura del Proyecto

```
rag_system/
│
├── data/
│   └── docs/              # Archivos .md para ingestion
│
├── src/
│   ├── embeddings/
│   │   └── embedder.py    # Generación de embeddings BGE-M3
│   ├── database/
│   │   ├── connection.py  # Conexión a SQL Server
│   │   └── repository.py  # Operaciones CRUD
│   ├── ingestion/
│   │   └── ingest_docs.py # Carga y preprocesamiento
│   ├── rag/
│   │   ├── retriever.py   # Búsqueda semántica
│   │   └── rag_pipeline.py # Pipeline completo
│   ├── llm/
│   │   └── deepseek_client.py # Cliente DeepSeek API
│   ├── chatbot/
│   │   └── chatbot.py     # Chatbot con historial 🆕
│   ├── chat.py            # Chatbot interactivo de consola 🆕
│   └── main.py            # Punto de entrada CLI
│
├── .env.example           # Template de variables de entorno
├── requirements.txt       # Dependencias
├── README.md              # Esta documentación
└── CLAUDE.md              # Guía para Claude Code
```

## 🚀 Instalación

### 1. Clonar o descargar el proyecto

```bash
cd rag_system
```

### 2. Crear entorno virtual

```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar SQL Server

Necesitas tener SQL Server instalado y accesible. El sistema creará automáticamente la tabla `Documents` con el siguiente esquema:

```sql
CREATE TABLE Documents (
    id INT PRIMARY KEY IDENTITY(1,1),
    filename NVARCHAR(255),
    content NVARCHAR(MAX),
    embedding VARBINARY(MAX)
)
```

### 5. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y configura tus credenciales:

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

```env
# SQL Server
DB_HOST=localhost
DB_PORT=1433
DB_NAME=RAG_Database
DB_USER=sa
DB_PASSWORD=TuPassword123

# LLM API - Usa Groq (recomendado) o DeepSeek
# Groq API (ultra-rápido, 14,400 requests/día gratis)
GROQ_API_KEY=tu_groq_api_key_aqui

# DeepSeek API (alternativa más lenta pero buena calidad)
DEEPSEEK_API_KEY=tu_deepseek_api_key_aqui
```

**Obtener API Key de Groq** (Recomendado - Ultra Rápido ⚡):
1. Visita [https://console.groq.com/](https://console.groq.com/)
2. Crea una cuenta gratuita
3. Ve a API Keys
4. Genera una nueva API key
5. Cópiala en el archivo `.env` como `GROQ_API_KEY`

**Obtener API Key de DeepSeek** (Alternativa):
1. Visita [https://platform.deepseek.com/](https://platform.deepseek.com/)
2. Crea una cuenta o inicia sesión
3. Ve a la sección de API Keys
4. Genera una nueva API key
5. Cópiala en el archivo `.env` como `DEEPSEEK_API_KEY`

**Comparación de LLMs:**

| Característica | Groq ⚡ | DeepSeek |
|----------------|---------|----------|
| **Velocidad** | ~200-500ms | ~1-3 segundos |
| **Gratis/día** | 14,400 requests | Según plan |
| **Modelos** | Mixtral, Llama 3.3 | DeepSeek-Chat |
| **Calidad** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

💡 **Recomendación**: Usa **Groq** para velocidad óptima (10x más rápido) con tier gratuito generoso.

### 6. Preparar documentos

Coloca tus archivos `.md` en la carpeta `data/docs/`:

```bash
mkdir -p data/docs
# Copia tus archivos .md a data/docs/
```

## 📖 Uso

### Ingestion de Documentos

Procesa los archivos markdown y genera sus embeddings:

```bash
# Ingestion básica
python src/main.py --ingest

# Ingestion dividiendo documentos en chunks
python src/main.py --ingest --chunk

# Forzar re-procesamiento de documentos existentes
python src/main.py --ingest --force
```

### Consultas

#### Consulta única

```bash
python src/main.py --query "¿Qué es Python?"
```

#### Consulta con fuentes

```bash
python src/main.py --query "¿Cómo funciona el sistema?" --show-sources
```

#### Modo interactivo

```bash
python src/main.py
```

Esto iniciará un modo interactivo donde puedes hacer múltiples preguntas:

```
💬 Tu pregunta: ¿Qué información tienes sobre machine learning?
🤖 Respuesta: [Respuesta basada en tus documentos]

💬 Tu pregunta: salir
¡Hasta luego!
```

### Opciones avanzadas

```bash
# Recuperar más documentos relevantes
python src/main.py --query "tu pregunta" --top-k 5

# Ajustar temperatura de DeepSeek (0.0 = más determinista, 1.0 = más creativo)
python src/main.py --query "tu pregunta" --temperature 0.5

# Combinación de opciones
python src/main.py --query "tu pregunta" --top-k 5 --temperature 0.7 --show-sources
```

### 🤖 Chatbot Interactivo (Consola) 🆕

Inicia el chatbot interactivo por consola:

```bash
python src/chat.py
```

**✨ Características del Chatbot:**
- 💬 Interfaz de chat por consola limpia e intuitiva
- 🧠 Mantiene historial de los últimos 5 mensajes
- 🔍 Sistema RAG con búsqueda semántica en documentos
- 📚 Muestra fuentes consultadas con scores de similitud
- 📊 Comandos especiales:
  - `salir` o `exit`: Terminar el chat
  - `limpiar`: Borrar historial de conversación
  - `stats`: Ver estadísticas del sistema

**Ejemplo de uso:**
```
🧑 Tú: ¿Qué información tienes sobre becas?

🤖 Chatbot: [Respuesta basada en documentos...]

📚 Fuentes consultadas:
  1. becas.md (similitud: 0.845)
  2. menciones_honorificas.md (similitud: 0.234)
```

### Estadísticas

Ver información del sistema:

```bash
python src/main.py --stats
```

### Limpiar base de datos

Eliminar todos los documentos:

```bash
python src/main.py --reset
```

## 🔧 Arquitectura Técnica

### Pipeline de Ingestion

1. **Carga de archivos**: Lee archivos `.md` desde `data/docs/`
2. **Preprocesamiento**: Limpia el texto (espacios, saltos de línea)
3. **Chunking** (opcional): Divide documentos largos en segmentos
4. **Generación de embeddings**: BGE-M3 crea vectores de 1024 dimensiones
5. **Conversión a bytes**: Transforma `float32` array a `VARBINARY`
6. **Almacenamiento**: Guarda en SQL Server

### Pipeline de Consulta

1. **Embedding de consulta**: Convierte la pregunta en vector
2. **Recuperación**: Obtiene TODOS los documentos de SQL Server
3. **Cálculo de similitud**: Similitud coseno en Python
4. **Ranking**: Ordena por relevancia y selecciona top-k
5. **Generación RAG**: Envía contexto + pregunta a DeepSeek
6. **Respuesta**: Retorna respuesta basada en contexto

### Conversión de Embeddings

```python
# Guardar
embedding_bytes = embedding_array.astype('float32').tobytes()

# Recuperar
embedding_array = np.frombuffer(embedding_bytes, dtype='float32')
```

## 🧪 Testing de Módulos Individuales

Cada módulo puede ejecutarse de forma independiente para testing:

```bash
# Test de embeddings
python src/embeddings/embedder.py

# Test de conexión a base de datos
python src/database/connection.py

# Test de ingestion
python src/ingestion/ingest_docs.py

# Test de DeepSeek client
python src/llm/deepseek_client.py

# Test de retriever
python src/rag/retriever.py
```

## ⚠️ Requisitos del Sistema

- **Python**: 3.8 o superior
- **SQL Server**: 2017 o superior
- **ODBC Driver**: ODBC Driver 17 for SQL Server
- **RAM**: Mínimo 4GB (recomendado 8GB para BGE-M3)
- **Espacio en disco**: ~2GB para el modelo BGE-M3

### Instalar ODBC Driver en Linux

```bash
# Ubuntu/Debian
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

## 🐛 Troubleshooting

### Error: "pyodbc.Error: SQL Server connection failed"

- Verifica que SQL Server esté corriendo
- Confirma host, puerto, usuario y password en `.env`
- Verifica que el firewall permita conexiones al puerto 1433

### Error: "DEEPSEEK_API_KEY no está configurada"

- Asegúrate de tener el archivo `.env` en la raíz del proyecto
- Verifica que la API key sea válida

### Error: "No hay documentos en la base de datos"

- Ejecuta primero `python src/main.py --ingest`
- Verifica que haya archivos `.md` en `data/docs/`

### El modelo BGE-M3 se descarga muy lento

- El modelo pesa ~2GB, la primera vez tomará tiempo
- Se descarga automáticamente en `~/.cache/huggingface/`

### Errores de memoria con BGE-M3

- Cierra otras aplicaciones
- Reduce el tamaño de los documentos usando `--chunk`

## 📝 Ejemplo de Uso Completo

```bash
# 1. Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Agregar documentos
echo "# Python\nPython es un lenguaje de programación." > data/docs/python.md
echo "# SQL\nSQL es un lenguaje de consultas." > data/docs/sql.md

# 4. Ingerir documentos
python src/main.py --ingest

# 5. Hacer consultas
python src/main.py --query "¿Qué es Python?" --show-sources

# 6. Modo interactivo
python src/main.py
```

## 🤝 Contribuciones

Este es un proyecto de referencia. Siéntete libre de modificarlo según tus necesidades.

## 📄 Licencia

MIT License - Siéntete libre de usar este código.

## 🔗 Enlaces Útiles

- [BGE-M3 en Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [DeepSeek Platform](https://platform.deepseek.com/)
- [Documentación SQL Server](https://docs.microsoft.com/sql/)
- [pyodbc Documentation](https://github.com/mkleehammer/pyodbc)
