import glob
import os
import re
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.utils import secure_filename

from autentificacion.routes import rol_requerido
from models import Productos, db

from . import productos


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTOS_IMG_DIR = os.path.join(BASE_DIR, "static", "img", "productos")
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TAMANOS_PRODUCTO = ("Chica", "Mediana", "Grande")
PATRON_NOMBRE_CATALOGO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9 ]+$")


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
    catalogo = {valor.lower(): valor for valor in TAMANOS_PRODUCTO}

    if tamano_limpio not in catalogo:
        raise ValueError("El tamano del producto debe ser Chica, Mediana o Grande.")

    return catalogo[tamano_limpio]


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


def _parsear_decimal_positivo(valor, etiqueta):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{etiqueta} debe ser un numero valido.")

    if numero <= 0:
        raise ValueError(f"{etiqueta} debe ser mayor a 0.")

    return numero


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

    for ruta_existente in glob.glob(os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}.*")):
        if os.path.isfile(ruta_existente):
            os.remove(ruta_existente)

    ruta_destino = os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}{extension}")
    archivo.save(ruta_destino)


def _obtener_tamano_producto_modelo(producto):
    return (
        getattr(producto, "tamano", None)
        or getattr(producto, "tamaño", None)
        or getattr(producto, "tamaÃ±o", None)
        or getattr(producto, "tamaÃƒÂ±o", None)
        or getattr(producto, "tamaÃƒÆ’Ã‚Â±o", None)
    )


def _obtener_imagen_producto(id_producto, nombre_producto):
    for ruta_existente in glob.glob(os.path.join(PRODUCTOS_IMG_DIR, f"producto_{id_producto}.*")):
        if os.path.isfile(ruta_existente):
            return f"img/productos/{os.path.basename(ruta_existente)}"


def _resolver_columna_tamano():
    columnas = db.session.execute(text("SHOW COLUMNS FROM productos")).mappings().all()
    nombres = {columna["Field"] for columna in columnas}

    for candidata in ("tamano", "tamaño", "tamaÃ±o", "tamaÃƒÂ±o"):
        if candidata in nombres:
            return candidata

    return "tamano"


def _existe_producto_duplicado(nombre, tamano, id_producto=None):
    nombre_normalizado = _normalizar_nombre_catalogo(nombre)
    tamano_normalizado = re.sub(r"\s+", " ", (tamano or "").strip()).lower()

    for producto in Productos.query.all():
        if id_producto is not None and producto.idProducto == id_producto:
            continue

        tamano_producto = _obtener_tamano_producto_modelo(producto)
        if (
            _normalizar_nombre_catalogo(producto.nombre) == nombre_normalizado
            and re.sub(r"\s+", " ", (tamano_producto or "").strip()).lower() == tamano_normalizado
        ):
            return True

    return False


@productos.route("/productos")
@rol_requerido("Administrador")
def listado_productos():
    columna_tamano = _resolver_columna_tamano()
    nombre = request.args.get("nombre", "").strip()
    precio_inicio = request.args.get("precio_inicio", "").strip()
    precio_fin = request.args.get("precio_fin", "").strip()
    estatus_receta = request.args.get("estatus_receta", "").strip()
    estatus = request.args.get("estatus", "").strip()

    condiciones = []
    parametros = {}

    if nombre:
        condiciones.append("nombre LIKE :nombre")
        parametros["nombre"] = f"%{nombre}%"

    if precio_inicio:
        condiciones.append("precio >= :precio_inicio")
        parametros["precio_inicio"] = precio_inicio

    if precio_fin:
        condiciones.append("precio <= :precio_fin")
        parametros["precio_fin"] = precio_fin

    if estatus in {"1", "0"}:
        condiciones.append("estatus = :estatus")
        parametros["estatus"] = int(estatus)

    if estatus_receta in {"1", "0"}:
        condiciones.append(
            """
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM recetas r
                    WHERE r.idProducto = productos.idProducto
                ) THEN 1 ELSE 0
            END = :estatus_receta
            """
        )
        parametros["estatus_receta"] = int(estatus_receta)

    where_clause = ""
    if condiciones:
        where_clause = "WHERE " + " AND ".join(condiciones)

    productos_view = db.session.execute(
        text(
            f"""
            SELECT
                idProducto,
                nombre,
                precio,
                `{columna_tamano}` AS tamano,
                stock,
                estatus,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM recetas r
                        WHERE r.idProducto = productos.idProducto
                    ) THEN 1 ELSE 0
                END AS receta_activa
            FROM productos
            {where_clause}
            ORDER BY nombre ASC
            """
        ),
        parametros,
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
    for producto in productos_view:
        nombre_producto = (producto["nombre"] or "").lower()
        imagen = _obtener_imagen_producto(producto["idProducto"], nombre_producto)

        if not imagen:
            imagen = "img/Pizzas/PizzaPepperoni.png"

            for clave, ruta in imagenes.items():
                if clave in nombre_producto:
                    imagen = ruta
                    break

        productos_final.append({**producto, "imagen": imagen})

    filtros = {
        "nombre": nombre,
        "precio_inicio": precio_inicio,
        "precio_fin": precio_fin,
        "estatus_receta": estatus_receta,
        "estatus": estatus,
    }
    form_error = session.pop("productos_form_error", None)

    return render_template(
        "productos/productos.html",
        productos=productos_final,
        filtros=filtros,
        form_error=form_error,
        tamanos_producto=TAMANOS_PRODUCTO,
    )


@productos.route("/registrar-producto", methods=["POST"])
@rol_requerido("Administrador")
def registrar_producto():
    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre del producto")
        tamano = _validar_tamano_producto(request.form["tamano"])
        precio = _parsear_decimal_positivo(request.form["precio"], "El precio")
        stock = _parsear_entero_positivo(request.form["stock"], "El stock")
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
                """
                CALL sp_gestion_productos(
                    :accion,
                    :idProducto,
                    :nombre,
                    :precio,
                    :tamano,
                    :stock,
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
        _guardar_error_formulario("registro", str(e), datos_formulario if 'datos_formulario' in locals() else {})

    return redirect(url_for("productos.listado_productos"))


@productos.route("/editar-producto/<int:id>", methods=["POST"])
@rol_requerido("Administrador")
def editar_producto(id):
    try:
        nombre = _validar_nombre_catalogo(request.form["nombre"], "El nombre del producto")
        tamano = _validar_tamano_producto(request.form["tamano"])
        precio = _parsear_decimal_positivo(request.form["precio"], "El precio")
        stock = _parsear_entero_positivo(request.form["stock"], "El stock")
        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "precio": str(precio),
            "tamano": tamano,
            "stock": str(stock),
            "estatus": request.form["estatus"],
        }

        if _existe_producto_duplicado(nombre, tamano, id):
            _guardar_error_formulario("edicion", "Ya existe otro producto con el mismo nombre y tamano.", datos_formulario)
            return redirect(url_for("productos.listado_productos"))

        db.session.execute(
            text(
                """
                CALL sp_gestion_productos(
                    :accion,
                    :idProducto,
                    :nombre,
                    :precio,
                    :tamano,
                    :stock,
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
                "idProducto": id,
                "nombre": nombre,
                "precio": precio,
                "tamano": tamano,
                "stock": stock,
                "estatus": request.form["estatus"],
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
        _guardar_error_formulario("edicion", str(e), datos_formulario if 'datos_formulario' in locals() else {"id": id})

    return redirect(url_for("productos.listado_productos"))


@productos.route("/eliminar-producto/<int:id>")
@rol_requerido("Administrador")
def eliminar_producto(id):
    try:
        db.session.execute(
            text(
                """
                CALL sp_gestion_productos(
                    :accion,
                    :idProducto,
                    :nombre,
                    :precio,
                    :tamano,
                    :stock,
                    :estatus,
                    :ip,
                    :usuario,
                    @p_resultado,
                    @p_idGenerado
                )
                """
            ),
            {
                "accion": "DELETE",
                "idProducto": id,
                "nombre": None,
                "precio": None,
                "tamano": None,
                "stock": None,
                "estatus": None,
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
