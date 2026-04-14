from flask import Blueprint

materiasPrimas = Blueprint(
    'materiasPrimas',
    __name__,
    template_folder='templates',
    static_folder='static')