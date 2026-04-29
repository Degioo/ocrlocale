import json
import requests

class LLMParser:
    def __init__(self, api_key=None, base_url="http://ocr_glm:8080/v1", model="glm-ocr", local_model_path=None, timeout=60):
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

    def _normalize_ocr_text(self, raw_text):
        """
        Step 1: Normalizzazione del testo. Pulisce l'output sporco di docTR.
        """
        prompt = f"""
Sei un assistente specializzato nel correggere l'output OCR rumoroso di ricette mediche italiane.
Il tuo compito è ESCLUSIVAMENTE ricostruire il testo originale correggendo gli errori tipografici palesi generati dall'OCR.

Regole:
- NON AGGIUNGERE testo inventato.
- NON formatteggiare in JSON, restituisci solo il testo pulito in formato testuale.
- Correggi errori evidenti: es. CANNARIS -> CANNABIS, SLIVA -> OLIVA, BedroCAN -> Bedrocan.
- Mantieni i ritorni a capo se separano concetti diversi.

TESTO OCR GREZZO:
{raw_text}

TESTO CORRETTO:
"""
        # 1. Direct Local LLM
        if self._llm:
            try:
                response = self._llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                return response['choices'][0]['message']['content']
            except Exception as e:
                print(f"[!] Error in LLM normalization: {e}")
                return raw_text
                
        # 2. Remote / Ollama API
        headers = {"Content-Type": "application/json"}
        if self.api_key and "localhost" not in self.base_url:
            headers["Authorization"] = f"Bearer {self.api_key}"

        is_ollama_native = "11434" in self.base_url

        if is_ollama_native:
            url = f"{self.base_url.replace('/v1', '')}/api/chat"
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": { "temperature": 0.0 }
            }
        else:
            url = f"{self.base_url}/chat/completions"
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0
            }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                if is_ollama_native:
                    return result['message']['content']
                else:
                    return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"[!] Errore connessione durante la normalizzazione: {e}")

        # Fallback to raw text if error
        return raw_text

    def extract_fields(self, text, schema_fields):
        """
        text: The full OCR text
        schema_fields: List of field names to extract
        """
        # STEP 1: PRE-NORMALIZATION
        normalized_text = self._normalize_ocr_text(text)
        
        # STEP 2: EXTRACT JSON
        prompt = f"""
Sei un parser di OCR rumoroso per prescrizioni/etichette di cannabis terapeutica italiane.
Estrai i campi richiesti e restituisci SOLO un JSON valido.

Regole generali:
- Non inventare.
- Se un valore non è affidabile, usa null.
- Correggi piccoli errori OCR solo se la correzione è molto probabile.
- Se due valori sono possibili, scegli quello più compatibile con il formato atteso del campo.
- Non usare lo stesso valore per campi diversi, a meno che sia chiaramente corretto.

Regole di estrazione importanti:
- OCR_CODICE FISCALE: regex compatibile con [A-Z0-9]{{16}}. deve sembrare un codice fiscale italiano di 16 caratteri alfanumerici. Se non trovi un pattern compatibile, null.
- OCR_COGNOME E NOME ASSISTITO: cerca vicino a parole come "Sig." o nominativo assistito. Non usare codici o date.
- OCR_Etichetta - Nome e cognome o codice paziente: può essere nome/cognome oppure codice paziente, ma non usare una data o un importo.
- OCR_Etichetta - THC e OCR_Etichetta - CBD: estrai solo valori puliti come "19%", "0,5%", "22 mg", ecc. Se il testo è corrotto e non sicuro, null.
- OCR_DATA PRESCRIZIONE, OCR_DATA INVIO, OCR_Etichetta - Data preparazione, OCR_Etichetta - Data scadenza: estrai solo date plausibili. Formato preferito DD/MM/YYYY o DD/MM/YY.
- OCR_FIRMA MEDICO e OCR_TIMBRO MEDICO: solo "Presente", "Assente" oppure null.
- OCR_Etichetta - Ingredienti: elenco ingredienti riconoscibili, ripulendo errori OCR evidenti.
- OCR_TESTO PRESCRIZIONE: ricostruisci il testo prescrittivo dalle righe mediche, senza includere dati della farmacia o avvertenze etichetta.
- Prezzi: estrai gli importi più plausibili dal contesto etichetta. Mantieni il formato con virgola decimale, senza simbolo €. OCR_*Prezzo*: solo numero con virgola.
- OCR_Etichetta - Peso soluzione (g): solo numero.

Non fare questi errori:
- Non estrarre come codice fiscale stringhe tipo "Cod. 327 ABLI n. 134 Prov. VA"
- Non estrarre come nome paziente valori numerici che sembrano date o codici non etichettati
- Non estrarre THC da testo corrotto come "1970 THC-ACARBGO" se il valore percentuale non è chiaro

Output: solo JSON.

[ELENCO CAMPI]
{', '.join(schema_fields)}

[TESTO OCR RISOLTO]
{normalized_text}
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

    def extract_fields_from_image(self, image_base64_list, schema_fields):
        """
        image_base64_list: List of Base64 strings of the images
        schema_fields: List of field names to extract
        """
        if not isinstance(image_base64_list, list):
            image_base64_list = [image_base64_list]

        # Nota: per le immagini, il VisionLLM fa estrazione e OCR in un colpo solo. Non si applica la pre-normalizzazione.
        prompt = f"""
Sei un parser di prescrizioni/etichette di cannabis terapeutica italiane.
Estrai i campi richiesti e restituisci SOLO un JSON valido analizzando l'immagine.

Regole generali:
- Non inventare.
- Se un valore non è affidabile, usa null.
- Mappa i dati dell'immagine coerentemente col significato medico.
- Se due valori sono possibili, scegli quello più compatibile con il formato atteso del campo.

Regole di estrazione importanti:
- OCR_CODICE FISCALE: regex compatibile con [A-Z0-9]{{16}}. deve sembrare un codice fiscale italiano di 16 caratteri alfanumerici. Se non trovi un pattern compatibile, null.
- OCR_COGNOME E NOME ASSISTITO: cerca vicino a parole come "Sig." o nominativo assistito. Non usare codici o date.
- OCR_Etichetta - Nome e cognome o codice paziente: può essere nome/cognome oppure codice paziente, ma non usare una data o un importo.
- OCR_Etichetta - THC e OCR_Etichetta - CBD: estrai solo valori puliti come "19%", "0,5%", "22 mg", ecc. Se testo incerto, null.
- OCR_DATA PRESCRIZIONE, OCR_DATA INVIO, OCR_Etichetta - Data preparazione, OCR_Etichetta - Data scadenza: estrai solo date plausibili. Formato preferito DD/MM/YYYY o DD/MM/YY.
- OCR_FIRMA MEDICO e OCR_TIMBRO MEDICO: solo "Presente", "Assente" oppure null.
- OCR_Etichetta - Ingredienti: elenco ingredienti riconoscibili, ripulendo errori OCR evidenti.
- OCR_TESTO PRESCRIZIONE: ricostruisci il testo prescrittivo dalle righe mediche, senza includere dati della farmacia o avvertenze etichetta.
- Prezzi: estrai gli importi più plausibili dal contesto etichetta. Mantieni il formato con virgola decimale, senza simbolo €. OCR_*Prezzo*: solo numero con virgola.
- OCR_Etichetta - Peso soluzione (g): solo numero.

Non fare questi errori:
- Non estrarre come codice fiscale stringhe tipo "Cod. 327 ABLI n. 134 Prov. VA"
- Non estrarre come nome paziente valori numerici che sembrano date o codici non etichettati

Output: solo JSON.

[ELENCO CAMPI]
{', '.join(schema_fields)}
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
                    "images": image_base64_list
                }],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0
                }
            }
        else:
            url = f"{self.base_url}/chat/completions"
            content_payload = [{"type": "text", "text": prompt}]
            for b64 in image_base64_list:
                content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                
            data = {
                "model": self.model,
                "messages": [{
                    "role": "user", 
                    "content": content_payload
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
    
    default_url = "http://ocr_glm:8080/v1"
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('IS_DOCKER') == '1'
    
    if is_docker:
        default_url = "http://ocr_glm:8080/v1"
        if base_url:
            base_url = base_url.replace("localhost", "ocr_glm").replace("127.0.0.1", "ocr_glm")
            
    if _parser_instance is None or api_key or base_url or model or local_model_path or timeout:
        # Aumentato il timeout di default perché i task in 2 step sono più pesanti
        _parser_instance = LLMParser(
            api_key=api_key, 
            base_url=base_url or default_url, 
            model=model or "glm-ocr",
            local_model_path=local_model_path,
            timeout=timeout or 120
        )
    return _parser_instance
