# Análisis de Instancias EC2 por Escenario de Despliegue
**Proyecto:** VOAE Chatbot — rama `feature/simli`

---

## Escenario 1 — Arquitectura actual (APIs externas: Groq + Amazon Polly)

El LLM y STT corren vía Groq API. Solo **BGE-M3 corre localmente** (~4–5 GB RAM CPU). No se requiere GPU.

| Instancia | vCPUs | RAM | GPU | VRAM | Precio/hr | Precio/mes |
|-----------|-------|-----|-----|------|-----------|------------|
| `t3.large` | 2 | 8 GB | — | — | $0.083 | ~$60 |
| `t3.xlarge` ✅ | 4 | 16 GB | — | — | $0.166 | ~$120 |

> **Recomendado:** `t3.xlarge` — margen cómodo para BGE-M3 en CPU + servidor FastAPI.

---

## Escenario 2 — Autoalojamiento completo de todos los modelos

### 2a — Configuración mínima (BGE-M3 + whisper-medium + llama-3.1-8b)

**VRAM total estimada:** ~20–23 GB (FP16) · ~8–9 GB (INT4/INT8)

| Precisión | Instancia | GPU | VRAM disponible | TFLOPS FP16 | Precio/hr | Precio/mes |
|-----------|-----------|-----|-----------------|-------------|-----------|------------|
| INT4/INT8 | `g4dn.xlarge` | 1× T4 | 16 GB | ~65 TOPS INT8 | $0.526 | ~$380 |
| FP16 | `g5.xlarge` | 1× A10G | 24 GB | 70 TF | $1.006 | ~$725 |
| FP16 ✅ | `g5.2xlarge` | 1× A10G | 24 GB | 70 TF | $1.212 | ~$870 |

> `g5.xlarge` y `g5.2xlarge` tienen el mismo GPU (A10G 24 GB). El `g5.2xlarge` añade 32 GB de RAM de sistema vs 16 GB, dando margen para múltiples usuarios simultáneos.

### 2b — Configuración actual autoalojada (BGE-M3 + whisper-large-v3 + llama-3.3-70b)

**VRAM total estimada:** ~146 GB (FP16) · ~41–48 GB (INT4)

| Precisión | Instancia | GPU | VRAM disponible | TFLOPS FP16 | Precio/hr | Precio/mes |
|-----------|-----------|-----|-----------------|-------------|-----------|------------|
| INT4 ✅ | `g5.12xlarge` | 4× A10G | 96 GB | 280 TF | $5.672 | ~$4,084 |
| FP16 | `p4d.24xlarge` | 8× A100 40 GB | 320 GB | 1,248 TF | $21.96 | ~$15,811 |

> Autoalojar llama 70B **no tiene justificación económica** frente a la API de Groq salvo volúmenes muy altos.

---

## Escenario 3 — Todos los modelos por API + AWS Elastic Beanstalk

Todo se consume vía APIs externas (Groq para LLM + STT, Amazon Polly para TTS, Simli para avatar). Solo se despliega **FastAPI + React** en la nube. Elastic Beanstalk gestiona el escalado automáticamente **sin costo adicional** por la plataforma — solo pagas la EC2 subyacente.

### Instancia EC2 dentro de Elastic Beanstalk

| Instancia EB | vCPUs | RAM | Precio/hr | Precio/mes | Notas |
|--------------|-------|-----|-----------|------------|-------|
| `t3.small` | 2 | 2 GB | $0.023 | ~$17 | Mínimo absoluto, sin concurrencia |
| `t3.medium` | 2 | 4 GB | $0.042 | ~$30 | Uso ligero, 1–5 usuarios |
| `t3.large` ✅ | 2 | 8 GB | $0.083 | ~$60 | Recomendado para producción |

> En modo **single-instance** no hay Load Balancer (~$18/mes adicional). Con auto-scaling se agrega el LB automáticamente.

### Costos adicionales por APIs externas

| Servicio | Modelo | Costo aproximado |
|----------|--------|-----------------|
| Groq LLM | llama-3.3-70b-versatile | ~$0.59/M tokens entrada · $0.79/M salida |
| Groq STT | whisper-large-v3 | ~$0.111/hora de audio |
| Amazon Polly | Lupe neural (es-US) | ~$16/M caracteres |
| Simli Avatar | WebRTC streaming | Según plan Simli |

---

## Escenario 4 — Configuración mínima + MuseTalk local

**MuseTalk** es un modelo de lip-sync en tiempo real (UNet de SD v1.4 + VAE + whisper-tiny). Referencia de rendimiento oficial: **30fps+ en Tesla V100**.

### Desglose de VRAM del stack completo

| Modelo | Precisión | VRAM estimada |
|--------|-----------|---------------|
| BGE-M3 | FP16 | ~2 GB |
| whisper-medium | INT8 | ~0.73 GB |
| llama-3.1-8b | INT4 | ~5–6 GB |
| **MuseTalk** | FP16 | **~8 GB** |
| **Total** | | **~16–17 GB** |

### Requisito de cómputo para MuseTalk en tiempo real

| GPU referencia | FP32 TFLOPS | FP16 TFLOPS | MuseTalk fps |
|----------------|-------------|-------------|--------------|
| Tesla V100 (referencia oficial) | 14–16.4 TF | 112–130 TF | **30fps+** |
| NVIDIA T4 (g4dn) | 8.1 TF | ~65 TOPS INT8 | ~15fps ❌ |
| NVIDIA A10G (g5) | 35 TF | 70 TF | **30fps+** ✅ |

> La T4 queda descartada: sus 8.1 TFLOPS FP32 son ~50% menos que el V100, resultando en ~15fps — no apto para tiempo real.

### Instancias candidatas para Escenario 4

| Instancia | GPU | VRAM | FP32 TF | FP16 TF | MuseTalk real-time | Precio/hr | Precio/mes |
|-----------|-----|------|---------|---------|--------------------|-----------|------------|
| `g4dn.xlarge` | T4 | 16 GB | 8.1 TF | — | ❌ ~15fps | $0.526 | ~$379 |
| `g4dn.2xlarge` | T4 | 16 GB | 8.1 TF | — | ❌ ~15fps | $0.752 | ~$541 |
| `g5.xlarge` ✅ | A10G | 24 GB | 35 TF | 70 TF | ✅ 30fps+ | $1.006 | ~$725 |
| `g5.2xlarge` | A10G | 24 GB | 35 TF | 70 TF | ✅ 30fps+ holgado | $1.212 | ~$873 |

> **Recomendado: `g5.xlarge`** — 24 GB VRAM cubre los ~16 GB del stack con margen y los 35 TFLOPS FP32 (2.5× V100) garantizan MuseTalk a 30fps+.

---

## Cuadro Comparativo General — Los 4 Escenarios

| | **Escenario 1** | **Escenario 2a** | **Escenario 2b** | **Escenario 3** | **Escenario 4** |
|--|--|--|--|--|--|
| **Descripción** | APIs externas (Groq + Polly) | Autoalojado mínimo | Autoalojado actual | Todo por API + EB | Mínimo + MuseTalk local |
| **LLM** | Groq API | llama-3.1-8b local | llama-3.3-70b local | Groq API | Groq API |
| **STT** | Groq API | whisper-medium local | whisper-large-v3 local | Groq API | Groq API |
| **Avatar / TTS** | Polly + Simli API | Polly local | Polly local | Polly + Simli API | MuseTalk local |
| **GPU necesaria** | No | Sí | Sí | No | Sí |
| **Instancia recomendada** | `t3.xlarge` | `g5.2xlarge` | `g5.12xlarge` (INT4) | `t3.large` (EB) | `g5.xlarge` |
| **VRAM disponible** | — | 24 GB | 96 GB | — | 24 GB |
| **TFLOPS FP16** | — | 70 TF | 280 TF | — | 70 TF |
| **Precio instancia/hr** | $0.166 | $1.212 | $5.672 | $0.083 | $1.006 |
| **Precio instancia/mes** | ~$120 | ~$873 | ~$4,084 | ~$60 | ~$725 |
| **Costos API adicionales** | Groq + Polly + Simli | Solo Polly | Solo Polly | Groq + Polly + Simli | Solo Groq (STT + LLM) |
| **Escalabilidad** | Alta | Media | Media | Alta (auto-scaling EB) | Media |
| **Complejidad despliegue** | Baja | Alta | Muy alta | Muy baja | Alta |

---

## Fuentes

- [AWS EC2 Accelerated Computing Instances](https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html)
- [Vantage — g4dn.xlarge](https://instances.vantage.sh/aws/ec2/g4dn.xlarge)
- [Vantage — g5.xlarge](https://instances.vantage.sh/aws/ec2/g5.xlarge)
- [Vantage — g5.2xlarge](https://instances.vantage.sh/aws/ec2/g5.2xlarge)
- [Vantage — g5.12xlarge](https://instances.vantage.sh/aws/ec2/g5.12xlarge)
- [Vantage — p4d.24xlarge](https://instances.vantage.sh/aws/ec2/p4d.24xlarge)
- [Vantage — t3.large](https://instances.vantage.sh/aws/ec2/t3.large)
- [AWS Elastic Beanstalk Pricing](https://aws.amazon.com/elasticbeanstalk/pricing/)
- [NVIDIA A10G Datasheet (AWS)](https://d1.awsstatic.com/product-marketing/ec2/NVIDIA_AWS_A10G_DataSheet_FINAL_02_17_2022.pdf)
- [NVIDIA V100 Datasheet](https://images.nvidia.com/content/technologies/volta/pdf/volta-v100-datasheet-update-us-1165301-r5.pdf)
- [MuseTalk — GitHub oficial (TMElyralab)](https://github.com/TMElyralab/MuseTalk)
- [MuseTalk — DeepWiki Model Architecture](https://deepwiki.com/TMElyralab/MuseTalk/3-model-architecture)
- [Parameter Tuning & GPU Selection for MuseTalk](https://frankfu.blog/real-time-digital-human/digital-human-series-4-parameter-tuning-and-gpu-selection-for-a-real-time-digital-human-system-based-on-musetalk-realtime-api/)
