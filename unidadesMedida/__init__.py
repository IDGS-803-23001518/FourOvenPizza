from flask import Blueprint

unidadesMedida = Blueprint(
    'unidadesMedida',
    __name__,
    template_folder='templates',
    static_folder='static')