import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time
import schedule
import os

tz = pytz.timezone("America/Mexico_City")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = os.environ.get("CANAL")

CATEGORIAS = [
    "celulares", "laptops", "televisores", "audifonos", "tablets",
    "camaras-fotograficas", "consolas-videojuegos", "smartwatches",
    "impresoras", "monitores", "teclados-mouse", "bocinas",
    "proyectores", "memorias-usb", "discos-duros", "routers",
    "drones", "camaras-seguridad", "accesorios-celulares",
    "electrodomesticos", "aires-acondicionados", "lavadoras",
    "refrigeradores", "microondas", "aspiradoras", "licuadoras",
    "cafeteras", "freidoras-aire", "ventiladores", "calentadores",
    "muebles", "colchones", "almohadas", "cortinas",
    "lampara", "organizadores",
    "zapatos", "ropa", "perfumes", "maquillaje", "bolsas",
    "relojes", "lentes", "ropa-deportiva", "zapatos-deportivos",
    "joyeria", "vitaminas-suplementos", "aparatos-medicos",
    "cuidado-piel", "cuidado-cabello", "afeitadoras",
    "bicicletas", "patinetas", "pesas-gimnasio", "tenis",
    "equipos-futbol", "albercas-inflables", "campismo",
    "accesorios-autos", "llantas", "audio-autos", "herramientas-autos",
    "herramientas", "plantas", "semillas", "mangueras",
    "pinturas", "cerraduras", "escaleras",
    "juguetes", "carriolas", "cunas", "ropa-bebe",
    "sillas-auto-bebe", "juegos-jardin",
    "perros", "gatos", "accesorios-mascotas", "alimento-mascotas",
    "libros", "instrumentos-musicales", "arte-manualidades",
    "videojuegos", "figuras-coleccion",
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
memoria_ram = []

def extraer_precio_original(item):
    # Intento 1: etiqueta <s> clasica
    s_tag = item.find("s")
    if s_tag:
        return s_tag.get_text(strip=True)

    # Intento 2: clase con 'original' o 'strike' o 'previous'
    for tag in item.find_all(True):
        clases = " ".join(tag.get("class", []))
        if any(x in clases for x in ["original", "strike", "previous", "before"]):
            txt = tag.get_text(strip=True)
            if "$" in txt or any(c.isdigit() for c in txt):
                return txt

    # Intento 3: buscar el porcentaje de descuento y calcular precio original
    return None

def extraer_descuento_directo(item):
    # MercadoLibre a veces muestra "X% OFF" directamente
    for tag in item.find_all(True):
        clases = " ".join(tag.get("class", []))
        if "discount" in clases or "off" in clases.lower():
            txt = tag.get_text(strip=True)
            if "%" in txt:
                try:
                    pct = int(''.join(filter(str.isdigit, txt.split("%")[0])))
                    return pct
                except:
                    pass
    return None

def enviar_telegram(titulo, precio_antes, precio_ahora, descuento, url_afiliado, img_url):
    if not titulo or not precio_antes or not precio_ahora or not descuento or not url_afiliado:
        return False
    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    texto = (
        "OFERTA DEL DIA\n\n"
        + str(titulo)[:50] + "\n\n"
        + "Antes: $" + str(precio_antes) + " MXN\n"
        + "AHORA: $" + str(precio_ahora) + " MXN\n"
        + "Ahorras: " + str(descuento) + "%\n\n"
        + "Compra aqui:\n"
        + str(url_afiliado) + "\n\n"
        + fecha
    )
    try:
        if img_url:
            r = requests.post(
                "https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto",
                data={"chat_id": CANAL, "caption": texto, "photo": img_url},
                timeout=15
            )
        else:
            r = requests.post(
                "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                data={"chat_id": CANAL, "text": texto},
                timeout=15
            )
        if r.status_code == 200:
            print("  -> Publicada: " + str(titulo)[:40])
            return True
        else:
            print("  -> Error Telegram: " + str(r.json()))
            return False
    except Exception as e:
        print("  -> Error: " + str(e))
        return False

def buscar_y_publicar():
    global memoria_ram
    print("\n" + "=" * 40)
    print("Iniciando: " + datetime.now(tz).strftime("%d/%m/%Y %H:%M"))
    print("=" * 40)

    total = 0

    for i, cat in enumerate(CATEGORIAS):
        print("(" + str(i+1) + "/" + str(len(CATEGORIAS)) + ") " + cat)
        try:
            r = requests.get(
                "https://listado.mercadolibre.com.mx/" + cat,
                headers=headers,
                timeout=10
            )
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all("li", class_=lambda c: c and "ui-search-layout__item" in c and "intervention" not in c)

            for item in items[:15]:
                try:
                    titulo = item.find("h3")
                    link = item.find("a", class_="poly-component__title")
                    imagen = item.find("img", class_="poly-component__picture")
                    precios = item.find_all("span", class_=lambda c: c and "fraction" in c)

                    if not titulo or not link:
                        continue

                    url = link['href'].split("#")[0]
                    url_afiliado = url + "?tracking_id=gioponce11"

                    if url_afiliado in memoria_ram:
                        continue

                    precio_ahora_txt = precios[0].text.strip() if precios else None
                    if not precio_ahora_txt:
                        continue

                    # Intenta obtener precio original
                    precio_original_tag = extraer_precio_original(item)
                    descuento_directo = extraer_descuento_directo(item)

                    if precio_original_tag:
                        precio_antes_txt = precio_original_tag.replace("$", "").replace(",", "").strip()
                        try:
                            antes = float(precio_antes_txt.replace(",", ""))
                            ahora = float(precio_ahora_txt.replace(",", ""))
                            if antes <= ahora:
                                continue
                            descuento = int((1 - ahora / antes) * 100)
                        except:
                            continue
                    elif descuento_directo:
                        # Usa el % que muestra MercadoLibre directamente
                        descuento = descuento_directo
                        ahora = float(precio_ahora_txt.replace(",", ""))
                        antes = ahora / (1 - descuento / 100)
                        precio_antes_txt = str(int(antes))
                    else:
                        continue

                    if descuento < 5:
                        continue

                    img_url = imagen['src'] if imagen else None

                    exito = enviar_telegram(titulo.text.strip(), precio_antes_txt, precio_ahora_txt, str(descuento), url_afiliado, img_url)
                    if exito:
                        memoria_ram.append(url_afiliado)
                        if len(memoria_ram) > 1000:
                            memoria_ram = memoria_ram[-1000:]
                        total += 1
                        time.sleep(3)
                except:
                    continue
        except:
            print("  -> Error")
            continue

    print("\nPublicadas: " + str(total) + " ofertas con descuento real")
    print("Proxima en 1 hora")
    print("=" * 40)

print("OfertonLoco Bot iniciado!")
buscar_y_publicar()
schedule.every(1).hours.do(buscar_y_publicar)

print("Esperando...")
while True:
    schedule.run_pending()
    time.sleep(60)
