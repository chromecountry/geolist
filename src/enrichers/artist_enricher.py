import musicbrainzngs as mb
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import backoff
from threading import Lock
from tqdm import tqdm
from pathlib import Path
import json
from typing import Dict, Tuple

from credentials import MusicBrainz as MusicBrainzCredentials


class ArtistEnricher:
    """Handles enrichment of artist data from MusicBrainz."""

    RATE_LIMIT = 1  # seconds between API calls
    MAX_WORKERS = 8
    MAX_RETRIES = 3

    def __init__(self, cache_file: str = 'mb_cache.json'):
        self._initialize_stats()
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.stats_lock = Lock()
        self._setup_musicbrainz()

    def _initialize_stats(self) -> None:
        """Initialize statistics counters."""
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'no_data': 0,
            'no_area': 0,
            'no_country': 0,
            'no_city': 0,
            'errors': Counter()
        }

    def _setup_musicbrainz(self) -> None:
        """Setup MusicBrainz client with authentication."""
        mb.set_useragent("Geolist", "1.0")
        try:
            mb.auth(
                MusicBrainzCredentials.USERNAME,
                MusicBrainzCredentials.PASSWORD
            )
        except Exception as e:
            print(f"Error authenticating with MusicBrainz: {e}")

    def _load_cache(self) -> Dict:
        """Load existing cache or create new one."""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
        return {}

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def _update_location_stats(self, origin_data: Dict) -> None:
        """Update stats for missing location data."""
        with self.stats_lock:
            if not origin_data.get('city'):
                self.stats['no_city'] += 1
            if not origin_data.get('country'):
                self.stats['no_country'] += 1
            if not origin_data.get('area'):
                self.stats['no_area'] += 1

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=MAX_RETRIES
    )
    def _get_artist_location(self, artist_name: str) -> Dict:
        """Get artist location from cache or MusicBrainz API."""
        # Check cache first
        if artist_name in self.cache:
            with self.stats_lock:
                self.stats['from_cache'] = self.stats.get('from_cache', 0) + 1
            cached_data = self.cache[artist_name]
            self._update_location_stats(cached_data)
            return cached_data

        # Get from API
        time.sleep(self.RATE_LIMIT)
        result = mb.search_artists(artist=artist_name, limit=1)

        if not result['artist-list']:
            with self.stats_lock:
                self.stats['no_data'] += 1
            origin_data = {'status': 'not_found'}
            self.cache[artist_name] = origin_data
            self._save_cache()
            return origin_data

        artist_info = result['artist-list'][0]
        origin_data = self._extract_location_data(artist_info)
        self.cache[artist_name] = origin_data
        self._save_cache()

        return origin_data

    def _extract_location_data(self, artist_info: Dict) -> Dict:
        """Extract location data from artist info."""
        origin_data = {
            'city': artist_info.get('begin-area', {}).get('name'),
            'country': artist_info.get('country'),
            'area': artist_info.get('area', {}).get('name'),
            'status': 'success'
        }

        self._update_location_stats(origin_data)

        if any(origin_data.values()):
            with self.stats_lock:
                self.stats['success'] += 1
        else:
            with self.stats_lock:
                self.stats['no_data'] += 1
            origin_data['status'] = 'no_location_data'

        return origin_data

    def _process_artist(self, artist_tuple: Tuple[str, Dict]) -> Tuple[str, Dict]:
        """Process a single artist."""
        artist_name, artist_data = artist_tuple
        try:
            return artist_name, self._get_artist_location(artist_name)
        except Exception as e:
            with self.stats_lock:
                self.stats['failed'] += 1
                self.stats['errors'][str(e)] += 1
            return artist_name, {
                'status': 'error',
                'error': str(e)
            }

    def enrich_locations(self, library: Dict) -> Tuple[Dict, Dict]:
        """Enrich library with artist location data."""
        print("Enriching artist locations from MusicBrainz...")
        self.stats['total'] = len(library)
        enriched_library = library.copy()

        with tqdm(
            total=self.stats['total'],
            desc="Getting artist locations",
            colour='green',
            bar_format='{l_bar}{bar:30}{r_bar}'
        ) as pbar:
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                futures = [
                    executor.submit(self._process_artist, artist_tuple)
                    for artist_tuple in library.items()
                ]
                for future in futures:
                    artist_name, origin_data = future.result()
                    enriched_library[artist_name]['origin'] = origin_data
                    pbar.update(1)

        self._print_stats()
        return enriched_library, self.stats

    def _print_stats(self) -> None:
        """Print enrichment statistics."""
        print("\nLocation Enrichment Statistics:")
        print(f"Total artists: {self.stats['total']}")
        print(f"Successfully enriched: {self.stats['success']} "
              f"({(self.stats['success']/self.stats['total'])*100:.1f}%)")
        print(f"No data found: {self.stats['no_data']} "
              f"({(self.stats['no_data']/self.stats['total'])*100:.1f}%)")
        print(f"Missing city: {self.stats['no_city']} "
              f"({(self.stats['no_city']/self.stats['total'])*100:.1f}%)")
        print(f"Missing country: {self.stats['no_country']} "
              f"({(self.stats['no_country']/self.stats['total'])*100:.1f}%)")
        print(f"Missing area: {self.stats['no_area']} "
              f"({(self.stats['no_area']/self.stats['total'])*100:.1f}%)")
        print(f"Failed: {self.stats['failed']} "
              f"({(self.stats['failed']/self.stats['total'])*100:.1f}%)")

        if 'from_cache' in self.stats:
            print(f"Retrieved from cache: {self.stats['from_cache']} "
                  f"({(self.stats['from_cache']/self.stats['total'])*100:.1f}%)")

        if self.stats['errors']:
            print("\nCommon errors:")
            for error, count in self.stats['errors'].most_common(3):
                print(f"- {error}: {count} times")
