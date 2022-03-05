from flask import Flask # noqa: F401
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from flask_cors import CORS
from arm.config.config import cfg
# import omdb

from flask_login import LoginManager


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "send_wildcard": "False"}})

# why is it needed??
# login_manager = LoginManager()
# login_manager.init_app(app)

db = SQLAlchemy()


def configure_app():
    if cfg.get("DB_URL"):
        app.config['SQLALCHEMY_DATABASE_URI'] = cfg.get("DB_URL")
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + cfg['DBFILE']        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # We should really gen a key for each system
    app.config['SECRET_KEY'] = "Big secret key"
    # not seen any reference of it
    app.config['LOGIN_DISABLED'] = cfg.get('DISABLE_LOGIN', False)
    if cfg.get('SQLALCHEMY_ENGINE_OPTIONS'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = cfg.get('SQLALCHEMY_ENGINE_OPTIONS')
    db.init_app(app)
    app.app_context().push()
    db.create_all()
    migrate = Migrate(app, db)


# import arm.ui.routes  # noqa: E402,F401
# import models.models  # noqa: E402
# import ui.config  # noqa: E402
# import ui.utils  # noqa: E402,F401
