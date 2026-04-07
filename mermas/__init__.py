from flask import Blueprint

mermas=Blueprint(
    'mermas',
    __name__,
    template_folder='templates',
    static_folder='static')
from . import routes