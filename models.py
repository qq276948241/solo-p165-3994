from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(50))
    qr_code = db.Column(db.String(100), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship('Membership', backref='member', lazy=True)
    bookings = db.relationship('Booking', backref='member', lazy=True)
    checkins = db.relationship('CheckIn', backref='member', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'qr_code': self.qr_code,
            'created_at': self.created_at.isoformat()
        }


class Membership(db.Model):
    __tablename__ = 'memberships'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    card_type = db.Column(db.String(20), nullable=False)
    total_sessions = db.Column(db.Integer, default=0)
    remaining_sessions = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_active(self):
        now = datetime.utcnow()
        return self.start_date <= now <= self.end_date

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'card_type': self.card_type,
            'total_sessions': self.total_sessions,
            'remaining_sessions': self.remaining_sessions,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active()
        }


class Coach(db.Model):
    __tablename__ = 'coaches'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    courses = db.relationship('Course', backref='coach', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    coach_id = db.Column(db.Integer, db.ForeignKey('coaches.id'), nullable=False)
    course_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, default=12)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='course', lazy=True)

    def get_booked_count(self):
        return db.session.query(db.func.count(Booking.id)).filter(
            Booking.course_id == self.id,
            Booking.status == 'booked'
        ).scalar() or 0

    def is_full(self):
        return self.get_booked_count() >= self.capacity

    def can_cancel(self):
        now = datetime.utcnow()
        course_datetime = datetime.combine(self.course_date, self.start_time)
        return (course_datetime - now).total_seconds() > 2 * 3600

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'coach_id': self.coach_id,
            'coach_name': self.coach.name if self.coach else None,
            'course_date': self.course_date.isoformat(),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'capacity': self.capacity,
            'booked_count': self.get_booked_count(),
            'is_full': self.is_full()
        }


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    status = db.Column(db.String(20), default='booked')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)

    checkin = db.relationship('CheckIn', backref='booking', uselist=False, lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'course_id': self.course_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None
        }


class Waitlist(db.Model):
    __tablename__ = 'waitlists'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='waiting', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    converted_to_booking_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('ix_waitlist_course_status', 'course_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'course_id': self.course_id,
            'position': self.position,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'converted_to_booking_at': self.converted_to_booking_at.isoformat() if self.converted_to_booking_at else None
        }


class CheckIn(db.Model):
    __tablename__ = 'checkins'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    checkin_time = db.Column(db.DateTime, default=datetime.utcnow)
    sessions_deducted = db.Column(db.Integer, default=0)
    card_type_used = db.Column(db.String(20))

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'course_id': self.course_id,
            'booking_id': self.booking_id,
            'checkin_time': self.checkin_time.isoformat(),
            'sessions_deducted': self.sessions_deducted,
            'card_type_used': self.card_type_used
        }
