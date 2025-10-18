import csv
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from unidecode import unidecode
import time

# --- Configuración de Flask y Datos en Memoria ---
app = Flask(__name__)
# CORS es crucial para que el Frontend (en otro puerto) pueda conectar
CORS(app)
RECIPES = []
CSV_FILE_PATH = 'recetas.csv'

# Mapeo crucial: categoría del CSV (Español) -> clave interna (Catalán/Frontend)
CATEGORY_MAPPING = {
    'aperitivos_y_tapas': 'aperitius_tapes',
    'bebidas': 'begudes',
    'carnes_y_aves': 'carns_aus',
    'ensaladas': 'amanides',
    'guarniciones': 'guarnicions',
    'huevos': 'ous',
    'legumbres': 'llegums',
    'pescado_y_marisco': 'peix_marisc',
    'postres': 'postres',
    'salsas_y_cremas': 'salses_cremes',
    'sopas_y_cremas': 'sopes_cremes',
    'verduras': 'verdures',
    'internacionales': 'internacionals',
    'para_fiestas': 'festes',
    'para_ninos': 'nens',
}

# Dades de prova (Fallback)
def add_dummy_recipes_fallback():
    global RECIPES
    RECIPES = [
        {'id': 1001, 'nombre': "Escalivada al Forn (MOCK)", 'categoria': "verdures", 'ingredientes': "Albergínia\nPebrot\nCeba", 'pasos': "Preparació de prova.", 'imagen_url': "https://placehold.co/400x300/a3e635/000?text=MOCK"},
        {'id': 1002, 'nombre': "Arròs negre amb calamars (MOCK)", 'categoria': "peix_marisc", 'ingredientes': "Arròs\nCalamars\nTinta", 'pasos': "Preparació de prova.", 'imagen_url': "https://placehold.co/400x300/fca5a5/000?text=MOCK"},
    ]


# --- Funciones de Carga de Datos (Múltiples codificaciones para mayor robustez) ---

def load_recipes_from_csv():
    global RECIPES
    RECIPES = []
    DEFAULT_STEPS = "Passos no especificats al CSV."
   
    try:
        encodings = ['utf-8', 'latin-1']
        success = False
       
        for encoding in encodings:
            try:
                # Intenta abrir el archivo
                with open(CSV_FILE_PATH, mode='r', encoding=encoding) as file:
                    csv_reader = csv.reader(file, delimiter='|')
                    next(csv_reader) # Ignorar cabecera
                   
                    COL_CATEGORY = 1
                    COL_NAME = 2
                    COL_INGREDIENTS = 12
                    recipe_id_counter = 1
                   
                    for row in csv_reader:
                        if len(row) > COL_INGREDIENTS:
                            # Limpieza y mapeo de categoría
                            raw_category = row[COL_CATEGORY].split('Recetas de ')[-1]
                            clean_category_key = unidecode(raw_category).lower().replace(' ', '_').replace('_y_', '_i_')
                            final_category = CATEGORY_MAPPING.get(clean_category_key, clean_category_key)
                           
                            # Limpieza de nombre y formato de ingredientes
                            clean_name = row[COL_NAME].split('Receta de ')[-1]
                            ingredients_formatted = row[COL_INGREDIENTS].replace(',', '\n')
                           
                            RECIPES.append({
                                'id': recipe_id_counter,
                                'nombre': clean_name,
                                'categoria': final_category, # CLAVE ESTANDARIZADA
                                'ingredientes': ingredients_formatted,
                                'pasos': DEFAULT_STEPS,
                                'imagen_url': f"https://placehold.co/400x300/cccccc/000?text={clean_name.replace(' ', '+')}"
                            })
                            recipe_id_counter += 1
                           
                    success = True
                    break # Salir si la carga es exitosa
               
            except UnicodeDecodeError:
                continue # Probar la siguiente codificación
            except Exception as e:
                raise e

        if not success or not RECIPES:
            print(f" ❌ ERROR: No s'ha pogut llegir correctament el fitxer '{CSV_FILE_PATH}'.")
            add_dummy_recipes_fallback()
        else:
            print(f" ✅ Dades carregades amb èxit: {len(RECIPES)} receptes des de {CSV_FILE_PATH} (codificació: {encoding})")

    except FileNotFoundError:
        print(f" ⚠️ ERROR FATAL: No s'ha trobat el fitxer '{CSV_FILE_PATH}'.")
        add_dummy_recipes_fallback()
    except Exception as e:
        print(f" ❌ ERROR durant el processament del CSV: {e}")
        add_dummy_recipes_fallback()


# --- RUTAS DE LA API ---

@app.route('/', methods=['GET'])
def home():
    """Ruta base (soluciona el 'Not Found' en 5000)"""
    status_message = "Servidor Flask Recetario actiu. OK."
    if not RECIPES or 'MOCK' in RECIPES[0]['nombre']:
        status_message += " WARNING: Mostrant DADES DE PROVA."
   
    return jsonify({
        "status": status_message,
        "recipe_count": len(RECIPES),
        "instructions": "Use /recipes/all o /recipes/category/<CLAVE_INTERNA>"
    })

@app.route('/recipes/all', methods=['GET'])
def get_all_recipes():
    """Retorna todas las recetas en memoria."""
    return jsonify(RECIPES)

@app.route('/recipes/category/<category>', methods=['GET'])
def get_recipes_by_category(category):
    """Filtra por la CLAVE estandarizada (ej: verdures)."""
    category = unidecode(category).lower()
    recipes = [r for r in RECIPES if r['categoria'] == category]
    return jsonify(recipes)

@app.route('/chatbot', methods=['POST'])
def chatbot():
    # Lógica del chatbot...
    return jsonify({"response": "La funció de chatbot està activa."})


if __name__ == '__main__':
    print("Iniciando la carga de datos del CSV...")
    load_recipes_from_csv()
    app.run(host='0.0.0.0', port=5000, debug=True)
