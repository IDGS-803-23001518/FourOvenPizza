from flask import Blueprint

compras = Blueprint(
    'compras',
    __name__
)

from . import routes