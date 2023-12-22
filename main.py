import spotipy, time, requests, re
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect, render_template
from bs4 import BeautifulSoup
from datetime import datetime
# Bug-to-fix: when logged in another account, it showed me my songs

UPCOMING_RELEASES = 'https://www.metacritic.com/browse/albums/release-date/coming-soon/date'
##TOKEN_INFO_PREFIX = 'token_info_'

# Initialize Flask application
app = Flask(__name__)

app.secret_key = '7491yrhjkwbf7023h'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Redirects users to Spotify's authorization page
@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

# Retrieves information after the user's authorization
@app.route('/redirect')
def redirect_page():
    session.clear()
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code)

    # Get the user's information and use it to create a new session
    ##spotify_user_info = get_spotify_user_info(token_info['access_token'])
    ##user_session_key = TOKEN_INFO_PREFIX + spotify_user_info['id']

    session["token_info"] = token_info
    return redirect(url_for('find_artists', external = True))

# Gets the user's token and gets information from their liked songs
@app.route('/findArtists')
def find_artists():
    try:
        token_info = get_token()
    except:
        print("User not logged in")
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Getting all liked songs
    liked_songs = []
    songs = sp.current_user_saved_tracks()
    liked_songs.extend(songs['items'])

    # Pagination! Spotify only allows us to get a limited amount of songs
    # Because of this, we have to request them until all are retrieved
    while songs['next']:
        songs = sp.next(songs)
        liked_songs.extend(songs['items'])

    # Retrieving all artists
    artists_map = {}
    for item in liked_songs:
        track = item['track']
        for artist in track['artists']:
            artist_name = artist['name']
            if artist_name not in artists_map:
                artists_map[artist_name] = 1
            else:
                artists_map[artist_name] += 1

    # Sorts the artists by how frequent their song appears in the user's liked songs
    sorted_artists = sorted(artists_map, key=lambda x: artists_map[x], reverse=True)
    
    upcoming = find_upcoming_releases(sorted_artists, artists_map)

    return render_template('upcoming_releases.html', upcoming=upcoming)


# Finds any upcoming releases from the list of artists
def find_upcoming_releases(artists, artists_map):
    url = UPCOMING_RELEASES
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers)
    upcoming = []
    date = None

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Finding the upcoming releases
        rows = soup.select('table.musicTable:nth-of-type(1) tr')
        for r in rows:
            if r.find('th', class_='head_type_1'):
                date = r.get_text(strip=True)
            else:
                artist = r.find('td', class_='artistName').get_text(strip=True)
                album = r.find('td', class_='albumTitle').get_text(strip=True)
                if date and artist in artists:
                    upcoming.append((date, artist, album, artists_map.get(artist)))

        # Finding the anticipated releases
        anticipated = []

        rows = soup.select('table.musicTable:nth-of-type(2) tr')
        for r in rows:
            artist = r.find('td', class_='artistName').get_text(strip=True)
            album = r.find('td', class_='albumTitle').get_text(strip=True)
            date = r.find('td', class_='dataComment').get_text(strip=True)
            if artist in artists:
                anticipated.append((date, artist, album, artists_map.get(artist)))

    return upcoming + organize_dates(anticipated)

# Organizes the dates. Dates may be in the format year, month-year, season-year, TBA
# The dates will be organized chronologically with the most to least prioritized as follows:
# month-year, season-year, year, TBA
def organize_dates(dates):
    # Months subject to change (not sure)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    seasons = ['Spring', 'Summer', 'Fall', 'Winter']
    tba = []
    year = []
    month_year = []
    season_year = []

    for date,artist,album,count in dates:
        info = (date, artist, album, count)
        if re.match(r'^\d{4}$', date):
            year.append(info)
        elif re.match(r'^\w{3} \d{4}$', date):
            month_year.append(info)
        elif re.match(r'^\w+ \d{4}$', date):
            season_year.append(info)
        else:
            tba.append(info)

    sorted_month_year = sorted(month_year, key=lambda x: datetime.strptime(x[0], '%b %Y'))
    sorted_season_year = sorted(season_year, key=lambda x: seasons.index(x[0].split()[0]))  
    sorted_year = sorted(year, key=lambda x: int(x[0]))  

    return sorted_month_year + sorted_season_year + sorted_year + tba


# Gets the access token
def get_token():
    token_info = session.get("token_info", {})

    if not (session.get('token_info', False)):
        redirect(url_for('login', external=False))

    # Checks if the token has expired
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60

    if is_expired:
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])
    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id = '2f852f4929ac43d380baf3732cc3175d',
        client_secret = 'e0b9173fcdb7452f84b66e210330335f',
        redirect_uri = url_for('redirect_page', _external=True),
        scope='user-library-read'
    )

def get_spotify_user_info(access_token):
    sp = spotipy.Spotify(auth=access_token)
        
app.run(debug=True)