import os
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from src.services.gemini_service import GeminiVisionService

load_dotenv() # <--- IMPORTANTE: Carga tu GOOGLE_API_KEY del .env

from src.services.gemini_service import GeminiVisionService
from src.services.pdf_filler import PDFFormFiller
from src.utils.image_converter import ImageConverter


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
        images_pages = converter.pdf_to_images(input_path)
        gemini = GeminiVisionService()
        filler = PDFFormFiller(input_path)

        keys_to_search = list(data.keys())

        for idx, (img, p_num) in enumerate(images_pages):
            detected_fields = gemini.analyze_form_page(img, keys_to_search)
            print(f"[MAIN] Página {p_num}: campos detectados -> {[f['id'] for f in detected_fields]}")
            filler.fill_page(p_num - 1, detected_fields, data)

            from io import BytesIO
            buffer = BytesIO()
            filler.save(buffer)
            buffer.seek(0)
            headers = {"Content-Disposition": f"attachment; filename={os.path.splitext(file.filename)[0]}.pdf"}
            return StreamingResponse(buffer, media_type="application/pdf", headers=headers)
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run("src.main:app", host="0.0.0.0", port=8001, reload=True)
    except Exception as e:
        print(f"Fallo al arrancar el servidor: {e}")