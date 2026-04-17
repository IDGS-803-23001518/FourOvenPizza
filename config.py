class Config(object):
    SECRET_KEY = "ClaveSecreta"
    SESSION_COOKIE_SECURE  = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    MAIL_SERVER   = 'smtp.gmail.com'
    MAIL_PORT     = 587
    MAIL_USE_TLS  = True
    MAIL_USERNAME = 'fourovenpizzas@gmail.com'
    MAIL_PASSWORD = 'jzxj dcnv ncqy notp'
    MAIL_DEFAULT_SENDER = 'fourovenpizzas@gmail.com'

    DB_HOST = '127.0.0.1'
    DB_NAME = 'fourovenpizzadb'

    DB_URIS = {
        'Administrador': 'mysql+pymysql://administrador:AdminPass2024!@127.0.0.1/fourovenpizzadb',
        'Ventas':        'mysql+pymysql://ventas:VentasPass2024!@127.0.0.1/fourovenpizzadb',
        'Cocinero':      'mysql+pymysql://cocina:CocineroPass2024!@127.0.0.1/fourovenpizzadb',
    }
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://administrador:AdminPass2024!@127.0.0.1/fourovenpizzadb'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True