# CI/CD para `voae-chatbot` — Análisis e integración

Fecha: 2026-04-17
Aplicación: VOAE Chatbot (Lambda `voae-chatbot` en `us-east-2`, cuenta `824333136555`)
Frontend: CloudFront `d1jjhwm5s0qx67.cloudfront.net`, `d2oef8cfr2hc98.cloudfront.net`

---

## 0. ¿Qué es CI/CD y por qué lo piden?

- **CI (Continuous Integration):** cada push a git dispara un pipeline que valida el código (lint, tests, build del paquete).
- **CD (Continuous Deployment):** el mismo pipeline, si CI pasó, despliega automáticamente a AWS.

**Estado actual:** despliegue manual — `lambda_function.zip` subido a mano por consola de Lambda. Sin versionado de infraestructura, sin validación previa, sin rollback confiable. Eso es lo que el requerimiento busca eliminar.

---

## 1. Docker vs GitHub Actions — no son alternativas, son capas distintas

La frase "Docker o GitHub Actions" del requerimiento es ambigua. Realmente son complementarios:

| Herramienta | Rol |
|---|---|
| **GitHub Actions** | Orquestador del pipeline (corre workflows en `.github/workflows/*.yml` al hacer push). |
| **Docker** | Empaquetado reproducible (imagen con Python 3.10 + deps, idéntica en CI y en Lambda). |

### Opción A — GitHub Actions sin Docker (más simple)

```
push a main → GH Actions workflow:
  1. checkout
  2. setup python 3.10
  3. pip install -r requirements.txt -t package/
  4. zip package/ + api/ + src/ → lambda.zip
  5. aws lambda update-function-code ...
  6. invalidar CloudFront
```

### Opción B — GitHub Actions + Docker (recomendado si el paquete crece)

- `lambda_function.zip` actual pesa 11.84 MB. Lambda permite hasta 250 MB descomprimido en zip, pero hasta **10 GB con contenedor Docker**.
- Lambda soporta container images: imagen construida desde `public.ecr.aws/lambda/python:3.10`, pushed a ECR, Lambda la ejecuta.
- Ventaja real: **mismo entorno en local, CI y Lambda**. Hoy `lambda_package/` se construye en WSL; si una dep binaria (`pydantic_core`, `awscrt`) se compila distinto, rompe en Lambda. Docker elimina ese riesgo.

### Recomendación

**Opción A por ahora** (zip es chico). Migrar a contenedores si se suman deps pesadas (pandas, numpy, sentence-transformers).

---

## 2. AWS CodeBuild vs GitHub Actions — elegir uno

| Aspecto | GitHub Actions | AWS CodeBuild |
|---|---|---|
| Dónde corre | Runners de GitHub (SaaS) | Cuenta AWS del cliente |
| Config | `.github/workflows/deploy.yml` | `buildspec.yml` |
| Auth a AWS | **OIDC** (sin keys) o secretos | Rol IAM nativo |
| Costo | 2000 min/mes gratis en repos privados | ~$0.005/min |
| Integración con AWS | Vía CLI | Nativa |
| Logs | GitHub UI | CloudWatch |

### Interpretación del requerimiento ("Se recomienda CodeBuild")

Dos lecturas válidas:
- **CodeBuild solo:** GitHub webhook → CodePipeline → CodeBuild → despliega.
- **GitHub Actions + CodeBuild:** Actions para validación rápida (tests, lint), CodeBuild para build pesado dentro de AWS.

### Recomendación para este proyecto

**GitHub Actions con OIDC a AWS** — lo más limpio y barato. CodeBuild solo compensa si:
- Hace falta build dentro de VPC (no aplica aquí).
- El equipo ya usa CodePipeline como estándar corporativo.

### Cómo funciona OIDC

Se crea un rol IAM `github-actions-deploy` con una *trust policy* que acepta tokens firmados por `token.actions.githubusercontent.com`, scoped al repo `RoboerWaters/LLAMA_BGE_CHATBOT`. En el workflow:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::824333136555:role/github-actions-deploy
    aws-region: us-east-2
```

Sin Access Keys de IAM en los secretos de GitHub. Más seguro y sin rotación manual.

---

## 3. Serverless Framework (o alternativas) — Infrastructure as Code

**Problema actual:** la infra (Lambda, IAM role, API Gateway, env vars) se creó a mano en consola. No está en git, no es reproducible, no se puede revertir.

**Infrastructure as Code (IaC)** resuelve eso. Opciones principales:

| Framework | Lenguaje | Nivel de abstracción |
|---|---|---|
| **Serverless Framework** | YAML | Alto (específico Lambda) — **recomendado por el requerimiento** |
| **AWS SAM** | YAML | Alto (oficial AWS) |
| **AWS CDK** | Python/TS | Medio (código imperativo) |
| **Terraform** | HCL | Bajo (agnóstico cloud) |

### Ejemplo `serverless.yml` para esta app

```yaml
service: voae-chatbot

provider:
  name: aws
  runtime: python3.10
  region: us-east-2
  memorySize: 1024
  timeout: 29
  environment:
    BEDROCK_KNOWLEDGE_BASE_ID: ATRGGUJIS9
    BEDROCK_MODEL_ID: us.anthropic.claude-3-5-haiku-20241022-v1:0
    BEDROCK_REGION: us-east-2
    POLLY_REGION: us-east-1
    POLLY_VOICE: Lupe
    POLLY_LANGUAGE: es-US
    POLLY_ENGINE: neural
    API_CORS_ORIGINS: https://d1jjhwm5s0qx67.cloudfront.net,https://d2oef8cfr2hc98.cloudfront.net
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - bedrock:InvokeModel
            - bedrock:Retrieve
            - bedrock:RetrieveAndGenerate
          Resource: "*"
        - Effect: Allow
          Action: [polly:SynthesizeSpeech]
          Resource: "*"
        - Effect: Allow
          Action: [transcribe:StartStreamTranscription]
          Resource: "*"

functions:
  chatbot:
    handler: api.main.handler
    events:
      - http:
          path: /{proxy+}
          method: any
          cors: true

package:
  exclude:
    - frontend/**
    - data/**
    - venv/**
    - "*.zip"
```

### Beneficios

- `sls deploy` crea Lambda + API Gateway + rol IAM de cero, en cualquier región/cuenta.
- `sls remove` borra todo limpiamente.
- Versionado: `serverless.yml` vive en git; cada PR muestra cambios de infra.
- **Resuelve el problema de `AWSLambda_FullAccess`:** aquí se definen permisos mínimos explícitos.

### Caveat

Una vez desplegando con Serverless, **no editar la Lambda por consola** — la siguiente `sls deploy` sobrescribe. Requiere disciplina del equipo: una sola fuente de verdad.

---

## 4. Invalidación de CloudFront

### El problema

El frontend React vive en CloudFront (`d1jjhwm5s0qx67.cloudfront.net`, `d2oef8cfr2hc98.cloudfront.net`), probablemente servido desde un bucket S3.

CloudFront **cachea** `index.html`, `assets/*.js`, `assets/*.css` en edge locations. Tras subir una versión nueva al S3, los usuarios **siguen viendo la vieja** hasta que expire el TTL (típicamente horas).

### La solución — invalidación

```bash
aws cloudfront create-invalidation \
  --distribution-id E1ABC123XYZ \
  --paths "/*"
```

Fuerza a los edges a refrescar desde el origin (S3) en la siguiente request.

### Integración en el pipeline

```yaml
# .github/workflows/deploy-frontend.yml
- name: Build frontend
  run: cd frontend && npm ci && npm run build

- name: Sync to S3
  run: aws s3 sync frontend/dist/ s3://voae-frontend-bucket/ --delete

- name: Invalidate CloudFront
  run: |
    aws cloudfront create-invalidation \
      --distribution-id ${{ secrets.CF_DISTRIBUTION_ID }} \
      --paths "/*"
```

### Gotchas

- `/*` invalida todo. Primeras 1000 paths/mes gratis; después $0.005 cada una.
- **Buena práctica:** Vite ya hashea `assets/index-abc123.js`. Basta con invalidar `/index.html` (el archivo que apunta a los hashes). Más barato y más rápido.
- La invalidación tarda **3-5 minutos** en propagar a todos los edges.
- Hay **dos distribuciones activas** (`d1jjhwm5s0qx67` y `d2oef8cfr2hc98`) — invalidar ambas.

### Patrón recomendado

```yaml
aws cloudfront create-invalidation --distribution-id ${{ secrets.CF_DIST_1 }} --paths "/index.html"
aws cloudfront create-invalidation --distribution-id ${{ secrets.CF_DIST_2 }} --paths "/index.html"
```

---

## 5. Cómo encajan todas las piezas

```
[ git push a main ]
        │
        ├──── Backend workflow (.github/workflows/deploy-backend.yml)
        │     ├─ checkout
        │     ├─ configure-aws-credentials (vía OIDC)
        │     ├─ npm install -g serverless
        │     ├─ pip install -r requirements.txt
        │     ├─ sls deploy --stage prod
        │     │   → crea/actualiza Lambda voae-chatbot
        │     │   → crea/actualiza API Gateway
        │     │   → crea/actualiza IAM role mínimo
        │     └─ (opcional) smoke test: curl /api/health
        │
        └──── Frontend workflow (.github/workflows/deploy-frontend.yml)
              ├─ checkout
              ├─ configure-aws-credentials (OIDC)
              ├─ cd frontend && npm ci && npm run build
              ├─ aws s3 sync dist/ s3://voae-frontend/
              └─ aws cloudfront create-invalidation
                  → usuarios ven la nueva versión en ~3 min
```

---

## 6. Errores típicos y cómo resolverlos

| Problema | Causa | Solución |
|---|---|---|
| `User is not authorized to perform: lambda:UpdateFunctionCode` | El rol IAM de GH Actions no tiene permisos | Ampliar trust policy y permisos del rol `github-actions-deploy` |
| `Unzipped size must be smaller than 262144000 bytes` | Dependencias infladas | Migrar a container image, o usar Lambda Layers para deps pesadas |
| Cold start sube a 5-8 s tras cada deploy | Paquete grande, cada deploy resetea contenedores | Configurar `provisioned concurrency` o Lambda SnapStart (aún no para Python) |
| Invalidación CloudFront no surte efecto | Caché del navegador del usuario | Hashes en nombres de archivo (Vite ya lo hace) + `Cache-Control: max-age=31536000, immutable` en assets y `no-cache` en `index.html` |
| API Gateway devuelve 500 después del deploy | Handler path mal (`api.main.handler` vs `api/main.handler`) | Validar con `sls invoke -f chatbot` antes del deploy real |
| `sls deploy` entra en conflicto con Lambda hecha a mano | Choque de nombres | Importar el estado actual con `sls create --template aws-python3`, desplegar con nombre distinto, migrar tráfico |
| OIDC falla: `No identity-based policy allows sts:AssumeRoleWithWebIdentity` | Trust policy del rol mal configurada | La condition debe incluir `token.actions.githubusercontent.com:sub = "repo:RoboerWaters/LLAMA_BGE_CHATBOT:*"` |
| `Timeout` en el pipeline durante `pip install` | Compilación de deps binarias | Cachear `pip` con `actions/cache@v4` usando hash de `requirements.txt` como key |
| La Lambda despliega pero las env vars no aparecen | Olvidaste declararlas en `serverless.yml` | Centralizar todas las env vars en el `serverless.yml`, no mezclar con configuración de consola |

---

## 7. Propuesta de orden de implementación

1. **Fase 1 — IaC primero:** convertir la Lambda actual a `serverless.yml` sin desplegar aún. Validar que `sls package` genera un zip equivalente al actual.
2. **Fase 2 — GH Actions backend:** workflow que corre `sls deploy` en push a `main`. Configurar OIDC (eliminar Access Keys de GitHub Secrets).
3. **Fase 3 — GH Actions frontend:** sync a S3 + invalidación CloudFront de ambas distribuciones.
4. **Fase 4 — Hardening:** quitar `AWSLambda_FullAccess` del rol, tightening de CORS, alarmas CloudWatch (errores, duración p99, throttles).

---

## 8. Resumen ejecutivo

| Requerimiento | Cómo se resuelve |
|---|---|
| CI/CD | GitHub Actions workflows en `.github/workflows/` |
| Docker o GH Actions | GH Actions para orquestar; Docker opcional (sólo si paquete supera 250 MB) |
| CodeBuild | **Alternativa a GH Actions** — se elige uno; se recomienda GH Actions con OIDC |
| Serverless Framework | `serverless.yml` define Lambda + API Gateway + IAM role de forma versionada |
| Invalidación CloudFront | Paso final del workflow de frontend, invalidando ambas distribuciones |

El resultado: push a `main` → en 3-5 minutos la versión nueva está viva en producción, con infra versionada, permisos mínimos, sin intervención manual, y reversible vía `git revert`.
