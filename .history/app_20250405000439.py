from flask import Flask, render_template, jsonify, request
from geopy.geocoders import Nominatim
import folium
from folium import plugins

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True) 