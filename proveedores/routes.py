from . import proveedores
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import generate_csrf, validate_csrf
from models import Proveedores, db
from autentificacion.routes import rol_requerido
from sqlalchemy import text
import re
import forms


def validar_campos_proveedor(nombre, correo, telefono, direccion, es_edicion=False):
    if not nombre or not nombre.strip():
        return False, 'El nombre del proveedor es requerido'
    if len(nombre.strip()) < 3:
        return False, 'El nombre debe tener al menos 3 caracteres'
    if len(nombre.strip()) > 100:
        return False, 'El nombre no puede superar los 100 caracteres'
    if not re.match(r"^[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s\.\-']+$", nombre.strip()):
        return False, 'El nombre solo puede contener letras, espacios, puntos, guiones y apóstrofes'
    if not correo or not correo.strip():
        return False, 'El correo electrónico es requerido'
    patron_email = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron_email, correo.strip()):
        return False, 'El formato del correo electrónico no es válido'
    if len(correo.strip()) > 100:
        return False, 'El correo no puede superar los 100 caracteres'
    if not telefono or not telefono.strip():
        return False, 'El teléfono es requerido'
    if not re.match(r'^[0-9+\-\s()]+$', telefono.strip()):
        return False, 'El teléfono solo puede contener números, +, -, espacios y paréntesis'
    if len(telefono.strip()) < 8:
        return False, 'El teléfono debe tener al menos 8 caracteres'
    if len(telefono.strip()) > 20:
        return False, 'El teléfono no puede superar los 20 caracteres'
    if not direccion or not direccion.strip():
        return False, 'La dirección es requerida'
    if len(direccion.strip()) > 200:
        return False, 'La dirección no puede superar los 200 caracteres'

    return True, None

def get_ip():
    from flask import request
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

def ejecutar_sp_proveedor(accion, idProveedor=None, nombre=None, correo=None,
                          telefono=None, direccion=None, estatus=None):
    sql = text("""
        CALL sp_gestion_proveedores(
            :accion, :idProveedor, :nombre, :correo, :telefono, :direccion, :estatus,
            :ip, :ejecutadoPor,
            @p_resultado, @p_idGenerado
        )
    """)
    db.session.execute(sql, {
        'accion': accion,
        'idProveedor': idProveedor,
        'nombre': nombre,
        'correo': correo,
        'telefono': telefono,
        'direccion': direccion,
        'estatus': estatus,
        'ip': get_ip(),
        'ejecutadoPor': session.get('usuario_id'),
    })
    row = db.session.execute(text("SELECT @p_resultado, @p_idGenerado")).fetchone()
    return row[0], row[1]

# Rutas para proveedores PIPOOOOOL :]

@proveedores.route("/proveedores", methods=['GET'])
@rol_requerido('Administrador')
def lista_proveedores():
    if not session.get('usuario_id'):
        flash('Debes iniciar sesión.', 'danger')
        return redirect(url_for('autentificacion.login'))
    
    form = forms.ProveedorForm()
    lista_proveedores = Proveedores.query.order_by(Proveedores.nombre.asc()).all()
    
    return render_template("proveedores/proveedores.html",
                         form=form,
                         proveedores=lista_proveedores,
                         csrf_token=generate_csrf())

@proveedores.route("/registrar-proveedor", methods=['POST'])
@rol_requerido('Administrador')
def registrar_proveedor():
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        return jsonify({'success': False, 'message': 'Token CSRF inválido'})
    
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'message': 'Debes iniciar sesión'})
    
    try:
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()

        valido, mensaje = validar_campos_proveedor(nombre, correo, telefono, direccion)
        if not valido:
            return jsonify({'success': False, 'message': mensaje})

        if Proveedores.query.filter(db.func.lower(Proveedores.nombre) == nombre.lower()).first():
            return jsonify({'success': False, 'message': 'El nombre del proveedor ya está registrado'})

        if Proveedores.query.filter(db.func.lower(Proveedores.correo) == correo.lower()).first():
            return jsonify({'success': False, 'message': 'El correo electrónico ya está registrado'})

        resultado, id_generado = ejecutar_sp_proveedor(
            accion='INSERT',
            nombre=nombre,
            correo=correo,
            telefono=telefono,
            direccion=direccion,
            estatus=1
        )

        if resultado.startswith('ERROR'):
            return jsonify({'success': False, 'message': resultado.replace('ERROR: ', '')})

        return jsonify({'success': True, 'message': 'Proveedor registrado exitosamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error inesperado: {str(e)}'})

@proveedores.route("/editar-proveedor/<int:id>", methods=['POST'])
@rol_requerido('Administrador')
def editar_proveedor(id):
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        return jsonify({'success': False, 'message': 'Token CSRF inválido'})
    
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'message': 'Debes iniciar sesión'})
    
    try:
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()

        proveedor_obj = Proveedores.query.get(id)
        if not proveedor_obj:
            return jsonify({'success': False, 'message': 'Proveedor no encontrado'})

        valido, mensaje = validar_campos_proveedor(nombre, correo, telefono, direccion, es_edicion=True)
        if not valido:
            return jsonify({'success': False, 'message': mensaje})

        if Proveedores.query.filter(
                db.func.lower(Proveedores.nombre) == nombre.lower(),
                Proveedores.idProveedor != id).first():
            return jsonify({'success': False, 'message': 'El nombre del proveedor ya está en uso por otro proveedor'})

        if Proveedores.query.filter(
                db.func.lower(Proveedores.correo) == correo.lower(),
                Proveedores.idProveedor != id).first():
            return jsonify({'success': False, 'message': 'El correo electrónico ya está en uso por otro proveedor'})

        resultado, _ = ejecutar_sp_proveedor(
            accion='UPDATE',
            idProveedor=id,
            nombre=nombre,
            correo=correo,
            telefono=telefono,
            direccion=direccion,
            estatus=proveedor_obj.estatus
        )

        if resultado.startswith('ERROR'):
            return jsonify({'success': False, 'message': resultado.replace('ERROR: ', '')})

        return jsonify({'success': True, 'message': 'Proveedor actualizado exitosamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error inesperado: {str(e)}'})

@proveedores.route("/cambiar-estatus-proveedor/<int:id>/<int:estatus>")
@rol_requerido('Administrador')
def cambiar_estatus_proveedor(id, estatus):
    if not session.get('usuario_id'):
        flash('Debes iniciar sesión.', 'danger')
        return redirect(url_for('autentificacion.login'))
    
    try:
        resultado, _ = ejecutar_sp_proveedor(
            accion='CHANGE_STATUS',
            idProveedor=id,
            estatus=estatus
        )

        if resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            estado_texto = "activado" if estatus == 1 else "desactivado"
            flash(f'Proveedor {estado_texto} exitosamente', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('proveedores.lista_proveedores'))