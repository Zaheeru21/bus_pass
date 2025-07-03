from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database connection
def get_db_connection():
    conn = sqlite3.connect('bus_pass.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize Database Tables (Run once at app start)
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            password TEXT
        )
    ''')

    # Bus pass requests table
    c.execute('''
        CREATE TABLE IF NOT EXISTS bus_pass_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            old_pass_no TEXT,
            id_proof_path TEXT,
            old_pass_copy_path TEXT,
            status TEXT DEFAULT 'Pending',
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # Admin table
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    # Insert default admin credentials (if not exists)
    c.execute('INSERT OR IGNORE INTO admin (username, password) VALUES (?, ?)', ('admin', 'admin123'))

    conn.commit()
    conn.close()

# Run DB initializer
init_db()

# ------------------- Routes -------------------

# Home Page
@app.route('/')
def index():
    return render_template('index.html')

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)',
                         (name, email, phone, password))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists! Try another.')
        finally:
            conn.close()
    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            flash('Login successful! Now you can apply for renewal.')
            return redirect(url_for('renew_pass'))
        else:
            flash('Invalid email or password.')
    return render_template('login.html')

# Bus Pass Renewal Form
@app.route('/renew', methods=['GET', 'POST'])
def renew_pass():
    if request.method == 'POST':
        name = request.form['name']
        old_pass_no = request.form['old_pass_no']

        id_proof = request.files['id_proof']
        id_proof_path = os.path.join(app.config['UPLOAD_FOLDER'], id_proof.filename)
        id_proof.save(id_proof_path)

        old_pass_copy_path = ''
        if 'old_pass_copy' in request.files and request.files['old_pass_copy'].filename != '':
            old_pass_copy = request.files['old_pass_copy']
            old_pass_copy_path = os.path.join(app.config['UPLOAD_FOLDER'], old_pass_copy.filename)
            old_pass_copy.save(old_pass_copy_path)

        conn = get_db_connection()
        user = conn.execute('SELECT user_id FROM users WHERE name = ?', (name,)).fetchone()
        if user:
            conn.execute('INSERT INTO bus_pass_requests (user_id, old_pass_no, id_proof_path, old_pass_copy_path) VALUES (?, ?, ?, ?)',
                         (user['user_id'], old_pass_no, id_proof_path, old_pass_copy_path))
            conn.commit()
            flash('Renewal request submitted successfully!')
        else:
            flash('User not found. Please register first.')
        conn.close()
    return render_template('renew_pass.html')

# Check Status
@app.route('/status', methods=['GET', 'POST'])
def status():
    status_message = ''
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT user_id FROM users WHERE email = ?', (email,)).fetchone()
        if user:
            request_row = conn.execute('SELECT status FROM bus_pass_requests WHERE user_id = ? ORDER BY request_date DESC LIMIT 1',
                                       (user['user_id'],)).fetchone()
            if request_row:
                status_message = f"Your latest application status: {request_row['status']}"
            else:
                status_message = 'No application found.'
        else:
            status_message = 'Email not registered.'
        conn.close()
    return render_template('status.html', status_message=status_message)

# Admin Login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM admin WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

        if admin:
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.')
    return render_template('admin_login.html')

# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    conn = get_db_connection()
    requests = conn.execute('''
        SELECT r.request_id, u.name, r.old_pass_no, r.status 
        FROM bus_pass_requests r
        JOIN users u ON r.user_id = u.user_id
    ''').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', requests=requests)

# Admin: Update Request Status (Approve/Reject)
@app.route('/update_status/<int:request_id>/<string:new_status>')
def update_status(request_id, new_status):
    conn = get_db_connection()
    conn.execute('UPDATE bus_pass_requests SET status = ? WHERE request_id = ?', (new_status, request_id))
    conn.commit()
    conn.close()
    flash(f'Request {request_id} status updated to {new_status}.')
    return redirect(url_for('admin_dashboard'))

# Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
