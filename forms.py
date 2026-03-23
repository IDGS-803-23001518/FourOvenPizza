from wtforms import Form
from wtforms import StringField, IntegerField, PasswordField, SelectField, HiddenField, DecimalField, TextAreaField, DateTimeField
from wtforms import EmailField, BooleanField
from wtforms import validators
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Optional, NumberRange, Length

class RolForm(Form):
    idRol = IntegerField('idRol')
    nombre = StringField('Nombre del Rol', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=50, message='El nombre debe tener entre 3 y 50 caracteres')
    ])
    estatus = BooleanField('Estatus', default=True)

class UsuarioForm(Form):
    idUsuario = IntegerField('idUsuario')
    idRol = SelectField('Rol',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un rol')]
    )
    nombre = StringField('Nombre Completo', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
    ])
    usuario = StringField('Nombre de Usuario', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=4, max=50, message='El usuario debe tener entre 4 y 50 caracteres')
    ])
    email = EmailField('Correo Electrónico', [          # ← NUEVO
        validators.DataRequired(message='El campo es requerido'),
        validators.Email(message='Ingrese un correo válido'),
        validators.length(max=150)
    ])
    contrasenia = PasswordField('Contraseña', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=6, max=255, message='La contraseña debe tener al menos 6 caracteres')
    ])
    estatus = BooleanField('Estatus', default=True)

class LoginForm(FlaskForm):
    usuario = StringField('Nombre de Usuario', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=4, max=50, message='El usuario debe tener entre 4 y 50 caracteres')
    ])
    contrasenia = PasswordField('Contraseña', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=6, max=255, message='La contraseña debe tener al menos 6 caracteres')
    ])

class CategoriaForm(Form):
    idCategoria = IntegerField('idCategoria')
    nombre = StringField('Nombre de la Categoría', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
    ])
    descripcion = TextAreaField('Descripción', [
        validators.Optional(),
        validators.length(max=200, message='La descripción no puede exceder los 200 caracteres')
    ])
    estatus = BooleanField('Estatus', default=True)

class ProductoForm(Form):
    idProducto = IntegerField('idProducto')
    nombre = StringField('Nombre del Producto', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
    ])
    precio = DecimalField('Precio', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
    ], places=2)
    tamaño = StringField('Tamaño', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=50, message='El tamaño no puede exceder los 50 caracteres')
    ])
    stock = DecimalField('Stock', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El stock debe ser mayor o igual a 0')
    ], places=2)
    estatus = BooleanField('Estatus', default=True)

class ProveedorForm(Form):
    idProveedor = IntegerField('idProveedor')
    nombre = StringField('Nombre del Proveedor', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
    ])
    correo = EmailField('Correo Electrónico', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Email(message='Ingrese un correo electrónico válido')
    ])
    telefono = StringField('Teléfono', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=8, max=20, message='El teléfono debe tener entre 8 y 20 caracteres')
    ])
    direccion = StringField('Dirección', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=200, message='La dirección no puede exceder los 200 caracteres')
    ])
    estatus = BooleanField('Estatus', default=True)

class UnidadMedidaForm(Form):
    idUnidadM = IntegerField('idUnidadM')
    nombre = StringField('Nombre de la Unidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=2, max=50, message='El nombre debe tener entre 2 y 50 caracteres')
    ])
    tipo = StringField('Tipo de Unidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=50, message='El tipo no puede exceder los 50 caracteres')
    ])
    equivalente = DecimalField('Equivalente', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El equivalente debe ser mayor o igual a 0')
    ], places=2)
    estatus = BooleanField('Estatus', default=True)

class MateriaPrimaForm(Form):
    idMateriaP = IntegerField('idMateriaP')
    nombre = StringField('Nombre de la Materia Prima', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres')
    ])
    tipo = StringField('Tipo', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=50, message='El tipo no puede exceder los 50 caracteres')
    ])
    idCategoria = SelectField('Categoría',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione una categoría')]
    )
    stock = DecimalField('Stock Actual', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El stock debe ser mayor o igual a 0')
    ], places=2)
    stockMinimo = DecimalField('Stock Mínimo', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El stock mínimo debe ser mayor o igual a 0')
    ], places=2)
    estatus = BooleanField('Estatus', default=True)

class CompraForm(Form):
    idCompra = IntegerField('idCompra')
    idProveedor = SelectField('Proveedor',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un proveedor')]
    )
    idUsuario = SelectField('Usuario',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un usuario')]
    )
    estado = SelectField('Estado', 
        choices=[('PENDIENTE', 'Pendiente'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')],
        validators=[DataRequired(message='El campo es requerido')]
    )


class DetalleCompraForm(Form):
    idDetalleC = IntegerField('idDetalleC')
    idCompra = HiddenField()
    idMateriaP = SelectField('Materia Prima',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione una materia prima')]
    )
    idUnidadM = SelectField('Unidad de Medida',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione una unidad de medida')]
    )
    cantidad = DecimalField('Cantidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='La cantidad debe ser mayor a 0')
    ], places=2)
    precio = DecimalField('Precio Unitario', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
    ], places=2)

class VentaForm(Form):
    idVenta = IntegerField('idVenta')
    idUsuario = SelectField('Usuario',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un usuario')]
    )
    nombreCliente = StringField('Nombre del Cliente', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=100, message='El nombre no puede exceder los 100 caracteres')
    ])
    tipo = SelectField('Tipo de Venta', 
        choices=[('CONTADO', 'Contado'), ('CREDITO', 'Crédito')],
        validators=[DataRequired(message='El campo es requerido')]
    )
    metodoPago = SelectField('Método de Pago', 
        choices=[('EFECTIVO', 'Efectivo'), ('TARJETA', 'Tarjeta'), ('TRANSFERENCIA', 'Transferencia')],
        validators=[DataRequired(message='El campo es requerido')]
    )
    estado = SelectField('Estado', 
        choices=[('PENDIENTE', 'Pendiente'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')],
        validators=[DataRequired(message='El campo es requerido')]
    )


class DetalleVentaForm(Form):
    idDetalleV = IntegerField('idDetalleV')
    idVenta = HiddenField()
    idProducto = SelectField('Producto',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un producto')]
    )
    cantidad = IntegerField('Cantidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=1, message='La cantidad debe ser mayor a 0')
    ])
    precio = DecimalField('Precio Unitario', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
    ], places=2)

class CajaMovimientoForm(Form):
    idMovimiento = IntegerField('idMovimiento')
    idUsuario = SelectField('Usuario',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un usuario')]
    )
    tipo = SelectField('Tipo de Movimiento', 
        choices=[('INGRESO', 'Ingreso'), ('EGRESO', 'Egreso')],
        validators=[DataRequired(message='El campo es requerido')]
    )
    monto = DecimalField('Monto', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='El monto debe ser mayor a 0')
    ], places=2)
    descripcion = StringField('Descripción', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=200, message='La descripción no puede exceder los 200 caracteres')
    ])

class OrdenProduccionForm(Form):
    idOrden = IntegerField('idOrden')
    idUsuario = SelectField('Usuario',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un usuario')]
    )
    estado = SelectField('Estado', 
        choices=[('PENDIENTE', 'Pendiente'), ('EN_PRODUCCION', 'En Producción'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')],
        validators=[DataRequired(message='El campo es requerido')]
    )


class DetalleProduccionForm(Form):
    idDetalleP = IntegerField('idDetalleP')
    idProducto = SelectField('Producto',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un producto')]
    )
    idOrden = HiddenField()
    cantidad = DecimalField('Cantidad a Producir', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='La cantidad debe ser mayor a 0')
    ], places=2)

class RecetaForm(Form):
    idReceta = IntegerField('idReceta')
    idProducto = SelectField('Producto',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione un producto')]
    )
    descripcion = TextAreaField('Descripción de la Receta', [
        validators.Optional(),
        validators.length(max=200, message='La descripción no puede exceder los 200 caracteres')
    ])


class DetalleRecetaForm(Form):
    idDetalleR = IntegerField('idDetalleR')
    idReceta = HiddenField()
    idMateriaP = SelectField('Materia Prima',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione una materia prima')]
    )
    cantidad = DecimalField('Cantidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='La cantidad debe ser mayor a 0')
    ], places=2)

class MermaForm(Form):
    idMerma = IntegerField('idMerma')
    descripcion = TextAreaField('Descripción de la Merma', [
        validators.DataRequired(message='El campo es requerido'),
        validators.length(max=200, message='La descripción no puede exceder los 200 caracteres')
    ])
    estatus = BooleanField('Estatus', default=True)


class DetalleMermaForm(Form):
    idDetalleM = IntegerField('idDetalleM')
    idMerma = HiddenField()
    idMateriaP = SelectField('Materia Prima',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Seleccione una materia prima')]
    )
    cantidad = DecimalField('Cantidad', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='La cantidad debe ser mayor a 0')
    ], places=2)

class ReporteFechasForm(Form):
    fecha_inicio = DateTimeField('Fecha de Inicio', [
        validators.DataRequired(message='El campo es requerido')
    ], format='%Y-%m-%d')
    fecha_fin = DateTimeField('Fecha de Fin', [
        validators.DataRequired(message='El campo es requerido')
    ], format='%Y-%m-%d')