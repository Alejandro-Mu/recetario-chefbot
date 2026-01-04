import pandas as pd
import os
import sqlite3
from unidecode import unidecode
from flask import Flask, request, jsonify, send_from_directory, render_template
import re
import random
import urllib.parse

# --- Configuració de Flask i Constants ---
app = Flask(__name__)

CSV_FILE_PATH = 'recetas_traducidas.csv'
DB_FILE = 'recetas.db'
STATIC_FOLDER = 'static'

CATEGORY_LOAD_LIMIT = 5000
SEARCH_RESULT_LIMIT = 50
INITIAL_PER_CATEGORY_SAMPLE = 100

INTERNAL_CATEGORIES = [
    'mexic', 'peru', 'españa', 'argentina', 'colombia',
    'chile', 'venezuela', 'ecuador', 'italia', 'eua', 'altres'
]

INVERSE_CATEGORY_MAPPING = {
    'mexic': 'Mèxic',
    'peru': 'Perú',
    'españa': 'Espanya',
    'argentina': 'Argentina',
    'colombia': 'Colòmbia',
    'chile': 'Xile',
    'venezuela': 'Veneçuela',
    'ecuador': 'Equador',
    'italia': 'Itàlia',
    'eua': 'Estats Units (EUA)',
    'altres': 'Altres'
}

COLUMN_MAPPING = {
    'Id': 'id',
    'Nombre': 'nombre',
    'URL': 'url',
    'Ingredientes': 'ingredientes',
    'Pasos': 'pasos',
    'Pais': 'pais',
    'Duracion': 'duracion',
    'Porciones': 'porciones',
    'Calorias': 'calorias',
    'Categoria': 'categoria_raw',
    'Contexto': 'contexto',
    'Valoracion y Votos': 'valoracion_votos',
    'Comensales': 'comensales',
    'Tiempo': 'tiempo',
    'Dificultad': 'dificultad',
    'Categoria 2': 'categoria_2',
}

# =======================================================
# NETEJA NLP AGRESSIVA
# =======================================================
def aggressive_nlp_clean(text):
    if pd.isna(text) or not isinstance(text, str):
        return ''

    try:
        text = urllib.parse.unquote(text)
        repaired = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
        if len(repaired) > len(text) * 0.5:
            text = repaired
    except:
        pass

    text = unidecode(text).lower()
    # Eliminar tot el que no sigui lletres, números o espais
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# --- Funcions d'Utilitat de Base de Dades ---

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_recipes(query, params=()):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR en consultar la base de dades: {e}")
        return []

def get_recipe_count():
    try:
        with get_db_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    except Exception:
        return 0

def get_all_categories_keys(read_from_db=False):
    return INTERNAL_CATEGORIES

def repair_text_encoding(text):
    return aggressive_nlp_clean(text)

# =======================================================
# NORMALITZACIÓ DE CATEGORIES
# =======================================================
def normalize_category(raw_pais):
    if pd.isna(raw_pais) or not raw_pais:
        return 'altres'

    normalized = aggressive_nlp_clean(str(raw_pais))
   
    COUNTRY_KEYWORDS = {
        'espana': 'españa',
        'peru': 'peru',
        'mexico': 'mexic',
        'argentina': 'argentina',
        'colombia': 'colombia',
        'chile': 'chile',
        'venezuela': 'venezuela',
        'ecuador': 'ecuador',
        'italia': 'italia',
        'estados unidos': 'eua',
        'usa': 'eua',
        'eeuu': 'eua'
    }

    for keyword, internal_key in COUNTRY_KEYWORDS.items():
        if keyword in normalized:
            return internal_key
           
    if 'internacional' in normalized:
        return 'altres'
       
    return 'altres'

# --- Funció de Càrrega de Dades ---

def load_data(csv_file_path=CSV_FILE_PATH, db_file=DB_FILE):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Base de dades '{DB_FILE}' existent eliminada per a recàrrega neta.")

    try:
        df = pd.read_csv(csv_file_path, encoding='utf-8')
    except Exception as e:
        print(f"Error fatal: No es va poder llegir l'arxiu CSV traduït. {e}")
        return False

    current_cols = {col.strip(): col.strip() for col in df.columns}
    final_column_mapping = {}
    for csv_col, db_col in COLUMN_MAPPING.items():
        if csv_col in current_cols:
             final_column_mapping[csv_col] = db_col

    if not final_column_mapping:
           return False

    df = df.rename(columns=final_column_mapping)
    df = df[list(final_column_mapping.values())]

    text_columns = ['nombre', 'ingredientes', 'pasos', 'pais']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(aggressive_nlp_clean)

    if 'pais' in df.columns:
        df['categoria_interna'] = df['pais'].apply(normalize_category)
    else:
        df['categoria_interna'] = 'altres'
       
    df['nombre_limpio'] = df['nombre']

    df = df.fillna({col: '' for col in df.columns if col not in ['calorias', 'id']})
    if 'calorias' in df.columns:
        df['calorias'] = pd.to_numeric(df['calorias'], errors='coerce').fillna(0).astype(int)

    if 'id' in df.columns:
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        df = df[df['id'] > 0]

    try:
        conn = get_db_connection()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            nombre_limpio TEXT,
            url TEXT,
            ingredientes TEXT,
            pasos TEXT,
            pais TEXT,
            duracion TEXT,
            porciones TEXT,
            calorias INTEGER,
            categoria_interna TEXT,
            contexto TEXT,
            valoracion_votos TEXT,
            comensales TEXT,
            tiempo TEXT,
            dificultad TEXT,
            categoria_2 TEXT,
            categoria_raw TEXT
        );
        """
        conn.execute(create_table_query)
        conn.commit()

        required_cols = [
            'id', 'nombre', 'nombre_limpio', 'url', 'ingredientes', 'pasos', 'pais',
            'duracion', 'porciones', 'calorias', 'categoria_interna', 'contexto',
            'valoracion_votos', 'comensales', 'tiempo', 'dificultad', 'categoria_2',
            'categoria_raw'
        ]
       
        cols_to_keep = [col for col in required_cols if col in df.columns]
        df_final = df[cols_to_keep]

        df_final.to_sql('recipes', conn, if_exists='replace', index=False)
        conn.close()
        return True
    except Exception as e:
        print(f"Error en carregar dades a SQLite: {e}")
        return False

# Inicialització
load_data()

# =======================================================
#  LÒGICA DEL CHATBOT
# =======================================================

CATEGORY_SYNONYMS = {}
for key, name in INVERSE_CATEGORY_MAPPING.items():
    clean_name = aggressive_nlp_clean(name)
    CATEGORY_SYNONYMS[clean_name] = key
    CATEGORY_SYNONYMS[key] = key
    if key == 'eua':
        CATEGORY_SYNONYMS['estats units'] = key
        CATEGORY_SYNONYMS['usa'] = key
    if key == 'españa':
        CATEGORY_SYNONYMS['espanya'] = key
   

def extract_search_entities(normalized_message):
    search_term = ""
    category_key = 'all'
   
    # Neteja prèvia del missatge
    msg = aggressive_nlp_clean(normalized_message)
   
    # 1. Detectar Categoria (País)
    found_category = None
    sorted_synonyms = sorted(CATEGORY_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True)
   
    for synonym, key in sorted_synonyms:
        if re.search(r'\b' + re.escape(synonym) + r'\b', msg):
            found_category = synonym
            category_key = key
            break
           
    # 2. SECCIÓ DE PARAULES IGNORADES (STOPWORDS)
    # Afegim formes verbals, articles i crosses del llenguatge
    search_keywords_to_remove = [
        # Verbs i accions
        'magradaria', 'agradaria', 'vull', 'vul', 'voldria', 'cuinar', 'cuina',
        'fer', 'preparar', 'buscar', 'busca', 'cercar', 'cerca', 'trobar', 'troba',
        'fes', 'fems', 'ensenyams', 'digues', 'explica', 'recepta', 'receptes',
        'plat', 'plats', 'menjar', 'menjars',
       
        # Articles i Connectors
        'un', 'una', 'uns', 'unes', 'el', 'la', 'els', 'les', 'en', 'na',
        'de', 'del', 'dels', 'dela', 'amb', 'per', 'per a', 'que', 'qui'
    ]
   
    if found_category:
        msg = msg.replace(found_category, ' ')
   
    # Apliquem l'eliminació de paraules clau
    for keyword in search_keywords_to_remove:
        # \b garanteix que només s'elimini la paraula exacta, no part d'una altra
        msg = re.sub(r'\b' + keyword + r'\b', ' ', msg)
       
    search_term = ' '.join(msg.split()).strip()
    return search_term, category_key


def process_chatbot_message(message):
    normalized_message = aggressive_nlp_clean(message)
   
    if any(saludo in normalized_message for saludo in ['hola', 'bon dia', 'que tal']):
        return {"response": "Hola! Sóc el teu assistent de cuina. Què t'agradaria cuinar avui?"}

    if any(despedida in normalized_message for despedida in ['gracies', 'adeu', 'merci']):
        return {"response": "De res! Gaudeix del teu plat. Fins aviat!"}

    if any(comando in normalized_message for comando in ['categories', 'paisos']):
        category_list = ", ".join([f"'{INVERSE_CATEGORY_MAPPING[key]}'" for key in INTERNAL_CATEGORIES])
        return {"response": f"Puc buscar receptes de: {category_list}"}

    if any(comando in normalized_message for comando in ['suggereix', 'que menjo', 'atzar']):
        try:
            recipes = fetch_recipes("SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1")
            if recipes:
                recipe = recipes[0].copy()
                recipe['nombre'] = str(recipe['nombre']).title()
                return {"response": f"Et suggereixo: **{recipe['nombre']}**", "recipe": recipe}
        except:
            return {"response": "Error al cercar sugeriment."}

    search_term, category_key = extract_search_entities(message)
   
    if len(search_term) < 2 and category_key == 'all':
        return {"response": "Específica una mica més quin ingredient o plat busques (ex: 'vull pollastre')."}
   
    normalized_query = '%' + search_term + '%'
    where_clauses = []
    params = []
   
    if category_key != 'all':
        where_clauses.append("categoria_interna = ?")
        params.append(category_key)

    where_clauses.append("(nombre_limpio LIKE ? OR ingredientes LIKE ? OR pasos LIKE ?)")
    params.extend([normalized_query, normalized_query, normalized_query])
   
    sql_query = "SELECT * FROM recipes WHERE " + " AND ".join(where_clauses) + f" LIMIT {SEARCH_RESULT_LIMIT}"
    recipes = fetch_recipes(sql_query, params)
   
    if recipes:
        recipe = random.choice(recipes).copy()
        recipe['nombre'] = str(recipe['nombre']).title()
        return {"response": f"He trobat això: **{recipe['nombre']}**. T'interessa?", "recipe": recipe}
    else:
        return {"response": f"Ho sento, no he trobat cap recepta de '{search_term}'."}


# --- Rutes de l'API (Flask) ---

@app.route('/api/chatbot', methods=['POST'])
def chatbot_api():
    data = request.json
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({"response": "Missatge buit."}), 400
    return jsonify(process_chatbot_message(user_message))

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_index(path):
    if path != "" and os.path.exists(os.path.join(STATIC_FOLDER, path)):
        return send_from_directory(STATIC_FOLDER, path)
    return render_template('index.html')

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    search_query = aggressive_nlp_clean(request.args.get('q', ''))
    category_filter = request.args.get('cat', 'all').strip()
    recipes = []
   
    if not search_query and category_filter == 'all':
        for cat_key in INTERNAL_CATEGORIES:
            sql = f"SELECT * FROM recipes WHERE categoria_interna = ? ORDER BY RANDOM() LIMIT {INITIAL_PER_CATEGORY_SAMPLE}"
            recipes.extend(fetch_recipes(sql, (cat_key,)))
        random.shuffle(recipes)
    else:
        params = []
        where = []
        if category_filter != 'all':
            where.append("categoria_interna = ?")
            params.append(category_filter)
        if search_query:
            where.append("(nombre_limpio LIKE ? OR ingredientes LIKE ? OR pasos LIKE ?)")
            q = f"%{search_query}%"
            params.extend([q, q, q])
       
        sql = "SELECT * FROM recipes"
        if where: sql += " WHERE " + " AND ".join(where)
        sql += f" LIMIT {SEARCH_RESULT_LIMIT}"
        recipes = fetch_recipes(sql, params)

    for r in recipes:
        r['nombre'] = str(r['nombre']).title()
        r['categoria'] = r.pop('categoria_interna', 'altres')
        r.pop('nombre_limpio', None)

    return jsonify(recipes)

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify([{"key": k, "name": INVERSE_CATEGORY_MAPPING.get(k, k)} for k in INTERNAL_CATEGORIES])

if __name__ == '__main__':
    app.run(debug=True, port=5000)

