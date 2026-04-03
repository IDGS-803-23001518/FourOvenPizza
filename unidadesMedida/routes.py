import re
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for, session
from sqlalchemy import extract, func, text

import forms
from autentificacion.routes import rol_requerido
from models import UnidadesMedida, db

from . import unidadesMedida

PATRON_NOMBRE_CATALOGO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ]+$")


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


def _guardar_error_formulario(modal, mensaje, datos=None):
    session["unidades_form_error"] = {
        "modal": modal,
        "mensaje": mensaje,
        "datos": datos or {},
    }


def _normalizar_nombre_catalogo(valor):
    valor = re.sub(r"\s+", " ", (valor or "").strip())
    valor = re.sub(r"\s+\d+$", "", valor).strip()
    return valor.lower()


def _validar_nombre_catalogo(nombre, etiqueta):
    nombre_limpio = re.sub(r"\s+", " ", (nombre or "").strip())

    if not nombre_limpio:
        raise ValueError(f"{etiqueta} es requerido.")

    if len(nombre_limpio) < 2:
        raise ValueError(f"{etiqueta} debe tener al menos 2 caracteres.")

    if not PATRON_NOMBRE_CATALOGO.fullmatch(nombre_limpio):
        raise ValueError(f"{etiqueta} solo puede contener letras, numeros y espacios.")

    return nombre_limpio


def _parsear_entero_positivo(valor, etiqueta):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{etiqueta} debe ser un numero valido.")

    if numero <= 0:
        raise ValueError(f"{etiqueta} debe ser mayor a 0.")

    if numero != numero.to_integral_value():
        raise ValueError(f"{etiqueta} debe ser un numero entero.")

    return int(numero)


def _existe_unidad_duplicada(nombre, id_unidad=None):
    unidades = UnidadesMedida.query.all()
    nombre_normalizado = _normalizar_nombre_catalogo(nombre)

    for unidad in unidades:
        if id_unidad is not None and unidad.idUnidadM == id_unidad:
            continue
        if _normalizar_nombre_catalogo(unidad.nombre) == nombre_normalizado:
            return True

    return False


@unidadesMedida.route("/unidades-medida")
@rol_requerido("Administrador")
def listado_unidades():

    unidades = UnidadesMedida.query.all()
    form_error = session.pop("unidades_form_error", None)

    return render_template("unidadesMedida/unidadesMedida.html", unidades=unidades, form_error=form_error)


@unidadesMedida.route("/registrar-unidad", methods=["POST"])
@rol_requerido("Administrador")
def registrar_unidad():
    datos_formulario = {}

    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre de la unidad")
        tipo = _validar_nombre_catalogo(request.form["tipo"], "El tipo")
        equivalente = _parsear_entero_positivo(request.form["equivalente"], "El equivalente")
        datos_formulario = {
            "nombre": nombre,
            "tipo": tipo,
            "equivalente": str(equivalente),
        }

        if _existe_unidad_duplicada(nombre):
            _guardar_error_formulario("registro", "La unidad de medida ya existe.", datos_formulario)
            return redirect(url_for("unidadesMedida.listado_unidades"))

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
                "nombre": nombre,
                "tipo": tipo,
                "equivalente": equivalente,
                "estatus": 1,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("registro", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:

        db.session.rollback()
        _guardar_error_formulario("registro", str(e), datos_formulario)

    return redirect(url_for("unidadesMedida.listado_unidades"))


@unidadesMedida.route("/editar-unidad/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_unidad(id):
    datos_formulario = {"id": id}

    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre de la unidad")
        tipo = _validar_nombre_catalogo(request.form["tipo"], "El tipo")
        equivalente = _parsear_entero_positivo(request.form["equivalente"], "El equivalente")
        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "tipo": tipo,
            "equivalente": str(equivalente),
        }

        if _existe_unidad_duplicada(nombre, id):
            _guardar_error_formulario("edicion", "Ya existe otra unidad de medida con ese nombre.", datos_formulario)
            return redirect(url_for("unidadesMedida.listado_unidades"))

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
                "nombre": nombre,
                "tipo": tipo,
                "equivalente": equivalente,
                "estatus": None,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("edicion", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:

        db.session.rollback()
        _guardar_error_formulario("edicion", str(e), datos_formulario)

    return redirect(url_for("unidadesMedida.listado_unidades"))


@unidadesMedida.route("/cambiar-estatus-unidad/<int:id>")
@rol_requerido("Administrador")
def cambiar_estatus_unidad(id):
    try:
        unidad = db.session.execute(
            text("SELECT estatus FROM unidadesmedida WHERE idUnidadM = :id"),
            {"id": id},
        ).fetchone()

        if not unidad:
            flash("Unidad de medida no encontrada.", "danger")
            return redirect(url_for("unidadesMedida.listado_unidades"))

        nuevo_estatus = 0 if unidad[0] == 1 else 1

        db.session.execute(
            text("CALL sp_gestion_unidadesmedida(:accion,:id,NULL,NULL,NULL,:estatus,:ip,:usuario,@p_resultado,@p_id)"),
            {
                "accion": "CHANGE_STATUS",
                "id": id,
                "estatus": nuevo_estatus,
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
