import re
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for, session
from sqlalchemy import extract, func, text

import forms
from autentificacion.routes import rol_requerido
from models import Categorias, MateriasPrimas, Productos, Recetas, DetalleReceta, UnidadesMedida,MiniRecetas, DetalleMiniReceta, db

from . import materiasPrimas

PATRON_NOMBRE_CATALOGO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ]+$")


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


def _guardar_error_formulario(modal, mensaje, datos=None):
    session["materias_form_error"] = {
        "modal": modal,
        "mensaje": mensaje,
        "datos": datos or {},
    }


def _normalizar_nombre_catalogo(valor):
    valor = re.sub(r"\s+", " ", (valor or "").strip())
    valor = re.sub(r"\s+\d+$", "", valor).strip()
    return valor.lower()


def _validar_nombre_catalogo(nombre, etiqueta):
    nombre_limpio = re.sub(r"\s+", " ", (nombre or "").strip())

    if not nombre_limpio:
        raise ValueError(f"{etiqueta} es requerido.")

    if len(nombre_limpio) < 3:
        raise ValueError(f"{etiqueta} debe tener al menos 3 caracteres.")

    if not PATRON_NOMBRE_CATALOGO.fullmatch(nombre_limpio):
        raise ValueError(f"{etiqueta} solo puede contener letras, numeros y espacios.")

    return nombre_limpio


def _parsear_entero_positivo(valor, etiqueta):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{etiqueta} debe ser un numero valido.")

    if numero <= 0:
        raise ValueError(f"{etiqueta} debe ser mayor a 0.")

    if numero != numero.to_integral_value():
        raise ValueError(f"{etiqueta} debe ser un numero entero.")

    return int(numero)


def _parsear_entero_no_negativo(valor, etiqueta):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{etiqueta} debe ser un numero valido.")

    if numero < 0:
        raise ValueError(f"{etiqueta} no puede ser negativo.")

    if numero != numero.to_integral_value():
        raise ValueError(f"{etiqueta} debe ser un numero entero.")

    return int(numero)


def _existe_materia_prima_duplicada(nombre, id_materia_prima=None):
    materias = MateriasPrimas.query.all()
    nombre_normalizado = _normalizar_nombre_catalogo(nombre)

    for materia in materias:
        if id_materia_prima is not None and materia.idMateriaP == id_materia_prima:
            continue
        if _normalizar_nombre_catalogo(materia.nombre) == nombre_normalizado:
            return True

    return False


def _obtener_alertas_stock_materias():
    alertas = []
    registros = db.session.execute(text("CALL sp_obtener_alertas_stock_mp()")).mappings().all()
    for r in registros:
        stock_actual = Decimal(str(r["stock"] or 0))
        stock_minimo = Decimal(str(r["stockMinimo"] or 0))
        unidad = "g" if r["tipo"] == "Solido" else "ml"
        alertas.append(
            {
                "idMateriaP": r["idMateriaP"],
                "nombre": r["nombre"],
                "stock": stock_actual,
                "stock_minimo": stock_minimo,
                "unidad": unidad,
            }
        )
    return alertas


def _desactivar_productos_por_materia_prima(id_materia_prima, ip, usuario_id):
    """
    Desactiva todos los productos cuyas recetas contengan la materia prima dada.
    Retorna la lista de nombres de productos desactivados.
    """
    productos_desactivados = []

    # Buscar todos los detalles de receta que usen esta materia prima
    detalles = DetalleReceta.query.filter_by(idMateriaP=id_materia_prima).all()

    # Obtener las recetas únicas afectadas
    ids_recetas = list({d.idReceta for d in detalles})

    if not ids_recetas:
        return productos_desactivados

    # Obtener los productos vinculados a esas recetas
    recetas = Recetas.query.filter(Recetas.idReceta.in_(ids_recetas)).all()
    ids_productos = list({r.idProducto for r in recetas})

    if not ids_productos:
        return productos_desactivados

    # Desactivar solo los productos que estén activos
    productos_activos = Productos.query.filter(
        Productos.idProducto.in_(ids_productos),
        Productos.estatus == True
    ).all()

    for producto in productos_activos:
        db.session.execute(
            text(
                "CALL sp_gestion_productos("
                ":accion,:idProducto,:nombre,:precio,:tamano,:stock,:estatus,:ip,:usuario,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "UPDATE",
                "idProducto": producto.idProducto,
                "nombre": producto.nombre,
                "precio": producto.precio,
                "tamano": getattr(producto, "tamano", "") or "",
                "stock": producto.stock,
                "estatus": 0,
                "ip": ip,
                "usuario": usuario_id,
            },
        )
        productos_desactivados.append(producto.nombre)

    return productos_desactivados


@materiasPrimas.route("/materiasPrimas", methods=["GET", "POST"])
@rol_requerido("Administrador")
def listadoMaterias():
    create_form = forms.MateriaPrimaForm(request.form)
    lista_materias = MateriasPrimas.query.order_by(MateriasPrimas.nombre.asc()).all()
    categorias = Categorias.query.filter_by(estatus=1).all()
    form_error = session.pop("materias_form_error", None)
    alertas_stock = _obtener_alertas_stock_materias()
    return render_template(
        "materiasPrimas/materiasPrimas.html",
        form=create_form,
        materias=lista_materias,
        categorias=categorias,
        form_error=form_error,
        alertas_stock=alertas_stock,
    )

@materiasPrimas.route("/registrar-materia-prima", methods=["POST"])
@rol_requerido("Administrador")
def registrar_materia_prima():
    datos_formulario = {}
    try:
        nombre = _validar_nombre_catalogo(request.form.get("nombre"), "El nombre de la materia prima")
        tipo = request.form.get("tipo")
        id_categoria = int(request.form.get("idCategoria"))
        stock = _parsear_entero_no_negativo(request.form.get("stock"), "El stock")
        stock_minimo = _parsear_entero_no_negativo(request.form.get("stockMinimo"), "El stock minimo")
        datos_formulario = {
            "nombre": nombre,
            "tipo": tipo,
            "idCategoria": id_categoria,
            "stock": str(stock),
            "stockMinimo": str(stock_minimo),
        }

        if _existe_materia_prima_duplicada(nombre):
            _guardar_error_formulario("registro", "La materia prima ya existe.", datos_formulario)
            return redirect(url_for("materiasPrimas.listadoMaterias"))

        db.session.execute(
            text(
                """
                CALL sp_gestion_materiasprimas(
                    :accion,
                    :idMateriaP,
                    :nombre,
                    :tipo,
                    :idCategoria,
                    :stock,
                    :stockMinimo,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
            """
            ),
            {
                "accion": "INSERT",
                "idMateriaP": None,
                "nombre": nombre,
                "tipo": tipo,
                "idCategoria": id_categoria,
                "stock": stock,
                "stockMinimo": stock_minimo,
                "estatus": 1,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("registro", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        _guardar_error_formulario("registro", str(e), datos_formulario)

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route("/editar-materia-prima/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_materia_prima(id):
    datos_formulario = {"id": id}

    try:
        nombre = _validar_nombre_catalogo(request.form.get("nombre"), "El nombre de la materia prima")
        tipo = request.form.get("tipo")
        id_categoria = int(request.form.get("idCategoria"))
        stock = _parsear_entero_no_negativo(request.form.get("stock"), "El stock")
        stock_minimo = _parsear_entero_no_negativo(request.form.get("stockMinimo"), "El stock minimo")
        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "tipo": tipo,
            "idCategoria": id_categoria,
            "stock": str(stock),
            "stockMinimo": str(stock_minimo),
        }

        if _existe_materia_prima_duplicada(nombre, id):
            _guardar_error_formulario("edicion", "Ya existe otra materia prima con ese nombre.", datos_formulario)
            return redirect(url_for("materiasPrimas.listadoMaterias"))

        db.session.execute(
            text(
                """
                CALL sp_gestion_materiasprimas(
                    :accion,
                    :idMateriaP,
                    :nombre,
                    :tipo,
                    :idCategoria,
                    :stock,
                    :stockMinimo,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
            """
            ),
            {
                "accion": "UPDATE",
                "idMateriaP": id,
                "nombre": nombre,
                "tipo": tipo,
                "idCategoria": id_categoria,
                "stock": stock,
                "stockMinimo": stock_minimo,
                "estatus": None,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )

        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]

        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("edicion", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        _guardar_error_formulario("edicion", str(e), datos_formulario)

    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route("/cambiar-estatus-materia-prima/<int:id>/<int:estatus>")
@rol_requerido("Administrador")
def cambiar_estatus_materia_prima(id, estatus):
    try:
        nuevo_estatus = 0 if estatus == 1 else 1
 
        if nuevo_estatus == 0:
            materia = MateriasPrimas.query.get(id)
            nombre_materia = materia.nombre if materia else str(id)
 
            # Desactivar la materia prima
            db.session.execute(
                text("""
                    CALL sp_gestion_materiasprimas(
                        :accion,:idMateriaP,:nombre,:tipo,:idCategoria,
                        :stock,:stockMinimo,:estatus,:ip,:usuario,
                        @p_resultado,@p_idGenerado
                    )
                """),
                {
                    "accion": "CHANGE_STATUS", "idMateriaP": id,
                    "nombre": None, "tipo": None, "idCategoria": None,
                    "stock": None, "stockMinimo": None,
                    "estatus": nuevo_estatus,
                    "ip": request.remote_addr, "usuario": session["usuario_id"],
                },
            )
            resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
            mensaje, categoria = _texto_resultado(resultado)
 
            if categoria == "success":
                # ── Desactivar mini recetas en cascada ──
                mini_recetas_afectadas_nombres = []
                mini_recetas_afectadas = (
                    MiniRecetas.query
                    .join(DetalleMiniReceta, DetalleMiniReceta.idMiniReceta == MiniRecetas.idMiniReceta)
                    .filter(DetalleMiniReceta.idMateriaP == id, MiniRecetas.estatus == True)
                    .all()
                )
                for mr in mini_recetas_afectadas:
                    mr.estatus = False
                    mini_recetas_afectadas_nombres.append(mr.nombre)
 
                # ── Desactivar productos en cascada ──
                productos_desactivados = _desactivar_productos_por_materia_prima(
                    id, request.remote_addr, session["usuario_id"],
                )
                db.session.commit()
 
                flash(mensaje, "success")
 
                if mini_recetas_afectadas_nombres:
                    nombres_mr = ", ".join(mini_recetas_afectadas_nombres)
                    flash(
                        f"Las siguientes mini recetas fueron desactivadas automáticamente porque "
                        f"contienen «{nombre_materia}»: {nombres_mr}.",
                        "warning",
                    )
 
                if productos_desactivados:
                    nombres_p = ", ".join(productos_desactivados)
                    flash(
                        f"Los siguientes productos fueron desactivados porque su receta contiene "
                        f"«{nombre_materia}»: {nombres_p}.",
                        "danger",
                    )
            else:
                db.session.rollback()
                flash(mensaje, "danger")
 
        else:
            # Activar normalmente (mini recetas NO se reactivan en automático)
            db.session.execute(
                text("""
                    CALL sp_gestion_materiasprimas(
                        :accion,:idMateriaP,:nombre,:tipo,:idCategoria,
                        :stock,:stockMinimo,:estatus,:ip,:usuario,
                        @p_resultado,@p_idGenerado
                    )
                """),
                {
                    "accion": "CHANGE_STATUS", "idMateriaP": id,
                    "nombre": None, "tipo": None, "idCategoria": None,
                    "stock": None, "stockMinimo": None,
                    "estatus": nuevo_estatus,
                    "ip": request.remote_addr, "usuario": session["usuario_id"],
                },
            )
            resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
            db.session.commit()
            mensaje, categoria = _texto_resultado(resultado)
            flash(mensaje, categoria)
 
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
 
    return redirect(url_for("materiasPrimas.listadoMaterias"))


@materiasPrimas.route('/ver-materia-prima/<int:id>')
@rol_requerido('Administrador')
def ver_materia_prima(id):
    mp = MateriasPrimas.query.get_or_404(id)
    return render_template('materiasPrimas/verMateriaPrima.html', mp=mp)


@materiasPrimas.route("/registrar-unidad-medida", methods=["POST"])
@rol_requerido("Administrador")
def registrar_unidad_medida():
    create_form = forms.UnidadMedidaForm(request.form)
    if create_form.validate_on_submit():
        try:
            db.session.execute(
                text("""
                    CALL sp_gestion_unidadesmedida(
                        :accion, :id, :nombre, :tipo, :equivalente,
                        :estatus, :ip, :usuario, @p_resultado, @p_id
                    )
                """),
                {
                    "accion": "INSERT",
                    "id": None,
                    "nombre": create_form.nombre.data,
                    "tipo": create_form.simbolo.data or "",
                    "equivalente": 1,
                    "estatus": 1,
                    "ip": request.remote_addr,
                    "usuario": session["usuario_id"],
                },
            )
            resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
            db.session.commit()
            if resultado and resultado.startswith("SUCCESS"):
                flash("Unidad de medida registrada exitosamente.", "success")
            else:
                mensaje = resultado.split(":", 1)[1].strip() if resultado and ":" in resultado else "Error al registrar unidad"
                flash(mensaje, "danger")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    return redirect(url_for("materiasPrimas.listadoMaterias"))