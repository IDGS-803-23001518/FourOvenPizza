from flask import Flask, render_template, redirect, url_for, session, request
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from datetime import datetime, timedelta, timezone
from config import DevelopmentConfig
from autentificacion.routes import autentificacion
from bitacoras.routes import bitacoras
from compras.routes import compras
from materiasPrimas.routes import materiasPrimas
from proveedores.routes import proveedores
from unidadesMedida.routes import unidadesMedida
from recetas.routes import recetas
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
app.register_blueprint(compras)
app.register_blueprint(materiasPrimas)
app.register_blueprint(unidadesMedida)
app.register_blueprint(productos)
app.register_blueprint(recetas)

db.init_app(app)


@app.before_request
def verificar_sesion():
    if not session.get('usuario_id'):
        return

    ahora = datetime.now(timezone.utc)
    ultima = session.get('ultima_actividad')

    if ultima:
        if isinstance(ultima, str):
            ultima = datetime.fromisoformat(ultima)
        if (ahora - ultima) > timedelta(minutes=10):
            from models import BitacoraAccesos, db
            try:
                entrada = BitacoraAccesos(
                    usuarioId=session.get('usuario_id'),
                    nombreUsuario=session.get('usuario_nombre'),
                    evento='LOGOUT_INACTIVIDAD',
                    ip=request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip(),
                    navegador=request.headers.get('User-Agent', '')[:255],
                    resultado='SESION_EXPIRADA'
                )
                db.session.add(entrada)
                db.session.commit()
            except Exception:
                db.session.rollback()

            session.clear()
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