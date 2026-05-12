import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
import time

# --- 1. AUTHENTICATION & SHEET CONNECTION ---
# This looks for the [gcp_service_account] section in your Streamlit Secrets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # EXACT name of your Google Sheet
    SHEET_NAME = "Varun’s Cinematic Buffet"
    spreadsheet = client.open(SHEET_NAME)
    sheet = spreadsheet.sheet1
except Exception as e:
    st.error("⚠️ Connection Error: Check your Streamlit Secrets or ensure you shared the Google Sheet with the bot's email.")
    st.stop()

# --- 2. API CONFIGURATION ---
TMDB_API_KEY = "1e08f4e7f84d8985db9da59d7d71e8e8"
OMDB_API_KEY = "28f7ec5e"

st.set_page_config(page_title="Varun's Buffet Pro", layout="wide")
st.title("🍽️ Varun’s Cinematic Buffet PRO")

# --- 3. NAVIGATION ---
menu = st.sidebar.radio("Navigation", ["Add to Watchlist", "Manage My Watchlist"])

# --- 4. PAGE: ADD TO WATCHLIST ---
if menu == "Add to Watchlist":
    query = st.text_input("Search for a Cinema or Web Series to add:")
    if query:
        search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}"
        try:
            results = requests.get(search_url).json().get('results', [])
            
            for item in results[:5]:
                m_type_raw = item.get('media_type', 'movie')
                if m_type_raw not in ['movie', 'tv']: continue
                
                m_id = item['id']
                # Localization
                display_type = "Web Series" if m_type_raw == "tv" else "Cinema"
                
                details = requests.get(f"https://api.themoviedb.org/3/{m_type_raw}/{m_id}?api_key={TMDB_API_KEY}").json()
                title = details.get('title') or details.get('name')
                year = details.get('release_date', details.get('first_air_date', '????'))[:4]
                genres = ", ".join([g['name'] for g in details.get('genres', [])])
                poster_url = f"https://image.tmdb.org/t/p/w500{details.get('poster_path', '')}"

                # IMDB Search
                imdb_rate = "N/A"
                try:
                    omdb_type = "series" if m_type_raw == "tv" else "movie"
                    o_res = requests.get(f"http://www.omdbapi.com/?t={title}&y={year}&type={omdb_type}&apikey={OMDB_API_KEY}").json()
                    imdb_rate = o_res.get('imdbRating', 'N/A')
                except: pass

                # Duration Logic
                total_mins = 0
                ep_count = details.get('number_of_episodes', 0) if m_type_raw == "tv" else 0
                if m_type_raw == "tv":
                    for s in details.get('seasons', []):
                        if s.get('season_number') == 0: continue
                        s_data = requests.get(f"https://api.themoviedb.org/3/tv/{m_id}/season/{s.get('season_number')}?api_key={TMDB_API_KEY}").json()
                        for ep in s_data.get('episodes', []): total_mins += ep.get('runtime', 0)
                else:
                    total_mins = details.get('runtime', 0)
                
                h, m = total_mins // 60, total_mins % 60
                dur_str = f"{h}h {m}m"
                if ep_count > 0: dur_str += f" ({ep_count} Episodes)"

                st.markdown("---")
                c1, c2, c3 = st.columns([1, 2, 1.5])
                with c1: st.image(poster_url)
                with c2:
                    st.subheader(f"{title} ({year})")
                    st.write(f"🎭 **Genre:** {genres}")
                    st.write(f"📺 **Type:** {display_type} | ⭐ **IMDB:** {imdb_rate}")
                    st.write(f"⏳ **Total:** {dur_str}")
                with c3:
                    trust = st.slider("Trust Rating (2-5):", 2.0, 5.0, 4.0, 0.5, key=f"t_{m_id}")
                    interest = st.select_slider("My Interest:", options=["Low", "Medium", "High"], value="High", key=f"i_{m_id}")
                    
                    if st.button("Add to Watchlist", key=f"b_{m_id}"):
                        w_map = {"High": 3, "Medium": 2, "Low": 1}
                        # Creating the row for Google Sheets
                        new_row = [title, year, display_type, genres, imdb_rate, dur_str, poster_url, trust, interest, w_map[interest], "Planned"]
                        sheet.append_row(new_row)
                        st.success(f"Added {title} to your Buffet!")
        except Exception as e:
            st.error(f"Search error: {e}")

# --- 5. PAGE: MANAGE WATCHLIST ---
elif menu == "Manage My Watchlist":
    st.header("🍴 Your Selected Buffet")
    
    # This reads EVERYTHING, including headers
    all_values = sheet.get_all_values()
    
    if len(all_values) <= 1:
        st.info("The Buffet is empty! Add something first.")
    else:
        # We manually set the headers to avoid 'get_all_records' being picky
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        
        # Sort logic
        if 'Interest Weight' in df.columns:
            df['Interest Weight'] = pd.to_numeric(df['Interest Weight'], errors='coerce')
            df['Trust Rating'] = pd.to_numeric(df['Trust Rating'], errors='coerce')
            df = df.sort_values(by=['Interest Weight', 'Trust Rating'], ascending=[False, False])
        
        # Display Grid
        n = 4 
        for i in range(0, len(df), n):
            cols = st.columns(n)
            chunk = df.iloc[i:i+n]
            for j, (idx, row) in enumerate(chunk.iterrows()):
                with cols[j]:
                    if row.get('Poster URL'): st.image(row['Poster URL'], use_column_width=True)
                    st.markdown(f"**{row.get('Name')}**")
                    
                    status = row.get('Status', 'Planned')
                    st.write(f"Status: {status}")
                    
                    # Row index in Google Sheets is (original dataframe index + 2)
                    # because Sheets start at 1 and we have a header row
                    row_num = int(idx) + 2
                    
                    if status == "Planned":
                        if st.button("Start Watching", key=f"sw_{idx}"):
                            sheet.update_cell(row_num, 11, "Watching")
                            st.rerun()
                    elif status == "Watching":
                        if st.button("Finish Meal", key=f"fin_{idx}"):
                            sheet.update_cell(row_num, 11, "Completed")
                            st.rerun()
                    st.write("---")
