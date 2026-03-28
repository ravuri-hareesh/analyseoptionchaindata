# NSE Pro Terminal: User & Analysis Guide 📖

This guide explains how to interpret the charts and manage the automated data feed for your Option Chain dashboard.

## 📊 1. Understanding the Charts

### A. Snapshot (Latest Analysis)
The first tab shows the **most recent bar chart** of Call vs Put Open Interest (OI).
-   **Green Bars**: Put Open Interest (Support).
-   **Red Bars**: Call Open Interest (Resistance).
-   **Strikes**: The strikes with the tallest bars are your major psychological levels.

### B. Price vs. Sentiment (Evolution Tab)
This chart correlates the Index price with the Put-Call Ratio (PCR).
-   **Spot Price (Yellow Bold)**: Shows the 10-20 point minute movements of the Nifty Index.
-   **PCR (Near Money) (Solid Blue)**: Calculated *only* for strikes within ±2% of the spot price. This is a "Fast" indicator for immediate sentiment.
-   **PCR (Market) (Dotted Blue)**: Calculated for the entire option chain. This is a "Slow" indicator for overall daily sentiment.
    -   *Interpretation*: If the Solid Blue line is crossing above the Dotted Blue line, it may indicate a bullish local shift.

### C. Wall Stability Tracking (Step Chart)
Instead of a smooth line, this uses a "Step" shape (`hv`) to track Support and Resistance.
-   **Major Resistance (Bold Red)**: The price level with the absolute maximum Call OI.
-   **Major Support (Bold Green)**: The price level with the absolute maximum Put OI.
-   **Why "Step"?**: In trading, barriers don't "drift"; they jump from one strike to another. The step chart helps you see exactly when a barrier "broke" or shifted to a new strike.

## 🟢 2. Monitoring the Scraper

### Scraper Status Box (Sidebar)
-   **SYNC SUCCESS (Green)**: Data was pulled within the last 10 minutes.
-   **DELAYED / IDLE (Red)**: No new data has arrived for 10+ minutes. 
-   **POST-MARKET (Final)**: Appears after 3:30 PM IST to indicate that the final market closing data has been successfully archived.

## ⏳ 3. Historical Archive (Time Travel)
The dashboard automatically organizes data by date. To view a previous day:
1.  Go to the Sidebar.
2.  Use the **"Market Analysis Date"** dropdown.
3.  Select any previous date (e.g., `2026-03-25`).
4.  The dashboard will instantly switch all snapshots and evolution trends to that specific day.

## 🛠️ 4. Manual Upload (Emergency Override)
If the automated scraper is blocked by NSE or your connection is down:
1.  Go to the NSE Option Chain website.
2.  Download the CSV manually.
3.  Use the **"Import Archive Data"** button in the sidebar.
4.  The dashboard will process your manual file and update today's trend instantly.

---
*Note: This tool is for analytical purposes. Always verify with live exchange feeds before taking trading decisions.*
