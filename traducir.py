import pandas as pd
from googletrans import Translator
import time
from tqdm import tqdm
import re
import urllib.parse
from unidecode import unidecode # Assegura't que tens aquestes llibreries instal·lades!

# --- CONFIGURACIÓ DE FITXERS I TRADUCCIÓ ---
INPUT_CSV_FILE = 'recetasdelaabuela.csv'
OUTPUT_CSV_FILE = 'recetas_traducidas.csv'
# Columnes a traduir
COLUMNS_TO_TRANSLATE = ['Nombre', 'Ingredientes', 'Pasos'] 

# Configuració de fiabilitat
MAX_RETRIES = 3 
INITIAL_SLEEP = 0.5  # Pausa de 0.5 segons entre CADA camp (per fiabilitat)
BATCH_SIZE = 50      # Utilitzem el batch per a la lògica de "checkpointing" (cada 50 receptes)


# --- INICIALITZACIÓ DEL TRADUCTOR ---
try:
    TRANSLATOR = Translator()
    print("Traductor de Google inicialitzat i llest per començar.")
except Exception as e:
    print(f"❌ ERROR: No es va poder inicialitzar el traductor. {e}")
    exit()


# --- FUNCIONS D'UTIILITAT ---

def repair_text_encoding(text):
    """Neteja i repara strings abans de la traducció."""
    if pd.isna(text) or not isinstance(text, str):
        return ''
    try:
        text = urllib.parse.unquote(text)
    except:
        pass
    text = re.sub(r'[^\x00-\x7F\u00A0-\uFFFF\s]+', '', text)
    return text.strip()


def translate_text_with_retry(text, retries=MAX_RETRIES):
    """
    Tradueix un text (UN ÚNIC CAMP) amb reintents i pausa.
    """
    if not text:
        return ""
        
    text_to_translate = str(text).strip()
    if len(text_to_translate) > 4900:
        text_to_translate = text_to_translate[:4900]
    
    current_attempt = 0
    
    while current_attempt < retries:
        try:
            # ⏸️ PAUSA: 0.5 segons entre CADA camp
            time.sleep(INITIAL_SLEEP) 
            
            translation = TRANSLATOR.translate(text_to_translate, dest='ca')
            return translation.text
            
        except Exception as e:
            current_attempt += 1
            if current_attempt < retries:
                print(f"\n⚠️ Falla temporal (Timeout o Límits) al camp. Reintent {current_attempt}/{retries}. Esperant 10 segons...")
                time.sleep(10) 
            else:
                print(f"\n❌ ERROR CRÍTIC: No s'ha pogut traduir el camp. Retornant original després de {retries} intents.")
                return text 
    
    return text 


# --- PROCÉS PRINCIPAL ---
def translate_csv_with_checkpoint():
    
    # 1. Carregar dades originals
    try:
        df_original = pd.read_csv(INPUT_CSV_FILE, encoding='latin1')
    except Exception:
        df_original = pd.read_csv(INPUT_CSV_FILE, encoding='utf-8')
    
    df_original.index.name = 'OriginalIndex' # Afegim un nom a l'índex per al merge posterior
    
    # Aplicar neteja prèvia al DataFrame original (només si es processa per primer cop)
    for col in COLUMNS_TO_TRANSLATE:
        if col in df_original.columns:
            df_original[col] = df_original[col].apply(repair_text_encoding)

    # 2. Carregar o crear el DataFrame de resultats
    try:
        df_translated = pd.read_csv(OUTPUT_CSV_FILE)
        # Assegurem que les dades traduïdes mantinguin el mateix índex de referència
        print(f"✅ S'ha reprès la traducció. Ja hi ha {len(df_translated)} files traduïdes.")
    except FileNotFoundError:
        df_translated = df_original.head(0).copy() # DataFrame buit amb columnes originals
        print("🔍 S'inicia la traducció des del principi (no s'han trobat checkpoints).")


    # 3. Determinar quines files s'han de processar
    # Identificar files ja traduïdes
    translated_count = len(df_translated)
    
    # Seleccionar les files pendents (a partir de l'última fila traduïda)
    df_remaining = df_original.iloc[translated_count:].copy().reset_index(drop=True)
    
    
    total_remaining = len(df_remaining)
    
    # 4. Procesar en blocs (per fer el checkpoint)
    # Utilitzem tqdm per al feedback de progrés, sumant l'índex ja traduït
    for start in tqdm(range(0, total_remaining, BATCH_SIZE), 
                      desc="Traducció de Receptes",
                      initial=translated_count // BATCH_SIZE, # Inicialitza la barra
                      total=(total_rows // BATCH_SIZE) + 1 ): # Total estimat de batches

        end = min(start + BATCH_SIZE, total_remaining)
        batch = df_remaining.iloc[start:end].copy()
        
        # Iterem per fila per garantir la traducció individual
        for idx, row in batch.iterrows():
            
            # 5. Traduir cada camp per separat
            for col in COLUMNS_TO_TRANSLATE:
                if col in batch.columns:
                    original_text = row[col]
                    
                    translated_text = translate_text_with_retry(original_text)
                    
                    # 6. Guardar la traducció DINS de la columna original
                    batch.at[idx, col] = translated_text.strip()
            
        # 7. Unir i Guardar resultats (Checkpoint)
        df_translated = pd.concat([df_translated, batch], ignore_index=True)
        df_translated.to_csv(OUTPUT_CSV_FILE, index=False, encoding='utf-8')
        
        # El feedback es gestiona per tqdm, no cal un print per cada batch, però
        # deixem la pausa per fiabilitat
        # time.sleep(delay_between_batches) # Eliminat el delay extra ja que hi ha un sleep de 0.5s per camp

    print(f"\n\n✅ PROCÉS FINALITZAT AMB ÈXIT! Total de {len(df_translated)} receptes traduïdes.")


if __name__ == '__main__':
    # Afegim una línia per obtenir el total de files abans de cridar la funció
    try:
        df_check = pd.read_csv(INPUT_CSV_FILE, encoding='latin1')
        total_rows = len(df_check)
    except Exception:
        print("Error: No es pot carregar el fitxer original per obtenir el total de files.")
        total_rows = 0

    if total_rows > 0:
        translate_csv_with_checkpoint()
    else:
        print("No hi ha dades per processar.")
