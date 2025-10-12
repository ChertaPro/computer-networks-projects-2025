import sys

def contar_caracteres_sin_espacio(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
        # Filtramos todo lo que no sea espacio ni salto de línea
        sin_espacios = [c for c in contenido if not c.isspace()]
        print(f"Cantidad de caracteres sin espacio: {len(sin_espacios)}")
    except FileNotFoundError:
        print(f"Error: el archivo '{ruta}' no existe.")
    except Exception as e:
        print(f"Ocurrió un error: {e}")

if __name__ == "__main__":
    # Puedes pasar el archivo por argumento o te lo pide por consola
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
    else:
        archivo = input("Introduce la ruta del archivo: ")
    contar_caracteres_sin_espacio(archivo)
