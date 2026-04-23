#!/bin/bash
# Script para crear el paquete de deployment de Lambda
set -e

echo "=== Creando paquete Lambda ==="

DIST_DIR="lambda_package"
ZIP_FILE="lambda_function.zip"

# Limpiar builds anteriores
rm -rf "$DIST_DIR" "$ZIP_FILE"
mkdir -p "$DIST_DIR"

# Instalar dependencias en el directorio de deployment
echo "Instalando dependencias..."
pip install \
    fastapi \
    mangum \
    pydantic \
    python-multipart \
    python-dotenv \
    amazon-transcribe \
    -t "$DIST_DIR" -q --upgrade

# Copiar codigo fuente
echo "Copiando codigo..."
cp -r src/ "$DIST_DIR/src/"
cp -r api/ "$DIST_DIR/api/"

# Remover archivos innecesarios para reducir tamano
echo "Limpiando archivos innecesarios..."
find "$DIST_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DIST_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$DIST_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$DIST_DIR" -name "*.pyc" -delete 2>/dev/null || true

# No incluir boto3/botocore (ya vienen en Lambda runtime)
rm -rf "$DIST_DIR/boto3" "$DIST_DIR/botocore" "$DIST_DIR/s3transfer" "$DIST_DIR/jmespath"

# Crear ZIP
echo "Creando ZIP..."
cd "$DIST_DIR"
zip -r "../$ZIP_FILE" . -q
cd ..

# Mostrar tamano
SIZE=$(du -sh "$ZIP_FILE" | cut -f1)
echo ""
echo "=== Listo ==="
echo "Archivo: $ZIP_FILE ($SIZE)"
echo "Handler: api.main.handler"
