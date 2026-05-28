from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from dotenv import load_dotenv
import os

load_dotenv()
database_url = os.environ.get('DATABASE_URL', '')
if database_url.startswith('postgres://'):
    os.environ['DATABASE_URL'] = database_url.replace('postgres://', 'postgresql://', 1)

db            = SQLAlchemy()
login_manager = LoginManager()
migrate       = Migrate()
mail          = Mail()

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY']                     = os.environ.get('SECRET_KEY', 'dev-key')
    app.config['SQLALCHEMY_DATABASE_URI']        = os.environ.get('DATABASE_URL', 'sqlite:///dpp.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS']      = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'pool_size': 5,
        'max_overflow': 2,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    }
    app.config['UPLOAD_FOLDER']                  = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH']             = 500 * 1024 * 1024
    app.config['MAIL_SERVER']                    = os.environ.get('MAIL_SERVER')
    app.config['MAIL_PORT']                      = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']                   = True
    app.config['MAIL_USERNAME']                  = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD']                  = os.environ.get('MAIL_PASSWORD')

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view     = 'auth.login'
    login_manager.login_message  = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    from app.auth.routes      import auth
    from app.users.routes     import users
    from app.recordings.routes import recordings
    from app.transcripts.routes import transcripts

    app.register_blueprint(auth)
    app.register_blueprint(users)
    app.register_blueprint(recordings)
    app.register_blueprint(transcripts)

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))