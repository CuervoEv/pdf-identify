import os
import base64
from io import BytesIO
from typing import List, Tuple
from PIL import Image
from pdf2image import convert_from_path

class ImageConverter:
    @staticmethod
    def pdf_to_images(pdf_path: str) -> List[Tuple[Image.Image, int]]:
        # Tu ruta de Poppler verificada
        POPPLER_PATH = r"C:\src\poppler\poppler-25.12.0\Library\bin"
        
        try:
            pil_images = convert_from_path(
                pdf_path, 
                dpi=150,
                poppler_path=POPPLER_PATH
            )
            return [(img, i+1) for i, img in enumerate(pil_images)]
        except Exception as e:
            raise Exception(f"Error en conversión PDF: {str(e)}")

    @staticmethod
    def image_to_base64(image: Image.Image) -> str:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @staticmethod
    def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
        # Esta es la función que faltaba en el error image_ce9936.png
        return image.size   