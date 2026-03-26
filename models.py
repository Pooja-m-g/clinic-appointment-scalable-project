import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import hashlib

class Database:
    def __init__(self):
        # Update these with your MySQL credentials
        self.host = 'rds-scalable-x23389401.clq22e042t6e.us-east-1.rds.amazonaws.com'
        self.user = 'admin'
        self.password = 'rds-scalable-x23389401'  # Change to your MySQL password
        self.database = 'rds-scalable-x23389401'
        self.port = 3306
        self.connection = None
        self.connect()
        
    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True
            )
            print(f"✓ Connected to database: {self.database}")
            return True
        except Error as e:
            print(f"✗ Database connection error: {e}")
            self.connection = None
            return False
    
    def ensure_connection(self):
        if self.connection is None:
            return self.connect()
        try:
            if not self.connection.is_connected():
                self.connection.reconnect()
            return True
        except:
            return self.connect()
    
    def execute_query(self, query, params=None):
        cursor = None
        try:
            if not self.ensure_connection():
                return None
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            self.connection.commit()
            return cursor
        except Error as e:
            print(f"Query error: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def fetch_one(self, query, params=None):
        cursor = None
        try:
            if not self.ensure_connection():
                return None
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchone()
        except Error as e:
            print(f"Fetch error: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def fetch_all(self, query, params=None):
        cursor = None
        try:
            if not self.ensure_connection():
                return []
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            return cursor.fetchall()
        except Error as e:
            print(f"Fetch error: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

class User:
    @staticmethod
    def create_user(db, email, password, name, phone, user_type='patient', **kwargs):
        #hashed_password = hashlib.sha256(password.encode()).hexdigest()
        query = """
        INSERT INTO users (email, password, name, phone, user_type, specialization, 
                          qualification, experience_years, consultation_fee, about)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (email, password, name, phone, user_type,
                 kwargs.get('specialization'), kwargs.get('qualification'),
                 kwargs.get('experience_years'), kwargs.get('consultation_fee'),
                 kwargs.get('about'))
        return db.execute_query(query, params)
    
    @staticmethod
    def get_user_by_email(db, email):
        query = "SELECT * FROM users WHERE email = %s"
        return db.fetch_one(query, (email,))
    
    @staticmethod
    def get_user_by_id(db, user_id):
        query = "SELECT * FROM users WHERE id = %s"
        return db.fetch_one(query, (user_id,))
    
    @staticmethod
    def verify_user(db, email, password):
        #hashed_password = hashlib.sha256(password.encode()).hexdigest()
        query = "SELECT * FROM users WHERE email = %s AND password = %s AND is_active = TRUE"
        #return db.fetch_one(query, (email, hashed_password))
        return db.fetch_one(query, (email, password))
    
    @staticmethod
    def get_doctors(db, specialization=None):
        query = "SELECT * FROM users WHERE user_type = 'doctor' AND is_active = TRUE"
        params = ()
        if specialization:
            query += " AND specialization = %s"
            params = (specialization,)
        query += " ORDER BY name"
        return db.fetch_all(query, params)
    
    @staticmethod
    def update_profile(db, user_id, **kwargs):
        set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
        query = f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = %s"
        params = list(kwargs.values()) + [user_id]
        return db.execute_query(query, params)

class DoctorSlot:
    @staticmethod
    def create_slot(db, doctor_id, slot_date, start_time, end_time, duration_minutes=30, max_patients=1):
        query = """
        INSERT INTO doctor_slots (doctor_id, slot_date, start_time, end_time, 
                                  duration_minutes, max_patients)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (doctor_id, slot_date, start_time, end_time, duration_minutes, max_patients)
        return db.execute_query(query, params)
    
    @staticmethod
    def get_doctor_slots(db, doctor_id, date=None):
        query = "SELECT * FROM doctor_slots WHERE doctor_id = %s"
        params = [doctor_id]
        if date:
            query += " AND slot_date = %s"
            params.append(date)
        query += " ORDER BY slot_date DESC, start_time"
        return db.fetch_all(query, tuple(params))
    
    @staticmethod
    def get_available_slots(db, doctor_id, date):
        query = """
        SELECT * FROM doctor_slots 
        WHERE doctor_id = %s AND slot_date = %s AND status = 'available' 
        AND booked_count < max_patients
        ORDER BY start_time
        """
        return db.fetch_all(query, (doctor_id, date))
    
    @staticmethod
    def update_slot(db, slot_id, **kwargs):
        set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
        query = f"UPDATE doctor_slots SET {set_clause} WHERE id = %s"
        params = list(kwargs.values()) + [slot_id]
        return db.execute_query(query, params)
    
    @staticmethod
    def delete_slot(db, slot_id):
        query = "DELETE FROM doctor_slots WHERE id = %s AND booked_count = 0"
        return db.execute_query(query, (slot_id,))
    
    @staticmethod
    def get_slot_by_id(db, slot_id):
        query = "SELECT * FROM doctor_slots WHERE id = %s"
        return db.fetch_one(query, (slot_id,))

class Appointment:
    @staticmethod
    def create_appointment(db, patient_id, doctor_id, slot_id, appointment_date, 
                          appointment_time, symptoms=None, notes=None):
        query = """
        INSERT INTO appointments (patient_id, doctor_id, slot_id, appointment_date, 
                                 appointment_time, symptoms, notes, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """
        params = (patient_id, doctor_id, slot_id, appointment_date, 
                 appointment_time, symptoms, notes)
        result = db.execute_query(query, params)
        
        # Update slot booked count
        if result:
            update_query = """
            UPDATE doctor_slots 
            SET booked_count = booked_count + 1,
                status = CASE WHEN booked_count + 1 >= max_patients THEN 'booked' ELSE 'available' END
            WHERE id = %s
            """
            db.execute_query(update_query, (slot_id,))
        
        return result
    
    @staticmethod
    def get_patient_appointments(db, patient_id):
        query = """
        SELECT a.*, u.name as doctor_name, u.specialization,
               ds.start_time, ds.end_time
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        JOIN doctor_slots ds ON a.slot_id = ds.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """
        return db.fetch_all(query, (patient_id,))
    
    @staticmethod
    def get_doctor_appointments(db, doctor_id, date=None):
        query = """
        SELECT a.*, u.name as patient_name, u.email, u.phone
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = %s
        """
        params = [doctor_id]
        if date:
            query += " AND a.appointment_date = %s"
            params.append(date)
        query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
        return db.fetch_all(query, tuple(params))
    
    @staticmethod
    def update_appointment_status(db, appointment_id, status):
        query = "UPDATE appointments SET status = %s, updated_at = NOW() WHERE id = %s"
        return db.execute_query(query, (status, appointment_id))
    
    @staticmethod
    def update_medical_details(db, appointment_id, prescription=None, diagnosis=None, follow_up_date=None):
        query = """
        UPDATE appointments 
        SET prescription = COALESCE(%s, prescription),
            diagnosis = COALESCE(%s, diagnosis),
            follow_up_date = COALESCE(%s, follow_up_date),
            status = 'completed',
            updated_at = NOW()
        WHERE id = %s
        """
        return db.execute_query(query, (prescription, diagnosis, follow_up_date, appointment_id))
    
    @staticmethod
    def get_appointment_by_id(db, appointment_id):
        query = """
        SELECT a.*, 
               p.name as patient_name, p.email as patient_email, p.phone as patient_phone,
               d.name as doctor_name, d.specialization
        FROM appointments a
        JOIN users p ON a.patient_id = p.id
        JOIN users d ON a.doctor_id = d.id
        WHERE a.id = %s
        """
        return db.fetch_one(query, (appointment_id,))
    
    @staticmethod
    def cancel_appointment(db, appointment_id):
        # Get slot_id first
        appointment = Appointment.get_appointment_by_id(db, appointment_id)
        if appointment:
            # Update slot booked count
            update_query = """
            UPDATE doctor_slots 
            SET booked_count = booked_count - 1,
                status = 'available'
            WHERE id = %s AND booked_count > 0
            """
            db.execute_query(update_query, (appointment['slot_id'],))
        
        # Cancel appointment
        query = "UPDATE appointments SET status = 'cancelled', updated_at = NOW() WHERE id = %s"
        return db.execute_query(query, (appointment_id,))

class OTP:
    @staticmethod
    def save_otp(db, email, otp, purpose='booking'):
        query = """
        INSERT INTO otp_verification (email, otp, purpose, created_at, expires_at, is_verified)
        VALUES (%s, %s, %s, NOW(), DATE_ADD(NOW(), INTERVAL 10 MINUTE), FALSE)
        """
        return db.execute_query(query, (email, otp, purpose))
    
    @staticmethod
    def verify_otp(db, email, otp):
        query = """
        SELECT * FROM otp_verification 
        WHERE email = %s AND otp = %s AND is_verified = FALSE 
        AND expires_at > NOW()
        ORDER BY created_at DESC LIMIT 1
        """
        result = db.fetch_one(query, (email, otp))
        if result:
            update_query = "UPDATE otp_verification SET is_verified = TRUE WHERE id = %s"
            db.execute_query(update_query, (result['id'],))
            return True
        return False

class Review:
    @staticmethod
    def add_review(db, patient_id, doctor_id, appointment_id, rating, comment):
        query = """
        INSERT INTO reviews (patient_id, doctor_id, appointment_id, rating, comment)
        VALUES (%s, %s, %s, %s, %s)
        """
        return db.execute_query(query, (patient_id, doctor_id, appointment_id, rating, comment))
    
    @staticmethod
    def get_doctor_reviews(db, doctor_id):
        query = """
        SELECT r.*, u.name as patient_name
        FROM reviews r
        JOIN users u ON r.patient_id = u.id
        WHERE r.doctor_id = %s
        ORDER BY r.created_at DESC
        """
        return db.fetch_all(query, (doctor_id,))
    
    @staticmethod
    def get_doctor_rating(db, doctor_id):
        query = """
        SELECT AVG(rating) as avg_rating, COUNT(*) as total_reviews
        FROM reviews
        WHERE doctor_id = %s
        """
        return db.fetch_one(query, (doctor_id,))