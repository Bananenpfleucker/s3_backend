# summarizer.py
import os
import time
import psycopg2
import json
from tiktoken import encoding_for_model
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# Lade Umgebungsvariablen aus keys.env (falls vorhanden) und Umgebung
dotenv_path = Path('keys.env')
load_dotenv(dotenv_path=dotenv_path, override=False)
# Fallback: lade auch Standard-.env, aber überschreibe bereits existierende Variablen nicht
load_dotenv(override=False)

# Holen des API-Schlüssels aus der Umgebung oder Fallback-Keys
OPENAI_API_KEY = (
    os.getenv("OPENAI_API_KEY") or
    os.getenv("OPENAI_KEY") or
    os.getenv("API_KEY")
)
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OpenAI API Key fehlt! Bitte setzen Sie 'OPENAI_API_KEY', 'OPENAI_KEY' oder 'API_KEY' in der .env oder Umgebung."
    )
# Stelle sicher, dass die lib den Key aus den ENV-Vars liest
os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)
# OpenAI‑Client initialisieren (nimmt api_key aus ENV)
client = OpenAI()
client = OpenAI(api_key=OPENAI_API_KEY)

# DB‑Settings
DB_HOST     = os.getenv("DB_HOST")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER_WRITE")
DB_PASSWORD = os.getenv("DB_PASSWORD_WRITE")
DB_PORT     = os.getenv("DB_PORT")

# Model‑Konfiguration
RAW_MODEL      = "gpt-3.5-turbo-16k"
FINAL_MODEL    = RAW_MODEL
MAX_TOKENS     = 3500
OVERLAP_TOKENS = 200
MAX_RETRIES    = 3
RETRY_DELAY    = 5  # Sekunden
MAX_RECURSION  = 3

# Statische Instruktion für Roh‑Zusammenfassung
RAW_SUMMARY_INSTRUCTION = (
    "Du bist ein spezialisiertes Modell zur Zusammenfassung medizinischer Leitlinien. "
    "Fasse den folgenden Textausschnitt kurz zusammen (1–2 Sätze) und liefere eine prägnante Rohzusammenfassung ohne Strukturvorgabe:\n"
)


def get_db_connection():
    print("[DEBUG] get_db_connection(): versuche Verbindung zu DB...")
    try:
        conn = psycopg2.connect(
            host     = DB_HOST,
            port     = DB_PORT,
            dbname   = DB_NAME,
            user     = DB_USER,
            password = DB_PASSWORD
        )
        print("[DEBUG] get_db_connection(): Verbindung erfolgreich")
        return conn
    except Exception as e:
        print(f"[ERROR] get_db_connection(): DB-Error: {e}")
        return None


def retry_chat_request(model, messages):
    print(f"[DEBUG] retry_chat_request(): Modell={model}, Nachrichten count={len(messages)}")
    for i in range(1, MAX_RETRIES+1):
        try:
            resp = client.chat.completions.create(model=model, messages=messages)
            content = resp.choices[0].message.content
            print(f"[DEBUG] retry_chat_request(): Erfolg im Versuch {i}, response length={len(content)} chars")
            return content
        except Exception as e:
            print(f"[WARN] retry_chat_request(): OpenAI error {i}/{MAX_RETRIES}: {e}")
            time.sleep(RETRY_DELAY)
    print("[ERROR] retry_chat_request(): Alle Versuche fehlgeschlagen")
    return None


def split_text(text, max_tokens=MAX_TOKENS, overlap=OVERLAP_TOKENS, model=RAW_MODEL):
    enc = encoding_for_model(model)
    tokens = enc.encode(text)
    chunks, start = [], 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(enc.decode(tokens[start:end]))
        start = end - overlap if end - overlap > start else end
    return chunks


def recursive_raw_summary(text, depth=0):
    if depth > MAX_RECURSION:
        return retry_chat_request(RAW_MODEL, [
            {"role": "system", "content": RAW_SUMMARY_INSTRUCTION},
            {"role": "user",   "content": text}
        ])
    summaries = []
    for chunk in split_text(text):
        res = retry_chat_request(RAW_MODEL, [
            {"role": "system", "content": RAW_SUMMARY_INSTRUCTION},
            {"role": "user",   "content": chunk}
        ])
        if res:
            summaries.append(res)
    if not summaries:
        return None
    joined = "\n\n".join(summaries)
    enc = encoding_for_model(RAW_MODEL)
    if len(enc.encode(joined)) > MAX_TOKENS:
        return recursive_raw_summary(joined, depth+1)
    return joined


def process_summary_for_id(guideline_id: int) -> bool:
    print(f"[INFO] process_summary_for_id(): Starte ID={guideline_id}")
    conn = get_db_connection()
    if not conn:
        print("[ERROR] process_summary_for_id: DB-Verbindung fehlgeschlagen")
        return False
    cur = conn.cursor()
    cur.execute("SELECT promptid, prompt_text FROM prompts ORDER BY promptid DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        print("[ERROR] Kein Prompt in DB gefunden")
        return False
    promptid, final_prompt = row
    print(f"[DEBUG] verwende PromptID={promptid}")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT extracted_text FROM guidelines WHERE id=%s AND extracted_text IS NOT NULL", (guideline_id,))
    text_row = cur.fetchone()
    cur.close()
    conn.close()
    if not text_row:
        print(f"[ERROR] Kein extracted_text für ID={guideline_id}")
        return False
    full_text = text_row[0]

    raw_summary = recursive_raw_summary(full_text)
    if not raw_summary:
        print("[ERROR] Rohzusammenfassung fehlgeschlagen")
        return False

    response = retry_chat_request(FINAL_MODEL, [
        {"role": "system", "content": final_prompt},
        {"role": "user",   "content": raw_summary}
    ])
    if not response:
        print("[ERROR] finale JSON-Zusammenfassung fehlgeschlagen")
        return False

    try:
        summary_json = json.loads(response)
        summary_json = {k:v for k,v in summary_json.items() if v.strip()}
        summary_str = json.dumps(summary_json, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        summary_str = response

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE guidelines SET compressed_text=%s WHERE id=%s", (summary_str, guideline_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[INFO] process_summary_for_id(): ID={guideline_id} erfolgreich gespeichert")
    return True
