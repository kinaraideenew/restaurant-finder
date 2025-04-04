from flask import Flask, render_template, jsonify
from geopy.geocoders import Nominatim
import folium

app = Flask(__name__)

@app.route('/')
def index():
    # Create a map centered at a default location (Bangkok)
    start_coords = (13.7563, 100.5018)
    folium_map = folium.Map(location=start_coords, 
                           zoom_start=15,
                           width='100%',
                           height='100%')
    
    # Convert map to HTML
    map_html = folium_map._repr_html_()
    return render_template('index.html', map=map_html)

@app.route('/get_location')
def get_location():
    try:
        geolocator = Nominatim(user_agent="my_web_app")
        location = geolocator.geocode("Bangkok")
        return jsonify({
            'status': 'success',
            'lat': location.latitude,
            'lon': location.longitude,
            'address': location.address
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True) 