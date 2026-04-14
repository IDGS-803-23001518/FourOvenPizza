import json
import re
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import text

from autentificacion.routes import rol_requerido
from models import DetalleMiniReceta, MateriasPrimas, MiniRecetas, Usuarios, db

from miniRecetas import miniRecetas

PATRON_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ]+$")
MINIMO_INSUMOS = 1


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _validar_nombre(nombre, etiqueta="El nombre"):
    nombre_limpio = re.sub(r"\s+", " ", (nombre or "").strip())
    if not nombre_limpio:
        raise ValueError(f"{etiqueta} es obligatorio.")
    if len(nombre_limpio) < 3:
        raise ValueError(f"{etiqueta} debe tener al menos 3 caracteres.")
    if not PATRON_NOMBRE.fullmatch(nombre_limpio):
        raise ValueError(f"{etiqueta} solo puede contener letras, números y espacios.")
    return nombre_limpio


def _parsear_cantidad(valor):
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("La cantidad ingresada no es válida.")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    return cantidad


def _ingredientes_desactivados(mini_receta):
    return [
        d.materia_prima.nombre
        for d in mini_receta.detalles
        if d.materia_prima and not d.materia_prima.estatus
    ]


def _obtener_mini_recetas():
    return MiniRecetas.query.order_by(MiniRecetas.nombre.asc()).all()


def _materias_activas():
    return MateriasPrimas.query.filter_by(estatus=1).order_by(MateriasPrimas.nombre.asc()).all()


# ── Rutas ──────────────────────────────────────────────────────────────────────

@miniRecetas.route("/mini-recetas")
@rol_requerido("Administrador", "Cocinero")
def listado():
    mini_recetas = _obtener_mini_recetas()
    materias = _materias_activas()
    form_error = session.pop("mr_form_error", None)

    # 🔥 Convertir materias a JSON serializable
    materias_json = [
        {
            "idMateriaP": m.idMateriaP,
            "nombre": m.nombre,
            "tipo": m.tipo
        }
        for m in materias
    ]

    datos = []
    for mr in mini_recetas:
        desactivados = _ingredientes_desactivados(mr)
        detalles_ord = sorted(
            mr.detalles,
            key=lambda d: (d.materia_prima.nombre if d.materia_prima else "")
        )

        # ✅ Listas normales (SIN json.dumps)
        ids_mp = [d.idMateriaP for d in detalles_ord]
        cantidades = [int(d.cantidad) for d in detalles_ord]

        datos.append({
            "obj": mr,
            "detalles": detalles_ord,
            "ingredientes_desactivados": desactivados,
            "edit_ids": ids_mp,
            "edit_cantidades": cantidades,
        })

    return render_template(
        "miniRecetas/miniRecetas.html",
        datos=datos,
        materias=materias_json,
        form_error=form_error,
    )


@miniRecetas.route("/mini-recetas/registrar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def registrar():
    try:
        nombre      = _validar_nombre(request.form.get("nombre"), "El nombre de la mini receta")
        ids_mp      = request.form.getlist("idMateriaP[]")
        cantidades  = request.form.getlist("cantidad[]")

        if not ids_mp:
            flash("Debe agregar al menos un insumo.", "danger")
            return redirect(url_for("miniRecetas.listado"))

        detalles = []
        vistos = set()
        for id_mp, cant in zip(ids_mp, cantidades):
            id_mp = int(id_mp)
            if id_mp in vistos:
                flash(f"La materia prima ID {id_mp} está duplicada.", "danger")
                return redirect(url_for("miniRecetas.listado"))
            vistos.add(id_mp)
            cantidad = _parsear_cantidad(cant)
            detalles.append({"idMateriaP": id_mp, "cantidad": float(cantidad)})

        detalles_json = json.dumps(detalles)

        db.session.execute(
            text(
                "CALL sp_gestion_mini_recetas("
                ":accion,:idMR,:nombre,:descripcion,:estatus,:ip,:usuario,:detalles,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "INSERT", "idMR": None,
                "nombre": nombre, "descripcion": None,
                "estatus": 1, "ip": request.remote_addr,
                "usuario": session["usuario_id"],
                "detalles": detalles_json,
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("miniRecetas.listado"))


@miniRecetas.route("/mini-recetas/<int:id>/editar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def editar(id):
    try:
        nombre     = _validar_nombre(request.form.get("nombre"), "El nombre de la mini receta")
        ids_mp     = request.form.getlist("idMateriaP[]")
        cantidades = request.form.getlist("cantidad[]")

        if not ids_mp:
            flash("Debe agregar al menos un insumo.", "danger")
            return redirect(url_for("miniRecetas.listado"))

        detalles = []
        vistos = set()
        for id_mp, cant in zip(ids_mp, cantidades):
            id_mp = int(id_mp)
            if id_mp in vistos:
                flash(f"La materia prima ID {id_mp} está duplicada.", "danger")
                return redirect(url_for("miniRecetas.listado"))
            vistos.add(id_mp)
            cantidad = _parsear_cantidad(cant)
            detalles.append({"idMateriaP": id_mp, "cantidad": float(cantidad)})

        detalles_json = json.dumps(detalles)

        db.session.execute(
            text(
                "CALL sp_gestion_mini_recetas("
                ":accion,:idMR,:nombre,:descripcion,:estatus,:ip,:usuario,:detalles,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "UPDATE", "idMR": id,
                "nombre": nombre, "descripcion": None,
                "estatus": None, "ip": request.remote_addr,
                "usuario": session["usuario_id"],
                "detalles": detalles_json,
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("miniRecetas.listado"))


@miniRecetas.route("/mini-recetas/<int:id>/estatus/<int:estatus>")
@rol_requerido("Administrador", "Cocinero")
def cambiar_estatus(id, estatus):
    try:
        nuevo = 0 if estatus == 1 else 1

        db.session.execute(
            text(
                "CALL sp_gestion_mini_recetas("
                ":accion,:idMR,:nombre,:descripcion,:estatus,:ip,:usuario,:detalles,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "CHANGE_STATUS", "idMR": id,
                "nombre": None, "descripcion": None,
                "estatus": nuevo, "ip": request.remote_addr,
                "usuario": session["usuario_id"],
                "detalles": None,
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("miniRecetas.listado"))


@miniRecetas.route("/mini-recetas/<int:id>/eliminar", methods=["POST"])
@rol_requerido("Administrador", "Cocinero")
def eliminar(id):
    try:
        # Eliminar detalles primero (el SP en MySQL no activa el cascade de SQLAlchemy)
        db.session.execute(
            text("DELETE FROM detalleMiniReceta WHERE idMiniReceta = :id"),
            {"id": id}
        )

        db.session.execute(
            text(
                "CALL sp_gestion_mini_recetas("
                ":accion,:idMR,:nombre,:descripcion,:estatus,:ip,:usuario,:detalles,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "DELETE", "idMR": id,
                "nombre": None, "descripcion": None,
                "estatus": None, "ip": request.remote_addr,
                "usuario": session["usuario_id"],
                "detalles": None,
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("miniRecetas.listado"))


@miniRecetas.route("/mini-recetas/<int:id>/detalles-json")
@rol_requerido("Administrador", "Cocinero")
def detalles_json(id):
    from flask import jsonify
    mr = MiniRecetas.query.get_or_404(id)
    data = [
        {
            "idMateriaP": d.idMateriaP,
            "nombre": d.materia_prima.nombre if d.materia_prima else str(d.idMateriaP),
            "tipo": d.materia_prima.tipo if d.materia_prima else "",
            "cantidad": float(d.cantidad),
            "activa": bool(d.materia_prima.estatus) if d.materia_prima else False,
        }
        for d in mr.detalles
    ]
    return jsonify({"ok": True, "nombre": mr.nombre, "detalles": data})