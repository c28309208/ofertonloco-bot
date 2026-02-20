import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
tz = pytz.timezone("America/Mexico_City")
import time
import schedule

BOT_TOKEN = "8593181383:AAFkzs68iwZm9hWx92pEGn9Mk7vwhyKwRS8"
CANAL = "@ofertonloco0911"

CATEGORIAS = [
    # Tecnologia
    "celulares", "laptops", "televisores", "audifonos", "tablets",
    "camaras-fotograficas", "consolas-videojuegos", "smartwatches",
    "impresoras", "monitores", "teclados-mouse", "bocinas",
    "proyectores", "memorias-usb", "discos-duros", "routers",
    "drones", "camaras-seguridad", "accesorios-celulares",
    
    # Hogar
    "electrodomesticos", "aires-acondicionados", "lavadoras",
    "refrigeradores", "microondas", "aspiradoras", "licuadoras",
    "cafeteras", "freidoras-aire", "ventiladores", "calentadores",
    "muebles", "colchones", "almohadas", "cortinas",
    "lampara", "organizadores",

    # Moda
    "zapatos", "ropa", "perfumes", "maquillaje", "bolsas",
    "relojes", "lentes", "ropa-deportiva", "zapatos-deportivos",
    "joyeria",

    # Salud y belleza
    "vitaminas-suplementos", "aparatos-medicos", "cuidado-piel",
    "cuidado-cabello", "afeitadoras",

    # Deportes
    "bicicletas", "patinetas", "pesas-gimnasio", "tenis",
    "equipos-futbol", "albercas-inflables", "campismo",

    # Autos
    "accesorios-autos", "llantas", "audio-autos", "herramientas-autos",

    # Hogar y jardin
    "herramientas", "plantas", "semillas", "mangueras",
    "pinturas", "cerraduras", "escaleras",

    # Bebes y ninos
    "juguetes", "carriolas", "cunas", "ropa-bebe",
    "sillas-auto-bebe", "juegos-jardin",

    # Mascotas
    "perros", "gatos", "accesorios-mascotas", "alimento-mascotas",

    # Otros
    "libros", "instrumentos-musicales", "arte-manualidades",
    "videojuegos", "figuras-coleccion",
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

memoria_ram = []

def enviar_telegram(titulo, precio, url_afiliado, img_url):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    texto = (
        "OFERTA\n\n"
        + titulo[:40] + "\n\n"
        + "Precio: $" + precio + " MXN\n\n"
        + "Compra aqui:\n"
        + url_afiliado + "\n\n"
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
            print("  -> Publicada: " + titulo[:40])
            return True
        else:
            print("  -> Error: " + str(r.json()))
            return False
    except Exception as e:
        print("  -> Error: " + str(e))
        return False

def buscar_y_publicar():
    global memoria_ram
    print("\n" + "=" * 40)
    print("Iniciando: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
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

            for item in items[:5]:
                try:
                    titulo = item.find("h3")
                    precio = item.find("span", class_=lambda c: c and "fraction" in c)
                    link = item.find("a", class_="poly-component__title")
                    imagen = item.find("img", class_="poly-component__picture")

                    if titulo and link:
                        url = link['href'].split("#")[0]
                        url_afiliado = url + "?tracking_id=gioponce11"

                        if url_afiliado in memoria_ram:
                            continue

                        precio_txt = precio.text.strip() if precio else "Ver precio"
                        img_url = imagen['src'] if imagen else None

                        exito = enviar_telegram(titulo.text.strip(), precio_txt, url_afiliado, img_url)
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

    print("\nPublicadas: " + str(total) + " ofertas nuevas")
    print("Proxima en 1 hora")
    print("=" * 40)

print("OfertonLoco Bot iniciado!")
buscar_y_publicar()
schedule.every(1).hours.do(buscar_y_publicar)

print("Esperando... (no cerrar)")
while True:
    schedule.run_pending()
    time.sleep(60)
