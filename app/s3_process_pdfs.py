import os
import requests
import sqlite3
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import pytesseract
import re
from multiprocessing import Pool, cpu_count

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DB_FILE = "leitlinien.db"


def extract_text_from_pdf(pdf_data):
    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        extracted_text = ""

        for page in doc:
            text = page.get_text("text")  # Versuch, Text direkt zu extrahieren
            if text.strip():
                extracted_text += text + "\n"
            else:
                images = convert_from_bytes(pdf_data, dpi=150)
                for img in images:
                    text = pytesseract.image_to_string(img, lang="deu",
                                                       config="--psm 3 --oem 1 -c preserve_interword_spaces=1")
                    extracted_text += text + "\n"

        return extracted_text.strip()
    except Exception as e:
        print(f"Fehler beim Extrahieren des PDFs: {e}")
        return None


def clean_ocr_text(text):

    text = text.replace("-\n", "  ")
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # Ersetze einzelne Zeilenumbrüche durch Leerzeichen
    text = re.sub(r"\n{3,}", "\n\n", text)  # Reduziert mehr als zwei Zeilenumbrüche auf zwei
    text = re.sub(r"\s+", " ", text).strip()
    return text


def process_single_pdf(row):
    pdf_id, pdf_data = row
    print(f"Verarbeite PDF mit ID {pdf_id}...")

    text = extract_text_from_pdf(pdf_data)
    if text:
        text = clean_ocr_text(text)
        return (pdf_id, text)
    return None


def process_pdfs():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(guidelines)")
    columns = [col[1] for col in cursor.fetchall()]
    if "extracted_text" not in columns:
        cursor.execute("ALTER TABLE guidelines ADD COLUMN extracted_text TEXT")
        conn.commit()

    cursor.execute("SELECT id, pdf FROM guidelines WHERE pdf IS NOT NULL AND extracted_text IS NULL")
    rows = cursor.fetchall()

    with Pool(cpu_count()) as pool:
        results = pool.map(process_single_pdf, rows)

    for result in results:
        if result:
            pdf_id, text = result
            cursor.execute("UPDATE guidelines SET extracted_text = ? WHERE id = ?", (text, pdf_id))
            conn.commit()
            print(f"✔ Text für PDF {pdf_id} gespeichert.")

    conn.close()
    print("Alle PDFs wurden verarbeitet.")


if __name__ == "__main__":
    process_pdfs()
