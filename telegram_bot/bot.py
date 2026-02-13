"""
🤖 Bot de Telegram para Gestión de Carteras
=============================================
Permite gestionar cuentas admin, suscripciones y permisos de empleados
directamente desde Telegram, con acceso directo a la base de datos.

Comandos:
  /start          - Bienvenida y lista de comandos
  /cuentas        - Lista todas las cuentas con resumen
  /ver <id>       - Detalle completo de una cuenta
  /plan <id> <empleados> <días>  - Actualizar plan de una cuenta
  /permiso <empleado_id> <cuenta_id>  - Rehabilitar permisos de descarga
  /empleados <id> - Lista empleados y permisos de una cuenta
  /sql <query>    - Ejecutar SQL personalizado (solo SELECT)
"""

import os
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db import get_cursor

# ── Configuración ──────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
TZ = ZoneInfo("America/Bogota")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Decorador de seguridad ─────────────────────────────────────
def solo_admin(func):
    """Solo permite ejecución al ADMIN_TELEGRAM_ID."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ No autorizado.")
            return
        return await func(update, context)
    return wrapper


# ── Helpers ────────────────────────────────────────────────────
def hoy_local() -> date:
    return datetime.now(TZ).date()


def estado_emoji(estado: str, dias_restantes: int) -> str:
    if estado == "vencida" or dias_restantes <= 0:
        return "🔴"
    if dias_restantes <= 7:
        return "🟡"
    return "🟢"


def markdown_escape(text: str) -> str:
    """Escapa caracteres especiales de Markdown para evitar errores de parseo."""
    if not text:
        return ""
    # Caracteres que pueden romper el modo Markdown de Telegram
    chars = ["_", "*", "`", "["]
    for char in chars:
        text = text.replace(char, f"\\{char}")
    return text


def formato_fecha(val) -> str:
    if val is None:
        return "—"
    if hasattr(val, "date"):
        val = val.date()
    return val.isoformat()


def calcular_dias_restantes(fecha_fin, trial_until, fecha_inicio) -> int:
    """Calcula días restantes de la suscripción."""
    hoy = hoy_local()
    # Normalizar a date
    for v in [fecha_fin, trial_until, fecha_inicio]:
        if v and hasattr(v, "date"):
            v = v.date()

    fin = fecha_fin or trial_until
    if fin and hasattr(fin, "date"):
        fin = fin.date()
    if not fin and fecha_inicio:
        if hasattr(fecha_inicio, "date"):
            fecha_inicio = fecha_inicio.date()
        fin = fecha_inicio + timedelta(days=30)
    if fin:
        return max((fin - hoy).days, 0)
    return 0


# ── /start ─────────────────────────────────────────────────────
@solo_admin
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 *Bot Gestión de Carteras*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Comandos disponibles:*\n\n"
        "🔹 /cuentas — Lista todas las cuentas\n"
        "🔹 /ver `<id>` — Detalle de una cuenta\n"
        "🔹 /plan `<id>` `<empleados>` `<días>` — Actualizar plan\n"
        "🔹 /permiso `<empleado_id>` `<cuenta_id>` — Rehabilitar descarga\n"
        "🔹 /empleados `<id>` — Empleados de una cuenta\n"
        "🔹 /sql `<query>` — Ejecutar SELECT\n\n"
        f"📅 Fecha local: `{hoy_local()}`\n"
        f"🆔 Tu ID: `{update.effective_user.id}`"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


# ── /cuentas ───────────────────────────────────────────────────
@solo_admin
async def cmd_cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT 
                    c.id, c.nombre, c.plan, c.estado_suscripcion,
                    c.max_empleados, c.fecha_fin, c.trial_until, c.fecha_inicio,
                    (SELECT COUNT(*) FROM empleados e WHERE e.cuenta_id = c.id) AS num_empleados,
                    (SELECT COUNT(*) FROM usuarios u WHERE u.role='cobrador' AND u.cuenta_id = c.id AND u.is_active=TRUE) AS cobradores_activos,
                    (SELECT STRING_AGG(username || ' (' || role || ')', ', ') 
                     FROM usuarios u WHERE u.cuenta_id = c.id AND u.is_active=TRUE) AS usuarios_lista
                FROM cuentas_admin c
                ORDER BY c.id
            """)
            rows = cur.fetchall()

        if not rows:
            await update.message.reply_text("📭 No hay cuentas registradas.")
            return

        hoy = hoy_local()
        activas = 0
        vencidas = 0
        lineas = ["📋 *TODAS LAS CUENTAS*\n━━━━━━━━━━━━━━━━━━━━━━\n"]

        for row in rows:
            (cid, nombre, plan, estado, max_emp, fecha_fin, trial_until,
             fecha_inicio, num_emp, cobr_activos, usuarios_lista) = row

            dias = calcular_dias_restantes(fecha_fin, trial_until, fecha_inicio)
            emoji = estado_emoji(estado or "", dias)

            if dias <= 0 or estado == "vencida":
                vencidas += 1
            else:
                activas += 1

            max_emp = max_emp or 1
            info_usuarios = f"\n    │ 👤 `{markdown_escape(usuarios_lista)}`" if usuarios_lista else ""
            
            lineas.append(
                f"*#{cid}* │ {markdown_escape(nombre or 'Sin nombre')}\n"
                f"    │ 📦 `{markdown_escape(plan or 'sin plan')}` │ 👥 {num_emp}/{max_emp} "
                f"│ ⏳ {dias} días │ {emoji} {markdown_escape(estado or '?')}"
                f"{info_usuarios}\n"
            )

        lineas.append(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Total:* {len(rows)} cuentas "
            f"({activas} activas, {vencidas} vencidas)"
        )

        await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /cuentas: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── /ver <id> ──────────────────────────────────────────────────
@solo_admin
async def cmd_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Uso: `/ver <id_cuenta>`", parse_mode="Markdown")
        return

    try:
        cuenta_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ El ID debe ser un número.")
        return

    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, nombre, plan, estado_suscripcion, max_empleados,
                       max_daily_routes, fecha_inicio, fecha_fin, trial_until,
                       daily_routes_date, daily_routes_empleados, timezone_default
                FROM cuentas_admin WHERE id = %s
            """, (cuenta_id,))
            cuenta = cur.fetchone()

            if not cuenta:
                await update.message.reply_text(f"❌ Cuenta #{cuenta_id} no encontrada.")
                return

            (cid, nombre, plan, estado, max_emp, max_routes, f_inicio, f_fin,
             trial, dr_date, dr_empleados, tz_default) = cuenta

            max_emp = max_emp or 1
            max_routes = max_routes or max_emp

            # Contar empleados
            cur.execute("SELECT COUNT(*) FROM empleados WHERE cuenta_id = %s", (cuenta_id,))
            num_empleados = cur.fetchone()[0] or 0

            # Contar cobradores activos / inactivos
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE is_active = TRUE),
                    COUNT(*) FILTER (WHERE is_active = FALSE)
                FROM usuarios WHERE role='cobrador' AND cuenta_id = %s
            """, (cuenta_id,))
            cobr_row = cur.fetchone()
            cobr_activos = cobr_row[0] or 0
            cobr_inactivos = cobr_row[1] or 0

            # Descargas hoy
            descargas_hoy = 0
            hoy = hoy_local()
            if dr_date:
                dr_date_val = dr_date
                if hasattr(dr_date_val, "date"):
                    dr_date_val = dr_date_val.date()
                if dr_date_val == hoy and isinstance(dr_empleados, dict):
                    descargas_hoy = len(dr_empleados)

            dias = calcular_dias_restantes(f_fin, trial, f_inicio)

        texto = (
            f"📋 *CUENTA #{cid}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Nombre:*       {markdown_escape(nombre or 'Sin nombre')}\n"
            f"📦 *Plan:*         `{markdown_escape(plan or 'sin plan')}`\n"
            f"📊 *Estado:*       {estado_emoji(estado or '', dias)} {markdown_escape(estado or '?')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *Empleados:*    {num_empleados} / {max_emp} (max)\n"
            f"🛣️ *Rutas diarias:* {max_routes} (max)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Inicio:*       `{formato_fecha(f_inicio)}`\n"
            f"📅 *Fin:*          `{formato_fecha(f_fin)}`\n"
            f"⏳ *Días restantes:* {dias}\n"
            f"🆓 *Trial hasta:*  `{formato_fecha(trial)}`\n"
            f"🌐 *Timezone:*     `{markdown_escape(tz_default or 'no definida')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 *Cobradores activos:*   {cobr_activos}\n"
            f"🔴 *Cobradores inactivos:* {cobr_inactivos}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 *Descargas hoy:* {descargas_hoy} / {max_routes}\n"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /ver: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── /plan <id> <empleados> <días> ──────────────────────────────
@solo_admin
async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ Uso: `/plan <id_cuenta> <max_empleados> <días>`\n"
            "Ejemplo: `/plan 20 5 30`",
            parse_mode="Markdown",
        )
        return

    try:
        cuenta_id = int(context.args[0])
        max_emp = int(context.args[1])
        dias = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Todos los argumentos deben ser números.")
        return

    # Determinar nombre del plan
    plan_nombre = f"plan_{max_emp}"
    hoy = hoy_local()
    fecha_fin = hoy + timedelta(days=dias)

    try:
        with get_cursor() as cur:
            # Verificar que la cuenta existe
            cur.execute("SELECT nombre FROM cuentas_admin WHERE id = %s", (cuenta_id,))
            row = cur.fetchone()
            if not row:
                await update.message.reply_text(f"❌ Cuenta #{cuenta_id} no encontrada.")
                return
            nombre = row[0]

            # Actualizar plan
            cur.execute("""
                UPDATE cuentas_admin 
                SET plan = %s,
                    max_empleados = %s,
                    max_daily_routes = %s,
                    estado_suscripcion = 'activa',
                    fecha_inicio = %s,
                    fecha_fin = %s,
                    trial_until = NULL
                WHERE id = %s
            """, (plan_nombre, max_emp, max_emp, hoy, fecha_fin, cuenta_id))

        texto = (
            f"✅ *PLAN ACTUALIZADO — Cuenta #{cuenta_id}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Cuenta: {nombre}\n"
            f"📦 Plan: `{plan_nombre}`\n"
            f"👥 Max empleados: {max_emp}\n"
            f"🛣️ Max rutas: {max_emp}\n"
            f"📅 Inicio: `{hoy}`\n"
            f"📅 Nuevo vencimiento: `{fecha_fin}`\n"
            f"📊 Estado: 🟢 activa\n"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /plan: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── /permiso <empleado_id> <cuenta_id> ─────────────────────────
@solo_admin
async def cmd_permiso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Uso: `/permiso <empleado_id> <cuenta_id>`\n"
            "Ejemplo: `/permiso 1234567 20`",
            parse_mode="Markdown",
        )
        return

    empleado_id = context.args[0]
    try:
        cuenta_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ El ID de cuenta debe ser un número.")
        return

    hoy = hoy_local()
    ayer = hoy - timedelta(days=1)

    try:
        with get_cursor() as cur:
            # Verificar que el empleado existe y pertenece a la cuenta
            cur.execute("""
                SELECT nombre FROM empleados 
                WHERE identificacion = %s AND cuenta_id = %s
            """, (empleado_id, cuenta_id))
            row = cur.fetchone()

            if not row:
                await update.message.reply_text(
                    f"❌ Empleado `{empleado_id}` no encontrado en cuenta #{cuenta_id}.",
                    parse_mode="Markdown",
                )
                return

            nombre = row[0]

            # Rehabilitar permisos: descargar=TRUE, subir=TRUE, fecha_accion=ayer
            cur.execute("""
                UPDATE empleados 
                SET descargar = TRUE, subir = TRUE, fecha_accion = %s
                WHERE identificacion = %s AND cuenta_id = %s
            """, (ayer, empleado_id, cuenta_id))

            # Verificar estado final
            cur.execute("""
                SELECT descargar, subir, fecha_accion 
                FROM empleados 
                WHERE identificacion = %s AND cuenta_id = %s
            """, (empleado_id, cuenta_id))
            estado = cur.fetchone()
            descargar, subir, fecha_accion = estado

            puede_descargar = bool(descargar) and (fecha_accion is None or fecha_accion < hoy)
            puede_subir = bool(subir) and (fecha_accion is None or fecha_accion < hoy)

        texto = (
            f"✅ *PERMISOS REHABILITADOS*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Empleado: {nombre}\n"
            f"🆔 ID: `{empleado_id}`\n"
            f"🏢 Cuenta: #{cuenta_id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 Descargar: {'✅' if puede_descargar else '❌'}\n"
            f"📤 Subir: {'✅' if puede_subir else '❌'}\n"
            f"📅 Fecha acción: `{formato_fecha(fecha_accion)}`\n"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /permiso: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── /empleados <id> ────────────────────────────────────────────
@solo_admin
async def cmd_empleados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso: `/empleados <id_cuenta>`", parse_mode="Markdown"
        )
        return

    try:
        cuenta_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ El ID debe ser un número.")
        return

    hoy = hoy_local()

    try:
        with get_cursor() as cur:
            # Info de la cuenta
            cur.execute("SELECT nombre FROM cuentas_admin WHERE id = %s", (cuenta_id,))
            cuenta_row = cur.fetchone()
            if not cuenta_row:
                await update.message.reply_text(f"❌ Cuenta #{cuenta_id} no encontrada.")
                return

            # Empleados con permisos y estado de cobrador
            cur.execute("""
                SELECT 
                    e.identificacion,
                    e.nombre,
                    e.descargar,
                    e.subir,
                    e.fecha_accion,
                    u.is_active AS cobrador_activo,
                    u.username
                FROM empleados e
                LEFT JOIN usuarios u 
                    ON u.empleado_identificacion = e.identificacion 
                    AND u.role = 'cobrador' 
                    AND u.cuenta_id = e.cuenta_id
                WHERE e.cuenta_id = %s
                ORDER BY e.nombre_completo
            """, (cuenta_id,))
            empleados = cur.fetchall()

        if not empleados:
            await update.message.reply_text(
                f"📭 No hay empleados en la cuenta #{cuenta_id}."
            )
            return

        lineas = [
            f"👥 *EMPLEADOS — Cuenta #{cuenta_id}* ({cuenta_row[0]})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        for emp in empleados:
            (eid, nombre, descargar, subir, fecha_accion, cobr_activo, username) = emp

            puede_desc = bool(descargar) and (
                fecha_accion is None or (hasattr(fecha_accion, '__lt__') and fecha_accion < hoy)
            )
            puede_sub = bool(subir) and (
                fecha_accion is None or (hasattr(fecha_accion, '__lt__') and fecha_accion < hoy)
            )

            cobr_status = ""
            if cobr_activo is True:
                cobr_status = f" │ 🟢 @{username}"
            elif cobr_activo is False:
                cobr_status = f" │ 🔴 @{username}"
            else:
                cobr_status = " │ ⚪ sin cobrador"

            lineas.append(
                f"*{markdown_escape(nombre or 'Sin nombre')}*\n"
                f"  🆔 `{eid}` {markdown_escape(cobr_status)}\n"
                f"  📥 {'✅' if puede_desc else '❌'} desc "
                f"│ 📤 {'✅' if puede_sub else '❌'} sub "
                f"│ 📅 `{formato_fecha(fecha_accion)}`\n"
            )

        lineas.append(f"━━━━━━━━━━━━━━━━━━━━━━\n*Total:* {len(empleados)} empleados")

        # Telegram tiene límite de 4096 chars por mensaje
        texto = "\n".join(lineas)
        if len(texto) > 4000:
            # Partir en chunks
            for i in range(0, len(texto), 4000):
                chunk = texto[i:i + 4000]
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /empleados: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── /sql <query> ───────────────────────────────────────────────
@solo_admin
async def cmd_sql(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ejecuta un SELECT en la base de datos. Solo lectura."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso: `/sql SELECT ...`", parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)

    # Seguridad: solo permitir SELECT
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        await update.message.reply_text(
            "⛔ Solo se permiten consultas SELECT por seguridad."
        )
        return

    # Bloquear keywords peligrosas
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                  "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "EXEC"]
    for word in forbidden:
        if word in query_upper:
            await update.message.reply_text(
                f"⛔ Palabra clave `{word}` no permitida en /sql."
            , parse_mode="Markdown")
            return

    try:
        with get_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description] if cur.description else []

        if not rows:
            await update.message.reply_text("📭 Sin resultados.")
            return

        # Formatear como tabla
        lineas = [" | ".join(col_names), "─" * 40]
        for row in rows[:50]:  # Máximo 50 filas
            lineas.append(" | ".join(str(v) for v in row))

        if len(rows) > 50:
            lineas.append(f"\n... y {len(rows) - 50} filas más")

        texto = f"```\n{chr(10).join(lineas)}\n```"

        if len(texto) > 4000:
            for i in range(0, len(texto), 4000):
                chunk = texto[i:i + 4000]
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /sql: {e}")
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


# ── Mensaje no reconocido ──────────────────────────────────────
@solo_admin
async def msg_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤔 Comando no reconocido. Usa /start para ver los comandos disponibles."
    )


# ── Main ───────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado en .env")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Registrar handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cuentas", cmd_cuentas))
    app.add_handler(CommandHandler("ver", cmd_ver))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("permiso", cmd_permiso))
    app.add_handler(CommandHandler("empleados", cmd_empleados))
    app.add_handler(CommandHandler("sql", cmd_sql))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_desconocido))

    print("🤖 Bot iniciado. Esperando comandos...")
    print(f"🔒 Solo responde a Telegram ID: {ADMIN_ID}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
