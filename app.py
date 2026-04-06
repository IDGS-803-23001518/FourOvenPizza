from flask import Flask, render_template, redirect, url_for, session, request
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
from models import db
from productos.routes import productos

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
    if not session.get('usuario_id'):
        return redirect(url_for('autentificacion.login'))
    return render_template("inicio.html")


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