from flask import Blueprint, jsonify
from db import get_db
airports_bp = Blueprint("airports", __name__)

@airports_bp.route("/airports")
def airports():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT airport_code, airport_name, city
        FROM airports
        ORDER BY city
    """)

    rows = cur.fetchall()
    result = [
        {"airport_code": r[0], "airport_name": r[1], "city": r[2]} 
        for r in rows
    ]
    cur.close()
    conn.close()

    return jsonify(result)


@airports_bp.route("/airports/<code>/inbound")
def inbound(code):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        WITH params AS (
    SELECT (SELECT MAX(actual_departure) FROM flights) AS now_ts
)
select r.route_no,
       r.days_of_week,
       r.scheduled_time::text,
       origin.airport_code as origin_airport,
       origin.airport_name->>'en' as origin_name,
       origin.city->>'en' as origin_city,
       origin.country->>'en' as origin_country
from routes r
    inner join airports_data origin on r.departure_airport = origin.airport_code
where (select now_ts from params) <@ r.validity
  and r.arrival_airport = %s
order by r.route_no;
    """, (code,))

    rows = cur.fetchall()
    result = [
        {
            "route_no": r[0], "days_of_week": r[1], "scheduled_time": r[2],
            "origin_airport": r[3], "origin_name": r[4], "origin_city": r[5], "origin_country": r[6]
        } for r in rows
    ]
    cur.close()
    conn.close()

    return jsonify(result)


@airports_bp.route("/airports/<code>/outbound")
def outbound(code):
    conn = get_db()
    cur = conn.cursor()
    #print(code, file=stderr)
    cur.execute("""
WITH params AS (
    SELECT (SELECT MAX(actual_departure) FROM flights) AS now_ts
)
select r.route_no,
       r.days_of_week,
       r.scheduled_time::text,
       destination.airport_code as destination_airport,
       destination.airport_name->>'en' as destination_name,
       destination.city->>'en' as destination_city,
       destination.country->>'en' as destination_country
from routes r
    inner join airports_data destination on r.arrival_airport = destination.airport_code
where (select now_ts from params) <@ r.validity
  and r.departure_airport = %s
order by r.route_no;
""", (code,))


    rows = cur.fetchall()
    result = [
        {
            "route_no": r[0], "days_of_week": r[1], "scheduled_time": r[2],
            "origin_airport": r[3], "origin_name": r[4], "origin_city": r[5], "origin_country": r[6]
        } for r in rows
    ]
    cur.close()
    conn.close()

    return jsonify(result)