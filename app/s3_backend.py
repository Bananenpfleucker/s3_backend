from flask import Flask, jsonify, request, send_file
import sqlite3
import os

app = Flask(__name__)
DB_FILE = "leitlinien.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/guidelines", methods=["GET"])
def get_guidelines():
    """Gibt alle verfügbaren Leitlinien zurück."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM guidelines")
    guidelines = cursor.fetchall()
    conn.close()

    return jsonify([dict(g) for g in guidelines])


@app.route("/guidelines/<int:guideline_id>", methods=["GET"])
def get_guideline(guideline_id):
    """Gibt eine einzelne Leitlinie anhand der ID zurück."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guidelines WHERE id = ?", (guideline_id,))
    guideline = cursor.fetchone()
    conn.close()

    if guideline:
        return jsonify(dict(guideline))
    return jsonify({"error": "Leitlinie nicht gefunden"}), 404


@app.route("/guidelines/search", methods=["GET"])
def search_guidelines():
    """Ermöglicht das Durchsuchen der extrahierten Texte."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Bitte geben Sie einen Suchbegriff an"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, extracted_text FROM guidelines WHERE extracted_text LIKE ?", (f"%{query}%",))
    results = cursor.fetchall()
    conn.close()

    return jsonify([dict(r) for r in results])


@app.route("/guidelines/<int:guideline_id>/download", methods=["GET"])
def download_guideline_pdf(guideline_id):
    """Stellt das PDF-Dokument einer Leitlinie zum Download bereit."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, pdf FROM guidelines WHERE id = ?", (guideline_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row["pdf"]:
        pdf_path = f"temp_{guideline_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(row["pdf"])

        return send_file(pdf_path, as_attachment=True, download_name=f"{row['title']}.pdf")

    return jsonify({"error": "PDF nicht gefunden"}), 404


if __name__ == "__main__":
    app.run(debug=True)
