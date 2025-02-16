from flask import (
    Blueprint, redirect, request, session, render_template, send_file
)
from spotipy.oauth2 import SpotifyOAuth
from src.geolist import Geolist
from credentials import Spotipy as SpotipyCredentials

from pathlib import Path
PROJECT_ROOT = Path(__file__).absolute().parents[1]
import sys; sys.path.append(str(PROJECT_ROOT))  # noqa

main = Blueprint('main', __name__)


@main.route('/')
def index():
    if not session.get('token_info'):
        return render_template('login.html')
    return redirect('/map')


@main.route('/login')
def login():
    sp_oauth = SpotifyOAuth(
        client_id=SpotipyCredentials.SPOTIPY_CLIENT_ID,
        client_secret=SpotipyCredentials.SPOTIPY_CLIENT_SECRET,
        redirect_uri='http://localhost:5000/callback',
        scope=SpotipyCredentials.SCOPE,
        cache_handler=None
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@main.route('/callback')
def callback():
    if 'error' in request.args:
        return f"Error: {request.args['error']}"
    if 'code' not in request.args:
        return 'No code provided'

    sp_oauth = SpotifyOAuth(
        client_id=SpotipyCredentials.SPOTIPY_CLIENT_ID,
        client_secret=SpotipyCredentials.SPOTIPY_CLIENT_SECRET,
        redirect_uri='http://localhost:5000/callback',
        scope=SpotipyCredentials.SCOPE
    )
    session['token_info'] = sp_oauth.get_access_token(request.args['code'])
    return redirect('/map')


@main.route('/map')
def map_page():
    if not session.get('token_info'):
        return redirect('/login')
    return render_template('loading.html')


@main.route('/generate')
def generate_map():
    if not session.get('token_info'):
        return redirect('/login')

    input_file = PROJECT_ROOT / 'data' / 'cache' / 'library_cache.json'
    output_file = PROJECT_ROOT / 'data' / 'output' / 'artist_map.html'

    geolist = Geolist(
        token_info=session['token_info'],
        input_file=str(input_file)
    )
    geolist.run()
    return send_file(str(output_file))


@main.route('/logout')
def logout():
    session.clear()
    return redirect('/')
