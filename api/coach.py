from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from models import db, Coach, Course, Booking, Member, CheckIn


coach_bp = Blueprint('coach', __name__)


@coach_bp.route('/register', methods=['POST'])
def register_coach():
    data = request.get_json()

    required_fields = ['phone', 'name', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400

    phone = data['phone'].strip()
    name = data['name'].strip()
    password = data['password']

    existing_coach = Coach.query.filter_by(phone=phone).first()
    if existing_coach:
        return jsonify({'error': '该手机号已注册'}), 400

    coach = Coach(phone=phone, name=name)
    coach.set_password(password)
    db.session.add(coach)
    db.session.commit()

    return jsonify({
        'message': '教练注册成功',
        'coach': coach.to_dict()
    }), 201


@coach_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or 'phone' not in data or 'password' not in data:
        return jsonify({'error': '手机号和密码不能为空'}), 400

    coach = Coach.query.filter_by(phone=data['phone']).first()
    if not coach or not coach.check_password(data['password']):
        return jsonify({'error': '手机号或密码错误'}), 401

    return jsonify({
        'message': '登录成功',
        'coach': coach.to_dict()
    }), 200


@coach_bp.route('/<int:coach_id>/courses', methods=['GET'])
def get_coach_courses(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    week_offset = request.args.get('week_offset', 0, type=int)
    status = request.args.get('status', 'all')

    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    start_date = monday + timedelta(weeks=week_offset)
    end_date = start_date + timedelta(days=6)

    query = Course.query.filter_by(coach_id=coach_id)

    if status == 'upcoming':
        query = query.filter(Course.course_date >= today)
    elif status == 'past':
        query = query.filter(Course.course_date < today)
    else:
        query = query.filter(
            Course.course_date >= start_date,
            Course.course_date <= end_date
        )

    courses = query.order_by(Course.course_date, Course.start_time).all()

    result = []
    for course in courses:
        course_dict = course.to_dict()
        bookings = Booking.query.filter_by(course_id=course.id, status='booked').all()
        course_dict['booked_count'] = len(bookings)
        checkins = CheckIn.query.filter_by(course_id=course.id).all()
        course_dict['checked_in_count'] = len(checkins)
        result.append(course_dict)

    return jsonify({
        'coach_id': coach_id,
        'coach_name': coach.name,
        'week_start': start_date.isoformat() if status == 'all' else None,
        'week_end': end_date.isoformat() if status == 'all' else None,
        'courses': result
    }), 200


@coach_bp.route('/<int:coach_id>/courses/today', methods=['GET'])
def get_coach_today_courses(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    today = datetime.utcnow().date()

    courses = Course.query.filter_by(
        coach_id=coach_id,
        course_date=today
    ).order_by(Course.start_time).all()

    result = []
    for course in courses:
        course_dict = course.to_dict()
        bookings = Booking.query.filter_by(course_id=course.id, status='booked').all()
        course_dict['booked_count'] = len(bookings)
        checkins = CheckIn.query.filter_by(course_id=course.id).all()
        course_dict['checked_in_count'] = len(checkins)

        members = []
        for booking in bookings:
            member = Member.query.get(booking.member_id)
            if member:
                checkin = CheckIn.query.filter_by(booking_id=booking.id).first()
                members.append({
                    'booking_id': booking.id,
                    'member_id': member.id,
                    'name': member.name,
                    'phone': member.phone,
                    'checked_in': checkin is not None,
                    'checkin_time': checkin.checkin_time.isoformat() if checkin else None
                })
        course_dict['members'] = members
        result.append(course_dict)

    return jsonify({
        'coach_id': coach_id,
        'coach_name': coach.name,
        'date': today.isoformat(),
        'courses': result
    }), 200


@coach_bp.route('/course/<int:course_id>/members', methods=['GET'])
def get_course_members(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    coach_id = request.args.get('coach_id', type=int)
    if coach_id and course.coach_id != coach_id:
        return jsonify({'error': '您不是该课程的教练'}), 403

    bookings = Booking.query.filter_by(course_id=course_id, status='booked').all()

    members = []
    for booking in bookings:
        member = Member.query.get(booking.member_id)
        if member:
            checkin = CheckIn.query.filter_by(booking_id=booking.id).first()
            memberships = [m for m in member.memberships if m.is_active()]
            active_membership = memberships[0] if memberships else None

            member_info = {
                'booking_id': booking.id,
                'member_id': member.id,
                'name': member.name,
                'phone': member.phone,
                'qr_code': member.qr_code,
                'checked_in': checkin is not None,
                'checkin_time': checkin.checkin_time.isoformat() if checkin else None,
                'card_type': active_membership.card_type if active_membership else None,
                'remaining_sessions': active_membership.remaining_sessions if active_membership else 0
            }
            members.append(member_info)

    return jsonify({
        'course_id': course_id,
        'course_name': course.name,
        'course_date': course.course_date.isoformat(),
        'start_time': course.start_time.isoformat(),
        'capacity': course.capacity,
        'booked_count': len(members),
        'members': members
    }), 200


@coach_bp.route('/<int:coach_id>/students', methods=['GET'])
def get_coach_students(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Course.query.filter_by(coach_id=coach_id)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Course.course_date >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Course.course_date <= end_dt)
        except ValueError:
            pass

    courses = query.all()
    course_ids = [c.id for c in courses]

    bookings = Booking.query.filter(
        Booking.course_id.in_(course_ids),
        Booking.status == 'booked'
    ).all()

    student_map = {}
    for booking in bookings:
        member_id = booking.member_id
        if member_id not in student_map:
            member = Member.query.get(member_id)
            if member:
                student_map[member_id] = {
                    'member_id': member_id,
                    'name': member.name,
                    'phone': member.phone,
                    'total_bookings': 0,
                    'total_checkins': 0,
                    'courses': []
                }

        course = Course.query.get(booking.course_id)
        if course:
            student_map[member_id]['courses'].append({
                'course_id': course.id,
                'course_name': course.name,
                'course_date': course.course_date.isoformat(),
                'booking_time': booking.created_at.isoformat()
            })

        checkin = CheckIn.query.filter_by(booking_id=booking.id).first()
        if checkin:
            student_map[member_id]['total_checkins'] += 1

        student_map[member_id]['total_bookings'] += 1

    students = sorted(
        student_map.values(),
        key=lambda x: x['total_checkins'],
        reverse=True
    )

    return jsonify({
        'coach_id': coach_id,
        'coach_name': coach.name,
        'total_students': len(students),
        'students': students
    }), 200


@coach_bp.route('/<int:coach_id>/statistics', methods=['GET'])
def get_coach_statistics(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Course.query.filter_by(coach_id=coach_id)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Course.course_date >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Course.course_date <= end_dt)
        except ValueError:
            pass

    courses = query.all()
    course_ids = [c.id for c in courses]

    total_courses = len(courses)
    total_bookings = Booking.query.filter(
        Booking.course_id.in_(course_ids),
        Booking.status == 'booked'
    ).count()

    total_checkins = CheckIn.query.filter(
        CheckIn.course_id.in_(course_ids)
    ).count()

    total_sessions_deducted = db.session.query(
        db.func.sum(CheckIn.sessions_deducted)
    ).filter(
        CheckIn.course_id.in_(course_ids)
    ).scalar() or 0

    by_course_type = {}
    for course in courses:
        course_name = course.name
        if course_name not in by_course_type:
            by_course_type[course_name] = {
                'count': 0,
                'bookings': 0,
                'checkins': 0
            }
        by_course_type[course_name]['count'] += 1
        by_course_type[course_name]['bookings'] += course.get_booked_count()
        by_course_type[course_name]['checkins'] += CheckIn.query.filter_by(course_id=course.id).count()

    return jsonify({
        'coach_id': coach_id,
        'coach_name': coach.name,
        'total_courses': total_courses,
        'total_bookings': total_bookings,
        'total_checkins': total_checkins,
        'total_sessions_deducted': total_sessions_deducted,
        'attendance_rate': (total_checkins / total_bookings * 100) if total_bookings > 0 else 0,
        'by_course': by_course_type
    }), 200


@coach_bp.route('/<int:coach_id>', methods=['GET'])
def get_coach_profile(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    return jsonify({
        'coach': coach.to_dict()
    }), 200


@coach_bp.route('/<int:coach_id>', methods=['PUT'])
def update_coach_profile(coach_id):
    coach = Coach.query.get(coach_id)
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    data = request.get_json()

    if 'name' in data:
        coach.name = data['name']
    if 'phone' in data:
        existing_coach = Coach.query.filter_by(phone=data['phone']).first()
        if existing_coach and existing_coach.id != coach_id:
            return jsonify({'error': '该手机号已被使用'}), 400
        coach.phone = data['phone']
    if 'password' in data:
        coach.set_password(data['password'])

    db.session.commit()

    return jsonify({
        'message': '个人信息更新成功',
        'coach': coach.to_dict()
    }), 200


@coach_bp.route('/course/<int:course_id>/attendance', methods=['GET'])
def get_course_attendance(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    coach_id = request.args.get('coach_id', type=int)
    if coach_id and course.coach_id != coach_id:
        return jsonify({'error': '您不是该课程的教练'}), 403

    bookings = Booking.query.filter_by(course_id=course_id).all()

    attendance_list = []
    for booking in bookings:
        member = Member.query.get(booking.member_id)
        checkin = CheckIn.query.filter_by(booking_id=booking.id).first()

        if member:
            attendance_list.append({
                'booking_id': booking.id,
                'member_id': member.id,
                'name': member.name,
                'phone': member.phone,
                'booking_status': booking.status,
                'checked_in': checkin is not None,
                'checkin_time': checkin.checkin_time.isoformat() if checkin else None,
                'sessions_deducted': checkin.sessions_deducted if checkin else 0,
                'card_type_used': checkin.card_type_used if checkin else None
            })

    return jsonify({
        'course_id': course_id,
        'course_name': course.name,
        'course_date': course.course_date.isoformat(),
        'start_time': course.start_time.isoformat(),
        'total_booked': len([b for b in bookings if b.status == 'booked']),
        'total_checked_in': len([a for a in attendance_list if a['checked_in']]),
        'attendance': attendance_list
    }), 200
