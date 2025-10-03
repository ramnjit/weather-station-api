import os
import uuid
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
import bcrypt
from datetime import datetime, timedelta
from sqlalchemy import func

# Initialize Flask App
app = Flask(__name__)

# DATABASE CONFIGURATION
# Replace with your local PostgreSQL credentials
DB_USERNAME = "postgres"
DB_PASSWORD = "password"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "weather_db"

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# DATABASE MODELS
class Station(db.Model):
    __tablename__ = 'stations'
    station_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    location_text = db.Column(db.String(255))
    api_key_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    readings = db.relationship('Reading', backref='station', lazy=True)

class Reading(db.Model):
    __tablename__ = 'readings'
    reading_id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(UUID(as_uuid=True), db.ForeignKey('stations.station_id'), nullable=False)
    temperature_celsius = db.Column(db.Numeric(5, 2), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

# API ROUTES
@app.route('/')
def index():
    return jsonify({"message": "Weather Station API is running!"})

# Endpoint to create a new station
@app.route('/stations', methods=['POST'])
def create_station():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Station name is required"}), 400

    # Generate a new, random API key
    api_key_plain = os.urandom(24).hex()

    # Hash the API key for secure storage
    hashed_key = bcrypt.hashpw(api_key_plain.encode('utf-8'), bcrypt.gensalt())

    new_station = Station(
        name=data['name'],
        location_text=data.get('location_text'),
        api_key_hash=hashed_key.decode('utf-8')
    )

    try:
        db.session.add(new_station)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Could not create station", "details": str(e)}), 500

    # Return the plaintext API key to the user ONCE
    return jsonify({
        "message": "Station created successfully. Save your API key!",
        "station_id": new_station.station_id,
        "api_key": api_key_plain
    }), 201

# Endpoint to submit a new reading from a station
@app.route('/readings', methods=['POST'])
def submit_reading():
    # Get the API key from the request headers
    api_key = request.headers.get('x-api-key')
    if not api_key:
        return jsonify({"error": "API key is missing"}), 401

    data = request.get_json()
    if not data or not data.get('station_id') or data.get('temperature_celsius') is None:
        return jsonify({"error": "station_id and temperature_celsius are required"}), 400

    # Find the station by its ID
    station = Station.query.get(data['station_id'])
    if not station:
        return jsonify({"error": "Station not found"}), 404

    # Check if the provided API key is correct
    if not bcrypt.checkpw(api_key.encode('utf-8'), station.api_key_hash.encode('utf-8')):
        return jsonify({"error": "Invalid API key"}), 401

    # If key is valid, create the new reading
    new_reading = Reading(
        station_id=station.station_id,
        temperature_celsius=data['temperature_celsius']
    )

    try:
        db.session.add(new_reading)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Could not save reading", "details": str(e)}), 500

    return jsonify({"message": "Reading submitted successfully"}), 201

# Endpoint to get all readings for a specific station
@app.route('/stations/<uuid:station_id>/readings', methods=['GET'])
def get_readings(station_id):
    station = Station.query.get(station_id)
    if not station:
        return jsonify({"error": "Station not found"}), 404

    readings = Reading.query.filter_by(station_id=station_id).order_by(Reading.timestamp.desc()).all()
    
    # Convert reading objects to a list of dictionaries
    output = []
    for reading in readings:
        output.append({
            "reading_id": reading.reading_id,
            "temperature_celsius": float(reading.temperature_celsius),
            "timestamp": reading.timestamp.isoformat()
        })

    return jsonify(output)

# Endpoint to get a data summary for a specific station
@app.route('/stations/<uuid:station_id>/summary', methods=['GET'])
def get_summary(station_id):
    station = Station.query.get(station_id)
    if not station:
        return jsonify({"error": "Station not found"}), 404
        
    # Calculate the time 24 hours ago
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

    # Query for aggregate data
    summary_data = db.session.query(
        func.count(Reading.reading_id),
        func.avg(Reading.temperature_celsius),
        func.max(Reading.temperature_celsius),
        func.min(Reading.temperature_celsius)
    ).filter(
        Reading.station_id == station_id,
        Reading.timestamp >= twenty_four_hours_ago
    ).first()

    if not summary_data or summary_data[0] == 0:
        return jsonify({"message": "No readings for this station in the last 24 hours."})

    return jsonify({
        "station_id": station_id,
        "reading_count": summary_data[0],
        "average_temp_last_24h": round(float(summary_data[1]), 2),
        "max_temp_last_24h": float(summary_data[2]),
        "min_temp_last_24h": float(summary_data[3])
    })

# MAIN
if __name__ == '__main__':
    app.run(debug=True)