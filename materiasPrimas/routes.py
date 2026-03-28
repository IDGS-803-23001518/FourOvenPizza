import re
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for, session
from sqlalchemy import extract, func, text

import forms
from autentificacion.routes import rol_requerido
from models import Categorias, MateriasPrimas, UnidadesMedida, db

from . import materiasPrimas

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
    session["materias_form_error"] = {
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

    if len(nombre_limpio) < 3:
        raise ValueError(f"{etiqueta} debe tener al menos 3 caracteres.")

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


def _existe_materia_prima_duplicada(nombre, id_materia_prima=None):
    materias = MateriasPrimas.query.all()
    nombre_normalizado = _normalizar_nombre_catalogo(nombre)

    for materia in materias:
        if id_materia_prima is not None and materia.idMateriaP == id_materia_prima:
            continue
        if _normalizar_nombre_catalogo(materia.nombre) == nombre_normalizado:
            return True

    return False


def _obtener_alertas_stock_materias():
    alertas = []

    for materia in MateriasPrimas.query.filter_by(estatus=1).order_by(MateriasPrimas.nombre.asc()).all():
        stock_actual = Decimal(str(materia.stock or 0))
        stock_minimo = Decimal(str(materia.stockMinimo or 0))

        if stock_minimo > 0 and stock_actual <= stock_minimo:
            alertas.append(
                {
                    "idMateriaP": materia.idMateriaP,
                    "nombre": materia.nombre,
                    "stock": stock_actual,
                    "stock_minimo": stock_minimo,
                }
            )

    return alertas


@materiasPrimas.route("/materiasPrimas", methods=["GET", "POST"])
@rol_requerido("Administrador")
def listadoMaterias():
    create_form = forms.MateriaPrimaForm(request.form)
    lista_materias = MateriasPrimas.query.all()
    categorias = Categorias.query.filter_by(estatus=1).all()
    form_error = session.pop("materias_form_error", None)
    alertas_stock = _obtener_alertas_stock_materias()
    return render_template(
        "materiasPrimas/materiasPrimas.html",
        form=create_form,
        materias=lista_materias,
        categorias=categorias,
        form_error=form_error,
        alertas_stock=alertas_stock,
    )

@materiasPrimas.route("/registrar-materia-prima", methods=["POST"])
@rol_requerido("Administrador")
def registrar_materia_prima():
    datos_formulario = {}
    try:
        nombre = _validar_nombre_catalogo(request.form.get("nombre"), "El nombre de la materia prima")
        tipo = request.form.get("tipo")
        id_categoria = int(request.form.get("idCategoria"))
        stock = _parsear_entero_positivo(request.form.get("stock"), "El stock")
        stock_minimo = _parsear_entero_positivo(request.form.get("stockMinimo"), "El stock minimo")
        datos_formulario = {
            "nombre": nombre,
            "tipo": tipo,
            "idCategoria": id_categoria,
            "stock": str(stock),
            "stockMinimo": str(stock_minimo),
        }

        if _existe_materia_prima_duplicada(nombre):
            _guardar_error_formulario("registro", "La materia prima ya existe.", datos_formulario)
            return redirect(url_for("materiasPrimas.listadoMaterias"))

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
                "nombre": nombre,
                "tipo": tipo,
                "idCategoria": id_categoria,
                "stock": stock,
                "stockMinimo": stock_minimo,
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

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route("/editar-materia-prima/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_materia_prima(id):
    datos_formulario = {"id": id}

    try:
        nombre = _validar_nombre_catalogo(request.form.get("nombre"), "El nombre de la materia prima")
        tipo = request.form.get("tipo")
        id_categoria = int(request.form.get("idCategoria"))
        stock = _parsear_entero_positivo(request.form.get("stock"), "El stock")
        stock_minimo = _parsear_entero_positivo(request.form.get("stockMinimo"), "El stock minimo")
        estatus = 1 if str(request.form.get("estatus", "1")) == "1" else 0
        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "tipo": tipo,
            "idCategoria": id_categoria,
            "stock": str(stock),
            "stockMinimo": str(stock_minimo),
            "estatus": estatus,
        }

        if _existe_materia_prima_duplicada(nombre, id):
            _guardar_error_formulario("edicion", "Ya existe otra materia prima con ese nombre.", datos_formulario)
            return redirect(url_for("materiasPrimas.listadoMaterias"))

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
                "nombre": nombre,
                "tipo": tipo,
                "idCategoria": id_categoria,
                "stock": stock,
                "stockMinimo": stock_minimo,
                "estatus": estatus,
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
