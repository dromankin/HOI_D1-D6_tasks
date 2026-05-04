from flask import Flask
from routes.index import index_bp
from routes.cities import cities_bp
from routes.airports import airports_bp
from routes.checkin import checkin_bp
from routes.bookings import bookings_bp
from routes.routes import routes_bp

app = Flask(__name__)


app.register_blueprint(index_bp)
app.register_blueprint(cities_bp)
app.register_blueprint(airports_bp)
app.register_blueprint(checkin_bp)
app.register_blueprint(bookings_bp)
app.register_blueprint(routes_bp)
if __name__ == "__main__":
    
    app.run(host="0.0.0.0", port=3000, debug=True)