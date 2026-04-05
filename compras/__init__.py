from flask import Blueprint

comprass = Blueprint(
    'comprass',
    __name__
)

from . import routes