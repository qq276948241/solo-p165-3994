from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from models import db, CheckIn, Member, Course, Booking, Membership
from api.services import get_active_membership


checkin_bp = Blueprint('checkin', __name__)


@checkin_bp.route('/scan', methods=['POST'])
def scan_checkin():
    data = request.get_json()

    required_fields = ['qr_code', 'course_id', 'coach_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400

    qr_code = data['qr_code'].strip()
    course_id = data['course_id']
    coach_id = data['coach_id']

    member = Member.query.filter_by(qr_code=qr_code).first()
    if not member:
        return jsonify({'error': '无效的会员二维码'}), 404

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    if course.coach_id != coach_id:
        return jsonify({'error': '您不是该课程的教练，无法签到'}), 403

    course_datetime = datetime.combine(course.course_date, course.start_time)
    time_diff = (course_datetime - datetime.utcnow()).total_seconds() / 3600

    if time_diff > 1:
        return jsonify({'error': '课程开始前1小时内才能签到'}), 400
    if time_diff < -2:
        return jsonify({'error': '课程结束后无法签到'}), 400

    booking = Booking.query.filter_by(
        member_id=member.id,
        course_id=course_id,
        status='booked'
    ).first()

    if not booking:
        return jsonify({'error': '该会员未预约此课程'}), 400

    existing_checkin = CheckIn.query.filter_by(
        booking_id=booking.id
    ).first()
    if existing_checkin:
        return jsonify({
            'message': '该会员已签到',
            'checkin': existing_checkin.to_dict()
        }), 200

    active_membership = get_active_membership(member.id)
    if not active_membership:
        return jsonify({'error': '没有有效的会员卡'}), 400

    sessions_deducted = 0
    card_type_used = active_membership.card_type

    if active_membership.card_type != 'monthly':
        if active_membership.remaining_sessions <= 0:
            return jsonify({'error': '会员卡次数不足'}), 400
        active_membership.remaining_sessions -= 1
        sessions_deducted = 1

    checkin = CheckIn(
        member_id=member.id,
        course_id=course_id,
        booking_id=booking.id,
        checkin_time=datetime.utcnow(),
        sessions_deducted=sessions_deducted,
        card_type_used=card_type_used
    )
    db.session.add(checkin)
    db.session.commit()

    return jsonify({
        'message': '签到成功',
        'checkin': checkin.to_dict(),
        'member': {
            'id': member.id,
            'name': member.name,
            'phone': member.phone
        },
        'membership': {
            'card_type': card_type_used,
            'remaining_sessions': active_membership.remaining_sessions,
            'sessions_deducted': sessions_deducted
        }
    }), 201


@checkin_bp.route('/course/<int:course_id>', methods=['GET'])
def get_course_checkins(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    checkins = CheckIn.query.filter_by(course_id=course_id).order_by(CheckIn.checkin_time).all()

    result = []
    for checkin in checkins:
        checkin_dict = checkin.to_dict()
        member = Member.query.get(checkin.member_id)
        if member:
            checkin_dict['member_name'] = member.name
            checkin_dict['member_phone'] = member.phone
        result.append(checkin_dict)

    return jsonify({
        'course_id': course_id,
        'course_name': course.name,
        'checkin_count': len(checkins),
        'checkins': result
    }), 200


@checkin_bp.route('/member/<int:member_id>', methods=['GET'])
def get_member_checkins(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = CheckIn.query.filter_by(member_id=member_id)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(CheckIn.checkin_time >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
            query = query.filter(CheckIn.checkin_time < end_dt)
        except ValueError:
            pass

    checkins = query.order_by(CheckIn.checkin_time.desc()).all()

    total = len(checkins)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_checkins = checkins[start_idx:end_idx]

    result = []
    total_sessions_used = 0
    for checkin in paginated_checkins:
        checkin_dict = checkin.to_dict()
        course = Course.query.get(checkin.course_id)
        if course:
            checkin_dict['course_name'] = course.name
            checkin_dict['course_date'] = course.course_date.isoformat()
            coach = course.coach
            if coach:
                checkin_dict['coach_name'] = coach.name
        total_sessions_used += checkin.sessions_deducted
        result.append(checkin_dict)

    return jsonify({
        'member_id': member_id,
        'member_name': member.name,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_sessions_used': sum(c.sessions_deducted for c in checkins),
        'checkins': result
    }), 200


@checkin_bp.route('/<int:checkin_id>', methods=['GET'])
def get_checkin_detail(checkin_id):
    checkin = CheckIn.query.get(checkin_id)
    if not checkin:
        return jsonify({'error': '签到记录不存在'}), 404

    result = checkin.to_dict()

    member = Member.query.get(checkin.member_id)
    if member:
        result['member'] = member.to_dict()

    course = Course.query.get(checkin.course_id)
    if course:
        result['course'] = course.to_dict()

    booking = Booking.query.get(checkin.booking_id)
    if booking:
        result['booking'] = booking.to_dict()

    return jsonify(result), 200


@checkin_bp.route('/today', methods=['GET'])
def get_today_checkins():
    coach_id = request.args.get('coach_id', type=int)

    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    query = CheckIn.query.filter(
        CheckIn.checkin_time >= start_of_day,
        CheckIn.checkin_time <= end_of_day
    )

    if coach_id:
        query = query.join(Course).filter(Course.coach_id == coach_id)

    checkins = query.order_by(CheckIn.checkin_time.desc()).all()

    result = []
    for checkin in checkins:
        checkin_dict = checkin.to_dict()
        member = Member.query.get(checkin.member_id)
        course = Course.query.get(checkin.course_id)
        if member:
            checkin_dict['member_name'] = member.name
            checkin_dict['member_phone'] = member.phone
        if course:
            checkin_dict['course_name'] = course.name
        result.append(checkin_dict)

    return jsonify({
        'date': today.isoformat(),
        'total': len(checkins),
        'checkins': result
    }), 200


@checkin_bp.route('/statistics', methods=['GET'])
def get_checkin_statistics():
    member_id = request.args.get('member_id', type=int)
    coach_id = request.args.get('coach_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = CheckIn.query

    if member_id:
        query = query.filter_by(member_id=member_id)

    if coach_id:
        query = query.join(Course).filter(Course.coach_id == coach_id)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(CheckIn.checkin_time >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
            query = query.filter(CheckIn.checkin_time < end_dt)
        except ValueError:
            pass

    checkins = query.all()

    total_checkins = len(checkins)
    total_sessions_deducted = sum(c.sessions_deducted for c in checkins)

    by_card_type = {}
    for checkin in checkins:
        card_type = checkin.card_type_used or 'unknown'
        if card_type not in by_card_type:
            by_card_type[card_type] = 0
        by_card_type[card_type] += 1

    return jsonify({
        'total_checkins': total_checkins,
        'total_sessions_deducted': total_sessions_deducted,
        'by_card_type': by_card_type
    }), 200
