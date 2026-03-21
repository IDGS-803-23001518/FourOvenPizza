from flask import Flask, render_template, request, redirect, url_for
from flask import flash
from flask_wtf.csrf import CSRFProtect
from flask import g
from config import DevelopmentConfig
from autentificacion.routes import autentificacion
import forms
from models import db

app = Flask(__name__)
csrf=CSRFProtect()
app.config.from_object(DevelopmentConfig)
app.register_blueprint(autentificacion)
db.init_app(app)

@app.route("/")
def index():
    return redirect(url_for('autentificacion.login'))

@app.route("/inicio", methods=['GET','POST'])
def inicio():
	return render_template("inicio.html")

@app.errorhandler(404)
def page_not_found(e):
	return render_template("404.html"),404

if __name__ == '__main__':
	csrf.init_app(app)
	with app.app_context():
		db.create_all()
	app.run(debug=True)