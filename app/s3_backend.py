from flask import Flask, jsonify, request, send_file
import psycopg2
import os

app = Flask(__name__)

DB_HOST = "192.168.178.121"
DB_NAME = "s3_backend_db"
DB_USER = "postgres"
DB_PASSWORD = "PostgresPassword"
DB_PORT = "5432"


def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Fehler bei der Verbindung zur Datenbank: {e}")
        return None


@app.route("/guidelines", methods=["GET"])
def get_guidelines():
    """Gibt alle verfügbaren Leitlinien zurück."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM guidelines")
    guidelines = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([{"id": g[0], "title": g[1]} for g in guidelines])


@app.route("/guidelines/<int:guideline_id>", methods=["GET"])
def get_guideline(guideline_id):
    """Gibt eine einzelne Leitlinie anhand der ID zurück."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guidelines WHERE id = %s", (guideline_id,))
    guideline = cursor.fetchone()
    cursor.close()
    conn.close()

    if guideline:
        columns = [desc[0] for desc in cursor.description]
        return jsonify(dict(zip(columns, guideline)))
    return jsonify({"error": "Leitlinie nicht gefunden"}), 404


@app.route("/guidelines/search", methods=["GET"])
def search_guidelines():
    """Ermöglicht das Durchsuchen der extrahierten Texte."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Bitte geben Sie einen Suchbegriff an"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, extracted_text FROM guidelines WHERE extracted_text ILIKE %s", (f"%{query}%",))
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{"id": r[0], "title": r[1], "extracted_text": r[2]} for r in results])


@app.route("/guidelines/<int:guideline_id>/download", methods=["GET"])
def download_guideline_pdf(guideline_id):
    """Stellt das PDF-Dokument einer Leitlinie zum Download bereit."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()
    cursor.execute("SELECT title, pdf FROM guidelines WHERE id = %s", (guideline_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row and row[1]:
        pdf_path = f"temp_{guideline_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(row[1])

        return send_file(pdf_path, as_attachment=True, download_name=f"{row[0]}.pdf")

    return jsonify({"error": "PDF nicht gefunden"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

