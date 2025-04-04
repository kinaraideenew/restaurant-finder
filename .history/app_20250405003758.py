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

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create data directory if not exists
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

LOCATION_HISTORY_FILE = os.path.join(DATA_DIR, 'location_history.json')

app = Flask(__name__)

# Initialize Google Maps client
api_key = os.getenv('GOOGLE_MAPS_API_KEY')
if not api_key:
    logger.error("Google Maps API key not found in environment variables")
    raise ValueError("Missing Google Maps API key")

gmaps = googlemaps.Client(key=api_key)

def save_location_history(location_data):
    try:
        # Load existing history
        history = []
        if os.path.exists(LOCATION_HISTORY_FILE):
            try:
                with open(LOCATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in history file, starting fresh")
                history = []
        
        # Add timestamp and address
        tz = pytz.timezone('Asia/Bangkok')
        location_data['timestamp'] = datetime.now(tz).isoformat()
        
        try:
            geolocator = Nominatim(user_agent="my_web_app")
            location = geolocator.reverse(f"{location_data['lat']}, {location_data['lon']}")
            location_data['address'] = location.address if location else None
        except Exception as e:
            logger.warning(f"Could not get address: {str(e)}")
            location_data['address'] = None
        
        # Append new location
        history.append(location_data)
        
        # Keep only last 100 locations
        if len(history) > 100:
            history = history[-100:]
        
        # Save back to file
        with open(LOCATION_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
        logger.debug(f"Location saved: {location_data}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving location history: {str(e)}")
        return False

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
        if not data or 'lat' not in data or 'lon' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing coordinates'
            })
        
        success = save_location_history(data)
        
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
        if os.path.exists(LOCATION_HISTORY_FILE):
            try:
                with open(LOCATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                return jsonify({
                    'status': 'success',
                    'history': history
                })
            except json.JSONDecodeError:
                logger.error("Invalid JSON in history file")
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
            return jsonify({
                'status': 'error',
                'message': 'Missing coordinates'
            })

        logger.debug(f"Searching for restaurants near lat: {lat}, lon: {lon}")

        # Search for nearby restaurants
        places_result = gmaps.places_nearby(
            location=(float(lat), float(lon)),
            radius=1000,  # 1km radius
            type='restaurant',
            language='th',
            rank_by='rating'  # Sort by rating
        )

        logger.debug(f"Found {len(places_result.get('results', []))} restaurants")

        # Process and sort restaurants by rating
        restaurants = []
        for place in places_result.get('results', []):
            if 'rating' in place:
                restaurant = {
                    'name': place.get('name', 'ไม่ระบุชื่อ'),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'vicinity': place.get('vicinity', 'ไม่ระบุที่อยู่'),
                    'lat': place['geometry']['location']['lat'],
                    'lng': place['geometry']['location']['lng'],
                    'place_id': place.get('place_id', '')
                }
                restaurants.append(restaurant)

        # Sort by rating (highest first)
        restaurants.sort(key=itemgetter('rating', 'user_ratings_total'), reverse=True)

        if not restaurants:
            logger.warning("No restaurants found in the area")
            return jsonify({
                'status': 'warning',
                'message': 'ไม่พบร้านอาหารในบริเวณนี้',
                'restaurants': []
            })

        return jsonify({
            'status': 'success',
            'restaurants': restaurants[:10]  # Return top 10 restaurants
        })

    except Exception as e:
        logger.error(f"Error in get_nearby_restaurants: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาด: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True) 