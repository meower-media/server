from quart import Blueprint

from .search import search_bp
from .chats import chats_bp
from .inbox import inbox_bp
from .posts import posts_bp
from .auth import auth_bp
from .me import me_bp
from .emojis import emojis_bp
from .emails import emails_bp

v0 = Blueprint("v0", __name__)

v0.register_blueprint(auth_bp)
v0.register_blueprint(emails_bp)
v0.register_blueprint(me_bp)
v0.register_blueprint(inbox_bp)
v0.register_blueprint(posts_bp)
v0.register_blueprint(chats_bp)
v0.register_blueprint(search_bp)
v0.register_blueprint(emojis_bp)
