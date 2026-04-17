from bitacoras import bitacoras
from flask import render_template, request, session, redirect, url_for, flash
from models import BitacoraAccesos, BitacoraEventos, BitacoraSistema, db
from autentificacion.routes import rol_requerido
from sqlalchemy import or_
import datetime

POR_PAGINA = 15

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def parsear_fechas():
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin    = request.args.get('fecha_fin', '').strip()
    try:
        inicio = datetime.datetime.strptime(fecha_inicio, '%Y-%m-%d') if fecha_inicio else None
        fin    = datetime.datetime.strptime(fecha_fin, '%Y-%m-%d').replace(
                     hour=23, minute=59, second=59) if fecha_fin else None
    except ValueError:
        inicio = fin = None
    return inicio, fin


# ─────────────────────────────────────────────
# Catálogos centralizados
# ─────────────────────────────────────────────

EVENTOS_ACCESO = [
    'LOGIN',
    'LOGIN_BLOQUEADO',
    'LOGOUT',
    'LOGOUT_INACTIVIDAD',
]

RESULTADOS_ACCESO = [
    'EXITOSO',
    'CONTRASENIA_INCORRECTA',
    'BLOQUEADO_POR_INTENTOS',
    'BLOQUEADO',
    'CUENTA_DESACTIVADA',
    'ROL_DESACTIVADO',
    'SESION_EXPIRADA',
]

MODULOS_EVENTOS = [
    'Usuarios',
    'Roles',
    'Proveedores',
    'MateriasPrimas',
    'UnidadesMedida',
    'Productos',
    'Recetas',
    'DetalleReceta',
    'Compras',
    'OrdenesProduccion',
    'Ventas',
    'Mermas',
    'MiniRecetas',
    'CorteCaja',
    'Produccion',
]

ACCIONES_EVENTOS = [
    'CREAR',
    'EDITAR',
    'ELIMINAR',
    'ACTIVAR',
    'DESACTIVAR',
    'AUTO_DESACTIVAR',
    'CAMBIO_CONTRASENIA',
    'COMPLETADO',
    'CANCELADO',
    'CANCELAR',
    'CONFIRMAR',
    'TERMINADA',
    'TERMINAR',
    'CORTE',
    'CREAR_ORDEN_PRODUCCION',
    'CANCELAR_CIERRE_DIA',
]

MODULOS_SISTEMA = [
    'Usuarios',
    'Roles',
    'Proveedores',
    'MateriasPrimas',
    'UnidadesMedida',
    'Productos',
    'Recetas',
    'DetalleReceta',
    'Compras',
    'OrdenesProduccion',
    'Ventas',
    'Mermas',
    'MiniRecetas',
    'CorteCaja',
    'Produccion',
]

NIVELES_SISTEMA = ['ERROR', 'WARNING', 'INFO']


# ─────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────

@bitacoras.route("/bitacoras")
@rol_requerido('Administrador')
def index():
    tab    = request.args.get('tab', 'accesos')
    pagina = request.args.get('pagina', 1, type=int)
    inicio, fin = parsear_fechas()

    # ── Bitácora de Accesos ──────────────────────────────────
    accesos_query      = BitacoraAccesos.query
    filtro_usuario_acc = request.args.get('usuario_acc', '').strip()
    filtro_evento      = request.args.get('evento', '').strip()
    filtro_resultado   = request.args.get('resultado', '').strip()

    if filtro_usuario_acc:
        accesos_query = accesos_query.filter(
            BitacoraAccesos.nombreUsuario.ilike(f'%{filtro_usuario_acc}%'))
    if filtro_evento:
        accesos_query = accesos_query.filter(BitacoraAccesos.evento == filtro_evento)
    if filtro_resultado:
        accesos_query = accesos_query.filter(BitacoraAccesos.resultado == filtro_resultado)
    if inicio:
        accesos_query = accesos_query.filter(BitacoraAccesos.fecha >= inicio)
    if fin:
        accesos_query = accesos_query.filter(BitacoraAccesos.fecha <= fin)

    accesos_query = accesos_query.order_by(BitacoraAccesos.fecha.desc())

    # ── Bitácora de Eventos ──────────────────────────────────
    eventos_query    = BitacoraEventos.query
    filtro_usuario_ev = request.args.get('usuario_ev', '').strip()
    filtro_modulo    = request.args.get('modulo', '').strip()
    filtro_accion    = request.args.get('accion', '').strip()

    if filtro_usuario_ev:
        eventos_query = eventos_query.filter(
            BitacoraEventos.nombreUsuario.ilike(f'%{filtro_usuario_ev}%'))
    if filtro_modulo:
        eventos_query = eventos_query.filter(BitacoraEventos.modulo == filtro_modulo)
    if filtro_accion:
        eventos_query = eventos_query.filter(BitacoraEventos.accion == filtro_accion)
    if inicio:
        eventos_query = eventos_query.filter(BitacoraEventos.fecha >= inicio)
    if fin:
        eventos_query = eventos_query.filter(BitacoraEventos.fecha <= fin)

    eventos_query = eventos_query.order_by(BitacoraEventos.fecha.desc())

    # ── Bitácora de Sistema ──────────────────────────────────
    sistema_query      = BitacoraSistema.query
    filtro_nivel       = request.args.get('nivel', '').strip()
    filtro_modulo_sis  = request.args.get('modulo_sis', '').strip()
    filtro_busqueda    = request.args.get('busqueda', '').strip()

    if filtro_nivel:
        sistema_query = sistema_query.filter(BitacoraSistema.nivel == filtro_nivel)
    if filtro_modulo_sis:
        sistema_query = sistema_query.filter(BitacoraSistema.modulo == filtro_modulo_sis)
    if filtro_busqueda:
        sistema_query = sistema_query.filter(
            or_(
                BitacoraSistema.mensaje.ilike(f'%{filtro_busqueda}%'),
                BitacoraSistema.detalles.ilike(f'%{filtro_busqueda}%'),
            ))
    if inicio:
        sistema_query = sistema_query.filter(BitacoraSistema.fecha >= inicio)
    if fin:
        sistema_query = sistema_query.filter(BitacoraSistema.fecha <= fin)

    sistema_query = sistema_query.order_by(BitacoraSistema.fecha.desc())

    # ── Paginación ───────────────────────────────────────────
    accesos_pag = accesos_query.paginate(
        page=pagina if tab == 'accesos' else 1, per_page=POR_PAGINA, error_out=False)
    eventos_pag = eventos_query.paginate(
        page=pagina if tab == 'eventos' else 1, per_page=POR_PAGINA, error_out=False)
    sistema_pag = sistema_query.paginate(
        page=pagina if tab == 'sistema' else 1, per_page=POR_PAGINA, error_out=False)

    return render_template(
        "bitacoras/bitacoras.html",
        tab=tab,
        accesos_pag=accesos_pag,
        eventos_pag=eventos_pag,
        sistema_pag=sistema_pag,
        # Filtros accesos
        filtro_usuario_acc=filtro_usuario_acc,
        filtro_evento=filtro_evento,
        filtro_resultado=filtro_resultado,
        # Filtros eventos
        filtro_usuario_ev=filtro_usuario_ev,
        filtro_modulo=filtro_modulo,
        filtro_accion=filtro_accion,
        # Filtros sistema
        filtro_nivel=filtro_nivel,
        filtro_modulo_sis=filtro_modulo_sis,
        filtro_busqueda=filtro_busqueda,
        # Rango de fechas
        fecha_inicio=request.args.get('fecha_inicio', ''),
        fecha_fin=request.args.get('fecha_fin', ''),
        # Catálogos para los <select>
        eventos_opciones=EVENTOS_ACCESO,
        resultado_opciones=RESULTADOS_ACCESO,
        modulos_opciones=MODULOS_EVENTOS,
        acciones_opciones=ACCIONES_EVENTOS,
        modulos_sis_opciones=MODULOS_SISTEMA,
        niveles_opciones=NIVELES_SISTEMA,
    )