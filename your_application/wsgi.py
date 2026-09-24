from asgiref.wsgi import WsgiToAsgi
from app.main import app

application = WsgiToAsgi(app)
