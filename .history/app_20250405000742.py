from flask import Flask, render_template, jsonify, request
from geopy.geocoders import Nominatim
import folium
from folium import plugins
import googlemaps
import os
from dotenv import load_dotenv
from operator import itemgetter

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

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

        # Search for nearby restaurants
        places_result = gmaps.places_nearby(
            location=(float(lat), float(lon)),
            radius=1000,  # 1km radius
            type='restaurant',
            language='th'
        )

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

        return jsonify({
            'status': 'success',
            'restaurants': restaurants[:10]  # Return top 10 restaurants
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True) 