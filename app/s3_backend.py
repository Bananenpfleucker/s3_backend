from flask import Flask, jsonify, request, send_file
import psycopg2
import os

app = Flask(__name__)

# Datenbankverbindungsdetails
DB_HOST = "192.168.178.121"
DB_NAME = "s3_backend_db"
DB_USER = "postgres"
DB_PASSWORD = "PostgresPassword"
DB_PORT = "5432"


def get_db_connection():
    """Stellt eine Verbindung zur PostgreSQL-Datenbank her."""
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
    """Gibt gültige Leitlinien mit Filter- und Pagination-Optionen zurück."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    # Query-Parameter abrufen
    limit = request.args.get("limit", 20, type=int)  # Standard: 20
    offset = request.args.get("offset", 0, type=int)
    title = request.args.get("title", type=str)
    lversion = request.args.get("lversion", type=str)
    stand = request.args.get("stand", type=str)
    remark = request.args.get("remark", type=str)

    # Basis-Query (nur gültige Leitlinien)
    query = """
        SELECT id, awmf_guideline_id, title, lversion, valid_until, stand, remark
        FROM guidelines
        WHERE (valid_until IS NULL OR valid_until > NOW())
    """
    params = []

    # Dynamische Filter anwenden
    if title:
        query += " AND title ILIKE %s"
        params.append(f"%{title}%")
    if lversion:
        query += " AND lversion = %s"
        params.append(lversion)
    if stand:
        query += " AND stand = %s"
        params.append(stand)
    if remark:
        query += " AND remark ILIKE %s"
        params.append(f"%{remark}%")

    # Pagination
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    # SQL-Abfrage ausführen
    cursor.execute(query, tuple(params))
    guidelines = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([
        {
            "id": g[0],
            "awmf_guideline_id": g[1],
            "title": g[2],
            "lversion": g[3],
            "valid_until": g[4],
            "stand": g[5],
            "remark": g[6],
        }
        for g in guidelines
    ])


@app.route("/guidelines/valid", methods=["GET"])
def get_valid_guidelines():
    """Gibt nur Leitlinien zurück, die noch gültig sind (valid_until > NOW())."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, awmf_guideline_id, title, lversion, valid_until, stand, remark
        FROM guidelines
        WHERE valid_until IS NULL OR valid_until > NOW()
        ORDER BY created_at DESC
    """)

    guidelines = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([
        {
            "id": g[0],
            "awmf_guideline_id": g[1],
            "title": g[2],
            "lversion": g[3],
            "valid_until": g[4],
            "stand": g[5],
            "remark": g[6],
        }
        for g in guidelines
    ])


@app.route("/guidelines/expired", methods=["GET"])
def get_expired_guidelines():
    """Gibt nur abgelaufene Leitlinien zurück (valid_until <= NOW())."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, awmf_guideline_id, title, lversion, valid_until, stand, remark
        FROM guidelines
        WHERE valid_until IS NOT NULL AND valid_until <= NOW()
        ORDER BY valid_until DESC
    """)

    guidelines = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([
        {
            "id": g[0],
            "awmf_guideline_id": g[1],
            "title": g[2],
            "lversion": g[3],
            "valid_until": g[4],
            "stand": g[5],
            "remark": g[6],
        }
        for g in guidelines
    ])


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

    cursor.execute("""
        SELECT id, awmf_guideline_id, title, lversion, extracted_text
        FROM guidelines
        WHERE extracted_text ILIKE %s
    """, (f"%{query}%",))

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "awmf_guideline_id": r[1],
            "title": r[2],
            "lversion": r[3],
            "extracted_text": r[4],
        }
        for r in results
    ])


@app.route("/guidelines/<int:guideline_id>/download", methods=["GET"])
def download_guideline_pdf(guideline_id):
    """Stellt das PDF-Dokument einer Leitlinie zum Download bereit."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    cursor.execute("SELECT awmf_guideline_id, pdf FROM guidelines WHERE id = %s", (guideline_id,))
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
