from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, timezone
from db import get_db

routes_bp = Blueprint("routes", __name__)

MIN_CONNECTION_MINUTES = 40
MAX_CONNECTION_HOURS = 24

def _day_bounds_utc(d_str):
    d = datetime.strptime(d_str, "%Y-%m-%d").date()
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end

def _normalize_booking_class(booking_class):
    if not booking_class:
        return None
    val = booking_class.strip().lower()
    
    mapping = {"economy": "Economy", "comfort": "Comfort", "business": "Business"}
    return mapping.get(val, val.capitalize())

@routes_bp.route("/routes")
def routes():
    
    from_point = request.args.get("from")
    to_point = request.args.get("to")
    dep_date_str = request.args.get("date")
    conn_limit = request.args.get("connections", "0")
    b_class = _normalize_booking_class(request.args.get("bookingClass"))

    if not all([from_point, to_point, dep_date_str]):
        return jsonify({"error": "Missing params"}), 400

    day_start, day_end = _day_bounds_utc(dep_date_str)
    max_connections = 10 if conn_limit == "unbound" else int(conn_limit)

    params = {
        "day_start": day_start,
        "day_end": day_end,
        "max_connections": max_connections,
        "min_interval": timedelta(minutes=MIN_CONNECTION_MINUTES),
        "max_interval": timedelta(hours=MAX_CONNECTION_HOURS),
        "booking_class": b_class,
        "from_p": from_point,
        "to_p": to_point
    }

    
    
    start_cond = [
        "f.scheduled_departure >= %(day_start)s",
        "f.scheduled_departure < %(day_end)s",
        "f.scheduled_departure <@ r.validity",
        "f.status = 'Scheduled'"
    ]
    
    if len(from_point) == 3 and from_point.isupper():
        start_cond.append("r.departure_airport = %(from_p)s")
    else:
        start_cond.append("dep_airport.city->>'en' = %(from_p)s")

    if b_class:
        start_cond.append("""
            EXISTS (SELECT 1 FROM seats s 
            WHERE s.airplane_code = r.airplane_code AND s.fare_conditions = %(booking_class)s)
        """)

    conn_cond = [
        "f2.scheduled_departure >= i.scheduled_arrival + %(min_interval)s",
        "f2.scheduled_departure <= i.scheduled_arrival + %(max_interval)s",
        "NOT (arr_airport2.city->>'en' = ANY(i.path_cities))",
        "i.connections + 1 <= %(max_connections)s",
        "f2.scheduled_departure <@ r2.validity",
        "f2.status = 'Scheduled'"
    ]
    if b_class:
        conn_cond.append("""
            EXISTS (SELECT 1 FROM seats s 
            WHERE s.airplane_code = r2.airplane_code AND s.fare_conditions = %(booking_class)s)
        """)

    finish_cond = []
    if len(to_point) == 3 and to_point.isupper():
        finish_cond.append("arrival_airport = %(to_p)s")
    else:
        finish_cond.append("arrival_city = %(to_p)s")

    
    sql = f"""
    WITH RECURSIVE itins AS (
        SELECT
            f.flight_id,
            r.departure_airport,
            dep_airport.city->>'en' AS departure_city,
            f.scheduled_departure,
            r.arrival_airport,
            arr_airport.city->>'en' AS arrival_city,
            f.scheduled_arrival,
            0 AS connections,
            ARRAY[dep_airport.city->>'en', arr_airport.city->>'en']::text[] AS path_cities,
            ARRAY[r.departure_airport::text, r.arrival_airport::text]::text[] AS path_airports,
            ARRAY[f.flight_id::bigint]::bigint[] AS path_flights
        FROM flights f
        JOIN routes r ON r.route_no = f.route_no
        JOIN airports_data dep_airport ON dep_airport.airport_code = r.departure_airport
        JOIN airports_data arr_airport ON arr_airport.airport_code = r.arrival_airport
        WHERE {" AND ".join(start_cond)}

        UNION ALL

        SELECT
            f2.flight_id,
            i.departure_airport,
            i.departure_city,
            i.scheduled_departure,
            r2.arrival_airport,
            arr_airport2.city->>'en' AS arrival_city,
            f2.scheduled_arrival,
            i.connections + 1 AS connections,
            (i.path_cities || (arr_airport2.city->>'en'))::text[] AS path_cities,
            (i.path_airports || r2.arrival_airport::text)::text[] AS path_airports,
            (i.path_flights || f2.flight_id::bigint)::bigint[] AS path_flights
        FROM itins i
        JOIN routes r2 ON r2.departure_airport = i.arrival_airport
        JOIN flights f2 ON f2.route_no = r2.route_no
        JOIN airports_data arr_airport2 ON arr_airport2.airport_code = r2.arrival_airport
        WHERE {" AND ".join(conn_cond)}
    )
    SELECT connections, path_flights FROM itins
    WHERE {" AND ".join(finish_cond)}
    ORDER BY connections, path_flights;
    """

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()

    result = []
    for row in rows:
        connections_count = row[0]
        flight_ids = row[1]

        
        cur.execute("""
            SELECT * FROM (
                SELECT DISTINCT ON (f.flight_id)
                    f.flight_id, f.route_no, r.departure_airport, r.arrival_airport, 
                    f.scheduled_departure, f.scheduled_arrival
                FROM flights f
                JOIN routes r ON r.route_no = f.route_no
                WHERE f.flight_id = ANY(%s)
                  AND f.scheduled_departure <@ r.validity
                ORDER BY f.flight_id
            ) sub
            ORDER BY array_position(%s, sub.flight_id)
        """, (flight_ids, flight_ids))
        
        segments = [
            {
                "routeNo": s[1],
                "departureAirportCode": s[2],
                "arrivalAirportCode": s[3],
                "departureTime": s[4].isoformat(),
                "arrivalTime": s[5].isoformat(),
            } for s in cur.fetchall()
        ]

        result.append({
            "connectionsCount": connections_count,
            "segments": segments
        })

    cur.close()
    conn.close()
    return jsonify(result)