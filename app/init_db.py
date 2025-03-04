import sqlite3

db_path = "/home/s3service/s3_backend/app/leitlinien.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Erstelle die Tabelle "guidelines", falls sie nicht existiert
cursor.execute("""
CREATE TABLE IF NOT EXISTS guidelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    pdf_url TEXT,
    pdf BLOB,
    extracted_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Stelle sicher, dass alle benötigten Spalten existieren
columns = [row[1] for row in cursor.execute("PRAGMA table_info(guidelines)").fetchall()]
missing_columns = {
    "url": "ALTER TABLE guidelines ADD COLUMN url TEXT;",
    "pdf_url": "ALTER TABLE guidelines ADD COLUMN pdf_url TEXT;",
    "pdf": "ALTER TABLE guidelines ADD COLUMN pdf BLOB;",
    "extracted_text": "ALTER TABLE guidelines ADD COLUMN extracted_text TEXT;"
}

for column, query in missing_columns.items():
    if column not in columns:
        cursor.execute(query)

# Testeintrag nur hinzufügen, wenn die Tabelle leer ist
cursor.execute("SELECT COUNT(*) FROM guidelines")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO guidelines (title, content) VALUES (?, ?)",
                   ("Beispiel-Leitlinie", "Dies ist eine Beispiel-Leitlinie."))

# Änderungen speichern
connection.commit()
connection.close()

print("Datenbank wurde initialisiert und fehlende Spalten ergänzt.")
