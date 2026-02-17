"""
Utilidades auxiliares para el procesamiento de documentos.
"""

import os
from pathlib import Path


def ensure_temp_dir(temp_dir: str) -> None:
    """
    Asegura que el directorio temporal existe.
    
    Args:
        temp_dir: Ruta del directorio temporal
    """
    os.makedirs(temp_dir, exist_ok=True)


def cleanup_temp_files(temp_dir: str, max_age_hours: int = 24) -> None:
    """
    Limpia archivos temporales antiguos.
    
    Args:
        temp_dir: Ruta del directorio temporal
        max_age_hours: Edad máxima de archivos en horas
    """
    import time
    
    if not os.path.exists(temp_dir):
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        file_age = current_time - os.path.getmtime(file_path)
        
        if file_age > max_age_seconds:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error limpiando {file_path}: {e}")


def get_file_extension(filename: str) -> str:
    """
    Obtiene la extensión de archivo.
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        Extensión en minúsculas (ej: .pdf)
    """
    return Path(filename).suffix.lower()


def is_supported_file(filename: str) -> bool:
    """
    Verifica si el archivo es soportado.
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        True si es PDF o XLSX/XLS
    """
    ext = get_file_extension(filename)
    return ext in ['.pdf', '.xlsx', '.xls']
