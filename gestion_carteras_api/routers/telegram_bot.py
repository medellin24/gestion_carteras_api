"""
Router para integrar el Bot de Telegram en la API via Webhook.
"""
import os
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import APIRouter, Request, BackgroundTasks, Header
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ..database.connection_pool import DatabasePool
from ..database.usuarios_db import logger as db_logger

router = APIRouter()

# ── Configuración ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
TZ = ZoneInfo("America/Bogota")

# Inicializar aplicación de telegram (sin iniciar polling)
tg_app = Application.builder().token(BOT_TOKEN).build() if BOT_TOKEN else None

# ── Decorador/Control de seguridad ─────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ── Helpers (Copiados de bot.py) ────────────────────────────────
def hoy_local() -> date:
    return datetime.now(TZ).date()

def markdown_escape(text: str) -> str:
    if not text: return ""
    chars = ["_", "*", "`", "["]
    for char in chars: text = text.replace(char, f"\\{char}")
    return text

def estado_emoji(estado: str, dias_restantes: int) -> str:
    if estado == "vencida" or dias_restantes <= 0: return "🔴"
    if dias_restantes <= 7: return "🟡"
    return "🟢"

def formato_fecha(val) -> str:
    if val is None: return "—"
    if hasattr(val, "date"): val = val.date()
    return val.isoformat()

def calcular_dias_restantes(fecha_fin, trial_until, fecha_inicio) -> int:
    hoy = hoy_local()
    fin = fecha_fin or trial_until
    if fin and hasattr(fin, "date"): fin = fin.date()
    if not fin and fecha_inicio:
        if hasattr(fecha_inicio, "date"): fecha_inicio = fecha_inicio.date()
        fin = fecha_inicio + timedelta(days=30)
    if fin: return max((fin - hoy).days, 0)
    return 0

# ── Handlers (Misma lógica que bot.py) ─────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    texto = (
        "🤖 *Bot Gestión de Carteras (API-Driven)*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Comandos:*\n"
        "🔹 /cuentas — Lista todas las cuentas\n"
        "🔹 /ver `<id>` — Detalle de cuenta\n"
        "🔹 /plan `<id>` `<emp>` `<dias>` — Act. plan\n"
        "🔹 /permiso `<emp_id>` `<cta_id>` — Permisos\n"
        "🔹 /empleados `<id>` — Ver empleados\n"
        f"\n📅 `{hoy_local()}`"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute("""
                SELECT 
                    c.id, c.nombre, c.plan, c.estado_suscripcion,
                    c.max_empleados, c.fecha_fin, c.trial_until, c.fecha_inicio,
                    (SELECT COUNT(*) FROM empleados e WHERE e.cuenta_id = c.id) AS num_empleados,
                    (SELECT COUNT(*) FROM usuarios u WHERE u.role='cobrador' AND u.cuenta_id = c.id AND u.is_active=TRUE) AS cobradores_activos,
                    (SELECT STRING_AGG(username || ' (' || role || ')', ', ') 
                     FROM usuarios u WHERE u.cuenta_id = c.id AND u.is_active=TRUE) AS usuarios_lista
                FROM cuentas_admin c ORDER BY c.id
            """)
            rows = cur.fetchall()

        if not rows:
            await update.message.reply_text("📭 No hay cuentas.")
            return

        lineas = ["📋 *CUENTAS*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for row in rows:
            (cid, nom, plan, est, max_e, f_fin, trial, f_ini, num_e, c_act, u_list) = row
            dias = calcular_dias_restantes(f_fin, trial, f_ini)
            emoji = estado_emoji(est or "", dias)
            info_u = f"\n    │ 👤 `{markdown_escape(u_list)}`" if u_list else ""
            lineas.append(
                f"*#{cid}* │ {markdown_escape(nom or 'Sin nombre')}\n"
                f"    │ 📦 `{markdown_escape(plan or 'sin plan')}` │ 👥 {num_e}/{max_e or 1} "
                f"│ ⏳ {dias}d │ {emoji} {markdown_escape(est or '?')}{info_u}\n"
            )
        await update.message.reply_text("".join(lineas), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: return
    cid_req = context.args[0]
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute("""
                SELECT id, nombre, plan, estado_suscripcion, max_empleados,
                       max_daily_routes, fecha_inicio, fecha_fin, trial_until,
                       daily_routes_date, daily_routes_empleados, timezone_default
                FROM cuentas_admin WHERE id = %s
            """, (cid_req,))
            row = cur.fetchone()
            if not row:
                await update.message.reply_text("❌ No encontrada")
                return
            (cid, nom, plan, est, m_e, m_r, f_i, f_f, tr, dr_d, dr_e, tz) = row
            dias = calcular_dias_restantes(f_f, tr, f_i)
            # Simplificado para brevedad, misma lógica que bot.py
            texto = f"📋 *CUENTA #{cid}*\n👤 {markdown_escape(nom)}\n📦 Plan: `{plan}`\n⏳ Días: {dias}"
            await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 3: return
    try:
        cid, max_e, dias = int(context.args[0]), int(context.args[1]), int(context.args[2])
        plan_n = f"plan_{max_e}"
        f_fin = hoy_local() + timedelta(days=dias)
        with DatabasePool.get_cursor() as cur:
            cur.execute("""
                UPDATE cuentas_admin SET plan=%s, max_empleados=%s, max_daily_routes=%s,
                estado_suscripcion='activa', fecha_inicio=%s, fecha_fin=%s, trial_until=NULL
                WHERE id=%s
            """, (plan_n, max_e, max_e, hoy_local(), f_fin, cid))
        await update.message.reply_text(f"✅ Cuenta #{cid} actualizada a {plan_n} por {dias} días.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_permiso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return
    emp_id, cta_id = context.args[0], int(context.args[1])
    try:
        ayer = hoy_local() - timedelta(days=1)
        with DatabasePool.get_cursor() as cur:
            cur.execute("UPDATE empleados SET descargar=TRUE, subir=TRUE, fecha_accion=%s WHERE identificacion=%s AND cuenta_id=%s", (ayer, emp_id, cta_id))
        await update.message.reply_text(f"✅ Permisos rehabilitados para ID `{emp_id}` en Cta #{cta_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ── Registro de Handlers ───────────────────────────────────────
if tg_app:
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("cuentas", cmd_cuentas))
    tg_app.add_handler(CommandHandler("ver", cmd_ver))
    tg_app.add_handler(CommandHandler("plan", cmd_plan))
    tg_app.add_handler(CommandHandler("permiso", cmd_permiso))

# ── Endpoint Webhook ───────────────────────────────────────────
@router.post("/webhook")
async def telegram_webhook(request: Request):
    if not tg_app: return {"ok": False}
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@router.get("/setup")
async def setup_webhook(url: str):
    """Llamar a este endpoint una vez para configurar el webhook en Telegram."""
    if not tg_app: return {"error": "No token"}
    webhook_url = f"{url}/telegram/webhook"
    success = await tg_app.bot.set_webhook(webhook_url)
    return {"webhook_set": success, "url": webhook_url}
