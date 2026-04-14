import json
import requests

class LLMParser:
    def __init__(self, api_key=None, base_url="http://localhost:11434/v1", model="llama3.2", local_model_path=None, timeout=60):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.local_model_path = local_model_path
        self.timeout = timeout
        self._llm = None

        if self.local_model_path:
            try:
                from llama_cpp import Llama
                print(f"[*] Caricamento modello locale da {self.local_model_path}...")
                self._llm = Llama(model_path=self.local_model_path, n_ctx=2048, verbose=False)
            except ImportError:
                print("[!] Errore: llama-cpp-python non installato. Impossibile usare modello locale diretto.")
            except Exception as e:
                print(f"[!] Errore caricamento modello locale: {e}")

    def extract_fields(self, text, schema_fields):
        """
        text: The full OCR text
        schema_fields: List of field names to extract
        """
        prompt = f"""
        Extract the following fields from the provided document text. 
        Return ONLY a valid JSON object where keys are the field names.
        If a field is not found, use null or an empty string.
        
        IMPORTANT RULES for specific fields:
        - "CODICE FISCALE": Must be a 16-character alphanumeric string (e.g. VTLGLI66A71C0040). Find it near 'Sig.' or 'CODICE FISCALE'. Do not ignore it!
        - "CODICE ESENZIONE": Usually a 3-letter code (e.g. "TDL"). Do NOT mistake it for pharmacy or ASL codes like '327' or 'ASL n. 134'.
        - "TESTO PRESCRIZIONE": You MUST extract the main scribbled/noisy handwriting block (e.g. "CANNARIS PLOS 1970...", "BeonoCAN", "di OLIVA..."). Do NOT just copy the printed pharmacy label!
        - "DATA PRESCRIZIONE": Look for numbers like "260423" or similar in the middle, formatting it as "26/04/2023".
        - "COGNOME E NOME ASSISTITO" or "Nome e cognome paziente": DO NOT extract boilerplate labels like "COGNOME E NOME DELL'ASSISTITO". If the name is blank, return null.
        - "Etichetta - Nome e cognome medico": Extract specifically the doctor's name (e.g., "Dott. GALATI RANDO VINCENZA"). DO NOT include the patient's codice fiscale inside this field!
        - "Etichetta - Ingredienti": Find text like "tocoferolo", "olio di oliva", "cannabis flos" located in the receipt section.
        - "Etichetta - Iva": Look explicitly for a percentage or small amount (e.g., 8,07) near standard boilerplate lines.
        - "TOTALE PRESCRIZIONE" / "Prezzo": Extract the biggest final amount near the Euro sign (e.g. 88,77).
        - "TIMBRO MEDICO" / "FIRMA MEDICO": Return strictly boolean `true` or `false` based on text evidence (e.g. titles or signatures).
        
        Fields to extract: {', '.join(schema_fields)}
        
        Document Text:
        {text}
        """

        # 1. Direct Local LLM (llama-cpp-python)
        if self._llm:
            try:
                response = self._llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                content = response['choices'][0]['message']['content']
                return json.loads(content)
            except Exception as e:
                return {"error": f"Local LLM Error: {e}"}

        # 2. Remote / Local API
        if not self.api_key and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            return {"error": "API Key is required for remote LLMs"}

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key and "localhost" not in self.base_url:
            headers["Authorization"] = f"Bearer {self.api_key}"

        is_ollama_native = "11434" in self.base_url

        if is_ollama_native:
            url = f"{self.base_url.replace('/v1', '')}/api/chat"
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0
                }
            }
        else:
            url = f"{self.base_url}/chat/completions"
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": { "type": "json_object" }
            }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            if response.status_code != 200:
                try:
                    err_msg = response.json().get("error", response.text)
                except:
                    err_msg = response.text
                return {"error": f"Ollama Error (HTTP {response.status_code}): {err_msg}"}
                
            result = response.json()
            
            if is_ollama_native:
                content = result['message']['content']
            else:
                content = result['choices'][0]['message']['content']
                
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

    def extract_fields_from_image(self, image_base64, schema_fields):
        """
        image_base64: Base64 string of the image
        schema_fields: List of field names to extract
        """
        prompt = f"""
        Extract the following fields from the provided document image. 
        Return ONLY a valid JSON object where keys are the field names.
        If a field is not found, use null or an empty string.
        
        IMPORTANT RULES for specific fields:
        - For "TIMBRO MEDICO": return `true` (boolean) if you find any text that looks like a medical stamp. Otherwise, return `false`.
        - For "FIRMA MEDICO": return `true` (boolean) if you find any text or string that suggests the presence of a signature. Otherwise, return `false`.
        - For "CODICE ESENZIONE": this is usually a short code (e.g., "TDL", "E01", "048"). Be careful to extract it exactly as it appears.
        - For "TESTO PRESCRIZIONE" or "Prescrizione": extract the main body of the prescription detailing the cannabis preparation (e.g., "CANNABIS FLOS", "BEDROCAN", "OLIO", doses, etc.). Combine all related text.
        - For "TOTALE PRESCRIZIONE" or "Totale": extract the total monetary cost or price in euros (e.g., 88,77 or 88.77).
        - For "COGNOME E NOME ASSISTITO" or "Paziente": DO NOT extract boilerplate labels like "COGNOME E NOME DELL'ASSISTITO" or "PRESCRITTO DALLA LEGGE". Only extract the actual handwritten/printed patient name. If it's missing or just a label, return null.
        - Tutte le date MUST be extracting in DD/MM/YYYY format.
        
        Fields to extract: {', '.join(schema_fields)}
        """

        if not self.api_key and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            return {"error": "API Key is required for remote LLMs"}

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key and "localhost" not in self.base_url:
            headers["Authorization"] = f"Bearer {self.api_key}"

        is_ollama_native = "11434" in self.base_url

        if is_ollama_native:
            url = f"{self.base_url.replace('/v1', '')}/api/chat"
            data = {
                "model": self.model,
                "messages": [{
                    "role": "user", 
                    "content": prompt,
                    "images": [image_base64]
                }],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0
                }
            }
        else:
            url = f"{self.base_url}/chat/completions"
            data = {
                "model": self.model,
                "messages": [{
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }],
                "temperature": 0.0,
                "response_format": { "type": "json_object" }
            }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            if response.status_code != 200:
                try:
                    err_msg = response.json().get("error", response.text)
                except:
                    err_msg = response.text
                return {"error": f"Ollama Error (HTTP {response.status_code}): {err_msg}"}
                
            result = response.json()
            
            if is_ollama_native:
                content = result['message']['content']
            else:
                content = result['choices'][0]['message']['content']
                
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

# Global instance for easy access in custom_logic
_parser_instance = None

def get_parser(api_key=None, base_url=None, model=None, local_model_path=None, timeout=None):
    global _parser_instance
    import os
    
    default_url = "http://localhost:11434/v1"
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('IS_DOCKER') == '1'
    
    if is_docker:
        default_url = "http://ocr_ollama:11434/v1"
        if base_url:
            base_url = base_url.replace("localhost", "ocr_ollama").replace("127.0.0.1", "ocr_ollama")
            
    if _parser_instance is None or api_key or base_url or model or local_model_path or timeout:
        _parser_instance = LLMParser(
            api_key=api_key, 
            base_url=base_url or default_url, 
            model=model or "llama3.2",
            local_model_path=local_model_path,
            timeout=timeout or 60
        )
    return _parser_instance
