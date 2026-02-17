"""
Script de ejemplo para testear el microservicio.

Uso:
    python test_example.py
"""

import requests
import json
import os

BASE_URL = "http://localhost:8000"


def test_health():
    """Prueba el endpoint de health check."""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")


def test_fill_document_pdf(pdf_path: str):
    """
    Prueba el endpoint de rellenado de PDF.
    
    Args:
        pdf_path: Ruta del archivo PDF
    """
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} no existe\n")
        return
    
    print(f"Testing /fill-document con PDF: {pdf_path}...")
    
    # Datos a rellenar (ajusta según tu formulario)
    data = {
        "campo_nombre": "Juan Pérez García",
        "campo_apellido": "Pérez García",
        "campo_dni": "12345678A",
        "campo_telefono": "555-123-4567",
        "campo_email": "juan@example.com",
        "campo_acepta_terminos": "X"
    }
    
    with open(pdf_path, "rb") as f:
        files = {"file": f}
        form_data = {"json_data": json.dumps(data)}
        
        response = requests.post(
            f"{BASE_URL}/fill-document",
            files=files,
            data=form_data
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        output_path = "resultado_rellenado.pdf"
        with open(output_path, "wb") as out:
            out.write(response.content)
        print(f"PDF rellenado guardado en: {output_path}\n")
    else:
        print(f"Error: {response.text}\n")


def test_fill_document_excel(excel_path: str):
    """
    Prueba el endpoint de rellenado de Excel.
    
    Args:
        excel_path: Ruta del archivo Excel
    """
    if not os.path.exists(excel_path):
        print(f"Error: {excel_path} no existe\n")
        return
    
    print(f"Testing /fill-document con Excel: {excel_path}...")
    
    # Datos a rellenar (ajusta según tu formulario)
    data = {
        "campo_nombre": "María López",
        "campo_empresa": "Acme Corp",
        "campo_cantidad": "100",
        "campo_precio": "50.00"
    }
    
    with open(excel_path, "rb") as f:
        files = {"file": f}
        form_data = {"json_data": json.dumps(data)}
        
        response = requests.post(
            f"{BASE_URL}/fill-document",
            files=files,
            data=form_data
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        output_path = "resultado_rellenado.xlsx"
        with open(output_path, "wb") as out:
            out.write(response.content)
        print(f"Excel rellenado guardado en: {output_path}\n")
    else:
        print(f"Error: {response.text}\n")


def test_invalid_file():
    """Prueba error con archivo inválido."""
    print("Testing error handling con archivo inválido...")
    
    with open("test.txt", "w") as f:
        f.write("This is a test file")
    
    with open("test.txt", "rb") as f:
        files = {"file": f}
        form_data = {"json_data": json.dumps({"test": "data"})}
        
        response = requests.post(
            f"{BASE_URL}/fill-document",
            files=files,
            data=form_data
        )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}\n")
    
    os.remove("test.txt")


def test_missing_json():
    """Prueba error sin json_data."""
    print("Testing error handling sin json_data...")
    
    # Crear archivo dummy
    with open("dummy.pdf", "wb") as f:
        f.write(b"dummy")
    
    with open("dummy.pdf", "rb") as f:
        files = {"file": f}
        
        response = requests.post(
            f"{BASE_URL}/fill-document",
            files=files
        )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}\n")
    
    os.remove("dummy.pdf")


if __name__ == "__main__":
    print("=" * 60)
    print("TESTS - Llenado Inteligente de Documentos")
    print("=" * 60 + "\n")
    
    # Test health
    test_health()
    
    # Test con archivos reales (descomentar si tienes archivos de prueba)
    # test_fill_document_pdf("formulario_ejemplo.pdf")
    # test_fill_document_excel("formulario_ejemplo.xlsx")
    
    # Test error handling
    test_invalid_file()
    test_missing_json()
    
    print("=" * 60)
    print("Tests completados")
    print("=" * 60)
