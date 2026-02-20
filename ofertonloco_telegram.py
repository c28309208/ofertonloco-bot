import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
import schedule

BOT_TOKEN = "8593181383:AAFkzs68iwZm9hWx92pEGn9Mk7vwhyKwRS8"
CANAL = "@ofertonloco0911"
ARCHIVO_MEMORIA = "memoria.json"

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

def cargar_memoria():
    try:
        with open(ARCHIVO_MEMORIA, "r") as f:
            return json.load(f)
    except:
        return []

def guardar_memoria(links):
    if len(links) > 1000:
        links = links[-1000:]
    with open(ARCHIVO_MEMORIA, "w") as f:
        json.dump(links, f)

def enviar_telegram(titulo, precio, url_afiliado, img_url):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    texto = (
        "OFERTA\n\n"
        + titulo[:40] + "\n\n"
        + "Precio: $" + precio + " MXN\n\n"
        + "Compra aqui:\n"
        + url_afiliado + "\n\n"
        + "Publicado: " + fecha
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
            print("  -> Error Telegram: " + str(r.json()))
            return False
    except Exception as e:
        print("  -> Error: " + str(e))
        return False

def buscar_y_publicar():
    print("\n" + "=" * 40)
    print("Iniciando: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 40)

    links_publicados = cargar_memoria()
    nuevos_links = []
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

                        if url_afiliado in links_publicados:
                            continue

                        precio_txt = precio.text.strip() if precio else "Ver precio"
                        img_url = imagen['src'] if imagen else None

                        exito = enviar_telegram(titulo.text.strip(), precio_txt, url_afiliado, img_url)
                        if exito:
                            nuevos_links.append(url_afiliado)
                            total += 1
                            time.sleep(3)
                except:
                    continue
        except:
            print("  -> Error")
            continue

    links_publicados.extend(nuevos_links)
    guardar_memoria(links_publicados)

    print("\nPublicadas: " + str(total) + " ofertas nuevas")
    print("Proxima publicacion a las 9am o 9pm")
    print("=" * 40)

print("OfertonLoco Bot iniciado!")
buscar_y_publicar()

schedule.every(1).hours.do(buscar_y_publicar)

print("Esperando... (no cerrar)")
while True:
    schedule.run_pending()
    time.sleep(60)
