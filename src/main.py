import os
import json
import uvicorn
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

# Importaciones locales
from src.services.gemini_service import GeminiVisionService
from src.services.pdf_filler import PDFFormFiller
from src.utils.image_converter import ImageConverter

load_dotenv()

app = FastAPI()
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/fill-document")
async def fill_document(file: UploadFile = File(...), json_data: str = Form(...)):
    try:
        data = json.loads(json_data)
        input_path = os.path.join(TEMP_DIR, f"in_{file.filename}")
        
        with open(input_path, "wb") as f:
            f.write(await file.read())

        converter = ImageConverter()
        gemini = GeminiVisionService()
        filler = PDFFormFiller(input_path)
        
        images_pages = converter.pdf_to_images(input_path)
        all_keys = list(data.keys())

        print(f"[MAIN] Procesando {len(images_pages)} páginas...")

        for img, p_num in images_pages:
            print(f"[MAIN] Analizando Página {p_num}...")
            
            # --- FILTRO DE SEGURIDAD POR PÁGINA ---
            # Si es la página 1, buscamos TODO (incluyendo accionistas)
            # Si es la página 2, excluimos las llaves que contengan "accionista"
            if p_num == 1:
                keys_for_page = all_keys
            else:
                # Evita que Gemini confunda la tabla PEP con la de Accionistas
                keys_for_page = [k for k in all_keys if "accionista" not in k.lower()]
            
            # Analizar solo con las llaves permitidas para esta página
            detected_fields = gemini.analyze_form_page(img, keys_for_page)
            
            if detected_fields:
                print(f"[MAIN] Página {p_num}: {len(detected_fields)} campos detectados.")
                filler.fill_page(p_num - 1, detected_fields, data)
            else:
                print(f"[WARNING] Página {p_num}: No se detectaron campos.")

        # Generar salida
        buffer = BytesIO()
        filler.save(buffer)
        buffer.seek(0)
        
        if os.path.exists(input_path):
            os.remove(input_path)

        headers = {
            "Content-Disposition": f"attachment; filename=filled_{file.filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8001, reload=True)
    