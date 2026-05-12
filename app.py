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

# --- 6. DISPLAY LISTS ---
else:
    status_map = {"⏳ Yet to Watch": "Planned", "📺 Started Watching": "Watching", "✅ Completed Watching": "Completed"}
    target_status = status_map[menu]
    
    filtered_df = df_master[df_master['Status'] == target_status]
    
    if filtered_df.empty:
        st.info(f"No titles in {menu} yet.")
    else:
        # SORTING LOGIC
        if target_status == "Planned":
            filtered_df['Interest Weight'] = pd.to_numeric(filtered_df['Interest Weight'])
            filtered_df['Trust Rating'] = pd.to_numeric(filtered_df['Trust Rating'])
            filtered_df = filtered_df.sort_values(by=['Interest Weight', 'Trust Rating'], ascending=[False, False])
        else:
            # Show latest additions to these lists at the top (reverse original order)
            filtered_df = filtered_df.iloc[::-1]

        n = 4
        for i in range(0, len(filtered_df), n):
            cols = st.columns(n)
            chunk = filtered_df.iloc[i:i+n]
            for j, (idx, row) in enumerate(chunk.iterrows()):
                row_num = idx + 2 # GSheet index
                with cols[j]:
                    st.image(row['Poster URL'], width=180)
                    st.markdown(f"**{row['Name']}**")
                    st.caption(f"{row['Year']} | {row['Type']}")
                    st.write(f"⭐ IMDB: {row['IMDB Rating']} | ⏳ {row['Duration']}")
                    
                    # ACTIONS PER LIST
                    if target_status == "Planned":
                        col1, col2 = st.columns(2)
                        if col1.button("📺 Start", key=f"sw_{idx}"): update_sheet(row_num, 11, "Watching")
                        if col2.button("✅ Finish", key=f"fin_{idx}"): update_sheet(row_num, 11, "Completed")
                        
                        # EDIT METADATA
                        with st.expander("📝 Edit Info"):
                            new_trust = st.slider("Trust:", 2.0, 5.0, float(row['Trust Rating']), 0.5, key=f"ed_t_{idx}")
                            new_imdb = st.text_input("IMDB:", row['IMDB Rating'], key=f"ed_i_{idx}")
                            if st.button("Save Changes", key=f"save_{idx}"):
                                sheet.update_cell(row_num, 8, new_trust)
                                sheet.update_cell(row_num, 5, new_imdb)
                                st.rerun()

                    elif target_status == "Watching":
                        if st.button("✅ Mark Completed", key=f"cp_{idx}"): update_sheet(row_num, 11, "Completed")
                        with st.expander("📝 Edit Info"):
                            new_imdb = st.text_input("IMDB:", row['IMDB Rating'], key=f"ed_i_w_{idx}")
                            if st.button("Save", key=f"save_w_{idx}"):
                                sheet.update_cell(row_num, 5, new_imdb)
                                st.rerun()

                    st.write("---")
