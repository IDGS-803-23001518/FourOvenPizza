from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_mail import Mail
from datetime import datetime, timedelta, timezone
from config import DevelopmentConfig
from autentificacion.routes import autentificacion
from bitacoras.routes import bitacoras
from compras.routes import comprass
from materiasPrimas.routes import materiasPrimas
from proveedores.routes import proveedores
from unidadesMedida.routes import unidadesMedida
from recetas.routes import recetas
from produccion.routes import produccion
from ventas.routes import ventas
from mermas.routes import mermas
from productos.routes import productos
from caja.routes import caja
from dashboard.routes import dashboard
from miniRecetas.routes import miniRecetas
from models import db
from autentificacion.routes import registrar_acceso

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
csrf = CSRFProtect(app)
mail = Mail(app)

app.register_blueprint(autentificacion)
app.register_blueprint(bitacoras)
app.register_blueprint(proveedores)
app.register_blueprint(comprass)
app.register_blueprint(materiasPrimas)
app.register_blueprint(unidadesMedida)
app.register_blueprint(productos)
app.register_blueprint(recetas)
app.register_blueprint(produccion)
app.register_blueprint(ventas)
app.register_blueprint(mermas)
app.register_blueprint(caja)
app.register_blueprint(dashboard)
app.register_blueprint(miniRecetas)

db.init_app(app)


# Rutas públicas que no deben disparar la verificación de sesión
RUTAS_PUBLICAS = {'autentificacion.login', 'autentificacion.logout', 'autentificacion.reset_contrasenia', 'static'}


@app.before_request
def verificar_sesion():
    # No verificar en rutas públicas para evitar bucles y doble registro
    if request.endpoint in RUTAS_PUBLICAS:
        return

    if not session.get('usuario_id'):
        return

    ahora = datetime.now(timezone.utc)
    ultima = session.get('ultima_actividad')

    if ultima:
        if isinstance(ultima, str):
            ultima = datetime.fromisoformat(ultima)

        if (ahora - ultima) > timedelta(minutes=10):
            # Guardar datos antes de limpiar la sesión
            usuario_id = session.get('usuario_id')
            usuario_nombre = session.get('usuario_nombre')

            # Limpiar primero para que el redirect no vuelva a entrar aquí
            session.clear()

            # Registrar UNA SOLA VEZ después de limpiar
            registrar_acceso(
                usuario_id,
                usuario_nombre,
                'LOGOUT_INACTIVIDAD',
                'SESION_EXPIRADA'
            )

            flash('Tu sesión ha expirado por inactividad.', 'warning')
            return redirect(url_for('autentificacion.login'))

    session['ultima_actividad'] = ahora.isoformat()
    session.modified = True


@app.route("/")
def index():
    return redirect(url_for('autentificacion.login'))


@app.route("/inicio")
def inicio():
    if not session.get('usuario_id'):
        return redirect(url_for('autentificacion.login'))

    rol = session.get('usuario_rol')

    if rol == 'Administrador':
        return redirect(url_for('dashboard.index'))
    elif rol == 'Ventas':
        return render_template("inicio.html")
    elif rol == 'Cocinero':
        return render_template("inicio.html")
    else:
        return render_template("inicio.html")


@app.route("/dashboard-redirect")
def dashboard_redirect():
    if not session.get('usuario_id'):
        return redirect(url_for('autentificacion.login'))

    if session.get('usuario_rol') != 'Administrador':
        flash('No tienes permisos para acceder al dashboard.', 'danger')
        return redirect(url_for('inicio'))

    return redirect(url_for('dashboard.index'))


@app.context_processor
def inject_layout():
    layouts = {
        'Administrador': 'layoutAdmin.html',
        'Ventas': 'layoutVentas.html',
        'Cocinero': 'layoutCocinero.html',
    }
    rol = session.get('usuario_rol', 'Administrador')
    return {'layout': layouts.get(rol, 'layoutAdmin.html')}


@app.errorhandler(CSRFError)
def manejar_csrf_error(e):
    # Token expirado (típicamente por sesión expirada): redirigir al login limpiamente
    flash('Tu sesión ha expirado. Por favor inicia sesión de nuevo.', 'warning')
    return redirect(url_for('autentificacion.login'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)