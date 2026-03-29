import sys
import streamlit as st
from pathlib import Path
from datetime import datetime, time as dtime
import time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import streamlit_authenticator as stauth
import random
import string
from captcha.image import ImageCaptcha

# Add current dir to path for local imports
sys.path.append(str(Path(__file__).parent))

import threading
from nse_scraper import run_scraper, fetch_and_save
from data_manager import (
    get_input_dir, 
    get_output_dir,
    get_output_path,
    save_uploaded_file,
    get_available_dates, 
    get_last_sync_info, 
    load_option_chain,
    get_current_date_str
)
from analysis import compute_support_resistance, compute_pcr, compute_evolution_data
from plot import plot_support_resistance
from auth_manager import AuthManager

# --- Initialize Auth Manager ---
auth_manager = AuthManager()

# --- Page Layout ---
st.set_page_config(
    page_title="OptEazy",
    page_icon="📈",
    layout="wide",
)

# Load Custom CSS
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

# --- Authentication Logic ---
credentials = auth_manager.get_user_credentials()

authenticator = stauth.Authenticate(
    credentials,
    "opteazy_cookie",
    "opteazy_key",
    cookie_expiry_days=30,
)

# --- Captcha Helper ---
def generate_captcha():
    chars = string.ascii_uppercase + string.digits
    captcha_text = ''.join(random.choice(chars) for _ in range(5))
    image = ImageCaptcha()
    data = image.generate(captcha_text)
    return captcha_text, data

# Login / Register Toggle
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

if not st.session_state.get("authentication_status"):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.session_state.auth_mode == "login":
            st.markdown('<h1 style="text-align:center; color:#2962ff;">OPTEAZY LOGIN</h1>', unsafe_allow_html=True)
            authenticator.login(location='main')
            authentication_status = st.session_state.get("authentication_status")
            username = st.session_state.get("username")
            name = st.session_state.get("name")
            
            if authentication_status == False:
                st.error('Username/password is incorrect')
            elif authentication_status == None:
                st.info('Please enter your username and password')
                if st.button("New user? Register here"):
                    st.session_state.auth_mode = "register"
                    st.rerun()
        else:
            st.markdown('<h1 style="text-align:center; color:#2962ff;">CREATE ACCOUNT</h1>', unsafe_allow_html=True)
            with st.form("registration_form"):
                new_user = st.text_input("Username")
                new_email = st.text_input("Email")
                new_name = st.text_input("Full Name")
                new_pw = st.text_input("Password", type="password")
                
                # Captcha logic
                if "captcha_text" not in st.session_state:
                    st.session_state.captcha_text, st.session_state.captcha_data = generate_captcha()
                
                st.image(st.session_state.captcha_data)
                captcha_input = st.text_input("Enter the code above")
                
                submit = st.form_submit_button("Register")
                
            if st.button("🔄 Refresh Captcha"):
                st.session_state.captcha_text, st.session_state.captcha_data = generate_captcha()
                st.rerun()

            if submit:
                if captcha_input.upper() != st.session_state.captcha_text:
                    st.error("Invalid Captcha!")
                elif not all([new_user, new_email, new_name, new_pw]):
                    st.error("Please fill all fields!")
                else:
                    success = auth_manager.add_user(new_user, new_email, new_name, new_pw, role="public_user")
                    if success:
                        st.success("Registration successful! You can now login.")
                        st.session_state.auth_mode = "login"
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Username already exists!")
            
            if st.button("Back to Login"):
                st.session_state.auth_mode = "login"
                st.rerun()

# --- Authenticated App ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_role = auth_manager.get_user_role(username)
    user_data = credentials["usernames"][username]
    
    # --- Background Scraper Integration ---
    @st.cache_resource
    def start_background_scraper(symbol="NIFTY"):
        """Starts the scraper in a non-blocking background thread."""
        thread = threading.Thread(target=run_scraper, args=(symbol,), daemon=True)
        thread.start()
        return thread

    # Start scraper if not already running (only for Admin or Editor)
    if user_role in ["admin", "content_editor"]:
        scraper_thread = start_background_scraper()

    # --- Sidebar Layout ---
    with st.sidebar:
        st.markdown(f'<h2 style="color:#2962ff;">OPTEAZY</h2>', unsafe_allow_html=True)
        st.markdown(f"**Welcome, {user_data['name']}!**")
        st.markdown(f"Role: `{user_role.upper()}`")
        authenticator.logout('Logout', 'sidebar')
        
        st.sidebar.markdown("---")
        
        # Admin / Editor Features
        if user_role in ["admin", "content_editor"]:
            st.sidebar.subheader("🛡️ Terminal Health")
            if st.sidebar.button("🧼 Scrub & Repair History"):
                with st.spinner("Scrubbing corrupted snapshots..."):
                    scrubbed_count = 0
                    for date_dir in Path("input_file").iterdir():
                        if date_dir.is_dir():
                            for fpath in date_dir.glob("*.csv"):
                                try:
                                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                        first_lines = "".join([f.readline() for _ in range(5)])
                                        if "<!DOCTYPE html" in first_lines.lower() or "<html" in first_lines.lower():
                                            fpath.unlink() # Delete corrupted file
                                            scrubbed_count += 1
                                except: continue
                    if scrubbed_count > 0:
                        st.sidebar.success(f"Purged {scrubbed_count} corrupted snapshots!")
                        st.cache_data.clear()
                    else:
                        st.sidebar.info("History is 100% clean!")

        # User Management (Admin Only)
        if user_role == "admin":
            with st.sidebar.expander("👥 User Management"):
                all_users = auth_manager.get_all_users()
                for u in all_users:
                    col_u, col_r = st.columns([3, 2])
                    col_u.write(f"{u['username']} ({u['role']})")
                    if u['username'] != "admin":
                        new_r = col_r.selectbox("Role", ["public_user", "content_editor", "admin"], 
                                               index=["public_user", "content_editor", "admin"].index(u['role']),
                                               key=f"role_{u['username']}")
                        if new_r != u['role']:
                            auth_manager.update_user_role(u['username'], new_r)
                            st.rerun()

        st.sidebar.markdown("---")
        # Date Selection
        available_dates = get_available_dates()
        selected_date = st.selectbox("Market Analysis Date", options=available_dates, index=0)
        is_today = (selected_date == get_current_date_str())

        # Scraper Status Badge
        st.markdown("### SYSTEM CONNECTIVITY")
        last_sync_time, is_recent = get_last_sync_info(selected_date)
        
        now_ist = datetime.now().time()
        market_close = dtime(15, 30)
        
        if is_today:
            status_label = "LIVE FEED" if (is_recent and not (now_ist > market_close)) else \
                           "SYNC SUCCESS" if (is_recent and (now_ist > market_close)) else \
                           "DELAYED / IDLE"
            
            if 'target_expiry' not in st.session_state:
                st.session_state.target_expiry = "Searching..."
            
            st.metric(
                label=f"Market Loop Sync ({st.session_state.target_expiry})", 
                value=status_label, 
                delta=f"Sync: {last_sync_time}",
                delta_color="normal" if is_recent else "inverse"
            )
            
            # Manual Force Pull (Admin/Editor Only)
            if user_role in ["admin", "content_editor"]:
                if st.button("🔄 Get Fresh File"):
                    curl_input = st.session_state.get("curl_command_input", "").strip()
                    manual_cookie = st.session_state.get("manual_cookie_input", "").strip()
                    with st.status("Performing Absolute Zero Sync...", expanded=True) as status:
                        success, msg, target_expiry = fetch_and_save(
                            symbol="NIFTY", 
                            curl_command=curl_input if curl_input else None,
                            manual_cookie=manual_cookie if manual_cookie else None
                        )
                        if success:
                            st.session_state.target_expiry = target_expiry
                            status.update(label=f"Success! {msg}", state="complete", expanded=True)
                            st.toast(f"Sync complete for {target_expiry}!", icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else:
                            status.update(label=f"Sync Failed: {msg}", state="error", expanded=True)
                            st.toast("Blocking detected.", icon="❌")

                # MIRROR MODE
                with st.sidebar.expander("🛡️ THE ABSOLUTE ZERO (Mirror Mode)", expanded=False):
                    st.warning("Only use if sync fails.")
                    curl_val = st.text_area("Paste cURL (bash) here", key="curl_command_input", height=150)
                    if curl_val and st.button("🔗 Apply & Sync Now"):
                        with st.status("Validating cURL Identity...", expanded=True) as status:
                            success, msg, target_expiry = fetch_and_save(symbol="NIFTY", curl_command=curl_val)
                            if success:
                                st.session_state.target_expiry = target_expiry
                                status.update(label=f"Success! {msg}", state="complete", expanded=True)
                                st.rerun()
                            else:
                                status.update(label=f"Mirror Failed: {msg}", state="error", expanded=True)
            else:
                st.info("Manual refresh disabled for Public role.")

        else:
            st.info(f"Archive Mode: {selected_date}")

        st.markdown("---")
        # Uploads (Admin/Editor Only)
        if user_role in ["admin", "content_editor"]:
            uploaded_file = st.file_uploader("Import Archive Data (.csv, .xlsx)", type=["csv", "xlsx"])
            if uploaded_file:
                with st.spinner("Processing..."):
                    file_path = save_uploaded_file(uploaded_file)
                    try:
                        df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(str(file_path))
                        result = compute_support_resistance(df=df, strike_col=strike_col, ce_oi_col=ce_oi_col, pe_oi_col=pe_oi_col)
                        output_path = get_output_path(uploaded_file.name)
                        plot_support_resistance(analysis_result=result, output_path=str(output_path), show=False, title=f"Analysis: {uploaded_file.name}")
                        st.success("Analysis Complete")
                    except Exception as e:
                        st.error(str(e))

        if st.button("Instant Refresh"):
            st.rerun()

    # --- Main Layout ---
    st.markdown(f'# Market Sentiment & OI Analysis <span style="font-size:0.5em; color:#8b949e;">({selected_date})</span>', unsafe_allow_html=True)
    
    tab_snapshot, tab_evolution = st.tabs(["📊 Live Snapshot", "📈 Evolution Trend"])
    
    output_dir = get_output_dir(selected_date)
    input_dir = get_input_dir(selected_date)
    
    with tab_snapshot:
        input_files = sorted(list(input_dir.glob("*.[cx][sl][sv]*")), key=os.path.getmtime, reverse=True)
        if not input_files:
            st.info("📊 Awaiting data... Admin will populate this soon.")
        else:
            valid_found = False
            for fpath in input_files:
                try:
                    df, s_col, c_col, p_col = load_option_chain(str(fpath))
                    res = compute_support_resistance(df, s_col, c_col, p_col, top_n=5, smooth_window=3)
                    data = res["data"]
                    st.markdown(f"### Current Market Profile: {fpath.stem}")
                    valid_found = True
                    break
                except Exception: continue
            
            if not valid_found:
                st.warning("⚠️ No valid snapshots found.")
            else:
                fig_snapshot = go.Figure()
                fig_snapshot.add_trace(go.Bar(x=data["strike"], y=data["pe_oi"], name="Put OI (Support)", marker_color='#00c853', opacity=0.8))
                fig_snapshot.add_trace(go.Bar(x=data["strike"], y=data["ce_oi"], name="Call OI (Resistance)", marker_color='#ff5252', opacity=0.8))
                fig_snapshot.add_vline(x=res["max_support"].strike, line_width=3, line_dash="dash", line_color="#00c853", annotation_text="MAJOR SUPPORT")
                fig_snapshot.add_vline(x=res["max_resistance"].strike, line_width=3, line_dash="dash", line_color="#ff5252", annotation_text="MAJOR RESISTANCE")
                fig_snapshot.update_layout(template="plotly_dark", paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', hovermode="x unified", barmode='group', height=600)
                st.plotly_chart(fig_snapshot, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🛡️ Support Walls")
                    st.dataframe(pd.DataFrame([{"Strike": l.strike, "OI": l.pe_oi} for l in res["top_support"]]), hide_index=True)
                with col2:
                    st.markdown("#### 🏰 Resistance Walls")
                    st.dataframe(pd.DataFrame([{"Strike": l.strike, "OI": l.ce_oi} for l in res["top_resistance"]]), hide_index=True)

    @st.cache_data(ttl=300)
    def get_cached_evolution(input_dir_path: str):
        fpaths = sorted(list(Path(input_dir_path).glob("*.csv")), key=os.path.getmtime)
        if not fpaths: return pd.DataFrame()
        return compute_evolution_data(fpaths, load_option_chain)

    with tab_evolution:
        st.subheader(f"📈 Evolution Trend ({selected_date})")
        evolution_df = get_cached_evolution(str(input_dir))
        if evolution_df.empty:
            st.info("Accumulating data points...")
        else:
            fig_price = make_subplots(specs=[[{"secondary_y": True}]])
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Spot"], name="Spot Price", line=dict(color='#ffd700', width=4)), secondary_y=False)
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (2%)"], name="PCR", line=dict(color='#2962ff', width=3)), secondary_y=True)
            fig_price.update_layout(template="plotly_dark", paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', height=450)
            st.plotly_chart(fig_price, use_container_width=True)
            st.dataframe(evolution_df.set_index("Timestamp"), use_container_width=True)
