import random
import string
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from db import get_db

bookings_bp = Blueprint("bookings", __name__)


def gen_book_ref():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def gen_ticket_no():
    return '000543' + ''.join(random.choices(string.digits, k=7))

def _resolve_flight_ids(cur, segments_data):
    flight_ids = []
    for s in segments_data:
        cur.execute("""
            SELECT f.flight_id
            FROM flights f
            JOIN routes r ON r.route_no = f.route_no
            WHERE f.route_no = %(route_no)s
              AND r.departure_airport = %(dep)s
              AND r.arrival_airport = %(arr)s
              AND f.scheduled_departure = %(dep_time)s
            LIMIT 1
        """, {
            "route_no": s['routeNo'],
            "dep": s['departureAirportCode'],
            "arr": s['arrivalAirportCode'],
            "dep_time": s['departureTime']
        })
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Cannot resolve flight_id for segment: {s['routeNo']}")
        flight_ids.append(row[0])
    return flight_ids

@bookings_bp.route("/bookings", methods=["POST"])
def create_booking_route():
    data = request.get_json()
    passenger_id = data.get("passenger_id")
    passenger_name = data.get("passenger_name")
    segments_in = data.get("segments")
    fare_condition = data.get("fare_condition", "Economy")
    outbound = data.get("outbound", True)

    if not segments_in:
        return jsonify({"error": "segments must be non-empty"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        
        flight_ids = _resolve_flight_ids(cur, segments_in)

        
        for _ in range(50):
            book_ref = gen_book_ref()
            cur.execute("SELECT 1 FROM bookings WHERE book_ref = %s LIMIT 1", (book_ref,))
            if not cur.fetchone():
                break
        else:
            raise RuntimeError("Failed to generate unique book_ref")

        
        for _ in range(50):
            ticket_no = gen_ticket_no()
            cur.execute("SELECT 1 FROM tickets WHERE ticket_no = %s LIMIT 1", (ticket_no,))
            if not cur.fetchone():
                break
        else:
            raise RuntimeError("Failed to generate unique ticket_no")

        book_date = datetime.now(timezone.utc)

        
        cur.execute("""
            INSERT INTO bookings(book_ref, book_date, total_amount)
            SELECT
                %(book_ref)s,
                %(book_date)s,
                COALESCE(SUM(
                    CASE %(fare)s
                        WHEN 'Business' THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 100
                        WHEN 'Comfort'  THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 65
                        WHEN 'Economy'  THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 50
                    END
                ), 0)
            FROM flights f
            WHERE f.flight_id = ANY(%(flights)s)
        """, {
            "book_ref": book_ref,
            "book_date": book_date,
            "fare": fare_condition,
            "flights": flight_ids
        })

        
        cur.execute("""
            INSERT INTO tickets(ticket_no, book_ref, passenger_id, passenger_name, outbound)
            VALUES (%(ticket_no)s, %(book_ref)s, %(passenger_id)s, %(passenger_name)s, %(outbound)s)
        """, {
            "ticket_no": ticket_no,
            "book_ref": book_ref,
            "passenger_id": passenger_id,
            "passenger_name": passenger_name,
            "outbound": outbound
        })

        
        cur.execute("""
            INSERT INTO segments(ticket_no, flight_id, fare_conditions, price)
            SELECT
                %(ticket_no)s,
                f.flight_id,
                %(fare)s,
                CASE %(fare)s
                    WHEN 'Business' THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 100
                    WHEN 'Comfort'  THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 65
                    WHEN 'Economy'  THEN (EXTRACT(EPOCH FROM (f.scheduled_arrival - f.scheduled_departure)) / 60.0) * 50
                END
            FROM flights f
            WHERE f.flight_id = ANY(%(flights)s)
        """, {
            "ticket_no": ticket_no,
            "fare": fare_condition,
            "flights": flight_ids
        })

        conn.commit()
        return jsonify({"ticket_no": ticket_no, "book_ref": book_ref}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()