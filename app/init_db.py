import sqlite3

# Verbindung zur SQLite-Datenbank herstellen (Datei wird erstellt, falls nicht vorhanden)
db_path = "/home/s3service/s3_backend/app/leitlinien.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Erstelle die Tabelle "guidelines"
cursor.execute("""
CREATE TABLE IF NOT EXISTS guidelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Optionale: Testeintrag hinzufügen, falls die Tabelle leer ist
cursor.execute("SELECT COUNT(*) FROM guidelines")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO guidelines (title, content) VALUES (?, ?)", 
                   ("Beispiel-Leitlinie", "Dies ist eine Beispiel-Leitlinie."))

# Änderungen speichern und Verbindung schließen
connection.commit()
connection.close()

print("Datenbank wurde initialisiert und Tabelle 'guidelines' erstellt.")
