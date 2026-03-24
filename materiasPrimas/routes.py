from flask import render_template, request
from sqlalchemy import extract, func

import forms
from models import MateriasPrimas, UnidadesMedida

from . import materiasPrimas


@materiasPrimas.route("/materiasPrimas", methods=['GET','POST'])
def listadoMaterias():
    create_form = forms.MateriaPrimaForm(request.form)
    lista_materias = MateriasPrimas.query.all()
    return render_template("materiasPrimas/materiasPrimas.html", form=create_form, materias=lista_materias)

@materiasPrimas.route("/unidadesMedida", methods=['GET','POST'])
def listadoUnidades():
    create_form = forms.UnidadMedidaForm(request.form)
    lista_unidades = UnidadesMedida.query.all()
    return render_template("materiasPrimas/unidadesMedida.html", form=create_form, unidades=lista_unidades)