# Costo Computacional de los Modelos
**Proyecto:** VOAE Chatbot — rama `feature/simli`

---

## Configuración actual

| Modelo | Rol | Parámetros | FP16 | INT8 | INT4 | Disco (FP16) |
|--------|-----|-----------|------|------|------|--------------|
| `BAAI/bge-m3` | Embeddings | 568 M | ~1.5–2 GB | — | — | ~1.06 GB |
| `whisper-large-v3` | STT | 1.55 B | ~4 GB | — | ~735 MB | ~2.87 GB |
| `llama-3.3-70b-versatile` | LLM | 70 B | ~140 GB | ~70 GB | ~35–42 GB | ~131 GB |
| **Total** | | | **~146 GB** | **~70 GB** † | **~36–43 GB** † | **~135 GB** |

† Solo incluye modelos con datos disponibles en esa precisión.

**Fuentes:** [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) · [openai/whisper-large-v3](https://huggingface.co/openai/whisper-large-v3) · [meta-llama/Llama-3.3-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)

---

## Configuración mínima alternativa

| Modelo | Rol | Parámetros | FP16 | INT8 | INT4 | Disco (FP16) |
|--------|-----|-----------|------|------|------|--------------|
| `BAAI/bge-m3` | Embeddings | 568 M | ~1.5–2 GB | — | — | ~1.06 GB |
| `whisper-medium` | STT | 769 M | ~2–5 GB | ~730 MB | ~364 MB | ~1.42 GB |
| `llama-3.1-8b-instant` | LLM | 8 B | ~16 GB | ~8.5 GB | ~5–6 GB | ~14.1 GB |
| **Total** | | | **~20–23 GB** | **~9 GB** † | **~6 GB** † | **~17 GB** |

† BGE-M3 no tiene datos de INT8/INT4; no se incluye en esos subtotales.

**Fuentes:** [openai/whisper-medium](https://huggingface.co/openai/whisper-medium) · [openai/whisper — tabla oficial de parámetros](https://github.com/openai/whisper) · [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)

---

## Detalle por modelo

### BAAI/bge-m3
- **Arquitectura:** XLM-RoBERTa encoder-only, salida 1024D
- **VRAM (FP16):** ~1.06 GB modelo + overhead → ~1.5–2 GB en inferencia (batch=1)
- **RAM en CPU:** ~4–5 GB
- **Nota:** con batch size grande (128–256) puede llegar a 6–9 GB VRAM

### whisper-large-v3
- **Arquitectura:** Encoder-Decoder Transformer
- **VRAM (FP16):** ~3.9–4 GB
- **VRAM (FP32):** ~10 GB
- **Con faster-whisper (CTranslate2 FP16):** ~2–3 GB

### whisper-medium
- **Arquitectura:** Encoder-Decoder Transformer (misma que large-v3, menos capas)
- **VRAM (FP16):** ~2–5 GB (incluye buffer de audio de 30s)
- **Con faster-whisper INT8:** ~730 MB
- **Reducción vs large-v3:** ~50% menos parámetros, ~50% menos VRAM

### llama-3.3-70b-versatile
- **Arquitectura:** Llama decoder-only con GQA
- **VRAM (FP16/BF16):** ~140 GB → requiere cluster (2× A100 80 GB)
- **VRAM (INT8):** ~70 GB → 2× A100 80 GB
- **VRAM (INT4 Q4_K_M):** ~35–42 GB → 2× RTX 4090

### llama-3.1-8b-instant
- **Arquitectura:** Llama decoder-only con GQA, contexto 128K tokens
- **VRAM (FP16):** ~16 GB → 1× RTX 4090 o 1× A100 40 GB
- **VRAM (INT8):** ~8.5 GB → 1× RTX 3080/4070 Ti
- **VRAM (INT4 Q4_K_M):** ~5–6 GB → 1× RTX 3060 12 GB
