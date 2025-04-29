from functools import wraps
from flask import Flask, render_template, request, redirect, session, url_for, flash
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'


# ---------- Database Connection ----------
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn


# ---------- User Authentication ----------
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()

        if action == 'login':
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            conn.close()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash("Logged in successfully!")
                return redirect('/')
            else:
                flash("Invalid login credentials.")
        elif action == 'signup':
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            try:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
                flash("Account created! You can now log in.")
            except sqlite3.IntegrityError:
                flash("Username already exists.")
            finally:
                conn.close()
    return render_template('auth.html', active_page='auth')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect('/')


# ---------- Login Required Decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.")
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function


# ---------- Routes ----------
@app.route('/')
def home():
    return render_template('home.html', active_page='home')


@app.route("/map")
def map_view():
    create_interactive_map()
    return render_template("map.html", active_page='map')
@app.route("/analytics")
def analytics():
    df = pd.read_csv('data/hajj_umrah_data.csv')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df['Hour'] = df['Timestamp'].dt.hour
    df['Month'] = df['Timestamp'].dt.strftime('%B')  # Full month name (e.g., January)

    # Dropdown filter
    selected_month = request.args.get('month')
    months = sorted(df['Month'].dropna().unique().tolist())

    if selected_month:
        df = df[df['Month'] == selected_month]

    # Pie Chart
    pie_df = df.dropna(subset=['Crowd_Density', 'Stress_Level'])
    pie_df['Crowd_Density'] = pie_df['Crowd_Density'].str.strip().str.capitalize()

    fig = make_subplots(rows=1, cols=3, specs=[[{'type': 'domain'}]*3],
                        subplot_titles=["Low Density", "Medium Density", "High Density"])
    densities = ['Low', 'Medium', 'High']
    for i, density in enumerate(densities):
        group = pie_df[pie_df['Crowd_Density'] == density]['Stress_Level'].value_counts()
        fig.add_trace(go.Pie(labels=group.index, values=group.values, name=density), row=1, col=i+1)
    fig.update_layout(title_text='Stress Level Distribution Within Each Crowd Density Group')

    area = px.area(df.groupby(['Hour', 'Activity_Type']).size().reset_index(name='Count'),
                   x='Hour', y='Count', color='Activity_Type',
                   title='Crowd Buildup by Activity Over Time')

    heatmap_data = df[df['Incident_Type'].notnull()].groupby('Hour').size().reset_index(name='Incident_Count')
    heatmap = px.bar(heatmap_data, x='Hour', y='Incident_Count', title='Incidents by Time of Day')

    ar_df = df.dropna(subset=['Queue_Time_minutes', 'Satisfaction_Rating', 'AR_Navigation_Success'])
    queue_box = px.box(ar_df, x='AR_Navigation_Success', y='Queue_Time_minutes', color='AR_Navigation_Success',
                       title='Queue Time by AR Navigation Use')
    satisfaction_box = px.box(ar_df, x='AR_Navigation_Success', y='Satisfaction_Rating', color='AR_Navigation_Success',
                              title='Satisfaction by AR Navigation Use')

    health_df = df[df['Health_Condition'].notnull()]
    bubble_data = (
        health_df.groupby(['Health_Condition', 'Temperature'])
        .agg({'Time_Spent_at_Location_minutes': 'mean', 'Health_Condition': 'count'})
        .rename(columns={'Health_Condition': 'Incident_Count'})
        .reset_index()
    )
    bubble = px.scatter(bubble_data, x='Temperature', y='Time_Spent_at_Location_minutes',
                        size='Incident_Count', color='Health_Condition',
                        title='Health Incidents vs. Environmental Stressors (Temperature)')

    age_health = df.groupby(['Age_Group', 'Nationality', 'Health_Condition']).size().reset_index(name='Count')
    stacked_bar = px.bar(age_health, x='Age_Group', y='Count', color='Health_Condition',
                         barmode='stack', facet_col='Nationality',
                         title='Age Group vs. Health Condition by Nationality')

    graphs = {
        "pie": fig.to_html(full_html=False),
        "area": area.to_html(full_html=False),
        "heatmap": heatmap.to_html(full_html=False),
        "queue_box": queue_box.to_html(full_html=False),
        "satisfaction_box": satisfaction_box.to_html(full_html=False),
        "bubble": bubble.to_html(full_html=False),
        "stacked_bar": stacked_bar.to_html(full_html=False),
    }

    return render_template("analytics.html", graphs=graphs, months=months,
                           selected_month=selected_month, active_page='analytics')

@app.route("/about")
def about():
    return render_template("about.html", active_page='about')
@app.route("/crowd-personality", methods=["GET", "POST"])
@login_required
def crowd_personality():
    if request.method == "POST":
        q1 = request.form.get("q1")  # lead
        q2 = request.form.get("q2")  # stress
        q3 = request.form.get("q3")  # plan
        q4 = request.form.get("q4")  # follow
        q5 = request.form.get("q5")  # avoid

        if not all([q1, q2, q3, q4, q5]):
            flash("Please answer all questions before submitting.")
            return redirect(url_for("crowd_personality"))

        # Scoring system (basic)
        scores = {
            "Strategist": 0,
            "Explorer": 0,
            "Follower": 0,
            "Observer": 0,
            "Responder": 0
        }

        if q3 == "Agree":
            scores["Strategist"] += 2
        if q1 == "Agree":
            scores["Responder"] += 1
            scores["Explorer"] += 1
        if q4 == "Agree":
            scores["Follower"] += 2
        if q5 == "Agree":
            scores["Observer"] += 2
        if q2 == "Disagree":
            scores["Responder"] += 2
        if q2 == "Agree":
            scores["Observer"] += 1
        if q1 == "Disagree":
            scores["Follower"] += 1
        if q3 == "Disagree":
            scores["Explorer"] += 1

        # Determine the personality with the highest score
        quiz_result = max(scores, key=scores.get)

        # Store in database
        user_id = session['user_id']
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO quiz_results (user_id, result) VALUES (?, ?)",
            (user_id, quiz_result)
        )
        conn.commit()
        conn.close()

        flash(f"Thanks for submitting your response! Your crowd personality is: {quiz_result}")
        return redirect(url_for("crowd_personality"))

    # Show quiz history
    conn = get_db_connection()
    history = conn.execute(
        "SELECT result, timestamp FROM quiz_results WHERE user_id = ? ORDER BY timestamp DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()

    return render_template("crowd_personality.html", show_quiz=True, history=history, active_page='quiz')

# ---------- Map Generation ----------
def create_interactive_map(csv_file_path="data/hajj_umrah_data.csv", output_html_path="static/interactive_map.html"):
    df = pd.read_csv(csv_file_path)
    expected_columns = ['Location_Lat', 'Location_Long', 'Crowd_Density']
    if not all(col in df.columns for col in expected_columns):
        print("Missing columns in CSV")
        return

    df = df.dropna(subset=expected_columns)
    color_map = {'High': 'red', 'Medium': 'orange', 'Low': 'green'}

    m = folium.Map(location=[21.4225, 39.8262], zoom_start=12)
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in df.iterrows():
        lat = row['Location_Lat']
        lon = row['Location_Long']
        density = str(row['Crowd_Density']).strip().capitalize()
        color = color_map.get(density, 'gray')

        folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=f"Density: {density}"
        ).add_to(marker_cluster)

    m.save(output_html_path)


# ---------- Init Database ----------
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            result TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

@app.context_processor
def inject_user():
    return dict(session=session)

@app.route("/personality-data")
def personality_data():
    conn = get_db_connection()
    results = conn.execute(
        "SELECT result, COUNT(*) as count FROM quiz_results GROUP BY result"
    ).fetchall()
    conn.close()
    return {row["result"]: row["count"] for row in results}

# ---------- Main ----------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
