import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from datetime import datetime

# === Page Configuration ===
st.set_page_config(page_title="EV Adoption Forecast", layout="wide", page_icon="🔋")

# === Custom Fonts & Styling ===
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Roboto:wght@300;400;500&display=swap');

    html, body, .stApp {
        background: linear-gradient(to right, #2c3e50, #3498db);
        color: #ffffff;
        font-family: 'Poppins', sans-serif;
    }
    .main-title {
        font-family: 'Poppins', sans-serif;
        text-align: center;
        font-size: 42px;
        font-weight: 700;
        margin-top: 30px;
        margin-bottom: 10px;
        color: #ffffff;
    }
    .subtitle {
        font-family: 'Roboto', sans-serif;
        text-align: center;
        font-size: 22px;
        font-weight: 400;
        margin-bottom: 30px;
        color: #d1eaff;
    }
    .stSelectbox label, .stMultiSelect label, .stTextInput label {
        font-weight: 600;
        font-size: 16px;
        color: #ffffff;
        font-family: 'Poppins', sans-serif;
    }
    .stMarkdown, .stDataFrame, .stText, .stSubheader, .stHeader {
        font-family: 'Roboto', sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

# === Title ===
st.markdown("<div class='main-title'>🔮 EV Adoption Forecast Tool</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Forecast EV growth across Washington counties over the next 3 years</div>", unsafe_allow_html=True)

# === Load Model and Data ===
model = joblib.load("forecasting_ev_model.pkl")

@st.cache_data
def load_data():
    df = pd.read_csv("preprocessed_ev_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    return df

df = load_data()

# === Image ===
st.image("ev-car-factory3.jpg", use_container_width=True)

# === County Selection ===
county_list = sorted(df['County'].dropna().unique().tolist())
county = st.selectbox("Choose a county", county_list)

if county not in df['County'].unique():
    st.warning(f"County '{county}' not found in dataset.")
    st.stop()

county_df = df[df['County'] == county].sort_values("Date")
county_code = county_df['county_encoded'].iloc[0]

# === Forecasting Logic ===
historical_ev = list(county_df['Electric Vehicle (EV) Total'].values[-6:])
cumulative_ev = list(np.cumsum(historical_ev))
months_since_start = county_df['months_since_start'].max()
latest_date = county_df['Date'].max()
forecast_horizon = 36
future_rows = []

for i in range(1, forecast_horizon + 1):
    forecast_date = latest_date + pd.DateOffset(months=i)
    months_since_start += 1
    lag1, lag2, lag3 = historical_ev[-1], historical_ev[-2], historical_ev[-3]
    roll_mean = np.mean([lag1, lag2, lag3])
    pct_change_1 = (lag1 - lag2) / lag2 if lag2 != 0 else 0
    pct_change_3 = (lag1 - lag3) / lag3 if lag3 != 0 else 0
    ev_growth_slope = np.polyfit(range(6), cumulative_ev[-6:], 1)[0]

    new_row = {
        'months_since_start': months_since_start,
        'county_encoded': county_code,
        'ev_total_lag1': lag1,
        'ev_total_lag2': lag2,
        'ev_total_lag3': lag3,
        'ev_total_roll_mean_3': roll_mean,
        'ev_total_pct_change_1': pct_change_1,
        'ev_total_pct_change_3': pct_change_3,
        'ev_growth_slope': ev_growth_slope
    }

    pred = model.predict(pd.DataFrame([new_row]))[0]
    future_rows.append({"Date": forecast_date, "Predicted EV Total": round(pred)})
    historical_ev.append(pred)
    historical_ev = historical_ev[-6:]
    cumulative_ev.append(cumulative_ev[-1] + pred)
    cumulative_ev = cumulative_ev[-6:]

# === Merge Historical and Forecasted ===
historical_cum = county_df[['Date', 'Electric Vehicle (EV) Total']].copy()
historical_cum['Cumulative EV'] = historical_cum['Electric Vehicle (EV) Total'].cumsum()
historical_cum['Source'] = 'Historical'

forecast_df = pd.DataFrame(future_rows)
forecast_df['Cumulative EV'] = forecast_df['Predicted EV Total'].cumsum() + historical_cum['Cumulative EV'].iloc[-1]
forecast_df['Source'] = 'Forecast'

combined = pd.concat([
    historical_cum[['Date', 'Cumulative EV', 'Source']],
    forecast_df[['Date', 'Cumulative EV', 'Source']]
], ignore_index=True)

# === Plot ===
st.subheader(f"📊 Cumulative EV Forecast for {county}")
fig, ax = plt.subplots(figsize=(12, 6))
for label, data in combined.groupby('Source'):
    ax.plot(data['Date'], data['Cumulative EV'], label=label, marker='o')
ax.set_title(f"Cumulative EV Trend - {county}", fontsize=14, color='white')
ax.set_xlabel("Date", color='white')
ax.set_ylabel("Cumulative EV Count", color='white')
ax.grid(True, alpha=0.3)
ax.set_facecolor("#1c1c1c")
fig.patch.set_facecolor('#1c1c1c')
ax.tick_params(colors='white')
ax.legend()
st.pyplot(fig)

# === Forecast Summary ===
historical_total = historical_cum['Cumulative EV'].iloc[-1]
forecasted_total = forecast_df['Cumulative EV'].iloc[-1]

if historical_total > 0:
    growth = ((forecasted_total - historical_total) / historical_total) * 100
    trend = "increase 📈" if growth > 0 else "decrease 📉"
    st.success(f"Forecasted EV growth in **{county}**: **{trend} of {growth:.2f}%** over 3 years.")
else:
    st.warning("Historical total is zero. Growth % cannot be calculated.")

# === Multi-county comparison ===
st.markdown("---")
st.subheader("📍 Compare up to 3 Counties")
multi_counties = st.multiselect("Select counties to compare", county_list, max_selections=3)

if multi_counties:
    all_data = []
    for cty in multi_counties:
        cty_df = df[df['County'] == cty].sort_values("Date")
        code = cty_df['county_encoded'].iloc[0]
        hist = list(cty_df['Electric Vehicle (EV) Total'].values[-6:])
        cum = list(np.cumsum(hist))
        months = cty_df['months_since_start'].max()
        last = cty_df['Date'].max()
        fut = []

        for i in range(1, forecast_horizon + 1):
            last += pd.DateOffset(months=1)
            months += 1
            lag1, lag2, lag3 = hist[-1], hist[-2], hist[-3]
            roll = np.mean([lag1, lag2, lag3])
            pct1 = (lag1 - lag2) / lag2 if lag2 != 0 else 0
            pct3 = (lag1 - lag3) / lag3 if lag3 != 0 else 0
            slope = np.polyfit(range(6), cum[-6:], 1)[0]

            row = {
                'months_since_start': months,
                'county_encoded': code,
                'ev_total_lag1': lag1,
                'ev_total_lag2': lag2,
                'ev_total_lag3': lag3,
                'ev_total_roll_mean_3': roll,
                'ev_total_pct_change_1': pct1,
                'ev_total_pct_change_3': pct3,
                'ev_growth_slope': slope
            }

            pred = model.predict(pd.DataFrame([row]))[0]
            fut.append({'Date': last, 'Predicted EV Total': pred})
            hist.append(pred)
            hist = hist[-6:]
            cum.append(cum[-1] + pred)
            cum = cum[-6:]

        hist_df = cty_df[['Date', 'Electric Vehicle (EV) Total']].copy()
        hist_df['Cumulative EV'] = hist_df['Electric Vehicle (EV) Total'].cumsum()
        fut_df = pd.DataFrame(fut)
        fut_df['Cumulative EV'] = fut_df['Predicted EV Total'].cumsum() + hist_df['Cumulative EV'].iloc[-1]
        fut_df['County'] = cty
        hist_df['County'] = cty

        combined_cty = pd.concat([
            hist_df[['Date', 'Cumulative EV', 'County']],
            fut_df[['Date', 'Cumulative EV', 'County']]
        ])
        all_data.append(combined_cty)

    df_combined = pd.concat(all_data)

    st.subheader("📈 Multi-County EV Forecast")
    fig, ax = plt.subplots(figsize=(14, 7))
    for cty, group in df_combined.groupby('County'):
        ax.plot(group['Date'], group['Cumulative EV'], marker='o', label=cty)
    ax.set_title("3-Year EV Forecast Comparison", fontsize=16, color='white')
    ax.set_xlabel("Date", color='white')
    ax.set_ylabel("Cumulative EVs", color='white')
    ax.grid(True, alpha=0.3)
    ax.set_facecolor("#1c1c1c")
    fig.patch.set_facecolor('#1c1c1c')
    ax.tick_params(colors='white')
    ax.legend()
    st.pyplot(fig)

    st.success("Forecast complete ✅")

st.markdown("Prepared for **AICTE Internship Cycle 2 by S4F**")


# === Footer using custom GitHub icon ===
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Great+Vibes&display=swap');

    .footer-container {
        text-align: center;
        margin-top: 60px;
        margin-bottom: 20px;
    }

    .footer-name {
        font-family: 'Great Vibes', cursive;
        font-size: 28px;
        color: orange;
        margin-bottom: 14px;
    }

    .footer-box {
        display: inline-block;
        background: rgba(0, 0, 0, 0.5);
        padding: 12px 30px;
        border-radius: 40px;
    }

    .footer-icons a {
        margin: 0 15px;
        display: inline-block;
        transition: transform 0.2s ease;
    }

    .footer-icons img {
        width: 34px;
        height: 34px;
        transition: transform 0.2s ease;
        filter: drop-shadow(0 0 3px #74C0FC);
    }

    .footer-icons a:hover img {
        transform: scale(1.15);
    }
    </style>

    <div class="footer-container">
        <div class="footer-name">Developed by Saaiem Salaar</div>
        <div class="footer-box">
            <div class="footer-icons">
                <a href="https://github.com/Salaar-Saaiem" target="_blank">
                    <img src="https://github.com/Salaar-Saaiem/EV-Adoption-Forecasting/blob/3d01e93cf36e370572fa0341821dd1507590f5d3/github.png?raw=true" alt="GitHub">
                </a>
                <a href="https://www.linkedin.com/in/salaarsaaiem525/" target="_blank">
                       <img src="https://github.com/Salaar-Saaiem/EV-Adoption-Forecasting/blob/3d01e93cf36e370572fa0341821dd1507590f5d3/linkedin.png?raw=true" alt="LinkedIn">
                </a>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

