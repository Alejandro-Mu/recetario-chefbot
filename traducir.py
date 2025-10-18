import pandas as pd
from deep_translator import GoogleTranslator

# =================================================================================
#                         >>> CONFIGURACIÓN REQUERIDA <<<
# =================================================================================

# 1. RUTA Y NOMBRE DE TU ARCHIVO CSV ORIGINAL
#    (El archivo 'recetas.csv' debe estar en la misma carpeta que este script)
NOMBRE_ARCHIVO_ENTRADA = 'recetas.csv'

# 2. DELIMITADOR UTILIZADO EN TU CSV (El archivo 'recetas.csv' usa '|')
DELIMITADOR_CSV = '|'

# 3. NOMBRE DE LA COLUMNA QUE CONTIENE EL TEXTO A TRADUCIR
#    Opciones comunes: 'Nombre' o 'Ingredientes'
COLUMNA_A_TRADUCIR = 'Nombre'  # <--- ¡CAMBIA ESTO si quieres traducir 'Ingredientes'!

# 4. IDIOMAS (El español es el idioma de origen de tus recetas)
IDIOMA_ORIGEN = 'es'
IDIOMA_DESTINO = 'ca'  # Código del idioma al que quieres traducir (ej: 'en', 'fr', 'de')

# 5. NOMBRE DEL ARCHIVO DE SALIDA CON LOS RESULTADOS
NOMBRE_ARCHIVO_SALIDA = f"recetas_traducidas_{IDIOMA_DESTINO}.csv"

# =================================================================================
#                         >>> INICIO DEL CÓDIGO <<<
# =================================================================================

def traducir_columna_csv(input_path, output_path, delimiter, column_name, source_lang, target_lang):
    """
    Procesa el CSV con delimitador personalizado, traduce la columna especificada
    y guarda el resultado.
    """
    print(f"Iniciando lectura del archivo: {input_path} con delimitador '{delimiter}'")
   
    try:
        # 1. Cargar el CSV usando el delimitador correcto
        # Se usa 'engine='python'' para manejar delimitadores de un solo carácter en algunos sistemas.
        df = pd.read_csv(input_path, sep=delimiter, engine='python')
    except Exception as e:
        print(f"ERROR al leer el archivo. Verifica la ruta y codificación. Error: {e}")
        return

    if column_name not in df.columns:
        print(f"ERROR: La columna '{column_name}' no se encuentra en el CSV.")
        print(f"Columnas disponibles: {list(df.columns)}")
        return
       
    # Eliminar filas donde el valor de la columna a traducir es NaN (vacío)
    df.dropna(subset=[column_name], inplace=True)
   
    # Inicializar el traductor
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    nueva_columna = f"{column_name}_{target_lang}"
   
    print(f"Traduciendo columna '{column_name}' de {source_lang} a {target_lang}...")
    total_entradas = len(df)
   
    traducciones = []
   
    # 2. Iterar, Traducir y mostrar progreso
    for i, texto in enumerate(df[column_name].astype(str).tolist()):
        try:
            traduccion = translator.translate(texto)
            traducciones.append(traduccion)
           
            # Mostrar progreso cada 200 entradas
            if (i + 1) % 200 == 0:
                print(f"Progreso: {i + 1}/{total_entradas} entradas traducidas...")
               
        except Exception as e:
            # En caso de error (ej. límite de API), marca el error y continúa
            print(f"Advertencia: Error al traducir entrada {i+1}. Error: {e}. Saltando.")
            traducciones.append(f"[ERROR_TRADUCCION] {texto}")
           
    # 3. Añadir la nueva columna al DataFrame
    df[nueva_columna] = traducciones

    # 4. Guardar el nuevo CSV (usando el mismo delimitador para mantener formato)
    df.to_csv(output_path, index=False, sep=delimiter, encoding='utf-8')
   
    print("-" * 30)
    print(f"¡TRADUCCIÓN COMPLETADA!")
    print(f"Se tradujeron {len(traducciones)} entradas.")
    print(f"Archivo guardado como: {output_path}")

# --- EJECUCIÓN ---
traducir_columna_csv(
    NOMBRE_ARCHIVO_ENTRADA,
    NOMBRE_ARCHIVO_SALIDA,
    DELIMITADOR_CSV,
    COLUMNA_A_TRADUCIR,
    IDIOMA_ORIGEN,
    IDIOMA_DESTINO
)
