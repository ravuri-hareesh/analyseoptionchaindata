import sys
import streamlit as st
from pathlib import Path
from datetime import datetime, time as dtime
import time
import os
import random
import string
import threading

# Add current dir to path for local imports
sys.path.append(str(Path(__file__).parent))

from auth_manager import AuthManager
import extra_streamlit_components as stx

try:
    from data_manager import normalize_date_str
except ImportError:
    # Fallback if being initialized
    def normalize_date_str(d): return d

# --- Initialize Managers ---
auth_manager = AuthManager()
cookie_manager = stx.CookieManager()

# --- Page Layout & Global Configuration ---
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = "login"

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

st.set_page_config(
    page_title="OptEazy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Institutional High-Contrast Theme ---
st.markdown("""
    <style>
        /* Ensure All Headers & Labels are Pure White */
        h1, h2, h3, h4, h5, h6, label, .stMetric label, .stMarkdown p {
            color: #ffffff !important;
        }
        .stMetric [data-testid="stMetricValue"] {
            color: #ffffff !important;
        }
        
        /* High-Contrast Data Grid Foundation */
        [data-testid="stDataFrame"] {
            background-color: #ffffff;
            border-radius: 4px;
            padding: 2px;
        }
    </style>
""", unsafe_allow_html=True)

# --- Persistence Layer (Autologin) ---
# Retrieve cookies and query params on every page load
cookies = cookie_manager.get_all()
current_page = st.query_params.get("page")
current_date_param = normalize_date_str(st.query_params.get("date"))

# Logic Gate: If we haven't received browser state yet, pause the render
# Special Case: If we are on the dashboard page, we MUST wait for cookies to avoid "Home Jumping"
if cookies is None or (current_page == "dashboard" and not cookies):
    st.markdown('<div style="height:100vh; display:flex; align-items:center; justify-content:center; background-color:#0d1117; color:#8b949e; font-family:Inter,sans-serif;">🔄 Synchronizing OptEazy Terminal...</div>', unsafe_allow_html=True)
    st.stop()

if not st.session_state.get("authentication_status"):
    if cookies and "opteazy_user" in cookies:
        saved_user = cookies["opteazy_user"]
        # Fast-track validate against DB
        credentials = auth_manager.get_user_credentials()
        if saved_user in credentials["usernames"]:
            st.session_state["authentication_status"] = True
            st.session_state["username"] = saved_user
            st.session_state["name"] = credentials["usernames"][saved_user]["name"]
            
            # Persist date-specific access through autologin
            if current_date_param:
                st.session_state.selected_date = current_date_param
            
            # Ensure URL is synced
            st.query_params["page"] = "dashboard"
            st.rerun()
    elif current_page == "dashboard":
        # Force a clean redirect to home ONLY IF we are sure the cookie is actually missing
        st.query_params.clear()
        st.rerun()

# Load Consolidated CSS
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")
st.markdown('<style>div.block-container {padding-top:0.5rem; padding-bottom:0;} .main {overflow:hidden !important;} body {overflow:hidden !important;}</style>', unsafe_allow_html=True)

# --- Captcha Helper ---
def generate_captcha():
    from captcha.image import ImageCaptcha
    chars = string.ascii_uppercase + string.digits
    captcha_text = ''.join(random.choice(chars) for _ in range(5))
    image = ImageCaptcha()
    data = image.generate(captcha_text)
    return captcha_text, data

if not st.session_state.get("authentication_status"):
    # Unified Console Container (Consolidated Branding into Hero)
    st.markdown('<div class="unified-auth-console" style="padding:0; margin-top:10px; border:none; box-shadow:none; background:transparent;">', unsafe_allow_html=True)
    col_hero, col_login = st.columns([1.2, 1], gap="medium", vertical_alignment="top")
    
    # --- Performance-Optimized Asset Loader ---
    @st.cache_data
    def get_hero_b64():
        if os.path.exists("assets/hero_widescreen_3d.png"):
            import base64
            with open("assets/hero_widescreen_3d.png", "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None

    with col_hero:
        hero_b64 = get_hero_b64()
        if hero_b64:
            # Immersive Hero Background with Branding Overlay
            st.markdown(f"""
                <div class="hero-background-console">
                    <div class="hero-overlay-content">
                        <h1 class="hero-branding-title">OPTEAZY</h1>
                        <p class="hero-branding-slogan">Professional Edge, Made Eazy</p>
                    </div>
                </div>
                <style>
                .hero-background-console {{
                    background-image: linear-gradient(rgba(13, 17, 23, 0.45), rgba(13, 17, 23, 0.45)), url("data:image/png;base64,{hero_b64}");
                    background-size: cover;
                    background-position: center;
                    height: 390px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                    border: 1px solid rgba(41, 98, 255, 0.15);
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
                }}
                </style>
            """, unsafe_allow_html=True)
    
    with col_login:
        if st.session_state.auth_mode == "login":
            # Bold Institutional Header
            st.markdown('<h2 style="color:#ffffff; margin-top:0; margin-bottom:20px; font-size:1.5rem; font-weight:600;">Login</h2>', unsafe_allow_html=True)
            
            # Manual Secure Terminal Form
            with st.form("manual_login_form", clear_on_submit=False):
                manual_user = st.text_input("Username", key="user_in")
                manual_pw = st.text_input("Password", type="password", key="pw_in")
                
                # Unified Side-by-Side Buttons inside the form
                col_btn_l, col_btn_r = st.columns([1, 1], gap="small")
                with col_btn_l:
                    login_clicked = st.form_submit_button("Login", width="stretch")
                with col_btn_r:
                    # Upgrade to form_submit_button to resolve API constraint
                    signup_clicked = st.form_submit_button("Signup", width="stretch")
                
                if login_clicked:
                    if manual_user and manual_pw:
                        credentials = auth_manager.get_user_credentials()
                        if manual_user in credentials["usernames"]:
                            hashed_pw = credentials["usernames"][manual_user]["password"]
                            if auth_manager.check_password(manual_pw, hashed_pw):
                                st.session_state["authentication_status"] = True
                                st.session_state["username"] = manual_user
                                st.session_state["name"] = credentials["usernames"][manual_user]["name"]
                                # Set persistence cookie (30 days) and update URL
                                cookie_manager.set("opteazy_user", manual_user, key="set_user_cookie")
                                st.query_params["page"] = "dashboard"
                                st.rerun()
                            else:
                                st.error("Invalid password")
                        else:
                            st.error("User not found")
                    else:
                        st.error("Please enter credentials")
            
            if signup_clicked:
                st.session_state.auth_mode = "register"
                st.rerun()
        else:
            # Registration Mode remains professional
            with st.form("registration_form"):
                new_user = st.text_input("Username")
                new_email = st.text_input("Email")
                new_name = st.text_input("Full Name")
                new_pw = st.text_input("Password", type="password")
                
                if "captcha_text" not in st.session_state:
                    st.session_state.captcha_text, st.session_state.captcha_data = generate_captcha()
                
                st.image(st.session_state.captcha_data, width=150)
                captcha_input = st.text_input("Enter the code above")
                submit = st.form_submit_button("Register", width="stretch")
            
            if st.button("Back to Login"):
                st.session_state.auth_mode = "login"
                st.rerun()

            if submit:
                if captcha_input.upper() == st.session_state.captcha_text:
                    if auth_manager.add_user(new_user, new_pw, new_email, new_name, role="public_user"):
                        st.success("Registration successful! Please login.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    else:
                        st.error("Username already exists!")
                else:
                    st.error("Incorrect Captcha code. Refresh and try again.")
                    st.session_state.captcha_text, st.session_state.captcha_data = generate_captcha()
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Minimalist Risk Disclosure
    st.markdown('<p style="font-size:0.65rem; color:#8b949e; text-align:center; margin-top:15px;">'
                '<b>RISK DISCLAIMER:</b> Trading involves significant loss risk. Informational/educational only. NOT SEBI registered.</p>', 
                unsafe_allow_html=True)

# --- Authenticated App ---
if st.session_state.get("authentication_status"):
    # --- LAZY MODULE INJECTION (High Speed) ---
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from nse_scraper import run_scraper, fetch_and_save
    from data_manager import (
        get_input_dir, 
        get_output_dir,
        get_output_path,
        save_uploaded_file,
        get_available_dates, 
        get_available_expiries,
        get_latest_analysis_date,
        discover_expiry_from_file,
        get_last_sync_info, 
        load_option_chain,
        get_current_date_str,
        APP_DATE_FORMAT,
        DB_DATE_FORMAT
    )
    from analysis import compute_support_resistance, compute_pcr, compute_evolution_data, clear_evolution_cache
    from db_connector import OptEazyDB
    db_manager = OptEazyDB()
    from plot import plot_support_resistance
    from financial_data import run_indicator_service

    username = st.session_state.get("username")
    user_role = auth_manager.get_user_role(username)
    user_name = st.session_state.get("name", username)
    
    # --- Background Scraper Integration ---
    @st.cache_resource
    def start_background_scraper(symbol="NIFTY"):
        """Starts the scraper in a non-blocking background thread."""
        thread = threading.Thread(target=run_scraper, args=(symbol,), daemon=True)
        thread.start()
        return thread

    # Start scraper if not already running (only for Admin or Editor)
    if user_role in ["admin", "content_editor"]:
        if 'scraper_thread_init' not in st.session_state:
            st.session_state.scraper_thread_init = start_background_scraper()
        
    # --- Background Financial Indicators Service ---
    @st.cache_resource
    def start_indicator_service():
        """Starts the USD/INR and Oil price fetcher in the background."""
        stop_event = threading.Event()
        thread = threading.Thread(target=run_indicator_service, args=(db_manager, stop_event), daemon=True)
        thread.start()
        return thread, stop_event

    if 'indicator_service' not in st.session_state:
        st.session_state.indicator_service, st.session_state.indicator_stop = start_indicator_service()

    # --- Sidebar Layout ---
    with st.sidebar:
        # 1. Branding Header (Ultra-Compact)
        st.markdown(f'<h3 style="color:#2962ff; margin-bottom:0; font-size:1.3rem;">OPTEAZY</h3>', unsafe_allow_html=True)
        st.markdown(f'<p style="color:#8b949e; font-size:0.65rem; margin-top:-5px; margin-bottom:10px;">Institutional Terminal</p>', unsafe_allow_html=True)
        
        # 2. Welcome Info (Zero Margin)
        st.markdown(f'<p style="font-size:0.8rem; margin-bottom:0; margin-top:0;">Welcome, <b>{user_name}</b></p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:0.65rem; color:#8b949e; margin-bottom:12px;">Role: <span style="color:#2962ff;">{user_role.upper()}</span></p>', unsafe_allow_html=True)
        st.caption("🟢 SYSTEM CONNECTIVITY: ACTIVE")
        
        # 3. NAVIGATION & SESSION
        col_nav1, col_nav2 = st.columns([1, 1])
        with col_nav1:
            if st.button("🏠 Home", key="nav_home", width="stretch"):
                st.session_state.selected_date = get_current_date_str()
                # Clear date param when returning to live
                st.query_params.pop("date", None)
                st.rerun()
        with col_nav2:
             # Logout as secondary button in sidebar
            if st.button("🚪 Logout", key="manual_logout", type="primary", width="stretch"):
                st.session_state["authentication_status"] = False
                st.session_state["username"] = None
               # 4. Manual Operations (Admin Only)
        if user_role in ["admin", "content_editor"]:
            st.markdown("---")
            st.markdown(f'<p style="font-size:0.75rem; color:#8b949e; margin-bottom:5px;">ADMIN TOOLS</p>', unsafe_allow_html=True)
            if st.button("🚀 Force Pulse Sync", use_container_width=True, help="Trigger manual NSE Fetch & DB Update"):
                with st.spinner("Pulsing NSE..."):
                    success, msg, target = fetch_and_save("NIFTY")
                    if success:
                        st.success(f"Sync Success: {msg}")
                        st.info(f"Target Expiry: {target}")
                        st.rerun()
                    else:
                        st.error(f"Sync Failed: {msg}")

        # 5. Session Control
        st.markdown("---")
        logout = st.button("Logout", use_container_width=True)
        if logout:
            cookie_manager.delete("opteazy_user")
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
                
        st.markdown("---")
        
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
                        clear_evolution_cache() # Purge the parallel hot-cache as well
                    else:
                        st.sidebar.info("History is 100% clean!")
                    
                if st.sidebar.button("🧨 Reset Databases", help="Wipe all data from MySQL and MongoDB"):
                    db_manager.reset_databases()
                    st.sidebar.success("Databases wiped successfully!")
                    st.cache_data.clear()
                    clear_evolution_cache()
                    st.rerun()
                    
                if st.sidebar.button("🧨 Reset Databases", help="Wipe all data from MySQL and MongoDB"):
                    db_manager.reset_databases()
                    st.sidebar.success("Databases wiped successfully!")
                    st.cache_data.clear()
                    clear_evolution_cache()
                    st.rerun()

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
        # --- DUAL-GATE DATE & EXPIRY SELECTION ---
        available_dates = get_available_dates()
        
        if not available_dates:
            st.sidebar.warning("📊 No data snapshots found yet.")
            selected_date = get_current_date_str()
            available_expiries = ["07-Apr-2026"]
        else:
            # 1. Market Analysis Date Selection (Priority)
            current_date_val = st.query_params.get("date", st.session_state.get("selected_date", available_dates[0]))
            
            try:
                date_ix = available_dates.index(current_date_val)
            except ValueError:
                date_ix = 0
            
            selected_date = st.sidebar.selectbox("📅 Market Analysis Date", options=available_dates, index=date_ix, key="sidebar_date_selector")
            
            # 2. Target Expiry Selection (Dependent on Date)
            available_expiries = get_available_expiries(selected_date)
            current_expiry_param = normalize_date_str(st.query_params.get("expiry", "07-Apr-2026"))
            
            try:
                expiry_ix = available_expiries.index(current_expiry_param)
            except ValueError:
                expiry_ix = 0
                
            selected_expiry = st.sidebar.selectbox("🎯 Target Expiry", options=available_expiries, index=expiry_ix, key="sidebar_expiry_selector")
            
            # 3. Synchronize Session and URL
            if (selected_expiry != st.query_params.get("expiry") or 
                selected_date != st.query_params.get("date")):
                st.session_state.selected_date = selected_date
                st.query_params["expiry"] = selected_expiry
                st.query_params["date"] = selected_date
                # No rerun here to avoid infinite loops, Streamlit picks it up on next interaction
                # or we can force it if state gets out of sync
            
            # 4. Spectral Overlay (Comparative Analysis)
            other_expiries = [e for e in available_expiries if e != selected_expiry]
            overlay_expiries = st.sidebar.multiselect("📊 Overlay Expiries (1% PCR)", options=other_expiries, help="Overlay sentiment from other expiries on the evolution chart")
            
        is_today = (selected_date == get_current_date_str() and selected_expiry == normalize_date_str("07-Apr-2026"))

        # Scraper & DB Status Badge
        st.markdown("### SYSTEM CONNECTIVITY")
        
        # Dual DB Connectivity Check (Non-Blocking)
        db_status = db_manager.test_all_connections()
        db_cols = st.columns(2)
        with db_cols[0]:
            st.caption(f"{'🟢' if db_status['MySQL'] else '🔴'} MySQL")
        with db_cols[1]:
            st.caption(f"{'🟢' if db_status['MongoDB'] else '🔴'} MongoDB")

        last_sync_time, is_recent = get_last_sync_info(selected_expiry, selected_date)
        
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
            uploaded_files = st.file_uploader(
                "Import Archive Data (.csv, .xlsx)", 
                type=["csv", "xlsx"], 
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.uploader_key}"
            )
            if uploaded_files:
                with st.spinner(f"Processing {len(uploaded_files)} files..."):
                    for uploaded_file in uploaded_files:
                        file_path = save_uploaded_file(uploaded_file, date_str=selected_date)
                        expiry_for_upload = discover_expiry_from_file(uploaded_file)
                        try:
                            df, strike_col, ce_oi_col, pe_oi_col = load_option_chain(str(file_path))
                            result = compute_support_resistance(df=df, strike_col=strike_col, ce_oi_col=ce_oi_col, pe_oi_col=pe_oi_col)
                            output_path = get_output_path(uploaded_file.name, expiry_date=expiry_for_upload, date_str=selected_date)
                            plot_support_resistance(analysis_result=result, output_path=str(output_path), show=False, title=f"Analysis: {uploaded_file.name}")
                            st.toast(f"✅ Success: {uploaded_file.name}")
                        except Exception as e:
                            st.error(f"Error processing {uploaded_file.name}: {str(e)}")

                    st.cache_data.clear() # Clear Streamlit cache
                    clear_evolution_cache() # Clear analysis analysis hot-cache
                    # Increment key to reset uploader and rerun
                    st.session_state.uploader_key += 1
                    st.rerun()

        if st.button("Instant Refresh"):
            st.rerun()

    # --- Main Layout ---
    st.markdown(f'<h1 style="color:#ffffff; margin-bottom:0;">Market Sentiment & OI Analysis</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:#2962ff; font-weight:600; margin-top:-5px;">OptEazy: Professional Edge, Made Eazy <span style="color:#8b949e; font-weight:400; font-size:0.8rem;">({selected_expiry} | {selected_date})</span></p>', unsafe_allow_html=True)
    
    tab_snapshot, tab_evolution = st.tabs(["📊 Live Snapshot", "📈 Evolution Trend"])
    
    output_dir = get_output_dir(selected_expiry, selected_date)
    input_dir = get_input_dir(selected_expiry, selected_date)
    
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
                fig_snapshot.update_layout(
                    template="plotly_dark", 
                    paper_bgcolor='#0e1117', 
                    plot_bgcolor='#0e1117', 
                    hovermode="x unified", 
                    barmode='group', 
                    height=850,
                    legend=dict(font=dict(color="white"))
                )
                st.plotly_chart(fig_snapshot, width="stretch")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🛡️ Support Walls")
                    st.dataframe(pd.DataFrame([{"Strike": l.strike, "OI": l.pe_oi} for l in res["top_support"]]), hide_index=True)
                with col2:
                    st.markdown("#### 🏰 Resistance Walls")
                    st.dataframe(pd.DataFrame([{"Strike": l.strike, "OI": l.ce_oi} for l in res["top_resistance"]]), hide_index=True)

                # --- NEW SECTION: Global Indicators (Currency & Oil) ---
                st.markdown("---")
                st.markdown("### 🌍 Global Indicators (Current)")
                indicator_df = db_manager.query_market_indicators(selected_date)
                
                if not indicator_df.empty:
                    latest_indic = indicator_df.iloc[-1]
                    prev_indic = indicator_df.iloc[-2] if len(indicator_df) > 1 else latest_indic
                    
                    cur_col1, cur_col2, cur_col3 = st.columns(3)
                    cur_col1.metric("USD/INR", f"₹{latest_indic['usd_inr']:.2f}", f"{latest_indic['usd_inr'] - prev_indic['usd_inr']:+.2f}")
                    cur_col2.metric("WTI CRUDE", f"${latest_indic['wti_crude']:.2f}", f"{latest_indic['wti_crude'] - prev_indic['wti_crude']:+.2f}")
                    cur_col3.metric("BRENT CRUDE", f"${latest_indic['brent_crude']:.2f}", f"{latest_indic['brent_crude'] - prev_indic['brent_crude']:+.2f}")
                    st.caption(f"Last updated: {latest_indic['timestamp']}")
                else:
                    st.info("Global indicators data pending first fetch...")

    @st.cache_data(ttl=60)
    def get_cached_evolution(expiry: str, date_str: str, fingerprint: str):
        """Fetches from MySQL for high production speed."""
        df = db_manager.query_evolution_data(expiry)
        if df.empty:
            # Fallback to file scan if DB is empty or during migration
            input_dir_path = get_input_dir(expiry, date_str)
            fpaths = sorted(list(input_dir_path.glob("*.csv")), key=os.path.getmtime)
            if not fpaths: return pd.DataFrame()
            return compute_evolution_data(fpaths, load_option_chain)
        
        # Filter by date if needed (MySQL query currently returns all for expiry)
        # We ensure it's filtered for the selected day for this view
        df['Date'] = pd.to_datetime(df['Timestamp']).dt.date
        try:
            target_date = datetime.strptime(date_str, APP_DATE_FORMAT).date()
        except:
            # Fallback for during-migration moments
            target_date = pd.to_datetime(date_str).date()
            
        df = df[df['Date'] == target_date].drop(columns=['Date'])
        return df

    with tab_evolution:
        st.subheader(f"📈 Evolution Trend ({selected_expiry} | {selected_date})")
        with st.spinner("🚀 Pulse Synchronization: Querying Analytical Repository..."):
            # Use a simpler fingerprint for DB-backed query
            current_files = list(input_dir.glob("*.csv"))
            fingerprint = f"DB_V1_{len(current_files)}"
            evolution_df = get_cached_evolution(selected_expiry, selected_date, fingerprint)
        if evolution_df.empty:
            st.info("Accumulating data points...")
        else:
            # Show Latest Spot Price prominently
            latest_spot = evolution_df["Spot"].iloc[-1]
            prev_spot = evolution_df["Spot"].iloc[-2] if len(evolution_df) > 1 else latest_spot
            delta_spot = latest_spot - prev_spot
            
            # --- ADVANCED SIGNAL INTELLIGENCE (B/S) ---
            # Dual-indicator consensus: Both 1% and 2% PCR must align
            evolution_df['Spot_Rise'] = evolution_df['Spot'].diff() > 0
            evolution_df['Spot_Fall'] = evolution_df['Spot'].diff() < 0
            evolution_df['PCR1_Rise'] = evolution_df['PCR Ranged (1%)'].diff() > 0
            evolution_df['PCR1_Fall'] = evolution_df['PCR Ranged (1%)'].diff() < 0
            evolution_df['PCR2_Rise'] = evolution_df['PCR Ranged (2%)'].diff() > 0
            evolution_df['PCR2_Fall'] = evolution_df['PCR Ranged (2%)'].diff() < 0

            # Convergent Sentiment Requirement (1% & 2% Alignment)
            evolution_df['PCR_Consensus_Rise'] = evolution_df['PCR1_Rise'] & evolution_df['PCR2_Rise']
            evolution_df['PCR_Consensus_Fall'] = evolution_df['PCR1_Fall'] & evolution_df['PCR2_Fall']

            # Temporal Sequence Detection (Immediate Follow-through within ~5 mins)
            evolution_df['Spot_Rise_Prev'] = evolution_df['Spot_Rise'].shift(1, fill_value=False)
            evolution_df['Spot_Fall_Prev'] = evolution_df['Spot_Fall'].shift(1, fill_value=False)
            evolution_df['PCR_Rise_Prev'] = evolution_df['PCR_Consensus_Rise'].shift(1, fill_value=False)
            evolution_df['PCR_Fall_Prev'] = evolution_df['PCR_Consensus_Fall'].shift(1, fill_value=False)

            # Signal Logic: Start/Confirmed Consensus
            evolution_df['Signal'] = ""
            
            # BUY: (Rise Now + Rise Now) OR (Rise Now + Rise Prev) OR (Rise Prev + Rise Now)
            buy_mask = (evolution_df['PCR_Consensus_Rise'] & evolution_df['Spot_Rise']) | \
                       (evolution_df['PCR_Consensus_Rise'] & evolution_df['Spot_Rise_Prev']) | \
                       (evolution_df['PCR_Rise_Prev'] & evolution_df['Spot_Rise'])
            
            # SELL: (Fall Now + Fall Now) OR (Fall Now + Fall Prev) OR (Fall Prev + Fall Now)
            sell_mask = (evolution_df['PCR_Consensus_Fall'] & evolution_df['Spot_Fall']) | \
                        (evolution_df['PCR_Consensus_Fall'] & evolution_df['Spot_Fall_Prev']) | \
                        (evolution_df['PCR_Fall_Prev'] & evolution_df['Spot_Fall'])

            evolution_df.loc[buy_mask, 'Signal'] = "B"
            evolution_df.loc[sell_mask, 'Signal'] = "S"
            
            latest_signal = evolution_df['Signal'].iloc[-1] if not evolution_df.empty else ""
            
            if 'evolution_reset_key' not in st.session_state:
                st.session_state.evolution_reset_key = 0

            col_metric1, col_metric2, col_reset = st.columns([1, 2, 2])
            col_metric1.metric("LATEST SPOT", f"{latest_spot:,.2f}", f"{delta_spot:+.2f}")
            
            if col_reset.button("🔄 Reset Evolution View", help="Click to restore original zoom levels"):
                st.session_state.evolution_reset_key += 1
                st.rerun()
            
            # --- SPECTRAL PCR LAYERS ---
            # Gate: 1% Core sentiment (Visible by default)
            fig_price = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (1%)"], 
                name="PCR (Near Money 1%)", line=dict(color='#00e676', width=5)), secondary_y=True)
            
            # Gate: 2% Transition (Hidden by default)
            if "PCR Ranged (2%)" in evolution_df.columns:
                fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (2%)"], 
                    name="PCR (Near Money 2%)", line=dict(color='#1a237e', width=5)), secondary_y=True)
            
            # Gate: 3% Interaction (Hidden by default)
            if "PCR Ranged (3%)" in evolution_df.columns:
                fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (3%)"], 
                    name="PCR (Near Money 3%)", visible='legendonly', line=dict(color='#ff9100', width=2)), secondary_y=True)

            # Gate: 4% Expansion (Hidden by default)
            if "PCR Ranged (4%)" in evolution_df.columns:
                fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (4%)"], 
                    name="PCR (Near Money 4%)", visible='legendonly', line=dict(color='#e65100', width=4)), secondary_y=True)

            # Gate: 5% Outer Threshold (Visible by default)
            if "PCR Ranged (5%)" in evolution_df.columns:
                fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (5%)"], 
                    name="PCR (Near Money 5%)", visible='legendonly', line=dict(color='#2962ff', width=3)), secondary_y=True)
            
            # Gate: Market Overall (Hidden by default)
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Overall"], 
                name="PCR (Overall)", visible='legendonly', line=dict(color='#ffffff', width=4)), secondary_y=True)
            
            # --- SPECTRAL OVERLAYS (COMPARATIVE ANALYSIS) ---
            overlay_colors = ['#e91e63', '#9c27b0', '#673ab7', '#3f51b5', '#03a9f4']
            for i, overlay_exp in enumerate(overlay_expiries):
                latest_analysis = get_latest_analysis_date(overlay_exp)
                if latest_analysis:
                    overlay_input_dir = get_input_dir(overlay_exp, latest_analysis)
                    overlay_df = get_cached_evolution(overlay_exp, latest_analysis, f"DB_V1_{len(list(overlay_input_dir.glob('*.csv')))}")
                    if not overlay_df.empty and "PCR Ranged (1%)" in overlay_df.columns:
                        color = overlay_colors[i % len(overlay_colors)]
                        fig_price.add_trace(go.Scatter(
                            x=overlay_df["Timestamp"], y=overlay_df["PCR Ranged (1%)"],
                            name=f"PCR 1% ({overlay_exp})",
                            line=dict(color=color, width=2, dash='dot'),
                            hovertemplate=f"PCR 1% ({overlay_exp}): %{{y:.2f}}<extra></extra>"
                        ), secondary_y=True)

            # --- GROUND TRUTH SPOT TRAJECTORY ---
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Spot"], 
                name="Spot Price", mode='lines+markers', line=dict(color='#ffff00', width=5)), secondary_y=False)
            
            # Add horizontal line for current spot
            fig_price.add_hline(y=latest_spot, line_dash="dash", line_color="#ffff00", opacity=0.5, annotation_text=f"LIVE: {latest_spot:,.2f}")
            
            # --- SIGNAL MARKERS ON SPOT ---
            buy_points = evolution_df[evolution_df['Signal'] == "B"]
            sell_points = evolution_df[evolution_df['Signal'] == "S"]
            
            if not buy_points.empty:
                fig_price.add_trace(go.Scatter(
                    x=buy_points["Timestamp"], y=buy_points["Spot"],
                    mode='text', text="B", textfont=dict(color="#00e676", size=18, family="Arial Black"),
                    textposition="top center", name="BUY Signal", showlegend=False
                ), secondary_y=False)
            
            if not sell_points.empty:
                fig_price.add_trace(go.Scatter(
                    x=sell_points["Timestamp"], y=sell_points["Spot"],
                    mode='text', text="S", textfont=dict(color="#ff5252", size=18, family="Arial Black"),
                    textposition="bottom center", name="SELL Signal", showlegend=False
                ), secondary_y=False)
            
            fig_price.update_xaxes(
                rangeslider=dict(visible=True, thickness=0.03),
                showspikes=True, 
                spikecolor="gray", 
                spikemode="across", 
                spikesnap="cursor"
            )
            fig_price.update_layout(
                template="plotly_dark", 
                paper_bgcolor='#0e1117', 
                plot_bgcolor='#0e1117', 
                height=1000, 
                hovermode="x unified", 
                dragmode='zoom',
                hoverdistance=100,
                spikedistance=1000,
                legend=dict(font=dict(color="white"))
            )
            # Force full numbers on Y-axis (no "k")
            fig_price.update_yaxes(
                tickformat=".2f", 
                secondary_y=False,
                showspikes=True, 
                spikecolor="gray", 
                spikemode="across", 
                spikesnap="cursor"
            )
            
            col_graph, col_terminal = st.columns([12, 1], gap="small")
            
            with col_graph:
                st.plotly_chart(fig_price, width="stretch", key=f"evolution_plt_{st.session_state.evolution_reset_key}", config={
                    'scrollZoom': True,
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraselayer'],
                    'editSelection': True
                })
            
            with col_terminal:
                st.markdown('<div style="margin-top: 100px;"></div>', unsafe_allow_html=True)
                if latest_signal == "B":
                    st.markdown("""
                        <div style="background-color: rgba(0, 230, 118, 0.15); border-left: 4px solid #00c853; padding: 10px; border-radius: 4px; text-align: center;">
                            <h4 style="color: #00c853; margin: 0; font-size: 0.9rem;">SIGNAL</h4>
                            <h2 style="color: #00c853; margin: 0; font-size: 2rem; font-weight: 800;">BUY</h2>
                            <p style="color: #8b949e; font-size: 0.6rem; margin-top: 5px;">Converging PCR/Spot</p>
                        </div>
                    """, unsafe_allow_html=True)
                elif latest_signal == "S":
                    st.markdown("""
                        <div style="background-color: rgba(255, 82, 82, 0.15); border-left: 4px solid #ff5252; padding: 10px; border-radius: 4px; text-align: center;">
                            <h4 style="color: #ff5252; margin: 0; font-size: 0.9rem;">SIGNAL</h4>
                            <h2 style="color: #ff5252; margin: 0; font-size: 2rem; font-weight: 800;">SELL</h2>
                            <p style="color: #8b949e; font-size: 0.6rem; margin-top: 5px;">Converging PCR/Spot</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div style="background-color: rgba(139, 148, 158, 0.05); border-left: 4px solid #8b949e; padding: 10px; border-radius: 4px; text-align: center;">
                            <h4 style="color: #8b949e; margin: 0; font-size: 0.8rem;">NEUTRAL</h4>
                            <p style="color: #8b949e; font-size: 0.55rem; margin-top: 5px;">Awaiting Consensus</p>
                        </div>
                    """, unsafe_allow_html=True)
                
                # Dynamic Divergence Check (Price vs Consensus Sentiment)
                last_pcr1_rise = evolution_df['PCR1_Rise'].iloc[-1] if not evolution_df.empty else False
                last_pcr2_rise = evolution_df['PCR2_Rise'].iloc[-1] if not evolution_df.empty else False
                
                # Divergence: Price moves Up but Sentiment is Down (or vice-versa)
                is_diverging = (delta_spot > 0 and (not last_pcr1_rise or not last_pcr2_rise)) or \
                               (delta_spot < 0 and (last_pcr1_rise or last_pcr2_rise))
                
                if is_diverging:
                    st.markdown('<p style="color:#ff9100; font-size:0.6rem; margin-top:10px; text-align:center;">⚠️ Divergence Detected</p>', unsafe_allow_html=True)
            
            # --- SIGNAL-AWARE DATA GRID ---
            st.markdown("#### 🕵️ Sentiment Trajectory Audit")
            col_sens1, col_sens2 = st.columns(2)
            spot_pcr_sens = col_sens1.slider("📉 Spot and PCR change (%)", 1.0, 10.0, 5.0, 0.5, help="Highlight price and sentiment shifts")
            contract_sens = col_sens2.slider("🏗️ Contract change (%)", 10.0, 100.0, 10.0, 5.0, help="Highlight institutional wall strength shifts")
            
            # 1. Institutional Reorganization
            audit_df = evolution_df.copy()
            audit_df = audit_df.rename(columns={"Timestamp": "Time"})
            
            # Explicit Strategic Column Order
            strategic_order = ["Time"]
            strategic_order += [f"PCR Ranged ({i}%)" for i in range(1, 6)]
            strategic_order += ["PCR Overall", "Spot", "Major Support", "Major Resistance", "Immediate Support", "Immediate Resistance"]
            
            # Identify columns to drop (all the raw OI columns used for styling)
            oi_cols = ["Major Support OI", "Major Resistance OI", "Immediate Support OI", "Immediate Resistance OI"]
            
            # 2. Contract-Aware Styling Engine (Dual-Gate Sensitivity)
            # Default: Thick Black Text on White Canvas
            styles_df = pd.DataFrame('color: #000000; font-weight: 600; background-color: #ffffff;', index=audit_df.index, columns=audit_df.columns)
            
            # Layer: PCR and Spot (Surgical Price/Sentiment Gate)
            sentiment_cols = [c for c in audit_df.columns if "PCR" in c or c == "Spot"]
            for col in sentiment_cols:
                # Force strictly numeric float64 arrays
                vals = pd.to_numeric(audit_df[col], errors='coerce').fillna(0).astype('float64').values
                prev = pd.Series(vals).shift(1, fill_value=0).values.astype('float64')
                
                # Manual Gate: Pre-allocate zero-filled float array
                pct_change = np.zeros_like(vals, dtype='float64')
                mask = (prev != 0)
                if mask.any():
                    pct_change[mask] = ((vals[mask] - prev[mask]) / prev[mask]) * 100
                
                pct_change_s = pd.Series(pct_change, index=audit_df.index)
                styles_df.loc[pct_change_s >= spot_pcr_sens, col] += 'background-color: rgba(0, 230, 118, 0.4);'
                styles_df.loc[pct_change_s <= -spot_pcr_sens, col] += 'background-color: rgba(255, 82, 82, 0.4);'
            
            # Layer: Wall-Strength S/R (Heavy-Duty Contract Gate)
            # Support Walls: Green Alerts (Put OI Build-up)
            for col in ["Major Support", "Immediate Support"]:
                oi_col = f"{col} OI"
                if oi_col in audit_df.columns:
                    vals = pd.to_numeric(audit_df[oi_col], errors='coerce').fillna(0).astype('float64').values
                    prev = pd.Series(vals).shift(1, fill_value=0).values.astype('float64')
                    
                    oi_change = np.zeros_like(vals, dtype='float64')
                    mask = (prev != 0)
                    if mask.any():
                        oi_change[mask] = ((vals[mask] - prev[mask]) / prev[mask]) * 100
                    
                    oi_change_s = pd.Series(oi_change, index=audit_df.index)
                    styles_df.loc[oi_change_s >= contract_sens, col] += 'background-color: rgba(0, 230, 118, 0.4);'
                    styles_df.loc[oi_change_s <= -contract_sens, col] += 'background-color: rgba(0, 230, 118, 0.15);'

            # Resistance Walls: Red Alerts (Call OI Build-up)
            for col in ["Major Resistance", "Immediate Resistance"]:
                oi_col = f"{col} OI"
                if oi_col in audit_df.columns:
                    vals = pd.to_numeric(audit_df[oi_col], errors='coerce').fillna(0).astype('float64').values
                    prev = pd.Series(vals).shift(1, fill_value=0).values.astype('float64')
                    
                    oi_change = np.zeros_like(vals, dtype='float64')
                    mask = (prev != 0)
                    if mask.any():
                        oi_change[mask] = ((vals[mask] - prev[mask]) / prev[mask]) * 100
                        
                    oi_change_s = pd.Series(oi_change, index=audit_df.index)
                    styles_df.loc[oi_change_s >= contract_sens, col] += 'background-color: rgba(255, 82, 82, 0.4);'
                    styles_df.loc[oi_change_s <= -contract_sens, col] += 'background-color: rgba(0, 230, 118, 0.15);'

            # 3. Final View Assembly (Hide Alpha and OI utility columns)
            final_cols = [c for c in strategic_order if c in audit_df.columns]
            
            # Professional Formatting Layer
            fmt_dict = {c: "{:.3f}" for c in final_cols if "PCR" in c}
            fmt_dict["Spot"] = "{:,.2f}"
            fmt_dict["Major Support"] = "{:,.0f}"
            fmt_dict["Major Resistance"] = "{:,.0f}"
            fmt_dict["Immediate Support"] = "{:,.0f}"
            fmt_dict["Immediate Resistance"] = "{:,.0f}"
            
            styled_df = audit_df[final_cols].style.format(fmt_dict).apply(lambda _: styles_df[final_cols], axis=None)
            st.dataframe(styled_df, width="stretch", hide_index=True)

            # --- NEW SECTION: Rupee and Oil Movement (Below Audit Table) ---
            st.markdown("---")
            st.markdown("### 📊 Rupee and Oil Movement")
            indic_evolution_df = db_manager.query_market_indicators(selected_date)
            
            if not indic_evolution_df.empty:
                fig_indic = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Dynamic USD/INR Color based on trend
                usd_inr_color = "#ff5252" # Default Red
                if len(indic_evolution_df) > 1:
                    last_val = indic_evolution_df["usd_inr"].iloc[-1]
                    prev_val = indic_evolution_df["usd_inr"].iloc[-2]
                    if last_val < prev_val:
                        usd_inr_color = "#00c853" # Green (Strengthening)
                    elif last_val > prev_val:
                        usd_inr_color = "#ff5252" # Red (Weakening)

                # USD/INR (Left Axis)
                fig_indic.add_trace(go.Scatter(x=indic_evolution_df["timestamp"], y=indic_evolution_df["usd_inr"],
                    name="USD/INR", line=dict(color=usd_inr_color, width=4)), secondary_y=False)
                
                # Crude (Right Axis) - Orange Shades (Thick)
                fig_indic.add_trace(go.Scatter(x=indic_evolution_df["timestamp"], y=indic_evolution_df["wti_crude"],
                    name="WTI Crude", line=dict(color='#ffab40', width=5)), secondary_y=True) # Bright Orange
                fig_indic.add_trace(go.Scatter(x=indic_evolution_df["timestamp"], y=indic_evolution_df["brent_crude"],
                    name="Brent Crude", line=dict(color='#ff6d00', width=5)), secondary_y=True) # Dark Orange
                
                fig_indic.update_layout(
                    template="plotly_dark", 
                    paper_bgcolor='#0e1117', 
                    plot_bgcolor='#0e1117', 
                    height=450, 
                    hovermode="x unified",
                    legend=dict(font=dict(color="white")),
                    xaxis=dict(title_font=dict(color="white"), tickfont=dict(color="white")),
                    yaxis=dict(title_font=dict(color="white"), tickfont=dict(color="white")),
                    yaxis2=dict(title_font=dict(color="white"), tickfont=dict(color="white"))
                )
                fig_indic.update_yaxes(title_text="USD/INR (₹)", secondary_y=False)
                fig_indic.update_yaxes(title_text="Crude ($)", secondary_y=True)
                
                st.plotly_chart(fig_indic, width="stretch")
            else:
                st.info("Waiting for Rupee and Oil movement history...")

    # --- Global Footer (Disclaimer) ---
    st.markdown("---")
    st.markdown(
        '<p style="color:#8b949e; font-size:0.75rem; text-align:center; opacity:0.6;">'
        '<b>⚠️ Risk Disclaimer:</b> OptEazy is for analytical and educational purposes only. '
        'NSE option chain data is sourced dynamically and may have delays. We are not responsible for any financial losses '
        'incurred from trades based on this application. Always verify with official NSE India feeds before making execution decisions.'
        '</p>', 
        unsafe_allow_html=True
    )
