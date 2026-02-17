from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any
from config.settings import COORDINATE_SCALE


class ExcelFiller:
    """Inserta datos en archivos Excel priorizando celdas detectadas."""

    def __init__(self, excel_path: str):
        """
        Inicializa el rellenador de Excel.
        
        Args:
            excel_path: Ruta del archivo Excel
        """
        self.workbook = load_workbook(excel_path)
        self.worksheet = self.workbook.active
        self.excel_path = excel_path

    def fill_cells(self, fields: List[Dict[str, Any]], data: Dict[str, str]) -> None:
        """
        Rellena celdas en Excel basado en campos detectados.
        
        Prioriza:
        1. Celdas combinadas existentes
        2. Celdas simples detectadas
        3. Ajusta ancho automáticamente
        
        Args:
            fields: Campos detectados con coordenadas normalizadas
            data: Diccionario {campo_id: valor}
        """
        for field in fields:
            field_id = field['id']
            if field_id not in data:
                continue
            
            # Convertir coordenadas normalizadas a referencias de celda
            cell_ref = self._normalize_to_cell_reference(
                field['coordenadas_x'],
                field['coordenadas_y'],
                field.get('ancho_estimado', 100),
                field.get('alto_estimado', 20)
            )
            
            if cell_ref:
                self._insert_into_cell(cell_ref, data[field_id])

    def _normalize_to_cell_reference(self, norm_x: float, norm_y: float, 
                                      norm_width: float, norm_height: float) -> str:
        """
        Convierte coordenadas normalizadas de imagen a referencia de celda Excel.
        
        Args:
            norm_x, norm_y: Coordenadas normalizadas [0-1000]
            norm_width, norm_height: Dimensiones normalizadas
            
        Returns:
            Referencia de celda (ej: 'B3') o None si no se puede determinar
        """
        # Estimación heurística: mapear coordenadas a columnas/filas
        # Asumiendo una disposición estándar de formulario
        
        # Convertir X normalizada a número de columna (A-Z)
        col_index = int((norm_x / COORDINATE_SCALE) * 26) + 1
        col_index = max(1, min(26, col_index))  # Limitar a A-Z
        
        # Convertir Y normalizada a número de fila
        row_index = int((norm_y / COORDINATE_SCALE) * 100) + 1
        row_index = max(1, row_index)
        
        col_letter = get_column_letter(col_index)
        cell_ref = f"{col_letter}{row_index}"
        
        return cell_ref

    def _insert_into_cell(self, cell_ref: str, value: str) -> None:
        """
        Inserta valor en una celda y ajusta el ancho.
        
        Args:
            cell_ref: Referencia de celda (ej: 'B3')
            value: Valor a insertar
        """
        try:
            cell = self.worksheet[cell_ref]
            cell.value = value
            
            # Auto-ajustar ancho de columna
            col_letter = cell_ref[0]
            col_dim = self.worksheet.column_dimensions[col_letter]
            
            # Calcular ancho basado en longitud del contenido
            content_width = len(str(value)) * 1.2 + 2
            current_width = col_dim.width or 10
            
            if content_width > current_width:
                col_dim.width = min(content_width, 50)  # Máximo 50 caracteres
            
            # Si el valor tiene saltos de línea, ajustar altura de fila
            if '\n' in str(value):
                row_num = int(cell_ref[1:])
                row_dim = self.worksheet.row_dimensions[row_num]
                row_dim.height = min(len(str(value).split('\n')) * 15, 100)
        
        except Exception as e:
            # Si la celda no existe o hay error, intentar crear
            try:
                self.worksheet[cell_ref] = value
            except Exception as inner_e:
                raise Exception(f"Error al insertar en celda {cell_ref}: {str(inner_e)}")

    def save(self, output_path: str) -> None:
        """
        Guarda el Excel modificado.
        
        Args:
            output_path: Ruta de salida del Excel rellenado
        """
        self.workbook.save(output_path)
        self.workbook.close()

    def close(self) -> None:
        """Cierra el libro de Excel."""
        if self.workbook:
            self.workbook.close()
