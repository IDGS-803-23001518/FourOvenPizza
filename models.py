import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Roles(db.Model):
    __tablename__ = "roles"
    idRol = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50))
    estatus = db.Column(db.Boolean)

    usuarios = db.relationship('Usuarios', back_populates='rol')


class Usuarios(db.Model):
    __tablename__ = "usuarios"
    idUsuario = db.Column(db.Integer, primary_key=True)
    idRol = db.Column(db.Integer, db.ForeignKey('roles.idRol'), nullable=False)
    nombre = db.Column(db.String(100))
    usuario = db.Column(db.String(50))
    email = db.Column(db.String(150), unique=True, nullable=True)
    contrasenia = db.Column(db.String(255))
    estatus = db.Column(db.Boolean)
    fechaCreacion = db.Column(db.DateTime, default=datetime.datetime.now)

    rol = db.relationship('Roles', back_populates='usuarios')
    compras = db.relationship('Compras', back_populates='usuario')
    ventas = db.relationship('Ventas', back_populates='usuario')
    caja_movimientos = db.relationship('CajaMovimientos', back_populates='usuario')
    ordenes_produccion = db.relationship('OrdenesProduccion', back_populates='usuario')
    resets = db.relationship('ResetContrasenia', back_populates='usuario')


class ResetContrasenia(db.Model):
    __tablename__ = 'resetContrasenia'
    idReset = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expiracion = db.Column(db.DateTime, nullable=False)
    usado = db.Column(db.Boolean, default=False)

    usuario = db.relationship('Usuarios', back_populates='resets')

    def esta_vigente(self):
        return not self.usado and datetime.datetime.utcnow() < self.expiracion


class IntentosFallidos(db.Model):
    __tablename__ = "intentos_fallidos"
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), nullable=False, index=True)
    intentos = db.Column(db.Integer, default=0)
    bloqueado_hasta = db.Column(db.DateTime, nullable=True)

    def esta_bloqueado(self):
        if self.bloqueado_hasta and datetime.datetime.utcnow() < self.bloqueado_hasta:
            return True
        return False

    def segundos_restantes(self):
        if self.bloqueado_hasta:
            diff = (self.bloqueado_hasta - datetime.datetime.utcnow()).total_seconds()
            return max(0, int(diff))
        return 0


class Categorias(db.Model):
    __tablename__ = "categorias"
    idCategoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    descripcion = db.Column(db.String(200))
    estatus = db.Column(db.Boolean)

    materias_primas = db.relationship('MateriasPrimas', back_populates='categoria')


class Proveedores(db.Model):
    __tablename__ = "proveedores"
    idProveedor = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    correo = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    estatus = db.Column(db.Boolean)

    compras = db.relationship('Compras', back_populates='proveedor')


class UnidadesMedida(db.Model):
    __tablename__ = "unidadesMedida"
    idUnidadM = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50))
    tipo = db.Column(db.String(50))
    equivalente = db.Column(db.Numeric(10, 2))
    estatus = db.Column(db.Boolean)

    detalle_compras = db.relationship('DetalleCompra', back_populates='unidad_medida')


class MateriasPrimas(db.Model):
    __tablename__ = "materiasPrimas"
    idMateriaP = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    tipo = db.Column(db.String(50))
    idCategoria = db.Column(db.Integer, db.ForeignKey('categorias.idCategoria'), nullable=False)
    stock = db.Column(db.Numeric(10, 2))
    stockMinimo = db.Column(db.Numeric(10, 2))
    estatus = db.Column(db.Boolean)

    categoria = db.relationship('Categorias', back_populates='materias_primas')
    detalle_compras = db.relationship('DetalleCompra', back_populates='materia_prima')
    detalle_recetas = db.relationship('DetalleReceta', back_populates='materia_prima')
    detalle_mermas = db.relationship('DetalleMerma', back_populates='materia_prima')


class Mermas(db.Model):
    __tablename__ = "mermas"
    idMerma = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    estatus = db.Column(db.Boolean)

    detalle_mermas = db.relationship('DetalleMerma', back_populates='merma', cascade='all, delete-orphan')


class DetalleMerma(db.Model):
    __tablename__ = "detalleMerma"
    idDetalleM = db.Column(db.Integer, primary_key=True)
    idMerma = db.Column(db.Integer, db.ForeignKey('mermas.idMerma'), nullable=False)
    idMateriaP = db.Column(db.Integer, db.ForeignKey('materiasPrimas.idMateriaP'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2))

    merma = db.relationship('Mermas', back_populates='detalle_mermas')
    materia_prima = db.relationship('MateriasPrimas', back_populates='detalle_mermas')


class Compras(db.Model):
    __tablename__ = "compras"
    idCompra = db.Column(db.Integer, primary_key=True)
    idProveedor = db.Column(db.Integer, db.ForeignKey('proveedores.idProveedor'), nullable=False)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    estatus = db.Column(db.String(30))
    proveedor = db.relationship('Proveedores', back_populates='compras')
    usuario = db.relationship('Usuarios', back_populates='compras')
    detalle_compras = db.relationship('DetalleCompra', back_populates='compra', cascade='all, delete-orphan')


class DetalleCompra(db.Model):
    __tablename__ = "detalleCompra"
    idDetalleC = db.Column(db.Integer, primary_key=True)
    idCompra = db.Column(db.Integer, db.ForeignKey('compras.idCompra'), nullable=False)
    idMateriaP = db.Column(db.Integer, db.ForeignKey('materiasPrimas.idMateriaP'), nullable=False)
    idUnidadM = db.Column(db.Integer, db.ForeignKey('unidadesMedida.idUnidadM'), nullable=True)
    cantidad = db.Column(db.Numeric(10, 2))
    precio = db.Column(db.Numeric(10, 2))

    compra = db.relationship('Compras', back_populates='detalle_compras')
    materia_prima = db.relationship('MateriasPrimas', back_populates='detalle_compras')
    unidad_medida = db.relationship('UnidadesMedida', back_populates='detalle_compras')


class Productos(db.Model):
    __tablename__ = "productos"
    idProducto = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    precio = db.Column(db.Numeric(10, 2))
    tamano = db.Column('tamaño', db.String(50))
    stock = db.Column(db.Numeric(10, 2))
    imagen = db.Column(db.LargeBinary(length=2000000))
    estatus = db.Column(db.Boolean)

    detalle_ventas = db.relationship('DetalleVenta', back_populates='producto')
    detalle_produccion = db.relationship('DetalleProduccion', back_populates='producto')
    recetas = db.relationship('Recetas', back_populates='producto')
    ventas_stock_reservado = db.relationship('VentaStockReservado', back_populates='producto')


class Ventas(db.Model):
    __tablename__ = "ventas"
    idVenta = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    nombreCliente = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    tipo = db.Column(db.String(50))
    metodoPago = db.Column(db.String(50))
    estado = db.Column(db.String(50))

    usuario = db.relationship('Usuarios', back_populates='ventas')
    detalle_ventas = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')
    stock_reservado = db.relationship('VentaStockReservado', back_populates='venta', cascade='all, delete-orphan')


class DetalleVenta(db.Model):
    __tablename__ = "detalleVenta"
    idDetalleV = db.Column(db.Integer, primary_key=True)
    idVenta = db.Column(db.Integer, db.ForeignKey('ventas.idVenta'), nullable=False)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    cantidad = db.Column(db.Integer)
    precio = db.Column(db.Numeric(10, 2))

    venta = db.relationship('Ventas', back_populates='detalle_ventas')
    producto = db.relationship('Productos', back_populates='detalle_ventas')


# ===================================================================
# NUEVA TABLA: Stock reservado temporalmente por ventas activas
# (Esto reemplaza el CREATE TABLE del SP)
# ===================================================================
class VentaStockReservado(db.Model):
    __tablename__ = "ventaStockReservado"
    idReserva = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idVenta = db.Column(db.Integer, db.ForeignKey('ventas.idVenta'), nullable=False)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    cantidadReservada = db.Column(db.Integer, nullable=False, default=0)  # tomado del stock actual
    cantidadFaltante = db.Column(db.Integer, nullable=False, default=0)   # enviado a producción
    idOrdenProduccion = db.Column(db.Integer, db.ForeignKey('ordenesProduccion.idOrden'), nullable=True)

    # Relaciones
    venta = db.relationship('Ventas', back_populates='stock_reservado')
    producto = db.relationship('Productos', back_populates='ventas_stock_reservado')
    orden_produccion = db.relationship('OrdenesProduccion', back_populates='ventas_reservadas')

    # Restricción única por venta+producto (evita duplicados)
    __table_args__ = (
        db.UniqueConstraint('idVenta', 'idProducto', name='uk_venta_producto'),
    )


class TicketVenta(db.Model):
    __tablename__ = "ticket_venta"
    id = db.Column(db.Integer, primary_key=True)
    idVenta = db.Column(db.Integer, db.ForeignKey('ventas.idVenta'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    tipoVenta = db.Column(db.String(50))
    usuarioId = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    nombreCliente = db.Column(db.String(100))
    total = db.Column(db.Numeric(10, 2))
    estado = db.Column(db.String(50))
    numeroTicket = db.Column(db.String(50), unique=True)
    pdfGenerado = db.Column(db.Boolean, default=False)
    fechaGeneracion = db.Column(db.DateTime, nullable=True)

    venta = db.relationship('Ventas', backref='tickets')
    usuario = db.relationship('Usuarios', backref='tickets_generados')


class DetalleTicketVenta(db.Model):
    __tablename__ = "detalle_ticket_venta"
    idDetalleTicket = db.Column(db.Integer, primary_key=True)
    idTicket = db.Column(db.Integer, db.ForeignKey('ticket_venta.id'), nullable=False)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    nombreProducto = db.Column(db.String(100))
    cantidad = db.Column(db.Integer)
    precioUnitario = db.Column(db.Numeric(10, 2))
    subtotal = db.Column(db.Numeric(10, 2))

    ticket = db.relationship('TicketVenta', backref='detalles')
    producto = db.relationship('Productos', backref='tickets_detalle')


class Recetas(db.Model):
    __tablename__ = "recetas"
    idReceta = db.Column(db.Integer, primary_key=True)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    descripcion = db.Column(db.String(200))

    producto = db.relationship('Productos', back_populates='recetas')
    detalle_recetas = db.relationship('DetalleReceta', back_populates='receta', cascade='all, delete-orphan')


class DetalleReceta(db.Model):
    __tablename__ = "detalleReceta"
    idDetalleR = db.Column(db.Integer, primary_key=True)
    idReceta = db.Column(db.Integer, db.ForeignKey('recetas.idReceta'), nullable=False)
    idMateriaP = db.Column(db.Integer, db.ForeignKey('materiasPrimas.idMateriaP'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2))

    receta = db.relationship('Recetas', back_populates='detalle_recetas')
    materia_prima = db.relationship('MateriasPrimas', back_populates='detalle_recetas')


# ===================================================================
# TABLA MODIFICADA: OrdenesProduccion con columnas de origen
# (Esto reemplaza el ALTER TABLE del SP)
# ===================================================================
class OrdenesProduccion(db.Model):
    __tablename__ = "ordenesProduccion"
    idOrden = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    estado = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    
    # NUEVAS COLUMNAS (reemplazan el ALTER TABLE)
    origen = db.Column(db.String(20), default='Manual', nullable=True)  # 'Manual' | 'Venta'
    idVentaOrigen = db.Column(db.Integer, db.ForeignKey('ventas.idVenta'), nullable=True)

    # Relaciones
    usuario = db.relationship('Usuarios', back_populates='ordenes_produccion')
    detalle_produccion = db.relationship('DetalleProduccion', back_populates='orden', cascade='all, delete-orphan')
    ventas_reservadas = db.relationship('VentaStockReservado', back_populates='orden_produccion')
    venta_origen = db.relationship('Ventas', foreign_keys=[idVentaOrigen], backref='ordenes_produccion_relacionadas')


class DetalleProduccion(db.Model):
    __tablename__ = "detalleProduccion"
    idDetalleP = db.Column(db.Integer, primary_key=True)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    idOrden = db.Column(db.Integer, db.ForeignKey('ordenesProduccion.idOrden'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2))

    producto = db.relationship('Productos', back_populates='detalle_produccion')
    orden = db.relationship('OrdenesProduccion', back_populates='detalle_produccion')


class BitacoraAccesos(db.Model):
    __tablename__ = "bitacora_accesos"
    id = db.Column(db.Integer, primary_key=True)
    usuarioId = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=True)
    nombreUsuario = db.Column(db.String(100))
    evento = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    ip = db.Column(db.String(45))
    navegador = db.Column(db.String(255))
    resultado = db.Column(db.String(50))

    usuario = db.relationship('Usuarios', backref='bitacora_accesos')


class BitacoraEventos(db.Model):
    __tablename__ = "bitacora_eventos"
    id = db.Column(db.Integer, primary_key=True)
    usuarioId = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=True)
    nombreUsuario = db.Column(db.String(100))
    modulo = db.Column(db.String(100))
    accion = db.Column(db.String(100))
    referencial = db.Column(db.String(100))
    referencia = db.Column(db.String(255))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    ip = db.Column(db.String(45))

    usuario = db.relationship('Usuarios', backref='bitacora_eventos')


class BitacoraSistema(db.Model):
    __tablename__ = "bitacora_sistema"
    id = db.Column(db.Integer, primary_key=True)
    nivel = db.Column(db.String(20))
    modulo = db.Column(db.String(100))
    mensaje = db.Column(db.Text)
    detalles = db.Column(db.Text, nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    ip = db.Column(db.String(45))
    usuarioId = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=True)

    usuario = db.relationship('Usuarios', backref='bitacora_sistema')


class CajaMovimientos(db.Model):
    __tablename__ = "cajaMovimientos"
    idMovimiento = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    tipo = db.Column(db.String(50))
    monto = db.Column(db.Numeric(10, 2))
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)

    usuario = db.relationship('Usuarios', back_populates='caja_movimientos')