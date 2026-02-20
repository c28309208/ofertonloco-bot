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

                    if not titulo or not link:
                        continue

                    url = link['href'].split("#")[0]
                    url_afiliado = url + "?tracking_id=gioponce11"

                    if url_afiliado in memoria_ram:
                        continue

                    # Precio actual
                    precio_actual_tag = item.find("div", class_="poly-price__current")
                    if not precio_actual_tag:
                        continue
                    fraccion_actual = precio_actual_tag.find("span", class_="andes-money-amount__fraction")
                    if not fraccion_actual:
                        continue
                    precio_ahora_txt = fraccion_actual.get_text(strip=True)

                    # Precio anterior (antes del descuento)
                    precio_anterior_tag = item.find("span", class_=lambda c: c and "andes-money-amount--previous" in c)
                    if not precio_anterior_tag:
                        continue
                    fraccion_anterior = precio_anterior_tag.find("span", class_="andes-money-amount__fraction")
                    if not fraccion_anterior:
                        continue
                    precio_antes_txt = fraccion_anterior.get_text(strip=True)

                    antes = float(precio_antes_txt.replace(",", ""))
                    ahora = float(precio_ahora_txt.replace(",", ""))

                    if antes <= ahora:
                        continue

                    descuento = int((1 - ahora / antes) * 100)

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
