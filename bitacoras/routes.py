from bitacoras import bitacoras
from flask import render_template, request, session, redirect, url_for, flash
from models import BitacoraAccesos, BitacoraEventos, BitacoraSistema, db
from autentificacion.routes import rol_requerido
from sqlalchemy import or_
import datetime

POR_PAGINA = 15

# Funciones extras

def parsear_fechas():
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin = request.args.get('fecha_fin', '').strip()
    try:
        inicio = datetime.datetime.strptime(fecha_inicio, '%Y-%m-%d') if fecha_inicio else None
        fin = datetime.datetime.strptime(fecha_fin, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59) if fecha_fin else None
    except ValueError:
        inicio = fin = None
    return inicio, fin


# Rutas :s

@bitacoras.route("/bitacoras")
@rol_requerido('Administrador')
def index():
    tab = request.args.get('tab', 'accesos')
    pagina = request.args.get('pagina', 1, type=int)
    inicio, fin = parsear_fechas()

    accesos_query = BitacoraAccesos.query
    filtro_usuario_acc = request.args.get('usuario_acc', '').strip()
    filtro_evento = request.args.get('evento', '').strip()
    filtro_resultado = request.args.get('resultado', '').strip()

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

    eventos_query = BitacoraEventos.query
    filtro_usuario_ev = request.args.get('usuario_ev', '').strip()
    filtro_modulo = request.args.get('modulo', '').strip()
    filtro_accion = request.args.get('accion', '').strip()

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

    sistema_query = BitacoraSistema.query
    filtro_nivel = request.args.get('nivel', '').strip()
    filtro_modulo_sis = request.args.get('modulo_sis', '').strip()
    filtro_busqueda = request.args.get('busqueda', '').strip()

    if filtro_nivel:
        sistema_query = sistema_query.filter(BitacoraSistema.nivel == filtro_nivel)
    if filtro_modulo_sis:
        sistema_query = sistema_query.filter(BitacoraSistema.modulo == filtro_modulo_sis)
    if filtro_busqueda:
        sistema_query = sistema_query.filter(
            or_(
                BitacoraSistema.mensaje.ilike(f'%{filtro_busqueda}%'),
                BitacoraSistema.detalles.ilike(f'%{filtro_busqueda}%')
            ))
    if inicio:
        sistema_query = sistema_query.filter(BitacoraSistema.fecha >= inicio)
    if fin:
        sistema_query = sistema_query.filter(BitacoraSistema.fecha <= fin)

    sistema_query = sistema_query.order_by(BitacoraSistema.fecha.desc())

    accesos_pag = accesos_query.paginate(
        page=pagina if tab == 'accesos' else 1, per_page=POR_PAGINA, error_out=False)
    eventos_pag = eventos_query.paginate(
        page=pagina if tab == 'eventos' else 1, per_page=POR_PAGINA, error_out=False)
    sistema_pag = sistema_query.paginate(
        page=pagina if tab == 'sistema' else 1, per_page=POR_PAGINA, error_out=False)

    eventos_opciones = ['LOGIN', 'LOGIN_BLOQUEADO', 'LOGOUT', 'LOGOUT_INACTIVIDAD']
    resultado_opciones = ['EXITOSO', 'CONTRASENIA_INCORRECTA', 'BLOQUEADO_POR_INTENTOS',
                          'BLOQUEADO', 'CUENTA_DESACTIVADA', 'ROL_DESACTIVADO', 'SESION_EXPIRADA']
    modulos_opciones = ['Usuarios', 'Roles']
    acciones_opciones = ['CREAR', 'EDITAR', 'ACTIVAR', 'DESACTIVAR', 'CAMBIO_CONTRASENIA']
    niveles_opciones = ['ERROR', 'WARNING', 'INFO']

    return render_template(
        "bitacoras/bitacoras.html",
        tab=tab,
        accesos_pag=accesos_pag,
        eventos_pag=eventos_pag,
        sistema_pag=sistema_pag,
        filtro_usuario_acc=filtro_usuario_acc,
        filtro_evento=filtro_evento,
        filtro_resultado=filtro_resultado,
        filtro_usuario_ev=filtro_usuario_ev,
        filtro_modulo=filtro_modulo,
        filtro_accion=filtro_accion,
        filtro_nivel=filtro_nivel,
        filtro_modulo_sis=filtro_modulo_sis,
        filtro_busqueda=filtro_busqueda,
        fecha_inicio=request.args.get('fecha_inicio', ''),
        fecha_fin=request.args.get('fecha_fin', ''),
        eventos_opciones=eventos_opciones,
        resultado_opciones=resultado_opciones,
        modulos_opciones=modulos_opciones,
        acciones_opciones=acciones_opciones,
        niveles_opciones=niveles_opciones,
    )