import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
from datetime import datetime

# --- 1. AUTH & CONNECTION ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
SHEET_NAME = "Varun’s Cinematic Buffet"
spreadsheet = client.open(SHEET_NAME)
sheet = spreadsheet.sheet1

# --- 2. CONFIG ---
TMDB_API_KEY = "1e08f4e7f84d8985db9da59d7d71e8e8"
OMDB_API_KEY = "28f7ec5e"

st.set_page_config(page_title="Varun's Buffet Pro", layout="wide")
st.title("🍽️ Varun’s Cinematic Buffet PRO")

# --- 3. SIDEBAR NAVIGATION ---
menu = st.sidebar.radio("Navigation", [
    "🔍 Add New Content", 
    "⏳ Yet to Watch", 
    "📺 Started Watching", 
    "✅ Completed Watching"
])

# Helper to check if title exists
def check_exists(title, existing_titles):
    return title.lower() in [t.lower() for t in existing_titles]

# Helper to update cell
def update_sheet(row_idx, col_idx, value):
    sheet.update_cell(row_idx, col_idx, value)
    st.rerun()

# --- 4. DATA LOADING ---
all_values = sheet.get_all_values()
headers = all_values[0]
data_rows = all_values[1:]
df_master = pd.DataFrame(data_rows, columns=headers)
existing_titles = df_master['Name'].tolist() if not df_master.empty else []

# --- 5. PAGE: ADD NEW CONTENT ---
if menu == "🔍 Add New Content":
    query = st.text_input("Search Cinema or Web Series:")
    if query:
        results = requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}").json().get('results', [])
        
        for item in results[:5]:
            m_type_raw = item.get('media_type', 'movie')
            if m_type_raw not in ['movie', 'tv']: continue
            
            # Metadata Fetching
            details = requests.get(f"https://api.themoviedb.org/3/{m_type_raw}/{item['id']}?api_key={TMDB_API_KEY}").json()
            title = details.get('title') or details.get('name')
            year = details.get('release_date', details.get('first_air_date', '????'))[:4]
            poster_url = f"https://image.tmdb.org/t/p/w500{details.get('poster_path', '')}"
            
            st.markdown("---")
            c1, c2, c3 = st.columns([1, 2, 1.5])
            with c1: st.image(poster_url, width=150)
            with c2:
                st.subheader(f"{title} ({year})")
                if check_exists(title, existing_titles):
                    st.error(f"⚠️ '{title}' is already in your Buffet!")
                    continue
            
            with c3:
                # Inputs for new entry
                t_val = st.slider("Trust:", 2.0, 5.0, 4.0, 0.5, key=f"t_{item['id']}")
                i_val = st.select_slider("Interest:", ["Low", "Medium", "High"], "High", key=f"i_{item['id']}")
                w_map = {"High": 3, "Medium": 2, "Low": 1}
                
                # Three Destination Buttons
                col_a, col_b, col_c = st.columns(3)
                if col_a.button("➕ Add", key=f"a_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", "Genre", "N/A", "Dur", poster_url, t_val, i_val, w_map[i_val], "Planned"])
                    st.success("Added to Watchlist!")
                    st.rerun()
                if col_b.button("📺 Watch", key=f"w_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", "Genre", "N/A", "Dur", poster_url, t_val, i_val, w_map[i_val], "Watching"])
                    st.success("Started Watching!")
                    st.rerun()
                if col_c.button("✅ Done", key=f"d_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", "Genre", "N/A", "Dur", poster_url, t_val, i_val, w_map[i_val], "Completed"])
                    st.success("Marked as Completed!")
                    st.rerun()
all these should apply to 
