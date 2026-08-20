# Joselyn Ramirez — Nails · Art · Lashes 💅

Web de reservas para el salón de belleza: uñas, cejas y pestañas.
Los clientes agendan su cita eligiendo día y hora libre; tú (admin) las aceptas o
rechazas, y cada solicitud te llega a tu WhatsApp.

## Cómo funciona
- **Menú lateral (4 secciones):** Uñas · Cejas · Pestañas · Agendar cita. Además: *Ver estado* y *Administración*.
- Cada servicio abre una **ventana emergente** con su explicación y un botón para agendar.
- **Agendar:** nombre y apellido, teléfono y descripción (obligatorios) + servicios + día (L-V) + hora libre. Citas de **2 horas**, de 08:00 a 17:00. **Sin precios.**
- El cliente recibe un **código** y puede *Ver estado* (pendiente / aceptada / rechazada).
- **Administración** (solo tú): ves todas las solicitudes y las aceptas o rechazas. Al decidir, aparece un botón para avisar al cliente por WhatsApp.

## Probar en tu PC (Windows)
```bash
py -3 -m pip install -r requirements.txt
py -3 server.py
```
Abre http://localhost:8000

## Que la cita llegue SOLA a tu WhatsApp (CallMeBot, gratis)
Se hace **una sola vez**:
1. Agenda el número **+34 644 66 32 62** en tus contactos como "CallMeBot".
2. Desde TU WhatsApp (593969521836) envíale el mensaje: **I allow callmebot to send me messages**
3. Te responde con tu **apikey**. Pon ese valor en la variable `CALLMEBOT_APIKEY`.

Si no lo configuras, la web igual guarda todas las citas en el panel y muestra un
botón de respaldo para enviarte la cita por WhatsApp con un clic.

## Configuración (variables de entorno)
- `ADMIN_PASSWORD` — contraseña del panel de administración (por defecto `joselyn2026`, **cámbiala**).
- `CALLMEBOT_APIKEY` — apikey de CallMeBot (opcional pero recomendado).
- `OWNER_WHATSAPP` — tu número (por defecto `593969521836`).

En local: copia `.env.example` a `.env` y rellena los valores.

## Publicar en Render (gratis)
1. Sube esta carpeta a un repositorio de GitHub.
2. En Render: **New + → Blueprint** y conecta el repo (usa `render.yaml`).
3. En el panel de Render añade `ADMIN_PASSWORD` y `CALLMEBOT_APIKEY`.
4. Deploy. Tendrás tu web pública para compartir con tus clientas.
