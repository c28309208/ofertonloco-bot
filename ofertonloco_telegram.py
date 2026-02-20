import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
import time

# ============================================================
# CONFIGURACION
# ============================================================
BOT_TOKEN = "8593181383:AAFkzs68iwZm9hWx92pEGn9Mk7vwhyKwRS8"
CANAL = "@ofertonloco0911"
ARCHIVO_MEMORIA = "precios_guardados.json"   # ahora guarda PRECIOS, no links
INTERVALO_MINUTOS = 15

CATEGORIAS = [
    "celulares", "laptops", "televisores", "audifonos", "tablets",
    "camaras-fotograficas", "consolas-videojuegos", "smartwatches",
    "herramientas", "electrodomesticos", "aires-acondicionados",
    "lavadoras", "refrigeradores", "microondas", "aspiradoras",
    "muebles", "colchones", "zapatos", "ropa", "perfumes",
    "maquillaje", "vitaminas-suplementos", "bicicletas", "patinetas",
    "juguetes", "libros", "impresoras", "monitores", "teclados-mouse", "bocinas",
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ============================================================
# MEMORIA DE PRECIOS
# Estructura: { "url": { "precio": 1234.0, "titulo": "...", "imagen": "..." } }
# ============================================================
def cargar_precios():
    if os.path.exists(ARCHIVO_MEMORIA):
        with open(ARCHIVO_MEMORIA, "r") as f:
            return json.load(f)
    return {}

def guardar_precios(datos):
    # Limitar a 2000 productos para no crecer infinito
    if len(datos) > 2000:
        claves = list(datos.keys())[-2000:]
        datos = {k: datos[k] for k in claves}
    with open(ARCHIVO_MEMORIA, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def limpiar_precio(texto):
    """Convierte '1,299' o '1299' a float 1299.0"""
    try:
        limpio = texto.replace(",", "").replace("$", "").replace(" ", "").strip()
        return float(limpio)
    except:
        return None

# ============================================================
# TELEGRAM
# ============================================================
def enviar_alerta_bajada(imagen_url, titulo, precio_anterior, precio_actual, url_afiliado):
    porcentaje = round((1 - precio_actual / precio_anterior) * 100, 1)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    texto = (
        "BAJADA DE PRECIO DETECTADA\n\n"
        + titulo[:60] + "\n\n"
        + "Antes: $" + "{:,.0f}".format(precio_anterior) + " MXN\n"
        + "Ahora: $" + "{:,.0f}".format(precio_actual) + " MXN\n"
        + "Ahorro: " + str(porcentaje) + "% menos\n\n"
        + "Compra aqui:\n"
        + url_afiliado + "\n\n"
        + "Detectado: " + fecha
    )
    try:
        if imagen_url:
            r = requests.post(
                "https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto",
                data={"chat_id": CANAL, "caption": texto, "photo": imagen_url},
                timeout=15
            )
        else:
            r = requests.post(
                "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                data={"chat_id": CANAL, "text": texto},
                timeout=15
            )
        return r.status_code == 200
    except:
        return False

# ============================================================
# BUSCAR Y DETECTAR BAJADAS
# ============================================================
def revisar_precios():
    print("\n" + "=" * 45)
    print("Revisando precios: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 45)

    precios_guardados = cargar_precios()
    total_bajadas = 0
    total_revisados = 0

    for i, cat in enumerate(CATEGORIAS):
        print("(" + str(i+1) + "/" + str(len(CATEGORIAS)) + ") " + cat)
        try:
            r = requests.get(
                "https://listado.mercadolibre.com.mx/" + cat,
                headers=headers,
                timeout=10
            )
            if r.status_code != 200:
                print("  -> Sin respuesta")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(
                "li",
                class_=lambda c: c and "ui-search-layout__item" in c and "intervention" not in c
            )

            for item in items[:8]:  # revisar los primeros 8 de cada categoria
                try:
                    titulo_tag = item.find("h3")
                    precio_tag = item.find("span", class_=lambda c: c and "fraction" in c)
                    link_tag = item.find("a", class_="poly-component__title")
                    imagen_tag = item.find("img", class_="poly-component__picture")

                    if not (titulo_tag and link_tag and precio_tag):
                        continue

                    url = link_tag['href'].split("#")[0]
                    url_afiliado = url + "?tracking_id=gioponce11"
                    precio_actual = limpiar_precio(precio_tag.text)
                    titulo = titulo_tag.text.strip()
                    img_url = imagen_tag['src'] if imagen_tag else None

                    if precio_actual is None:
                        continue

                    total_revisados += 1

                    if url_afiliado in precios_guardados:
                        precio_anterior = precios_guardados[url_afiliado]["precio"]

                        # Solo publicar si bajó al menos 5%
                        if precio_actual < precio_anterior * 0.95:
                            print("  BAJADA: " + titulo[:40])
                            print("    " + str(precio_anterior) + " -> " + str(precio_actual))
                            exito = enviar_alerta_bajada(img_url, titulo, precio_anterior, precio_actual, url_afiliado)
                            if exito:
                                total_bajadas += 1
                                time.sleep(3)  # pausa entre mensajes

                    # Actualizar precio en memoria (siempre)
                    precios_guardados[url_afiliado] = {
                        "precio": precio_actual,
                        "titulo": titulo,
                        "imagen": img_url or "",
                        "ultima_vez": datetime.now().strftime("%d/%m/%Y %H:%M")
                    }

                except:
                    continue

        except Exception as e:
            print("  -> Error en categoria " + cat + ": " + str(e))
            continue

    guardar_precios(precios_guardados)

    print("\n" + "=" * 45)
    print("Revisados: " + str(total_revisados) + " productos")
    print("Bajadas detectadas: " + str(total_bajadas))
    print("Proxima revision en " + str(INTERVALO_MINUTOS) + " minutos")
    print("=" * 45)

# ============================================================
# LOOP PRINCIPAL - corre para siempre cada 15 minutos
# ============================================================
print("OfertonLoco Bot iniciado!")
print("Canal: " + CANAL)
print("Modo: Deteccion de bajadas de precio")
print("Intervalo: cada " + str(INTERVALO_MINUTOS) + " minutos")
print("Umbral: publica solo si el precio bajo 5% o mas\n")

while True:
    revisar_precios()
    print("Esperando " + str(INTERVALO_MINUTOS) + " minutos...")
    time.sleep(INTERVALO_MINUTOS * 60)
