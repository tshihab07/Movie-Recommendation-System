import werkzeug
werkzeug.urls.url_quote = werkzeug.utils.escape
from flask import Flask, render_template, request, redirect, url_for, jsonify  # Updated import
import pandas as pd
import pickle
import requests
from datetime import datetime

# updated: 03-06-2025 12:41 AM
import re
from difflib import get_close_matches
from functools import lru_cache


# Flask application setup
app = Flask(__name__)

# Load data
data = pd.read_csv('model/movie_cleaned.csv')
similar = pickle.load(open('model/similarities.pkl', 'rb'))

# TMDB API Key
API_KEY = '5dd351fde2e8606b5b6e50a24d10e888'

################ HELPER FUNCTIONS ############
# Function to get movie poster from TMDB API
def get_poster(mov_id):
    response = requests.get(f'https://api.themoviedb.org/3/movie/{mov_id}?api_key={API_KEY}&language=en-US')
    data = response.json()
    return f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None


# Function to get movie details from TMDB API
def get_movie_details(mov_id):
    response = requests.get(f'https://api.themoviedb.org/3/movie/{mov_id}?api_key={API_KEY}&language=en-US')
    return response.json()


# Function to get movie recommendations based on title
def get_recommendations(movie_name):
    movie_idx = data[data['Title'] == movie_name].index[0]
    distances = similar[movie_idx]
    movie_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
    
    recommendations = []
    for i in movie_list:
        movie_id = data.iloc[i[0]].ID
        movie_title = data.iloc[i[0]].Title
        poster = get_poster(movie_id)
        recommendations.append({
            'title': movie_title,
            'poster': poster,
            'id': movie_id
        })
    return recommendations



############ SEARCH ENHANCEMENTS ############

@lru_cache(maxsize=5000)                                        # Cache normalized titles for performance
def normalize_search_text(text):
    """Converts all variants to searchable format"""
    if pd.isna(text): 
        return ""
    text = str(text).lower()
    text = re.sub(r"[-\s_]+", " ", text)                        # Replace hyphens/underscores with spaces
    text = re.sub(r"[^\w\s]", "", text)                         # Remove special characters
    return text.strip()


# Enhanced search function to provide suggestions and corrections
# This function will return exact matches, partial matches, and suggestions for misspelled titles
def get_search_suggestions(query):
    """ Enhanced search with 'Did You Mean' feature """
    # normalize the query for comparison
    norm_query = normalize_search_text(query)
    
    # find exact matches first
    # use both direct string match and normalized match
    direct_matches = data[
        (data['Title'].str.lower() == query.lower()) |
        (data['Title'].apply(normalize_search_text) == norm_query)
    ]
    
    # Find partial matches if no direct hits
    if len(direct_matches) == 0:
        partial_matches = data[
            data['Title'].str.lower().str.contains(query.lower()) |
            data['Title'].apply(normalize_search_text).str.contains(norm_query)
        ]
        
        # Fuzzy match suggestions if still no results
        if len(partial_matches) == 0:
            all_titles = data['Title'].apply(normalize_search_text).tolist()
            suggestions = get_close_matches(norm_query, all_titles, n=3, cutoff=0.6)
            return data[data['Title'].apply(normalize_search_text).isin(suggestions)]
        
        return partial_matches
    
    return direct_matches


# Enhanced search function to find related movies
def find_related_movies(query, exact_match_only=False):
    """
    Find movies with matching keywords in title
    Returns: (matches, suggestions, original_query)
    """
    normalized_query = normalize_search_text(query)
    
    # First try exact matches
    exact_matches = data[
        (data['Title'].str.lower() == query.lower()) |
        (data['Title'].apply(normalize_search_text) == normalized_query)
    ]
    
    if not exact_match_only and (exact_matches.empty or len(exact_matches) < 5):
        # Split query into keywords (ignore small words)
        keywords = [word for word in re.split(r'\W+', query.lower()) 
                  if len(word) > 2 and word not in ['the', 'and', 'of']]
        
        # Find movies containing all keywords
        keyword_matches = data
        for keyword in keywords:
            keyword_matches = keyword_matches[
                data['Title'].str.lower().str.contains(keyword)
            ]
        
        # Combine with exact matches
        matches = pd.concat([exact_matches, keyword_matches]).drop_duplicates()
    else:
        matches = exact_matches
    
    # Get spelling suggestions if needed
    suggestions = []
    if matches.empty:
        all_titles = data['Title'].apply(normalize_search_text).tolist()
        suggestions = get_close_matches(normalized_query, all_titles, n=3, cutoff=0.5)
    
    return matches, suggestions, query


# Flask routes for handling requests
@app.route('/')
def home():
    # Get latest 10 movies by release date
    latest_movies = data.sort_values('Release Date', ascending=False).head(10)
    latest_with_posters = []
    
    for _, row in latest_movies.iterrows():
        latest_with_posters.append({
            'title': row['Title'],
            'poster': get_poster(row['ID']),
            'id': row['ID'],
            'release_date': row['Release Date']
        })
    
    return render_template('index.html', latest_movies=latest_with_posters)


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    # Get movie details from TMDB API
    movie_data = get_movie_details(movie_id)
    
    # Get recommendations
    movie_title = data[data['ID'] == movie_id]['Title'].values[0]
    recommendations = get_recommendations(movie_title)
    
    return render_template('movie.html', 
                         movie=movie_data, 
                         recommendations=recommendations)


# Search suggestions endpoint
@app.route('/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').lower()
    if len(query) < 2:
        return jsonify([])
    
    matches = data[data['Title'].str.lower().str.contains(query)].head(5)
    results = []
    for _, row in matches.iterrows():
        results.append({
            'title': row['Title'],
            'id': row['ID'],
            'poster': get_poster(row['ID']) if pd.notnull(row['ID']) else None
        })
    return jsonify(results)


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    
    if not query:
        return redirect(url_for('home'))
    
    matches, suggestions, original_query = find_related_movies(query)
    
    # Prepare results
    results = []
    for _, row in matches.iterrows():
        results.append({
            'title': row['Title'],
            'id': row['ID'],
            'poster': get_poster(row['ID']),
            'release_date': row['Release Date']
        })
    
    return render_template('search_results.html',
                         query=original_query,
                         results=results,
                         suggestions=suggestions,
                         is_corrected=len(suggestions) > 0)


if __name__ == '__main__':
    app.run(debug=True)