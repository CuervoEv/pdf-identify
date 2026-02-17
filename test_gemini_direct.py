#!/usr/bin/env python
"""Script de prueba para verificar que Gemini funciona correctamente"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from src.utils.image_converter import ImageConverter
from src.services.gemini_service import GeminiVisionService

# Cargar variables de entorno
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

print("=" * 60)
print("PRUEBA GEMINI - Análisis de Formulario")
print("=" * 60)

# Verificar API key
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY no encontrada en .env")
    exit(1)

print(f"✓ API KEY detectada: {api_key[:10]}...")

# Crear servicio Gemini
try:
    gemini = GeminiVisionService()
    assert gemini.model_id == "gemini-3-flash-preview", "El modelo Gemini no está configurado correctamente."
    print("✓ Servicio Gemini inicializado correctamente")
except Exception as e:
    print(f"❌ Error al inicializar Gemini: {e}")
    exit(1)

# Buscar un PDF de prueba
test_pdf = Path("temp") / "test.pdf"
if not test_pdf.exists():
    print(f"⚠️  No hay PDF de prueba en {test_pdf}")
    print("   Crea un PDF de prueba en temp/test.pdf")
    exit(1)

print(f"✓ PDF encontrado: {test_pdf}")

# Convertir PDF a imágenes
try:
    image_converter = ImageConverter()
    images_with_pages = image_converter.pdf_to_images(str(test_pdf))
    print(f"✓ PDF convertido: {len(images_with_pages)} página(s)")
except Exception as e:
    print(f"❌ Error al convertir PDF: {e}")
    exit(1)

# Analizar cada página
for image, page_num in images_with_pages[:1]:  # Solo primera página para test
    print(f"\n--- Página {page_num} ---")
    try:
        fields = gemini.analyze_form_page(image)
        print(f"✓ Gemini respondió correctamente")
        print(f"  Campos detectados: {len(fields)}")
        
        if fields:
            print(f"\n  Primeros 3 campos:")
            for field in fields[:3]:
                print(f"    - {field.get('id')}: ({field.get('coordenadas_x')}, {field.get('coordenadas_y')}) "
                      f"[{field.get('ancho_estimado')}x{field.get('alto_estimado')}]")
        else:
            print("  ⚠️  No se detectaron campos")
            
    except Exception as e:
        print(f"❌ Error al analizar página: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("Prueba completada")
print("=" * 60)
