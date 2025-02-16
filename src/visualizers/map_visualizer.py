import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from tqdm import tqdm
from typing import Dict, Tuple
import json
import backoff
from collections import Counter

from pathlib import Path
PROJECT_ROOT = Path(__file__).absolute().parents[2]
import sys; sys.path.append(str(PROJECT_ROOT))  # noqa


class MapVisualizer:
    def __init__(self):
        self.geolocator = Nominatim(
            user_agent="Geolist shulalex1998@gmail.com",
            timeout=5
        )
        # Setup cache and output directories
        self.cache_dir = PROJECT_ROOT / 'data' / 'cache'
        self.output_dir = PROJECT_ROOT / 'data' / 'output'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.cache_dir / 'geocode_cache.json'
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

    def _initialize_map(self):
        """Initialize the base map with settings."""
        return folium.Map(
            location=[20, 0],
            zoom_start=2,
            world_copy_jump=False,
            no_wrap=True,
            min_lon=-180,
            max_lon=180,
            min_lat=-90,
            max_lat=90,
            max_bounds=True
        )

    def _load_assets(self, m):
        """Load and add CSS and JS assets to map."""
        # Load CSS
        css_path = PROJECT_ROOT / 'app' / 'static' / 'css' / 'tooltip.css'
        with open(css_path) as f:
            css = f"<style>{f.read()}</style>"
        m.get_root().html.add_child(folium.Element(css))

        # Load JavaScript
        js_path = PROJECT_ROOT / 'app' / 'static' / 'js' / 'map_bounds.js'
        with open(js_path) as f:
            script = f"<script>{f.read()}</script>"
        m.get_root().html.add_child(folium.Element(script))

    def _create_marker_groups(self, m):
        """Create and return cluster and individual marker groups."""
        cluster_group = MarkerCluster(
            name='Clustered View',
            options={
                'maxClusterRadius': 30,
                'disableClusteringAtZoom': 8,
                'spiderfyOnMaxZoom': True
            }
        ).add_to(m)

        individual_group = folium.FeatureGroup(
            name='Individual Points', show=False
        )
        return cluster_group, individual_group

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

            if not location and ',' in location_str:
                shorter_location = ','.join(
                    location_str.rsplit(',', 1)[0].split(',')
                )
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

    def _process_artist_locations(self, library):
        """Process and return artist locations."""
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
        return artist_locations

    def _add_markers(self, cluster_group, individual_group, artist_locations):
        """Add markers to both groups."""
        for coords, artists in artist_locations.items():
            base_lat, base_lng = coords
            for i, artist in enumerate(artists):
                offset = i * 0.0001
                adjusted_coords = (base_lat + offset, base_lng + offset)

                tooltip_html = f'<div class="custom-tooltip">{artist}</div>'

                # Add to cluster view
                self._create_marker(
                    adjusted_coords,
                    artist,
                    tooltip_html,
                    'red',
                    cluster_group
                )

                # Add to individual view
                self._create_marker(
                    adjusted_coords,
                    artist,
                    tooltip_html,
                    'blue',
                    individual_group
                )

    def _create_marker(self, coords, artist, tooltip_html, color, group):
        """Create and add a single marker to a group."""
        folium.CircleMarker(
            location=coords,
            radius=3,
            popup=folium.Popup(artist, max_width=200),
            tooltip=folium.Tooltip(
                tooltip_html,
                permanent=False,
                sticky=True
            ),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7
        ).add_to(group)

    def create_map(self, library: Dict):
        """Create an interactive map of artist locations."""
        output_path = self.output_dir / 'artist_map.html'
        # Initialize map
        m = self._initialize_map()

        # Load assets
        self._load_assets(m)

        # Create marker groups
        cluster_group, individual_group = self._create_marker_groups(m)

        # Process locations
        artist_locations = self._process_artist_locations(library)

        # Add markers
        self._add_markers(cluster_group, individual_group, artist_locations)

        # Add layer control
        individual_group.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)

        # Save map
        m.save(output_path)
        print(f"Map saved as {output_path}")
        self._print_stats()

    def _print_stats(self) -> None:
        """Print geocoding statistics."""
        print("\nGeocoding Statistics:")
        print(f"Total locations: {self.stats['total_locations']}")
        print(f"Successful geocodes: {self.stats['successful_geocodes']}")
        print(
            f"Successful retry geocodes: "
            f"{self.stats['successful_retry_geocodes']}"
        )
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
            if self.cache_file.exists():
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
