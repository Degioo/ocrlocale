import sqlite3
from pathlib import Path
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="output/database.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Manteniamo i nomi delle colonne invariati per non spaccare vecchi DB se l'utente non lo cancella,
            # ma salveremo stringhe Markdown al posto di JSON.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    original_file TEXT,
                    barcode TEXT,
                    page INTEGER,
                    mean_ocr_confidence REAL,
                    ocr_data_json TEXT, -- Ora conterrà il Markdown grezzo
                    verified_data_json TEXT, -- Ora conterrà il Markdown verificato dall'operatore
                    image_path TEXT,
                    status TEXT
                )
            ''')
            conn.commit()

    def insert_prescription(self, original_file, barcode, page, confidence, ocr_markdown, image_path):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO prescriptions 
                (created_at, original_file, barcode, page, mean_ocr_confidence, ocr_data_json, verified_data_json, image_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (now, original_file, barcode, page, confidence, ocr_markdown, ocr_markdown, image_path, "Da Verificare"))
            
            conn.commit()
            return cursor.lastrowid

    def get_all_prescriptions(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM prescriptions ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def update_verification(self, pres_id, verified_markdown):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE prescriptions 
                SET verified_data_json = ?, status = ?
                WHERE id = ?
            ''', (verified_markdown, "Approvato", pres_id))
            conn.commit()
