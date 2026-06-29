"""
Extrae texto de un PDF escaneado usando OCR (Tesseract + PyMuPDF).
Uso: python extraer.py <archivo.pdf> [pagina_inicio] [pagina_fin]

Ejemplos:
  python extraer.py "../ANALISIS DE PRECIOS UNITARIOS EN EDIFICACIONES.pdf"
  python extraer.py "../ANALISIS DE PRECIOS UNITARIOS EN EDIFICACIONES.pdf" 1 10
"""
import sys
import os
import fitz          # PyMuPDF
import pytesseract
from PIL import Image
import io

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extraer_texto_pdf(pdf_path, pagina_inicio=1, pagina_fin=None, dpi=250, lang='spa+eng'):
    doc = fitz.open(pdf_path)
    total = len(doc)
    pagina_fin = min(pagina_fin or total, total)

    print(f"PDF: {os.path.basename(pdf_path)}")
    print(f"Total paginas: {total} - Extrayendo paginas {pagina_inicio} a {pagina_fin}")
    print("=" * 70)

    texto_total = []

    for num in range(pagina_inicio - 1, pagina_fin):
        page = doc[num]
        # Renderizar página como imagen a alta resolución
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # OCR
        texto = pytesseract.image_to_string(img, lang=lang, config='--psm 6')

        print(f"\n{'-' * 70}")
        print(f"  PAGINA {num + 1}")
        print(f"{'-' * 70}")
        print(texto.strip())
        texto_total.append(f"=== PÁGINA {num + 1} ===\n{texto.strip()}")

    doc.close()
    return "\n\n".join(texto_total)


def guardar_txt(texto, pdf_path, sufijo=""):
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{base}{sufijo}.txt")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"\n{'=' * 70}")
    print(f"Guardado en: {salida}")
    return salida


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf = sys.argv[1]
    inicio = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    fin    = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if not os.path.exists(pdf):
        print(f"Error: No se encuentra el archivo '{pdf}'")
        sys.exit(1)

    texto = extraer_texto_pdf(pdf, inicio, fin)
    sufijo = f"_p{inicio}-{fin}" if fin else ""
    guardar_txt(texto, pdf, sufijo)
