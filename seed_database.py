import sqlite3
from datetime import datetime, timedelta

def seed_database():
    conn = sqlite3.connect('patient_portal.db')
    c = conn.cursor()
    
    # Clear existing data
    c.execute('DELETE FROM waiting_room')
    c.execute('DELETE FROM appointments')
    c.execute('DELETE FROM patients')
    
    # Sample patients
    patients = [
        ('John', 'Doe', '1980-05-15', '0771234567', '10115'),
        ('Jane', 'Smith', '1992-08-22', '0779876543', '10200'),
        ('Michael', 'Johnson', '1975-12-03', '0763456789', '10300'),
        ('Emily', 'Brown', '1988-03-17', '0754321098', '10400'),
        ('David', 'Williams', '1995-07-28', '0712345678', '10500')
    ]
    
    for patient in patients:
        c.execute('''INSERT INTO patients (first_name, last_name, dob, mobile, postcode)
                     VALUES (?, ?, ?, ?, ?)''', patient)
    
    conn.commit()
    
    # Sample appointments for today and future dates
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    appointments = [
        # Today's appointments
        (1, today, '09:00', 'Dr. Anderson', 'scheduled', None),
        (2, today, '09:30', 'Dr. Peterson', 'scheduled', None),
        (3, today, '10:00', 'Dr. Anderson', 'scheduled', None),
        (4, today, '10:30', 'Dr. Chen', 'scheduled', None),
        (5, today, '11:00', 'Dr. Peterson', 'scheduled', None),
        
        # Future appointments
        (1, tomorrow, '14:00', 'Dr. Anderson', 'scheduled', 'Follow-up visit'),
        (2, next_week, '09:00', 'Dr. Chen', 'scheduled', 'Annual checkup'),
        (3, next_week, '11:30', 'Dr. Peterson', 'scheduled', None),
    ]
    
    for appt in appointments:
        c.execute('''INSERT INTO appointments 
                     (patient_id, appt_date, appt_time, doctor, status, notes)
                     VALUES (?, ?, ?, ?, ?, ?)''', appt)
    
    conn.commit()
    conn.close()
    
    print("✅ Database seeded successfully!")
    print("\n📋 Sample patients for testing:")
    print("-" * 70)
    print("1. John Doe - DOB: 1980-05-15, Mobile: 0771234567, Postcode: 10115")
    print("2. Jane Smith - DOB: 1992-08-22, Mobile: 0779876543, Postcode: 10200")
    print("3. Michael Johnson - DOB: 1975-12-03, Mobile: 0763456789, Postcode: 10300")
    print("4. Emily Brown - DOB: 1988-03-17, Mobile: 0754321098, Postcode: 10400")
    print("5. David Williams - DOB: 1995-07-28, Mobile: 0712345678, Postcode: 10500")
    print("-" * 70)
    print(f"\n🗓️  All patients have appointments scheduled for today ({today})")
    print("   Use their details to test the check-in portal!\n")

if __name__ == '__main__':
    seed_database()
