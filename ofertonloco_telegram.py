import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time
import schedule
import re
import sqlite3
import random
import string
import threading

# ─────────────────────────────────────────
# CONFIGURACIÓN — EDITA SOLO ESTA SECCIÓN
# ─────────────────────────────────────────
tz = pytz.timezone("America/Mexico_City")

BOT_TOKEN      = "8593181383:AAFkzs68iwZm9hWx92pEGn9Mk7vwhyKwRS8"
CANAL_TELEGRAM = "@ofertonloco0911"
CANAL_ID       = "@ofertonloco0911"

FB_PAGE_TOKEN  = "EAAUj7vuVOtgBQ4w2pw2UltZANKJJpxDz5T37OgqGsrMBJHEgBZCxivd3K4Mpttv6e7EYYgM8kNZBoYcmWZCYbabpZBucMXima4rd1srhD7FkF5GDuLWK6SGV0XO4wNLBZC7ZBWppA1hUjBIxU0z5SRiaTtlkZBWUmQZCksBZAPU3eNUYRRVycSca4FMIWZBzlkdZCjnay7LEYMO6"
FB_PAGE_ID     = "1044747028730801"
FB_ENABLED     = True

# ─────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────
DB_FILE = "rifa.db"

def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS participantes (
            user_id       TEXT PRIMARY KEY,
            username      TEXT,
            boletos       INTEGER DEFAULT 0,
            suscrito      INTEGER DEFAULT 0,
            invitados     INTEGER DEFAULT 0,
            fb_compartido INTEGER DEFAULT 0,
            fecha         TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS boletos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  TEXT NOT NULL,
            username TEXT,
            codigo   TEXT NOT NULL,
            motivo   TEXT,
            fecha    TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invitaciones (
            invitado_id  TEXT PRIMARY KEY,
            invitador_id TEXT,
            fecha        TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rifas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            premio TEXT NOT NULL,
            activa INTEGER DEFAULT 1,
            fecha  TEXT
        )
    """)
    con.commit()
    con.close()

def generar_codigo():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def dar_boleto(user_id, username, motivo):
    codigo = generar_codigo()
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO boletos (user_id, username, codigo, motivo, fecha) VALUES (?,?,?,?,?)",
        (str(user_id), username, codigo, motivo, datetime.now(tz).strftime("%d/%m/%Y %H:%M"))
    )
    cur.execute("""
        INSERT INTO participantes (user_id, username, boletos, fecha)
        VALUES (?,?,1,?)
        ON CONFLICT(user_id) DO UPDATE SET boletos = boletos + 1, username = excluded.username
    """, (str(user_id), username, datetime.now(tz).strftime("%d/%m/%Y %H:%M")))
    con.commit()
    con.close()
    return codigo

def verificar_suscripcion(user_id):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
            params={"chat_id": CANAL_ID, "user_id": user_id},
            timeout=10
        )
        if r.status_code == 200:
            status = r.json().get("result", {}).get("status", "")
            return status in ["member", "administrator", "creator"]
    except:
        pass
    return False

def ya_suscrito_registrado(user_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT suscrito FROM participantes WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    con.close()
    return row and row[0] == 1

def marcar_suscrito(user_id, username):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO participantes (user_id, username, suscrito, boletos, fecha)
        VALUES (?,?,1,0,?)
        ON CONFLICT(user_id) DO UPDATE SET suscrito = 1, username = excluded.username
    """, (str(user_id), username, datetime.now(tz).strftime("%d/%m/%Y %H:%M")))
    con.commit()
    con.close()

def ya_compartio_fb(user_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT fb_compartido FROM participantes WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    con.close()
    return row and row[0] == 1

def marcar_fb_compartido(user_id, username):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO participantes (user_id, username, fb_compartido, boletos, fecha)
        VALUES (?,?,1,0,?)
        ON CONFLICT(user_id) DO UPDATE SET fb_compartido = 1
    """, (str(user_id), username, datetime.now(tz).strftime("%d/%m/%Y %H:%M")))
    con.commit()
    con.close()

def registrar_invitacion(invitado_id, invitador_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT invitador_id FROM invitaciones WHERE invitado_id = ?", (str(invitado_id),))
    if cur.fetchone():
        con.close()
        return False
    cur.execute(
        "INSERT INTO invitaciones (invitado_id, invitador_id, fecha) VALUES (?,?,?)",
        (str(invitado_id), str(invitador_id), datetime.now(tz).strftime("%d/%m/%Y %H:%M"))
    )
    cur.execute("""
        INSERT INTO participantes (user_id, username, invitados, boletos, fecha)
        VALUES (?,?,1,0,?)
        ON CONFLICT(user_id) DO UPDATE SET invitados = invitados + 1
    """, (str(invitador_id), "", datetime.now(tz).strftime("%d/%m/%Y %H:%M")))
    con.commit()
    con.close()
    return True

def mis_boletos(user_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT codigo, motivo FROM boletos WHERE user_id = ?", (str(user_id),))
    rows = cur.fetchall()
    con.close()
    return rows

def realizar_sorteo():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT premio FROM rifas WHERE activa = 1 ORDER BY id DESC LIMIT 1")
    rifa = cur.fetchone()
    if not rifa:
        con.close()
        return None, None, 0
    cur.execute("SELECT user_id, username, codigo FROM boletos")
    todos = cur.fetchall()
    con.close()
    if not todos:
        return rifa[0], None, 0
    ganador = random.choice(todos)
    return rifa[0], ganador, len(todos)

def crear_rifa(premio):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("UPDATE rifas SET activa = 0")
    cur.execute(
        "INSERT INTO rifas (premio, activa, fecha) VALUES (?,1,?)",
        (premio, datetime.now(tz).strftime("%d/%m/%Y %H:%M"))
    )
    cur.execute("DELETE FROM boletos")
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM invitaciones")
    con.commit()
    con.close()

def enviar_msg(chat_id, texto):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=10
        )
    except:
        pass

# ─────────────────────────────────────────
# CATEGORÍAS
# ─────────────────────────────────────────
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

# ─────────────────────────────────────────
# ESTADO DE FACEBOOK (para detectar token caído)
# ─────────────────────────────────────────
fb_token_valido = True  # Se pone en False si el token falla

def acortar_url(url):
    try:
        r = requests.get(
            f"https://tinyurl.com/api-create.php?url={url}",
            timeout=10
        )
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except:
        pass
    return url  # Si falla, usa la URL original

def limpiar_url(href):
    if "mercadolibre.com.mx/p/" in href or "mercadolibre.com.mx/" in href:
        match = re.search(r'(https://www\.mercadolibre\.com\.mx/[^\s?#&]+)', href)
        if match:
            return match.group(1)
    if "click1.mercadolibre" in href:
        match = re.search(r'(https://www\.mercadolibre\.com\.mx/[^&"]+)', href)
        if match:
            return match.group(1)
    return href.split("#")[0].split("?")[0]

# ─────────────────────────────────────────
# PUBLICAR EN TELEGRAM
# ─────────────────────────────────────────
def enviar_telegram(titulo, precio_antes, precio_ahora, descuento, url_afiliado, url_visible, img_url):
    if not all([titulo, precio_antes, precio_ahora, descuento, url_afiliado]):
        return False
    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    texto = (
        "🔥 OFERTA DEL DIA 🔥\n\n"
        + str(titulo)[:50] + "\n\n"
        + "💸 Antes: $" + str(precio_antes) + " MXN\n"
        + "✅ AHORA: $" + str(precio_ahora) + " MXN\n"
        + "🎯 Ahorras: " + str(descuento) + "%\n\n"
        + "🛒 Compra aqui:\n" + str(url_visible) + "\n\n"
        + "🎟️ GANA BOLETOS PARA LA RIFA:\n"
        + "1️⃣ Suscribete al canal " + CANAL_TELEGRAM + "\n"
        + "2️⃣ Escribe /rifa a @Ofertonloco_bot\n"
        + "3️⃣ Invita amigos y gana mas boletos\n\n"
        + fecha
    )
    try:
        if img_url:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CANAL_TELEGRAM, "caption": texto, "photo": img_url},
                timeout=15
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CANAL_TELEGRAM, "text": texto},
                timeout=15
            )
        ok = r.status_code == 200
        if ok:
            print(f"  [Telegram] ✓ {titulo[:40]}")
        else:
            print(f"  [Telegram] Error: {r.json()}")
        return ok
    except Exception as e:
        print(f"  [Telegram] Excepción: {e}")
        return False

# ─────────────────────────────────────────
# PUBLICAR EN FACEBOOK  ← CORREGIDO
# ─────────────────────────────────────────
def enviar_facebook(titulo, precio_antes, precio_ahora, descuento, url_afiliado, url_visible, img_url):
    global fb_token_valido

    if not FB_ENABLED:
        return False

    # Si el token ya falló, no intentar más hasta reiniciar el bot
    if not fb_token_valido:
        return False

    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    mensaje = (
        "🔥 OFERTA DEL DIA 🔥\n\n"
        + str(titulo)[:80] + "\n\n"
        + f"💸 Antes: ${precio_antes} MXN\n"
        + f"✅ AHORA: ${precio_ahora} MXN\n"
        + f"🎯 Ahorras: {descuento}%\n\n"
        + f"🛒 Compra aqui: {url_visible}\n\n"   # URL limpia visible para el usuario
        + "🎟️ PARTICIPA EN LA RIFA GRATIS:\n"
        + "1️⃣ Comparte esta publicacion (1 boleto)\n"
        + "2️⃣ Suscribete al canal: t.me/ofertonloco0911 (1 boleto)\n"
        + "3️⃣ Invita amigos al bot (1 boleto por amigo)\n"
        + "👉 Entra a t.me/Ofertonloco_bot y escribe /rifa\n\n"
        + fecha
    )

    try:
        endpoint = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"

        payload = {
            "access_token": FB_PAGE_TOKEN,
            "message": mensaje,
            "link": url_afiliado,   # tracking oculto aquí, solo FB lo ve para el preview
        }

        r = requests.post(endpoint, data=payload, timeout=15)
        data = r.json()

        if r.status_code == 200 and "id" in data:
            print(f"  [Facebook] ✓ {titulo[:40]}")
            return True

        # ── Manejo de errores específicos ─────────────────────────────────
        error = data.get("error", {})
        code  = error.get("code", 0)
        msg   = error.get("message", "")

        if code == 190:
            # Token expirado o sesión cerrada
            fb_token_valido = False
            print("  [Facebook] ❌ TOKEN EXPIRADO — Renovar en developers.facebook.com/tools/explorer")
            print("  [Facebook] ⚠️  Facebook desactivado hasta reiniciar el bot con token nuevo")
            # Notificar por Telegram al admin
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={
                        "chat_id": BOT_TOKEN.split(":")[0],  # ID del creador del bot
                        "text": "⚠️ *Token de Facebook expirado*\nRenúevalo en:\nhttps://developers.facebook.com/tools/explorer\nLuego reinicia el bot.",
                        "parse_mode": "Markdown"
                    },
                    timeout=5
                )
            except:
                pass
            return False

        elif code == 200:
            # Permiso denegado — el token no tiene pages_manage_posts
            fb_token_valido = False
            print("  [Facebook] ❌ PERMISOS INCORRECTOS en el token")
            print("  [Facebook] → Al generar el token en Graph Explorer asegúrate de activar:")
            print("               ✅ pages_manage_posts")
            print("               ✅ pages_read_engagement")
            print("  [Facebook] ⚠️  Facebook desactivado hasta reiniciar el bot con token correcto")
            return False

        elif code == 368 or code == 32:
            # Rate limit de Facebook
            print(f"  [Facebook] ⏳ Rate limit — esperando 5 minutos...")
            time.sleep(300)
            return False

        else:
            print(f"  [Facebook] Error ({code}): {msg}")
            return False

    except Exception as e:
        print(f"  [Facebook] Excepción: {e}")
        return False

# ─────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────
def buscar_y_publicar():
    global memoria_ram
    print("\n" + "=" * 45)
    print("Iniciando: " + datetime.now(tz).strftime("%d/%m/%Y %H:%M"))
    print("=" * 45)
    total = 0

    for i, cat in enumerate(CATEGORIAS):
        print(f"({i+1}/{len(CATEGORIAS)}) {cat}")
        try:
            r = requests.get(
                f"https://listado.mercadolibre.com.mx/{cat}",
                headers=headers, timeout=10
            )
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(
                "li",
                class_=lambda c: c and "ui-search-layout__item" in c and "intervention" not in c
            )

            candidatos = []
            for item in items[:20]:
                try:
                    titulo = item.find("h3")
                    link   = item.find("a", class_="poly-component__title")
                    imagen = item.find("img", class_="poly-component__picture")
                    if not titulo or not link:
                        continue

                    url          = limpiar_url(link['href'])
                    url_afiliado = url + "?tracking_id=gioponce11"
                    url_visible  = url  # URL limpia sin tracking para mostrar
                    if url_afiliado in memoria_ram:
                        continue

                    precio_actual_tag = item.find("div", class_="poly-price__current")
                    if not precio_actual_tag:
                        continue
                    fraccion_actual = precio_actual_tag.find("span", class_="andes-money-amount__fraction")
                    if not fraccion_actual:
                        continue
                    precio_ahora_txt = fraccion_actual.get_text(strip=True)

                    precio_anterior_tag = item.find("s", class_=lambda c: c and "andes-money-amount--previous" in c)
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
                    candidatos.append({
                        "titulo":       titulo.text.strip(),
                        "precio_antes": precio_antes_txt,
                        "precio_ahora": precio_ahora_txt,
                        "ahora_num":    ahora,
                        "descuento":    str(descuento),
                        "url_afiliado": url_afiliado,
                        "url_visible":  url_visible,
                        "img_url":      img_url,
                    })
                except:
                    continue

            candidatos.sort(key=lambda x: x["ahora_num"])
            for p in candidatos[:2]:
                ok_tg = enviar_telegram(p["titulo"], p["precio_antes"], p["precio_ahora"],
                                        p["descuento"], p["url_afiliado"], p["url_visible"], p["img_url"])
                ok_fb = enviar_facebook(p["titulo"], p["precio_antes"], p["precio_ahora"],
                                        p["descuento"], p["url_afiliado"], p["url_visible"], p["img_url"])
                if ok_tg or ok_fb:
                    memoria_ram.append(p["url_afiliado"])
                    if len(memoria_ram) > 2000:
                        memoria_ram = memoria_ram[-2000:]
                    total += 1
                time.sleep(30)

        except Exception as e:
            print(f"  -> Error: {e}")
            continue

    print(f"\n✅ Publicadas: {total} ofertas")
    print("Próxima revisión en 2 horas")
    print("=" * 45)

# ─────────────────────────────────────────
# BOT TELEGRAM — RIFA
# ─────────────────────────────────────────
ultimo_update = 0

def procesar_updates_rifa():
    global ultimo_update
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": ultimo_update + 1, "timeout": 5},
            timeout=10
        )
        if r.status_code != 200:
            return

        for upd in r.json().get("result", []):
            ultimo_update = upd["update_id"]
            msg       = upd.get("message", {})
            texto_msg = msg.get("text", "")
            user      = msg.get("from", {})
            user_id   = user.get("id")
            uname     = user.get("username") or user.get("first_name", "Usuario")
            chat_id   = msg.get("chat", {}).get("id")

            if not texto_msg or not user_id:
                continue

            if texto_msg.strip() == "/rifa":
                if not verificar_suscripcion(user_id):
                    enviar_msg(chat_id,
                        "⚠️ *Primero debes suscribirte al canal*\n\n"
                        f"👉 {CANAL_TELEGRAM}\n\n"
                        "Cuando te suscribas escribe /rifa de nuevo\n"
                        "y recibirás tu primer boleto gratis 🎟️"
                    )
                    continue

                boleto_nuevo = ""
                if not ya_suscrito_registrado(user_id):
                    marcar_suscrito(user_id, uname)
                    codigo = dar_boleto(user_id, uname, "suscripcion al canal")
                    boleto_nuevo = f"\n\n🎟️ *Boleto por suscripción: `{codigo}`*"

                boletos = mis_boletos(user_id)
                link_inv = f"https://t.me/Ofertonloco_bot?start=inv_{user_id}"

                enviar_msg(chat_id,
                    f"🎉 *Hola {uname}!*{boleto_nuevo}\n\n"
                    f"🎟️ Tienes *{len(boletos)} boleto(s)* acumulados\n\n"
                    "*Como ganar mas boletos:*\n"
                    f"👥 Invita amigos con tu link personal:\n`{link_inv}`\n"
                    "_(1 boleto por cada amigo que entre)_\n\n"
                    "📘 Comparte en Facebook y escribe /yocomparti\n"
                    "_(1 boleto extra, solo 1 vez)_\n\n"
                    "*Comandos disponibles:*\n"
                    "/misboletos — ver todos tus boletos\n"
                    "/yocomparti — reclamar boleto por FB\n"
                )

            elif texto_msg.startswith("/start inv_"):
                invitador_id = texto_msg.replace("/start inv_", "").strip()
                if invitador_id and invitador_id != str(user_id):
                    es_nuevo = registrar_invitacion(user_id, invitador_id)
                    if es_nuevo:
                        con = sqlite3.connect(DB_FILE)
                        cur = con.cursor()
                        cur.execute("SELECT username FROM participantes WHERE user_id = ?", (invitador_id,))
                        row = cur.fetchone()
                        con.close()
                        inv_uname = row[0] if row else "Usuario"
                        codigo = dar_boleto(invitador_id, inv_uname, f"invito a {uname}")
                        enviar_msg(invitador_id,
                            f"🎟️ *Nuevo boleto ganado!*\n"
                            f"{uname} se unio con tu link de invitacion\n"
                            f"Tu nuevo boleto: `{codigo}`"
                        )
                enviar_msg(chat_id,
                    f"👋 *Bienvenido {uname}!*\n\n"
                    "Escribe /rifa para participar en el sorteo\n"
                    "y obtener tus boletos 🎟️"
                )

            elif texto_msg.strip() == "/start":
                suscrito = verificar_suscripcion(user_id)
                if suscrito:
                    boleto_nuevo = ""
                    if not ya_suscrito_registrado(user_id):
                        marcar_suscrito(user_id, uname)
                        codigo = dar_boleto(user_id, uname, "suscripcion al canal")
                        boleto_nuevo = f"\n\n🎟️ *Boleto gratis por estar suscrito: `{codigo}`*"

                    boletos = mis_boletos(user_id)
                    link_inv = f"https://t.me/Ofertonloco_bot?start=inv_{user_id}"

                    enviar_msg(chat_id,
                        f"👋 *Hola {uname}! Bienvenido a OfertonLoco* 🎉{boleto_nuevo}\n\n"
                        f"🎟️ Tienes *{len(boletos)} boleto(s)* acumulados\n\n"
                        "*Como ganar mas boletos:*\n"
                        f"👥 Comparte tu link personal:\n`{link_inv}`\n"
                        "_(1 boleto por cada amigo que entre)_\n\n"
                        "📘 Comparte en Facebook y escribe /yocomparti\n"
                        "_(1 boleto extra)_\n\n"
                        "*Comandos:*\n"
                        "/rifa — ver tus boletos y link de invitacion\n"
                        "/misboletos — lista de todos tus boletos\n"
                        "/yocomparti — boleto por compartir en Facebook\n"
                    )
                else:
                    enviar_msg(chat_id,
                        f"👋 *Hola {uname}! Bienvenido a OfertonLoco* 🎉\n\n"
                        "Aqui publicamos las *mejores ofertas* de MercadoLibre\n"
                        "y sorteamos premios entre nuestra comunidad 🏆\n\n"
                        "⚠️ *Para participar en la rifa primero debes:*\n\n"
                        f"👉 Suscribirte al canal: {CANAL_TELEGRAM}\n\n"
                        "Una vez suscrito regresa aqui y escribe /rifa\n"
                        "para recibir tu primer boleto gratis 🎟️"
                    )

            elif texto_msg.strip() == "/misboletos":
                boletos = mis_boletos(user_id)
                if not boletos:
                    enviar_msg(chat_id,
                        "No tienes boletos aun.\n"
                        "Escribe /rifa para empezar a participar 🎟️"
                    )
                else:
                    lista = "\n".join([f"🎟️ `{b[0]}` — _{b[1]}_" for b in boletos])
                    enviar_msg(chat_id,
                        f"*Tus {len(boletos)} boleto(s):*\n\n{lista}\n\n"
                        "Mucha suerte en el sorteo! 🍀"
                    )

            elif texto_msg.strip() == "/yocomparti":
                if ya_compartio_fb(user_id):
                    enviar_msg(chat_id,
                        "Ya recibiste tu boleto por compartir en Facebook 😊\n"
                        "Escribe /misboletos para ver todos tus boletos."
                    )
                else:
                    enviar_msg(chat_id,
                        "📘 *Para ganar tu boleto por compartir:*\n\n"
                        "1️⃣ Visita nuestra página de Facebook:\n"
                        "👉 https://www.facebook.com/profile.php?id=1044747028730801\n\n"
                        "2️⃣ Comparte cualquier publicación de ofertas en tu muro\n\n"
                        "3️⃣ Toma una *captura de pantalla* del post compartido\n\n"
                        "4️⃣ Envía la captura aquí mismo en este chat\n\n"
                        "⏳ Un admin la revisará y te dará tu boleto en breve 🎟️"
                    )

            # ── Recibir captura de pantalla ────────────────────────────────
            elif upd.get("message", {}).get("photo"):
                msg_foto  = upd.get("message", {})
                user_f    = msg_foto.get("from", {})
                user_id_f = user_f.get("id")
                uname_f   = user_f.get("username") or user_f.get("first_name", "Usuario")
                chat_id_f = msg_foto.get("chat", {}).get("id")

                if ya_compartio_fb(user_id_f):
                    enviar_msg(chat_id_f, "Ya tienes tu boleto por compartir en Facebook 😊")
                else:
                    # Reenviar captura al admin para revisión
                    foto = msg_foto["photo"][-1]["file_id"]
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data={
                            "chat_id": "994517706",
                            "photo": foto,
                            "caption": (
                                f"📸 *Captura de @{uname_f}*\n"
                                f"ID: `{user_id_f}`\n\n"
                                f"Si es válida escribe:\n`/aprobar {user_id_f}`\n\n"
                                f"Si no es válida:\n`/rechazar {user_id_f}`"
                            ),
                            "parse_mode": "Markdown"
                        },
                        timeout=10
                    )
                    enviar_msg(chat_id_f,
                        "✅ *Captura recibida!*\n\n"
                        "Un admin la revisará pronto y recibirás tu boleto 🎟️\n"
                        "Normalmente tarda menos de 24 horas."
                    )

            # ── /aprobar ID → admin ────────────────────────────────────────
            elif texto_msg.startswith("/aprobar "):
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso.")
                    continue
                aprobar_id = texto_msg.replace("/aprobar ", "").strip()
                if ya_compartio_fb(aprobar_id):
                    enviar_msg(chat_id, f"⚠️ El usuario `{aprobar_id}` ya tiene su boleto de Facebook.")
                else:
                    # Buscar username
                    con = sqlite3.connect(DB_FILE)
                    cur = con.cursor()
                    cur.execute("SELECT username FROM participantes WHERE user_id = ?", (aprobar_id,))
                    row = cur.fetchone()
                    con.close()
                    apro_uname = row[0] if row else "Usuario"
                    marcar_fb_compartido(aprobar_id, apro_uname)
                    codigo = dar_boleto(aprobar_id, apro_uname, "compartio en Facebook ✓ verificado")
                    # Notificar al usuario
                    enviar_msg(aprobar_id,
                        f"🎉 *Tu captura fue aprobada!*\n\n"
                        f"🎟️ Tu boleto: `{codigo}`\n\n"
                        "Mucha suerte en el sorteo! 🍀"
                    )
                    enviar_msg(chat_id, f"✅ Boleto `{codigo}` dado a @{apro_uname} ({aprobar_id})")

            # ── /rechazar ID → admin ───────────────────────────────────────
            elif texto_msg.startswith("/rechazar "):
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso.")
                    continue
                rechazar_id = texto_msg.replace("/rechazar ", "").strip()
                con = sqlite3.connect(DB_FILE)
                cur = con.cursor()
                cur.execute("SELECT username FROM participantes WHERE user_id = ?", (rechazar_id,))
                row = cur.fetchone()
                con.close()
                rec_uname = row[0] if row else "Usuario"
                enviar_msg(rechazar_id,
                    "❌ *Tu captura no fue aprobada*\n\n"
                    "Asegúrate de:\n"
                    "1️⃣ Compartir desde nuestra página de Facebook\n"
                    "2️⃣ Que el post sea visible (no privado)\n"
                    "3️⃣ Mandar la captura completa con tu nombre visible\n\n"
                    "Inténtalo de nuevo con /yocomparti 🙏"
                )
                enviar_msg(chat_id, f"❌ Captura de @{rec_uname} ({rechazar_id}) rechazada.")

            elif texto_msg.strip() == "/sorteo":
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso para usar este comando.")
                    continue
                premio, ganador, total_p = realizar_sorteo()
                if not ganador:
                    enviar_msg(chat_id, "No hay participantes o no hay rifa activa.")
                else:
                    resultado = (
                        f"🎉 *GANADOR DE LA RIFA* 🎉\n\n"
                        f"🏆 Premio: *{premio}*\n"
                        f"🎟️ Boleto ganador: `{ganador[2]}`\n"
                        f"👤 Usuario: @{ganador[1]}\n"
                        f"📊 Total boletos participantes: {total_p}"
                    )
                    enviar_msg(chat_id, resultado)
                    enviar_msg(CANAL_TELEGRAM, resultado)

            elif texto_msg.startswith("/nuevarifa "):
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso para usar este comando.")
                    continue
                premio = texto_msg.replace("/nuevarifa ", "").strip()
                crear_rifa(premio)
                enviar_msg(chat_id,
                    f"✅ *Nueva rifa creada*\n"
                    f"Premio: *{premio}*\n\n"
                    "Participantes y boletos anteriores eliminados.\n"
                    "Ya se anuncio en el canal! 🎟️"
                )
                enviar_msg(CANAL_TELEGRAM,
                    f"🎊 *NUEVA RIFA DISPONIBLE* 🎊\n\n"
                    f"🏆 Premio: *{premio}*\n\n"
                    "*Como participar:*\n"
                    f"1️⃣ Suscribete a {CANAL_TELEGRAM}\n"
                    "2️⃣ Escribe /rifa a @Ofertonloco_bot\n"
                    "3️⃣ Invita amigos y gana mas boletos\n"
                    "4️⃣ Comparte en FB para 1 boleto extra\n\n"
                    "Mas boletos = mas probabilidad de ganar! 🍀"
                )

            elif texto_msg.strip() == "/estadisticas":
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso para usar este comando.")
                    continue
                con = sqlite3.connect(DB_FILE)
                cur = con.cursor()
                cur.execute("SELECT COUNT(DISTINCT user_id) FROM participantes")
                total_u = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM boletos")
                total_b = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM invitaciones")
                total_i = cur.fetchone()[0]
                cur.execute("SELECT username, boletos FROM participantes ORDER BY boletos DESC LIMIT 5")
                top = cur.fetchall()
                con.close()
                top_txt = "\n".join([f"  {i+1}. @{r[0]} — {r[1]} boletos" for i, r in enumerate(top)])
                enviar_msg(chat_id,
                    f"📊 *Estadisticas de la Rifa*\n\n"
                    f"👥 Participantes: {total_u}\n"
                    f"🎟️ Boletos totales: {total_b}\n"
                    f"🔗 Invitaciones: {total_i}\n\n"
                    f"🏆 *Top 5 con mas boletos:*\n{top_txt}"
                )

            elif texto_msg.strip() == "/exportar":
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso para usar este comando.")
                    continue
                try:
                    con = sqlite3.connect(DB_FILE)
                    cur = con.cursor()
                    cur.execute("SELECT codigo, username, motivo, fecha FROM boletos ORDER BY id")
                    boletos_todos = cur.fetchall()
                    con.close()

                    if not boletos_todos:
                        enviar_msg(chat_id, "No hay boletos aún.")
                        continue

                    # Crear CSV en memoria
                    import io
                    output = io.StringIO()
                    output.write("CODIGO,USUARIO,MOTIVO,FECHA\n")
                    for b in boletos_todos:
                        output.write(f"{b[0]},{b[1]},{b[2]},{b[3]}\n")
                    csv_bytes = output.getvalue().encode("utf-8")

                    # Mandar como archivo por Telegram
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                        data={"chat_id": chat_id, "caption": f"🎟️ Total boletos: {len(boletos_todos)}"},
                        files={"document": ("boletos_rifa.csv", csv_bytes, "text/csv")},
                        timeout=15
                    )
                except Exception as e:
                    enviar_msg(chat_id, f"Error al exportar: {e}")
                if str(user_id) != "994517706":
                    enviar_msg(chat_id, "⛔ No tienes permiso para usar este comando.")
                    continue
                con = sqlite3.connect(DB_FILE)
                cur = con.cursor()
                # Totales
                cur.execute("SELECT COUNT(DISTINCT user_id) FROM participantes")
                total_u = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM boletos")
                total_b = cur.fetchone()[0]
                # Rifa activa
                cur.execute("SELECT premio, fecha FROM rifas WHERE activa = 1 ORDER BY id DESC LIMIT 1")
                rifa = cur.fetchone()
                # Todos los participantes con boletos
                cur.execute("SELECT username, boletos, invitados FROM participantes ORDER BY boletos DESC")
                participantes = cur.fetchall()
                # Últimos 5 boletos generados
                cur.execute("SELECT username, codigo, motivo, fecha FROM boletos ORDER BY id DESC LIMIT 5")
                ultimos = cur.fetchall()
                con.close()

                rifa_txt = f"🏆 *{rifa[0]}* (desde {rifa[1]})" if rifa else "❌ Sin rifa activa"

                part_txt = "\n".join([
                    f"  @{r[0]} — {r[1]} 🎟️  ({r[2]} invitados)"
                    for r in participantes
                ]) if participantes else "  Nadie aún"

                ultimos_txt = "\n".join([
                    f"  @{r[0]} `{r[1]}` — {r[2]} ({r[3]})"
                    for r in ultimos
                ]) if ultimos else "  Sin boletos aún"

                enviar_msg(chat_id,
                    f"🔐 *PANEL ADMIN*\n\n"
                    f"🎁 Rifa activa: {rifa_txt}\n\n"
                    f"👥 Participantes: {total_u}\n"
                    f"🎟️ Boletos totales: {total_b}\n\n"
                    f"📋 *Todos los participantes:*\n{part_txt}\n\n"
                    f"🕐 *Últimos 5 boletos generados:*\n{ultimos_txt}\n\n"
                    f"*Comandos admin:*\n"
                    f"/sorteo — elegir ganador\n"
                    f"/nuevarifa PREMIO — reiniciar rifa\n"
                    f"/estadisticas — resumen rápido"
                )

    except Exception as e:
        print(f"  [Rifa Bot] Error: {e}")

# ─────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────
init_db()
print("=" * 45)
print("OfertonLoco Bot iniciado!")
print(f"Telegram : {CANAL_TELEGRAM}")
print(f"Facebook : {'ACTIVO ✓' if FB_ENABLED else 'INACTIVO'}")
print("Rifa     : ACTIVO ✓")
print("=" * 45)
print()
print("Comandos admin (escríbelos al bot):")
print("  /nuevarifa PREMIO  → crear rifa y anunciar")
print("  /sorteo            → elegir ganador al azar")
print("  /estadisticas      → ver participantes y top")
print("=" * 45)

def hilo_rifa():
    print("[Rifa] Hilo de respuestas iniciado ✓")
    while True:
        try:
            procesar_updates_rifa()
        except Exception as e:
            print(f"[Rifa] Error en hilo: {e}")
        time.sleep(2)

def hilo_ofertas():
    buscar_y_publicar()
    schedule.every(2).hours.do(buscar_y_publicar)
    while True:
        schedule.run_pending()
        time.sleep(30)

t_rifa    = threading.Thread(target=hilo_rifa,    daemon=True)
t_ofertas = threading.Thread(target=hilo_ofertas, daemon=True)

t_rifa.start()
t_ofertas.start()

print("=" * 45)
print("✅ Bot corriendo en 2 hilos paralelos:")
print("   Hilo 1 — Ofertas: publica cada 2 horas")
print("   Hilo 2 — Rifa: responde mensajes cada 2s")
print("=" * 45)
print("Ctrl+C para detener")

while True:
    time.sleep(60)
