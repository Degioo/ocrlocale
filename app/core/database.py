import sqlite3
import json
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    original_file TEXT,
                    barcode TEXT,
                    page INTEGER,
                    mean_ocr_confidence REAL,
                    ocr_data_json TEXT, -- L'output originale dell'LLM (JSON)
                    verified_data_json TEXT, -- I dati confermati o modificati dall'operatore (JSON)
                    image_path TEXT, -- Il percorso del PNG generato da docTR/pipeline
                    status TEXT -- "Da Verificare", "Approvato"
                )
            ''')
            conn.commit()

    def insert_prescription(self, original_file, barcode, page, confidence, ocr_data, image_path):
        """Inserisce una nuova prescrizione processata nel DB"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Trasformo il dict in JSON string
            ocr_data_str = json.dumps(ocr_data, ensure_ascii=False)
            
            cursor.execute('''
                INSERT INTO prescriptions 
                (created_at, original_file, barcode, page, mean_ocr_confidence, ocr_data_json, verified_data_json, image_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (now, original_file, barcode, page, confidence, ocr_data_str, ocr_data_str, image_path, "Da Verificare"))
            
            conn.commit()
            return cursor.lastrowid

    def get_all_prescriptions(self):
        """Ottiene tutte le ricette dal DB con i loro stati"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM prescriptions ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def update_verification(self, pres_id, verified_data_dict):
        """Aggiorna la ricetta definendola Approvata e salvando i dati editati."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            verified_data_str = json.dumps(verified_data_dict, ensure_ascii=False)
            cursor.execute('''
                UPDATE prescriptions 
                SET verified_data_json = ?, status = ?
                WHERE id = ?
            ''', (verified_data_str, "Approvato", pres_id))
            conn.commit()
