from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
import random
from functools import wraps

from models import Database, User, DoctorSlot, Appointment, OTP, Review

application = Flask(__name__)

app = application

app.secret_key = 'your-secret-key-change-this-in-production'
app.permanent_session_lifetime = timedelta(hours=24)

# Initialize database
db = Database()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'doctor':
            flash('Doctor access required', 'error')
            return redirect(url_for('patient_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions


# Public Routes
@app.route('/')
def index():
    doctors = User.get_doctors(db)
    return render_template('index.html', doctors=doctors)




import requests

AUTH_API = "https://w9j9sskln0.execute-api.us-east-1.amazonaws.com/prod"
PROJECT_DOMAIN = "ClinicAppointment"

HEADERS = {
    "Content-Type": "application/json",
    "X-Project-Domain": PROJECT_DOMAIN
}


@app.route('/patient/signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        phone = request.form['phone']

        try:
            response = requests.post(
                f"{AUTH_API}/auth/signup",
                headers=HEADERS,
                json={
                    "email": email,
                    "password": password,
                    "name": name
                },
                timeout=10
            )

            data = response.json()

            if response.status_code == 201:
                # Save in your current DB
                result = User.create_user(db, email, password, name, phone, 'patient')

                if result:
                    flash('Registration successful! Please login.', 'success')
                    return redirect(url_for('patient_login'))
                else:
                    flash('Account created but DB save failed.', 'error')

            elif response.status_code == 409:
                flash('Email already registered', 'error')
            else:
                flash(data.get("message", "Signup failed"), 'error')

        except Exception as e:
            print("Signup API error:", e)
            flash('Authentication service error', 'error')

    return render_template('patient/signup.html')






@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            response = requests.post(
                f"{AUTH_API}/auth/login",
                headers=HEADERS,
                json={
                    "email": email,
                    "password": password
                },
                timeout=10
            )

            data = response.json()

            if response.status_code == 200:
                session['user_id'] = data['id']
                session['user_email'] = data['email']
                session['user_name'] = data['name']
                session['user_type'] = 'patient'
                session['token'] = data['token']
                session.permanent = True

                flash('Login successful!', 'success')
                return redirect(url_for('patient_dashboard'))

            else:
                flash(data.get("message", "Invalid credentials"), 'error')

        except Exception as e:
            print("Login API error:", e)
            flash('Authentication service unavailable', 'error')

    return render_template('patient/login.html')



# @app.route('/patient/signup', methods=['GET', 'POST'])
# def patient_signup():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         name = request.form['name']
#         phone = request.form['phone']
        
#         existing = User.get_user_by_email(db, email)
#         if existing:
#             flash('Email already registered', 'error')
#             return redirect(url_for('patient_signup'))
        
#         result = User.create_user(db, email, password, name, phone, 'patient')
#         if result:
#             flash('Registration successful! Please login.', 'success')
#             return redirect(url_for('patient_login'))
#         else:
#             flash('Registration failed. Please try again.', 'error')
    
#     return render_template('patient/signup.html')

# @app.route('/patient/login', methods=['GET', 'POST'])
# def patient_login():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
        
#         user = User.verify_user(db, email, password)
#         if user and user['user_type'] == 'patient':
#             session['user_id'] = user['id']
#             session['user_email'] = user['email']
#             session['user_name'] = user['name']
#             session['user_type'] = 'patient'
#             session.permanent = True
#             flash('Login successful!', 'success')
#             return redirect(url_for('patient_dashboard'))
#         else:
#             flash('Invalid credentials', 'error')
    
#     return render_template('patient/login.html')




@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.verify_user(db, email, password)
        if user and user['user_type'] == 'doctor' :
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['user_type'] = 'doctor'
            session.permanent = True
            flash('Login successful!', 'success')
            return redirect(url_for('doctor_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('doctor/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# Patient Routes
@app.route('/patient/dashboard')
@login_required
def patient_dashboard():
    if session['user_type'] != 'patient':
        return redirect(url_for('doctor_dashboard'))
    
    appointments = Appointment.get_patient_appointments(db, session['user_id'])
    upcoming = [a for a in appointments if a['appointment_date'] >= datetime.now().date() and a['status'] in ['pending', 'confirmed']]
    past = [a for a in appointments if a['appointment_date'] < datetime.now().date() or a['status'] in ['completed', 'cancelled']]
    
    return render_template('patient/dashboard.html', 
                         upcoming=upcoming[:5], 
                         past=past[:5],
                         total=len(appointments))

@app.route('/patient/book', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if session['user_type'] != 'patient':
        return redirect(url_for('doctor_dashboard'))
    
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        slot_id = request.form['slot_id']
        symptoms = request.form.get('symptoms', '')
        notes = request.form.get('notes', '')
        
        slot = DoctorSlot.get_slot_by_id(db, slot_id)
        if slot and slot['status'] == 'available' and slot['booked_count'] < slot['max_patients']:
            result = Appointment.create_appointment(
                db, session['user_id'], doctor_id, slot_id,
                slot['slot_date'], slot['start_time'], symptoms, notes
            )
            if result:
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('patient_dashboard'))
            else:
                flash('Failed to book appointment', 'error')
        else:
            flash('Slot no longer available', 'error')
    
    doctors = User.get_doctors(db)
    return render_template('patient/book_appointment.html', doctors=doctors)

# @app.route('/patient/get_available_slots/<int:doctor_id>/<string:date>')
# @login_required
# def get_available_slots(doctor_id, date):
#     slots = DoctorSlot.get_available_slots(db, doctor_id, date)
#     return jsonify(slots)


@app.route('/patient/get_available_slots/<int:doctor_id>/<string:date>')
@login_required
def get_available_slots(doctor_id, date):
    slots = DoctorSlot.get_available_slots(db, doctor_id, date)

    cleaned_slots = []
    for slot in slots:
        slot_dict = dict(slot)

        # Convert non-JSON fields
        if 'slot_date' in slot_dict:
            slot_dict['slot_date'] = str(slot_dict['slot_date'])

        if 'start_time' in slot_dict:
            slot_dict['start_time'] = str(slot_dict['start_time'])

        if 'end_time' in slot_dict:
            slot_dict['end_time'] = str(slot_dict['end_time'])

        if 'duration_minutes' in slot_dict:
            slot_dict['duration_minutes'] = int(slot_dict['duration_minutes'])

        # Fix timedelta issue
        for key, value in slot_dict.items():
            if isinstance(value, timedelta):
                slot_dict[key] = value.total_seconds() // 60

        cleaned_slots.append(slot_dict)

    return jsonify(cleaned_slots)

@app.route('/patient/my_appointments')
@login_required
def my_appointments():
    if session['user_type'] != 'patient':
        return redirect(url_for('doctor_dashboard'))
    
    appointments = Appointment.get_patient_appointments(db, session['user_id'])
    return render_template('patient/my_appointments.html', appointments=appointments)

@app.route('/patient/cancel_appointment/<int:appointment_id>')
@login_required
def cancel_appointment(appointment_id):
    if session['user_type'] != 'patient':
        return redirect(url_for('doctor_dashboard'))
    
    result = Appointment.cancel_appointment(db, appointment_id)
    if result:
        flash('Appointment cancelled successfully', 'success')
    else:
        flash('Failed to cancel appointment', 'error')
    
    return redirect(url_for('my_appointments'))

# Doctor Routes
@app.route('/doctor/dashboard')
@login_required
@doctor_required
def doctor_dashboard():
    today = datetime.now().date()
    today_appointments = Appointment.get_doctor_appointments(db, session['user_id'], today)
    upcoming_appointments = Appointment.get_doctor_appointments(db, session['user_id'])
    
    # Get slots for today
    today_slots = DoctorSlot.get_doctor_slots(db, session['user_id'], today)
    
    # Get statistics
    all_appointments = Appointment.get_doctor_appointments(db, session['user_id'])
    total_patients = len(set([a['patient_id'] for a in all_appointments]))
    completed = len([a for a in all_appointments if a['status'] == 'completed'])
    cancelled = len([a for a in all_appointments if a['status'] == 'cancelled'])
    
    # Get rating
    rating = Review.get_doctor_rating(db, session['user_id'])
    
    return render_template('doctor/dashboard.html',
                         today_appointments=today_appointments[:5],
                         upcoming_appointments=upcoming_appointments[:10],
                         today_slots=today_slots,
                         total_appointments=len(all_appointments),
                         total_patients=total_patients,
                         completed=completed,
                         cancelled=cancelled,
                         rating=rating)

@app.route('/doctor/manage_slots')
@login_required
@doctor_required
def manage_slots():
    slots = DoctorSlot.get_doctor_slots(db, session['user_id'])
    return render_template('doctor/manage_slots.html', slots=slots)

@app.route('/doctor/create_slot', methods=['GET', 'POST'])
@login_required
@doctor_required
def create_slot():
    if request.method == 'POST':
        slot_date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        duration = int(request.form.get('duration', 30))
        max_patients = int(request.form.get('max_patients', 1))
        
        result = DoctorSlot.create_slot(db, session['user_id'], slot_date, 
                                       start_time, end_time, duration, max_patients)
        if result:
            flash('Slot created successfully', 'success')
            return redirect(url_for('manage_slots'))
        else:
            flash('Failed to create slot', 'error')
    
    return render_template('doctor/create_slot.html')

@app.route('/doctor/edit_slot/<int:slot_id>', methods=['GET', 'POST'])
@login_required
@doctor_required
def edit_slot(slot_id):
    slot = DoctorSlot.get_slot_by_id(db, slot_id)
    if not slot or slot['doctor_id'] != session['user_id']:
        flash('Slot not found', 'error')
        return redirect(url_for('manage_slots'))
    
    if request.method == 'POST':
        if slot['booked_count'] == 0:
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            max_patients = int(request.form['max_patients'])
            
            result = DoctorSlot.update_slot(db, slot_id, 
                                          start_time=start_time,
                                          end_time=end_time,
                                          max_patients=max_patients)
            if result:
                flash('Slot updated successfully', 'success')
            else:
                flash('Failed to update slot', 'error')
        else:
            flash('Cannot edit slot with existing bookings', 'error')
        
        return redirect(url_for('manage_slots'))
    
    return render_template('doctor/edit_slot.html', slot=slot)

@app.route('/doctor/delete_slot/<int:slot_id>')
@login_required
@doctor_required
def delete_slot(slot_id):
    slot = DoctorSlot.get_slot_by_id(db, slot_id)
    if slot and slot['doctor_id'] == session['user_id'] and slot['booked_count'] == 0:
        result = DoctorSlot.delete_slot(db, slot_id)
        if result:
            flash('Slot deleted successfully', 'success')
        else:
            flash('Failed to delete slot', 'error')
    else:
        flash('Cannot delete slot with existing bookings', 'error')
    
    return redirect(url_for('manage_slots'))

@app.route('/doctor/appointments')
@login_required
@doctor_required
def doctor_appointments():
    date = request.args.get('date')
    appointments = Appointment.get_doctor_appointments(db, session['user_id'], date)
    return render_template('doctor/appointments.html', appointments=appointments)

@app.route('/doctor/appointment/<int:appointment_id>')
@login_required
@doctor_required
def appointment_details(appointment_id):
    appointment = Appointment.get_appointment_by_id(db, appointment_id)
    if not appointment or appointment['doctor_id'] != session['user_id']:
        flash('Appointment not found', 'error')
        return redirect(url_for('doctor_appointments'))
    
    return render_template('doctor/appointment_details.html', appointment=appointment)

@app.route('/doctor/update_appointment/<int:appointment_id>', methods=['POST'])
@login_required
@doctor_required
def update_appointment(appointment_id):
    status = request.form.get('status')
    prescription = request.form.get('prescription')
    diagnosis = request.form.get('diagnosis')
    follow_up_date = request.form.get('follow_up_date')
    
    if status:
        result = Appointment.update_appointment_status(db, appointment_id, status)
        if result:
            flash('Appointment status updated', 'success')
    
    if prescription or diagnosis or follow_up_date:
        result = Appointment.update_medical_details(db, appointment_id, prescription, diagnosis, follow_up_date)
        if result:
            flash('Medical details updated', 'success')
    
    return redirect(url_for('appointment_details', appointment_id=appointment_id))

@app.route('/doctor/profile', methods=['GET', 'POST'])
@login_required
@doctor_required
def doctor_profile():
    doctor = User.get_user_by_id(db, session['user_id'])
    
    if request.method == 'POST':
        update_data = {}
        if request.form.get('name'):
            update_data['name'] = request.form['name']
        if request.form.get('phone'):
            update_data['phone'] = request.form['phone']
        if request.form.get('specialization'):
            update_data['specialization'] = request.form['specialization']
        if request.form.get('qualification'):
            update_data['qualification'] = request.form['qualification']
        if request.form.get('experience_years'):
            update_data['experience_years'] = int(request.form['experience_years'])
        if request.form.get('consultation_fee'):
            update_data['consultation_fee'] = float(request.form['consultation_fee'])
        if request.form.get('about'):
            update_data['about'] = request.form['about']
        
        if update_data:
            result = User.update_profile(db, session['user_id'], **update_data)
            if result:
                flash('Profile updated successfully', 'success')
                return redirect(url_for('doctor_profile'))
            else:
                flash('Failed to update profile', 'error')
    
    rating = Review.get_doctor_rating(db, session['user_id'])
    reviews = Review.get_doctor_reviews(db, session['user_id'])
    
    return render_template('doctor/profile.html', doctor=doctor, rating=rating, reviews=reviews)




import requests
from flask import request, jsonify, session

OTP_API_URL = "https://rmqu3w12mj.execute-api.us-east-1.amazonaws.com/default/otp-api-x23389401"


@app.route('/api/send-otp', methods=['POST'])
def api_send_otp():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email required'}), 400

    try:
        payload = {
            "action": "generate_otp",
            "email": email
        }

        response = requests.post(OTP_API_URL, json=payload, timeout=10)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return jsonify({'success': True, 'message': 'OTP sent successfully'})
        else:
            return jsonify({'error': 'Failed to send OTP'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
        
        
@app.route('/api/verify-booking-otp', methods=['POST'])
def api_verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'error': 'Email and OTP required'}), 400

    try:
        payload = {
            "action": "verify_otp",
            "email": email,
            "otp": otp
        }

        response = requests.post(OTP_API_URL, json=payload, timeout=10)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid OTP'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/send-booking-otp', methods=['POST'])
@login_required
def api_send_booking_otp():
    data = request.json
    email = data.get('email')

    if not email or email != session.get('user_email'):
        return jsonify({'error': 'Invalid email or session mismatch'}), 400

    try:
        payload = {
            "action": "generate_otp",
            "email": email
        }

        response = requests.post(OTP_API_URL, json=payload, timeout=10)
        result = response.json()

        if response.status_code == 200 and result.get("success"):
            return jsonify({
                'success': True,
                'message': 'OTP sent to your email'
            })
        else:
            return jsonify({'error': 'Failed to send OTP'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
        
@app.route('/api/current-user-email', methods=['GET'])
@login_required
def api_current_user_email():
    if 'user_id' in session and 'user_email' in session:
        return jsonify({
            'success': True,
            'email': session['user_email'],
            'user_id': session['user_id'],
            'user_name': session['user_name'],
            'user_type': session.get('user_type', 'patient')
        })
    return jsonify({'error': 'User not logged in'}), 401


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)