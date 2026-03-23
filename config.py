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

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI  = "mysql+pymysql://root:5522@127.0.0.1/fourovenpizzadb"
    SQLALCHEMY_TRACK_MODIFICATIONS = False