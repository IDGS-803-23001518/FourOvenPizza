import io
from datetime import date, timedelta
from decimal import Decimal

from flask import (
    Blueprint, flash, redirect, render_template,
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
    sp_corte_caja_resumen devuelve 2 result sets:
      RS1 -> totales de ventas del dia
      RS2 -> movimientos informativos
    """
    rs = _raw_call("CALL sp_corte_caja_resumen(%s)", (fecha or None,))

    ventas_row  = rs[0][0] if len(rs) > 0 and rs[0] else {}
    movimientos = rs[1]    if len(rs) > 1 else []

    resumen = {
        "total_ventas":   float(ventas_row.get("total_ventas",   0) or 0),
        "total_efectivo": float(ventas_row.get("total_efectivo", 0) or 0),
        "total_tarjeta":  float(ventas_row.get("total_tarjeta",  0) or 0),
        "num_ventas":     int(ventas_row.get("num_ventas",       0) or 0),
    }
    return resumen, movimientos


def _alertas_stock():
    """
    Retorna insumos cuyo stock actual esta por debajo del stock minimo.
    """
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

    return render_template(
        "caja/corte_caja.html",
        fecha_hoy=fecha_hoy,
        resumen=resumen,
        movimientos=movimientos,
        cortes=cortes,
    )


@caja.route("/caja/corte/registrar", methods=["POST"])
@rol_requerido("Administrador", "Ventas")
def registrar_corte():
    try:
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
            flash(f'Ya existe un corte de caja para el turno "{turno}" del dia {fecha}.', "danger")
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

        # Utilidad por producto (RS2 del sp_utilidades_resumen)
        rs = _raw_call("CALL sp_utilidades_resumen(%s, %s)", (fecha_ini, fecha_fin))
        utilidad_productos = rs[2] if len(rs) > 2 else (rs[-1] if rs else [])

        # Mas vendidos
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

        # Ventas por dia (tendencia)
        rs = _raw_call("CALL sp_reporte_ventas_por_dia(%s, %s)", (fecha_ini, fecha_fin))
        ventas_por_dia = rs[0] if rs else []

        # Metodo de pago
        rs = _raw_call("CALL sp_reporte_metodo_pago(%s, %s)", (fecha_ini, fecha_fin))
        metodo_pago = rs[0] if rs else []

        # Costos de materias primas
        rs = _raw_call("CALL sp_reporte_costos_materias_primas(%s, %s)", (fecha_ini, fecha_fin))
        costos_mp = rs[0] if rs else []

        # Mermas del periodo
        rs = _raw_call("CALL sp_reporte_mermas_periodo(%s, %s)", (fecha_ini, fecha_fin))
        mermas_periodo = rs[0] if rs else []

        # Alertas de stock bajo (consulta directa, sin filtro de fechas)
        alertas_stock = _alertas_stock()

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
        alertas_stock      = []

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
        alertas_stock=alertas_stock,
    )