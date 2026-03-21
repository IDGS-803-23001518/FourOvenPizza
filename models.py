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
    contrasenia = db.Column(db.String(255))
    estatus = db.Column(db.Boolean)
    fechaCreacion = db.Column(db.DateTime, default=datetime.datetime.now)
    
    rol = db.relationship('Roles', back_populates='usuarios')
    compras = db.relationship('Compras', back_populates='usuario')
    ventas = db.relationship('Ventas', back_populates='usuario')
    caja_movimientos = db.relationship('CajaMovimientos', back_populates='usuario')
    ordenes_produccion = db.relationship('OrdenesProduccion', back_populates='usuario')


class Categorias(db.Model):
    __tablename__ = "categorias"
    idCategoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    descripcion = db.Column(db.String(200))
    estatus = db.Column(db.Boolean)
    
    materias_primas = db.relationship('MateriasPrimas', back_populates='categoria')


class Productos(db.Model):
    __tablename__ = "productos"
    idProducto = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    precio = db.Column(db.Numeric(10, 2))
    tamaño = db.Column(db.String(50))
    stock = db.Column(db.Numeric(10, 2))
    estatus = db.Column(db.Boolean)
    
    detalle_ventas = db.relationship('DetalleVenta', back_populates='producto')
    detalle_produccion = db.relationship('DetalleProduccion', back_populates='producto')
    recetas = db.relationship('Recetas', back_populates='producto')


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


class Compras(db.Model):
    __tablename__ = "compras"
    idCompra = db.Column(db.Integer, primary_key=True)
    idProveedor = db.Column(db.Integer, db.ForeignKey('proveedores.idProveedor'), nullable=False)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    estado = db.Column(db.String(50))
    
    proveedor = db.relationship('Proveedores', back_populates='compras')
    usuario = db.relationship('Usuarios', back_populates='compras')
    detalle_compras = db.relationship('DetalleCompra', back_populates='compra', cascade='all, delete-orphan')


class DetalleCompra(db.Model):
    __tablename__ = "detalleCompra"
    idDetalleC = db.Column(db.Integer, primary_key=True)
    idCompra = db.Column(db.Integer, db.ForeignKey('compras.idCompra'), nullable=False)
    idMateriaP = db.Column(db.Integer, db.ForeignKey('materiasPrimas.idMateriaP'), nullable=False)
    idUnidadM = db.Column(db.Integer, db.ForeignKey('unidadesMedida.idUnidadM'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2))
    precio = db.Column(db.Numeric(10, 2))
    
    compra = db.relationship('Compras', back_populates='detalle_compras')
    materia_prima = db.relationship('MateriasPrimas', back_populates='detalle_compras')
    unidad_medida = db.relationship('UnidadesMedida', back_populates='detalle_compras')


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


class DetalleVenta(db.Model):
    __tablename__ = "detalleVenta"
    idDetalleV = db.Column(db.Integer, primary_key=True)
    idVenta = db.Column(db.Integer, db.ForeignKey('ventas.idVenta'), nullable=False)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    cantidad = db.Column(db.Integer)
    precio = db.Column(db.Numeric(10, 2))
    
    venta = db.relationship('Ventas', back_populates='detalle_ventas')
    producto = db.relationship('Productos', back_populates='detalle_ventas')


class CajaMovimientos(db.Model):
    __tablename__ = "cajaMovimientos"
    idMovimiento = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    tipo = db.Column(db.String(50))
    monto = db.Column(db.Numeric(10, 2))
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    
    usuario = db.relationship('Usuarios', back_populates='caja_movimientos')


class OrdenesProduccion(db.Model):
    __tablename__ = "ordenesProduccion"
    idOrden = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.Integer, db.ForeignKey('usuarios.idUsuario'), nullable=False)
    estado = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.datetime.now)
    
    usuario = db.relationship('Usuarios', back_populates='ordenes_produccion')
    detalle_produccion = db.relationship('DetalleProduccion', back_populates='orden', cascade='all, delete-orphan')


class DetalleProduccion(db.Model):
    __tablename__ = "detalleProduccion"
    idDetalleP = db.Column(db.Integer, primary_key=True)
    idProducto = db.Column(db.Integer, db.ForeignKey('productos.idProducto'), nullable=False)
    idOrden = db.Column(db.Integer, db.ForeignKey('ordenesProduccion.idOrden'), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2))
    
    producto = db.relationship('Productos', back_populates='detalle_produccion')
    orden = db.relationship('OrdenesProduccion', back_populates='detalle_produccion')


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