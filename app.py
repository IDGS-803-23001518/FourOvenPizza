from flask import Flask, render_template, request, redirect, url_for
from flask import flash
from flask_wtf.csrf import CSRFProtect
from flask import g

app = Flask(__name__)
csrf=CSRFProtect()

@app.route("/", methods=['GET','POST'])
def inicio():
	return render_template("inicio.html")

if __name__ == '__main__':
	csrf.init_app(app)
	app.run(debug=True)