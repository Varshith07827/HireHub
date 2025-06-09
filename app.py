from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random

app = Flask(__name__,template_folder='templates',static_folder='static')
app.secret_key = 'your_secret_key'

DATABASE_PATH = 'database.db'

def get_db_connection():
        return sqlite3.connect(DATABASE_PATH)

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                applicant_name TEXT NOT NULL,
                applicant_email TEXT NOT NULL,
                applicant_resume TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        ''')

        conn.commit()

def is_logged_in():
    return 'user_id' in session

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Check if user_id exists in session
            flash('You need to be logged in to access this page.')
            return redirect(url_for('login', next=request.url))  # Store the URL user was trying to visit
        return f(*args, **kwargs)
    return decorated_function

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            conn.close()
            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already taken. Please choose another.')
            return redirect(url_for('signup'))

    return render_template('sign_up.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password): 
            session['user_id'] = user[0]  
            session['username'] = user[1]  
            flash('Login successful!')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        flash('Please log in to access the dashboard.')
        return redirect(url_for('login', next=request.url))  # Store the URL user was trying to visit

    user_id = session['user_id']  # Get the logged-in user's ID
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE user_id = ?", (user_id,))
        jobs = cursor.fetchall()

    return render_template('dashboard.html', username=session['username'], jobs=jobs)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/main')
def page():
    return render_template('main.html')

@app.route('/')
def home():
    return render_template('main.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session: 
        flash('Please log in to post a job.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        user_id = session['user_id']  
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(''' 
            INSERT INTO jobs (title, description, requirements, user_id) 
            VALUES (?, ?, ?, ?)
        ''', (title, description, requirements, user_id))
        conn.commit()
        conn.close()
        
        flash('Job posted successfully!')
        return redirect(url_for('home'))

    return render_template('post_job.html')

@app.route('/try_new_job')
@login_required
def try_new_job():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM jobs')
    job_ids = cursor.fetchall()

    if not job_ids:
        flash('No jobs available at the moment.')
        return redirect(url_for('home'))

    random_job_id = random.choice(job_ids)[0]
    conn.close()

    return redirect(url_for('job_detail', job_id=random_job_id))

@app.route('/job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def job_detail(job_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()

    if request.method == 'POST':
        applicant_name = request.form['name']
        applicant_email = request.form['email']
        applicant_resume = request.form['resume']

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO applications (job_id, applicant_name, applicant_email, applicant_resume) VALUES (?, ?, ?, ?)", 
                           (job_id, applicant_name, applicant_email, applicant_resume))
            conn.commit()

        flash("Application submitted successfully!", "success")
        return redirect(url_for('home')) 

    return render_template('job_detail.html', job=job)

@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if the job exists and belongs to the logged-in user
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()

        if job is None:
            flash('Job not found.')
            return redirect(url_for('dashboard'))

        if job[4] != session['user_id']:
            flash('You do not have permission to delete this job.')
            return redirect(url_for('dashboard'))

        # Perform the deletion
        cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        flash('Job deleted successfully!')
    except Exception as e:
        flash(f'An error occurred while deleting the job: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/jobs')
def jobs():
    """Fetch and display all jobs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs')
    jobs = cursor.fetchall() 
    conn.close()

    return render_template('view_jobs.html', jobs=jobs)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)