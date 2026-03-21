from . import autentificacion
from flask import Flask, render_template, request, redirect, url_for
from flask import flash
from flask_wtf.csrf import CSRFProtect
from config import DevelopmentConfig
from flask import g
import forms
from models import Usuarios, Roles

@autentificacion.route("/", methods=['GET','POST'])
def login():
    form = forms.LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        usuario = Usuarios.query.filter_by(usuario=form.usuario.data).first()
        if usuario and usuario.contrasenia == form.contrasenia.data:
            g.user = usuario
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('inicio'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template("autentificacion/login.html", form=form)