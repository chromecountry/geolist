from tqdm import tqdm
from src.util.utils import trim_year
import json

from src.enrichers.artist_enricher import ArtistEnricher


class SpotifyLibraryBuilder:
    """Handles organization and structuring of Spotify library data."""

    def __init__(self):
        self.library = {}

    def _get_artist_info(self, artist_data) -> dict:
        return {
            'songs': {},
            'artist_uri': artist_data['uri'],
            'artist_id': artist_data['id'],
            # 'artist_popularity' = self.sp.artist(
            #     self.library[artist]['artist_id'])['popularity']
        }

    def _get_song_info(self, track) -> dict:
        return {
            'name': track['name'],
            'popularity': track['popularity'],
            'release_date': trim_year(track['album']['release_date']),
            'id': track['id']
        }

    def build(self, tracks):
        pbar = tqdm(
            total=len(tracks),
            desc='Building library',
            colour='green',
            bar_format='{l_bar}{bar:30}{r_bar}'
        )

        for track_item in tracks:
            track = track_item['track']
            artist = track['artists'][0]['name']

            if artist not in self.library:
                self.library[artist] = self._get_artist_info(
                    track['artists'][0]
                )

            self.library[artist]['songs'][track['uri']] = (
                self._get_song_info(track)
            )
            pbar.update(1)

        pbar.close()
        return self.library

    def enrich_artist_location(self):
        """Enrich library with artist location data using MusicBrainz."""
        enricher = ArtistEnricher()
        self.library, _ = enricher.enrich_locations(self.library)
        return self.library

    def save(self, filename):
        """Save library to JSON file."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.library, f, indent=4, ensure_ascii=False)
            print(f'Library saved to {filename}')
        except Exception as e:
            print(f'Error saving library: {e}')

    def load(self, filename):
        """Load library from JSON file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.library = json.load(f)
            print(f'Library loaded from {filename}')
        except Exception as e:
            print(f'Error loading library: {e}')
