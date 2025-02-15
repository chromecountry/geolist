import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from tqdm import tqdm
from typing import Dict, Tuple
from pathlib import Path
import json
import backoff


class MapVisualizer:
    def __init__(self, cache_file: str = 'geocode_cache.json'):
        self.geolocator = Nominatim(user_agent="Geolist", timeout=5)
        self.cache_file = cache_file
        self.location_cache = self._load_cache()

    def _get_location_string(self, artist_data: Dict) -> str:
        """Construct location string from artist data."""
        location_parts = []
        if artist_data.get('city'):
            location_parts.append(artist_data['city'])
        if artist_data.get('area'):
            location_parts.append(artist_data['area'])
        if artist_data.get('country'):
            location_parts.append(artist_data['country'])

        return ", ".join(location_parts)

    @backoff.on_exception(
        backoff.expo,
        (GeocoderTimedOut, GeocoderServiceError),
        max_tries=3
    )
    def _geocode_location(self, location_str: str) -> Tuple[float, float]:
        """Get coordinates for a location string."""
        if location_str in self.location_cache:
            return tuple(self.location_cache[location_str])

        try:
            time.sleep(1)  # Respect rate limits
            location = self.geolocator.geocode(location_str)
            if location:
                coords = (location.latitude, location.longitude)
                self.location_cache[location_str] = coords
                self._save_cache()
                return coords
        except Exception as e:
            print(f"Error geocoding location: {location_str}: {e}")
        return None

    def create_map(self, library: Dict, output_file: str = 'artist_map.html'):
        """Create an interactive map of artist locations."""
        # Initialize map centered on world
        m = folium.Map(location=[20, 0], zoom_start=2)

        # Process each artist
        artist_locations = {}
        print("Processing artist locations...")

        for artist, data in tqdm(library.items()):
            if 'origin' in data and data['origin'].get('status') == 'success':
                location_str = self._get_location_string(data['origin'])
                if location_str:
                    coords = self._geocode_location(location_str)
                    if coords:
                        if coords not in artist_locations:
                            artist_locations[coords] = []
                        artist_locations[coords].append(artist)

        # Add markers to map
        for coords, artists in artist_locations.items():
            # Size marker based on number of artists
            radius = 5 + (len(artists) * 2)

            folium.CircleMarker(
                location=coords,
                radius=radius,
                popup=f"Artists: {', '.join(artists)}",
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

        # Save map
        m.save(output_file)
        print(f"Map saved as {output_file}")

    def _load_cache(self) -> Dict:
        """Load geocoding cache."""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
        return {}

    def _save_cache(self) -> None:
        """Save geocoding cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.location_cache, f)
        except Exception as e:
            print(f"Error saving cache: {e}")
