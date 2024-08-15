from quart import Blueprint

from .search import search_bp
from .chats import chats_bp
from .inbox import inbox_bp
from .posts import posts_bp
from .users import users_bp
from .auth import auth_bp
from .home import home_bp
from .me import me_bp

v0 = Blueprint("v0", __name__)

v0.register_blueprint(auth_bp)
v0.register_blueprint(me_bp)
v0.register_blueprint(home_bp)
v0.register_blueprint(inbox_bp)
v0.register_blueprint(posts_bp)
v0.register_blueprint(users_bp)
v0.register_blueprint(chats_bp)
v0.register_blueprint(search_bp)

