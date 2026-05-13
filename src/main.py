import os
import json
import logging
import uvicorn
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

# Importaciones locales
from src.services.gemini_service import GeminiVisionService
from src.services.pdf_filler import PDFFormFiller
from src.utils.image_converter import ImageConverter

load_dotenv()

app = FastAPI()
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)
logger = logging.getLogger(__name__)

@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...), 
    json_maestro: str = Form("{}")
):
    """
    ENDPOINT UNIFICADO (Recomendado)
    Recibe el PDF y el JSON Maestro. Detecta automáticamente si es AcroForm o Plano.
    """
    input_path = None
    try:
        data = json.loads(json_maestro)
        input_path = os.path.join(TEMP_DIR, f"auto_{file.filename}")
        
        with open(input_path, "wb") as f:
            f.write(await file.read())

        filler = PDFFormFiller(input_path)

        # RUTA A: Es un AcroForm nativo (PDF Rellenoable)
        if filler.is_acroform():
            logger.info("AcroForm detectado. Rellenando nativamente.")
            # Aquí podrías usar Gemini solo para cruzar las llaves si es necesario,
            # pero por ahora intentamos el match directo de llaves normalizadas.
            filler.fill_acroform(data)

        # RUTA B: Es un PDF Plano (requiere visión)
        else:
            logger.info("PDF Plano detectado. Iniciando pipeline de visión.")
            converter = ImageConverter()
            gemini = GeminiVisionService()
            images_pages = converter.pdf_to_images(input_path)
            
            # Llaves esperadas a partir del maestro
            expected_keys = list(data.keys())

            for img, p_num in images_pages:
                # Filtrado de llaves por página (tu lógica original)
                keys_for_page = expected_keys
                if p_num > 1:
                    keys_for_page = [k for k in expected_keys if "accionista" not in str(k).lower()]

                detected_fields = gemini.analyze_form_page(
                    img,
                    keys_for_page,
                    page_num=p_num,
                    debug_dir=TEMP_DIR,
                )
                
                # Rellenar la página con las coordenadas detectadas
                page_values = {str(f.get("id")): data.get(f.get("id"), "") for f in detected_fields}
                filler.fill_page(p_num - 1, detected_fields, page_values)
                
                if hasattr(img, "close"): img.close()

        # Generar salida
        buffer = BytesIO()
        filler.save(buffer)
        buffer.seek(0)

        headers = {
            "Content-Disposition": f"attachment; filename=filled_{file.filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

    except Exception as e:
        logger.error(f"Error en /process-document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if input_path and os.path.exists(input_path): os.remove(input_path)


# =====================================================================
# ENDPOINTS LEGACY (Mantienen compatibilidad con tu flujo actual de n8n)
# =====================================================================

@app.post("/get-map")
async def get_map(file: UploadFile = File(...), expected_keys: str = Form("[]")):
    input_path = None
    images_pages = []
    try:
        try:
            keys_list = json.loads(expected_keys)
        except:
            keys_list = []

        input_path = os.path.join(TEMP_DIR, f"map_{file.filename}")
        with open(input_path, "wb") as f:
            f.write(await file.read())

        converter = ImageConverter()
        gemini = GeminiVisionService()
        images_pages = converter.pdf_to_images(input_path)
        full_map = {}

        for img, p_num in images_pages:
            keys_for_page = keys_list
            if p_num > 1:
                keys_for_page = [k for k in keys_list if "accionista" not in str(k).lower()]

            detected_fields = gemini.analyze_form_page(
                img,
                keys_for_page,
                page_num=p_num,
                debug_dir=TEMP_DIR,
            )
            full_map[f"page_{p_num}"] = detected_fields

        return JSONResponse(content={"map": full_map, "filename": file.filename})

    except Exception as e:
        logger.error(f"Error en /get-map: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for img, _ in images_pages:
            if hasattr(img, "close"): img.close()
        if input_path and os.path.exists(input_path): os.remove(input_path)


@app.post("/fill-from-map")
async def fill_from_map(file: UploadFile = File(...), mapped_data: str = Form(...)):
    input_path = None
    try:
        final_instructions = json.loads(mapped_data)
        input_path = os.path.join(TEMP_DIR, f"fill_{file.filename}")
        
        with open(input_path, "wb") as f:
            f.write(await file.read())

        filler = PDFFormFiller(input_path)

        for page_key, fields in final_instructions.items():
            try:
                p_num_idx = int(page_key.replace("page_", "")) - 1
                page_values = {str(f.get("id")): f.get("value", "") for f in fields}
                filler.fill_page(p_num_idx, fields, page_values)
            except Exception as e:
                logger.warning(f"Error procesando {page_key}: {e}")

        buffer = BytesIO()
        filler.save(buffer)
        buffer.seek(0)

        headers = {
            "Content-Disposition": f"attachment; filename=filled_{file.filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

    except Exception as e:
        logger.error(f"Error en /fill-from-map: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if input_path and os.path.exists(input_path): os.remove(input_path)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)