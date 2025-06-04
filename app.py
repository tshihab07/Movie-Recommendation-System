import werkzeug
werkzeug.urls.url_quote = werkzeug.utils.escape
from flask import Flask, render_template, request, redirect, url_for, jsonify
import pandas as pd
import pickle
import requests
import re
from difflib import get_close_matches
from functools import lru_cache


# Flask application setup
app = Flask(__name__)

# load data
data = pd.read_csv('model/movie_cleaned.csv')
similar = pickle.load(open('model/similarities.pkl', 'rb'))

# TMDB API Key
API_KEY = '5dd351fde2e8606b5b6e50a24d10e888'



################ HELPER FUNCTIONS ################

# function to retrieve the poster URL for a given movie ID
def get_poster(mov_id):
    response = requests.get(f'https://api.themoviedb.org/3/movie/{mov_id}?api_key={API_KEY}&language=en-US')
    data = response.json()
    return f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get('poster_path') else None


# function to get movie details from TMDB
def get_movie_details(mov_id):
    response = requests.get(f'https://api.themoviedb.org/3/movie/{mov_id}?api_key={API_KEY}&language=en-US')
    return response.json()


# function to retrieve similar movies based on the title
# it uses precomputed similarities to find the closest matches
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



################ SEARCH ENHANCEMENT ################

# function to normalizes text for better search matching
@lru_cache(maxsize=5000)  # Cache for performance
def normalize_search_text(text):
    """Converts all variants to searchable format"""
    if pd.isna(text): 
        return ""
    text = str(text).lower()
    text = re.sub(r"[-\s_]+", " ", text)  # Replace hyphens/underscores with spaces
    text = re.sub(r"[^\w\s]", "", text)   # Remove special characters
    return text.strip()


# function to find related movies with enhanced search which combines exact matches, keyword matching, and suggestions
def find_related_movies(query):
    """
    Enhanced version with:
    - Better spelling correction
    - Complete keyword matching
    - Clear suggestion handling
    """
    original_query = query.strip()
    normalized_query = normalize_search_text(original_query)
    
    # exact matches
    exact_matches = data[
        (data['Title'].str.lower() == original_query.lower()) |
        (data['Title'].apply(normalize_search_text) == normalized_query)
    ]
    
    # extract keywords from the query
    # splits the query into keywords for better matching
    keywords = [word for word in re.split(r'\W+', original_query.lower()) 
              if len(word) > 2 and word not in ['the', 'and', 'of']]
    
    
    # find movies that match any of the keywords
    # filters the dataset for movies that contain any of the keywords in their titles
    keyword_matches = data.copy()
    for keyword in keywords:
        keyword_matches = keyword_matches[
            keyword_matches['Title'].str.lower().str.contains(keyword)
        ]
    
    # combined matches
    # combines exact matches and keyword matches, ensuring no duplicates
    all_matches = pd.concat([exact_matches, keyword_matches]).drop_duplicates()
    
    # get spelling suggestions if too few matches
    # checks if the number of matches is less than 3, indicating a possible typo
    suggestions = []
    if len(all_matches) < 2:
        all_titles = data['Title'].apply(normalize_search_text).tolist()
        suggestions = get_close_matches(normalized_query, all_titles, n=3, cutoff=0.5)
        
        # use the best suggestion to find more movies
        if suggestions:
            suggested_matches, _, _ = find_related_movies(suggestions[0])
            all_matches = pd.concat([all_matches, suggested_matches]).drop_duplicates()
    
    return all_matches, suggestions, original_query



################ APPLICATION ROUTES ################

# main route to serves the home page with the latest movies and their posters
@app.route('/')
def home():
    # get latest 10 movies by release date
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
    # get movie details from TMDB API
    movie_data = get_movie_details(movie_id)
    
    # Get recommendations
    movie_title = data[data['ID'] == movie_id]['Title'].values[0]
    recommendations = get_recommendations(movie_title)
    
    return render_template('movie.html', movie=movie_data, recommendations=recommendations)


@app.route('/search', methods=['GET'])
def search():
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return redirect(url_for('home'))
        
        matches, suggestions, original_query = find_related_movies(query)
        
        # Prepare results
        results = []
        for _, row in matches.iterrows():
            poster = get_poster(row['ID']) if pd.notnull(row['ID']) else None
            if poster:
                results.append({
                    'title': row['Title'],
                    'id': row['ID'],
                    'poster': poster,
                    'release_date': row['Release Date']
                })
        
        return render_template('query_correction.html',
                            query=original_query,
                            results=results,
                            suggestions=suggestions,
                            is_corrected=len(suggestions) > 0,
                            has_results=len(results) > 0)
    
    except Exception as e:
        print(f"Search error: {e}")
        return render_template('query_correction.html', query=request.args.get('q', ''), results=[], suggestions=[], has_results=False)


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


if __name__ == '__main__':
    app.run(debug=True)
