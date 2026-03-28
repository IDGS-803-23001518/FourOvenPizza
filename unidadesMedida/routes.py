from flask import flash, redirect, render_template, request, url_for, session
from sqlalchemy import extract, func, text

import forms
from autentificacion.routes import rol_requerido
from models import UnidadesMedida, db

from . import unidadesMedida


def _texto_resultado(resultado):
    if not resultado:
        return "No se obtuvo respuesta del procedimiento almacenado.", "danger"

    if ":" in resultado:
        _, mensaje = resultado.split(":", 1)
        mensaje = mensaje.strip()
    else:
        mensaje = resultado.strip()

    categoria = "success" if resultado.startswith("SUCCESS") else "danger"
    return mensaje, categoria


@unidadesMedida.route("/unidades-medida")
@rol_requerido("Administrador")
def listado_unidades():

    unidades = UnidadesMedida.query.all()

    return render_template("unidadesMedida/unidadesMedida.html", unidades=unidades)


@unidadesMedida.route("/registrar-unidad", methods=["POST"])
@rol_requerido("Administrador")
def registrar_unidad():

    try:

        db.session.execute(
            text(
                """
            CALL sp_gestion_unidadesmedida(
                :accion,
                :id,
                :nombre,
                :tipo,
                :equivalente,
                :estatus,
                :ip,
                :usuario,
                @p_resultado,
                @p_id
            )
        """
            ),
            {
                "accion": "INSERT",
                "id": None,
                "nombre": request.form["nombre"],
                "tipo": request.form["tipo"],
                "equivalente": request.form["equivalente"],
                "estatus": 1,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:

        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("unidadesMedida.listado_unidades"))


@unidadesMedida.route("/editar-unidad/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_unidad(id):

    try:

        db.session.execute(
            text(
                """
            CALL sp_gestion_unidadesmedida(
                :accion,
                :id,
                :nombre,
                :tipo,
                :equivalente,
                :estatus,
                :ip,
                :usuario,
                @p_resultado,
                @p_id
            )
        """
            ),
            {
                "accion": "UPDATE",
                "id": id,
                "nombre": request.form["nombre"],
                "tipo": request.form["tipo"],
                "equivalente": request.form["equivalente"],
                "estatus": request.form["estatus"],
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:

        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("unidadesMedida.listado_unidades"))


@unidadesMedida.route("/eliminar-unidad/<int:id>")
@rol_requerido("Administrador")
def eliminar_unidad(id):

    try:

        db.session.execute(
            text(
                """
            CALL sp_gestion_unidadesmedida(
                :accion,
                :id,
                NULL,
                NULL,
                NULL,
                NULL,
                :ip,
                :usuario,
                @p_resultado,
                @p_id
            )
        """
            ),
            {
                "accion": "DELETE",
                "id": id,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:

        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("unidadesMedida.listado_unidades"))
