import pandas as pd
import plotly.graph_objects as go
from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    # Load data
    df = pd.read_csv("data/hajj_umrah_data.csv")

    # Debugging: Check first 5 rows
    print("\n🔹 First 5 rows of data:")
    print(df.head())

    # Ensure numeric data
    df['Location_Lat'] = pd.to_numeric(df['Location_Lat'], errors='coerce')
    df['Location_Long'] = pd.to_numeric(df['Location_Long'], errors='coerce')
    df['Crowd_Density'] = pd.to_numeric(df['Crowd_Density'], errors='coerce')

    # Remove NaN values
    df_clean = df.dropna(subset=['Location_Lat', 'Location_Long', 'Crowd_Density'])

    print(f"\n✅ Total valid data points: {len(df_clean)}")
    print("Valid data points (Lat, Long, Density):")
    print(df_clean[['Location_Lat', 'Location_Long', 'Crowd_Density']].head())

    # Create 3D map using scattermapbox
    fig = go.Figure(go.Scattermapbox(
        lat=df_clean['Location_Lat'],
        lon=df_clean['Location_Long'],
        mode='markers',
        marker=dict(
            size=df_clean['Crowd_Density'] * 10,  # Adjust size scale to make markers visible
            color=df_clean['Crowd_Density'],  # Color by crowd density
            colorscale='Viridis',  # Color scale for density
            colorbar=dict(title='Crowd Density')
        ),
        text=df_clean['Crowd_Density'],  # Tooltip for crowd density
        hoverinfo='text'
    ))

    # Update map layout for 3D visualization
    fig.update_layout(
        mapbox=dict(
            accesstoken="your-mapbox-access-token",  # Replace with your Mapbox token
            center=dict(lat=21.4225, lon=39.8262),  # Center map around Mecca
            zoom=15,  # Set zoom level
            style="open-street-map",  # Style the map (e.g., 'open-street-map', 'satellite')
            pitch=45,  # Set the angle of the map for a 3D effect
            bearing=0  # Set map rotation if necessary
        ),
        title="Crowd Density 3D Map - Mecca & Madina",
        template='plotly',
        hovermode="closest"
    )

    # Save heatmap inside static folder
    heatmap_path = "static/heatmap.html"
    fig.write_html(heatmap_path)

    print(f"✅ 3D Heatmap saved at {heatmap_path}\n")

    return render_template("index.html")  # Make sure to load index.html

if __name__ == "__main__":
    app.run(debug=True, port=4997)
