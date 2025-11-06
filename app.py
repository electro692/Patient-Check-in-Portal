from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
CORS(app)

# Database setup
def init_db():
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    # Patients table
    c.execute('''CREATE TABLE IF NOT EXISTS patients
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  first_name TEXT NOT NULL,
                  last_name TEXT NOT NULL,
                  dob TEXT NOT NULL,
                  mobile TEXT,
                  postcode TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Appointments table
    c.execute('''CREATE TABLE IF NOT EXISTS appointments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  patient_id INTEGER,
                  appt_date TEXT NOT NULL,
                  appt_time TEXT NOT NULL,
                  doctor TEXT,
                  status TEXT DEFAULT 'scheduled',
                  checked_in_at TIMESTAMP,
                  notes TEXT,
                  FOREIGN KEY (patient_id) REFERENCES patients(id))''')
    
    # Waiting room table
    c.execute('''CREATE TABLE IF NOT EXISTS waiting_room
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  patient_id INTEGER,
                  appointment_id INTEGER,
                  checked_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT DEFAULT 'waiting',
                  FOREIGN KEY (patient_id) REFERENCES patients(id),
                  FOREIGN KEY (appointment_id) REFERENCES appointments(id))''')
    
    conn.commit()
    conn.close()

# Helper function to hash DOB for security
def hash_dob(dob):
    return hashlib.sha256(dob.encode()).hexdigest()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/checkin', methods=['POST'])
def checkin():
    data = request.json
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    dob = data.get('dob', '').strip()
    mobile = data.get('mobile', '').strip()
    postcode = data.get('postcode', '').strip()
    
    if not all([first_name, last_name, dob]) or not (mobile or postcode):
        return jsonify({'error': 'Please provide all required fields'}), 400
    
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    # Find patient
    query = '''SELECT p.*, a.id as appt_id, a.appt_date, a.appt_time, 
                      a.doctor, a.status, a.notes
               FROM patients p
               LEFT JOIN appointments a ON p.id = a.patient_id
               WHERE p.first_name = ? AND p.last_name = ? AND p.dob = ?'''
    
    params = [first_name, last_name, dob]
    
    if mobile:
        query += ' AND p.mobile = ?'
        params.append(mobile)
    elif postcode:
        query += ' AND p.postcode = ?'
        params.append(postcode)
    
    query += ' AND a.appt_date = ? ORDER BY a.appt_time'
    params.append(datetime.now().strftime('%Y-%m-%d'))
    
    c.execute(query, params)
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({'error': 'No appointment found for today with these details'}), 404
    
    patient_data = {
        'patient_id': result[0],
        'first_name': result[1],
        'last_name': result[2],
        'dob': result[3],
        'mobile': result[4],
        'postcode': result[5],
        'appointment': {
            'id': result[7],
            'date': result[8],
            'time': result[9],
            'doctor': result[10],
            'status': result[11],
            'notes': result[12]
        }
    }
    
    conn.close()
    return jsonify(patient_data), 200

@app.route('/api/confirm-checkin', methods=['POST'])
def confirm_checkin():
    data = request.json
    patient_id = data.get('patient_id')
    appointment_id = data.get('appointment_id')
    
    if not patient_id or not appointment_id:
        return jsonify({'error': 'Missing patient or appointment ID'}), 400
    
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    # Update appointment status
    c.execute('''UPDATE appointments 
                 SET status = 'checked_in', checked_in_at = ? 
                 WHERE id = ?''', 
              (datetime.now().isoformat(), appointment_id))
    
    # Add to waiting room
    c.execute('''INSERT INTO waiting_room (patient_id, appointment_id)
                 VALUES (?, ?)''', (patient_id, appointment_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Successfully checked in', 'status': 'in_waiting_room'}), 200

@app.route('/api/appointments/<int:patient_id>', methods=['GET'])
def get_appointments(patient_id):
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    c.execute('''SELECT id, appt_date, appt_time, doctor, status, notes
                 FROM appointments
                 WHERE patient_id = ? AND appt_date >= ?
                 ORDER BY appt_date, appt_time''',
              (patient_id, datetime.now().strftime('%Y-%m-%d')))
    
    appointments = []
    for row in c.fetchall():
        appointments.append({
            'id': row[0],
            'date': row[1],
            'time': row[2],
            'doctor': row[3],
            'status': row[4],
            'notes': row[5]
        })
    
    conn.close()
    return jsonify(appointments), 200

@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
def update_appointment(appointment_id):
    data = request.json
    new_date = data.get('date')
    new_time = data.get('time')
    
    if not new_date or not new_time:
        return jsonify({'error': 'Date and time required'}), 400
    
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    c.execute('''UPDATE appointments 
                 SET appt_date = ?, appt_time = ?, status = 'rescheduled'
                 WHERE id = ?''',
              (new_date, new_time, appointment_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Appointment updated successfully'}), 200

@app.route('/api/waiting-room', methods=['GET'])
def get_waiting_room():
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    c.execute('''SELECT w.id, p.first_name, p.last_name, 
                        w.checked_in_at, w.status, a.doctor, a.appt_time
                 FROM waiting_room w
                 JOIN patients p ON w.patient_id = p.id
                 JOIN appointments a ON w.appointment_id = a.id
                 WHERE w.status = 'waiting'
                 ORDER BY w.checked_in_at''')
    
    waiting_list = []
    for row in c.fetchall():
        waiting_list.append({
            'id': row[0],
            'patient_name': f"{row[1]} {row[2]}",
            'checked_in_at': row[3],
            'status': row[4],
            'doctor': row[5],
            'appt_time': row[6]
        })
    
    conn.close()
    return jsonify(waiting_list), 200

# HTML Template for frontend
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patient Check-in Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .alert-error {
            background: #fee;
            color: #c33;
            border: 1px solid #fcc;
        }
        .alert-success {
            background: #efe;
            color: #3c3;
            border: 1px solid #cfc;
        }
        .appointment-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin-top: 20px;
        }
        .appointment-card h3 {
            color: #667eea;
            margin-bottom: 15px;
        }
        .appt-detail {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .appt-detail:last-child {
            border-bottom: none;
        }
        .waiting-status {
            background: #4caf50;
            color: white;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            margin-top: 20px;
            font-weight: 600;
        }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 Patient Check-in</h1>
        <p class="subtitle">Please enter your details to check in</p>
        
        <div id="alertBox" class="hidden"></div>
        
        <form id="checkinForm">
            <div class="form-group">
                <label>First Name *</label>
                <input type="text" id="firstName" required>
            </div>
            
            <div class="form-group">
                <label>Last Name *</label>
                <input type="text" id="lastName" required>
            </div>
            
            <div class="form-group">
                <label>Date of Birth *</label>
                <input type="date" id="dob" required>
            </div>
            
            <div class="form-group">
                <label>Mobile Number</label>
                <input type="tel" id="mobile" placeholder="Optional">
            </div>
            
            <div class="form-group">
                <label>Postcode</label>
                <input type="text" id="postcode" placeholder="Optional">
            </div>
            
            <button type="submit" class="btn" id="submitBtn">Check In</button>
        </form>
        
        <div id="appointmentDetails" class="hidden"></div>
    </div>

    <script>
        const form = document.getElementById('checkinForm');
        const alertBox = document.getElementById('alertBox');
        const appointmentDetails = document.getElementById('appointmentDetails');
        const submitBtn = document.getElementById('submitBtn');

        function showAlert(message, type) {
            alertBox.className = `alert alert-${type}`;
            alertBox.textContent = message;
            alertBox.classList.remove('hidden');
            setTimeout(() => alertBox.classList.add('hidden'), 5000);
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const mobile = document.getElementById('mobile').value.trim();
            const postcode = document.getElementById('postcode').value.trim();
            
            if (!mobile && !postcode) {
                showAlert('Please provide either mobile number or postcode', 'error');
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Checking...';
            
            try {
                const response = await fetch('/api/checkin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        first_name: document.getElementById('firstName').value.trim(),
                        last_name: document.getElementById('lastName').value.trim(),
                        dob: document.getElementById('dob').value,
                        mobile: mobile,
                        postcode: postcode
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    displayAppointment(data);
                } else {
                    showAlert(data.error || 'Check-in failed', 'error');
                }
            } catch (error) {
                showAlert('Connection error. Please try again.', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Check In';
            }
        });

        async function displayAppointment(data) {
            appointmentDetails.innerHTML = `
                <div class="appointment-card">
                    <h3>Welcome, ${data.first_name}!</h3>
                    <div class="appt-detail">
                        <strong>Doctor:</strong>
                        <span>${data.appointment.doctor || 'TBA'}</span>
                    </div>
                    <div class="appt-detail">
                        <strong>Time:</strong>
                        <span>${data.appointment.time}</span>
                    </div>
                    <div class="appt-detail">
                        <strong>Status:</strong>
                        <span>${data.appointment.status}</span>
                    </div>
                    <button class="btn" onclick="confirmCheckin(${data.patient_id}, ${data.appointment.id})" style="margin-top: 20px;">
                        Confirm & Join Waiting Room
                    </button>
                </div>
            `;
            appointmentDetails.classList.remove('hidden');
            form.classList.add('hidden');
        }

        async function confirmCheckin(patientId, appointmentId) {
            try {
                const response = await fetch('/api/confirm-checkin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        patient_id: patientId,
                        appointment_id: appointmentId
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    appointmentDetails.innerHTML += `
                        <div class="waiting-status">
                            ✓ Checked In Successfully! You're in the waiting room.
                        </div>
                    `;
                    showAlert('Check-in complete!', 'success');
                } else {
                    showAlert(data.error || 'Failed to confirm check-in', 'error');
                }
            } catch (error) {
                showAlert('Connection error. Please try again.', 'error');
            }
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    init_db()
    print("Database initialized!")
    print("Server starting on http://localhost:5000")
    app.run(debug=True, port=5000)
