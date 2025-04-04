from flask import Flask, render_template, jsonify, request
from geopy.geocoders import Nominatim
import folium
from folium import plugins
import googlemaps
import os
from dotenv import load_dotenv
from operator import itemgetter
import logging
import json
from datetime import datetime
import pytz
import math

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create required directories
DATA_DIR = 'data'
USER_DATA_DIR = os.path.join(DATA_DIR, 'user_data')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')

for directory in [DATA_DIR, USER_DATA_DIR, BACKUP_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

LOCATION_HISTORY_FILE = os.path.join(DATA_DIR, 'location_history.json')

app = Flask(__name__)

# Initialize Google Maps client
api_key = os.getenv('GOOGLE_MAPS_API_KEY')
if not api_key:
    logger.error("Google Maps API key not found in environment variables")
    raise ValueError("Missing Google Maps API key")

gmaps = googlemaps.Client(key=api_key)

def get_user_location_file(user_id):
    """Get location history file path for specific user"""
    return os.path.join(USER_DATA_DIR, f'location_history_{user_id}.json')

def get_backup_file(user_id):
    """Get backup file path for specific user"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(BACKUP_DIR, f'location_history_{user_id}_{timestamp}.json')

def save_location_history(location_data, user_id='default'):
    try:
        # Validate input data
        required_fields = ['lat', 'lon']
        for field in required_fields:
            if field not in location_data:
                logger.error(f"Missing required field: {field}")
                return False
            try:
                location_data[field] = float(location_data[field])
            except ValueError:
                logger.error(f"Invalid {field} value: {location_data[field]}")
                return False

        # Get user-specific location file
        location_file = get_user_location_file(user_id)
        
        # Load existing history
        history = []
        if os.path.exists(location_file):
            try:
                with open(location_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        logger.error("History file contains invalid data format")
                        history = []
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read history file: {str(e)}")
                history = []
        
        # Add timestamp and format in Thai timezone
        tz = pytz.timezone('Asia/Bangkok')
        current_time = datetime.now(tz)
        location_data['timestamp'] = current_time.isoformat()
        location_data['formatted_time'] = current_time.strftime("%d/%m/%Y %H:%M:%S")
        
        try:
            # Get address with timeout
            geolocator = Nominatim(user_agent="restaurant_finder_app")
            location = geolocator.reverse(
                f"{location_data['lat']}, {location_data['lon']}", 
                timeout=5,
                language='th'
            )
            location_data['address'] = location.address if location else None
        except Exception as e:
            logger.warning(f"Could not get address: {str(e)}")
            location_data['address'] = None
        
        # Check for duplicate locations
        if history:
            last_location = history[-1]
            time_diff = (current_time - datetime.fromisoformat(last_location['timestamp'])).total_seconds()
            
            if time_diff < 300:  # 5 minutes
                distance = calculate_distance(
                    last_location['lat'], last_location['lon'],
                    location_data['lat'], location_data['lon']
                )
                
                if distance < 10:  # 10 meters
                    logger.debug("Skipping duplicate location")
                    return True
        
        # Append new location
        history.append(location_data)
        
        # Keep only last 100 locations
        if len(history) > 100:
            # Create backup before truncating
            backup_file = get_backup_file(user_id)
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            
            history = history[-100:]
        
        # Save to file
        try:
            with open(location_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Location saved successfully for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving location data: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error in save_location_history: {str(e)}")
        return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@app.route('/')
def index():
    # Create a map centered at a default location (Bangkok)
    start_coords = (13.7563, 100.5018)
    folium_map = folium.Map(location=start_coords, 
                           zoom_start=15,
                           width='100%',
                           height='100%')
    
    # Add locate control
    plugins.LocateControl(auto_start=True).add_to(folium_map)
    
    # Convert map to HTML
    map_html = folium_map._repr_html_()
    return render_template('index.html', map=map_html)

@app.route('/save_location', methods=['POST'])
def save_location():
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'default')
        
        if not data or 'lat' not in data or 'lon' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing coordinates'
            })
        
        success = save_location_history(data, user_id)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': 'Location saved successfully' if success else 'Failed to save location'
        })
        
    except Exception as e:
        logger.error(f"Error in save_location: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_location_history')
def get_location_history():
    try:
        user_id = request.args.get('user_id', 'default')
        location_file = get_user_location_file(user_id)
        
        if os.path.exists(location_file):
            try:
                with open(location_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                return jsonify({
                    'status': 'success',
                    'history': history
                })
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in history file for user {user_id}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid history data'
                })
        return jsonify({
            'status': 'success',
            'history': []
        })
    except Exception as e:
        logger.error(f"Error getting location history: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_location')
def get_location():
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        if not lat or not lon:
            return jsonify({
                'status': 'error',
                'message': 'Missing coordinates'
            })
            
        geolocator = Nominatim(user_agent="my_web_app")
        location = geolocator.reverse(f"{lat}, {lon}")
        
        return jsonify({
            'status': 'success',
            'lat': float(lat),
            'lon': float(lon),
            'address': location.address if location else 'ไม่พบข้อมูลที่อยู่'
        })
    except Exception as e:
        logger.error(f"Error in get_location: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_nearby_restaurants')
def get_nearby_restaurants():
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        if not lat or not lon:
            logger.warning("Missing coordinates in get_nearby_restaurants request")
            return jsonify({
                'status': 'error',
                'message': 'กรุณาระบุตำแหน่งของคุณ'
            }), 400

        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            logger.error(f"Invalid coordinates: lat={lat}, lon={lon}")
            return jsonify({
                'status': 'error',
                'message': 'พิกัดไม่ถูกต้อง'
            }), 400

        logger.debug(f"Searching for restaurants near lat: {lat}, lon: {lon}")

        try:
            # Search for nearby restaurants
            places_result = gmaps.places_nearby(
                location=(lat, lon),
                radius=1000,  # 1km radius
                type='restaurant',
                language='th'
            )

            if not places_result.get('results'):
                logger.info(f"No restaurants found near lat: {lat}, lon: {lon}")
                return jsonify({
                    'status': 'success',
                    'message': 'ไม่พบร้านอาหารในบริเวณนี้',
                    'restaurants': []
                })

            # Process and sort restaurants
            restaurants = []
            for place in places_result.get('results', []):
                restaurant = {
                    'name': place.get('name', 'ไม่ระบุชื่อ'),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'vicinity': place.get('vicinity', 'ไม่ระบุที่อยู่'),
                    'lat': place['geometry']['location']['lat'],
                    'lng': place['geometry']['location']['lng']
                }
                restaurants.append(restaurant)

            # Sort by rating (highest first)
            restaurants.sort(key=lambda x: (x['rating'] or 0, x['user_ratings_total'] or 0), reverse=True)

            logger.debug(f"Successfully found {len(restaurants)} restaurants")
            return jsonify({
                'status': 'success',
                'restaurants': restaurants
            })

        except Exception as e:
            logger.error(f"Google Maps API error: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'เกิดข้อผิดพลาดในการค้นหาร้านอาหาร'
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error in get_nearby_restaurants: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดที่ไม่คาดคิด กรุณาลองใหม่อีกครั้ง'
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 