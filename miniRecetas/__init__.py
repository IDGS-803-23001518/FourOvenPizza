from flask import Blueprint

miniRecetas=Blueprint(
    'miniRecetas',
    __name__,
    template_folder='templates',
    static_folder='static')
from . import routes