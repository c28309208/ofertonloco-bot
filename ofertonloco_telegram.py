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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
memoria_ram = []

DEBUG = True  # Cambia a False para silenciar logs detallados

def log(msg):
    if DEBUG:
        print(msg)

def limpiar_precio(texto):
    """Extrae número limpio de un string de precio."""
    if not texto:
        return None
    limpio = texto.replace("$", "").replace(",", "").replace("\xa0", "").strip()
    try:
        return float(limpio)
    except:
        return None

def extraer_precio_actual(item):
    """Intenta múltiples selectores para el precio actual."""
    # Selector 1: clase fraction (precio entero)
    fraccion = item.find("span", class_=lambda c: c and "price__fraction" in c)
    if fraccion:
        return fraccion.get_text(strip=True)

    # Selector 2: cualquier span con 'fraction'
    fraccion = item.find("span", class_=lambda c: c and "fraction" in c)
    if fraccion:
        return fraccion.get_text(strip=True)

    # Selector 3: data-price o aria-label en el contenedor de precio
    precio_div = item.find(class_=lambda c: c and "price" in c.lower() if c else False)
    if precio_div:
        txt = precio_div.get_text(strip=True)
        if "$" in txt:
            return txt.replace("$", "").split()[0]

    return None

def extraer_precio_original(item):
    """Intenta múltiples selectores para el precio tachado."""
    # Selector 1: etiqueta <s> directa
    s_tag = item.find("s")
    if s_tag:
        return s_tag.get_text(strip=True)

    # Selector 2: clase con 'original' o 'strike'
    orig = item.find(class_=lambda c: c and ("original" in c or "strike" in c or "previous" in c) if c else False)
    if orig:
        return orig.get_text(strip=True)

    return None

def extraer_imagen(item):
    """Intenta múltiples selectores para la imagen."""
    # Selector 1: clase poly-component__picture
    img = item.find("img", class_=lambda c: c and "picture" in c)
    if img:
        src = img.get("data-src") or img.get("src")
        if src and src.startswith("http"):
            return src

    # Selector 2: cualquier img con src http
    for img in item.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and src.startswith("http") and "mlstatic" in src:
            return src

    return None

def extraer_link(item):
    """Extrae el link del producto."""
    # Selector 1: clase poly-component__title
    a = item.find("a", class_=lambda c: c and "title" in c)
    if a and a.get("href"):
        return a["href"]

    # Selector 2: primer <a> con href de MercadoLibre
    for a in item.find_all("a"):
        href = a.get("href", "")
        if "mercadolibre.com.mx" in href or href.startswith("/"):
            return href

    return None

def enviar_telegram(titulo, precio_antes, precio_ahora, descuento, url_afiliado, img_url):
    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    texto = (
        "🔥 OFERTA DEL DIA 🔥\n\n"
        + titulo[:60] + "\n\n"
        + "~~Antes: $" + precio_antes + " MXN~~\n"
        + "💰 AHORA: $" + precio_ahora + " MXN\n"
        + "✅ Ahorras: " + descuento + "%\n\n"
        + "🛒 Compra aqui:\n"
        + url_afiliado + "\n\n"
        + "📅 " + fecha
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
            print("  -> Error Telegram: " + str(r.status_code) + " " + str(r.text[:200]))
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
    debug_primera_cat = True  # Solo muestra debug detallado de la primera categoria

    for i, cat in enumerate(CATEGORIAS):
        print("(" + str(i+1) + "/" + str(len(CATEGORIAS)) + ") " + cat)
        try:
            r = requests.get(
                "https://listado.mercadolibre.com.mx/" + cat,
                headers=headers,
                timeout=15
            )
            if r.status_code != 200:
                print("  -> HTTP " + str(r.status_code))
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Intentar varios selectores para los items
            items = soup.find_all("li", class_=lambda c: c and "ui-search-layout__item" in c and "intervention" not in c)

            if not items:
                # Fallback: buscar cualquier li con producto
                items = soup.find_all("li", class_=lambda c: c and "ui-search-layout__item" in c)

            if debug_primera_cat:
                log("  -> Items encontrados: " + str(len(items)))
                if items:
                    log("  -> Clases del primer item: " + str(items[0].get("class")))
                    # Muestra estructura del primer item para diagnostico
                    log("  -> HTML muestra (primer item, 500 chars): " + str(items[0])[:500])
                debug_primera_cat = False

            for item in items[:15]:
                try:
                    titulo_tag = item.find("h3") or item.find("h2")
                    if not titulo_tag:
                        continue
                    titulo = titulo_tag.get_text(strip=True)

                    url = extraer_link(item)
                    if not url:
                        log("    -> Sin link: " + titulo[:30])
                        continue

                    if not url.startswith("http"):
                        url = "https://www.mercadolibre.com.mx" + url
                    url = url.split("#")[0].split("?")[0]
                    url_afiliado = url + "?tracking_id=gioponce11"

                    if url_afiliado in memoria_ram:
                        continue

                    precio_ahora_txt = extraer_precio_actual(item)
                    precio_antes_txt = extraer_precio_original(item)

                    if not precio_ahora_txt or not precio_antes_txt:
                        log("    -> Sin precios para: " + titulo[:30] + " | actual=" + str(precio_ahora_txt) + " | original=" + str(precio_antes_txt))
                        continue

                    antes = limpiar_precio(precio_antes_txt)
                    ahora = limpiar_precio(precio_ahora_txt)

                    if not antes or not ahora or antes <= ahora:
                        continue

                    descuento = int((1 - ahora / antes) * 100)

                    if descuento < 5:
                        continue

                    img_url = extraer_imagen(item)

                    exito = enviar_telegram(titulo, precio_antes_txt, precio_ahora_txt, str(descuento), url_afiliado, img_url)
                    if exito:
                        memoria_ram.append(url_afiliado)
                        if len(memoria_ram) > 1000:
                            memoria_ram = memoria_ram[-1000:]
                        total += 1
                        time.sleep(3)
                except Exception as e:
                    log("    -> Error item: " + str(e))
                    continue

        except Exception as e:
            print("  -> Error categoria: " + str(e))
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
