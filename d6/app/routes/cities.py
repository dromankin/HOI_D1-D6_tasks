from flask import Blueprint, jsonify
from db import get_db
cities_bp = Blueprint("cities", __name__)

@cities_bp.route("/cities")
def cities():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT city
        FROM airports
        ORDER BY city
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([r[0] for r in rows])


@cities_bp.route("/cities/<city>/airports")
def airports_in_city(city):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT airport_code, airport_name
        FROM airports
        WHERE city = %s
    """, (city,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(rows)