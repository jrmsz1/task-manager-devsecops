import logging
import logging.handlers
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt


def _setup_logging(app_name: str = "task-manager") -> logging.Logger:
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        f"%(asctime)s {app_name} %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Syslog: só tenta se o socket existir (não existe em Docker/WSL2)
    syslog_path = "/dev/log"
    if os.path.exists(syslog_path):
        sh = logging.handlers.SysLogHandler(address=syslog_path)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    # stdout — sempre ativo, capturado pelo Docker
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


logger = _setup_logging()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-insecure-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'danger'

bcrypt = Bcrypt(app)

logger.info("app_start env=%s", os.environ.get('FLASK_ENV', 'development'))

from todo_project import routes  # noqa: E402, F401
