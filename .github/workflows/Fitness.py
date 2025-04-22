from flask import Flask, render_template_string, request, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            minutes_done REAL,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Call init_db when starting the app
init_db()

# Save progress to the database
def save_progress(minutes):
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO progress (minutes_done, date)
        VALUES (?, ?)
    ''', (minutes, date.today().isoformat()))
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def fitness():
    page = '''
    {% raw %}
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Fitness App</title>

        <script src="https://cdn.jsdelivr.net/npm/vue@3.2.45/dist/vue.global.prod.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css" rel="stylesheet" />
    </head>
    <body>
        <div id="app" class="container mt-5">
            <h1 class="title is-3">Daily Workout Tracker</h1>

            <div class="mb-5">
                <canvas id="progressChart" height="100"></canvas>
            </div>

            <div v-if="loading">Loading exercises...</div>

            <div v-else class="columns is-multiline">
                <div class="column is-half" v-for="exercise in exercises" :key="exercise.id">
                    <div class="card">
                        <div class="card-image" v-if="exercise.image">
                            <figure class="image is-4by3">
                                <img :src="exercise.image" alt="Exercise Image">
                            </figure>
                        </div>
                        <div class="card-content">
                            <p class="title is-5">{{ exercise.name }}</p>
                            <p class="subtitle is-6" v-html="exercise.description"></p>

                            <div class="block">
                                <p>Time left: {{ exercise.timer }}s</p>
                                <button class="button is-success" @click="startTimer(exercise)">Start</button>
                            </div>

                            <progress class="progress is-info" :value="exercise.timer" max="30"></progress>
                        </div>
                    </div>
                </div>
            </div>

            <div class="box" v-if="history.length">
                <h2 class="subtitle">Previous Workouts</h2>
                <ul>
                    <li v-for="item in history" :key="item[0]">
                        {{ item[2] }} ({{ item[1] }} min)
                    </li>
                </ul>
            </div>

        </div>

        <script>
        const { createApp, ref, onMounted } = Vue;

        createApp({
            setup() {
                const exercises = ref([]);
                const loading = ref(true);
                const dailyGoal = 5;
                const minutesDone = ref(0);
                let chart = null;
                const history = ref([]);

                const fetchData = async () => {
                    try {
                        const [exRes, imgRes] = await Promise.all([
                            axios.get("https://wger.de/api/v2/exercise/?language=2&limit=5"),
                            axios.get("https://wger.de/api/v2/exerciseimage/?limit=100")
                        ]);

                        const imageMap = {};
                        imgRes.data.results.forEach(img => {
                            imageMap[img.exercise] = img.image;
                        });

                        exercises.value = exRes.data.results.map(ex => ({
                            ...ex,
                            image: imageMap[ex.id] || null,
                            favorite: false,
                            timer: 30,
                            interval: null
                        }));
                    } catch (err) {
                        console.error("Error fetching data", err);
                    } finally {
                        loading.value = false;
                        updateChart();
                    }
                };

                const startTimer = (exercise) => {
                    if (exercise.interval) return;

                    exercise.interval = setInterval(() => {
                        if (exercise.timer > 0) {
                            exercise.timer--;
                        } else {
                            clearInterval(exercise.interval);
                            exercise.interval = null;
                            minutesDone.value += 0.5;

                            axios.post('/save_progress', {
                                minutes_done: 0.5
                            }).then(() => {
                                console.log("Progress saved!");
                            }).catch(err => {
                                console.error("Failed to save progress", err);
                            });

                            updateChart();
                        }
                    }, 1000);
                };

                const updateChart = () => {
                    const percent = Math.min((minutesDone.value / dailyGoal) * 100, 100);

                    if (!chart) {
                        chart = new Chart(document.getElementById("progressChart"), {
                            type: "doughnut",
                            data: {
                                labels: ["Completed", "Remaining"],
                                datasets: [{
                                    data: [percent, 100 - percent],
                                    backgroundColor: ["#48c774", "#eee"]
                                }]
                            },
                            options: {
                                plugins: {
                                    legend: {
                                        display: true
                                    }
                                }
                            }
                        });
                    } else {
                        chart.data.datasets[0].data = [percent, 100 - percent];
                        chart.update();
                    }
                };

                const fetchHistory = async () => {
                    try {
                        const res = await axios.get('/history');
                        history.value = res.data;
                        console.log("Fetched history", history.value);
                    } catch (err) {
                        console.error("Error loading history", err);
                    }
                };

                onMounted(() => {
                    fetchData();
                    fetchHistory(); // Fetch history on load
                });

                return {
                    exercises,
                    loading,
                    startTimer,
                    history
                };
            }
        }).mount("#app");
        </script>
    </body>
    </html>
    {% endraw %}
    '''
    return render_template_string(page)

# API to save progress
@app.route('/save_progress', methods=['POST'])
def save():
    data = request.get_json()

    # Debugging: Check what data is being sent
    print("Received data:", data)

    # Safely extract values
    minutes_done = data.get('minutes_done')

    # Check if the required data is present
    if minutes_done is None:
        return jsonify({"status": "error", "message": "Missing 'minutes_done'"}), 400

    # Save to database if minutes_done is present
    save_progress(minutes_done)
    return jsonify({"status": "success"})

# API to fetch workout history
@app.route('/history')
def history():
    conn = sqlite3.connect('fitness.db')
    c = conn.cursor()
    c.execute('SELECT * FROM progress ORDER BY date DESC')
    data = c.fetchall()
    conn.close()
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
