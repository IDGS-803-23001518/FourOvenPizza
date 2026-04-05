import glob
import os
import re
from decimal import Decimal, InvalidOperation
from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.utils import secure_filename
from autentificacion.routes import rol_requerido
from models import BitacoraEventos, DetalleReceta, MateriasPrimas, Productos, Recetas, Usuarios, db
from . import productos


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTOS_IMG_DIR = os.path.join(BASE_DIR, "static", "img", "productos")
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TAMANOS_PRODUCTO = ("Chica", "Mediana", "Grande")
PATRON_NOMBRE_CATALOGO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ]+$")


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _guardar_error_formulario(modal, mensaje, datos=None):
    session["productos_form_error"] = {
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


def _validar_tamano_producto(tamano):
    tamano_limpio = re.sub(r"\s+", " ", (tamano or "").strip()).lower()
    catalogo = {v.lower(): v for v in TAMANOS_PRODUCTO}
    if tamano_limpio not in catalogo:
        raise ValueError("El tamano del producto debe ser Chica, Mediana o Grande.")
    return catalogo[tamano_limpio]


def _parsear_decimal_positivo(valor, etiqueta):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{etiqueta} debe ser un numero valido.")
    if numero <= 0:
        raise ValueError(f"{etiqueta} debe ser mayor a 0.")
    return numero


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


def _asegurar_directorio_imagenes():
    os.makedirs(PRODUCTOS_IMG_DIR, exist_ok=True)


def _guardar_imagen_producto(archivo, id_producto):
    if not archivo or not archivo.filename:
        return
    _, extension = os.path.splitext(secure_filename(archivo.filename))
    extension = extension.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato de imagen no permitido. Usa png, jpg, jpeg, webp o gif.")
    _asegurar_directorio_imagenes()
    for ruta in glob.glob(os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}.*")):
        if os.path.isfile(ruta):
            os.remove(ruta)
    archivo.save(os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}{extension}"))


def _obtener_imagen_producto(id_producto, nombre_producto):
    for ruta in glob.glob(os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}.*")):
        if os.path.isfile(ruta):
            return f"img/productos/{os.path.basename(ruta)}"


def _existe_producto_duplicado(nombre, tamano, id_producto=None):
    nombre_norm = _normalizar_nombre_catalogo(nombre)
    tamano_norm = re.sub(r"\s+", " ", (tamano or "").strip()).lower()
    for p in Productos.query.all():
        if id_producto is not None and p.idProducto == id_producto:
            continue
        tamano_p = getattr(p, "tamano", None) or ""
        if (
            _normalizar_nombre_catalogo(p.nombre) == nombre_norm
            and re.sub(r"\s+", " ", tamano_p.strip()).lower() == tamano_norm
        ):
            return True
    return False


def _validar_activacion_producto(id_producto):
    """
    Valida si un producto puede ser activado.
    Retorna (puede_activar: bool, mensaje_error: str | None).
    
    Reglas:
    - Debe tener una receta registrada.
    - La receta no debe contener materias primas desactivadas.
    """
    receta = Recetas.query.filter_by(idProducto=id_producto).first()

    if not receta:
        return False, "No se puede activar el producto porque no tiene una receta registrada."

    # Obtener los detalles de la receta
    detalles = DetalleReceta.query.filter_by(idReceta=receta.idReceta).all()

    if not detalles:
        return False, "No se puede activar el producto porque su receta no tiene insumos registrados."

    # Verificar que todas las materias primas estén activas
    materias_desactivadas = []
    for detalle in detalles:
        mp = MateriasPrimas.query.get(detalle.idMateriaP)
        if mp and not mp.estatus:
            materias_desactivadas.append(mp.nombre)

    if materias_desactivadas:
        nombres = ", ".join(materias_desactivadas)
        return (
            False,
            f"No se puede activar el producto porque su receta contiene materias primas "
            f"desactivadas: {nombres}. Activa esas materias primas primero.",
        )

    return True, None


# ── Rutas ──────────────────────────────────────────────────────────────────────

@productos.route("/productos")
@rol_requerido("Administrador")
def listado_productos():
    nombre = request.args.get("nombre", "").strip()
    precio_inicio = request.args.get("precio_inicio", "").strip()
    precio_fin = request.args.get("precio_fin", "").strip()
    estatus_receta = request.args.get("estatus_receta", "").strip()
    estatus = request.args.get("estatus", "").strip()
    tamano_filtro = request.args.get("tamano", "").strip()

    nombre_val = nombre if nombre else None
    precio_inicio_val = Decimal(precio_inicio) if precio_inicio else None
    precio_fin_val = Decimal(precio_fin) if precio_fin else None
    estatus_val = estatus if estatus in {"1", "0", "todos"} else None
    tamano_val = tamano_filtro if tamano_filtro else None
    estatus_receta_val = estatus_receta if estatus_receta in {"1", "0"} else None

    productos_view = db.session.execute(
        text("CALL sp_listar_productos(:nombre, :precio_inicio, :precio_fin, :estatus, :tamano, :estatus_receta)"),
        {
            "nombre": nombre_val,
            "precio_inicio": precio_inicio_val,
            "precio_fin": precio_fin_val,
            "estatus": estatus_val,
            "tamano": tamano_val,
            "estatus_receta": estatus_receta_val,
        },
    ).mappings().all()

    imagenes = {
        "pepperoni": "img/Pizzas/PizzaPepperoni.png",
        "hawaiana": "img/Pizzas/PizzaHawaiana.png",
        "3 carnes": "img/Pizzas/PIzza3Carnes.png",
        "tres carnes": "img/Pizzas/PIzza3Carnes.png",
        "4 carnes": "img/Pizzas/Pizza4Carnes.png",
        "cuatro carnes": "img/Pizzas/Pizza4Carnes.png",
        "4 quesos": "img/Pizzas/Pizza4Quesos.png",
        "cuatro quesos": "img/Pizzas/Pizza4Quesos.png",
        "mexicana": "img/Pizzas/PizzaMexicana.png",
        "vegetariana": "img/Pizzas/PizzaVegetariana.png",
        "suprema": "img/Pizzas/PizzaSuprema.png",
        "espanola": "img/Pizzas/PizzaEspañola.png",
        "española": "img/Pizzas/PizzaEspañola.png",
        "fogatta": "img/Pizzas/PizzaFogatta.png",
    }

    _asegurar_directorio_imagenes()
    productos_final = []
    for p in productos_view:
        nombre_p = (p["nombre"] or "").lower()
        imagen = _obtener_imagen_producto(p["idProducto"], nombre_p)
        if not imagen:
            imagen = "img/Pizzas/PizzaPepperoni.png"
            for clave, ruta in imagenes.items():
                if clave in nombre_p:
                    imagen = ruta
                    break
        productos_final.append({**p, "imagen": imagen})

    filtros = {
        "nombre": nombre,
        "precio_inicio": precio_inicio,
        "precio_fin": precio_fin,
        "estatus_receta": estatus_receta,
        "estatus": estatus,
        "tamano": tamano_filtro,
    }
    form_error = session.pop("productos_form_error", None)
    return render_template(
        "productos/productos.html",
        productos=productos_final,
        filtros=filtros,
        form_error=form_error,
        tamanos_producto=TAMANOS_PRODUCTO,
        tamanos_filtro=TAMANOS_PRODUCTO,
    )


@productos.route("/registrar-producto", methods=["POST"])
@rol_requerido("Administrador")
def registrar_producto():
    datos_formulario = {}
    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre del producto")
        tamano = _validar_tamano_producto(request.form["tamano"])
        precio = _parsear_decimal_positivo(request.form["precio"], "El precio")
        stock = _parsear_entero_no_negativo(request.form["stock"], "El stock")
        datos_formulario = {
            "nombre": nombre,
            "precio": str(precio),
            "tamano": tamano,
            "stock": str(stock),
        }

        if _existe_producto_duplicado(nombre, tamano):
            _guardar_error_formulario("registro", "El producto ya existe.", datos_formulario)
            return redirect(url_for("productos.listado_productos"))

        db.session.execute(
            text(
                "CALL sp_gestion_productos("
                ":accion,:idProducto,:nombre,:precio,:tamano,:stock,:estatus,:ip,:usuario,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "INSERT",
                "idProducto": None,
                "nombre": nombre,
                "precio": precio,
                "tamano": tamano,
                "stock": stock,
                "estatus": 1,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        id_generado = db.session.execute(text("SELECT @p_idGenerado")).fetchone()[0]
        archivo_imagen = request.files.get("imagen")
        if resultado and resultado.startswith("SUCCESS") and id_generado:
            _guardar_imagen_producto(archivo_imagen, id_generado)
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("registro", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        _guardar_error_formulario("registro", str(e), datos_formulario)

    return redirect(url_for("productos.listado_productos"))


@productos.route("/editar-producto/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_producto(id):
    datos_formulario = {"id": id}
    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre del producto")
        tamano = _validar_tamano_producto(request.form["tamano"])
        precio = _parsear_decimal_positivo(request.form["precio"], "El precio")
        stock = _parsear_entero_no_negativo(request.form["stock"], "El stock")
        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "precio": str(precio),
            "tamano": tamano,
            "stock": str(stock),
        }

        if _existe_producto_duplicado(nombre, tamano, id):
            _guardar_error_formulario(
                "edicion",
                "Ya existe otro producto con el mismo nombre y tamano.",
                datos_formulario,
            )
            return redirect(url_for("productos.listado_productos"))

        db.session.execute(
            text(
                "CALL sp_gestion_productos("
                ":accion,:idProducto,:nombre,:precio,:tamano,:stock,:estatus,:ip,:usuario,"
                "@p_resultado,@p_idGenerado)"
            ),
            {
                "accion": "UPDATE",
                "idProducto": id,
                "nombre": nombre,
                "precio": precio,
                "tamano": tamano,
                "stock": stock,
                "estatus": None,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        archivo_imagen = request.files.get("imagen")
        if resultado and resultado.startswith("SUCCESS") and archivo_imagen and archivo_imagen.filename:
            _guardar_imagen_producto(archivo_imagen, id)
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        if categoria == "danger":
            _guardar_error_formulario("edicion", mensaje, datos_formulario)
        else:
            flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        _guardar_error_formulario("edicion", str(e), datos_formulario)

    return redirect(url_for("productos.listado_productos"))


@productos.route("/cambiar-estatus-producto/<int:id>/<int:estatus>")
@rol_requerido("Administrador")
def cambiar_estatus_producto(id, estatus):
    """
    Igual que materias primas: recibe el estatus actual en la URL y lo invierte.
    NUEVA LÓGICA: Si se va a ACTIVAR, valida que el producto tenga receta
    y que todas sus materias primas estén activas.
    """
    try:
        nuevo_estatus = 0 if estatus == 1 else 1

        # ── VALIDACIÓN AL ACTIVAR ──
        if nuevo_estatus == 1:
            puede_activar, mensaje_error = _validar_activacion_producto(id)
            if not puede_activar:
                flash(mensaje_error, "danger")
                return redirect(url_for("productos.listado_productos"))

        db.session.execute(
            text(
                "CALL sp_cambiar_estatus_producto(:idProducto,:ip,:usuario,"
                "@p_resultado,@p_nuevoEstatus)"
            ),
            {
                "idProducto": id,
                "ip": request.remote_addr,
                "usuario": session["usuario_id"],
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()
        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("productos.listado_productos"))


@productos.route("/productosTerminados")
@rol_requerido("Administrador")
def listado_productos_terminados():
    """
    Lista solo productos ACTIVOS con receta activa.
    Reutiliza sp_listar_productos con estatus=1 y estatus_receta=1.
    """
    nombre        = request.args.get("nombre",        "").strip()
    precio_inicio = request.args.get("precio_inicio", "").strip()
    precio_fin    = request.args.get("precio_fin",    "").strip()
    tamano_filtro = request.args.get("tamano",        "").strip()
    stock_filtro  = request.args.get("stock_filtro",  "").strip()

    nombre_val        = nombre         if nombre         else None
    precio_inicio_val = Decimal(precio_inicio) if precio_inicio else None
    precio_fin_val    = Decimal(precio_fin)    if precio_fin    else None
    tamano_val        = tamano_filtro  if tamano_filtro  else None

    productos_view = db.session.execute(
        text(
            "CALL sp_listar_productos("
            ":nombre, :precio_inicio, :precio_fin, :estatus, :tamano, :estatus_receta)"
        ),
        {
            "nombre":         nombre_val,
            "precio_inicio":  precio_inicio_val,
            "precio_fin":     precio_fin_val,
            "estatus":        "1",   # solo activos
            "tamano":         tamano_val,
            "estatus_receta": "1",   # solo con receta activa
        },
    ).mappings().all()

    imagenes = {
        "pepperoni":     "img/Pizzas/PizzaPepperoni.png",
        "hawaiana":      "img/Pizzas/PizzaHawaiana.png",
        "3 carnes":      "img/Pizzas/PIzza3Carnes.png",
        "tres carnes":   "img/Pizzas/PIzza3Carnes.png",
        "4 carnes":      "img/Pizzas/Pizza4Carnes.png",
        "cuatro carnes": "img/Pizzas/Pizza4Carnes.png",
        "4 quesos":      "img/Pizzas/Pizza4Quesos.png",
        "cuatro quesos": "img/Pizzas/Pizza4Quesos.png",
        "mexicana":      "img/Pizzas/PizzaMexicana.png",
        "vegetariana":   "img/Pizzas/PizzaVegetariana.png",
        "suprema":       "img/Pizzas/PizzaSuprema.png",
        "espanola":      "img/Pizzas/PizzaEspañola.png",
        "española":      "img/Pizzas/PizzaEspañola.png",
        "fogatta":       "img/Pizzas/PizzaFogatta.png",
    }

    _asegurar_directorio_imagenes()
    productos_final = []
    for p in productos_view:
        nombre_p = (p["nombre"] or "").lower()
        imagen   = _obtener_imagen_producto(p["idProducto"], nombre_p)
        if not imagen:
            imagen = "img/Pizzas/PizzaPepperoni.png"
            for clave, ruta in imagenes.items():
                if clave in nombre_p:
                    imagen = ruta
                    break

        # Filtro de stock en Python (evita modificar el SP existente)
        stock_actual = int(p["stock"] or 0)
        if stock_filtro == "con_stock" and stock_actual <= 0:
            continue
        if stock_filtro == "sin_stock" and stock_actual > 0:
            continue

        productos_final.append({**p, "imagen": imagen})

    filtros = {
        "nombre":       nombre,
        "precio_inicio": precio_inicio,
        "precio_fin":   precio_fin,
        "tamano":       tamano_filtro,
        "stock_filtro": stock_filtro,
    }

    return render_template(
        "productos/productosTerminados.html",
        productos=productos_final,
        filtros=filtros,
        tamanos_filtro=TAMANOS_PRODUCTO,
    )


@productos.route("/productos-terminados/actualizar-stock/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def actualizar_stock_producto_terminado(id):
    """
    Recibe el nuevo stock desde el formulario (campo 'nuevo_stock')
    y actualiza el producto usando sp_gestion_productos con acción UPDATE.
    """
    try:
        nuevo_stock_raw = request.form.get("nuevo_stock", "").strip()
        try:
            nuevo_stock = int(nuevo_stock_raw)
        except (ValueError, TypeError):
            flash("El stock debe ser un número entero válido.", "danger")
            return redirect(url_for("productos.listado_productos_terminados"))

        if nuevo_stock < 0:
            flash("El stock no puede ser negativo.", "danger")
            return redirect(url_for("productos.listado_productos_terminados"))

        producto = Productos.query.filter_by(idProducto=id, estatus=True).first()
        if not producto:
            flash("Producto no encontrado o inactivo.", "danger")
            return redirect(url_for("productos.listado_productos_terminados"))

        tiene_receta = db.session.execute(
            text("SELECT COUNT(*) FROM recetas WHERE idProducto = :id"),
            {"id": id},
        ).scalar()
        if not tiene_receta:
            flash("El producto no tiene receta activa.", "danger")
            return redirect(url_for("productos.listado_productos_terminados"))

        tamano_actual = getattr(producto, "tamano", "") or ""

        db.session.execute(
            text(
                "CALL sp_gestion_productos("
                ":accion, :idProducto, :nombre, :precio, :tamano, :stock, :estatus, :ip, :usuario,"
                "@p_resultado, @p_idGenerado)"
            ),
            {
                "accion":     "UPDATE",
                "idProducto": id,
                "nombre":     producto.nombre,
                "precio":     producto.precio,
                "tamano":     tamano_actual,
                "stock":      nuevo_stock,
                "estatus":    None,
                "ip":         request.remote_addr,
                "usuario":    session.get("usuario_id"),
            },
        )
        resultado = db.session.execute(text("SELECT @p_resultado")).fetchone()[0]
        db.session.commit()

        mensaje, categoria = _texto_resultado(resultado)
        flash(mensaje, categoria)

    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("productos.listado_productos_terminados"))