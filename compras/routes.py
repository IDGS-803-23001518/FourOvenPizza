from flask import render_template, session, redirect, url_for
from . import compras

@compras.route("/compras")
def vista_compras():
    if not session.get('usuario_id'):
        return redirect(url_for('autentificacion.login'))
    
    return render_template("compras/compras.html")