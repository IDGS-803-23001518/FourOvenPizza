from flask import Blueprint

bitacoras=Blueprint(
    'bitacoras',
    __name__,
    template_folder='templates',
    static_folder='static')
from . import routes