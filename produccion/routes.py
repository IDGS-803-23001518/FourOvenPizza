import json
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import DetalleProduccion, MateriasPrimas, OrdenesProduccion, Productos, Recetas, db

from . import produccion  # blueprint registrado como 'produccion'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _texto_resultado(resultado):
    if not resultado:
        return "No se obtuvo respuesta del servidor.", "danger"
    if ":" in resultado:
        _, mensaje = resultado.split(":", 1)
        mensaje = mensaje.strip()
    else:
        mensaje = resultado.strip()
    categoria = "success" if resultado.startswith("SUCCESS") else "danger"
    return mensaje, categoria


def _productos_disponibles():
    """Productos activos con receta activa."""
    rows = db.session.execute(
        text(
            "CALL sp_listar_productos(:nombre,:precio_ini,:precio_fin,:estatus,:tamano,:estatus_receta)"
        ),
        {
            "nombre":         None,
            "precio_ini":     None,
            "precio_fin":     None,
            "estatus":        "1",
            "tamano":         None,
            "estatus_receta": "1",
        },
    ).mappings().all()
    return rows


def _detalle_orden(id_orden):
    return db.session.execute(
        text("CALL sp_detalle_orden_produccion(:id)"),
        {"id": id_orden},
    ).mappings().all()


def _segundos_desde_creacion(id_orden):
    row = db.session.execute(
        text(
            "SELECT TIMESTAMPDIFF(SECOND, fecha, NOW()) AS seg "
            "FROM ordenesProduccion WHERE idOrden = :id"
        ),
        {"id": id_orden},
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 9999


# ── Vista ADMINISTRADOR ────────────────────────────────────────────────────────

@produccion.route("/produccion")
@rol_requerido("Administrador")
def listado_ordenes():
    estado_f    = request.args.get("estado",    "").strip() or None
    fecha_ini_f = request.args.get("fecha_ini", "").strip() or None
    fecha_fin_f = request.args.get("fecha_fin", "").strip() or None
    pagina_f    = request.args.get("page", "1").strip()
    
    try:
        pagina = int(pagina_f)
        if pagina < 1:
            pagina = 1
    except ValueError:
        pagina = 1
    
    limite = 10

    ordenes = db.session.execute(
        text("CALL sp_listar_ordenes_produccion(:estado, :fecha_ini, :fecha_fin)"),
        {"estado": estado_f, "fecha_ini": fecha_ini_f, "fecha_fin": fecha_fin_f},
    ).mappings().all()
    
    total_ordenes = len(ordenes)
    total_paginas = (total_ordenes + limite - 1) // limite if total_ordenes > 0 else 1
    
    if pagina > total_paginas:
        pagina = total_paginas if total_paginas > 0 else 1
    
    inicio = (pagina - 1) * limite
    fin = inicio + limite
    ordenes_pagina = ordenes[inicio:fin] if ordenes else []

    productos_disponibles = _productos_disponibles()
    form_error     = session.pop("produccion_form_error",    None)
    detalle_editar = session.pop("produccion_detalle_editar", None)

    filtros = {
        "estado":    estado_f    or "",
        "fecha_ini": fecha_ini_f or "",
        "fecha_fin": fecha_fin_f or "",
    }

    return render_template(
        "produccion/ordenes.html",
        ordenes=ordenes_pagina,
        productos_disponibles=productos_disponibles,
        form_error=form_error,
        detalle_editar=detalle_editar,
        filtros=filtros,
        pagina_actual=pagina,
        total_paginas=total_paginas,
        total_ordenes=total_ordenes,
    )


@produccion.route("/produccion/registrar", methods=["POST"])
@rol_requerido("Administrador")
def registrar_orden():
    try:
        detalles_raw = request.form.get("detalles_json", "[]").strip()
        detalles     = json.loads(detalles_raw)

        if not detalles:
            session["produccion_form_error"] = {
                "modal": "registro", "mensaje": "Agrega al menos un producto.", "detalles": [],
            }
            return redirect(url_for("produccion.listado_ordenes"))

        detalles_sp = json.dumps(
            [{"idProducto": int(d["idProducto"]), "cantidad": int(d["cantidad"])} for d in detalles]
        )

        db.session.execute(
            text(
                "CALL sp_gestion_ordenes_produccion("
                ":accion,:idOrden,:idUsuario,:estado,:detalles,:ip,:ejecutadoPor,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "INSERT", "idOrden": None,
                "idUsuario": session["usuario_id"], "estado": None,
                "detalles": detalles_sp, "ip": request.remote_addr,
                "ejecutadoPor": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)

        if categoria == "danger":
            session["produccion_form_error"] = {
                "modal": "registro", "mensaje": mensaje, "detalles": detalles,
            }
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        session["produccion_form_error"] = {
            "modal": "registro", "mensaje": str(e), "detalles": [],
        }

    return redirect(url_for("produccion.listado_ordenes"))


@produccion.route("/produccion/editar/<int:id_orden>", methods=["POST"])
@rol_requerido("Administrador")
def editar_orden(id_orden):
    try:
        seg = _segundos_desde_creacion(id_orden)
        if seg > 60:
            flash("El tiempo de edición ha expirado (máximo 1 minuto).", "danger")
            return redirect(url_for("produccion.listado_ordenes"))

        detalles_raw = request.form.get("detalles_json", "[]").strip()
        detalles     = json.loads(detalles_raw)

        if not detalles:
            flash("Agrega al menos un producto.", "danger")
            return redirect(url_for("produccion.listado_ordenes"))

        detalles_sp = json.dumps(
            [{"idProducto": int(d["idProducto"]), "cantidad": int(d["cantidad"])} for d in detalles]
        )

        db.session.execute(
            text(
                "CALL sp_gestion_ordenes_produccion("
                ":accion,:idOrden,:idUsuario,:estado,:detalles,:ip,:ejecutadoPor,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "UPDATE", "idOrden": id_orden,
                "idUsuario": session["usuario_id"], "estado": None,
                "detalles": detalles_sp, "ip": request.remote_addr,
                "ejecutadoPor": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)

        if categoria == "danger":
            session["produccion_form_error"] = {
                "modal": "edicion", "mensaje": mensaje, "id_orden": id_orden,
            }
            session["produccion_detalle_editar"] = {
                "id_orden": id_orden, "detalles": detalles,
            }
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("produccion.listado_ordenes"))


@produccion.route("/produccion/cancelar/<int:id_orden>", methods=["POST"])
@rol_requerido("Administrador")
def cancelar_orden(id_orden):
    try:
        db.session.execute(
            text(
                "CALL sp_gestion_ordenes_produccion("
                ":accion,:idOrden,:idUsuario,:estado,:detalles,:ip,:ejecutadoPor,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "CHANGE_STATUS", "idOrden": id_orden,
                "idUsuario": session["usuario_id"], "estado": "Cancelada",
                "detalles": None, "ip": request.remote_addr,
                "ejecutadoPor": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("produccion.listado_ordenes"))


@produccion.route("/produccion/ver/<int:id_orden>")
@rol_requerido("Administrador")
def ver_orden(id_orden):
    """Fragmento HTML para el modal Ver (admin)."""
    try:
        detalle = _detalle_orden(id_orden)
        seg     = _segundos_desde_creacion(id_orden)
        orden   = db.session.execute(
            text("SELECT * FROM ordenesProduccion WHERE idOrden = :id"),
            {"id": id_orden},
        ).mappings().fetchone()
        return render_template(
            "produccion/_detalle_orden.html",
            detalle=detalle, orden=orden, segundos=seg,
        )
    except Exception as e:
        return f"<p class='text-red-500 text-sm p-4'>Error: {e}</p>", 500


@produccion.route("/produccion/detalle-json/<int:id_orden>")
@rol_requerido("Administrador")
def detalle_orden_json(id_orden):
    try:
        detalle = _detalle_orden(id_orden)
        seg     = _segundos_desde_creacion(id_orden)
        orden   = db.session.execute(
            text("SELECT fecha FROM ordenesProduccion WHERE idOrden = :id"),
            {"id": id_orden},
        ).mappings().fetchone()

        ts_unix = int(orden["fecha"].timestamp()) if orden and orden["fecha"] else 0

        items = [
            {
                "idProducto": d["idProducto"],
                "nombre":     d["nombre_producto"],
                "tamano":     d["tamano"],
                "cantidad":   int(d["cantidad"]),
            }
            for d in detalle
        ]

        return jsonify({
            "ok":      True,
            "items":   items,
            "ts_unix": ts_unix,
            "segundos_transcurridos": seg,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Vista COCINA ──────────────────────────────────────────────────────────────

@produccion.route("/produccion/cocina")
@rol_requerido("Cocinero", "Administrador")
def vista_cocina():
    ordenes = db.session.execute(
        text("CALL sp_ordenes_cocina()")
    ).mappings().all()

    ordenes_con_detalle = []
    for o in ordenes:
        detalle = _detalle_orden(o["idOrden"])
        ordenes_con_detalle.append({**o, "detalle": detalle})

    return render_template(
        "produccion/cocina.html",
        ordenes=ordenes_con_detalle,
    )


@produccion.route("/produccion/cocina/json")
@rol_requerido("Cocinero", "Administrador")
def cocina_json():
    try:
        ordenes = db.session.execute(
            text("CALL sp_ordenes_cocina()")
        ).mappings().all()

        resultado = []
        for o in ordenes:
            detalle = _detalle_orden(o["idOrden"])
            ts_unix = int(o["fecha"].timestamp()) if o["fecha"] else 0
            hora    = o["fecha"].strftime("%H:%M") if o["fecha"] else ""

            resultado.append({
                "idOrden":        o["idOrden"],
                "nombre_usuario": o["nombre_usuario"],
                "ts_unix":        ts_unix,
                "hora":           hora,
                "minutos_espera": int(o["minutos_espera"]) if o["minutos_espera"] is not None else 0,
                "detalle": [
                    {
                        "idProducto":      d["idProducto"],
                        "nombre_producto": d["nombre_producto"],
                        "tamano":          d["tamano"],
                        "cantidad":        int(d["cantidad"]),
                        "idReceta":        d["idReceta"],
                    }
                    for d in detalle
                ],
            })

        return jsonify({"ok": True, "ordenes": resultado})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@produccion.route("/produccion/terminar/<int:id_orden>", methods=["POST"])
@rol_requerido("Cocinero", "Administrador")
def terminar_orden(id_orden):
    """
    Termina una orden de producción.

    - Si la orden es de origen 'Venta':
        · Descuenta materias primas.
        · NO suma al stock de productos terminados (irán al cliente).
        · Mueve cantidadFaltante → cantidadReservada en ventaStockReservado.
        · Si no quedan órdenes pendientes para esa venta, cambia la venta
          a 'Lista para entregar' para que el vendedor pueda confirmarla.

    - Si la orden es manual:
        · Descuenta materias primas.
        · Suma los productos producidos al stock de inventario.
    """
    try:
        orden = OrdenesProduccion.query.get_or_404(id_orden)

        if orden.estado != "En proceso":
            flash("La orden ya no está en proceso.", "danger")
            return redirect(url_for("produccion.vista_cocina"))

        origen    = orden.origen or "Manual"
        id_venta  = orden.idVentaOrigen

        # ── Descontar materias primas (aplica siempre) ──────────────────
        db.session.execute(
            text("""
                UPDATE materiasPrimas mp
                JOIN (
                    SELECT dr.idMateriaP,
                           SUM(dr.cantidad * dp.cantidad) AS total_consumido
                    FROM detalleProduccion dp
                    JOIN recetas r       ON r.idProducto  = dp.idProducto
                    JOIN detalleReceta dr ON dr.idReceta   = r.idReceta
                    WHERE dp.idOrden = :id
                    GROUP BY dr.idMateriaP
                ) consumo ON consumo.idMateriaP = mp.idMateriaP
                SET mp.stock = mp.stock - consumo.total_consumido
            """),
            {"id": id_orden},
        )

        # ── Marcar orden como Terminada ─────────────────────────────────
        orden.estado = "Terminada"

        if origen == "Venta" and id_venta:
            # ── Orden vinculada a una venta ─────────────────────────────

            # Mover cantidadFaltante a cantidadReservada
            # (los productos ya están listos para el cliente)
            db.session.execute(
                text("""
                    UPDATE ventaStockReservado
                    SET cantidadReservada = cantidadReservada + cantidadFaltante,
                        cantidadFaltante  = 0
                    WHERE idVenta = :vid AND idOrdenProduccion = :oid
                """),
                {"vid": id_venta, "oid": id_orden},
            )

            # ¿Quedan otras órdenes activas para esta venta?
            pendientes = db.session.execute(
                text("""
                    SELECT COUNT(*) AS cnt
                    FROM ventaStockReservado vsr
                    JOIN ordenesProduccion op ON op.idOrden = vsr.idOrdenProduccion
                    WHERE vsr.idVenta          = :vid
                      AND op.estado            = 'En proceso'
                      AND vsr.cantidadFaltante > 0
                """),
                {"vid": id_venta},
            ).scalar()

            if pendientes == 0:
                from models import Ventas as VentasModel
                venta_obj = VentasModel.query.get(id_venta)
                if venta_obj and venta_obj.estado == "En proceso":
                    venta_obj.estado = "Lista para entregar"

        else:
            # ── Orden manual: sumar al stock de productos terminados ────
            db.session.execute(
                text("""
                    UPDATE productos p
                    JOIN detalleProduccion dp ON dp.idProducto = p.idProducto
                    SET p.stock = p.stock + dp.cantidad
                    WHERE dp.idOrden = :id
                """),
                {"id": id_orden},
            )

        # ── Bitácora ────────────────────────────────────────────────────
        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                SELECT :uid, u.nombre, 'Produccion', 'TERMINAR',
                       'orden', CONCAT('ID:', :oid), NOW(), :ip
                FROM usuarios u WHERE u.idUsuario = :uid
            """),
            {"uid": session["usuario_id"], "oid": id_orden, "ip": request.remote_addr},
        )

        db.session.commit()
        flash("Orden marcada como terminada correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("produccion.vista_cocina"))


@produccion.route("/produccion/cocina/cancelar/<int:id_orden>", methods=["POST"])
@rol_requerido("Cocinero", "Administrador")
def cancelar_orden_cocina(id_orden):
    try:
        db.session.execute(
            text(
                "CALL sp_gestion_ordenes_produccion("
                ":accion,:idOrden,:idUsuario,:estado,:detalles,:ip,:ejecutadoPor,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "CHANGE_STATUS", "idOrden": id_orden,
                "idUsuario": session["usuario_id"], "estado": "Cancelada",
                "detalles": None, "ip": request.remote_addr,
                "ejecutadoPor": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("produccion.vista_cocina"))


@produccion.route("/produccion/receta/<int:id_producto>")
@rol_requerido("Cocinero", "Administrador")
def receta_readonly(id_producto):
    try:
        producto = Productos.query.get_or_404(id_producto)
        receta   = Recetas.query.filter_by(idProducto=id_producto).first()
        detalles = []
        if receta:
            detalles = sorted(
                receta.detalle_recetas,
                key=lambda d: (d.materia_prima.nombre or "").lower(),
            )
        return render_template(
            "produccion/_receta_readonly.html",
            producto=producto,
            receta=receta,
            detalles=detalles,
        )
    except Exception as e:
        return f"<p class='text-red-500 text-sm p-4'>Error: {e}</p>", 500