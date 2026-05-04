from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from db import get_db
from sys import stderr
checkin_bp = Blueprint("checkin", __name__)

@checkin_bp.route("/check-in", methods=["POST"])
def do_check_in():
    data = request.get_json()
    ticket_no = data.get("ticket_no")

    if not ticket_no:
        return jsonify({"error": "ticket_no is required"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        
        cur.execute("""
            SELECT bp.flight_id, bp.seat_no, bp.boarding_no, bp.boarding_time
            FROM boarding_passes bp
            WHERE bp.ticket_no = %(ticket_no)s
            ORDER BY bp.flight_id
        """, {"ticket_no": ticket_no})
        
        existing = cur.fetchall()
        if existing:
            return jsonify([
                {
                    "flightId": r[0],
                    "seatNo": r[1],
                    "boardingNo": r[2],
                    "boardingTime": r[3].isoformat() if r[3] else None
                } for r in existing
            ])

        
        cur.execute("""
            SELECT s.flight_id, s.fare_conditions
            FROM segments s
            WHERE s.ticket_no = %(ticket_no)s
            ORDER BY s.flight_id
        """, {"ticket_no": ticket_no})
        
        seg_rows = cur.fetchall()
        if not seg_rows:
            return jsonify([]), 200

        results = []

        for seg in seg_rows:
            print("seg = ", seg, file=stderr)
            flight_id = seg[0]
            fare_conditions = seg[1]

            
            cur.execute("""
                SELECT f.scheduled_departure, r.airplane_code
                FROM flights f
                JOIN routes r ON r.route_no = f.route_no
                WHERE f.flight_id = %(flight_id)s
                  AND f.scheduled_departure <@ r.validity
                LIMIT 1
            """, {"flight_id": flight_id})
            
            flight_row = cur.fetchone()
            print("flight row = ", flight_row, file=stderr)
            if not flight_row:
                continue

            scheduled_departure = flight_row[0]
            airplane_code = flight_row[1]
            print("airplane code = ", airplane_code, file=stderr)
            
            cur.execute("""
                SELECT st.seat_no
                FROM seats st
                WHERE st.airplane_code = %(airplane_code)s
                  AND st.fare_conditions = %(fare_conditions)s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM boarding_passes bp
                      WHERE bp.flight_id = %(flight_id)s
                        AND bp.seat_no = st.seat_no
                  )
                ORDER BY st.seat_no
                LIMIT 1
            """, {
                "airplane_code": airplane_code,
                "fare_conditions": fare_conditions,
                "flight_id": flight_id
            })
            
            seat_row = cur.fetchone()
            print("seat row = ", seat_row, file=stderr)
            if not seat_row:
                
                continue

            seat_no = seat_row[0]
            
            boarding_time = scheduled_departure - timedelta(minutes=30)

            
            cur.execute("""
                SELECT coalesce(max(bp.boarding_no), 0) + 1
                FROM boarding_passes bp
                WHERE bp.flight_id = %(flight_id)s
            """, {"flight_id": flight_id})
            
            boarding_no = cur.fetchone()[0]

            
            cur.execute("""
                INSERT INTO boarding_passes (
                    ticket_no, flight_id, seat_no, boarding_no, boarding_time
                )
                VALUES (
                    %(ticket_no)s, %(flight_id)s, %(seat_no)s, %(boarding_no)s, %(boarding_time)s
                )
            """, {
                "ticket_no": ticket_no,
                "flight_id": flight_id,
                "seat_no": seat_no,
                "boarding_no": boarding_no,
                "boarding_time": boarding_time
            })

            results.append({
                "flightId": flight_id,
                "seatNo": seat_no,
                "boardingNo": boarding_no,
                "boardingTime": boarding_time.isoformat()
            })
        print("results = ", results, file=stderr)
        conn.commit()
        return jsonify(results), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()