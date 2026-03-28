from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import DetalleReceta, MateriasPrimas, Productos, Recetas, db

from . import recetas


def _parsear_cantidad(valor):
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("La cantidad capturada no es valida.")

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    return cantidad


def _texto_resultado(resultado):
    if not resultado:
        return "No se obtuvo respuesta del procedimiento almacenado.", "danger"

    if ":" in resultado:
        _, mensaje = resultado.split(":", 1)
        mensaje = mensaje.strip()
    else:
        mensaje = resultado

    categoria = "success" if resultado.startswith("SUCCESS") else "danger"
    return mensaje, categoria


def _obtener_tamano_producto(producto):
    tamano = getattr(producto, "tamano", None) or getattr(producto, "tamaño", None)

    if tamano:
        return tamano

    for atributo in ("tamaÃ±o", "tamaÃƒÂ±o"):
        if hasattr(producto, atributo):
            tamano = getattr(producto, atributo)
            if tamano:
                return tamano

    return None


def _obtener_receta_producto(id_producto):
    return (
        Recetas.query.filter_by(idProducto=id_producto)
        .order_by(Recetas.idReceta.asc())
        .first()
    )


def _asegurar_receta_por_sp(id_producto, descripcion=""):
    receta = _obtener_receta_producto(id_producto)

    if receta:
        return receta

    db.session.execute(
        text(
            """
            CALL sp_gestion_recetas(
                :accion,
                :idReceta,
                :idProducto,
                :descripcion,
                :ip,
                :usuario,
                @p_resultado,
                @p_idGenerado
            )
            """
        ),
        {
            "accion": "INSERT",
            "idReceta": None,
            "idProducto": id_producto,
            "descripcion": descripcion or None,
            "ip": request.remote_addr,
            "usuario": session["usuario_id"],
        },
    )

    resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
    if not resultado or not resultado.startswith("SUCCESS"):
        mensaje, _ = _texto_resultado(resultado)
        raise ValueError(mensaje)

    db.session.commit()
    return _obtener_receta_producto(id_producto)


@recetas.route("/recetas")
@rol_requerido("Administrador")
def listado_recetas():
    productos = Productos.query.order_by(Productos.nombre.asc()).all()
    recetas_activas = {
        fila.idProducto: fila.idReceta
        for fila in Recetas.query.with_entities(Recetas.idProducto, Recetas.idReceta).all()
    }

    productos_recetas = []
    for producto in productos:
        productos_recetas.append(
            {
                "idProducto": producto.idProducto,
                "nombre": producto.nombre,
                "precio": producto.precio,
                "stock": producto.stock,
                "tamano": _obtener_tamano_producto(producto),
                "estatus": producto.estatus,
                "tiene_receta": producto.idProducto in recetas_activas,
            }
        )

    return render_template("recetas/recetas.html", productos=productos_recetas)


@recetas.route("/recetas/producto/<int:id_producto>")
@rol_requerido("Administrador")
def ver_receta_producto(id_producto):
    producto = Productos.query.get_or_404(id_producto)
    receta = _obtener_receta_producto(id_producto)
    detalles_receta = []

    if receta:
        detalles_receta = sorted(
            receta.detalle_recetas,
            key=lambda detalle: (detalle.materia_prima.nombre or "").lower(),
        )

    materias_primas = (
        MateriasPrimas.query.filter_by(estatus=1)
        .order_by(MateriasPrimas.nombre.asc())
        .all()
    )

    return render_template(
        "recetas/detalle.html",
        producto=producto,
        receta=receta,
        detalles_receta=detalles_receta,
        tamano_producto=_obtener_tamano_producto(producto),
        materias_primas=materias_primas,
    )


@recetas.route("/recetas/producto/<int:id_producto>/guardar", methods=["POST"])
@rol_requerido("Administrador")
def guardar_receta_producto(id_producto):
    producto = Productos.query.get_or_404(id_producto)
    descripcion = request.form.get("descripcion", "").strip()
    receta = _obtener_receta_producto(id_producto)
    accion = "UPDATE" if receta else "INSERT"
    id_receta = receta.idReceta if receta else None

    try:
        db.session.execute(
            text(
                """
                CALL sp_gestion_recetas(
                    :accion,
                    :idReceta,
                    :idProducto,
                    :descripcion,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
                """
            ),
            {
                "accion": accion,
                "idReceta": id_receta,
                "idProducto": id_producto,
                "descripcion": descripcion or None,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/producto/<int:id_producto>/detalle", methods=["POST"])
@rol_requerido("Administrador")
def agregar_detalle_receta(id_producto):
    producto = Productos.query.get_or_404(id_producto)

    try:
        id_materia_prima = int(request.form["idMateriaP"])
        cantidad = _parsear_cantidad(request.form["cantidad"])
        receta = _asegurar_receta_por_sp(id_producto)
        if receta.idReceta is None:
            raise ValueError("No fue posible preparar la receta para registrar el detalle.")

        db.session.execute(
            text(
                """
                CALL sp_gestion_detalle_receta(
                    :accion,
                    :idDetalleR,
                    :idReceta,
                    :idMateriaP,
                    :cantidad,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
                """
            ),
            {
                "accion": "INSERT",
                "idDetalleR": None,
                "idReceta": receta.idReceta,
                "idMateriaP": id_materia_prima,
                "cantidad": cantidad,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/detalle/<int:id_detalle>/editar", methods=["POST"])
@rol_requerido("Administrador")
def editar_detalle_receta(id_detalle):
    detalle = DetalleReceta.query.get_or_404(id_detalle)
    receta = detalle.receta

    try:
        cantidad = _parsear_cantidad(request.form["cantidad"])
        db.session.execute(
            text(
                """
                CALL sp_gestion_detalle_receta(
                    :accion,
                    :idDetalleR,
                    :idReceta,
                    :idMateriaP,
                    :cantidad,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
                """
            ),
            {
                "accion": "UPDATE",
                "idDetalleR": id_detalle,
                "idReceta": detalle.idReceta,
                "idMateriaP": detalle.idMateriaP,
                "cantidad": cantidad,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("recetas.ver_receta_producto", id_producto=receta.idProducto))


@recetas.route("/recetas/detalle/<int:id_detalle>/eliminar", methods=["POST"])
@rol_requerido("Administrador")
def eliminar_detalle_receta(id_detalle):
    detalle = DetalleReceta.query.get_or_404(id_detalle)
    receta = detalle.receta

    try:
        db.session.execute(
            text(
                """
                CALL sp_gestion_detalle_receta(
                    :accion,
                    :idDetalleR,
                    :idReceta,
                    :idMateriaP,
                    :cantidad,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
                """
            ),
            {
                "accion": "DELETE",
                "idDetalleR": id_detalle,
                "idReceta": detalle.idReceta,
                "idMateriaP": detalle.idMateriaP,
                "cantidad": detalle.cantidad,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("recetas.ver_receta_producto", id_producto=receta.idProducto))
