from compras import comprass
from flask import render_template, request, redirect, url_for, flash, session
from models import (Compras, DetalleCompra, Proveedores, MateriasPrimas, UnidadesMedida, db)
from sqlalchemy import text
from flask_wtf.csrf import generate_csrf
import json
import datetime


def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


def login_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            flash('Debes iniciar sesión.', 'danger')
            return redirect(url_for('autentificacion.login'))
        return f(*args, **kwargs)
    return decorated


def rol_requerido(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('usuario_id'):
                flash('Debes iniciar sesión.', 'danger')
                return redirect(url_for('autentificacion.login'))
            if session.get('usuario_rol') not in roles:
                flash('No tienes permisos para acceder a esta sección.', 'danger')
                return redirect(url_for('inicio'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def ejecutar_sp_compras(accion, idCompra=None, idProveedor=None,
                         estatus=None, detalles=None, fecha=None):
    detalles_json = json.dumps(detalles) if detalles is not None else json.dumps([])
    
    if fecha is None:
        fecha = datetime.datetime.now().strftime('%Y-%m-%d')

    sql = text("""
        CALL sp_gestion_compras(
            :accion, :idCompra, :idProveedor, :idUsuario,
            :estatus, :detalles,
            :ip, :ejecutadoPor, :fecha,
            @p_resultado, @p_idGenerado
        )
    """)

    db.session.execute(sql, {
        'accion': accion,
        'idCompra': idCompra,
        'idProveedor': idProveedor,
        'idUsuario': session.get('usuario_id'),
        'estatus': estatus,
        'detalles': detalles_json,
        'ip': get_ip(),
        'ejecutadoPor': session.get('usuario_id'),
        'fecha': fecha
    })

    row = db.session.execute(text("SELECT @p_resultado, @p_idGenerado")).fetchone()
    return row[0], row[1]


def _serializar_compras(lista_compras):
    resultado = []
    for c in lista_compras:
        detalles = []
        for d in c.detalle_compras:
            nombre_mp = d.materia_prima.nombre if d.materia_prima else '—'
            nombre_unidad = '—'
            if d.idUnidadM:
                u = UnidadesMedida.query.get(d.idUnidadM)
                nombre_unidad = u.nombre if u else '—'
            else:
                if d.materia_prima and d.materia_prima.tipo == 'Solido':
                    nombre_unidad = 'g'
                elif d.materia_prima and d.materia_prima.tipo == 'Liquido':
                    nombre_unidad = 'ml'
                else:
                    nombre_unidad = 'Por cantidad'

            detalles.append({
                'idDetalleC': d.idDetalleC,
                'idMateriaP': d.idMateriaP,
                'idUnidadM': d.idUnidadM,
                'nombreMP': nombre_mp,
                'nombreUnidad': nombre_unidad,
                'cantidad': float(d.cantidad),
                'precio': float(d.precio),
            })

        resultado.append({
            'idCompra': c.idCompra,
            'idProveedor': c.idProveedor,
            'nombreProveedor': c.proveedor.nombre if c.proveedor else '—',
            'fecha': c.fecha.strftime('%Y-%m-%d'),
            'fechaDisplay': c.fecha.strftime('%d/%m/%Y'),
            'estatus': c.estatus,
            'detalles': detalles,
        })
    return resultado


@comprass.route('/compras', methods=['GET'])
@rol_requerido('Administrador')
def compras():
    lista_compras = (
        Compras.query
        .join(Compras.proveedor)
        .order_by(Compras.fecha.desc())
        .all()
    )

    proveedores = Proveedores.query.filter_by(estatus=1).order_by(Proveedores.nombre).all()
    materias = MateriasPrimas.query.filter_by(estatus=1).order_by(MateriasPrimas.nombre).all()
    unidades = UnidadesMedida.query.filter_by(estatus=1).order_by(UnidadesMedida.nombre).all()

    compras_json = json.dumps(_serializar_compras(lista_compras))
    unidades_json = json.dumps([{
        'idUnidadM': u.idUnidadM,
        'nombre': u.nombre,
        'tipo': u.tipo,
        'equivalente': float(u.equivalente),
    } for u in unidades])

    return render_template(
        'compras/compras.html',
        compras=lista_compras,
        proveedores=proveedores,
        materias_primas=materias,
        compras_json=compras_json,
        unidades_medida_json=unidades_json,
        csrf_token=generate_csrf(),
        layout='layoutAdmin.html',
    )


@comprass.route('/compras/registrar', methods=['POST'])
@rol_requerido('Administrador')
def registrar_compra():
    try:
        id_proveedor = request.form.get('idProveedor', '').strip()
        fecha = request.form.get('fecha', '')
        detalles_raw = request.form.get('detalles', '[]')

        if not id_proveedor:
            flash('Selecciona un proveedor.', 'danger')
            return redirect(url_for('comprass.compras'))

        if not fecha:
            flash('Selecciona una fecha.', 'danger')
            return redirect(url_for('comprass.compras'))

        try:
            detalles = json.loads(detalles_raw)
        except (json.JSONDecodeError, ValueError):
            flash('Error al procesar los insumos. Intenta de nuevo.', 'danger')
            return redirect(url_for('comprass.compras'))

        if not detalles:
            flash('Debes agregar al menos un insumo.', 'danger')
            return redirect(url_for('comprass.compras'))

        proveedor_obj = Proveedores.query.get(int(id_proveedor))
        if not proveedor_obj or not proveedor_obj.estatus:
            flash('El proveedor seleccionado no es válido.', 'danger')
            return redirect(url_for('comprass.compras'))

        detalles_sp = []
        for d in detalles:
            id_unidad = d.get('idUnidadM')
            if id_unidad is not None:
                id_unidad = int(id_unidad) if id_unidad else None
            else:
                id_unidad = None

            detalles_sp.append({
                'idMateriaP': int(d['idMateriaP']),
                'idUnidadM': id_unidad,
                'cantidad': float(d['cantidad']),
                'precio': float(d['precio']),
            })

        resultado, id_generado = ejecutar_sp_compras(
            accion='INSERT',
            idProveedor=int(id_proveedor),
            detalles=detalles_sp,
            fecha=fecha
        )
        db.session.commit()

        if resultado and resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            flash('Compra registrada correctamente con estado Pendiente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error inesperado: {str(e)}', 'danger')

    return redirect(url_for('comprass.compras'))


@comprass.route('/compras/editar/<int:id>', methods=['POST'])
@rol_requerido('Administrador')
def editar_compra(id):
    try:
        id_proveedor = request.form.get('idProveedor', '').strip()
        fecha = request.form.get('fecha', '')
        detalles_raw = request.form.get('detalles', '[]')

        if not id_proveedor:
            flash('Selecciona un proveedor.', 'danger')
            return redirect(url_for('comprass.compras'))

        if not fecha:
            flash('Selecciona una fecha.', 'danger')
            return redirect(url_for('comprass.compras'))

        compra_obj = Compras.query.get(id)
        if not compra_obj:
            flash('La compra no existe.', 'danger')
            return redirect(url_for('comprass.compras'))

        if compra_obj.estatus != 'Pendiente':
            flash('Solo se pueden editar compras en estado Pendiente.', 'danger')
            return redirect(url_for('comprass.compras'))

        try:
            detalles = json.loads(detalles_raw)
        except (json.JSONDecodeError, ValueError):
            flash('Error al procesar los insumos.', 'danger')
            return redirect(url_for('comprass.compras'))

        if not detalles:
            flash('Debes agregar al menos un insumo.', 'danger')
            return redirect(url_for('comprass.compras'))

        detalles_sp = []
        for d in detalles:
            id_unidad = d.get('idUnidadM')
            if id_unidad is not None:
                id_unidad = int(id_unidad) if id_unidad else None
            else:
                id_unidad = None

            detalles_sp.append({
                'idMateriaP': int(d['idMateriaP']),
                'idUnidadM': id_unidad,
                'cantidad': float(d['cantidad']),
                'precio': float(d['precio']),
            })

        resultado, _ = ejecutar_sp_compras(
            accion='UPDATE',
            idCompra=id,
            idProveedor=int(id_proveedor),
            detalles=detalles_sp,
            fecha=fecha
        )
        db.session.commit()

        if resultado and resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            flash('Compra actualizada correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error inesperado: {str(e)}', 'danger')

    return redirect(url_for('comprass.compras'))


@comprass.route('/compras/completar/<int:id>', methods=['POST'])
@rol_requerido('Administrador')
def completar_compra(id):
    try:
        detalles_raw = request.form.get('detalles', '[]')

        compra_obj = Compras.query.get(id)
        if not compra_obj:
            flash('La compra no existe.', 'danger')
            return redirect(url_for('comprass.compras'))

        if compra_obj.estatus != 'Pendiente':
            flash('Solo se pueden completar compras en estado Pendiente.', 'danger')
            return redirect(url_for('comprass.compras'))

        try:
            detalles = json.loads(detalles_raw)
        except (json.JSONDecodeError, ValueError):
            flash('Error al procesar los insumos recibidos.', 'danger')
            return redirect(url_for('comprass.compras'))

        if not detalles:
            flash('Debes incluir al menos un insumo para completar la compra.', 'danger')
            return redirect(url_for('comprass.compras'))

        detalles_sp = []
        for d in detalles:
            id_unidad = d.get('idUnidadM')
            if id_unidad is not None:
                id_unidad = int(id_unidad) if id_unidad else None
            else:
                id_unidad = None

            detalles_sp.append({
                'idMateriaP': int(d['idMateriaP']),
                'idUnidadM': id_unidad,
                'cantidad': float(d['cantidad']),
                'precio': float(d['precio']),
            })

        resultado_update, _ = ejecutar_sp_compras(
            accion='UPDATE',
            idCompra=id,
            idProveedor=compra_obj.idProveedor,
            detalles=detalles_sp,
            fecha=compra_obj.fecha.strftime('%Y-%m-%d')
        )

        if resultado_update and resultado_update.startswith('ERROR'):
            db.session.rollback()
            flash(resultado_update.replace('ERROR: ', ''), 'danger')
            return redirect(url_for('comprass.compras'))

        resultado_status, _ = ejecutar_sp_compras(
            accion='CHANGE_STATUS',
            idCompra=id,
            estatus='Completado',
            fecha=compra_obj.fecha.strftime('%Y-%m-%d')
        )
        db.session.commit()

        if resultado_status and resultado_status.startswith('ERROR'):
            flash(resultado_status.replace('ERROR: ', ''), 'danger')
        else:
            flash('Compra completada. El stock de materias primas ha sido actualizado.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error inesperado: {str(e)}', 'danger')

    return redirect(url_for('comprass.compras'))


@comprass.route('/compras/cancelar/<int:id>')
@rol_requerido('Administrador')
def cancelar_compra(id):
    try:
        compra_obj = Compras.query.get(id)
        if not compra_obj:
            flash('La compra no existe.', 'danger')
            return redirect(url_for('comprass.compras'))

        if compra_obj.estatus != 'Pendiente':
            flash('Solo se pueden cancelar compras en estado Pendiente.', 'danger')
            return redirect(url_for('comprass.compras'))

        resultado, _ = ejecutar_sp_compras(
            accion='CHANGE_STATUS',
            idCompra=id,
            estatus='Cancelado',
            fecha=compra_obj.fecha.strftime('%Y-%m-%d')
        )
        db.session.commit()

        if resultado and resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            flash('Compra cancelada correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error inesperado: {str(e)}', 'danger')

    return redirect(url_for('comprass.compras'))