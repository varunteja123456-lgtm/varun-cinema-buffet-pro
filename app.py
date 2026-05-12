import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd

# --- 1. AUTH & CONNECTION ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
SHEET_NAME = "Varun’s Cinematic Buffet"
spreadsheet = client.open(SHEET_NAME)
sheet = spreadsheet.sheet1

# --- 2. CONFIG ---
TMDB_API_KEY = "1e08f4e7f84d8985db9da59d7d71e8e8"

st.set_page_config(page_title="Varun's Buffet Pro", layout="wide")
st.title("🍽️ Varun’s Cinematic Buffet PRO")

# Helper to update cell and refresh
def update_sheet(row_idx, col_idx, value):
    sheet.update_cell(row_idx, col_idx, value)
    st.rerun()

# --- 3. SIDEBAR NAVIGATION ---
menu = st.sidebar.radio("Navigation", [
    "🔍 Add New Content", 
    "⏳ Yet to Watch", 
    "📺 Started Watching", 
    "✅ Completed Watching"
])

# --- 4. DATA LOADING ---
all_values = sheet.get_all_values()
headers = all_values[0]
df_master = pd.DataFrame(all_values[1:], columns=headers)
existing_titles = df_master['Name'].tolist() if not df_master.empty else []

# --- 5. PAGE: ADD NEW CONTENT ---
if menu == "🔍 Add New Content":
    query = st.text_input("Search Cinema or Web Series:")
    if query:
        results = requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}").json().get('results', [])
        
        for item in results[:5]:
            m_type_raw = item.get('media_type', 'movie')
            if m_type_raw not in ['movie', 'tv']: continue
            
            details = requests.get(f"https://api.themoviedb.org/3/{m_type_raw}/{item['id']}?api_key={TMDB_API_KEY}").json()
            title = details.get('title') or details.get('name')
            year = details.get('release_date', details.get('first_air_date', '????'))[:4]
            genres = ", ".join([g['name'] for g in details.get('genres', [])])
            poster_url = f"https://image.tmdb.org/t/p/w500{details.get('poster_path', '')}"

            # Calculate Duration
            total_mins = 0
            ep_count = details.get('number_of_episodes', 0) if m_type_raw == "tv" else 0
            if m_type_raw == "tv":
                for s in details.get('seasons', []):
                    if s.get('season_number') == 0: continue
                    try:
                        s_data = requests.get(f"https://api.themoviedb.org/3/tv/{item['id']}/season/{s.get('season_number')}?api_key={TMDB_API_KEY}").json()
                        for ep in s_data.get('episodes', []): total_mins += ep.get('runtime', 0)
                    except: pass
            else: total_mins = details.get('runtime', 0)
            dur_str = f"{total_mins//60}h {total_mins%60}m" + (f" ({ep_count} Eps)" if ep_count > 0 else "")

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 2, 1.5])
            with c1: st.image(poster_url, width=150)
            with c2:
                st.subheader(f"{title} ({year})")
                if title.lower() in [t.lower() for t in existing_titles]:
                    st.error("Already in your Buffet!")
                    continue
                st.write(f"🎭 {genres}")
                st.write(f"⏳ {dur_str}")
            
            with c3:
                t_val = st.slider("Trust:", 2.0, 5.0, 4.0, 0.5, key=f"t_new_{item['id']}")
                i_val = st.select_slider("Interest:", ["Low", "Medium", "High"], "High", key=f"i_new_{item['id']}")
                w_map = {"High": 3, "Medium": 2, "Low": 1}
                
                col_a, col_b, col_c = st.columns(3)
                if col_a.button("➕ Add", key=f"a_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", genres, "N/A", dur_str, poster_url, t_val, i_val, w_map[i_val], "Planned"])
                    st.rerun()
                if col_b.button("📺 Watch", key=f"w_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", genres, "N/A", dur_str, poster_url, t_val, i_val, w_map[i_val], "Watching"])
                    st.rerun()
                if col_c.button("✅ Done", key=f"d_{item['id']}"):
                    sheet.append_row([title, year, "Web Series" if m_type_raw=="tv" else "Cinema", genres, "N/A", dur_str, poster_url, t_val, i_val, w_map[i_val], "Completed"])
                    st.rerun()

# --- 6. DISPLAY LISTS ---
else:
    status_map = {"⏳ Yet to Watch": "Planned", "📺 Started Watching": "Watching", "✅ Completed Watching": "Completed"}
    target_status = status_map[menu]
    filtered_df = df_master[df_master['Status'] == target_status]
    
    if filtered_df.empty:
        st.info(f"No titles in {menu} yet.")
    else:
        # SORTING
        if target_status == "Planned":
            filtered_df['Interest Weight'] = pd.to_numeric(filtered_df['Interest Weight'], errors='coerce')
            filtered_df['Trust Rating'] = pd.to_numeric(filtered_df['Trust Rating'], errors='coerce')
            filtered_df = filtered_df.sort_values(by=['Interest Weight', 'Trust Rating'], ascending=[False, False])
        else:
            filtered_df = filtered_df.iloc[::-1]

        n = 4
        for i in range(0, len(filtered_df), n):
            cols = st.columns(n)
            chunk = filtered_df.iloc[i:i+n]
            for j, (idx, row) in enumerate(chunk.iterrows()):
                row_num = int(idx) + 2
                with cols[j]:
                    st.image(row['Poster URL'], width=180)
                    st.markdown(f"**{row['Name']}**")
                    st.caption(f"{row['Year']} | {row['Type']}")
                    st.write(f"🎭 {row['Genre']}")
                    st.write(f"⏳ {row['Duration']}")

                    # --- PENCIL ICON EDITING ---
                    # IMDB
                    ci1, ci2 = st.columns([4, 1])
                    ci1.write(f"⭐ IMDB: {row['IMDB Rating']}")
                    if ci2.button("✏️", key=f"e_imdb_{idx}"): st.session_state[f"m_imdb_{idx}"] = True
                    if st.session_state.get(f"m_imdb_{idx}"):
                        new_imdb = st.text_input("New Rating:", row['IMDB Rating'], key=f"in_imdb_{idx}")
                        if st.button("Save", key=f"s_imdb_{idx}"):
                            update_sheet(row_num, 5, new_imdb)
                            del st.session_state[f"m_imdb_{idx}"]

                    # Interest
                    interest = row['Interest Level']
                    color = {"High": "green", "Medium": "orange", "Low": "gray"}.get(interest, "blue")
                    cn1, cn2 = st.columns([4, 1])
                    cn1.markdown(f":{color}[❤️ {interest}]")
                    if cn2.button("✏️", key=f"e_int_{idx}"): st.session_state[f"m_int_{idx}"] = True
                    if st.session_state.get(f"m_int_{idx}"):
                        new_int = st.select_slider("New Interest:", ["Low", "Medium", "High"], value=interest, key=f"in_int_{idx}")
                        if st.button("Save", key=f"s_int_{idx}"):
                            w_map = {"High": 3, "Medium": 2, "Low": 1}
                            sheet.update_cell(row_num, 9, new_int)
                            sheet.update_cell(row_num, 10, w_map[new_int])
                            del st.session_state[f"m_int_{idx}"]
                            st.rerun()

                    # Trust
                    trust = row['Trust Rating']
                    ct1, ct2 = st.columns([4, 1])
                    ct1.write(f"⭐ Trust: {trust}")
                    if ct2.button("✏️", key=f"e_tru_{idx}"): st.session_state[f"m_tru_{idx}"] = True
                    if st.session_state.get(f"m_tru_{idx}"):
                        new_tru = st.slider("New Trust:", 2.0, 5.0, float(trust) if trust else 4.0, 0.5, key=f"in_tru_{idx}")
                        if st.button("Save", key=f"s_tru_{idx}"):
                            update_sheet(row_num, 8, new_tru)
                            del st.session_state[f"m_tru_{idx}"]

                    # --- ACTION BUTTONS ---
                    if target_status == "Planned":
                        if st.button("🎬 Start Watching", key=f"btn_sw_{idx}", use_container_width=True): 
                            update_sheet(row_num, 11, "Watching")
                        if st.button("✅ Already Watched", key=f"btn_aw_{idx}", use_container_width=True): 
                            update_sheet(row_num, 11, "Completed")
                    elif target_status == "Watching":
                        if st.button("✅ Finished Watching", key=f"btn_fw_{idx}", use_container_width=True): 
                            update_sheet(row_num, 11, "Completed")

                    st.write("---")
