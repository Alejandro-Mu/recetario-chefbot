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
# CANVI CLAU: Assumim que aquest CSV ja ha estat traduït a català externament.
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
            # Retorna una llista de diccionaris a partir de les files de sqlite3.Row
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


# =======================================================
# 🤖 LÒGICA DEL CHATBOT MILLORADA 🤖
# =======================================================

# Global per a la detecció d'entitats (països/categories)
# Clau: sinònim d'usuari (sense accents) -> Valor: clau interna de la DB
CATEGORY_SYNONYMS = {}
for key, name in INVERSE_CATEGORY_MAPPING.items():
    clean_name = unidecode(name).lower()
    CATEGORY_SYNONYMS[clean_name] = key
    CATEGORY_SYNONYMS[key] = key # Per si l'usuari diu 'mexic'
    if key == 'eua':
        CATEGORY_SYNONYMS['estats units'] = key
        CATEGORY_SYNONYMS['usa'] = key
        CATEGORY_SYNONYMS['eeuu'] = key
    if key == 'españa':
        CATEGORY_SYNONYMS['espanya'] = key
        CATEGORY_SYNONYMS['espana'] = key
    if key == 'altres':
        CATEGORY_SYNONYMS['internacional'] = key
        CATEGORY_SYNONYMS['altres'] = key
   

def extract_search_entities(normalized_message):
    """
    Extreu el terme de cerca i la categoria (si n'hi ha) d'un missatge normalitzat.
    Aquesta funció neteja el missatge de les paraules clau d'intenció i categoria.
    """
    search_term = ""
    category_key = 'all'
   
    # 1. Trobar la categoria (Busca primer per trobar el terme de cerca més net)
    found_category = None
    # Iterem sobre sinònims més llargs primer per evitar coincidències parcials (e.g. 'eua' abans de 'estats units')
    sorted_synonyms = sorted(CATEGORY_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True)
   
    for synonym, key in sorted_synonyms:
        # Utilitzem \b (boundary) per coincidir amb la paraula completa i no parcial
        if re.search(r'\b' + re.escape(synonym) + r'\b', normalized_message):
            found_category = synonym
            category_key = key
            break
           
    # 2. Determinar el terme de cerca
    # Paraules que volem eliminar si no són part de la cerca real
    search_keywords_to_remove = ['cercar', 'buscar', 'vull', 'recepta', 'fes-me', 'de', 'un', 'una', 'a', 'en', 'la', 'el', 'plat', 'menjar', 'sopa', 'postre']
   
    # Eliminar el nom de la categoria trobada
    if found_category:
        # Reemplacem la categoria per un espai per evitar unir paraules
        normalized_message = normalized_message.replace(found_category, ' ')
       
    # Netejar el missatge de les paraules clau d'intenció
    cleaned_message = normalized_message
    for keyword in search_keywords_to_remove:
        cleaned_message = re.sub(r'\b' + keyword + r'\b', ' ', cleaned_message)
       
    # Netejar espais múltiples i retornar el terme de cerca
    search_term = ' '.join(cleaned_message.split()).strip()
   
    return search_term, category_key


def process_chatbot_message(message):
    """Processa el missatge de l'usuari i genera una resposta basada en intencions i cerca de la DB."""
   
    normalized_message = unidecode(message).lower().strip()
   
    # --- 1. INTENCIONS SIMPLES (Salutacions, Comandes Generals) ---
    if any(saludo in normalized_message for saludo in ['hola', 'bon dia', 'que tal', 'com estas']):
        return {"response": "Hola! Sóc el teu assistent de receptes. Puc ajudar-te a cercar plats, llistar categories (països) o suggerir-te alguna cosa. **Comencem amb una cerca?**"}

    if any(despedida in normalized_message for despedida in ['gracies', 'adeu', 'merci', 'bye', 'adieu']):
        return {"response": "De res! Que tinguis un bon dia i bon profit! **Fins aviat!**"}

    if any(comando in normalized_message for comando in ['categories', 'llista categories', 'quines categories', 'mostra categories', 'països', 'paisos']):
        category_list = ", ".join([f"'{INVERSE_CATEGORY_MAPPING[key]}'" for key in INTERNAL_CATEGORIES])
        return {"response": f"Les categories (països) disponibles són: {category_list}. **Prova de dir 'Vull la recepta de paella espanyola'**."}

    # --- 2. INTENCIÓ DE SUGGERIMENT (Random amb correcció de retorn) ---
    if any(comando in normalized_message for comando in ['suggereix', 'que menjo', 'recomana', 'atzar', 'sorpren-me']):
        try:
            sql_query = "SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1"
            recipes = fetch_recipes(sql_query)
           
            if recipes:
                # CORRECCIÓ CLAU: Utilitzem .copy() per garantir que totes les dades es mantenen.
                recipe = recipes[0].copy()
               
                # Neteja i format de la recepta
                recipe['nombre'] = str(recipe['nombre']).title()
                recipe['categoria'] = recipe.pop('categoria_interna', 'altres')
                recipe.pop('nombre_limpio', None)
               
                return {
                    "response": f"Avui et suggereixo provar la recepta de **'{recipe['nombre']}'**, un plat típic {INVERSE_CATEGORY_MAPPING.get(recipe['categoria'], 'Altres')}. **Què et sembla?**",
                    "recipe": recipe # Retornem el diccionari de la recepta complet i net
                }
            else:
                return {"response": "No tinc receptes ara mateix per suggerir-te. La base de dades està buida."}
        except Exception as e:
            print(f"Error en suggeriment: {e}")
            return {"response": "He tingut un problema a l'hora de buscar una suggerència. Prova de nou."}


    # --- 3. INTENCIÓ DE CERCA (La més complexa) ---
    search_term, category_key = extract_search_entities(normalized_message)
   
    if len(search_term) < 2:
        # Captura missatges que no han estat cap intenció anterior i tenen un terme de cerca massa curt
        return {"response": "Si us plau, especifica **què vols cercar** (més de dues lletres). Per exemple: 'Cercar Pastís de xocolata' o 'vull una recepta de Xile'."}
   
   
    # 4. Construcció de la Query SQL per semblança millorada
   
    normalized_query = '%' + unidecode(search_term).lower() + '%'
    normalized_query_startswith = unidecode(search_term).lower() + '%'
    exact_search_term = unidecode(search_term).lower()
   
    where_clauses = []
    params = []
   
    if category_key != 'all':
        where_clauses.append("categoria_interna = ?")
        params.append(category_key)

    # Clàusula WHERE (cerca àmplia per semblança en 3 camps)
    where_clauses.append("""
        (nombre_limpio LIKE ? OR
         ingredientes LIKE ? OR
         pasos LIKE ?)
    """)
   
    params.extend([normalized_query, normalized_query, normalized_query])
   
    sql_query = "SELECT * FROM recipes WHERE " + " AND ".join(where_clauses) + f"""
        ORDER BY
            CASE
                WHEN nombre_limpio = ? THEN 0 -- MAXIMA RELLEVANCIA: Coincidència EXACTA
                WHEN nombre_limpio LIKE ? THEN 1 -- ALTA RELLEVANCIA: Comença amb el terme
                ELSE 2                           -- RELLEVANCIA BAIXA: Coincidència de subcadena
            END,
        nombre ASC LIMIT {SEARCH_RESULT_LIMIT}
    """
   
    # Afegim els paràmetres d'ordenació al final de la llista de paràmetres
    final_params = params + [exact_search_term, normalized_query_startswith]
   
    recipes = fetch_recipes(sql_query, final_params)
   
    # 5. Resposta final de Cerca
    if recipes:
        # Triem una recepta de les trobades
        # CORRECCIÓ CLAU: Utilitzem .copy() per garantir que totes les dades es mantenen.
        recipe = random.choice(recipes).copy()
       
        # Neteja i format de la recepta
        recipe['nombre'] = str(recipe['nombre']).title()
        recipe['categoria'] = recipe.pop('categoria_interna', 'altres')
        recipe.pop('nombre_limpio', None)
       
        cat_response = f"a la categoria {INVERSE_CATEGORY_MAPPING.get(recipe['categoria'], 'Altres')}" if category_key != 'all' else ""

        # Missatges amb èmfasi basat en la qualitat de la cerca
        if unidecode(recipe['nombre']).lower() == exact_search_term or unidecode(recipe['nombre']).lower().startswith(exact_search_term):
             response_text = f"Molt bé! He trobat una coincidència excel·lent: **'{recipe['nombre']}'** {cat_response}. **Comença la cocció!**"
        else:
             response_text = f"He trobat la recepta de **'{recipe['nombre']}'** {cat_response}, que s'assembla molt a la teva cerca. **Vols provar-la?**"


        return {
            "response": response_text,
            "recipe": recipe # Retornem el diccionari de la recepta complet i net
        }
    else:
        cat_response = f"a la categoria {INVERSE_CATEGORY_MAPPING.get(category_key, 'Altres')}" if category_key != 'all' else ""
        return {"response": f"No he trobat cap recepta que s'assembli a '{search_term}' {cat_response}. Recorda que només puc cercar per nom, ingredients o passos. **Prova amb una altra paraula clau!**"}


    # --- RESPOSTA PER DEFECTE FINAL ---
    return {"response": "No t'he entès. Recorda que puc: **Cercar plats, llistar categories o suggerir-te un plat a l'atzar**."}


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
           
            # Nota: la cerca de l'API manté la desaccentuació amb REPLACE a SQL,
            # ja que la columna ingredients i passos no tenen una versió 'neta' precalculada.
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
            # Paràmetres per a l'ordenació
            normalized_query_startswith = unidecode(search_query).lower() + '%'
            exact_search_term = unidecode(search_query).lower()
           
            final_params = params + [exact_search_term, normalized_query_startswith]
           
            sql_query += f"""
                ORDER BY
                    CASE
                        WHEN nombre_limpio = ? THEN 0
                        WHEN nombre_limpio LIKE ? THEN 1
                        ELSE 2                          
                    END,
                nombre ASC
                LIMIT {limit}
            """
            recipes = fetch_recipes(sql_query, final_params)
        else:
            # Ordenació simple per nom si no hi ha cerca
            sql_query += " ORDER BY nombre ASC"
            sql_query += f" LIMIT {limit}"
            recipes = fetch_recipes(sql_query, params)
        # -------------------------------------------------------------------

    # 3. Format de la resposta
    formatted_recipes = []
    for recipe in recipes:
        # Utilitzem .copy() aquí també per precaució, tot i que fetch_recipes ja retorna dict(row)
        recipe_copy = recipe.copy()
       
        recipe_copy['nombre'] = str(recipe_copy['nombre']).title()
        recipe_copy['categoria'] = recipe_copy.pop('categoria_interna', 'altres')
        recipe_copy.pop('nombre_limpio', None)
        formatted_recipes.append(recipe_copy)


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
    # És important que el fitxer CSV 'recetas_traducidas.csv' existeixi al mateix directori.
    app.run(debug=True, port=5000)

