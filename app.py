import pandas as pd
import os
import sqlite3
from unidecode import unidecode
from flask import Flask, request, jsonify, send_from_directory, render_template
import re
import random
import urllib.parse
# La llibreria de traducció s'ha eliminat. La base de dades s'ha de carregar ja traduïda.

# --- Configuració de Flask i Constants ---
app = Flask(__name__)

# --- CONFIGURACIÓ D'ARXIUS I BASE DE DADES ---
# 🚨 CANVI CLAU: Assumim que aquest CSV ja ha estat traduït a català externament.
CSV_FILE_PATH = 'recetas_traducidas.csv'
DB_FILE = 'recetas.db'
STATIC_FOLDER = 'static'

# CONSTANTS DE LÍMIT
CATEGORY_LOAD_LIMIT = 5000
SEARCH_RESULT_LIMIT = 50
INITIAL_PER_CATEGORY_SAMPLE = 100

# Alineació de Categories a Països (Frontend/Backend)
INTERNAL_CATEGORIES = [
    'mexic', 'peru', 'españa', 'argentina', 'colombia',
    'chile', 'venezuela', 'ecuador', 'italia', 'eua', 'altres'
]

# Mapeig invers (Intern -> Nom Amigable CAT)
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

# Mapeig de columnes del CSV a la DB
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

# --- Funcions d'Utilitat de Base de Dades ---

def get_db_connection():
    """Crea i retorna una connexió a la base de dades."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_recipes(query, params=()):
    """Executa una consulta SQL i retorna els resultats com a llista de diccionaris."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR en consultar la base de dades: {e}")
        return []

def get_recipe_count():
    """Retorna el nombre total de receptes."""
    try:
        with get_db_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    except Exception:
        return 0

def get_all_categories_keys(read_from_db=False):
    """Retorna totes les claus de categoria (països) des de la llista interna."""
    return INTERNAL_CATEGORIES

# =======================================================
# CORRECCIÓ DE CODIFICACIÓ REFORÇADA
# =======================================================
def repair_text_encoding(text):
    """
    Repara strings que han estat llegits incorrectament i elimina caràcters URL-encoded.
    """
    if pd.isna(text) or not isinstance(text, str):
        return ''
        
    # 1. Arreglar el URL encoding
    try:
        text = urllib.parse.unquote(text)
    except:
        pass
        
    # 2. Arreglar el doble encoding
    try:
        repaired_text = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
        if len(repaired_text) > len(text) * 0.5:
            text = repaired_text
    except:
        pass
        
    # 3. Eliminar caràcters no desitjats o de control
    text = re.sub(r'[^\x00-\x7F\u00A0-\uFFFF\s]+', '', text)
    
    return text.strip()

# =======================================================
# NORMALITZACIÓ DE CATEGORIES
# =======================================================
def normalize_category(raw_pais):
    """
    Mapeja una cadena de país bruta (ja reparada) del CSV a una de les claus
    definides a INTERNAL_CATEGORIES (en català).
    """
    if pd.isna(raw_pais) or not raw_pais:
        return 'altres'

    normalized = unidecode(str(raw_pais)).lower()
    
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
    """Carrega les dades del CSV (TRADUÏT), les neteja i les insereix a la base de dades SQLite."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Base de dades '{DB_FILE}' existent eliminada per a recàrrega neta.")

    try:
        # Intentem llegir el CSV traduït
        df = pd.read_csv(csv_file_path, encoding='utf-8')
    except Exception as e:
        print(f"Error fatal: No es va poder llegir l'arxiu CSV traduït. Assegura't que existeix '{csv_file_path}'. {e}")
        return False

    current_cols = {col.strip(): col.strip() for col in df.columns}
    final_column_mapping = {}
    for csv_col, db_col in COLUMN_MAPPING.items():
        if csv_col in current_cols:
              final_column_mapping[csv_col] = db_col

    if not final_column_mapping:
          print("Error: No es van trobar columnes rellevants en el CSV.")
          return False

    df = df.rename(columns=final_column_mapping)
    df = df[list(final_column_mapping.values())]

    # Aplicar la reparació de codificació a les columnes rellevants (ja traduïdes)
    df['nombre'] = df['nombre'].apply(repair_text_encoding)
    df['ingredientes'] = df['ingredientes'].apply(repair_text_encoding)
    df['pasos'] = df['pasos'].apply(repair_text_encoding)
    df['pais'] = df['pais'].apply(repair_text_encoding)

    # Aplicar la normalització de Categoria (País)
    if 'pais' in df.columns:
        df['categoria_interna'] = df['pais'].apply(normalize_category)
    else:
        df['categoria_interna'] = 'altres'
        
    # Crear una columna de nom net per a cerques sense accents/caràcters especials
    df['nombre_limpio'] = df['nombre'].apply(lambda x: unidecode(str(x)).lower() if pd.notna(x) else '')


    df = df.fillna({col: '' for col in df.columns if col not in ['calorias', 'id']})
    if 'calorias' in df.columns:
        df['calorias'] = pd.to_numeric(df['calorias'], errors='coerce').fillna(0).astype(int)

    if 'id' in df.columns:
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        df = df[df['id'] > 0]

    try:
        conn = get_db_connection()
        create_table_query = f"""
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
        print(f"Dades carregades correctament: {len(df_final)} receptes a '{db_file}'.")
        return True
    except Exception as e:
        print(f"Error en carregar dades a SQLite: {e}")
        return False

# Inicialitzar la base de dades a l'arrencar
print("Forçant inicialització de base de dades per aplicar correccions de codificació...")
if not load_data():
    print("Falla en la càrrega inicial de dades.")


# --- Lògica del Chatbot (Traduïda al català) ---

def process_chatbot_message(message):
    """Processa el missatge de l'usuari i genera una resposta basada en regles (en català)."""
    
    # 1. Normalització del missatge
    normalized_message = unidecode(message).lower().strip()
    
    # 2. Respostes basades en regles i paraules clau
    
    # --- SALUDES I COMANDES GENERALS ---
    if any(saludo in normalized_message for saludo in ['hola', 'bon dia', 'que tal', 'com estas']):
        return {"response": "Hola! Sóc el teu assistent de receptes. Puc ajudar-te a cercar plats, llistar categories (països) o suggerir-te alguna cosa. **Comencem amb una cerca?**"}

    if any(despedida in normalized_message for despedida in ['gracies', 'adeu', 'merci', 'bye']):
        return {"response": "De res! Que tinguis un bon dia i bon profit! **Fins aviat!**"}

    if any(comando in normalized_message for comando in ['categories', 'llista categories', 'quines categories', 'mostra categories', 'països', 'paisos']):
        category_list = ", ".join([f"'{INVERSE_CATEGORY_MAPPING[key]}'" for key in INTERNAL_CATEGORIES])
        return {"response": f"Les categories (països) disponibles són: {category_list}. **Prova de dir 'Cercar [nom del plat] a [nom del país]'**."}

    # --- COMANDES DE SUGGERIMENT ---
    if any(comando in normalized_message for comando in ['suggereix', 'que menjo', 'recomana', 'un plat a l\'atzar', 'atzar']):
        try:
            sql_query = "SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1"
            recipes = fetch_recipes(sql_query)
            
            if recipes:
                recipe = recipes[0]
                # Capitalització (MODIFICACIÓ SOL·LICITADA)
                recipe['nombre'] = str(recipe['nombre']).title()
                recipe['categoria'] = recipe.pop('categoria_interna', 'altres')
                
                return {
                    "response": f"Et suggereixo provar la recepta de **'{recipe['nombre']}'**, de {INVERSE_CATEGORY_MAPPING.get(recipe['categoria'], 'Altres')}. **Et pot interessar una altra cerca?**",
                    "recipe": recipe
                }
            else:
                return {"response": "No tinc receptes ara mateix per suggerir-te. La base de dades està buida."}
        except Exception:
            return {"response": "He tingut un problema a l'hora de buscar una suggerència. Prova de nou."}

    # --- LÒGICA DE CERCA REFINADA (PER SEMBLANÇA) ---
    search_keywords = ['cercar', 'buscar', 'vull', 'recepta de', 'fes-me']
    
    if any(keyword in normalized_message for keyword in search_keywords) or not any(x in normalized_message for x in ['hola', 'gracies', 'categories', 'suggereix']):
        
        search_term = ""
        category_key = 'all'
        
        # 3a. Detecció de Terme de Cerca
        search_term_match = re.search(r'(?:' + '|'.join(search_keywords) + r')\s+(.*?)(\s+a la categoria|\s+en la categoria|$)', normalized_message)
        
        if search_term_match:
            search_term = search_term_match.group(2).strip()
        elif 'recepta de' in normalized_message:
            search_term = normalized_message.split('recepta de', 1)[1].strip()
        elif not any(keyword in normalized_message for keyword in search_keywords):
             # Assumim que el missatge sencer és el terme de cerca si no és una comanda coneguda.
             search_term = normalized_message.strip() 
        
        # 3b. Detecció de Categoria
        category_match = re.search(r'(?:a la categoria|en la categoria)\s+(.*)', normalized_message)
        category_name = category_match.group(1).strip() if category_match else ""
        
        if category_name:
            for key, name in INVERSE_CATEGORY_MAPPING.items():
                if unidecode(category_name).lower() in unidecode(name).lower():
                    category_key = key
                    break
        
        if len(search_term) < 2:
             return {"response": "Si us plau, especifica **què vols cercar** (més de dues lletres). Per exemple: 'Cercar Pastís'."}


        # 4. Construcció de la Query SQL per semblança
        
        # Paràmetre per a la cerca àmplia (LIKE %query%)
        normalized_query = '%' + unidecode(search_term).lower() + '%'
        
        # Paràmetre per a la Priorització (LIKE query%)
        normalized_query_startswith = unidecode(search_term).lower() + '%'
        
        where_clauses = []
        # El primer paràmetre és per l'ORDER BY (Priorització)
        params = [normalized_query_startswith] 
        
        if category_key != 'all':
            where_clauses.append("categoria_interna = ?")
            params.append(category_key)

        # Clàusula WHERE (cerca àmplia per semblança en 3 camps)
        where_clauses.append("""
            (nombre_limpio LIKE ? OR
             LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(ingredientes, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')) LIKE ? OR
             LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(pasos, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')) LIKE ?)
        """)
        # Afegim els 3 wildcards per la cerca (nombre, ingredientes, pasos)
        params.extend([normalized_query, normalized_query, normalized_query]) 
        
        sql_query = "SELECT * FROM recipes WHERE " + " AND ".join(where_clauses) + f""" 
            ORDER BY
                CASE
                    WHEN nombre_limpio LIKE ? THEN 0 -- MAXIMA RELLEVANCIA: El nom comença amb el terme de cerca (Cerca per semblança)
                    ELSE 1                           -- RELLEVANCIA BAIXA: Coincidència de subcadena en qualsevol lloc
                END,
            nombre ASC LIMIT {SEARCH_RESULT_LIMIT}
        """
        
        recipes = fetch_recipes(sql_query, params)
        
        # 5. Resposta final
        if recipes:
            recipe = random.choice(recipes)
            recipe['nombre'] = str(recipe['nombre']).title()
            recipe['categoria'] = recipe.pop('categoria_interna', 'altres')
            
            cat_response = f"de la categoria {INVERSE_CATEGORY_MAPPING.get(recipe['categoria'], 'Altres')}" if category_key != 'all' else ""

            return {
                "response": f"He trobat la recepta de **'{recipe['nombre']}'** {cat_response}. **La priorització per semblança ha funcionat!** T'agradaria cercar alguna cosa més o que et suggereixi un altre plat?",
                "recipe": recipe
            }
        else:
            cat_response = f"a la categoria {INVERSE_CATEGORY_MAPPING.get(category_key, 'Altres')}" if category_key != 'all' else ""
            return {"response": f"No he trobat cap recepta que s'assembli a '{search_term}' {cat_response}. **Prova amb una altra paraula clau!**"}


    # --- RESPOSTA PER DEFECTE MILLORADA ---
    return {"response": "No t'he entès. Recorda que puc: **Cercar plats, llistar categories o suggerir-te un plat**."}


# --- Rutes de l'API (Flask) ---

@app.route('/api/chatbot', methods=['POST'])
def chatbot_api():
    """Ruta per gestionar la comunicació amb el chatbot (en català)."""
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({"response": "Missatge buit."}), 400
    
    chatbot_response = process_chatbot_message(user_message)
    
    return jsonify(chatbot_response)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_index(path):
    """Serveix l'arxiu index.html des de l'arrel o gestiona rutes estàtiques/reactives."""
    if path != "" and os.path.exists(os.path.join(STATIC_FOLDER, path)):
        return send_from_directory(STATIC_FOLDER, path)
    else:
        return render_template('index.html')


@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    """Retorna una llista filtrada i paginada de receptes des de la base de dades."""
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('cat', 'all').strip()

    recipes = []
    
    # 1. Lògica de Càrrega Inicial (mostreig per categoria)
    if not search_query and category_filter == 'all':
        
        for cat_key in INTERNAL_CATEGORIES:
            limit = INITIAL_PER_CATEGORY_SAMPLE
            if cat_key == 'altres':
                  limit = INITIAL_PER_CATEGORY_SAMPLE * 2
                  
            sql_query = f"""
                SELECT * FROM recipes
                WHERE categoria_interna = ?
                ORDER BY RANDOM()
                LIMIT {limit}
            """
            recipes.extend(fetch_recipes(sql_query, (cat_key,)))
        
        random.shuffle(recipes)
            
    # 2. Lògica de Cerca i Filtratge Simple
    else:
        params = []
        where_clauses = []
        
        limit = CATEGORY_LOAD_LIMIT 
        
        # Filtratge per Categoria (País)
        if category_filter != 'all':
            if category_filter in INTERNAL_CATEGORIES:
                where_clauses.append("categoria_interna = ?")
                params.append(category_filter)
            else:
                  return jsonify({"error": "Categoria no vàlida."}), 400

        # Filtratge per Cerca (nom, ingredients, passos)
        if search_query:
            limit = SEARCH_RESULT_LIMIT
            normalized_query = '%' + unidecode(search_query).lower() + '%'
            
            where_clauses.append("""
                (nombre_limpio LIKE ? OR
                 LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(ingredientes, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')) LIKE ? OR
                 LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(pasos, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')) LIKE ?)
            """)
            params.extend([normalized_query, normalized_query, normalized_query])
            
        # Construcció de la Query SQL
        sql_query = "SELECT * FROM recipes"
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        
        # --- LÒGICA D'ORDENACIÓ PER RELEVÀNCIA / NOM (Cerca per semblança) ---
        if search_query:
            # Paràmetre per a la prioritat (LIKE terme%)
            normalized_query_startswith = unidecode(search_query).lower() + '%'
            params.insert(0, normalized_query_startswith) 
            
            sql_query += f"""
                ORDER BY
                    CASE
                        WHEN nombre_limpio LIKE ? THEN 0 
                        ELSE 1                           
                    END,
                nombre ASC
                LIMIT {limit}
            """
        else:
            # Ordenació simple per nom si no hi ha cerca
            sql_query += " ORDER BY nombre ASC"
            sql_query += f" LIMIT {limit}"
        # -------------------------------------------------------------------
        
        recipes = fetch_recipes(sql_query, params)

    # 3. Format de la resposta
    formatted_recipes = []
    for recipe in recipes:
        # --- CAPITALITZACIÓ DEL NOM (MODIFICACIÓ SOL·LICITADA) ---
        recipe['nombre'] = str(recipe['nombre']).title()
        # ------------------------------------------
        recipe['categoria'] = recipe.pop('categoria_interna', 'altres')
        recipe.pop('nombre_limpio', None)
        formatted_recipes.append(recipe)


    return jsonify(formatted_recipes)


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Retorna la llista de categories internes (països) i els seus noms amigables (en català)."""
    categories_data = []
    for key in INTERNAL_CATEGORIES:
        categories_data.append({
            "key": key,
            "name": INVERSE_CATEGORY_MAPPING.get(key, key.replace('_', ' ').capitalize())
        })
    return jsonify(categories_data)


# Bloc d'inici
if __name__ == '__main__':
    app.run(debug=True, port=5000)
