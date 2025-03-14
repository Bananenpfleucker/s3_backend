from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Datenbankverbindungsdetails
DB_HOST = "192.168.178.121"
DB_NAME = "s3_backend_db"
DB_USER = "postgres"
DB_PASSWORD = "PostgresPassword"
DB_PORT = "5432"


def json_serial(guidelines):
    return jsonify(
        [
            {
                "id": g[0],
                "awmf_guideline_id": g[1],
                "detail_page_url": g[2],
                "pdf_url": g[3],
                "pdf": g[4],
                "extracted_text": [5],
                "created_at": g[6],
                "compressed_text": g[7],
                "titel": g[8],
                "lversion": g[9],
                "valid_until": g[10],
                "stand": g[11],
                "aktueller_hinweis": g[12]
            }
            for g in guidelines
        ]
    )


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


def build_order_clause(order_by, order_direction, allowed_columns):
    """für SQL-Abfragen mit Spaltennamen."""
    if order_by not in allowed_columns:
        order_by = "created_at"  # Standard
    order_direction = "DESC" if order_direction == "desc" else "ASC"
    return f" ORDER BY {order_by} {order_direction}"


@app.route("/guidelines", methods=["GET"])
def get_guidelines():
    """Gibt gültige Leitlinien mit Filter, Sortierung und Pagination zurueck."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    # Query-Parameter abrufen
    limit = request.args.get("limit", 20, type=int)  # Standard: 20
    offset = request.args.get("offset", 0, type=int)
    order_by = request.args.get("order_by", "created_at")
    order_direction = request.args.get("order_direction", "desc")

    # Erlaubte Sortierspalten
    allowed_columns = ["created_at", "title", "valid_until", "stand", "lversion"]
    order_clause = build_order_clause(order_by, order_direction, allowed_columns)

    # Basis-Query (nur gültige Leitlinien)
    query = f"""
        SELECT  id,
                awmf_guideline_id,
                null as detail_page_url,
                null as pdf_url,
                null as pdf,
                null as extracted_text,
                created_at,
                null compressed_text,  
                title,
                lversion,
                valid_until,
                stand,
                aktueller_hinweis
        FROM guidelines
        WHERE (valid_until IS NULL OR valid_until > NOW())
        {order_clause}
        LIMIT %s OFFSET %s
    """

    cursor.execute(query, (limit, offset))
    guidelines = cursor.fetchall()

    cursor.close()
    conn.close()

    return json_serial(guidelines)


@app.route("/guidelines/latest", methods=["GET"])
def get_latest_guidelines():
    """Gibt die letzten vier hinzugefügten Leitlinien zurück."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
        id,
        awmf_guideline_id,
        null as detail_page_url,
        null as pdf_url,
        null as pdf,
        null as extracted_text,
        null created_at,
        null compressed_text,  
        title,
        lversion,
        valid_until,
        stand,
        aktueller_hinweis  
        FROM guidelines
        WHERE (valid_until IS NULL OR valid_until > NOW())
        ORDER BY created_at DESC
        LIMIT 4
    """)

    guidelines = cursor.fetchall()
    cursor.close()
    conn.close()

    return json_serial(guidelines)

@app.route("/guidelines/search", methods=["GET"])
def search_guidelines():
    """Ermöglicht das Durchsuchen der extrahierten Texte mit Sortierung & Pagination."""

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Bitte geben Sie einen Suchbegriff an"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Datenbankverbindung fehlgeschlagen"}), 500
    cursor = conn.cursor()

    try:
        limit = int(request.args.get("limit", 10))  # Standard 10 Ergebnisse
        offset = int(request.args.get("offset", 0))  # Start bei 0
        if limit < 1 or offset < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Ungültige Werte für limit oder offset"}), 400

    order_by = request.args.get("order_by", "created_at")
    order_direction = request.args.get("order_direction", "desc").lower()

    allowed_columns = ["created_at", "title", "valid_until", "stand", "lversion"]
    if order_by not in allowed_columns:
        return jsonify({"error": "Ungültige Sortierspalte"}), 400
    if order_direction not in ["asc", "desc"]:
        return jsonify({"error": "Ungültige Sortierrichtung"}), 400

    # 🛡 Sichere ORDER BY-Klausel mit Platzhaltern (SQL-Injection vermeiden)
    query_order = f"ORDER BY {order_by} {order_direction}"

    cursor.execute(f"""
        SELECT 
        id,
        awmf_guideline_id,
        null as detail_page_url,
        null as pdf_url,
        null as pdf,
        null as extracted_text,
        created_at,
        compressed_text,  
        title,
        lversion,
        valid_until,
        stand,
        aktueller_hinweis  
        FROM guidelines
        WHERE extracted_text ILIKE %s
        {query_order}
        LIMIT %s OFFSET %s
    """, (f"%{query}%", limit, offset))

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return json_serial(results)



@app.route("/guidelines/<int:guideline_id>/download", methods=["GET"])
def download_guideline_pdf(guideline_id):
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
