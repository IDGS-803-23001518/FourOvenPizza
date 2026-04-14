import json
from decimal import Decimal, InvalidOperation

from flask import redirect, render_template, request, session, url_for, flash
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import BitacoraEventos, DetalleReceta, MateriasPrimas, MiniRecetas, DetalleMiniReceta, Productos, Recetas, Usuarios, db

from . import recetas

# Mínimo de insumos recomendado por receta
MINIMO_INSUMOS_RECETA = 4


def _guardar_error_formulario(seccion, mensaje, datos=None):
    session["recetas_form_error"] = {"seccion": seccion, "mensaje": mensaje, "datos": datos or {}}


def _guardar_mensaje_receta(mensaje, categoria):
    session["recetas_mensaje"] = {"mensaje": mensaje, "categoria": categoria}


def _registrar_bitacora(modulo, accion, referencial, referencia):
    try:
        usuario = Usuarios.query.get(session.get("usuario_id"))
        db.session.add(BitacoraEventos(
            usuarioId=session.get("usuario_id"),
            nombreUsuario=usuario.nombre if usuario else "Desconocido",
            modulo=modulo,
            accion=accion,
            referencial=referencial,
            referencia=referencia,
            ip=request.remote_addr,
        ))
    except Exception:
        pass


def _parsear_cantidad(valor):
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("La cantidad capturada no es valida.")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    if cantidad != cantidad.to_integral_value():
        raise ValueError("La cantidad debe ser un numero entero.")
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


def _obtener_alertas_stock_receta(id_receta):
    registros = db.session.execute(
        text("CALL sp_obtener_alertas_stock_receta(:id_receta)"),
        {"id_receta": id_receta},
    ).mappings().all()

    alertas = []
    for r in registros:
        stock_actual = Decimal(str(r["stock"] or 0))
        stock_minimo = Decimal(str(r["stock_minimo"] or 0))
        requerido = Decimal(str(r["requerido"] or 0))
        if r["tipo_alerta"] == "insuficiente":
            alertas.append({"tipo": "insuficiente", "materia_prima": r["materia_prima"],
                            "stock": stock_actual, "requerido": requerido, "stock_minimo": stock_minimo})
        elif r["tipo_alerta"] == "bajo":
            alertas.append({"tipo": "bajo", "materia_prima": r["materia_prima"],
                            "stock": stock_actual, "requerido": requerido, "stock_minimo": stock_minimo})
    return alertas


def _obtener_tamano_producto(producto):
    return getattr(producto, "tamano", None) or getattr(producto, "tamaño", None)


def _obtener_receta_producto(id_producto):
    return Recetas.query.filter_by(idProducto=id_producto).order_by(Recetas.idReceta.asc()).first()


def _asegurar_receta_por_sp(id_producto, descripcion=""):
    receta = _obtener_receta_producto(id_producto)
    if receta:
        return receta
    db.session.execute(
        text("CALL sp_gestion_recetas(:accion,:idReceta,:idProducto,:descripcion,:ip,:usuario,@p_resultado,@p_idGenerado)"),
        {"accion": "INSERT", "idReceta": None, "idProducto": id_producto,
         "descripcion": descripcion or None, "ip": request.remote_addr, "usuario": session["usuario_id"]},
    )
    resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
    if not resultado or not resultado.startswith("SUCCESS"):
        mensaje, _ = _texto_resultado(resultado)
        raise ValueError(mensaje)
    db.session.commit()
    return _obtener_receta_producto(id_producto)


def _obtener_alertas_ingredientes_desactivados(detalles_receta):
    desactivadas = []
    for detalle in detalles_receta:
        mp = detalle.materia_prima
        if mp and not mp.estatus:
            desactivadas.append(mp.nombre)
    return desactivadas


def _obtener_mini_recetas_data():
    """
    Retorna (lista_activas, dict_json) para pasar al template.
    lista_activas  → objetos MiniRecetas con estatus=1
    dict_json      → JSON serializable con detalles de cada mini receta
    """
    mini_recetas_activas = (
        MiniRecetas.query
        .filter_by(estatus=1)
        .order_by(MiniRecetas.nombre.asc())
        .all()
    )

    data = {}
    for mr in mini_recetas_activas:
        detalles_ordenados = sorted(
            mr.detalles,
            key=lambda d: d.materia_prima.nombre if d.materia_prima else ""
        )
        data[str(mr.idMiniReceta)] = {
            "nombre": mr.nombre,
            "detalles": [
                {
                    "idMateriaP": d.idMateriaP,
                    "nombre": d.materia_prima.nombre if d.materia_prima else str(d.idMateriaP),
                    "cantidad": float(d.cantidad),
                    "unidad": "ml" if (d.materia_prima and d.materia_prima.tipo == "Liquido") else "g",
                }
                for d in detalles_ordenados
            ],
        }

    return mini_recetas_activas, json.dumps(data)


@recetas.route("/recetas/producto/<int:id_producto>")
@rol_requerido("Administrador", "Cocinero")
def ver_receta_producto(id_producto):
    producto = Productos.query.get_or_404(id_producto)
    receta = _obtener_receta_producto(id_producto)
    detalles_receta = []
    if receta:
        detalles_receta = sorted(receta.detalle_recetas,
                                 key=lambda d: (d.materia_prima.nombre or "").lower())
    materias_primas = MateriasPrimas.query.filter_by(estatus=1).order_by(MateriasPrimas.nombre.asc()).all()
    form_error = session.pop("recetas_form_error", None)
    mensaje_receta = session.pop("recetas_mensaje", None)
    alertas_stock = _obtener_alertas_stock_receta(receta.idReceta) if receta else []
    ingredientes_desactivados = _obtener_alertas_ingredientes_desactivados(detalles_receta)
    receta_corta = receta is not None and len(detalles_receta) < MINIMO_INSUMOS_RECETA

    # Mini recetas activas y sus datos para el template
    mini_recetas_activas, mini_recetas_data_json = _obtener_mini_recetas_data()

    return render_template(
        "recetas/detalle.html",
        producto=producto,
        receta=receta,
        detalles_receta=detalles_receta,
        tamano_producto=_obtener_tamano_producto(producto),
        materias_primas=materias_primas,
        form_error=form_error,
        mensaje_receta=mensaje_receta,
        alertas_stock=alertas_stock,
        ingredientes_desactivados=ingredientes_desactivados,
        receta_corta=receta_corta,
        minimo_insumos=MINIMO_INSUMOS_RECETA,
        mini_recetas_activas=mini_recetas_activas,
        mini_recetas_data_json=mini_recetas_data_json,
    )


@recetas.route("/recetas/producto/<int:id_producto>/guardar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def guardar_receta_producto(id_producto):
    producto = Productos.query.get_or_404(id_producto)
    descripcion = request.form.get("descripcion", "").strip()
    receta = _obtener_receta_producto(id_producto)
    accion_sp = "UPDATE" if receta else "INSERT"
    id_receta = receta.idReceta if receta else None
    try:
        db.session.execute(
            text("CALL sp_gestion_recetas(:accion,:idReceta,:idProducto,:descripcion,:ip,:usuario,@p_resultado,@p_idGenerado)"),
            {"accion": accion_sp, "idReceta": id_receta, "idProducto": id_producto,
             "descripcion": descripcion or None, "ip": request.remote_addr, "usuario": session["usuario_id"]},
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "success":
            accion_bit = "Editar receta" if accion_sp == "UPDATE" else "Crear receta"
            _registrar_bitacora("Recetas", accion_bit, "Producto", producto.nombre)
            db.session.commit()
        _guardar_mensaje_receta(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        _guardar_mensaje_receta(str(exc), "danger")
    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/producto/<int:id_producto>/detalle", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def agregar_detalle_receta(id_producto):
    Productos.query.get_or_404(id_producto)
    datos_formulario = {}
    try:
        id_materia_prima = int(request.form["idMateriaP"])
        cantidad = _parsear_cantidad(request.form["cantidad"])
        datos_formulario = {"idMateriaP": str(id_materia_prima), "cantidad": str(int(cantidad))}
        receta = _asegurar_receta_por_sp(id_producto)
        if receta.idReceta is None:
            raise ValueError("No fue posible preparar la receta para registrar el detalle.")
        db.session.execute(
            text("CALL sp_gestion_detalle_receta(:accion,:idDetalleR,:idReceta,:idMateriaP,:cantidad,:ip,:usuario,@p_resultado,@p_idGenerado)"),
            {"accion": "INSERT", "idDetalleR": None, "idReceta": receta.idReceta,
             "idMateriaP": id_materia_prima, "cantidad": cantidad,
             "ip": request.remote_addr, "usuario": session["usuario_id"]},
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("detalle", mensaje, datos_formulario)
        else:
            mp = MateriasPrimas.query.get(id_materia_prima)
            _registrar_bitacora("Detalle Receta", "Agregar insumo", "Materia Prima",
                                mp.nombre if mp else str(id_materia_prima))
            db.session.commit()
            _guardar_mensaje_receta(mensaje, categoria)

            receta_actualizada = _obtener_receta_producto(id_producto)
            if receta_actualizada:
                total_insumos = DetalleReceta.query.filter_by(idReceta=receta_actualizada.idReceta).count()
                if total_insumos < MINIMO_INSUMOS_RECETA:
                    flash(
                        f"Aviso: la receta tiene solo {total_insumos} insumo(s). "
                        f"Se recomienda incluir al menos {MINIMO_INSUMOS_RECETA} para una receta completa.",
                        "warning",
                    )

    except Exception as exc:
        db.session.rollback()
        _guardar_error_formulario("detalle", str(exc), datos_formulario)
    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/producto/<int:id_producto>/mini-receta", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def aplicar_mini_receta(id_producto):
    """
    Agrega automáticamente todos los insumos de una mini receta a la receta del producto.
    Si un insumo ya existe, actualiza su cantidad; si no, lo inserta.
    """
    Productos.query.get_or_404(id_producto)
    try:
        id_mini_receta = int(request.form.get("idMiniReceta", 0))
        if not id_mini_receta:
            flash("Selecciona una mini receta válida.", "danger")
            return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))

        mini_receta = MiniRecetas.query.filter_by(idMiniReceta=id_mini_receta, estatus=1).first()
        if not mini_receta:
            flash("La mini receta seleccionada no existe o está inactiva.", "danger")
            return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))

        if not mini_receta.detalles:
            flash("La mini receta no tiene insumos definidos.", "danger")
            return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))

        # Asegurar que existe la receta del producto
        receta = _asegurar_receta_por_sp(id_producto)

        agregados = 0
        omitidos = 0
        for detalle_mr in mini_receta.detalles:
            # Verificar si ya existe ese insumo en la receta
            ya_existe = DetalleReceta.query.filter_by(
                idReceta=receta.idReceta,
                idMateriaP=detalle_mr.idMateriaP
            ).first()

            if ya_existe:
                omitidos += 1
                continue

            db.session.execute(
                text("CALL sp_gestion_detalle_receta(:accion,:idDetalleR,:idReceta,:idMateriaP,:cantidad,:ip,:usuario,@p_resultado,@p_idGenerado)"),
                {
                    "accion": "INSERT",
                    "idDetalleR": None,
                    "idReceta": receta.idReceta,
                    "idMateriaP": detalle_mr.idMateriaP,
                    "cantidad": detalle_mr.cantidad,
                    "ip": request.remote_addr,
                    "usuario": session["usuario_id"],
                },
            )
            resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
            if resultado and resultado.startswith("SUCCESS"):
                agregados += 1
            else:
                db.session.rollback()
                _, msg = _texto_resultado(resultado)
                flash(f"Error al agregar insumo: {msg}", "danger")
                return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))

        db.session.commit()
        _registrar_bitacora("Recetas", "Aplicar mini receta", "Mini Receta", mini_receta.nombre)
        db.session.commit()

        if agregados > 0 and omitidos == 0:
            flash(f"Mini receta «{mini_receta.nombre}» aplicada: {agregados} insumo(s) agregado(s).", "success")
        elif agregados > 0 and omitidos > 0:
            flash(
                f"Mini receta «{mini_receta.nombre}» aplicada: {agregados} insumo(s) nuevo(s) agregado(s), "
                f"{omitidos} ya existía(n) y no se modificaron.",
                "success",
            )
        else:
            flash(
                f"Todos los insumos de «{mini_receta.nombre}» ya están presentes en la receta. No se realizaron cambios.",
                "warning",
            )

    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/detalle/<int:id_detalle>/editar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def editar_detalle_receta(id_detalle):
    detalle = DetalleReceta.query.get_or_404(id_detalle)
    receta = detalle.receta
    try:
        cantidad = _parsear_cantidad(request.form["cantidad"])
        db.session.execute(
            text("CALL sp_gestion_detalle_receta(:accion,:idDetalleR,:idReceta,:idMateriaP,:cantidad,:ip,:usuario,@p_resultado,@p_idGenerado)"),
            {"accion": "UPDATE", "idDetalleR": id_detalle, "idReceta": detalle.idReceta,
             "idMateriaP": detalle.idMateriaP, "cantidad": cantidad,
             "ip": request.remote_addr, "usuario": session["usuario_id"]},
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "success":
            mp = MateriasPrimas.query.get(detalle.idMateriaP)
            _registrar_bitacora("Detalle Receta", "EDITAR INSUMO", "Materia Prima",
                                mp.nombre if mp else str(detalle.idMateriaP))
            db.session.commit()
        _guardar_mensaje_receta(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        _guardar_mensaje_receta(str(exc), "danger")
    return redirect(url_for("recetas.ver_receta_producto", id_producto=receta.idProducto))


@recetas.route("/recetas/detalle/<int:id_detalle>/eliminar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def eliminar_detalle_receta(id_detalle):
    detalle = DetalleReceta.query.get_or_404(id_detalle)
    receta = detalle.receta
    id_producto = receta.idProducto
    try:
        mp = MateriasPrimas.query.get(detalle.idMateriaP)
        nombre_mp = mp.nombre if mp else str(detalle.idMateriaP)
        db.session.execute(
            text("CALL sp_gestion_detalle_receta(:accion,:idDetalleR,:idReceta,:idMateriaP,:cantidad,:ip,:usuario,@p_resultado,@p_idGenerado)"),
            {"accion": "DELETE", "idDetalleR": id_detalle, "idReceta": detalle.idReceta,
             "idMateriaP": detalle.idMateriaP, "cantidad": detalle.cantidad,
             "ip": request.remote_addr, "usuario": session["usuario_id"]},
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "success":
            _registrar_bitacora("Detalle Receta", "Eliminar insumo", "Materia Prima", nombre_mp)
            db.session.commit()
        _guardar_mensaje_receta(mensaje, categoria)

        receta_actualizada = _obtener_receta_producto(id_producto)
        if receta_actualizada and categoria == "success":
            total_insumos = DetalleReceta.query.filter_by(idReceta=receta_actualizada.idReceta).count()
            if total_insumos < MINIMO_INSUMOS_RECETA:
                flash(
                    f"Aviso: la receta ahora tiene solo {total_insumos} insumo(s). "
                    f"Se recomienda incluir al menos {MINIMO_INSUMOS_RECETA} para una receta completa.",
                    "warning",
                )

    except Exception as exc:
        db.session.rollback()
        _guardar_mensaje_receta(str(exc), "danger")
    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))


@recetas.route("/recetas/producto/<int:id_producto>/eliminar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def eliminar_receta_completa(id_producto):
    producto = Productos.query.get_or_404(id_producto)
    receta = _obtener_receta_producto(id_producto)
    if not receta:
        flash("No hay receta para eliminar.", "danger")
        return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))
    try:
        db.session.execute(
            text("CALL sp_gestion_recetas(:accion,:idReceta,:idProducto,:descripcion,:ip,:usuario,@p_resultado,@p_idGenerado)"),
            {"accion": "DELETE", "idReceta": receta.idReceta, "idProducto": id_producto,
             "descripcion": None, "ip": request.remote_addr, "usuario": session["usuario_id"]},
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "success":
            _registrar_bitacora("Recetas", "Eliminar receta", "Producto", producto.nombre)
            db.session.commit()
        flash(mensaje, categoria)
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    # Redirigir siempre a la misma página de receta para ver el resultado
    return redirect(url_for("recetas.ver_receta_producto", id_producto=id_producto))