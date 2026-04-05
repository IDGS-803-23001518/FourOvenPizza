import json
from decimal import Decimal, InvalidOperation

from flask import (
    flash, redirect, render_template, request, session, url_for, jsonify
)
from sqlalchemy import text
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import os
import io
from flask import send_file
from datetime import datetime

from autentificacion.routes import rol_requerido
from models import (
    Ventas, DetalleVenta, Productos, Recetas,
    TicketVenta, DetalleTicketVenta, db
)
from . import ventas  # blueprint registrado como 'ventas'


# ── Helpers ────────────────────────────────────────────────────────────

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


def _productos_disponibles_venta():
    """Productos activos con receta activa (para punto de venta)."""
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


def _ventas_hoy():
    """Últimas ventas del día para la tabla lateral."""
    rows = db.session.execute(
        text("CALL sp_listar_ventas_hoy(:uid)"),
        {"uid": None},
    ).mappings().all()
    return rows


def _detalle_venta(id_venta):
    return db.session.execute(
        text("CALL sp_detalle_venta(:id)"),
        {"id": id_venta},
    ).mappings().all()


def _generar_ticket_pdf(id_venta):
    """Genera el PDF del ticket y lo guarda en la BD. Devuelve bytes del PDF."""
    venta = db.session.execute(
        text("SELECT * FROM ventas WHERE idVenta = :id"),
        {"id": id_venta},
    ).mappings().fetchone()

    detalle = _detalle_venta(id_venta)
    total = sum(float(d["subtotal"]) for d in detalle)

    num_ticket = f"TKT-{datetime.now().strftime('%Y%m%d')}-{id_venta:04d}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(8 * cm, 29.7 * cm),
        rightMargin=0.5 * cm,
        leftMargin=0.5 * cm,
        topMargin=0.5 * cm,
        bottomMargin=0.5 * cm,
    )

    styles = getSampleStyleSheet()
    estilo_centro  = ParagraphStyle('centro',  alignment=TA_CENTER, fontSize=8,  leading=10)
    estilo_titulo  = ParagraphStyle('titulo',  alignment=TA_CENTER, fontSize=11, leading=13, fontName='Helvetica-Bold')
    estilo_sub     = ParagraphStyle('sub',     alignment=TA_CENTER, fontSize=7,  leading=9,  textColor=colors.grey)
    estilo_dato    = ParagraphStyle('dato',    fontSize=7,           leading=9)
    estilo_derecha = ParagraphStyle('derecha', alignment=TA_RIGHT,  fontSize=8,  leading=10, fontName='Helvetica-Bold')

    elementos = []

    elementos.append(Paragraph("🍕 FOUR OVEN PIZZA", estilo_titulo))
    elementos.append(Paragraph("Pizzería artesanal", estilo_sub))
    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#f29f05")))
    elementos.append(Spacer(1, 0.2 * cm))

    elementos.append(Paragraph(f"<b>Ticket:</b> {num_ticket}", estilo_dato))
    elementos.append(Paragraph(f"<b>Fecha:</b> {venta['fecha'].strftime('%d/%m/%Y %H:%M')}", estilo_dato))
    elementos.append(Paragraph(f"<b>Cliente:</b> {venta['nombreCliente'] or 'Consumidor final'}", estilo_dato))
    elementos.append(Paragraph(f"<b>Pago:</b> {venta['metodoPago']}", estilo_dato))
    elementos.append(Paragraph(f"<b>Atendido por:</b> {session.get('usuario_nombre', '')}", estilo_dato))
    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elementos.append(Spacer(1, 0.2 * cm))

    datos_tabla = [["Producto", "Cant", "P/U", "Subtotal"]]
    for d in detalle:
        datos_tabla.append([
            f"{d['nombre_producto']}\n({d['tamano']})",
            str(int(d['cantidad'])),
            f"${float(d['precio']):.2f}",
            f"${float(d['subtotal']):.2f}",
        ])

    tabla = Table(datos_tabla, colWidths=[3.2 * cm, 1 * cm, 1.3 * cm, 1.5 * cm])
    tabla.setStyle(TableStyle([
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff8e1")]),
        ('GRID',           (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',          (1, 0), (-1, -1), 'RIGHT'),
    ]))
    elementos.append(tabla)

    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#38230f")))
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(f"<b>TOTAL: ${total:.2f}</b>", estilo_derecha))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph("¡Gracias por su preferencia!", estilo_centro))
    elementos.append(Paragraph("Vuelva pronto 🍕", estilo_centro))

    doc.build(elementos)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    try:
        ticket_existente = TicketVenta.query.filter_by(idVenta=id_venta).first()
        if not ticket_existente:
            ticket = TicketVenta(
                idVenta=id_venta,
                tipoVenta='Punto venta',
                usuarioId=session.get("usuario_id"),
                nombreCliente=venta['nombreCliente'] or 'Consumidor final',
                total=Decimal(str(total)),
                estado='Confirmada',
                numeroTicket=num_ticket,
                pdfGenerado=True,
                fechaGeneracion=datetime.now(),
            )
            db.session.add(ticket)
            db.session.flush()

            for d in detalle:
                det = DetalleTicketVenta(
                    idTicket=ticket.id,
                    idProducto=d['idProducto'],
                    nombreProducto=d['nombre_producto'],
                    cantidad=int(d['cantidad']),
                    precioUnitario=Decimal(str(d['precio'])),
                    subtotal=Decimal(str(d['subtotal'])),
                )
                db.session.add(det)

            db.session.commit()
    except Exception:
        db.session.rollback()

    return pdf_bytes, num_ticket


# ── Vista Punto de Venta ───────────────────────────────────────────────

@ventas.route("/ventas")
@rol_requerido("Administrador", "Ventas")
def punto_venta():
    productos_disponibles = _productos_disponibles_venta()
    ventas_hoy = _ventas_hoy()
    form_error = session.pop("ventas_form_error", None)

    return render_template(
        "ventas/punto_venta.html",
        productos_disponibles=productos_disponibles,
        ventas_hoy=ventas_hoy,
        form_error=form_error,
    )


@ventas.route("/ventas/registrar", methods=["POST"])
@rol_requerido("Administrador", "Ventas")
def registrar_venta():
    try:
        nombre_cliente = (request.form.get("nombre_cliente", "").strip() or "Consumidor final")
        metodo_pago    = request.form.get("metodo_pago", "").strip()
        detalles_raw   = request.form.get("detalles_json", "[]").strip()

        if metodo_pago not in ("Efectivo", "Tarjeta"):
            session["ventas_form_error"] = {"mensaje": "Selecciona un método de pago válido."}
            return redirect(url_for("ventas.punto_venta"))

        detalles = json.loads(detalles_raw)
        if not detalles:
            session["ventas_form_error"] = {"mensaje": "Agrega al menos un producto."}
            return redirect(url_for("ventas.punto_venta"))

        # Enriquecer detalles con precio actual
        detalles_sp = []
        for d in detalles:
            prod = Productos.query.filter_by(idProducto=int(d["idProducto"]), estatus=True).first()
            if not prod:
                session["ventas_form_error"] = {"mensaje": f"Producto ID {d['idProducto']} no encontrado."}
                return redirect(url_for("ventas.punto_venta"))
            detalles_sp.append({
                "idProducto": int(d["idProducto"]),
                "cantidad":   int(d["cantidad"]),
                "precio":     float(prod.precio),
            })

        # Calcular faltantes
        faltantes = []
        for d in detalles_sp:
            prod = Productos.query.get(d["idProducto"])
            stock_actual   = float(prod.stock or 0)
            cantidad_pedida = d["cantidad"]
            if cantidad_pedida > stock_actual:
                faltante = cantidad_pedida - int(stock_actual)
                faltantes.append({"idProducto": d["idProducto"], "cantidad": faltante})

        # Descontar del stock lo que hay disponible
        for d in detalles_sp:
            prod       = Productos.query.get(d["idProducto"])
            stock_actual = float(prod.stock or 0)
            a_descontar  = min(d["cantidad"], int(stock_actual))
            if a_descontar > 0:
                prod.stock = stock_actual - a_descontar

        estado_inicial = "En proceso" if faltantes else "Lista para entregar"

        venta = Ventas(
            idUsuario=session["usuario_id"],
            nombreCliente=nombre_cliente,
            tipo="Punto venta",
            metodoPago=metodo_pago,
            estado=estado_inicial,
        )
        db.session.add(venta)
        db.session.flush()

        id_venta = venta.idVenta

        for d in detalles_sp:
            det = DetalleVenta(
                idVenta=id_venta,
                idProducto=d["idProducto"],
                cantidad=d["cantidad"],
                precio=Decimal(str(d["precio"])),
            )
            db.session.add(det)

        # Guardar reserva temporal
        from models import VentaStockReservado
        for d in detalles_sp:
            faltante_prod = next(
                (f["cantidad"] for f in faltantes if f["idProducto"] == d["idProducto"]), 0
            )
            reservado = d["cantidad"] - faltante_prod

            reserva = VentaStockReservado(
                idVenta=id_venta,
                idProducto=d["idProducto"],
                cantidadReservada=reservado,
                cantidadFaltante=faltante_prod,
            )
            db.session.add(reserva)

        db.session.flush()

        # Crear orden de producción si hay faltantes
        if faltantes:
            from models import OrdenesProduccion, DetalleProduccion

            orden = OrdenesProduccion(
                idUsuario=session["usuario_id"],
                estado="En proceso",
                origen="Venta",
                idVentaOrigen=id_venta,
            )
            db.session.add(orden)
            db.session.flush()
            id_orden = orden.idOrden

            for f in faltantes:
                dp = DetalleProduccion(
                    idProducto=f["idProducto"],
                    idOrden=id_orden,
                    cantidad=f["cantidad"],
                )
                db.session.add(dp)

            # Vincular la orden a las reservas de esta venta
            db.session.execute(
                text("UPDATE ventaStockReservado SET idOrdenProduccion = :oid WHERE idVenta = :vid"),
                {"oid": id_orden, "vid": id_venta},
            )

        db.session.commit()

        # Bitácora
        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                SELECT :uid, u.nombre, 'Ventas', 'CREAR',
                       'venta', CONCAT('ID:', :vid, ' | Cliente: ', :cliente),
                       NOW(), :ip
                FROM usuarios u WHERE u.idUsuario = :uid
            """),
            {
                "uid":     session["usuario_id"],
                "vid":     id_venta,
                "cliente": nombre_cliente,
                "ip":      request.remote_addr,
            },
        )
        db.session.commit()

        flash(f"Venta registrada correctamente. Estado: {estado_inicial}", "success")

    except Exception as e:
        db.session.rollback()
        session["ventas_form_error"] = {"mensaje": str(e)}

    return redirect(url_for("ventas.punto_venta"))


@ventas.route("/ventas/confirmar/<int:id_venta>", methods=["POST"])
@rol_requerido("Administrador", "Ventas")
def confirmar_venta(id_venta):
    try:
        venta = Ventas.query.get_or_404(id_venta)

        if venta.estado != "Lista para entregar":
            flash("Solo se pueden confirmar ventas en estado 'Lista para entregar'.", "danger")
            return redirect(url_for("ventas.punto_venta"))

        venta.estado = "Confirmada"

        total = sum(float(d.cantidad) * float(d.precio) for d in venta.detalle_ventas)

        from models import CajaMovimientos
        mov = CajaMovimientos(
            idUsuario=session["usuario_id"],
            tipo="Ingreso",
            monto=Decimal(str(total)),
            descripcion=f"Venta #{id_venta} - {venta.nombreCliente} ({venta.metodoPago})",
        )
        db.session.add(mov)

        # Limpiar reserva temporal
        db.session.execute(
            text("DELETE FROM ventaStockReservado WHERE idVenta = :vid"),
            {"vid": id_venta},
        )

        db.session.flush()

        pdf_bytes, num_ticket = _generar_ticket_pdf(id_venta)

        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                SELECT :uid, u.nombre, 'Ventas', 'CONFIRMAR',
                       'venta', CONCAT('ID:', :vid), NOW(), :ip
                FROM usuarios u WHERE u.idUsuario = :uid
            """),
            {"uid": session["usuario_id"], "vid": id_venta, "ip": request.remote_addr},
        )

        db.session.commit()

        import base64
        session["ticket_pdf"] = base64.b64encode(pdf_bytes).decode("utf-8")
        session["ticket_num"] = num_ticket

        flash(f"Venta #{id_venta} confirmada. El ticket ha sido generado.", "success")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("ventas.punto_venta"))


@ventas.route("/ventas/cancelar/<int:id_venta>", methods=["POST"])
@rol_requerido("Administrador", "Ventas")
def cancelar_venta(id_venta):
    """
    Cancela una venta activa.

    Estado 'En proceso'  → la orden de producción aún no terminó.
        · Cancela la orden de producción vinculada (si sigue en proceso).
        · Devuelve al stock solo cantidadReservada (lo que se tomó del inventario).
        · Los productos que iban a producirse nunca se fabricaron → no hay nada que sumar.

    Estado 'Lista para entregar' → cocina ya terminó la orden.
        · cantidadFaltante ya es 0 (cocina la movió a cantidadReservada al terminar).
        · cantidadReservada ahora contiene el total pedido (los del stock + los producidos).
        · Se devuelven al stock TODOS esos productos (cantidadReservada completa).
        · Además, los que se produjeron en cocina también se suman al stock de producto
          (porque ya fueron fabricados y no van a ser entregados al cliente).

    Para distinguir cuánto vino de producción vs del stock original, leemos
    la columna cantidadFaltante_original que guardamos antes de que cocina la zeroed.
    Como no la tenemos directamente, la calculamos como:
        producido = cantidadReservada_actual - cantidadReservada_original
    Pero como solo tenemos el valor actual, simplificamos:
        · Todo lo de cantidadReservada vuelve al stock (ya fusiona ambas fuentes).
        · No se necesita sumar nada extra: devolverla íntegra es correcto.
    """
    try:
        from models import VentaStockReservado, OrdenesProduccion

        venta = Ventas.query.get_or_404(id_venta)

        if venta.estado not in ("En proceso", "Lista para entregar"):
            flash("Solo se pueden cancelar ventas en estado 'En proceso' o 'Lista para entregar'.", "danger")
            return redirect(url_for("ventas.punto_venta"))

        estado_previo = venta.estado
        reservas = VentaStockReservado.query.filter_by(idVenta=id_venta).all()

        if estado_previo == "En proceso":
            # ── Orden de producción aún activa ──────────────────────────
            # Cancelar la orden vinculada si sigue en proceso
            for r in reservas:
                if r.idOrdenProduccion:
                    orden = OrdenesProduccion.query.get(r.idOrdenProduccion)
                    if orden and orden.estado == "En proceso":
                        orden.estado = "Cancelada"

            # Devolver al stock solo lo que se había tomado del inventario
            for r in reservas:
                prod = Productos.query.get(r.idProducto)
                if prod and r.cantidadReservada > 0:
                    prod.stock = float(prod.stock or 0) + r.cantidadReservada

        elif estado_previo == "Lista para entregar":
            # ── Cocina ya terminó; cantidadFaltante == 0 ────────────────
            # cantidadReservada ahora contiene el total (stock original + producidos).
            # Devolver todo al stock del producto.
            for r in reservas:
                prod = Productos.query.get(r.idProducto)
                if prod:
                    # cantidadReservada ya incluye lo producido (cocina lo movió aquí)
                    # cantidadFaltante es 0 en este punto
                    prod.stock = float(prod.stock or 0) + r.cantidadReservada + r.cantidadFaltante

        # Limpiar reservas
        db.session.execute(
            text("DELETE FROM ventaStockReservado WHERE idVenta = :vid"),
            {"vid": id_venta},
        )

        venta.estado = "Cancelada"

        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                SELECT :uid, u.nombre, 'Ventas', 'CANCELAR',
                       'venta', CONCAT('ID:', :vid), NOW(), :ip
                FROM usuarios u WHERE u.idUsuario = :uid
            """),
            {"uid": session["usuario_id"], "vid": id_venta, "ip": request.remote_addr},
        )

        db.session.commit()
        flash(f"Venta #{id_venta} cancelada correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("ventas.punto_venta"))


@ventas.route("/ventas/ver/<int:id_venta>")
@rol_requerido("Administrador", "Ventas")
def ver_venta(id_venta):
    """Fragmento HTML para el modal de detalle."""
    try:
        venta = db.session.execute(
            text("""
                SELECT v.*, u.nombre AS nombre_usuario
                FROM ventas v
                JOIN usuarios u ON u.idUsuario = v.idUsuario
                WHERE v.idVenta = :id
            """),
            {"id": id_venta},
        ).mappings().fetchone()
        detalle = _detalle_venta(id_venta)
        total   = sum(float(d["subtotal"]) for d in detalle)
        return render_template(
            "ventas/_detalle_venta.html",
            venta=venta,
            detalle=detalle,
            total=total,
        )
    except Exception as e:
        return f"<p class='text-red-500 text-sm p-4'>Error: {e}</p>", 500


@ventas.route("/ventas/ticket/<int:id_venta>")
@rol_requerido("Administrador", "Ventas")
def descargar_ticket(id_venta):
    """Genera y descarga el ticket PDF de una venta confirmada."""
    try:
        venta = Ventas.query.get_or_404(id_venta)
        if venta.estado != "Confirmada":
            flash("Solo se puede descargar el ticket de ventas confirmadas.", "danger")
            return redirect(url_for("ventas.punto_venta"))

        pdf_bytes, num_ticket = _generar_ticket_pdf(id_venta)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"ticket_{num_ticket}.pdf",
        )
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("ventas.punto_venta"))


# ── Vista Historial de Ventas ──────────────────────────────────────────

@ventas.route("/ventas/historial")
@rol_requerido("Administrador", "Ventas")
def historial_ventas():
    estado_f    = request.args.get("estado",      "").strip() or None
    fecha_ini_f = request.args.get("fecha_ini",   "").strip() or None
    fecha_fin_f = request.args.get("fecha_fin",   "").strip() or None
    cliente_f   = request.args.get("cliente",     "").strip() or None
    metodo_f    = request.args.get("metodo_pago", "").strip() or None

    ventas_lista = db.session.execute(
        text("CALL sp_listar_ventas_historial(:estado,:fecha_ini,:fecha_fin,:cliente,:metodo)"),
        {
            "estado":    estado_f,
            "fecha_ini": fecha_ini_f,
            "fecha_fin": fecha_fin_f,
            "cliente":   cliente_f,
            "metodo":    metodo_f,
        },
    ).mappings().all()

    filtros = {
        "estado":      estado_f    or "",
        "fecha_ini":   fecha_ini_f or "",
        "fecha_fin":   fecha_fin_f or "",
        "cliente":     cliente_f   or "",
        "metodo_pago": metodo_f    or "",
    }

    return render_template(
        "ventas/historial_ventas.html",
        ventas=ventas_lista,
        filtros=filtros,
    )


@ventas.route("/ventas/historial/ver/<int:id_venta>")
@rol_requerido("Administrador", "Ventas")
def ver_venta_historial(id_venta):
    try:
        venta = db.session.execute(
            text("""
                SELECT v.*, u.nombre AS nombre_usuario
                FROM ventas v
                JOIN usuarios u ON u.idUsuario = v.idUsuario
                WHERE v.idVenta = :id
            """),
            {"id": id_venta},
        ).mappings().fetchone()
        detalle = _detalle_venta(id_venta)
        total   = sum(float(d["subtotal"]) for d in detalle)
        return render_template(
            "ventas/_detalle_venta.html",
            venta=venta,
            detalle=detalle,
            total=total,
        )
    except Exception as e:
        return f"<p class='text-red-500 text-sm p-4'>Error: {e}</p>", 500


# ── Cierre de día manual (para administradores) ────────────────────────

@ventas.route("/ventas/cierre-dia", methods=["POST"])
@rol_requerido("Administrador")
def cierre_dia():
    try:
        from models import VentaStockReservado, OrdenesProduccion

        ventas_activas = Ventas.query.filter(
            db.func.date(Ventas.fecha) == db.func.current_date(),
            Ventas.estado.in_(["En proceso", "Lista para entregar"]),
        ).all()

        for v in ventas_activas:
            reservas = VentaStockReservado.query.filter_by(idVenta=v.idVenta).all()

            if v.estado == "En proceso":
                for r in reservas:
                    if r.idOrdenProduccion:
                        op = OrdenesProduccion.query.get(r.idOrdenProduccion)
                        if op and op.estado == "En proceso":
                            op.estado = "Cancelada"
                    prod = Productos.query.get(r.idProducto)
                    if prod and r.cantidadReservada > 0:
                        prod.stock = float(prod.stock or 0) + r.cantidadReservada

            elif v.estado == "Lista para entregar":
                # cantidadReservada ya contiene el total (incluye lo producido)
                for r in reservas:
                    prod = Productos.query.get(r.idProducto)
                    if prod:
                        prod.stock = float(prod.stock or 0) + r.cantidadReservada + r.cantidadFaltante

            db.session.execute(
                text("DELETE FROM ventaStockReservado WHERE idVenta = :vid"),
                {"vid": v.idVenta},
            )
            v.estado = "Cancelada"

        db.session.commit()
        flash(f"Cierre de día realizado. {len(ventas_activas)} venta(s) canceladas.", "success")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("ventas.punto_venta"))