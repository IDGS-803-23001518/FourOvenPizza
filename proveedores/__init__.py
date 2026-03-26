from flask import Blueprint

proveedores=Blueprint(
    'proveedores',
    __name__,
    template_folder='templates',
    static_folder='static')
from . import routes