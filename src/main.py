import os
import json
import hashlib
import logging
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

from src.services.gemini_service import GeminiVisionService, MappingResponse
from src.services.pdf_filler import PDFFormFiller
from src.utils.image_converter import ImageConverter

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("form_filler_api")

app = FastAPI(title="PDF Auto-Filler API", version="1.1.0")
TEMP_DIR = "temp"
AUDIT_DIR = "auditoria"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)


@app.post("/get-map")
async def get_map(file: UploadFile = File(...), expected_keys: str = Form("[]")):
    input_path = None
    images_pages = []
    try:
        try:
            keys_list = json.loads(expected_keys)
        except Exception:
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
                img, keys_for_page, page_num=p_num, debug_dir=TEMP_DIR
            )
            full_map[f"page_{p_num}"] = detected_fields

        return JSONResponse(content={"map": full_map, "filename": file.filename})

    except Exception as e:
        logger.error(f"Error en /get-map: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for img, _ in images_pages:
            if hasattr(img, "close"):
                img.close()
        if input_path and os.path.exists(input_path):
            os.remove(input_path)


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
            "Access-Control-Expose-Headers": "Content-Disposition",
        }
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)

    except Exception as e:
        logger.error(f"Error en /fill-from-map: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)


# ... (Imports iniciales iguales) ...

@app.post("/procesar-formulario")
async def procesar_formulario(
    pdf: UploadFile = File(...),
    json_maestro: str = Form(..., description="JSON string con la base maestra"),
):
    pdf_bytes = await pdf.read()
    input_hash = hashlib.sha256(pdf_bytes).hexdigest()
    try:
        maestro = json.loads(json_maestro)
    except Exception:
        raise HTTPException(status_code=400, detail="json_maestro no es un JSON válido.")

    try:
        filler = PDFFormFiller(pdf_bytes, from_bytes=True)
        gemini = GeminiVisionService()

        if filler.is_acroform:
            logger.info("PDF AcroForm detectado. Extrayendo widgets...")
            campos = filler.get_acroform_fields()
            mapping: MappingResponse = gemini.map_fields_with_master(
                pdf_bytes, maestro, campos, pdf_is_acroform=True
            )
            filler.fill_pdf(
                [m.model_dump() for m in mapping.mappings],
                page_mode="acroform",
            )
        else:
            logger.info("PDF plano. Usando detección visual...")
            converter = ImageConverter()
            tmp_path = os.path.join(TEMP_DIR, f"procesar_{input_hash}.pdf")
            with open(tmp_path, "wb") as f:
                f.write(pdf_bytes)
            
            images_pages = converter.pdf_to_images(tmp_path)
            all_fields = []
            images_dict = {}  # NUEVO: Diccionario para retener imágenes vivas
            
            for img, p_num in images_pages:
                detected = gemini.analyze_form_page(
                    img, list(maestro.keys()), page_num=p_num, debug_dir=TEMP_DIR
                )
                for d in detected:
                    d["page"] = p_num - 1
                all_fields.extend(detected)
                
                images_dict[p_num - 1] = img  # Guardar imagen sin cerrar

            os.remove(tmp_path)

            mapping: MappingResponse = gemini.map_fields_with_master(
                pdf_bytes, maestro, all_fields, pdf_is_acroform=False
            )
            
            filler.fill_pdf(
                [m.model_dump() for m in mapping.mappings],
                page_mode="overlay",
                gemini_service=gemini,      # Pasar Gemini para detección de fuente
                images_by_page=images_dict   # Pasar imágenes para detección visual
            )
            
            # Liberar memoria cerrando las imágenes
            for img in images_dict.values():
                if hasattr(img, "close"):
                    img.close()

        buffer = BytesIO()
        filler.save(buffer)
        buffer.seek(0)
        output_pdf_bytes = buffer.read()
        output_hash = hashlib.sha256(output_pdf_bytes).hexdigest()

        audit_data = {
            "input_hash": input_hash,
            "output_hash": output_hash,
            "tipo_pdf": "acroform" if filler.is_acroform else "plano",
            "mappings": [m.model_dump() for m in mapping.mappings],
            "unmapped_keys": mapping.unmapped_master_keys,
            "notes": mapping.notes,
        }

        audit_path = os.path.join(AUDIT_DIR, f"{input_hash}.json")
        with open(audit_path, "w", encoding="utf-8") as af:
            json.dump(audit_data, af, ensure_ascii=False, indent=2)

        return StreamingResponse(
            BytesIO(output_pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="filled_{pdf.filename}"',
                "X-Audit-Trail": json.dumps(audit_data, ensure_ascii=False),
            },
        )

    except Exception as e:
        logger.error(f"Error en /procesar-formulario: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ... (resto de endpoints /get-map, /fill-from-map, /health iguales) ...
@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)