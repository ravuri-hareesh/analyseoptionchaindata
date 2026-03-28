# NSE Pro Terminal: Advanced Option Chain Suite 📈

A professional-grade, automated dashboard for real-time NSE Option Chain analysis. This tool transforms raw NSE data into actionable Support/Resistance barriers and sentiment indicators using high-fidelity Plotly visualizations and a TradingView-inspired dark theme.

## 🚀 Quickstart

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch the Dashboard**:
   ```bash
   python -m streamlit run app.py
   ```
   *The background scraper starts automatically on launch!*

## ✨ Key Features

- **Integrated Live Scraper**: Automatically fetches NIFTY data every 5 minutes during market hours (9:00 AM - 3:30 PM, Mon-Fri).
- **Near-The-Money (NTM) PCR**: A focused sentiment indicator targeting ±2% of the Spot price for precision signals.
- **Dynamic S/R Barriers**: Real-time "Step Chart" tracking of Major and Immediate Support/Resistance levels.
- **Multi-Day Archive**: Seamlessly "Time Travel" to view historical days' trends via the sidebar date selector.
- **Scraper Health Monitor**: Real-time pulsing status badge (🟢) shows live connectivity and data freshless.

## 📂 Architecture

- `app.py`: Main Streamlit UI and background thread manager.
- `nse_scraper.py`: Background worker for session-based data fetching.
- `analysis.py`: Core logic for PCR and S/R heuristics.
- `io_manager.py`: Handles date-based archiving in `input_file/` and `output/`.
- `style.css`: Professional modern dark theme with Glassmorphism.

## 📖 Usage Guidelines

For a detailed breakdown of how to interpret the charts and manage the data, please refer to the [USER_GUIDE.md](./USER_GUIDE.md).

---
*Optimized for professional traders and data-driven market analysis.*
