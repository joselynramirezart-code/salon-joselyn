"""
Joselyn Ramirez — Nails · Art · Lashes
Servidor de la web del salón de belleza.

Funciones:
  - Sirve la página (catálogo de servicios de uñas, cejas y pestañas).
  - Los clientes agendan una cita (nombre y apellido, teléfono y descripción
    obligatorios) eligiendo día y hora disponible (bloques de 2 horas,
    lunes a viernes de 08:00 a 17:00).
  - Cada solicitud llega a TU WhatsApp automáticamente (vía CallMeBot, si está
    configurado) y queda en el panel de administración.
  - Solo tú (admin) ves todas las solicitudes y las aceptas o rechazas.
  - El cliente consulta el estado de su solicitud con su código o su teléfono
    y ve si fue aceptada o rechazada.

Arranque local:
    pip install -r requirements.txt
    python server.py            ->  http://localhost:8000
En un hosting (Render) se usa la variable PORT automáticamente.
"""

import hashlib
import json
import os
import re
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse

load_dotenv()

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
APPTS_FILE = DATA_DIR / "citas.json"
CLIENTS_FILE = DATA_DIR / "clientes.json"

# Tu WhatsApp (el mismo de los otros proyectos). Se puede cambiar por variable.
OWNER_WHATSAPP = os.getenv("OWNER_WHATSAPP", "593969521836").strip()

# Tu correo principal (con el que entras al panel de administración).
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "joselynramirez.art@gmail.com").strip().lower()

# Contraseña del panel de administración (¡cámbiala en producción!).
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "joselyn2026").strip()

# Login con Google (Gmail). Pega aquí el Client ID de Google (OAuth Web).
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

# Tokens de sesión de admin (cuando la dueña entra con su Gmail). En memoria.
ADMIN_TOKENS: set[str] = set()

# CallMeBot: para que la cita llegue SOLA a tu WhatsApp.
# Configúralo una vez (ver README) y pega tu apikey en esta variable.
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY", "").strip()

# Horario de atención (lunes a viernes de 08:00 a 17:00).
OPEN_HOUR = 8
CLOSE_HOUR = 17
OPEN_MIN = OPEN_HOUR * 60       # 480
CLOSE_MIN = CLOSE_HOUR * 60     # 1020
STEP_MIN = 30                   # las citas empiezan cada 30 min
DEFAULT_DUR = 120              # duración por defecto si no se indica (min)

# --------------------------------------------------------------------------- #
# Catálogo de servicios (SIN precios) — el cliente elige qué quiere.
# "dur" = duración estimada en minutos; si elige varios, se SUMAN.
# --------------------------------------------------------------------------- #
# Cada servicio dura 2 horas (120 min). Si el cliente elige varios, se SUMAN
# (2 servicios = 4 h, etc.).
SERVICE_DUR = 120

SERVICES = [
    # ---- Uñas ----
    {"id": "manicura", "cat": "Uñas", "icon": "💅", "nombre": "Manicura clásica", "dur": SERVICE_DUR,
     "desc": "Limado, cutículas, hidratación y esmaltado tradicional para unas manos impecables."},
    {"id": "semi_manos", "cat": "Uñas", "icon": "✨", "nombre": "Esmaltado semipermanente (manos)", "dur": SERVICE_DUR,
     "desc": "Color de larga duración con acabado brillante que aguanta semanas sin descascararse."},
    {"id": "acrilicas", "cat": "Uñas", "icon": "💎", "nombre": "Uñas acrílicas", "dur": SERVICE_DUR,
     "desc": "Extensión y esculpido con acrílico profesional. Elige forma y largo a tu gusto."},
    {"id": "gel_polygel", "cat": "Uñas", "icon": "🪞", "nombre": "Uñas en gel / polygel", "dur": SERVICE_DUR,
     "desc": "Refuerzo natural y resistente, ideal para un acabado ligero y muy duradero."},
    {"id": "nail_art", "cat": "Uñas", "icon": "🎨", "nombre": "Diseños y decoración (nail art)", "dur": SERVICE_DUR,
     "desc": "Diseños personalizados: pedrería, francés, efectos, temáticas… tú imaginas, yo lo creo."},
    {"id": "pedicura", "cat": "Uñas", "icon": "🦶", "nombre": "Pedicura / esmaltado de pies", "dur": SERVICE_DUR,
     "desc": "Cuidado completo de pies con esmaltado profesional, clásico o semipermanente."},
    {"id": "retiro_unas", "cat": "Uñas", "icon": "🧴", "nombre": "Retiro de esmaltado / acrílico", "dur": SERVICE_DUR,
     "desc": "Retiro seguro que cuida tu uña natural, dejándola sana y lista para lo siguiente."},

    # ---- Cejas ----
    {"id": "diseno_cejas", "cat": "Cejas", "icon": "🪶", "nombre": "Alineado y diseño de cejas", "dur": SERVICE_DUR,
     "desc": "Diseño según tu rostro para realzar tu mirada con la forma que mejor te queda."},
    {"id": "cera_cejas", "cat": "Cejas", "icon": "🌸", "nombre": "Depilación con cera", "dur": SERVICE_DUR,
     "desc": "Depilación precisa y prolija para unas cejas definidas y de aspecto natural."},
    {"id": "tinte_cejas", "cat": "Cejas", "icon": "🖌️", "nombre": "Tinte / henna de cejas", "dur": SERVICE_DUR,
     "desc": "Color que rellena y define, dando profundidad y forma a tus cejas."},
    {"id": "laminado_cejas", "cat": "Cejas", "icon": "💫", "nombre": "Laminado de cejas", "dur": SERVICE_DUR,
     "desc": "Peinado fijado que ordena el vello y crea el efecto de cejas más pobladas y prolijas."},

    # ---- Pestañas ----
    {"id": "lifting", "cat": "Pestañas", "icon": "👁️", "nombre": "Lifting de pestañas", "dur": SERVICE_DUR,
     "desc": "Curva y eleva tus pestañas naturales para una mirada abierta que dura semanas."},
    {"id": "clasicas", "cat": "Pestañas", "icon": "🌼", "nombre": "Extensiones pelo a pelo (clásicas)", "dur": SERVICE_DUR,
     "desc": "Una extensión por pestaña para un efecto natural que alarga tu mirada."},
    {"id": "volumen", "cat": "Pestañas", "icon": "🖤", "nombre": "Extensiones volumen ruso", "dur": SERVICE_DUR,
     "desc": "Abanicos de varias fibras por pestaña para una mirada intensa y espectacular."},
    {"id": "tinte_pest", "cat": "Pestañas", "icon": "🌙", "nombre": "Tinte de pestañas", "dur": SERVICE_DUR,
     "desc": "Oscurece tus pestañas naturales para un efecto máscara permanente y sin maquillaje."},
    {"id": "retiro_pest", "cat": "Pestañas", "icon": "🫧", "nombre": "Retiro de extensiones", "dur": SERVICE_DUR,
     "desc": "Retiro profesional y cuidadoso que respeta tus pestañas naturales."},
]
SERVICES_BY_ID = {s["id"]: s for s in SERVICES}

app = FastAPI(title="Joselyn Ramirez — Nails · Art · Lashes")


# --------------------------------------------------------------------------- #
# Utilidades de almacenamiento
# --------------------------------------------------------------------------- #
def _load() -> list:
    try:
        return json.loads(APPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data: list) -> None:
    APPTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_clients() -> list:
    try:
        return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_clients(data: list) -> None:
    CLIENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _phone_key(telefono: str) -> str:
    return re.sub(r"\D", "", telefono or "")


def _hash_pw(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def _verify_pw(password: str, stored: str) -> bool:
    try:
        salt, h = (stored or "").split("$", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == h


def _client_public(cli: dict) -> dict:
    return {
        "nombre": cli.get("nombre", ""),
        "email": cli.get("email", ""),
        "telefono": cli.get("telefono", ""),
        "citas_count": int(cli.get("citas_count", 0)),
        "ultimo_servicio": cli.get("ultimo_servicio", ""),
    }


def _find_client(clients: list, email: str = "", telefono: str = "") -> dict | None:
    """Busca un cliente por correo (prioritario) o por teléfono."""
    email_l = (email or "").strip().lower()
    if email_l:
        for c in clients:
            if c.get("email", "").strip().lower() == email_l:
                return c
    key = _phone_key(telefono)
    if key:
        for c in clients:
            if c.get("telefono_key") == key:
                return c
    return None


def _upsert_client(nombre: str, telefono: str = "", email: str = "", cuenta_cita: bool = False,
                   servicios=None, google: bool = False) -> dict:
    """Crea o actualiza un cliente (por correo o teléfono). Si cuenta_cita, suma +1."""
    if not _phone_key(telefono) and not (email or "").strip():
        return {}
    clients = _load_clients()
    cli = _find_client(clients, email=email, telefono=telefono)
    if cli is None:
        cli = {
            "telefono_key": _phone_key(telefono), "nombre": nombre, "telefono": telefono,
            "email": (email or "").strip(), "citas_count": 0,
            "ultimo_servicio": "", "creado": _now_iso(), "ultima_cita": None,
        }
        clients.append(cli)
    if nombre:
        cli["nombre"] = nombre
    if email:
        cli["email"] = email.strip()
    if telefono and not cli.get("telefono"):
        cli["telefono"] = telefono
        cli["telefono_key"] = _phone_key(telefono)
    if google:
        cli["google"] = True
    if cuenta_cita:
        cli["citas_count"] = int(cli.get("citas_count", 0)) + 1
        cli["ultima_cita"] = _now_iso()
        if servicios:
            cli["ultimo_servicio"] = ", ".join(
                SERVICES_BY_ID.get(s, {}).get("nombre", s) for s in servicios)
    _save_clients(clients)
    return cli


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _total_dur(servicios: list) -> int:
    """Suma las duraciones (min) de los servicios elegidos."""
    return sum(SERVICES_BY_ID.get(s, {}).get("dur", 0) for s in servicios)


def _fmt_dur(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"


def _busy_intervals(citas: list, fecha: str, exclude_id: str = "") -> list:
    """Intervalos [inicio, fin) que bloquean ese día. SOLO las citas ACEPTADAS
    bloquean el horario; las pendientes no, para que no se llene la agenda
    con solicitudes sin confirmar. Se puede excluir una cita por id."""
    out = []
    for c in citas:
        if c["id"] == exclude_id:
            continue
        if c["fecha"] == fecha and c["estado"] == "aceptada":
            start = _to_min(c["hora"])
            out.append((start, start + int(c.get("dur_min", DEFAULT_DUR))))
    return out


def _fits(start: int, dur: int, busy: list) -> bool:
    """True si una cita [start, start+dur) cabe en el horario y no se solapa."""
    if start < OPEN_MIN or start + dur > CLOSE_MIN:
        return False
    end = start + dur
    return all(not (start < b_end and end > b_start) for b_start, b_end in busy)


def _is_weekday(fecha: str) -> bool:
    try:
        d = datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return False
    return d.weekday() < 5  # 0=lunes ... 4=viernes


def _check_admin(value: str | None) -> None:
    """Acepta la contraseña de admin O un token de sesión de admin (login Google)."""
    if value and (value == ADMIN_PASSWORD or value in ADMIN_TOKENS):
        return
    raise HTTPException(status_code=401, detail="No autorizado.")


def _issue_admin_token() -> str:
    t = secrets.token_hex(24)
    ADMIN_TOKENS.add(t)
    return t


def _verify_google(credential: str) -> dict | None:
    """Verifica el ID token de Google (firma + expiración) vía tokeninfo."""
    if not GOOGLE_CLIENT_ID or not credential:
        return None
    try:
        url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + urllib.parse.quote(credential)
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[google] no se pudo verificar: {exc}", flush=True)
        return None
    if data.get("aud") != GOOGLE_CLIENT_ID:
        return None
    if str(data.get("email_verified", "")).lower() not in ("true", "1"):
        return None
    return {"email": str(data.get("email", "")).lower(), "name": str(data.get("name", ""))}


# --------------------------------------------------------------------------- #
# WhatsApp (CallMeBot) — envía la cita a TU WhatsApp automáticamente
# --------------------------------------------------------------------------- #
def _wa_text(appt: dict) -> str:
    servicios = ", ".join(SERVICES_BY_ID.get(s, {}).get("nombre", s) for s in appt["servicios"])
    dur_txt = _fmt_dur(int(appt.get("dur_min", DEFAULT_DUR)))
    return (
        "NUEVA SOLICITUD DE CITA - Joselyn Ramirez\n"
        f"Cliente: {appt['nombre']}\n"
        f"Telefono: {appt['telefono']}\n"
        f"Fecha: {appt['fecha']}  Hora: {appt['hora']} a {appt['fin']} ({dur_txt})\n"
        f"Servicios: {servicios}\n"
        f"Descripcion: {appt['descripcion']}\n"
        f"Codigo: {appt['code']}\n"
        "Entra al panel de administracion para aceptar o rechazar."
    )


def wa_link(phone: str, text: str) -> str:
    """Enlace wa.me con el mensaje ya escrito (fallback que siempre funciona)."""
    return f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"


def send_whatsapp_to_owner(appt: dict) -> bool:
    """Envía la cita a tu WhatsApp vía CallMeBot. Devuelve True si se envió."""
    if not CALLMEBOT_APIKEY:
        return False
    try:
        url = (
            "https://api.callmebot.com/whatsapp.php?"
            + urllib.parse.urlencode({
                "phone": OWNER_WHATSAPP,
                "text": _wa_text(appt),
                "apikey": CALLMEBOT_APIKEY,
            })
        )
        with urllib.request.urlopen(url, timeout=15) as resp:
            resp.read()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[whatsapp] no se pudo enviar: {exc}", flush=True)
        return False


# --------------------------------------------------------------------------- #
# Rutas de la página y catálogo
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/logo.png")
def logo():
    return FileResponse(BASE_DIR / "logo.png", media_type="image/png")


@app.get("/fondo.jpg")
def fondo():
    return FileResponse(BASE_DIR / "fondo.jpg", media_type="image/jpeg")


@app.get("/api/config")
def config():
    return {
        "owner_whatsapp": OWNER_WHATSAPP,
        "owner_email": ADMIN_EMAIL,
        "google_client_id": GOOGLE_CLIENT_ID,
        "horario": {"open": OPEN_HOUR, "close": CLOSE_HOUR, "dias": "Lunes a viernes"},
        "step_min": STEP_MIN,
    }


@app.get("/api/services")
def services():
    return {"services": SERVICES}


@app.post("/api/register")
def register(payload: dict = Body(...)):
    """Crea una cuenta de cliente (con contraseña) para entrar y ver su historial."""
    nombre = str(payload.get("nombre", "")).strip()
    telefono = str(payload.get("telefono", "")).strip()
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    if len(nombre.split()) < 2:
        raise HTTPException(status_code=400, detail="Escribe tu nombre y apellido.")
    if len(_phone_key(telefono)) < 7:
        raise HTTPException(status_code=400, detail="Escribe un teléfono válido.")
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Escribe un correo válido.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")

    email_l = email.lower()
    if email_l == ADMIN_EMAIL:
        raise HTTPException(status_code=409, detail="Ese correo no está disponible.")

    clients = _load_clients()
    if any((c.get("email", "").lower() == email_l and c.get("password_hash")) for c in clients):
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado. Inicia sesión.")

    key = _phone_key(telefono)
    cli = next((c for c in clients if c.get("telefono_key") == key), None)
    if cli is None:
        cli = {
            "telefono_key": key, "nombre": nombre, "telefono": telefono,
            "email": email, "citas_count": 0, "ultimo_servicio": "",
            "creado": _now_iso(), "ultima_cita": None,
        }
        clients.append(cli)
    cli["nombre"] = nombre
    cli["email"] = email
    cli["password_hash"] = _hash_pw(password)
    _save_clients(clients)
    return {"ok": True, "role": "client", "cliente": _client_public(cli)}


@app.post("/api/login")
def login(payload: dict = Body(...)):
    """Login unificado: la dueña entra como admin; las clientas a su cuenta."""
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        raise HTTPException(status_code=400, detail="Escribe tu correo y contraseña.")

    # La dueña (admin)
    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        return {"ok": True, "role": "admin"}

    # Cliente registrado
    clients = _load_clients()
    cli = next((c for c in clients
                if c.get("email", "").strip().lower() == email and c.get("password_hash")), None)
    if cli and _verify_pw(password, cli["password_hash"]):
        return {"ok": True, "role": "client", "cliente": _client_public(cli)}

    raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")


@app.post("/api/google-login")
def google_login(payload: dict = Body(...)):
    """Entrar/registrarse con Google (Gmail). La dueña entra como admin automáticamente."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="El acceso con Google no está disponible aún.")
    info = _verify_google(str(payload.get("credential", "")).strip())
    if not info or not info.get("email"):
        raise HTTPException(status_code=401, detail="No se pudo verificar tu cuenta de Google.")

    email = info["email"]
    nombre = info.get("name") or email.split("@")[0]

    # La dueña: entra como admin con un token de sesión.
    if email == ADMIN_EMAIL:
        return {"ok": True, "role": "admin", "admin_token": _issue_admin_token()}

    # Cliente: se crea/actualiza su cuenta con Google (sin contraseña).
    cli = _upsert_client(nombre, email=email, google=True)
    return {"ok": True, "role": "client", "cliente": _client_public(cli)}


# --------------------------------------------------------------------------- #
# Disponibilidad de horarios
# --------------------------------------------------------------------------- #
@app.get("/api/availability")
def availability(date: str, dur: int = DEFAULT_DUR):
    """Devuelve las horas de inicio en que cabe una cita de 'dur' minutos ese día.

    La disponibilidad depende de cuánto dura la cita: si el cliente elige varios
    servicios, la duración total es mayor y hay menos horas de inicio posibles
    (y bloquea el tiempo de la siguiente cita según lo que demore).
    """
    if not _is_weekday(date):
        return {"date": date, "abierto": False, "slots": [], "dur": dur,
                "motivo": "Solo atendemos de lunes a viernes."}

    dur = max(STEP_MIN, int(dur or DEFAULT_DUR))
    if dur > (CLOSE_MIN - OPEN_MIN):
        return {"date": date, "abierto": True, "slots": [], "dur": dur,
                "motivo": "Esos servicios juntos superan el horario del día. Divídelos en dos citas."}

    busy = _busy_intervals(_load(), date)
    slots = []
    start = OPEN_MIN
    while start + dur <= CLOSE_MIN:
        if _fits(start, dur, busy):
            slots.append({"hora": _to_hhmm(start), "fin": _to_hhmm(start + dur)})
        start += STEP_MIN
    return {"date": date, "abierto": True, "dur": dur, "dur_txt": _fmt_dur(dur), "slots": slots}


# --------------------------------------------------------------------------- #
# Crear cita (cliente)
# --------------------------------------------------------------------------- #
@app.post("/api/appointments")
def create_appointment(payload: dict = Body(...)):
    nombre = str(payload.get("nombre", "")).strip()
    telefono = str(payload.get("telefono", "")).strip()
    descripcion = str(payload.get("descripcion", "")).strip()
    servicios = payload.get("servicios", [])
    fecha = str(payload.get("fecha", "")).strip()
    hora = str(payload.get("hora", "")).strip()
    email = str(payload.get("email", "")).strip()  # opcional: correo del cliente logueado

    # Validaciones obligatorias
    if len(nombre) < 3 or " " not in nombre:
        raise HTTPException(status_code=400, detail="Escribe tu nombre y apellido completos.")
    if len(re.sub(r"\D", "", telefono)) < 7:
        raise HTTPException(status_code=400, detail="Escribe un número de teléfono válido.")
    if len(descripcion) < 4:
        raise HTTPException(status_code=400, detail="Describe brevemente lo que quieres hacerte.")
    if not isinstance(servicios, list) or not servicios:
        raise HTTPException(status_code=400, detail="Elige al menos un servicio.")
    servicios = [s for s in servicios if s in SERVICES_BY_ID]
    if not servicios:
        raise HTTPException(status_code=400, detail="Los servicios elegidos no son válidos.")
    if not _is_weekday(fecha):
        raise HTTPException(status_code=400, detail="Elige un día de lunes a viernes.")

    # Duración total = suma de los servicios elegidos.
    dur = _total_dur(servicios)
    if dur <= 0:
        raise HTTPException(status_code=400, detail="Los servicios elegidos no tienen duración válida.")
    if dur > (CLOSE_MIN - OPEN_MIN):
        raise HTTPException(status_code=400,
                            detail="Esos servicios juntos superan el horario del día. Divídelos en dos citas.")

    try:
        start = _to_min(hora)
    except Exception:
        raise HTTPException(status_code=400, detail="Elige una hora válida.")
    if start % STEP_MIN != 0:
        raise HTTPException(status_code=400, detail="Elige una hora válida.")

    citas = _load()
    busy = _busy_intervals(citas, fecha)
    if not _fits(start, dur, busy):
        raise HTTPException(status_code=409,
                            detail="Ese horario ya no cabe (se cruza con otra cita o con el cierre). Elige otro.")

    appt = {
        "id": secrets.token_hex(8),
        "code": secrets.token_hex(3).upper(),  # 6 caracteres
        "nombre": nombre,
        "telefono": telefono,
        "email": email,
        "descripcion": descripcion,
        "servicios": servicios,
        "categoria": ", ".join(sorted({SERVICES_BY_ID[s]["cat"] for s in servicios})),
        "fecha": fecha,
        "hora": hora,
        "fin": _to_hhmm(start + dur),
        "dur_min": dur,
        "estado": "pendiente",
        "creado": _now_iso(),
        "respondido": None,
    }
    citas.insert(0, appt)
    _save(citas)

    # Registra al cliente y suma +1 a su historial de citas.
    _upsert_client(nombre, telefono, email=email, cuenta_cita=True, servicios=servicios)

    enviado = send_whatsapp_to_owner(appt)

    return JSONResponse({
        "ok": True,
        "code": appt["code"],
        "cita": _public(appt),
        "whatsapp_enviado": enviado,
        # Enlace de respaldo: abre TU WhatsApp con la cita ya escrita.
        "wa_owner_link": wa_link(OWNER_WHATSAPP, _wa_text(appt)),
    })


def _public(appt: dict) -> dict:
    """Versión de una cita para mostrar (con nombres de servicios)."""
    return {
        "code": appt["code"],
        "nombre": appt["nombre"],
        "telefono": appt["telefono"],
        "descripcion": appt["descripcion"],
        "categoria": appt["categoria"],
        "servicios": [SERVICES_BY_ID.get(s, {}).get("nombre", s) for s in appt["servicios"]],
        "fecha": appt["fecha"],
        "hora": appt["hora"],
        "fin": appt["fin"],
        "dur_txt": _fmt_dur(int(appt.get("dur_min", DEFAULT_DUR))),
        "estado": appt["estado"],
        "creado": appt["creado"],
        "respondido": appt["respondido"],
    }


# --------------------------------------------------------------------------- #
# Consulta de estado (cliente)
# --------------------------------------------------------------------------- #
@app.get("/api/status")
def status(code: str = "", phone: str = "", email: str = ""):
    code = (code or "").strip().upper()
    phone_digits = re.sub(r"\D", "", phone or "")
    email_l = (email or "").strip().lower()
    citas = _load()
    encontrados = []
    for c in citas:
        if code and c["code"] == code:
            encontrados.append(_public(c))
        elif phone_digits and re.sub(r"\D", "", c["telefono"]) == phone_digits:
            encontrados.append(_public(c))
        elif email_l and c.get("email", "").strip().lower() == email_l:
            encontrados.append(_public(c))
    if not encontrados:
        raise HTTPException(status_code=404, detail="No encontramos ninguna solicitud con esos datos.")
    return {"citas": encontrados}


# --------------------------------------------------------------------------- #
# Administración (solo tú)
# --------------------------------------------------------------------------- #
@app.post("/api/admin/login")
def admin_login(payload: dict = Body(...)):
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    if email != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    return {"ok": True, "email": ADMIN_EMAIL}


@app.get("/api/admin/clientes")
def admin_clientes(x_admin_password: str | None = Header(default=None)):
    """Registro de clientes con cuántas veces han agendado (solo admin)."""
    _check_admin(x_admin_password)
    clients = sorted(_load_clients(), key=lambda c: int(c.get("citas_count", 0)), reverse=True)
    safe = []
    for c in clients:
        item = {k: v for k, v in c.items() if k != "password_hash"}
        item["registrado"] = bool(c.get("password_hash"))  # True = tiene cuenta con contraseña
        safe.append(item)
    return {"clientes": safe, "total": len(safe)}


@app.get("/api/admin/appointments")
def admin_list(x_admin_password: str | None = Header(default=None)):
    _check_admin(x_admin_password)
    citas = _load()
    return {"citas": [_public(c) | {"id": c["id"]} for c in citas]}


@app.post("/api/admin/decision")
def admin_decision(payload: dict = Body(...), x_admin_password: str | None = Header(default=None)):
    _check_admin(x_admin_password)
    appt_id = str(payload.get("id", "")).strip()
    decision = str(payload.get("decision", "")).strip()
    if decision not in ("aceptada", "rechazada"):
        raise HTTPException(status_code=400, detail="Decisión inválida.")

    citas = _load()
    target = next((c for c in citas if c["id"] == appt_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    # Al ACEPTAR: verificar que no choque con otra cita ya aceptada ese día.
    if decision == "aceptada":
        start = _to_min(target["hora"])
        dur = int(target.get("dur_min", DEFAULT_DUR))
        end = start + dur
        busy = _busy_intervals(citas, target["fecha"], exclude_id=appt_id)
        if any(start < b_end and end > b_start for b_start, b_end in busy):
            raise HTTPException(
                status_code=409,
                detail="Ya tienes otra cita ACEPTADA a esa hora. Recházala o reagenda antes de aceptar esta.")

    target["estado"] = decision
    target["respondido"] = _now_iso()
    _save(citas)

    # Enlace para avisar al cliente por WhatsApp (un clic).
    if decision == "aceptada":
        msg = (
            f"Hola {target['nombre'].split()[0]}! Tu cita en Joselyn Ramirez (Nails Art Lashes) "
            f"fue ACEPTADA para el {target['fecha']} de {target['hora']} a {target['fin']}. "
            "Te espero. Codigo: " + target["code"]
        )
    else:
        msg = (
            f"Hola {target['nombre'].split()[0]}. Sobre tu solicitud del {target['fecha']} "
            f"a las {target['hora']} en Joselyn Ramirez: por ahora no pudo confirmarse. "
            "Escribeme para buscar otro horario. Codigo: " + target["code"]
        )
    return {
        "ok": True,
        "cita": _public(target),
        "wa_cliente_link": wa_link(re.sub(r"\D", "", target["telefono"]), msg),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"\n  Joselyn Ramirez — Nails · Art · Lashes  ->  http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
