from autentificacion import autentificacion
from flask import render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask_mail import Mail, Message
from models import Usuarios, Roles, ResetContrasenia, IntentosFallidos, BitacoraAccesos, BitacoraSistema, db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text
from functools import wraps
import secrets, re, datetime
import forms

LAYOUTS = {
    'Administrador': 'layoutAdmin.html',
    'Ventas': 'layoutVentas.html',
    'Cocinero': 'layoutCocinero.html',
}

# Funciones generales para las rutas ;)

def login_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            flash('Debes iniciar sesión.', 'danger')
            return redirect(url_for('autentificacion.login'))
        return f(*args, **kwargs)
    return decorated


def get_redirect_by_role():
    """Determina a qué página redirigir según el rol del usuario"""
    usuario_rol = session.get('usuario_rol')
    
    if usuario_rol == 'Administrador':
        return url_for('dashboard.index')  # Asumiendo que tu dashboard está aquí
    elif usuario_rol == 'Ventas':
        return url_for('inicio')  # O la página principal para ventas
    elif usuario_rol == 'Cocinero':
        return url_for('inicio')  # O la página principal para cocinero
    else:
        return url_for('inicio')  # Página por defecto


def rol_requerido(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('usuario_id'):
                flash('Debes iniciar sesión.', 'danger')
                return redirect(url_for('autentificacion.login'))
            
            if session.get('usuario_rol') not in roles:
                flash('No tienes permisos para acceder a esta sección.', 'danger')
                return redirect(get_redirect_by_role())
            
            return f(*args, **kwargs)
        return decorated
    return decorator


# Funciones extrass

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


def get_navegador():
    return request.headers.get('User-Agent', 'Desconocido')[:255]


def validar_seguridad_contrasenia(contrasenia):
    if len(contrasenia) < 8:
        return False
    if not re.search(r'[A-Z]', contrasenia):
        return False
    if not re.search(r'[a-z]', contrasenia):
        return False
    if not re.search(r'[0-9]', contrasenia):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', contrasenia):
        return False
    return True


def validar_campos_usuario(nombre, usuario, email, contrasenia=None, es_edicion=False):
    if not nombre or not nombre.strip():
        return False, 'El nombre completo es requerido'
    if len(nombre.strip()) < 3:
        return False, 'El nombre debe tener al menos 3 caracteres'
    if len(nombre.strip()) > 100:
        return False, 'El nombre no puede superar los 100 caracteres'
    if not re.match(r"^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s'-]+$", nombre.strip()):
        return False, 'El nombre solo puede contener letras, espacios, guiones y apóstrofes'

    if not usuario or not usuario.strip():
        return False, 'El nombre de usuario es requerido'
    if len(usuario.strip()) < 3:
        return False, 'El nombre de usuario debe tener al menos 3 caracteres'
    if len(usuario.strip()) > 50:
        return False, 'El nombre de usuario no puede superar los 50 caracteres'
    if not re.match(r'^[a-zA-Z0-9_.-]+$', usuario.strip()):
        return False, 'El usuario solo puede contener letras, números, puntos, guiones y guiones bajos'
    if usuario.strip().startswith(('.', '-', '_')) or usuario.strip().endswith(('.', '-', '_')):
        return False, 'El usuario no puede comenzar ni terminar con punto, guión o guión bajo'

    if not email or not email.strip():
        return False, 'El correo electrónico es requerido'
    patron_email = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron_email, email.strip()):
        return False, 'El formato del correo electrónico no es válido'
    if len(email.strip()) > 150:
        return False, 'El correo no puede superar los 150 caracteres'
    dominios_bloqueados = ['mailinator.com', 'tempmail.com', 'guerrillamail.com',
                           'throwaway.email', 'fakeinbox.com', 'yopmail.com']
    dominio = email.strip().split('@')[-1].lower()
    if dominio in dominios_bloqueados:
        return False, 'No se permiten correos de dominios temporales'

    if not es_edicion and not contrasenia:
        return False, 'La contraseña es requerida'
    if contrasenia and contrasenia.strip():
        if not validar_seguridad_contrasenia(contrasenia):
            return False, ('La contraseña debe tener mínimo 8 caracteres, '
                           'una mayúscula, una minúscula, un número y un carácter especial')

    return True, None


def ejecutar_sp_usuario(accion, idUsuario=None, idRol=None, nombre=None,
                        usuario=None, contrasenia=None, estatus=None, email=None):
    sql = text("""
        CALL sp_gestion_usuarios(
            :accion, :idUsuario, :idRol, :nombre,
            :usuario, :contrasenia, :estatus, :email,
            :ip, :ejecutadoPor,
            @p_resultado, @p_idGenerado
        )
    """)
    db.session.execute(sql, {
        'accion': accion,
        'idUsuario': idUsuario,
        'idRol': idRol,
        'nombre': nombre,
        'usuario': usuario,
        'contrasenia': contrasenia,
        'estatus': estatus,
        'email': email,
        'ip': get_ip(),
        'ejecutadoPor': session.get('usuario_id'),
    })
    row = db.session.execute(text("SELECT @p_resultado, @p_idGenerado")).fetchone()
    return row[0], row[1]


def enviar_correo_reset(email_destino, nombre_usuario, link):
    try:
        mail = Mail(current_app._get_current_object())
        msg = Message(
            subject='Restablece tu contraseña - FourOvenPizza',
            recipients=[email_destino]
        )
        msg.html = f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;padding:24px;
                    border:1px solid #e5e7eb;border-radius:12px;">
            <div style="background:#38230f;padding:16px;border-radius:8px 8px 0 0;text-align:center;">
                <h2 style="color:#f29f05;margin:0;">FourOven Pizza</h2>
            </div>
            <div style="padding:24px;">
                <p style="color:#374151;">Hola <strong>{nombre_usuario}</strong>,</p>
                <p style="color:#374151;">Se ha solicitado restablecer tu contraseña.
                   Haz clic en el botón para definir una nueva:</p>
                <div style="text-align:center;margin:24px 0;">
                    <a href="{link}"
                       style="background:#f29f05;color:#fff;padding:12px 28px;
                              border-radius:8px;text-decoration:none;font-weight:bold;">
                        Restablecer Contraseña
                    </a>
                </div>
                <p style="color:#6b7280;font-size:13px;">
                    Este enlace expira en <strong>24 horas</strong>.<br>
                    Si no solicitaste este cambio, ignora este correo.
                </p>
            </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error enviando correo: {e}")
        return False


def registrar_acceso(usuario_id, nombre_usuario, evento, resultado):
    try:
        entrada = BitacoraAccesos(
            usuarioId=usuario_id,
            nombreUsuario=nombre_usuario,
            evento=evento,
            ip=get_ip(),
            navegador=get_navegador(),
            resultado=resultado
        )
        db.session.add(entrada)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error registrando acceso en bitácora: {e}")
        return False


def registrar_error(modulo, mensaje, detalles=None):
    try:
        entrada = BitacoraSistema(
            nivel='ERROR',
            modulo=modulo,
            mensaje=mensaje,
            detalles=detalles,
            ip=get_ip(),
            usuarioId=session.get('usuario_id')
        )
        db.session.add(entrada)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error registrando en bitácora sistema: {e}")


# Rutas :D

@autentificacion.route("/", methods=['GET', 'POST'])
def login():
    if session.get('usuario_id'):
        return redirect(url_for('inicio'))

    form = forms.LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        nombre_usuario = form.usuario.data
        registro = IntentosFallidos.query.filter_by(usuario=nombre_usuario).first()

        if registro and registro.esta_bloqueado():
            minutos = registro.segundos_restantes() // 60
            segundos = registro.segundos_restantes() % 60
            registrar_acceso(None, nombre_usuario, 'LOGIN_BLOQUEADO', 'BLOQUEADO')
            flash(f'Cuenta bloqueada por demasiados intentos. '
                  f'Intenta de nuevo en {minutos}m {segundos}s.', 'danger')
            return render_template("autentificacion/login.html", form=form)

        usuario = Usuarios.query.filter_by(usuario=nombre_usuario).first()

        if usuario and check_password_hash(usuario.contrasenia, form.contrasenia.data):
            if registro:
                db.session.delete(registro)
                db.session.commit()

            if usuario.estatus != 1:
                registrar_acceso(usuario.idUsuario, usuario.nombre, 'LOGIN', 'CUENTA_DESACTIVADA')
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'danger')
                return render_template("autentificacion/login.html", form=form)

            if not usuario.rol or not usuario.rol.estatus:
                registrar_acceso(usuario.idUsuario, usuario.nombre, 'LOGIN', 'ROL_DESACTIVADO')
                flash('Tu rol ha sido desactivado. Contacta al administrador.', 'danger')
                return render_template("autentificacion/login.html", form=form)

            session.clear()
            session['usuario_id']     = usuario.idUsuario
            session['usuario_nombre'] = usuario.nombre
            session['usuario_user']   = usuario.usuario
            session['usuario_rol_id'] = usuario.idRol
            session['usuario_rol']    = usuario.rol.nombre

            _db_user_map = {
                'Administrador': 'administrador',
                'Ventas':        'ventas',
                'Cocinero':      'cocina',
            }
            session['db_user'] = _db_user_map.get(usuario.rol.nombre, 'ventas')
            session.permanent = True

            registrar_acceso(usuario.idUsuario, usuario.nombre, 'LOGIN', 'EXITOSO')
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('inicio'))

        else:
            if not registro:
                registro = IntentosFallidos(usuario=nombre_usuario, intentos=0)
                db.session.add(registro)

            if registro.bloqueado_hasta and not registro.esta_bloqueado():
                registro.intentos = 0
                registro.bloqueado_hasta = None

            registro.intentos += 1

            if registro.intentos >= 3:
                registro.bloqueado_hasta = (
                    datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
                )
                db.session.commit()
                registrar_acceso(None, nombre_usuario, 'LOGIN', 'BLOQUEADO_POR_INTENTOS')
                flash('Has superado el límite de intentos. '
                      'Tu acceso queda bloqueado por 1 minuto.', 'danger')
            else:
                restantes = 3 - registro.intentos
                db.session.commit()
                registrar_acceso(None, nombre_usuario, 'LOGIN', 'CONTRASENIA_INCORRECTA')
                flash(f'Usuario o contraseña incorrectos. '
                      f'Te quedan {restantes} intento{"s" if restantes != 1 else ""}.', 'danger')

    return render_template("autentificacion/login.html", form=form)


@autentificacion.route("/logout")
def logout():
    if session.get('usuario_id'):
        registrar_acceso(
            session.get('usuario_id'),
            session.get('usuario_nombre'),
            'LOGOUT_MANUAL',
            'EXITOSO'
        )
    
    session.clear()
    flash('Sesión cerrada exitosamente.', 'success')
    return redirect(url_for('autentificacion.login'))


@autentificacion.route("/usuarios", methods=['GET'])
@rol_requerido('Administrador')
def usuarios():
    form = forms.UsuarioForm()
    roles = Roles.query.filter_by(estatus=1).all()
    form.idRol.choices = [(r.idRol, r.nombre) for r in roles]
    lista_usuarios = Usuarios.query.join(Roles).order_by(Usuarios.nombre.asc()).all()
    return render_template("autentificacion/usuarios.html",
                           form=form,
                           usuarios=lista_usuarios,
                           csrf_token=generate_csrf())


@autentificacion.route("/registrar-usuario", methods=['POST'])
@rol_requerido('Administrador')
def registrar_usuario():
    try:
        id_rol = request.form.get('idRol', '').strip()
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        email = request.form.get('email', '').strip().lower()
        contrasenia = request.form.get('contrasenia', '')

        if not id_rol:
            return jsonify({'success': False, 'message': 'Debe seleccionar un rol'})

        rol_obj = Roles.query.get(int(id_rol))
        if not rol_obj or not rol_obj.estatus:
            return jsonify({'success': False, 'message': 'El rol seleccionado no es válido'})

        valido, mensaje = validar_campos_usuario(nombre, usuario, email, contrasenia)
        if not valido:
            return jsonify({'success': False, 'message': mensaje})

        if Usuarios.query.filter(db.func.lower(Usuarios.usuario) == usuario.lower()).first():
            return jsonify({'success': False, 'message': 'El nombre de usuario ya está en uso'})

        if Usuarios.query.filter(db.func.lower(Usuarios.email) == email.lower()).first():
            return jsonify({'success': False, 'message': 'El correo electrónico ya está registrado'})

        contrasenia_hash = generate_password_hash(contrasenia)
        resultado, id_generado = ejecutar_sp_usuario(
            accion='INSERT', idRol=id_rol, nombre=nombre,
            usuario=usuario, contrasenia=contrasenia_hash,
            estatus=1, email=email
        )

        if resultado.startswith('ERROR'):
            return jsonify({'success': False, 'message': resultado.replace('ERROR: ', '')})

        return jsonify({'success': True, 'message': 'Usuario registrado exitosamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error inesperado: {str(e)}'})


@autentificacion.route("/editar-usuario/<int:id>", methods=['POST'])
@rol_requerido('Administrador')
def editar_usuario(id):
    try:
        id_rol = request.form.get('idRol', '').strip()
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        email = request.form.get('email', '').strip().lower()
        contrasenia = request.form.get('contrasenia', '')

        if not id_rol:
            return jsonify({'success': False, 'message': 'Debe seleccionar un rol'})

        rol_obj = Roles.query.get(int(id_rol))
        if not rol_obj or not rol_obj.estatus:
            return jsonify({'success': False, 'message': 'El rol seleccionado no es válido'})

        usuario_obj = Usuarios.query.get(id)
        if not usuario_obj:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})

        valido, mensaje = validar_campos_usuario(
            nombre, usuario, email,
            contrasenia if contrasenia.strip() else None,
            es_edicion=True
        )
        if not valido:
            return jsonify({'success': False, 'message': mensaje})

        if Usuarios.query.filter(
                db.func.lower(Usuarios.usuario) == usuario.lower(),
                Usuarios.idUsuario != id).first():
            return jsonify({'success': False, 'message': 'El nombre de usuario ya está en uso por otro usuario'})

        if Usuarios.query.filter(
                db.func.lower(Usuarios.email) == email.lower(),
                Usuarios.idUsuario != id).first():
            return jsonify({'success': False, 'message': 'El correo electrónico ya está en uso por otro usuario'})

        contrasenia_hash = None
        if contrasenia and contrasenia.strip():
            contrasenia_hash = generate_password_hash(contrasenia)

        resultado, _ = ejecutar_sp_usuario(
            accion='UPDATE', idUsuario=id, idRol=id_rol, nombre=nombre,
            usuario=usuario, contrasenia=contrasenia_hash,
            estatus=usuario_obj.estatus, email=email
        )

        if resultado.startswith('ERROR'):
            return jsonify({'success': False, 'message': resultado.replace('ERROR: ', '')})

        usuario_obj.email = email
        db.session.commit()

        return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error inesperado: {str(e)}'})


@autentificacion.route("/cambiar-estatus-usuario/<int:id>/<int:estatus>")
@rol_requerido('Administrador')
def cambiar_estatus_usuario(id, estatus):
    try:
        resultado, _ = ejecutar_sp_usuario(accion='CHANGE_STATUS', idUsuario=id, estatus=estatus)

        if resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            estado_texto = "activado" if estatus == 1 else "desactivado"
            flash(f'Usuario {estado_texto} exitosamente', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('autentificacion.usuarios'))


@autentificacion.route("/roles", methods=['GET'])
@rol_requerido('Administrador')
def roles():
    lista_roles = Roles.query.order_by(Roles.nombre.asc()).all()
    return render_template("autentificacion/roles.html", roles=lista_roles)


@autentificacion.route("/cambiar-estatus-rol/<int:id>/<int:estatus>")
@rol_requerido('Administrador')
def cambiar_estatus_rol(id, estatus):
    try:
        rol = Roles.query.get(id)
        if not rol:
            flash('Rol no encontrado.', 'danger')
            return redirect(url_for('autentificacion.roles'))

        db.session.execute(
            text("CALL sp_cambiar_estatus_rol(:idRol, :estatus, :ejecutadoPor, :ip, @p_resultado)"),
            {
                'idRol': id,
                'estatus': estatus,
                'ejecutadoPor': session.get('usuario_id'),
                'ip': get_ip()
            }
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        if resultado.startswith('ERROR'):
            flash(resultado.replace('ERROR: ', ''), 'danger')
        else:
            estado_texto = "activado" if estatus == 1 else "desactivado"
            flash(f'Rol "{rol.nombre}" {estado_texto} exitosamente.', 'success')

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        registrar_error('Roles', f'Error al cambiar estatus de rol ID:{id}', str(e))
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('autentificacion.roles'))


@autentificacion.route("/generar-reset/<int:id>", methods=['POST'])
@rol_requerido('Administrador')
def generar_reset(id):
    try:
        usuario_obj = Usuarios.query.get(id)
        if not usuario_obj:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})
        if not usuario_obj.email:
            return jsonify({'success': False, 'message': 'El usuario no tiene correo registrado'})

        ResetContrasenia.query.filter_by(idUsuario=id, usado=False).update({'usado': True})
        db.session.commit()

        token = secrets.token_urlsafe(32)
        reset = ResetContrasenia(
            idUsuario=id,
            token=token,
            expiracion=datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        )
        db.session.add(reset)
        db.session.commit()

        link = url_for('autentificacion.reset_contrasenia', token=token, _external=True)
        enviado = enviar_correo_reset(usuario_obj.email, usuario_obj.nombre, link)

        if enviado:
            return jsonify({'success': True, 'message': f'Correo de reset enviado a {usuario_obj.email}'})
        else:
            return jsonify({'success': False, 'message': 'No se pudo enviar el correo. Verifica la configuración.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@autentificacion.route("/reset-password/<token>", methods=['GET', 'POST'])
def reset_contrasenia(token):
    reset = ResetContrasenia.query.filter_by(token=token, usado=False).first()

    if not reset or not reset.esta_vigente():
        flash('El enlace es inválido o ha expirado.', 'danger')
        return redirect(url_for('autentificacion.login'))

    if request.method == 'POST':
        contrasenia = request.form.get('contrasenia')
        contrasenia2 = request.form.get('contrasenia2')

        if not contrasenia or not contrasenia2:
            flash('Todos los campos son requeridos.', 'danger')
            return render_template('autentificacion/reset_password.html', token=token)

        if contrasenia != contrasenia2:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('autentificacion/reset_password.html', token=token)

        if not validar_seguridad_contrasenia(contrasenia):
            flash('La contraseña no cumple los requisitos de seguridad.', 'danger')
            return render_template('autentificacion/reset_password.html', token=token)

        reset.usuario.contrasenia = generate_password_hash(contrasenia)
        reset.usado = True
        db.session.commit()

        flash('Contraseña actualizada. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('autentificacion.login'))

    return render_template('autentificacion/reset_password.html', token=token)


@autentificacion.route("/cambiar-contraseña", methods=['GET'])
@login_requerido
def cambiar_contrasena_vista():
    return render_template("autentificacion/cambiar_contrasena.html", csrf_token=generate_csrf())


@autentificacion.route("/cambiar-contrasena", methods=['POST'])
@login_requerido
def cambiar_contrasena():
    try:
        actual = request.form.get('contrasenia_actual', '')
        nueva = request.form.get('contrasenia_nueva', '')
        confirmacion = request.form.get('contrasenia_confirmar', '')

        if not all([actual, nueva, confirmacion]):
            return jsonify({'success': False, 'message': 'Todos los campos son requeridos'})

        usuario_obj = Usuarios.query.get(session['usuario_id'])
        if not usuario_obj:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})

        if not check_password_hash(usuario_obj.contrasenia, actual):
            return jsonify({'success': False, 'message': 'La contraseña actual es incorrecta'})

        if nueva == actual:
            return jsonify({'success': False, 'message': 'La nueva contraseña no puede ser igual a la actual'})

        if nueva != confirmacion:
            return jsonify({'success': False, 'message': 'La nueva contraseña y su confirmación no coinciden'})

        if not validar_seguridad_contrasenia(nueva):
            return jsonify({'success': False,
                            'message': 'La contraseña debe tener mínimo 8 caracteres, '
                                       'una mayúscula, una minúscula, un número y un carácter especial'})

        nueva_hash = generate_password_hash(nueva)
        db.session.execute(
            text("CALL sp_cambiar_contrasenia(:idUsuario, :contrasenia, :ip, @p_resultado)"),
            {
                'idUsuario': session['usuario_id'],
                'contrasenia': nueva_hash,
                'ip': get_ip()
            }
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()

        if resultado.startswith('ERROR'):
            return jsonify({'success': False, 'message': resultado.replace('ERROR: ', '')})

        return jsonify({'success': True, 'message': 'Contraseña actualizada exitosamente'})

    except Exception as e:
        db.session.rollback()
        registrar_error('Usuarios', 'Error al cambiar contraseña', str(e))
        return jsonify({'success': False, 'message': f'Error inesperado: {str(e)}'})
    
@autentificacion.route("/logout-beacon", methods=['POST'])
def logout_beacon():
    # Similar al logout normal pero sin flash messages
    if session.get('usuario_id'):
        registrar_acceso(
            session.get('usuario_id'),
            session.get('usuario_nombre'),
            'LOGOUT_CIERRE_NAVEGADOR',
            'EXITOSO'
        )
        session.clear()
    return '', 204