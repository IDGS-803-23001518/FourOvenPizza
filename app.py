from datetime import datetime, timedelta, timezone

from flask import (Flask, g, redirect, render_template, request, session,
                   url_for)
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect

import forms
from autentificacion.routes import autentificacion
from bitacoras import bitacoras
from proveedores import proveedores
from compras import compras
from models import db

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
csrf = CSRFProtect(app)
mail = Mail(app)

app.register_blueprint(autentificacion)
app.register_blueprint(bitacoras)
app.register_blueprint(proveedores)
app.register_blueprint(compras) 
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
        if ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)

        if (ahora - ultima) > timedelta(minutes=1):
            usuario_id    = session.get('usuario_id')
            nombre_usuario = session.get('usuario_nombre')
            ip             = request.headers.get('X-Forwarded-For',
                             request.remote_addr).split(',')[0].strip()
            navegador      = request.headers.get('User-Agent', '')[:255]

            session.clear()

            try:
                from models import BitacoraAccesos
                entrada = BitacoraAccesos(
                    usuarioId     = usuario_id,
                    nombreUsuario = nombre_usuario,
                    evento        = 'LOGOUT_INACTIVIDAD',
                    ip            = ip,
                    navegador     = navegador,
                    resultado     = 'SESION_EXPIRADA'
                )
                db.session.add(entrada)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error registrando logout por inactividad: {e}")

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
