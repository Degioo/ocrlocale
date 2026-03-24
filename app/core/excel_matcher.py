import pandas as pd
import logging
import string
from pathlib import Path

logger = logging.getLogger("ExcelMatcher")

def clean_barcode(b):
    if pd.isna(b) or str(b).lower() in ['nan', 'undefined', 'null', 'none']:
        return str(b)
    # Rimuove spazi e caratteri speciali (come _) da entrambe le parti
    chars_to_strip = string.punctuation + string.whitespace
    return str(b).strip(chars_to_strip)

class ExcelProcessor:
    def __init__(self, excel_path: Path):
        self.excel_path = excel_path
        self.df = None
        self.barcode_col = None
        self._load()

    def _load(self):
        try:
            self.df = pd.read_excel(self.excel_path)
            # Find the barcode column. We assume it might be named "Barcode" or "Codice a Barre"
            for col in self.df.columns:
                if 'barcode' in str(col).lower() or 'codice' in str(col).lower() and 'barre' in str(col).lower():
                    self.barcode_col = col
                    break
                    
            if not self.barcode_col:
                # Fallback to the first column if not found explicitly, or ask user?
                # Usually there's a known schema. We'll warn if not found.
                logger.warning("[!] Could not auto-detect Barcode column. Using first column as key.")
                self.barcode_col = self.df.columns[0]
                
            # Ensure barcodes are treated as strings for merging and clean special chars
            self.df[self.barcode_col] = self.df[self.barcode_col].apply(clean_barcode)
            logger.info(f"[+] Loaded Region Excel with {len(self.df)} rows. Key column: {self.barcode_col}")
            
        except Exception as e:
            logger.error(f"[!] Failed to load Excel: {e}")

    def reconcile_and_merge(self, processed_results):
        """
        processed_results: List of dicts. 
        Each dict has: 'barcode', 'original_file', 'page', 'ocr_data': { ... }
        """
        if self.df is None:
            logger.error("[!] Cannot reconcile, DataFrame is empty.")
            return
            
        scanned_barcodes = set([clean_barcode(r['barcode']) for r in processed_results if str(r['barcode']) != 'undefined'])
        excel_barcodes = set(self.df[self.barcode_col].dropna().values)
        
        # Identify Discrepancies
        missing_in_scans = excel_barcodes - scanned_barcodes
        extra_in_scans = scanned_barcodes - excel_barcodes
        
        logger.info(f"[*] Reconciliation: {len(missing_in_scans)} missing from scans, {len(extra_in_scans)} extra in scans.")
        
        # Prepare Data for Merge
        # We'll create a DataFrame from processed_results
        rows = []
        for r in processed_results:
            row = {
                'Original_File': r['original_file'],
                'Page': r['page'],
                'OCR_Accuratezza': r.get('mean_ocr_confidence', 0.0)
            }
            # Flatten OCR data
            if isinstance(r.get('ocr_data'), dict) and "error" not in r.get('ocr_data'):
                for k, v in r['ocr_data'].items():
                    row[f'OCR_{k}'] = v
            else:
                 row['OCR_Error'] = r.get('ocr_data', {}).get('error', 'Unknown Error')
                 
            # Force the highly accurate CNN barcode over any LLM hallucinations
            row['OCR_BARCODE'] = clean_barcode(r['barcode']) if str(r['barcode']) != 'undefined' else 'undefined'
            
            # Remove duplicate casing keys if they exist from the LLM map
            if 'OCR_Barcode' in row:
                del row['OCR_Barcode']
            if 'OCR_barcode' in row:
                del row['OCR_barcode']
                 
            rows.append(row)
            
        results_df = pd.DataFrame(rows)
        
        # Merge by Barcode
        final_df = pd.merge(
            self.df, 
            results_df, 
            how='outer', 
            left_on=self.barcode_col, 
            right_on='OCR_BARCODE',
            indicator=True
        )
        
        # Flag Status Column
        def set_status(row):
            if row['_merge'] == 'left_only':
                return 'Missing in Scan'
            elif row['_merge'] == 'right_only':
                return 'Extra in Scan (Not in Excel)'
            else:
                return 'Matched'
                
        final_df['Reconciliation_Status'] = final_df.apply(set_status, axis=1)
        final_df.drop(columns=['_merge'], inplace=True)
        
        return final_df

    def save(self, df: pd.DataFrame, output_path: Path):
        try:
            df.to_excel(output_path, index=False)
            logger.info(f"[+] Verified data saved to {output_path}")
        except Exception as e:
            logger.error(f"[!] Failed to save Excel: {e}")
