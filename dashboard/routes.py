"""
dashboard/routes.py

Blueprint del dashboard principal de FourOvenPizza.
Se muestra al Administrador inmediatamente despues del login.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, session
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import db

dashboard = Blueprint("dashboard", __name__)


# ── Helpers ────────────────────────────────────────────────────────────

def _q(sql, params=None):
    """Ejecuta una query y devuelve lista de dicts."""
    result = db.session.execute(text(sql), params or {})
    cols = result.keys()
    return [dict(zip(cols, row)) for row in result.fetchall()]


def _q1(sql, params=None):
    """Devuelve solo la primera fila como dict (o {})."""
    rows = _q(sql, params)
    return rows[0] if rows else {}


def _alertas_stock():
    return _q("""
        SELECT mp.idMateriaP, mp.nombre, mp.stock, mp.stockMinimo,
               cat.nombre AS categoria
        FROM materiasPrimas mp
        JOIN categorias cat ON cat.idCategoria = mp.idCategoria
        WHERE mp.estatus = 1 AND mp.stock <= mp.stockMinimo
        ORDER BY (mp.stock - mp.stockMinimo) ASC
    """)


# ── Vista principal ─────────────────────────────────────────────────────

@dashboard.route("/")
@dashboard.route("/dashboard")
@rol_requerido("Administrador", "Ventas")
def index():
    hoy      = date.today()
    hoy_str  = hoy.isoformat()
    ini_mes  = hoy.replace(day=1).isoformat()
    ini_7d   = (hoy - timedelta(days=6)).isoformat()

    nombre_usuario = db.session.execute(
        text("SELECT nombre FROM usuarios WHERE idUsuario = :uid"),
        {"uid": session["usuario_id"]}
    ).scalar() or "Administrador"

    # ── Resumen ventas HOY ──────────────────────────────────────────
    resumen_hoy = _q1("""
        SELECT
            COALESCE(SUM(dv.cantidad * dv.precio), 0) AS total_ventas,
            COUNT(DISTINCT v.idVenta)                  AS num_ventas
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE v.estado = 'Confirmada'
          AND v.tipo   = 'Punto venta'
          AND DATE(v.fecha) = :hoy
    """, {"hoy": hoy_str})

    # ── Resumen ventas MES ──────────────────────────────────────────
    resumen_mes = _q1("""
        SELECT
            COALESCE(SUM(dv.cantidad * dv.precio), 0) AS total_ventas,
            COUNT(DISTINCT v.idVenta)                  AS num_ventas,
            COALESCE(SUM(dv.cantidad), 0)              AS total_unidades
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE v.estado = 'Confirmada'
          AND DATE(v.fecha) BETWEEN :ini AND :fin
    """, {"ini": ini_mes, "fin": hoy_str})

    # ── Ventas ultimos 7 dias ───────────────────────────────────────
    ventas_7d = _q("""
        SELECT
            DATE(v.fecha)                                   AS dia,
            COUNT(DISTINCT v.idVenta)                       AS num_ventas,
            COALESCE(SUM(dv.cantidad * dv.precio), 0)       AS total_ingresos
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE v.estado = 'Confirmada'
          AND DATE(v.fecha) BETWEEN :ini AND :fin
        GROUP BY DATE(v.fecha)
        ORDER BY dia ASC
    """, {"ini": ini_7d, "fin": hoy_str})

    # Convertir strings a date para que Jinja pueda usar .strftime
    for row in ventas_7d:
        if isinstance(row["dia"], str):
            row["dia"] = datetime.strptime(row["dia"], "%Y-%m-%d").date()

    # ── Metodo de pago HOY ──────────────────────────────────────────
    pago_hoy = _q("""
        SELECT
            v.metodoPago,
            COUNT(DISTINCT v.idVenta)                  AS num_ventas,
            COALESCE(SUM(dv.cantidad * dv.precio), 0)  AS total_ingresos
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE v.estado = 'Confirmada'
          AND DATE(v.fecha) = :hoy
        GROUP BY v.metodoPago
        ORDER BY total_ingresos DESC
    """, {"hoy": hoy_str})

    # ── Top 5 productos del mes ─────────────────────────────────────
    top_productos = _q("""
        SELECT
            p.nombre                                        AS nombre_producto,
            p.`tamaño`                                      AS tamano,
            COALESCE(SUM(dv.cantidad), 0)                   AS unidades_vendidas,
            COALESCE(SUM(dv.cantidad * dv.precio), 0)       AS ingresos
        FROM productos p
        JOIN detalleVenta dv ON dv.idProducto = p.idProducto
        JOIN ventas v        ON v.idVenta = dv.idVenta
        WHERE v.estado = 'Confirmada'
          AND DATE(v.fecha) BETWEEN :ini AND :fin
          AND p.estatus = 1
        GROUP BY p.idProducto, p.nombre, p.`tamaño`
        ORDER BY unidades_vendidas DESC
        LIMIT 5
    """, {"ini": ini_mes, "fin": hoy_str})

    # ── Ventas por hora HOY ─────────────────────────────────────────
    ventas_por_hora = _q("""
        SELECT
            HOUR(v.fecha)                                   AS hora,
            COUNT(DISTINCT v.idVenta)                       AS num_ventas,
            COALESCE(SUM(dv.cantidad * dv.precio), 0)       AS total_ingresos
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE v.estado = 'Confirmada'
          AND DATE(v.fecha) = :hoy
        GROUP BY HOUR(v.fecha)
        ORDER BY hora ASC
    """, {"hoy": hoy_str})

    # ── Ordenes de produccion activas y recientes ───────────────────
    ordenes_activas = _q("""
        SELECT idOrden, estado, fecha
        FROM ordenesProduccion
        WHERE estado IN ('Pendiente', 'En proceso')
        ORDER BY fecha DESC
    """)

    ordenes_recientes = _q("""
        SELECT op.idOrden, op.estado, op.fecha,
               u.nombre AS nombre_usuario
        FROM ordenesProduccion op
        JOIN usuarios u ON u.idUsuario = op.idUsuario
        ORDER BY op.fecha DESC
        LIMIT 7
    """)

    # ── Ventas individuales HOY (lista de actividad) ────────────────
    ventas_hoy = _q("""
        SELECT
            v.idVenta,
            v.nombreCliente,
            v.metodoPago,
            v.estado,
            v.fecha,
            COALESCE(SUM(dv.cantidad * dv.precio), 0) AS total
        FROM ventas v
        JOIN detalleVenta dv ON dv.idVenta = v.idVenta
        WHERE DATE(v.fecha) = :hoy
        GROUP BY v.idVenta, v.nombreCliente, v.metodoPago, v.estado, v.fecha
        ORDER BY v.fecha DESC
        LIMIT 15
    """, {"hoy": hoy_str})

    # ── Mermas de HOY ───────────────────────────────────────────────
    mermas_hoy = _q("""
        SELECT
            mp.nombre                                           AS materia_prima,
            dm.cantidad                                         AS cantidad_merma,
            COALESCE((
                SELECT SUM(dc2.precio) / NULLIF(SUM(dc2.cantidad), 0)
                FROM detalleCompra dc2
                JOIN compras c2 ON c2.idCompra = dc2.idCompra
                WHERE dc2.idMateriaP = mp.idMateriaP
                  AND c2.estatus = 'Completado'
                  AND DATE(c2.fecha) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ), 0) * dm.cantidad                                 AS valor_perdida
        FROM mermas m
        JOIN detalleMerma dm  ON dm.idMerma    = m.idMerma
        JOIN materiasPrimas mp ON mp.idMateriaP = dm.idMateriaP
        WHERE m.estatus = 1
          AND DATE(m.fecha) = :hoy
        ORDER BY valor_perdida DESC
    """, {"hoy": hoy_str})

    # ── Compras recientes ───────────────────────────────────────────
    compras_recientes = _q("""
        SELECT
            c.idCompra,
            c.fecha,
            c.estatus,
            p.nombre  AS nombre_proveedor,
            u.nombre  AS nombre_usuario
        FROM compras c
        JOIN proveedores p ON p.idProveedor = c.idProveedor
        JOIN usuarios u    ON u.idUsuario   = c.idUsuario
        ORDER BY c.fecha DESC
        LIMIT 6
    """)

    # ── Cortes de caja recientes ────────────────────────────────────
    cortes_recientes = _q("""
        SELECT cc.fecha, cc.turno, cc.totalVentas, cc.diferencia,
               u.nombre AS nombre_usuario
        FROM corteCaja cc
        JOIN usuarios u ON u.idUsuario = cc.idUsuario
        ORDER BY cc.fecha DESC, cc.fechaCreacion DESC
        LIMIT 5
    """)

    # ── Alertas de stock ────────────────────────────────────────────
    alertas_stock = _alertas_stock()

    # Meta diaria referencial (puede externalizarse a configuracion)
    META_DIARIA = 3000.0

    return render_template(
        "dashboard.html",
        nombre_usuario   = nombre_usuario,
        fecha_hoy        = hoy.strftime("%d de %B de %Y"),
        resumen_hoy      = resumen_hoy,
        resumen_mes      = resumen_mes,
        ventas_7d        = ventas_7d,
        pago_hoy         = pago_hoy,
        top_productos    = top_productos,
        ventas_por_hora  = ventas_por_hora,
        ordenes_activas  = ordenes_activas,
        ordenes_recientes= ordenes_recientes,
        ventas_hoy       = ventas_hoy,
        mermas_hoy       = mermas_hoy,
        compras_recientes= compras_recientes,
        cortes_recientes = cortes_recientes,
        alertas_stock    = alertas_stock,
        meta_diaria      = META_DIARIA,
    )