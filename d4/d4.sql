SELECT DISTINCT
    r.route_no,
    s.fare_conditions,
    r.duration,
    (pr.base_price * EXTRACT(EPOCH FROM r.duration) / 60)::numeric(10,2) as calculated_price,
    s.price as actual_price
FROM routes r
JOIN flights f ON r.route_no = f.route_no 
              AND r.validity @> f.scheduled_departure
JOIN segments s ON f.flight_id = s.flight_id
JOIN pricing_rules pr ON s.fare_conditions = pr.fare_conditions
		AND r.route_no = pr.route_no
WHERE f.status = 'Arrived'
ORDER BY r.route_no, s.fare_conditions, r.duration 
LIMIT 100;
