# Geolist

***
***

## Preamble ##

This document makes the following assumptions:

- developers have a working knowledge of:
  - Spotify API
  - Geographic data visualization
  - API rate limiting and caching

- developers have a thorough knowledge of:
  - Python, Folium, Spotipy
  - MusicBrainz API
  - Web mapping concepts

## Introduction ##

Geolist is a geographic music visualization tool that:

1. retrieves and processes:
    1. User's Spotify library data
    1. Artist origin information from MusicBrainz

2. provides the following visualization features:
    1. Interactive world map
    1. Clustered artist markers
    1. Individual artist markers
    1. Custom tooltips

These functionalities are served by a single Python application. Computation logic
for these different components live within the `src/` directory.

## Configuration ##

### Environment Variables ###

### credentials.py ###

Create a credentials.py file with the following classes:

```python
class Spotipy:
    SPOTIPY_CLIENT_ID = "your_spotify_client_id"
    SPOTIPY_CLIENT_SECRET = "your_spotify_client_secret"
    SPOTIPY_REDIRECT_URI = "your_redirect_uri"
    SCOPE = "user-library-read"

class MusicBrainz:
    USERNAME = "your_musicbrainz_username"
    PASSWORD = "your_musicbrainz_password"
```

### Installation ###

Ensure Python 3.8 or greater is available in the environment. If using virtual
environments, ensure the correct one is active.

To install required packages:

```bash
pip install -r requirements.txt
```

## Workflow ##

### Execution ###

### Running the application ###

To run Geolist with default settings:

```bash
python geolist.py
```

### Command Line Options ###

```bash
# Run without using cache
python geolist.py --no-cache

# Specify input/output files
python geolist.py -i input.json -o output.json

# Enable verbose output
python geolist.py -v
```

### Output ###

The application generates:
- `artist_map.html`: Interactive map visualization
- Cache files for API responses
- Optional JSON output of processed library

### Sample Output Structure ###
```json
{
    "Artist Name": {
        "songs": {
            "spotify:track:id": {
                "name": "Song Name",
                "popularity": 65,
                "release_date": "2020",
                "id": "track_id"
            }
        },
        "artist_uri": "spotify:artist:id",
        "artist_id": "artist_id",
        "origin": {
            "city": "City Name",
            "country": "Country Name",
            "area": "Area Name",
            "status": "success"
        }
    }
}
```
