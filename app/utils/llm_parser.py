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
        - For "TIMBRO MEDICO": return `true` (boolean) if you find any text that looks like a medical stamp (e.g., doctor name with titles like "Dott.", "Albo dei Medici", VAT numbers, or specialization). Otherwise, return `false`.
        - For "FIRMA MEDICO": return `true` (boolean) if you find any text or string that suggests the presence of a signature (e.g., scribbles interpreted by OCR as random connected letters, "Firmato", or the doctor's name written by hand). Otherwise, return `false`.
        - For "CODICE ESENZIONE": this is usually a short code (e.g., "TDL", "E01", "048"). Be careful to extract it exactly as it appears.
        - For "etichetta - IVA" (or any IVA field): search for the value near the keyword "IV" or "IV:" on the label.
        - Tutte le date (come Data_Preparazione, Scadenza, etc.) DEVONO essere scritte rigorosamente nel formato gg/mm/aaaa.
        
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
        - For "TIMBRO MEDICO": return `true` (boolean) if you find any text that looks like a medical stamp (e.g., doctor name with titles like "Dott.", "Albo dei Medici", VAT numbers, or specialization). Otherwise, return `false`.
        - For "FIRMA MEDICO": return `true` (boolean) if you find any text or string that suggests the presence of a signature (e.g., scribbles interpreted by OCR as random connected letters, "Firmato", or the doctor's name written by hand). Otherwise, return `false`.
        - For "CODICE ESENZIONE": this is usually a short code (e.g., "TDL", "E01", "048"). Be careful to extract it exactly as it appears.
        
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
    if _parser_instance is None or api_key or base_url or model or local_model_path or timeout:
        _parser_instance = LLMParser(
            api_key=api_key, 
            base_url=base_url or "http://localhost:11434/v1", 
            model=model or "llama3.2",
            local_model_path=local_model_path,
            timeout=timeout or 60
        )
    return _parser_instance
