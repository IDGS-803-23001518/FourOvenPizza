from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from flask import session as flask_session, has_request_context, g

_engines = {}
_session_factories = {}

_DB_CREDENTIALS = {
    'Administrador': 'mysql+pymysql://administrador:AdminPass2024!@127.0.0.1/fourovenpizzadb',
    'Ventas':        'mysql+pymysql://ventas:VentasPass2024!@127.0.0.1/fourovenpizzadb',
    'Cocinero':      'mysql+pymysql://cocina:CocineroPass2024!@127.0.0.1/fourovenpizzadb',
}

def init_role_switching(app, db):
    for rol, uri in _DB_CREDENTIALS.items():
        engine = create_engine(
            uri,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _engines[rol] = engine
        _session_factories[rol] = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False)
        )

    @app.before_request
    def set_session_by_role():
        if not has_request_context():
            return
        rol = flask_session.get('usuario_rol', 'Administrador')
        factory = _session_factories.get(rol, _session_factories['Administrador'])
        db.session = factory

    @app.teardown_request
    def remove_session(exc):
        rol = flask_session.get('usuario_rol', 'Administrador') if has_request_context() else 'Administrador'
        factory = _session_factories.get(rol)
        if factory:
            factory.remove()