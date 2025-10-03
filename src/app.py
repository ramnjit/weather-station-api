import os
import uuid
import json
import boto3
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

# Initialize Flask App
app = Flask(__name__)

# DATABASE CONFIGURATION 
# Fetches credentials from AWS Secrets Manager
def get_db_credentials():
    secret_name = os.environ.get('DB_SECRET_ARN')
    # If running locally, you might want a fallback for testing
    if not secret_name:
        # Fallback to local credentials if DB_SECRET_ARN is not set
        return {
            "username": "postgres",
            "password": "password",
            "host": "localhost",
            "port": 5432,
            "dbname": "weather_db"
        }

    region_name = "us-east-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(get_secret_value_response['SecretString'])
        return secret
    except Exception as e:
        # Handle exceptions for when the secret isn't found, etc.
        raise e

# Fetch credentials and configure SQLAlchemy
db_creds = get_db_credentials()
DB_USERNAME = db_creds['username']
DB_PASSWORD = db_creds['password']
DB_HOST = db_creds['host']
DB_PORT = db_creds['port']
DB_NAME = db_creds.get('dbname', 'weather_db')

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

@app.route('/stations', methods=['POST'])
def create_station():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Station name is required"}), 400

    api_key_plain = os.urandom(24).hex()
    hashed_key = bcrypt.hashpw(api_key_plain.encode('utf-8'), bcrypt.gensalt())

    new_station = Station(
        name=data['name'],
        location_text=data.get('location_text'),
        api_key_hash=hashed_key.decode('utf-8')
    )
    try:
        db.session.add(new_station)
        db.session.commit()
        return jsonify({
            "message": "Station created successfully. Save your API key!",
            "station_id": new_station.station_id,
            "api_key": api_key_plain
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Could not create station", "details": str(e)}), 500
    finally:
        db.session.close()

@app.route('/readings', methods=['POST'])
def submit_reading():
    api_key = request.headers.get('x-api-key')
    if not api_key:
        return jsonify({"error": "API key is missing"}), 401

    data = request.get_json()
    if not data or not data.get('station_id') or data.get('temperature_celsius') is None:
        return jsonify({"error": "station_id and temperature_celsius are required"}), 400

    station = Station.query.get(data['station_id'])
    if not station:
        return jsonify({"error": "Station not found"}), 404

    if not bcrypt.checkpw(api_key.encode('utf-8'), station.api_key_hash.encode('utf-8')):
        return jsonify({"error": "Invalid API key"}), 401

    new_reading = Reading(
        station_id=station.station_id,
        temperature_celsius=data['temperature_celsius']
    )
    try:
        db.session.add(new_reading)
        db.session.commit()
        return jsonify({"message": "Reading submitted successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Could not save reading", "details": str(e)}), 500
    finally:
        db.session.close()

@app.route('/stations/<uuid:station_id>/readings', methods=['GET'])
def get_readings(station_id):
    station = Station.query.get(station_id)
    if not station:
        return jsonify({"error": "Station not found"}), 404

    readings = Reading.query.filter_by(station_id=station_id).order_by(Reading.timestamp.desc()).all()
    output = []
    for reading in readings:
        output.append({
            "reading_id": reading.reading_id,
            "temperature_celsius": float(reading.temperature_celsius),
            "timestamp": reading.timestamp.isoformat()
        })
    return jsonify(output)

@app.route('/stations/<uuid:station_id>/summary', methods=['GET'])
def get_summary(station_id):
    station = Station.query.get(station_id)
    if not station:
        return jsonify({"error": "Station not found"}), 404
        
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
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
        "station_id": str(station_id),
        "reading_count": summary_data[0],
        "average_temp_last_24h": round(float(summary_data[1]), 2) if summary_data[1] else 0,
        "max_temp_last_24h": float(summary_data[2]) if summary_data[2] else 0,
        "min_temp_last_24h": float(summary_data[3]) if summary_data[3] else 0
    })

if __name__ == '__main__':
    # For local dev only
    from dotenv import load_dotenv
    load_dotenv()
    app.run(debug=True)