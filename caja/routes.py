import io
from datetime import date, timedelta
from decimal import Decimal

from flask import (
    Blueprint, flash, jsonify, redirect, render_template,
    request, session, url_for
)
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import db

caja = Blueprint("caja", __name__)


# ── Helpers ────────────────────────────────────────────────────────────

def _raw_call(sql, params=()):
    """
    Ejecuta un stored procedure con el cursor raw de PyMySQL
    y devuelve todos los result sets como lista de listas de dicts.
    """
    raw_conn = db.engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        cur.execute(sql, params)
        result_sets = []
        while True:
            if cur.description:
                cols = [d[0] for d in cur.description]
                result_sets.append([dict(zip(cols, row)) for row in cur.fetchall()])
            else:
                result_sets.append([])
            if not cur.nextset():
                break
        return result_sets
    finally:
        cur.close()
        raw_conn.close()


def _resumen_dia(fecha: str):
    """
    Resumen del día incluyendo ventas de punto de venta Y en línea.
    """
    try:
        # Totales por tipo y método de pago — incluye TODOS los tipos de venta
        ventas_row = db.session.execute(
            text("""
                SELECT
                    COALESCE(SUM(CASE WHEN v.metodoPago = 'Efectivo' THEN dv_t.total ELSE 0 END), 0) AS total_efectivo,
                    COALESCE(SUM(CASE WHEN v.metodoPago = 'Tarjeta'  THEN dv_t.total ELSE 0 END), 0) AS total_tarjeta,
                    COALESCE(SUM(dv_t.total), 0)                                                      AS total_ventas,
                    COUNT(v.idVenta)                                                                   AS num_ventas,
                    COALESCE(SUM(CASE WHEN v.tipo = 'Punto venta' THEN dv_t.total ELSE 0 END), 0)    AS total_punto_venta,
                    COALESCE(SUM(CASE WHEN v.tipo = 'En linea'    THEN dv_t.total ELSE 0 END), 0)    AS total_en_linea
                FROM ventas v
                JOIN (
                    SELECT idVenta, SUM(cantidad * precio) AS total
                    FROM detalleVenta GROUP BY idVenta
                ) dv_t ON dv_t.idVenta = v.idVenta
                WHERE DATE(v.fecha) = :fecha
                  AND v.estado = 'Confirmada'
            """),
            {"fecha": fecha}
        ).mappings().fetchone()

        resumen = {
            "total_ventas":      float(ventas_row.get("total_ventas",      0) or 0),
            "total_efectivo":    float(ventas_row.get("total_efectivo",    0) or 0),
            "total_tarjeta":     float(ventas_row.get("total_tarjeta",     0) or 0),
            "num_ventas":        int(ventas_row.get("num_ventas",          0) or 0),
            "total_punto_venta": float(ventas_row.get("total_punto_venta", 0) or 0),
            "total_en_linea":    float(ventas_row.get("total_en_linea",    0) or 0),
            "total_egresos":     0.0,
        }

        # Egresos del día
        egresos = db.session.execute(
            text("SELECT COALESCE(SUM(monto), 0) FROM cajaMovimientos WHERE DATE(fecha) = :f AND tipo = 'EGRESO'"),
            {"f": fecha}
        ).scalar()
        resumen["total_egresos"] = float(egresos or 0)

    except Exception:
        resumen = {
            "total_ventas": 0.0, "total_efectivo": 0.0, "total_tarjeta": 0.0,
            "num_ventas": 0, "total_punto_venta": 0.0, "total_en_linea": 0.0,
            "total_egresos": 0.0,
        }

    # Movimientos detallados (todas las ventas confirmadas del día)
    movimientos = db.session.execute(
        text("""
            SELECT
                v.idVenta        AS idMovimiento,
                v.fecha,
                'Ingreso'        AS tipo,
                u.nombre         AS nombre_usuario,
                v.metodoPago,
                v.tipo           AS tipoVenta,
                v.nombreCliente,
                COALESCE(SUM(dv.cantidad * dv.precio), 0) AS monto,
                CONCAT(
                    '[', v.tipo, '] Venta #', v.idVenta,
                    ' — ', v.nombreCliente,
                    ' (', v.metodoPago, ')'
                ) AS descripcion
            FROM ventas v
            JOIN usuarios u ON u.idUsuario = v.idUsuario
            JOIN detalleVenta dv ON dv.idVenta = v.idVenta
            WHERE v.estado = 'Confirmada'
              AND DATE(v.fecha) = :fecha
            GROUP BY v.idVenta, v.fecha, u.nombre, v.metodoPago, v.tipo, v.nombreCliente
            ORDER BY v.fecha DESC
        """),
        {"fecha": fecha}
    ).mappings().all()

    return resumen, [dict(m) for m in movimientos]


def _alertas_stock():
    try:
        rows = db.session.execute(
            text("""
                SELECT
                    mp.idMateriaP,
                    mp.nombre,
                    mp.stock,
                    mp.stockMinimo,
                    cat.nombre AS categoria
                FROM materiasPrimas mp
                JOIN categorias cat ON cat.idCategoria = mp.idCategoria
                WHERE mp.estatus = 1
                  AND mp.stock <= mp.stockMinimo
                ORDER BY (mp.stock - mp.stockMinimo) ASC
            """)
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _utilidades_por_tipo(fecha_ini: str, fecha_fin: str):
    """
    Desglose de ingresos separando punto de venta vs en línea.
    """
    try:
        rows = db.session.execute(
            text("""
                SELECT
                    v.tipo                                                    AS tipo_venta,
                    v.metodoPago,
                    COUNT(DISTINCT v.idVenta)                                AS num_ventas,
                    COALESCE(SUM(dv.cantidad * dv.precio), 0)               AS total_ingresos,
                    COALESCE(SUM(dv.cantidad), 0)                           AS total_unidades
                FROM ventas v
                JOIN detalleVenta dv ON dv.idVenta = v.idVenta
                WHERE v.estado = 'Confirmada'
                  AND DATE(v.fecha) BETWEEN :fi AND :ff
                GROUP BY v.tipo, v.metodoPago
                ORDER BY total_ingresos DESC
            """),
            {"fi": fecha_ini, "ff": fecha_fin}
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _productos_con_receta():
    """
    Productos activos que tienen receta registrada con al menos 1 ingrediente.
    """
    try:
        rows = db.session.execute(
            text("""
                SELECT
                    p.idProducto,
                    p.nombre,
                    p.`tamaño`  AS tamano,
                    p.precio,
                    p.stock,
                    CONCAT(p.nombre, ' — ', p.`tamaño`) AS label
                FROM productos p
                WHERE p.estatus = 1
                  AND EXISTS (
                      SELECT 1 FROM recetas r
                      JOIN detalleReceta dr ON dr.idReceta = r.idReceta
                      WHERE r.idProducto = p.idProducto
                  )
                ORDER BY p.nombre, p.`tamaño`
            """)
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── API: Detalle de producto para análisis asíncrono ──────────────────

@caja.route("/caja/api/producto/<int:id_producto>")
@rol_requerido("Administrador", "Ventas")
def api_detalle_producto(id_producto):
    fecha_ini = request.args.get("fecha_ini", (date.today() - timedelta(days=30)).isoformat())
    fecha_fin = request.args.get("fecha_fin", date.today().isoformat())

    try:
        # Info base del producto
        prod = db.session.execute(
            text("""
                SELECT p.idProducto, p.nombre, p.`tamaño` AS tamano,
                       p.precio, p.stock, p.estatus
                FROM productos p WHERE p.idProducto = :id
            """),
            {"id": id_producto}
        ).mappings().fetchone()

        if not prod:
            return jsonify({"error": "Producto no encontrado"}), 404

        # Receta con ingredientes
        receta = db.session.execute(
            text("""
                SELECT r.idReceta, r.descripcion,
                       mp.nombre AS materia_prima,
                       dr.cantidad,
                       cat.nombre AS categoria,
                       mp.stock AS stock_mp,
                       mp.stockMinimo,
                       COALESCE((
                           SELECT SUM(dc.precio) / NULLIF(SUM(dc.cantidad), 0)
                           FROM detalleCompra dc
                           JOIN compras c ON c.idCompra = dc.idCompra
                           WHERE dc.idMateriaP = mp.idMateriaP
                             AND c.estatus = 'Completado'
                             AND DATE(c.fecha) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                       ), 0) AS costo_unit_mp
                FROM recetas r
                JOIN detalleReceta dr ON dr.idReceta = r.idReceta
                JOIN materiasPrimas mp ON mp.idMateriaP = dr.idMateriaP
                JOIN categorias cat ON cat.idCategoria = mp.idCategoria
                WHERE r.idProducto = :id
                ORDER BY mp.nombre
            """),
            {"id": id_producto}
        ).mappings().all()

        # Ventas del producto en el período (todas las fuentes)
        ventas_periodo = db.session.execute(
            text("""
                SELECT
                    DATE(v.fecha)                           AS dia,
                    v.tipo                                  AS tipo_venta,
                    v.metodoPago,
                    COUNT(DISTINCT v.idVenta)               AS num_ventas,
                    COALESCE(SUM(dv.cantidad), 0)           AS unidades,
                    COALESCE(SUM(dv.cantidad * dv.precio), 0) AS ingresos
                FROM detalleVenta dv
                JOIN ventas v ON v.idVenta = dv.idVenta
                WHERE dv.idProducto = :id
                  AND v.estado = 'Confirmada'
                  AND DATE(v.fecha) BETWEEN :fi AND :ff
                GROUP BY DATE(v.fecha), v.tipo, v.metodoPago
                ORDER BY dia ASC
            """),
            {"id": id_producto, "fi": fecha_ini, "ff": fecha_fin}
        ).mappings().all()

        # KPIs del producto
        kpis = db.session.execute(
            text("""
                SELECT
                    COALESCE(SUM(dv.cantidad), 0)               AS total_unidades,
                    COALESCE(SUM(dv.cantidad * dv.precio), 0)   AS total_ingresos,
                    COUNT(DISTINCT v.idVenta)                    AS num_transacciones,
                    COALESCE(SUM(CASE WHEN v.tipo = 'Punto venta' THEN dv.cantidad ELSE 0 END), 0) AS unidades_pv,
                    COALESCE(SUM(CASE WHEN v.tipo = 'En linea'    THEN dv.cantidad ELSE 0 END), 0) AS unidades_ol,
                    COALESCE(SUM(CASE WHEN v.tipo = 'Punto venta' THEN dv.cantidad * dv.precio ELSE 0 END), 0) AS ingresos_pv,
                    COALESCE(SUM(CASE WHEN v.tipo = 'En linea'    THEN dv.cantidad * dv.precio ELSE 0 END), 0) AS ingresos_ol
                FROM detalleVenta dv
                JOIN ventas v ON v.idVenta = dv.idVenta
                WHERE dv.idProducto = :id
                  AND v.estado = 'Confirmada'
                  AND DATE(v.fecha) BETWEEN :fi AND :ff
            """),
            {"id": id_producto, "fi": fecha_ini, "ff": fecha_fin}
        ).mappings().fetchone()

        # Órdenes de producción relacionadas
        ordenes = db.session.execute(
            text("""
                SELECT
                    op.idOrden,
                    op.estado,
                    DATE(op.fecha)      AS fecha,
                    dp.cantidad,
                    op.origen,
                    u.nombre            AS usuario
                FROM detalleProduccion dp
                JOIN ordenesProduccion op ON op.idOrden = dp.idOrden
                JOIN usuarios u ON u.idUsuario = op.idUsuario
                WHERE dp.idProducto = :id
                  AND DATE(op.fecha) BETWEEN :fi AND :ff
                ORDER BY op.fecha DESC
                LIMIT 50
            """),
            {"id": id_producto, "fi": fecha_ini, "ff": fecha_fin}
        ).mappings().all()

        # Costo total estimado de la receta
        costo_receta = sum(
            float(r.get("cantidad", 0) or 0) * float(r.get("costo_unit_mp", 0) or 0)
            for r in receta
        )
        precio_venta = float(prod.get("precio", 0) or 0)
        margen = ((precio_venta - costo_receta) / precio_venta * 100) if precio_venta > 0 else 0

        return jsonify({
            "producto": dict(prod),
            "receta": [dict(r) for r in receta],
            "ventas_periodo": [
                {**dict(r), "dia": str(r["dia"]) if r["dia"] else None}
                for r in ventas_periodo
            ],
            "kpis": dict(kpis) if kpis else {},
            "ordenes": [
                {**dict(o), "fecha": str(o["fecha"]) if o["fecha"] else None}
                for o in ordenes
            ],
            "costo_receta": round(costo_receta, 4),
            "margen_pct": round(margen, 2),
            "fecha_ini": fecha_ini,
            "fecha_fin": fecha_fin,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Vista Corte de Caja ────────────────────────────────────────────────

@caja.route("/caja/corte")
@rol_requerido("Administrador", "Ventas")
def corte_caja():
    fecha_hoy = date.today().isoformat()
    resumen, movimientos = _resumen_dia(fecha_hoy)

    cortes = db.session.execute(
        text("""
            SELECT cc.*, u.nombre AS nombre_usuario
            FROM corteCaja cc
            JOIN usuarios u ON u.idUsuario = cc.idUsuario
            ORDER BY cc.fecha DESC, cc.fechaCreacion DESC
            LIMIT 30
        """)
    ).mappings().all()

    ultimo_corte = db.session.execute(
        text("SELECT fechaCreacion FROM corteCaja ORDER BY fechaCreacion DESC LIMIT 1")
    ).fetchone()

    if ultimo_corte:
        ventas_nuevas = db.session.execute(
            text("""
                SELECT COUNT(*) FROM ventas
                WHERE estado = 'Confirmada'
                  AND fecha > :fecha_corte
            """),
            {"fecha_corte": ultimo_corte[0]}
        ).scalar()
        corte_bloqueado = (ventas_nuevas == 0)
    else:
        corte_bloqueado = False

    return render_template(
        "caja/corte_caja.html",
        fecha_hoy=fecha_hoy,
        resumen=resumen,
        movimientos=movimientos,
        cortes=cortes,
        corte_bloqueado=corte_bloqueado,
    )


@caja.route("/caja/corte/registrar", methods=["POST"])
@rol_requerido("Administrador", "Ventas")
def registrar_corte():
    try:
        ultimo_corte = db.session.execute(
            text("SELECT fechaCreacion FROM corteCaja ORDER BY fechaCreacion DESC LIMIT 1")
        ).fetchone()

        if ultimo_corte:
            ventas_nuevas = db.session.execute(
                text("""
                    SELECT COUNT(*) FROM ventas
                    WHERE estado = 'Confirmada'
                      AND fecha > :fecha_corte
                """),
                {"fecha_corte": ultimo_corte[0]}
            ).scalar()

            if ventas_nuevas == 0:
                flash("No se puede registrar un nuevo corte: no hay ventas nuevas desde el último corte.", "danger")
                return redirect(url_for("caja.corte_caja"))

        fecha            = request.form.get("fecha", date.today().isoformat())
        turno            = request.form.get("turno", "General")
        efectivo_inicial = float(request.form.get("efectivo_inicial", 0) or 0)
        saldo_contado    = float(request.form.get("saldo_contado", 0) or 0)
        observaciones    = request.form.get("observaciones", "").strip() or None

        existente = db.session.execute(
            text("SELECT idCorte FROM corteCaja WHERE fecha = :f AND turno = :t"),
            {"f": fecha, "t": turno},
        ).fetchone()

        if existente:
            flash(f'Ya existe un corte de caja para el turno "{turno}" del día {fecha}.', "danger")
            return redirect(url_for("caja.corte_caja"))

        resumen, _ = _resumen_dia(fecha)

        total_ventas   = resumen["total_ventas"]
        total_efectivo = resumen["total_efectivo"]
        total_tarjeta  = resumen["total_tarjeta"]

        saldo_esperado = efectivo_inicial + total_efectivo
        diferencia     = saldo_contado - saldo_esperado

        db.session.execute(
            text("""
                INSERT INTO corteCaja (
                    idUsuario, fecha, turno,
                    efectivoInicial, totalVentas, totalEfectivo, totalTarjeta,
                    totalEgresos, saldoFinal, saldoContado, diferencia,
                    observaciones, estado, fechaCreacion, fechaCierre
                ) VALUES (
                    :uid, :fecha, :turno,
                    :efe_ini, :tot_v, :tot_ef, :tot_tj,
                    0, :saldo_esp, :saldo_cont, :dif,
                    :obs, 'Cerrado', NOW(), NOW()
                )
            """),
            {
                "uid":        session["usuario_id"],
                "fecha":      fecha,
                "turno":      turno,
                "efe_ini":    Decimal(str(efectivo_inicial)),
                "tot_v":      Decimal(str(total_ventas)),
                "tot_ef":     Decimal(str(total_efectivo)),
                "tot_tj":     Decimal(str(total_tarjeta)),
                "saldo_esp":  Decimal(str(saldo_esperado)),
                "saldo_cont": Decimal(str(saldo_contado)),
                "dif":        Decimal(str(diferencia)),
                "obs":        observaciones,
            },
        )

        id_corte = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        db.session.execute(
            text("""
                INSERT INTO cajaMovimientos (idUsuario, tipo, monto, descripcion, fecha)
                VALUES (:uid, 'CORTE', :monto, :desc, NOW())
            """),
            {
                "uid":   session["usuario_id"],
                "monto": Decimal(str(total_ventas)),
                "desc":  f"Corte de caja #{id_corte} | Turno: {turno} | Diferencia: {diferencia:.2f}",
            },
        )

        usuario_nombre = db.session.execute(
            text("SELECT nombre FROM usuarios WHERE idUsuario = :uid"),
            {"uid": session["usuario_id"]},
        ).scalar()

        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                VALUES (:uid, :nombre, 'CorteCaja', 'CREAR',
                        'corte', :ref, NOW(), :ip)
            """),
            {
                "uid":    session["usuario_id"],
                "nombre": usuario_nombre,
                "ref":    f"ID:{id_corte} | Fecha:{fecha} | Turno:{turno}",
                "ip":     request.remote_addr,
            },
        )

        db.session.commit()
        flash(
            f"Corte de caja registrado correctamente. "
            f"{'Sobrante' if diferencia > 0 else 'Faltante' if diferencia < 0 else 'Cuadrado'}: "
            f"${abs(diferencia):.2f}",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("caja.corte_caja"))


# ── Vista Utilidades / Reportes ────────────────────────────────────────

@caja.route("/caja/utilidades")
@rol_requerido("Administrador", "Ventas")
def utilidades():
    fecha_fin_d = date.today()
    fecha_ini_d = fecha_fin_d - timedelta(days=30)

    fecha_ini = request.args.get("fecha_ini", fecha_ini_d.isoformat())
    fecha_fin = request.args.get("fecha_fin", fecha_fin_d.isoformat())

    filtros = {"fecha_ini": fecha_ini, "fecha_fin": fecha_fin}

    try:
        # Utilidad neta global
        rs = _raw_call("CALL sp_reporte_utilidad_neta(%s, %s)", (fecha_ini, fecha_fin))
        utilidad_neta = rs[0][0] if rs and rs[0] else {}

        # Utilidad por producto
        rs = _raw_call("CALL sp_utilidades_resumen(%s, %s)", (fecha_ini, fecha_fin))
        utilidad_productos = rs[2] if len(rs) > 2 else (rs[-1] if rs else [])

        # Más vendidos
        rs = _raw_call(
            "CALL sp_reporte_productos_vendidos(%s, %s, %s, %s)",
            (fecha_ini, fecha_fin, 10, "DESC"),
        )
        mas_vendidos = rs[0] if rs else []

        # Menos vendidos
        rs = _raw_call(
            "CALL sp_reporte_productos_vendidos(%s, %s, %s, %s)",
            (fecha_ini, fecha_fin, 10, "ASC"),
        )
        menos_vendidos = rs[0] if rs else []

        # Ventas por día (tendencia)
        rs = _raw_call("CALL sp_reporte_ventas_por_dia(%s, %s)", (fecha_ini, fecha_fin))
        ventas_por_dia = rs[0] if rs else []

        # Método de pago — AHORA incluye todos los tipos de venta
        rs = _raw_call("CALL sp_reporte_metodo_pago(%s, %s)", (fecha_ini, fecha_fin))
        metodo_pago = rs[0] if rs else []

        # Costos de materias primas
        rs = _raw_call("CALL sp_reporte_costos_materias_primas(%s, %s)", (fecha_ini, fecha_fin))
        costos_mp = rs[0] if rs else []

        # Mermas del período
        rs = _raw_call("CALL sp_reporte_mermas_periodo(%s, %s)", (fecha_ini, fecha_fin))
        mermas_periodo = rs[0] if rs else []

        # Desglose por tipo de venta (Punto venta vs En línea)
        ventas_por_tipo = _utilidades_por_tipo(fecha_ini, fecha_fin)

        # Alertas de stock bajo
        alertas_stock = _alertas_stock()

        # Productos disponibles para análisis individual
        productos_lista = _productos_con_receta()

    except Exception as e:
        flash(str(e), "danger")
        utilidad_neta      = {}
        utilidad_productos = []
        mas_vendidos       = []
        menos_vendidos     = []
        ventas_por_dia     = []
        metodo_pago        = []
        costos_mp          = []
        mermas_periodo     = []
        ventas_por_tipo    = []
        alertas_stock      = []
        productos_lista    = []

    return render_template(
        "caja/utilidades.html",
        filtros=filtros,
        utilidad_neta=utilidad_neta,
        utilidad_productos=utilidad_productos,
        mas_vendidos=mas_vendidos,
        menos_vendidos=menos_vendidos,
        ventas_por_dia=ventas_por_dia,
        metodo_pago=metodo_pago,
        costos_mp=costos_mp,
        mermas_periodo=mermas_periodo,
        ventas_por_tipo=ventas_por_tipo,
        alertas_stock=alertas_stock,
        productos_lista=productos_lista,
    )