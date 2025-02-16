#!/usr/bin/env python

"""
Geolist
"""

import backoff
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from spotipy.exceptions import SpotifyException
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from credentials import Spotipy as SpotipyCredentials
from tqdm import tqdm
import colorama

from src.builders.library_builder import SpotifyLibraryBuilder
from src.visualizers.map_visualizer import MapVisualizer

from pathlib import Path
PROJECT_ROOT = Path(__file__).absolute().parents[1]
import sys; sys.path.append(str(PROJECT_ROOT))  # noqa

colorama.init()


class Geolist:
    def __init__(self, *args, **kwargs):
        self.no_cache = kwargs.get('no_cache', False)
        self.verbose = kwargs.get('verbose', False)
        self.input_file = kwargs.get('input_file', None)
        self.output_file = kwargs.get('output_file', None)
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SpotipyCredentials.SPOTIPY_CLIENT_ID,
            client_secret=SpotipyCredentials.SPOTIPY_CLIENT_SECRET,
            redirect_uri=SpotipyCredentials.SPOTIPY_REDIRECT_URI,
            scope=SpotipyCredentials.SCOPE
        ))

        self.library_builder = SpotifyLibraryBuilder()
        self.map_visualizer = MapVisualizer()

    @backoff.on_exception(
        backoff.expo,
        SpotifyException,
        max_tries=5
    )
    def get_tracks(self, offset):
        return self.sp.current_user_saved_tracks(limit=20, offset=offset)

    def get_library(self):
        start_time = time.time()

        initial_response = self.sp.current_user_saved_tracks(limit=1)
        total_tracks = initial_response['total']
        offsets = range(0, total_tracks, 20)

        # Create progress bar
        pbar = tqdm(
            total=total_tracks,
            desc="Retrieving tracks",
            colour='green',
            bar_format='{l_bar}{bar:30}{r_bar}'
        )

        # Iterate through library 20 tracks at a time
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(self.get_tracks, offset) for offset in offsets
            ]
            for f in futures:
                result = f.result()
                results.append(result)
                pbar.update(len(result['items']))
        pbar.close()

        # Compile all results
        tracks = []
        for result in results:
            tracks.extend(result['items'])

        execution_time = time.time() - start_time
        print(f'Track Retrieval Execution time: {execution_time:.2f} seconds')
        print(f'Expected tracks: {total_tracks}')
        print(f'Retrieved tracks: {len(tracks)}')
        print(f'Match: {total_tracks == len(tracks)}')

        start_time = time.time()
        self.library = self.library_builder.build(tracks)
        execution_time = time.time() - start_time
        print(f'Library Cleanup Execution time: {execution_time:.2f} seconds')

    def run(self):
        """
        Implement the geolist's main functionality here
        """
        if self.no_cache:
            self.get_library()
        # TODO: Implement cache instead of loading from test file
        else:
            try:
                self.library = self.library_builder.load(self.input_file)
            except FileNotFoundError:
                print('No file found.'
                      + 'Please run with --no-cache or input an existing file')
                return 1

        if self.output_file:
            self.library_builder.save(self.output_file)

        # TODO: Clean up library assigment
        self.library = self.library_builder.enrich_artist_location()

        self.map_visualizer.create_map(self.library, 'artist_map.html')

        return 0


def main():
    description = 'Geolist'

    parser = ArgumentParser(description=description)
    parser.add_argument(
        '-n', '--no-cache', dest='no_cache', action='store_true', default=False
    )
    parser.add_argument(
        '-v', '--verbose', dest='verbose', action='store_true', default=False
    )
    parser.add_argument(
        '-i', '--input-file', dest='input_file', default=None
    )
    parser.add_argument(
        '-o', '--output-file', dest='output_file', default=None
    )

    args = parser.parse_args()
    no_cache = args.no_cache
    verbose = args.verbose
    input_file = args.input_file
    output_file = args.output_file

    geolist = Geolist(
        no_cache=no_cache,
        verbose=verbose,
        input_file=input_file,
        output_file=output_file
    )
    retval = geolist.run()

    return retval


if __name__ == '__main__':
    retval = main()
    sys.exit(retval)
