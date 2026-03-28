import sys
import streamlit as st
from pathlib import Path
from datetime import datetime, time as dtime
import time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

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

# --- Background Scraper Integration ---
@st.cache_resource
def start_background_scraper(symbol="NIFTY"):
    """Starts the scraper in a non-blocking background thread."""
    thread = threading.Thread(target=run_scraper, args=(symbol,), daemon=True)
    thread.start()
    return thread

# Start scraper immediately on launch
scraper_thread = start_background_scraper()

# --- Page Layout ---
# Page Configuration
st.set_page_config(
    page_title="NSE Pro Terminal",
    page_icon="📈",
    layout="wide",
)

# Load Custom CSS
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

# --- Sidebar Layout ---
with st.sidebar:
    st.markdown('<h2 style="color:#2962ff;">NSE PRO TERMINAL</h2>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Date Selection
    available_dates = get_available_dates()
    selected_date = st.selectbox("Market Analysis Date", options=available_dates, index=0)
    is_today = (selected_date == get_current_date_str())

    # Scraper Status Badge (Professional High-Highlight)
    st.markdown("---")
    st.markdown("### SYSTEM CONNECTIVITY")
    last_sync_time, is_recent = get_last_sync_info(selected_date)
    
    # Logic to handle post-market display
    now_ist = datetime.now().time()
    market_close = dtime(15, 30)
    
    if is_today:
        status_label = "LIVE FEED" if (is_recent and not (now_ist > market_close)) else \
                       "SYNC SUCCESS" if (is_recent and (now_ist > market_close)) else \
                       "DELAYED / IDLE"
        
        # Color & Pulse logic
        status_color = "#00d46a" if is_recent else "#ff5252"
        pulse_html = '<div class="status-pulse"></div>' if (is_recent and not (now_ist > market_close)) else ""
        
        # Target Expiry initialization
        if 'target_expiry' not in st.session_state:
            st.session_state.target_expiry = "Searching..."
        
        # Display using standard Streamlit components (styled via CSS for premium look)
        st.metric(
            label=f"Market Loop Sync ({st.session_state.target_expiry})", 
            value=status_label, 
            delta=f"Sync: {last_sync_time}",
            delta_color="normal" if is_recent else "inverse"
        )
        
        # Manual Force Pull Button
        if st.button("🔄 Get Fresh File"):
            # Priorities: 1. cURL Mirror, 2. Manual Cookie, 3. Automated Stealth
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
                    st.toast("Blocking detected. See 'Advanced' sidebar for manual fix.", icon="❌")
                    
                    # Live Error Inspector (Diagnostics)
                    with st.expander("🔍 View Raw Error Details (Technical)"):
                        st.info("This is the exact message NSE returned to our script.")
                        st.code(msg, language="text")
                        if "403" in msg:
                            st.warning("⚠️ Access Denied (403): NSE's firewall definitely knows we are a script. Use the 'Absolute Zero' cURL Mirror below.")
                        elif "429" in msg:
                            st.warning("⚠️ Rate Limited (429): You are clicking too fast! Wait 2 minutes.")
                        elif "No response" in msg:
                            st.error("🔌 Connection Dropped: NSE closed the socket. This usually means an IP-level block. Try a mobile hotspot.")

        # --- THE ABSOLUTE ZERO BACKUP SECTION ---
        with st.sidebar.expander("🛡️ THE ABSOLUTE ZERO (Mirror Mode)", expanded=False):
            st.warning("Only use this if ALL other sync methods fail.")
            st.markdown("""
            **How to mirror your browser (100% Reliable):**
            1. Open [NSE Option Chain](https://www.nseindia.com/option-chain) in Chrome.
            2. Press `F12` -> **Network** tab.
            3. Refresh the page or click **'Download (.csv)'**.
            4. Right-click the request (look for `option-chain` or `indices`).
            5. Select **Copy** -> **Copy as cURL (bash)**.
            6. Paste the entire string below.
            """)
            curl_val = st.text_area(
                "Paste cURL (bash) here", 
                key="curl_command_input",
                placeholder="curl 'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY' ...",
                height=150
            )
            
            if curl_val:
                if st.button("🔗 Apply & Sync Now", use_container_width=True):
                    with st.status("Validating cURL Identity...", expanded=True) as status:
                        success, msg, target_expiry = fetch_and_save(symbol="NIFTY", curl_command=curl_val)
                        if success:
                            st.session_state.target_expiry = target_expiry
                            status.update(label=f"Success! {msg}", state="complete", expanded=True)
                            st.toast("Mirror Mode Active!", icon="🎯")
                            time.sleep(1)
                            st.rerun()
                        else:
                            status.update(label=f"Mirror Failed: {msg}", state="error", expanded=True)
                            st.error("Identity rejected. Try copying a fresh cURL.")

        with st.sidebar.expander("🛠️ Advanced / Cookie Backup"):
            st.text_input(
                "Manual NSE Cookie", 
                key="manual_cookie_input",
                placeholder="Paste 'Cookie:' value here...",
            )

        if not is_recent:
            if now_ist > market_close:
                st.info("🌙 Post-Market: Last final data was successfully captured.")
            else:
                st.warning("⚠️ Scraper is lagging behind market time.")
    else:
        st.info(f"Archive Mode: {selected_date}")

    st.markdown("---")
    
    # Uploads
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
        st.info("📊 Awaiting data... The background scraper will populate this soon.")
    else:
        latest_file = input_files[0]
        st.markdown(f"### Current Market Profile: {latest_file.stem}")
        
        try:
            # 1. Load and Analyze on-the-fly
            df, s_col, c_col, p_col = load_option_chain(str(latest_file))
            res = compute_support_resistance(df, s_col, c_col, p_col, top_n=5, smooth_window=3)
            data = res["data"]
            
            # 2. Interactive Bar Chart (Premium Layout)
            fig_snapshot = go.Figure()
            
            # Put OI (Support)
            fig_snapshot.add_trace(go.Bar(
                x=data["strike"], y=data["pe_oi"], name="Put OI (Support)",
                marker_color='#00c853', opacity=0.8
            ))
            
            # Call OI (Resistance)
            fig_snapshot.add_trace(go.Bar(
                x=data["strike"], y=data["ce_oi"], name="Call OI (Resistance)",
                marker_color='#ff5252', opacity=0.8
            ))
            
            # Add Sentiment Levels (Vertical Lines)
            fig_snapshot.add_vline(x=res["max_support"].strike, line_width=3, line_dash="dash", line_color="#00c853", 
                                  annotation_text=f"MAJOR SUPPORT ({int(res['max_support'].strike)})")
            fig_snapshot.add_vline(x=res["max_resistance"].strike, line_width=3, line_dash="dash", line_color="#ff5252",
                                  annotation_text=f"MAJOR RESISTANCE ({int(res['max_resistance'].strike)})")

            fig_snapshot.update_layout(
                title=dict(text="Open Interest Distribution", font=dict(size=20, color="#8b949e")),
                template="plotly_dark", 
                paper_bgcolor='#0e1117', 
                plot_bgcolor='#0e1117',
                hovermode="x unified",
                barmode='group',
                height=600,
                xaxis=dict(title="Strike Price", gridcolor='#30363d'),
                yaxis=dict(title="Open Interest (Contracts)", gridcolor='#30363d'),
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
            )
            
            st.plotly_chart(fig_snapshot, use_container_width=True)
            
            # 3. Tactical Table
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🛡️ Support Walls")
                supp_df = pd.DataFrame([{"Strike": l.strike, "OI": l.pe_oi} for l in res["top_support"]])
                st.dataframe(supp_df, hide_index=True, use_container_width=True)
            with col2:
                st.markdown("#### 🏰 Resistance Walls")
                res_df = pd.DataFrame([{"Strike": l.strike, "OI": l.ce_oi} for l in res["top_resistance"]])
                st.dataframe(res_df, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"Snapshot Analysis Error: {e}")
            st.info("The file format might be slightly different. Retrying with alternative parser...")

# --- EVOLUTION TREND SECTION ---
@st.cache_data(ttl=300) # Cache for 5 mins to ensure fast tab switching
def get_cached_evolution(input_dir_path: str):
    # Get all CSV files in the directory
    fpaths = sorted(list(Path(input_dir_path).glob("*.csv")), key=os.path.getmtime)
    if not fpaths:
        return pd.DataFrame()
    return compute_evolution_data(fpaths, load_option_chain)

with tab_evolution:
    st.subheader(f"📈 Evolution Trend ({selected_date})")
    
    with st.status("Analyzing historical snapshots...", expanded=False) as status:
        evolution_df = get_cached_evolution(str(input_dir))
        status.update(label="Evolution analysis complete!", state="complete")
    
    if evolution_df.empty:
        st.info("Accumulating data points... Evolution trend requires at least 2 analysis snapshots.")
    else:
        try:
            # 1. Price Sentiment
            fig_price = make_subplots(specs=[[{"secondary_y": True}]])
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Spot"], name="Spot Price", mode='lines+markers', line=dict(color='#ffd700', width=4)), secondary_y=False)
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Ranged (2%)"], name="PCR (Near Money)", line=dict(color='#2962ff', width=3)), secondary_y=True)
            fig_price.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["PCR Overall"], name="PCR (Market)", line=dict(color='#2962ff', width=1.5, dash='dot')), secondary_y=True)
            
            fig_price.update_layout(title="Sentiment Correlation", template="plotly_dark", paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', hovermode="x unified", height=450, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
            fig_price.update_yaxes(gridcolor='#30363d', zerolinecolor='#30363d')
            st.plotly_chart(fig_price, use_container_width=True)
            
            # 2. Barriers
            fig_lv = go.Figure()
            fig_lv.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Major Resistance"], name="Major Res.", line=dict(color='#ff5252', width=3), line_shape='hv'))
            fig_lv.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Major Support"], name="Major Supp.", line=dict(color='#00c853', width=3), line_shape='hv'))
            fig_lv.add_trace(go.Scatter(x=evolution_df["Timestamp"], y=evolution_df["Spot"], name="Spot Level", line=dict(color='#ffd700', width=1, dash='dash')))

            fig_lv.update_layout(title="Wall Stability Tracking", template="plotly_dark", paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', hovermode="x unified", height=500, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
            fig_lv.update_yaxes(gridcolor='#30363d', zerolinecolor='#30363d')
            st.plotly_chart(fig_lv, use_container_width=True)

            # Data Summary (styled dataframe)
            st.markdown("### Tactical Overview")
            st.dataframe(evolution_df.set_index("Timestamp"), use_container_width=True)
            
        except Exception as e:
            st.error(f"Evolution Plotting Error: {e}")
