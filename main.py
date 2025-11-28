from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr
from email.message import EmailMessage
from dotenv import load_dotenv
import smtplib
import os
import time

import models
from database import SessionLocal, engine

# ---------------------------
# Load .env file
# ---------------------------
load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL") or SMTP_USER
FROM_NAME = os.getenv("FROM_NAME") or "Course Team"
OWNER_EMAIL = os.getenv("OWNER_EMAIL")

# ---------------------------
# Course Timings
# ---------------------------
COURSE_SCHEDULE = {
    1: {"start": "5:00 PM", "end": "5:30 PM", "date": "December 1, 2025"},
    2: {"start": "5:45 PM", "end": "6:16 PM", "date": "December 1, 2025"},
}

# ---------------------------
# FastAPI App
# ---------------------------
app = FastAPI()

# ---------------------------
# Serve STATIC files
# ---------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------
# Serve index.html at "/"
# ---------------------------
@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/course-detail.html")
def course_detail_page():
    return FileResponse("static/course-detail.html")


# Debug helper: check working directory and file existence for troubleshooting 404s
@app.get("/debug/check-course-detail")
def debug_check_course_file():
    import os
    path = os.path.join("static", "course-detail.html")
    return {
        "cwd": os.getcwd(),
        "path": path,
        "absolute_path": os.path.abspath(path),
        "exists": os.path.exists(path)
    }


# Also accept a few common alternative paths (no-extension or trailing slash)
@app.get("/course-detail")
def course_detail_no_ext():
    return FileResponse("static/course-detail.html")


@app.get("/course-detail/")
def course_detail_trailing():
    return FileResponse("static/course-detail.html")


@app.get("/course-detail.html/")
def course_detail_html_trailing():
    return FileResponse("static/course-detail.html")

# ---------------------------
# CORS
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Create DB tables
# ---------------------------
models.Base.metadata.create_all(bind=engine)

# Initialize courses if they don't exist
def init_courses():
    db = SessionLocal()
    try:
        # Clear all existing bookings and courses
        db.query(models.Booking).delete()
        db.query(models.Course).delete()
        db.commit()
        print("Cleared all bookings and courses")
        
        # Create the two courses with 10 seats each
        courses_data = [
            {"id": 1, "name": "Artificial Intelligence (AI)", "description": "Learn ML, DL, Neural Networks, and AI applications.", "total_seats": 10},
            {"id": 2, "name": "Quantum Computing", "description": "Learn Qubits, Quantum Gates, and Algorithms.", "total_seats": 10}
        ]
        for cdata in courses_data:
            c = models.Course(id=cdata["id"], name=cdata["name"], description=cdata["description"], total_seats=cdata["total_seats"])
            db.add(c)
        db.commit()
        print("Initialized courses with 10 seats each")
    except Exception as e:
        print("Could not initialize courses:", e)
        db.rollback()
    finally:
        db.close()

init_courses()

# Ensure bookings table has email and phone columns (add them if missing)
with engine.connect() as conn:
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    except Exception:
        cols = []

    if 'email' not in cols:
        try:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN email VARCHAR"))
            print('Added bookings.email column')
        except Exception as e:
            print('Could not add bookings.email:', e)
    if 'phone' not in cols:
        try:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN phone VARCHAR"))
            print('Added bookings.phone column')
        except Exception as e:
            print('Could not add bookings.phone:', e)

# ---------------------------
# DB Session Dependency
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# Email Function
# ---------------------------
def send_confirmation_email(to_email: str, user_name: str, course_name: str, course_id: int):

    schedule = COURSE_SCHEDULE.get(course_id, {})
    start = schedule.get("start", "TBA")
    end = schedule.get("end", "TBA")
    date = schedule.get("date", "TBA")

    subject = f"Booking Confirmed — {course_name}"
    
    # HTML email template
    html_body = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 8px; }}
          .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
          .content {{ background-color: white; padding: 20px; }}
          .course-name {{ font-size: 24px; font-weight: bold; color: #4CAF50; margin-bottom: 10px; }}
          .course-details {{ background-color: #f0f0f0; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0; }}
          .detail-item {{ margin: 10px 0; }}
          .button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; text-align: center; font-weight: bold; }}
          .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Booking Confirmed!</h1>
          </div>
          <div class="content">
            <p>Hello <strong>{user_name}</strong>,</p>
            <p>Your booking is confirmed for:</p>
            
            <div class="course-name">{course_name} Course</div>
            
            <div class="course-details">
              <div class="detail-item"><strong>Date:</strong> {date}</div>
              <div class="detail-item"><strong>Time:</strong> {start} - {end}</div>
            </div>
            
            <p>We're excited to see you in this course! Make sure to mark your calendar and prepare for an amazing learning experience.</p>
            
            <center>
              <a href="http://127.0.0.1:8000/" class="button">Confirm Your Booking</a>
            </center>
            
            <p>If you have any questions, feel free to reach out to our support team.</p>
            <p>Best regards,<br><strong>Course Team</strong></p>
          </div>
          <div class="footer">
            <p>&copy; 2025 Course Booking Platform. All rights reserved.</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    # Plain text fallback
    text_body = f"""
Hello {user_name},

Thank you for booking the course: {course_name}.

Course Details:
  Date: {date}
  Time: {start} - {end}

We look forward to seeing you!

— Course Team
"""

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')

    # If SMTP is not configured, or sending fails, write the email to disk
    # so developers can inspect it. Return True if email was sent, False otherwise.
    if not SMTP_HOST:
        # Save to disk
        try:
            os.makedirs('outgoing_emails', exist_ok=True)
            fname = os.path.join('outgoing_emails', f"email_{course_id}_{int(time.time())}.html")
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(f"To: {to_email}\nSubject: {subject}\n\n{html_body}")
            print(f"Email saved to {fname} (SMTP not configured)")
        except Exception as e:
            print("Failed to save email to disk:", e)
        return False

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            # If credentials provided, try secure connection and login
            if SMTP_USER:
                try:
                    smtp.starttls()
                except Exception:
                    # starttls may not be supported; continue anyway
                    pass
                smtp.login(SMTP_USER, SMTP_PASS)
            # send message
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("EMAIL ERROR: failed to send via SMTP:", e)
        # fallback: save to disk
        try:
            os.makedirs('outgoing_emails', exist_ok=True)
            fname = os.path.join('outgoing_emails', f"email_{course_id}_{int(time.time())}.html")
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(f"To: {to_email}\nSubject: {subject}\n\n{html_body}")
            print(f"Email saved to {fname} (SMTP error)")
        except Exception as e2:
            print("Failed to save email to disk after SMTP error:", e2)
        return False

# ---------------------------
# Owner Notification Email Function
# ---------------------------
def send_owner_notification(user_name: str, user_email: str, user_phone: str, course_name: str, course_id: int):
    """Send booking notification to owner email"""
    
    schedule = COURSE_SCHEDULE.get(course_id, {})
    start = schedule.get("start", "TBA")
    end = schedule.get("end", "TBA")
    date = schedule.get("date", "TBA")
    
    subject = f"New Booking: {user_name} registered for {course_name}"
    
    # HTML email template for owner
    html_body = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 8px; }}
          .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
          .content {{ background-color: white; padding: 20px; }}
          .booking-details {{ background-color: #f0f0f0; padding: 15px; border-left: 4px solid #2196F3; margin: 15px 0; }}
          .detail-item {{ margin: 10px 0; }}
          .detail-label {{ font-weight: bold; color: #2196F3; }}
          .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>New Course Booking Received</h1>
          </div>
          <div class="content">
            <p>A new student has booked a course. Here are the details:</p>
            
            <div class="booking-details">
              <div class="detail-item">
                <span class="detail-label">Student Name:</span> {user_name}
              </div>
              <div class="detail-item">
                <span class="detail-label">Email:</span> {user_email}
              </div>
              <div class="detail-item">
                <span class="detail-label">Phone:</span> {user_phone}
              </div>
              <div class="detail-item">
                <span class="detail-label">Course:</span> {course_name}
              </div>
              <div class="detail-item">
                <span class="detail-label">Date:</span> {date}
              </div>
              <div class="detail-item">
                <span class="detail-label">Time:</span> {start} - {end}
              </div>
            </div>
            
            <p>Please review this booking in your course management system.</p>
            <p>Best regards,<br><strong>Course Booking System</strong></p>
          </div>
          <div class="footer">
            <p>&copy; 2025 Course Booking Platform. All rights reserved.</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    # Plain text fallback
    text_body = f"""
New Course Booking Notification

Student Name: {user_name}
Email: {user_email}
Phone: {user_phone}
Course: {course_name}
Date: {date}
Time: {start} - {end}

— Course Booking System
"""

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = OWNER_EMAIL
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')

    # If SMTP is not configured, skip sending to owner
    if not SMTP_HOST or not OWNER_EMAIL:
        print("Owner email not configured, skipping owner notification")
        return False

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            if SMTP_USER:
                try:
                    smtp.starttls()
                except Exception:
                    pass
                smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print(f"Owner notification sent to {OWNER_EMAIL}")
        return True
    except Exception as e:
        print("OWNER EMAIL ERROR: failed to send notification to owner:", e)
        return False

# ---------------------------
# Pydantic Input Schema
# ---------------------------
class BookingIn(BaseModel):
    user_name: str
    course_id: int
    email: str  # Accept as string; validation will be lenient
    phone: str
    payment_method: str = None  # Optional: upi or razorpay
    payment_id: str = None  # Optional: payment transaction ID

# ---------------------------
# GET /courses
# ---------------------------
@app.get("/courses")
def get_courses(db: Session = Depends(get_db)):
    courses = db.query(models.Course).all()
    result = []

    for c in courses:
        booked_count = (
            db.query(models.Booking)
            .filter(models.Booking.course_id == c.id)
            .count()
        )

        result.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "total_seats": c.total_seats,
            "booked_count": booked_count,
        })

    return result


@app.get("/courses/{course_id}/bookings")
def get_course_bookings(course_id: int, db: Session = Depends(get_db)):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    bookings = db.query(models.Booking).filter(models.Booking.course_id == course_id).all()
    return [{"id": b.id, "user_name": b.user_name, "email": b.email, "phone": b.phone} for b in bookings]

# ---------------------------
# POST /book
# ---------------------------
@app.post("/book")
def book_course(payload: BookingIn, db: Session = Depends(get_db)):
    try:
        course = db.query(models.Course).filter(
            models.Course.id == payload.course_id
        ).first()

        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        booked_count = db.query(models.Booking).filter(
            models.Booking.course_id == payload.course_id
        ).count()

        if booked_count >= course.total_seats:
            raise HTTPException(status_code=400, detail="Course is full")

        # Create booking
        booking = models.Booking(
            user_name=payload.user_name,
            course_id=payload.course_id,
            email=payload.email,
            phone=payload.phone,
        )
        db.add(booking)
        db.commit()

        # Try to send email but do not fail booking if email sending fails.
        try:
            print(f"DEBUG: Sending email for course ID {course.id}, course name: {course.name}")
            email_sent = send_confirmation_email(
                payload.email,
                payload.user_name,
                course.name,
                course.id,
            )
        except Exception as e:
            # Shouldn't normally happen because send_confirmation_email catches errors,
            # but defensively handle it here.
            print("Failed to send confirmation email (unexpected):", e)
            email_sent = False

        # Send notification to owner
        try:
            send_owner_notification(
                payload.user_name,
                payload.email,
                payload.phone,
                course.name,
                course.id,
            )
        except Exception as e:
            print("Failed to send owner notification (unexpected):", e)

        if email_sent:
            return {"message": "Booking successful! Confirmation email sent."}
        else:
            return {"message": "Booking successful! But confirmation email could not be sent."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in /book endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
