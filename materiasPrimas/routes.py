from flask import flash, redirect, render_template, request, url_for, session
from sqlalchemy import extract, func, text

import forms
from autentificacion.routes import rol_requerido
from models import Categorias, MateriasPrimas, UnidadesMedida, db

from . import materiasPrimas


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


@materiasPrimas.route("/materiasPrimas", methods=["GET", "POST"])
@rol_requerido("Administrador")
def listadoMaterias():
    create_form = forms.MateriaPrimaForm(request.form)
    lista_materias = MateriasPrimas.query.all()
    categorias = Categorias.query.filter_by(estatus=1).all()
    return render_template(
        "materiasPrimas/materiasPrimas.html",
        form=create_form,
        materias=lista_materias,
        categorias=categorias,
    )

@materiasPrimas.route("/registrar-materia-prima", methods=["POST"])
@rol_requerido("Administrador")
def registrar_materia_prima():
    form = forms.MateriaPrimaForm(request.form)
    try:
        db.session.execute(
            text(
                """
                CALL sp_gestion_materiasprimas(
                    :accion,
                    :idMateriaP,
                    :nombre,
                    :tipo,
                    :idCategoria,
                    :stock,
                    :stockMinimo,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
            """
            ),
            {
                "accion": "INSERT",
                "idMateriaP": None,
                "nombre": form.nombre.data,
                "tipo": form.tipo.data,
                "idCategoria": form.idCategoria.data,
                "stock": form.stock.data,
                "stockMinimo": form.stockMinimo.data,
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

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route("/editar-materia-prima/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_materia_prima(id):

    form = forms.MateriaPrimaForm(request.form)

    try:

        db.session.execute(
            text(
                """
                CALL sp_gestion_materiasprimas(
                    :accion,
                    :idMateriaP,
                    :nombre,
                    :tipo,
                    :idCategoria,
                    :stock,
                    :stockMinimo,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
            """
            ),
            {
                "accion": "UPDATE",
                "idMateriaP": id,
                "nombre": form.nombre.data,
                "tipo": form.tipo.data,
                "idCategoria": form.idCategoria.data,
                "stock": form.stock.data,
                "stockMinimo": form.stockMinimo.data,
                "estatus": form.estatus.data,
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

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route("/eliminar-materia-prima/<int:id>")
@rol_requerido("Administrador")
def eliminar_materia_prima(id):
    try:

        db.session.execute(
            text(
                """
                CALL sp_gestion_materiasprimas(
                    :accion,
                    :idMateriaP,
                    :nombre,
                    :tipo,
                    :idCategoria,
                    :stock,
                    :stockMinimo,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
            """
            ),
            {
                "accion": "DELETE",
                "idMateriaP": id,
                "nombre": None,
                "tipo": None,
                "idCategoria": None,
                "stock": None,
                "stockMinimo": None,
                "estatus": None,
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

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route('/ver-materia-prima/<int:id>')
@rol_requerido('Administrador')
def ver_materia_prima(id):
    mp = MateriasPrimas.query.get_or_404(id)
    return render_template('materiasPrimas/verMateriaPrima.html', mp=mp)


@materiasPrimas.route("/registrar-unidad-medida", methods=["POST"])
@rol_requerido("Administrador")
def registrar_unidad_medida():
    create_form = forms.UnidadMedidaForm(request.form)
    if create_form.validate_on_submit():
        unidad_medida = UnidadesMedida(
            nombre=create_form.nombre.data, simbolo=create_form.simbolo.data
        )
        db.session.add(unidad_medida)
        db.session.commit()
        flash("Unidad de medida registrada exitosamente.", "success")
    return redirect(url_for("materiasPrimas.listadoUnidades"))
