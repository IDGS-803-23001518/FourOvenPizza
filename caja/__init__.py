from flask import Blueprint

caja = Blueprint(
    'caja',
    __name__
)

from . import routes