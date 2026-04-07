from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Mermas, DetalleMerma, MateriasPrimas, Productos, Recetas, DetalleReceta
from mermas import mermas          # el Blueprint ya importado
from sqlalchemy import text
import json


# ── HELPER: productos activos con receta activa ───────────────────────────
def get_productos_con_receta():
    """
    Devuelve los Productos activos que tienen al menos una receta
    con al menos un ingrediente, y cuyos ingredientes existen en materias primas activas.
    """
    productos = (
        Productos.query
        .filter_by(estatus=True)
        .join(Recetas, Recetas.idProducto == Productos.idProducto)
        .join(DetalleReceta, DetalleReceta.idReceta == Recetas.idReceta)
        .join(MateriasPrimas, MateriasPrimas.idMateriaP == DetalleReceta.idMateriaP)
        .filter(MateriasPrimas.estatus == True)
        .distinct()
        .all()
    )
    return productos


# ── LISTAR ───────────────────────────────────────────────────────────────
@mermas.route('/mermas')
def index():
    registros           = Mermas.query.order_by(Mermas.fecha.desc()).all()
    materias            = MateriasPrimas.query.filter_by(estatus=True).all()
    tipos               = db.session.query(MateriasPrimas.tipo).distinct().all()
    tipos               = [t[0] for t in tipos]
    productos_con_receta = get_productos_con_receta()

    return render_template(
        'mermas/mermas.html',
        registros=registros,
        materias=materias,
        tipos=tipos,
        productos_con_receta=productos_con_receta,
    )


# ── CREAR ────────────────────────────────────────────────────────────────
@mermas.route('/crear', methods=['POST'])
def crear():
    descripcion   = request.form.get('descripcion', '').strip()
    insumos_json  = request.form.get('insumos_json', '[]')
    ip            = request.remote_addr
    ejecutado_por = session.get('idUsuario')

    try:
        detalle = json.loads(insumos_json)
    except (json.JSONDecodeError, TypeError):
        flash('Error al procesar los insumos enviados.', 'danger')
        return redirect(url_for('mermas.index'))

    if not descripcion:
        flash('La descripción es obligatoria.', 'danger')
        return redirect(url_for('mermas.index'))

    if not detalle:
        flash('Debe agregar al menos un insumo.', 'danger')
        return redirect(url_for('mermas.index'))

    detalle_json_str = json.dumps(detalle)

    sql = text("""
        CALL sp_gestion_mermas(
            'INSERT', NULL, :descripcion, NULL, :detalle,
            :ip, :ejecutado_por, @p_resultado, @p_idGenerado
        )
    """)
    db.session.execute(sql, {
        'descripcion': descripcion,
        'detalle':     detalle_json_str,
        'ip':          ip,
        'ejecutado_por': ejecutado_por,
    })

    resultado   = db.session.execute(text("SELECT @p_resultado")).scalar()
    db.session.commit()

    if resultado and resultado.startswith('SUCCESS'):
        flash(resultado.replace('SUCCESS: ', ''), 'success')

        # Detectar materias con stock bajo
        ids_afectados = [int(i['idMateriaP']) for i in detalle if 'idMateriaP' in i]
        if ids_afectados:
            bajas = MateriasPrimas.query.filter(
                MateriasPrimas.idMateriaP.in_(ids_afectados),
                MateriasPrimas.estatus == True,
                MateriasPrimas.stock <= MateriasPrimas.stockMinimo,
            ).all()
            if bajas:
                session['stock_alerts'] = [
                    {'nombre': m.nombre, 'stock': float(m.stock), 'minimo': float(m.stockMinimo)}
                    for m in bajas
                ]
    else:
        flash(resultado or 'Error desconocido', 'danger')

    return redirect(url_for('mermas.index'))


# ── ELIMINAR (permanente, devuelve stock) ────────────────────────────────
@mermas.route('/eliminar/<int:id>')
def eliminar(id):
    """
    Elimina la merma de forma permanente y devuelve el stock a cada
    materia prima afectada. No usa stored procedure para máximo control.
    """
    ejecutado_por = session.get('idUsuario')
    ip            = request.remote_addr

    merma = Mermas.query.get_or_404(id)

    try:
        # 1. Devolver stock a cada materia prima
        for detalle in merma.detalle_mermas:
            mp = MateriasPrimas.query.get(detalle.idMateriaP)
            if mp:
                mp.stock = mp.stock + detalle.cantidad

        # 2. Los detalles se eliminan en cascada gracias a cascade='all, delete-orphan'
        db.session.delete(merma)

        # 3. Bitácora
        nombre_ejecutor = 'Sistema'
        if ejecutado_por:
            from models import Usuarios
            u = Usuarios.query.get(ejecutado_por)
            if u:
                nombre_ejecutor = u.nombre

        db.session.execute(
            text("""
                INSERT INTO bitacora_eventos
                    (usuarioId, nombreUsuario, modulo, accion, referencial, referencia, fecha, ip)
                VALUES
                    (:uid, :uname, 'Mermas', 'ELIMINAR', 'merma', :ref, NOW(), :ip)
            """),
            {
                'uid':   ejecutado_por,
                'uname': nombre_ejecutor,
                'ref':   f'ID:{id} | {merma.descripcion}',
                'ip':    ip,
            }
        )

        db.session.commit()
        flash('Merma eliminada permanentemente y stock restaurado correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la merma: {str(e)}', 'danger')

    return redirect(url_for('mermas.index'))