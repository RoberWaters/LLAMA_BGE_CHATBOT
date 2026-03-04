"""
Utilidades para sincronización de ChromaDB y documentos con Amazon S3
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
from datetime import timezone

import boto3
import botocore.exceptions

from config import S3Config


def _s3_client():
    """Crea y retorna un cliente boto3 S3"""
    return boto3.client(
        's3',
        region_name=S3Config.AWS_REGION,
        aws_access_key_id=S3Config.AWS_ACCESS_KEY,
        aws_secret_access_key=S3Config.AWS_SECRET_KEY,
    )


def upload_chroma(local_path: str, bucket: str, prefix: str) -> None:
    """
    Sube chroma.sqlite3 al bucket S3.

    Args:
        local_path: Directorio local de ChromaDB (ej: data/chroma)
        bucket: Nombre del bucket S3
        prefix: Prefijo en S3 (ej: chroma/)
    """
    sqlite_file = Path(local_path) / 'chroma.sqlite3'
    if not sqlite_file.exists():
        print(f"[S3Sync] Advertencia: {sqlite_file} no existe, omitiendo upload")
        return

    s3_key = f"{prefix.rstrip('/')}/chroma.sqlite3"
    print(f"[S3Sync] Subiendo {sqlite_file} → s3://{bucket}/{s3_key}")
    client = _s3_client()
    client.upload_file(str(sqlite_file), bucket, s3_key)
    print(f"[S3Sync] Upload completado: s3://{bucket}/{s3_key}")


def download_chroma(bucket: str, prefix: str, local_path: str) -> bool:
    """
    Descarga chroma.sqlite3 desde S3 si es más reciente o no existe localmente.

    Args:
        bucket: Nombre del bucket S3
        prefix: Prefijo en S3 (ej: chroma/)
        local_path: Directorio local de ChromaDB (ej: data/chroma)

    Returns:
        True si se descargó, False si ya estaba actualizado o no existe en S3
    """
    s3_key = f"{prefix.rstrip('/')}/chroma.sqlite3"
    local_dir = Path(local_path)
    sqlite_file = local_dir / 'chroma.sqlite3'

    client = _s3_client()

    # Verificar que el objeto existe en S3 y obtener su fecha de modificación
    try:
        response = client.head_object(Bucket=bucket, Key=s3_key)
        s3_last_modified = response['LastModified']  # datetime UTC-aware
    except botocore.exceptions.ClientError as e:
        code = e.response['Error']['Code']
        if code in ('404', 'NoSuchKey', '403'):
            print(f"[S3Sync] chroma.sqlite3 no encontrado en s3://{bucket}/{s3_key}")
            return False
        raise

    # Comparar con archivo local: descargar solo si S3 es más reciente
    if sqlite_file.exists():
        local_mtime = sqlite_file.stat().st_mtime
        local_dt = datetime.datetime.fromtimestamp(local_mtime, tz=timezone.utc)
        if local_dt >= s3_last_modified:
            print("[S3Sync] ChromaDB local ya está actualizado, omitiendo descarga")
            return False

    # Descargar
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"[S3Sync] Descargando s3://{bucket}/{s3_key} → {sqlite_file}")
    client.download_file(bucket, s3_key, str(sqlite_file))
    print(f"[S3Sync] Descarga completada: {sqlite_file}")
    return True


def list_docs(bucket: str, prefix: str) -> list:
    """
    Lista objetos .md y .MD bajo el prefijo en S3 (con paginación).

    Args:
        bucket: Nombre del bucket S3
        prefix: Prefijo en S3 (ej: docs/)

    Returns:
        Lista de keys S3 (strings)
    """
    client = _s3_client()
    paginator = client.get_paginator('list_objects_v2')
    keys = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.lower().endswith('.md'):
                keys.append(key)

    print(f"[S3Sync] Encontrados {len(keys)} archivos .md en s3://{bucket}/{prefix}")
    return keys


def read_doc(bucket: str, key: str) -> str:
    """
    Descarga y decodifica un objeto S3 como string UTF-8.

    Args:
        bucket: Nombre del bucket S3
        key: Key del objeto S3

    Returns:
        Contenido del archivo como string
    """
    client = _s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    return content
