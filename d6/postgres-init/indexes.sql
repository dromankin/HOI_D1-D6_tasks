CREATE INDEX idx_airports_city ON airports_data(city);
CREATE INDEX idx_routes_departure_airport ON routes(departure_airport);
CREATE INDEX idx_routes_arrival_airport ON routes(arrival_airport);
CREATE INDEX idx_flights_departure_time ON flights(scheduled_departure);
CREATE INDEX idx_voarding_passes_flight_id ON boarding_passes(flight_id);
CREATE INDEX idx_boarding_passes_ticket ON boarding_passes(ticket_no);