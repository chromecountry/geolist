import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from tqdm import tqdm
from typing import Dict, Tuple
from pathlib import Path
import json
import backoff
from collections import Counter


class MapVisualizer:
    def __init__(self, cache_file: str = 'geocode_cache.json'):
        self.geolocator = Nominatim(user_agent="Geolist shulalex1998@gmail.com", timeout=5)
        self.cache_file = cache_file
        self.location_cache = self._load_cache()
        self._initialize_stats()

    def _initialize_stats(self) -> None:
        self.stats = {
            'total_locations': 0,
            'successful_geocodes': 0,
            'successful_retry_geocodes': 0,
            'failed_geocodes': 0,
            'from_cache': 0,
            'empty_locations': 0,
            'errors': Counter()
        }

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
            self.stats['from_cache'] += 1
            return tuple(self.location_cache[location_str])

        try:
            time.sleep(1)  # Respect rate limits
            location = self.geolocator.geocode(location_str)

            # If first attempt fails, try with shorter location string
            if not location and ',' in location_str:
                shorter_location = ','.join(location_str.rsplit(',', 1)[0].split(','))
                time.sleep(1)
                location = self.geolocator.geocode(shorter_location)
                if location:
                    self.stats['successful_retry_geocodes'] += 1

            if location:
                coords = (location.latitude, location.longitude)
                self.location_cache[location_str] = coords
                self._save_cache()
                self.stats['successful_geocodes'] += 1
                return coords
            self.stats['failed_geocodes'] += 1
        except Exception as e:
            self.stats['failed_geocodes'] += 1
            self.stats['errors'][str(e)] += 1
            print(f"Error geocoding location: {location_str}: {e}")
        return None

    def create_map(self, library: Dict, output_file: str = 'artist_map.html'):
        """Create an interactive map of artist locations."""
        # Initialize map centered on world
        m = folium.Map(location=[20, 0], zoom_start=2)
        cluster = MarkerCluster().add_to(m)

        # Process each artist
        artist_locations = {}
        self.stats['total_locations'] = len(library)
        
        print("Processing artist locations...")
        for artist, data in tqdm(list(library.items())):
            if 'origin' in data and data['origin'].get('status') == 'success':
                location_str = self._get_location_string(data['origin'])
                if location_str:
                    coords = self._geocode_location(location_str)
                    if coords:
                        if coords not in artist_locations:
                            artist_locations[coords] = []
                        artist_locations[coords].append(artist)
                else:
                    self.stats['empty_locations'] += 1

        # Add markers to map
        for coords, artists in artist_locations.items():
            base_lat, base_lng = coords
            for i, artist in enumerate(artists):
                # Add tiny offset to overlapping points
                offset = i * 0.0001  # Small offset ~10m
                adjusted_coords = (base_lat + offset, base_lng + offset)
                
                popup_html = f"<div><h4>{artist}</h4></div>"
                
                folium.Marker(
                    location=adjusted_coords,
                    popup=folium.Popup(popup_html, max_width=200),
                ).add_to(cluster)

        # Save map
        m.save(output_file)
        print(f"Map saved as {output_file}")
        self._print_stats()


    def _print_stats(self) -> None:
        """Print geocoding statistics."""
        print("\nGeocoding Statistics:")
        print(f"Total locations: {self.stats['total_locations']}")
        print(f"Successful geocodes: {self.stats['successful_geocodes']}")
        print(f"Successful retry geocodes: {self.stats['successful_retry_geocodes']}")
        print(f"Failed geocodes: {self.stats['failed_geocodes']}")
        print(f"From cache: {self.stats['from_cache']}")
        print(f"Empty locations: {self.stats['empty_locations']}")

        if self.stats['errors']:
            print("\nCommon errors:")
            for error, count in self.stats['errors'].most_common(3):
                print(f"- {error}: {count} times")

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
