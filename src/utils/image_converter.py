import os
import base64
import shutil
from io import BytesIO
from typing import List, Tuple
from PIL import Image
from pdf2image import convert_from_path

class ImageConverter:
    @staticmethod
    def _resolve_poppler_path() -> str | None:
        """
        Devuelve la ruta de Poppler si es necesaria.
        Si Poppler ya está en PATH, retorna None para que pdf2image use el PATH del sistema.
        """
        # 1) Prioridad: variable de entorno explícita
        poppler_env_path = os.getenv("POPPLER_PATH")
        if poppler_env_path and os.path.isdir(poppler_env_path):
            return poppler_env_path

        # 2) Si los binarios están en PATH, no se necesita ruta fija
        if shutil.which("pdftoppm") and shutil.which("pdfinfo"):
            return None

        raise RuntimeError(
            "Poppler no está disponible. Instala Poppler y agrega sus binarios al PATH, "
            "o define la variable de entorno POPPLER_PATH apuntando a la carpeta 'bin'."
        )

    @staticmethod
    def pdf_to_images(pdf_path: str) -> List[Tuple[Image.Image, int]]:
        try:
            poppler_path = ImageConverter._resolve_poppler_path()
            pil_images = convert_from_path(
                pdf_path,
                dpi=150,
                poppler_path=poppler_path
            )
            return [(img, i + 1) for i, img in enumerate(pil_images)]
        except Exception as e:
            raise RuntimeError(f"Error en conversión PDF a imágenes: {e}") from e

    @staticmethod
    def image_to_base64(image: Image.Image) -> str:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @staticmethod
    def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
        # Esta es la función que faltaba en el error image_ce9936.png
        return image.size   