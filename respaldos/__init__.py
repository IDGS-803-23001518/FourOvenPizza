from flask import Blueprint

respaldos = Blueprint(
    "respaldos",
    __name__,
    template_folder="templates",
    static_folder="static",
)
