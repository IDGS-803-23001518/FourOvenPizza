from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Mermas, MateriasPrimas
from mermas import mermas
from sqlalchemy import text


# ── LISTAR ───────────────────────────────────────────────────
@mermas.route('/mermas')
def index():
    registros = Mermas.query.order_by(Mermas.fecha.desc()).all()
    materias  = MateriasPrimas.query.filter_by(estatus=True).all()
    tipos     = db.session.query(MateriasPrimas.tipo).distinct().all()
    tipos     = [t[0] for t in tipos]

    return render_template(
        'mermas/mermas.html',
        registros=registros,
        materias=materias,
        tipos=tipos
    )


# ── CREAR ────────────────────────────────────────────────────
@mermas.route('/crear', methods=['POST'])
def crear():
    import json
    from flask import session

    descripcion    = request.form.get('descripcion')
    materias_ids   = request.form.getlist('materia[]')
    cantidades     = request.form.getlist('cantidad[]')
    ip             = request.remote_addr
    ejecutado_por  = session.get('idUsuario')

    detalle = []
    for id_mp, cant in zip(materias_ids, cantidades):
        if id_mp and cant:
            detalle.append({"idMateriaP": int(id_mp), "cantidad": float(cant)})

    detalle_json = json.dumps(detalle)

    sql = text("""
        CALL sp_gestion_mermas(
            'INSERT', NULL, :descripcion, NULL, :detalle,
            :ip, :ejecutado_por, @p_resultado, @p_idGenerado
        )
    """)
    db.session.execute(sql, {
        'descripcion': descripcion, 'detalle': detalle_json,
        'ip': ip, 'ejecutado_por': ejecutado_por
    })

    resultado   = db.session.execute(text("SELECT @p_resultado")).scalar()
    id_generado = db.session.execute(text("SELECT @p_idGenerado")).scalar()
    db.session.commit()

    if resultado and resultado.startswith('SUCCESS'):
        flash(resultado.replace('SUCCESS: ', ''), 'success')

        # ── NUEVO: detectar materias con stock bajo ──────────────
        ids_afectados = [int(i) for i in materias_ids if i]
        if ids_afectados:
            bajas = MateriasPrimas.query.filter(
                MateriasPrimas.idMateriaP.in_(ids_afectados),
                MateriasPrimas.estatus == True,
                MateriasPrimas.stock <= MateriasPrimas.stockMinimo
            ).all()
            if bajas:
                alertas = [
                    {"nombre": m.nombre, "stock": float(m.stock), "minimo": float(m.stockMinimo)}
                    for m in bajas
                ]
                session['stock_alerts'] = alertas   # guardamos en sesión para mostrar
        # ─────────────────────────────────────────────────────────

    else:
        flash(resultado or 'Error desconocido', 'danger')

    return redirect(url_for('mermas.index'))


# ── ACTIVAR ──────────────────────────────────────────────────
@mermas.route('/activar/<int:id>')
def activar(id):
    from flask import session

    ip            = request.remote_addr
    ejecutado_por = session.get('idUsuario')

    sql = text("""
        CALL sp_gestion_mermas(
            'CHANGE_STATUS',
            :id_merma,
            NULL,
            1,
            NULL,
            :ip,
            :ejecutado_por,
            @p_resultado,
            @p_idGenerado
        )
    """)

    db.session.execute(sql, {
        'id_merma':      id,
        'ip':            ip,
        'ejecutado_por': ejecutado_por
    })

    resultado = db.session.execute(text("SELECT @p_resultado")).scalar()
    db.session.commit()

    if resultado and resultado.startswith('SUCCESS'):
        flash(resultado.replace('SUCCESS: ', ''), 'success')
    else:
        flash(resultado or 'Error desconocido', 'danger')

    return redirect(url_for('mermas.index'))


# ── DESACTIVAR ───────────────────────────────────────────────
@mermas.route('/desactivar/<int:id>')
def desactivar(id):
    from flask import session

    ip            = request.remote_addr
    ejecutado_por = session.get('idUsuario')

    sql = text("""
        CALL sp_gestion_mermas(
            'CHANGE_STATUS',
            :id_merma,
            NULL,
            0,
            NULL,
            :ip,
            :ejecutado_por,
            @p_resultado,
            @p_idGenerado
        )
    """)

    db.session.execute(sql, {
        'id_merma':      id,
        'ip':            ip,
        'ejecutado_por': ejecutado_por
    })

    resultado = db.session.execute(text("SELECT @p_resultado")).scalar()
    db.session.commit()

    if resultado and resultado.startswith('SUCCESS'):
        flash(resultado.replace('SUCCESS: ', ''), 'warning')
    else:
        flash(resultado or 'Error desconocido', 'danger')

    return redirect(url_for('mermas.index'))