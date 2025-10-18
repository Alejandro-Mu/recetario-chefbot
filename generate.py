import sqlite3
import os
import sys
import random

# --- CONFIGURACIÓN DE LA BASE DE DATOS Y ESTRUCTURA ---
DB_NAME = 'recetas.db'
NUM_RECIPES_PER_CATEGORY = 200
TOTAL_RECIPES = 3 * NUM_RECIPES_PER_CATEGORY
CATEGORIES = ['primer_plato', 'segundo_plato', 'postres']

# Definición del esquema SQL de la tabla (debe coincidir con el modelo de Flask)
TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS recipe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL,
    ingredientes TEXT NOT NULL,
    pasos TEXT NOT NULL,
    imagen_url TEXT
);
"""

# --- DATOS PARA GENERACIÓN PROCEDURAL (ESPAÑOL) ---

# Ingredientes base comunes
COMMON_INGREDIENTS = [
    "Aceite de oliva virgen extra", "Sal", "Pimienta negra molida", "Cebolla", 
    "Ajo", "Agua", "Perejil fresco", "Huevo", "Leche", "Harina de trigo"
]

# Componentes para Primeros Platos (Primer_plato)
STARTERS_TYPES = ["Crema de", "Sopa de", "Ensalada de", "Timbal de", "Vichyssoise de"]
STARTERS_VEGS = ["Calabacín", "Zanahoria", "Tomate", "Puerro", "Remolacha", "Espárragos", "Brócoli"]
STARTERS_ADJ = ["Fina", "Fría", "Cremosa", "Templada", "Ecológica"]

# Componentes para Segundos Platos (Segundo_plato)
MAIN_TYPES = ["Filete de", "Lomo de", "Pechuga de", "Fideuá de", "Arroz con", "Merluza a la"]
MAIN_PROTEIN = ["Ternera", "Pollo", "Bacalao", "Salmón", "Cerdo ibérico", "Calamares", "Gambas"]
MAIN_PREP = ["a la plancha", "al horno", "a la marinera", "en salsa de almendras", "con salsa de mostaza", "estofado"]
MAIN_SIDES = ["Patatas panaderas", "Verduras salteadas", "Arroz blanco", "Puré de patatas cremoso"]

# Componentes para Postres (Postres)
DESSERT_TYPES = ["Tarta de", "Mousse de", "Flan de", "Brownie de", "Copa de"]
DESSERT_FLAVORS = ["Chocolate negro", "Limón", "Fresa", "Vainilla", "Avellanas", "Café", "Naranja"]
DESSERT_TOPPINGS = ["con nata montada", "y coulis de frambuesa", "y virutas de cacao", "con nueces caramelizadas"]


# --- FUNCIONES DE GENERACIÓN DE CONTENIDO ---

def generate_primer_plato():
    """Genera una receta de primer plato realista."""
    dish_type = random.choice(STARTERS_TYPES)
    main_veg = random.choice(STARTERS_VEGS)
    adj = random.choice(STARTERS_ADJ)

    name = f"{dish_type} {main_veg} {adj}"
    
    ingredients = [
        f"500g de {main_veg}", "1l de caldo de verduras", "200ml de nata para cocinar", 
        "1 cebolla pequeña", "1 diente de ajo", "2 cucharadas de Aceite de oliva virgen extra", 
        "Sal y Pimienta al gusto"
    ]
    ingredients_text = "\n".join(random.sample(ingredients, 6) + COMMON_INGREDIENTS[:2])

    steps = [
        "1. Sofreír la cebolla y el ajo picados en aceite.",
        f"2. Añadir el {main_veg} troceado y cocinar 5 minutos.",
        "3. Verter el caldo y cocer hasta que la verdura esté tierna.",
        "4. Triturar hasta obtener una crema fina, añadiendo la nata al final.",
        "5. Rectificar de sal y servir caliente (o fría, si es el caso)."
    ]
    steps_text = "\n".join(steps)
    
    url_name = name.replace(' ', '+')
    image_url = f"https://placehold.co/400x300/a3e635/000?text={url_name}"

    return name, ingredients_text, steps_text, image_url

def generate_segundo_plato():
    """Genera una receta de segundo plato realista."""
    dish_type = random.choice(MAIN_TYPES)
    protein = random.choice(MAIN_PROTEIN)
    prep = random.choice(MAIN_PREP)
    side = random.choice(MAIN_SIDES)

    name = f"{dish_type} {protein} {prep} con {side}"
    
    ingredients = [
        f"4 piezas de {protein}", "100ml de vino blanco", "200ml de caldo de carne", 
        "2 tomates maduros", "1 rama de romero", f"500g de {side.split(' ')[0]}", 
        "1 pimiento verde"
    ]
    ingredients_text = "\n".join(random.sample(ingredients, 7) + COMMON_INGREDIENTS[:4])

    steps = [
        f"1. Sellar la {protein} en una sartén a fuego alto.",
        f"2. Añadir el resto de verduras y desglasar con el vino.",
        "3. Incorporar el caldo, el romero, sal y pimienta.",
        f"4. Cocinar a fuego lento o en el horno a 180°C durante 30-40 minutos.",
        f"5. Servir la pieza de {protein} con la salsa y el acompañamiento de {side}."
    ]
    steps_text = "\n".join(steps)
    
    url_name = name.replace(' ', '+')
    image_url = f"https://placehold.co/400x300/fca5a5/000?text={url_name}"

    return name, ingredients_text, steps_text, image_url

def generate_postres():
    """Genera una receta de postre realista."""
    dish_type = random.choice(DESSERT_TYPES)
    flavor = random.choice(DESSERT_FLAVORS)
    topping = random.choice(DESSERT_TOPPINGS)

    name = f"{dish_type} {flavor} {topping}"
    
    ingredients = [
        "250g de azúcar", "150g de mantequilla", "3 huevos grandes", "200g de harina de repostería", 
        "1 sobre de levadura química", "100g de chocolate para fundir", "Esencia de vainilla", 
        "Ralladura de limón o naranja"
    ]
    ingredients_text = "\n".join(random.sample(ingredients, 6) + ["Pellizco de Sal", "200ml de Nata montada"])

    steps = [
        "1. Batir la mantequilla con el azúcar hasta que esté cremosa.",
        "2. Incorporar los huevos uno a uno, batiendo bien después de cada adición.",
        "3. Mezclar los ingredientes secos (harina, levadura, sal) y añadirlos a la mezcla.",
        f"4. Añadir el {flavor} fundido (si aplica).",
        "5. Verter en el molde y hornear a 170°C durante 35 minutos. Decorar con el topping."
    ]
    steps_text = "\n".join(steps)
    
    url_name = name.replace(' ', '+')
    image_url = f"https://placehold.co/400x300/fde047/000?text={url_name}"

    return name, ingredients_text, steps_text, image_url


def generate_recipe_data(category):
    """Genera una receta completa para una categoría dada."""
    if category == 'primer_plato':
        name, ingredients, steps, url = generate_primer_plato()
    elif category == 'segundo_plato':
        name, ingredients, steps, url = generate_segundo_plato()
    elif category == 'postres':
        name, ingredients, steps, url = generate_postres()
    else:
        raise ValueError(f"Categoría desconocida: {category}")
        
    return (name, category, ingredients, steps, url)

# --- FUNCIÓN PRINCIPAL DEL SCRIPT ---

def create_and_populate_db():
    """Crea la base de datos y la rellena con 600 recetas."""
    
    # 1. Comprobar argumento --force
    if '--force' in sys.argv and os.path.exists(DB_NAME):
        print(f"Detectado --force. Eliminando {DB_NAME}...")
        os.remove(DB_NAME)
        
    # 2. Conexión a la base de datos
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error al conectar/crear la base de datos: {e}")
        return

    # 3. Crear la tabla
    cursor.execute(TABLE_SCHEMA)
    conn.commit()
    print(f"Tabla 'recipe' asegurada en {DB_NAME}.")
    
    # 4. Comprobar si ya hay suficientes recetas
    cursor.execute("SELECT COUNT(*) FROM recipe")
    count = cursor.fetchone()[0]
    
    if count >= TOTAL_RECIPES:
        print(f"La base de datos ya contiene {count} recetas. No se añaden más.")
        conn.close()
        return

    # 5. Generar e insertar las 600 recetas
    print(f"Generando {TOTAL_RECIPES} recetas (200 por categoría)...")
    
    recipes_to_insert = []
    
    for category in CATEGORIES:
        for _ in range(NUM_RECIPES_PER_CATEGORY):
            name, ingredients, steps, url = generate_recipe_data(category)
            recipes_to_insert.append((name, category, ingredients, steps, url))
            
    # Mezclar las recetas antes de insertar para tener IDs intercalados
    random.shuffle(recipes_to_insert)

    insert_sql = "INSERT INTO recipe (nombre, categoria, ingredientes, pasos, imagen_url) VALUES (?, ?, ?, ?, ?)"
    cursor.executemany(insert_sql, recipes_to_insert)
    
    conn.commit()
    print(f"Se han insertado {len(recipes_to_insert)} nuevas recetas con éxito.")
    
    # 6. Verificación final
    cursor.execute("SELECT COUNT(*) FROM recipe")
    final_count = cursor.fetchone()[0]
    print(f"Total de recetas en la base de datos: {final_count}")
    
    conn.close()

if __name__ == '__main__':
    create_and_populate_db()

# Instrucciones de uso:
# Para crear/poblar la base de datos: python generate_db.py
# Para forzar la recreación completa: python generate_db.py --force
