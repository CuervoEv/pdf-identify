import os
import json
from PIL import Image
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

# @app.post("/detectar-font-size")
# async def detectar_font_size(file: UploadFile = File(...)):
#     filler = None
#     tmp_path = None
#     try:
#         pdf_bytes = await file.read()
#         input_hash = hashlib.sha256(pdf_bytes).hexdigest()
#         cache_path = os.path.join(TEMP_DIR, f"fontsize_{input_hash}.json")
        
#         # Verificar caché con protección
#         if os.path.exists(cache_path):
#             try:
#                 with open(cache_path, "r") as f:
#                     content = f.read().strip()
#                     if content:
#                         cached = json.loads(content)
#                         logger.info(f"[detectar-font-size] Cache hit: {cached.get('font_size', '?')}pt")
#                         return JSONResponse(content=cached)
#                     else:
#                         logger.warning("[detectar-font-size] Caché vacío, regenerando...")
#                         os.remove(cache_path)
#             except json.JSONDecodeError:
#                 logger.warning("[detectar-font-size] Caché corrupto, regenerando...")
#                 os.remove(cache_path)
        
#         # Guardar PDF temporal
#         tmp_path = os.path.join(TEMP_DIR, f"fontsize_{file.filename}")
#         with open(tmp_path, "wb") as f:
#             f.write(pdf_bytes)
        
#         filler = PDFFormFiller(tmp_path)
        
#         # Detectar con PyMuPDF
#         font_size = filler.detect_font_size(0)
#         metodo = "pymupdf"
        
#         # Si es fallback, usar Gemini visión
#         if font_size in (8.0, 9.0, 9.5, 10.0) and filler.doc[0].get_text("words").__len__() < 5:
#             logger.info("[detectar-font-size] PDF escaneado, usando Gemini...")
#             gemini = GeminiVisionService()
#             page = filler.doc[0]
#             pix = page.get_pixmap(dpi=150)
#             img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
#             font_size = gemini.estimar_tamano_fuente(img, page.rect.width, page.rect.height)
#             metodo = "gemini"
        
#         result = {
#             "pdf_hash": input_hash,
#             "filename": file.filename,
#             "font_size": font_size,
#             "metodo": metodo
#         }
        
#         # Guardar caché
#         with open(cache_path, "w") as f:
#             json.dump(result, f)
        
#         logger.info(f"[detectar-font-size] Final: {font_size}pt ({metodo})")
#         return JSONResponse(content=result)
    
#     except json.JSONDecodeError as e:
#         logger.error(f"[detectar-font-size] JSONDecodeError: {e}")
#         return JSONResponse(content={"font_size": 9.0, "metodo": "fallback_error"})
#     except Exception as e:
#         logger.error(f"[detectar-font-size] Error: {type(e).__name__}: {e}")
#         return JSONResponse(status_code=200, content={"font_size": 9.0, "metodo": "fallback_error", "error": str(e)})
#     finally:
#         if filler is not None and hasattr(filler, "doc"):
#             try:
#                 filler.doc.close()
#             except:
#                 pass
#         if tmp_path and os.path.exists(tmp_path):
#             try:
#                 os.remove(tmp_path)
#             except:
#                 pass
@app.post("/get-map")
async def get_map(file: UploadFile = File(...), expected_keys: str = Form("[]")):
    input_path = None
    images_pages = []
    try:
        try:
            keys_list = json.loads(expected_keys)
        except Exception:
            keys_list = []

        # Guardar PDF temporal
        pdf_bytes = await file.read()
        input_hash = hashlib.sha256(pdf_bytes).hexdigest()
        input_path = os.path.join(TEMP_DIR, f"map_{file.filename}")
        with open(input_path, "wb") as f:
            f.write(pdf_bytes)

        converter = ImageConverter()
        gemini = GeminiVisionService()
        images_pages = converter.pdf_to_images(input_path)
        full_map = {}

        # ─── Detectar tamaño de fuente ───
        # 1. Buscar en caché primero
        font_size_detected = None
        cache_path = os.path.join(TEMP_DIR, f"fontsize_{input_hash}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                font_size_detected = json.load(f)["font_size"]
            logger.info(f"[get-map] Font size desde caché: {font_size_detected}pt")
        
        # 2. Si no hay caché, detectar ahora
        if font_size_detected is None:
            filler = PDFFormFiller(input_path)
            if images_pages:
                font_size_detected = filler.detect_font_size(
                    0,
                    gemini_service=gemini,
                    image_pil=images_pages[0][0]
                )
            else:
                font_size_detected = 9.0
            logger.info(f"[get-map] Font size detectado: {font_size_detected}pt")
            
            # Guardar en caché para futuras llamadas
            with open(cache_path, "w") as f:
                json.dump({"pdf_hash": input_hash, "font_size": font_size_detected}, f)
        # ─────────────────────────────────

        # Procesar cada página con el tamaño detectado
        for img, p_num in images_pages:
            keys_for_page = keys_list
            if p_num > 1:
                keys_for_page = [k for k in keys_list if "accionista" not in str(k).lower()]
            detected_fields = gemini.analyze_form_page(
                img, keys_for_page, page_num=p_num, debug_dir=TEMP_DIR,
                font_size_pt=font_size_detected
        )
            full_map[f"page_{p_num}"] = detected_fields

        return JSONResponse(content={
            "map": full_map,
            "filename": file.filename,
            "font_size": font_size_detected
        })

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

@app.post("/detectar-font-size")
async def detectar_font_size(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        input_hash = hashlib.sha256(pdf_bytes).hexdigest()
        cache_path = os.path.join(TEMP_DIR, f"fontsize_{input_hash}.json")
        
        # Verificar caché
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                content = f.read().strip()
                if content:
                    cached = json.loads(content)
                    logger.info(f"[detectar-font-size] Cache hit: {cached['font_size']}pt")
                    return JSONResponse(content=cached)
        
        # Usar bytes directamente, sin archivo temporal
        filler = PDFFormFiller(pdf_bytes, from_bytes=True)
        font_size = filler.detect_font_size(0)
        metodo = "pymupdf"
        
        # Si no hay texto, usar Gemini
        if len(filler.doc[0].get_text("words")) < 5:
            logger.info("[detectar-font-size] PDF escaneado, usando Gemini...")
            gemini = GeminiVisionService()
            page = filler.doc[0]
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            font_size = gemini.estimar_tamano_fuente(img, page.rect.width, page.rect.height)
            metodo = "gemini"
        
        filler.doc.close()
        
        result = {"font_size": font_size, "metodo": metodo}
        with open(cache_path, "w") as f:
            json.dump(result, f)
        
        logger.info(f"[detectar-font-size] {font_size}pt ({metodo})")
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"[detectar-font-size] Error: {e}")
        return JSONResponse(content={"font_size": 9.0, "metodo": "error"})

# ... (resto de endpoints /get-map, /fill-from-map, /health iguales) ...
@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)