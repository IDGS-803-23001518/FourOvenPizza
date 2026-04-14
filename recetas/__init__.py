from flask import Blueprint

recetas = Blueprint(
    "recetas",
    __name__,
    template_folder="templates",
    static_folder="static",
)
