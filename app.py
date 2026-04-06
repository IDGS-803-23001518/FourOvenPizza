from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_wtf.csrf import CSRFProtect
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
from models import db

# Importar la función de registro de acceso
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

db.init_app(app)


@app.before_request
def verificar_sesion():
    # Si no hay sesión, no hacer nada
    if not session.get('usuario_id'):
        return

    ahora = datetime.now(timezone.utc)
    ultima = session.get('ultima_actividad')

    if ultima:
        if isinstance(ultima, str):
            ultima = datetime.fromisoformat(ultima)
        
        # Verificar si la sesión expiró por inactividad
        if (ahora - ultima) > timedelta(minutes=10):
            # Registrar logout por inactividad ANTES de limpiar la sesión
            registrar_acceso(
                session.get('usuario_id'),
                session.get('usuario_nombre'),
                'LOGOUT_INACTIVIDAD',
                'SESION_EXPIRADA'
            )
            
            # Limpiar sesión y redirigir al login
            session.clear()
            flash('Tu sesión ha expirado por inactividad.', 'warning')
            return redirect(url_for('autentificacion.login'))
    
    # Actualizar la última actividad
    session['ultima_actividad'] = ahora.isoformat()
    session.modified = True


@app.route("/")
def index():
    return redirect(url_for('autentificacion.login'))


@app.route("/inicio")
def inicio():
    """Redirige al dashboard o página principal según el rol del usuario"""
    if not session.get('usuario_id'):
        return redirect(url_for('autentificacion.login'))
    
    # Redirigir según el rol del usuario
    rol = session.get('usuario_rol')
    
    if rol == 'Administrador':
        return redirect(url_for('dashboard.index'))
    elif rol == 'Ventas':
        # Si tienes una página principal para ventas
        return render_template("inicio.html")  # O la vista que corresponda
    elif rol == 'Cocinero':
        # Si tienes una página principal para cocinero
        return render_template("inicio.html")  # O la vista que corresponda
    else:
        # Por defecto, mostrar una página de bienvenida
        return render_template("inicio.html")


@app.route("/dashboard-redirect")
def dashboard_redirect():
    """Redirección específica para el dashboard (solo administradores)"""
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


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)