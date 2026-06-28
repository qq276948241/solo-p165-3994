from datetime import datetime
from flask import Blueprint, request, jsonify
from models import db, Waitlist, Member, Course, Booking
from api.services import (
    MAX_WAITLIST,
    validate_membership_for_booking,
    get_waitlist_info_for_course,
    cancel_waitlist_entry,
)


waitlist_bp = Blueprint('waitlist', __name__)


@waitlist_bp.route('/<int:course_id>', methods=['POST'])
def join_waitlist(course_id):
    data = request.get_json()
    if not data or 'member_id' not in data:
        return jsonify({'error': '缺少会员ID'}), 400

    member_id = data['member_id']

    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    course_datetime = datetime.combine(course.course_date, course.start_time)
    if course_datetime < datetime.utcnow():
        return jsonify({'error': '课程已开始，无法加入候补'}), 400

    existing_booking = Booking.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='booked'
    ).first()
    if existing_booking:
        return jsonify({'error': '您已预约该课程'}), 400

    if not course.is_full():
        return jsonify({'error': '课程还有名额，请直接预约'}), 400

    existing_waitlist = Waitlist.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='waiting'
    ).first()
    if existing_waitlist:
        return jsonify({
            'message': f'您当前候补第{existing_waitlist.position}位',
            'waitlist': existing_waitlist.to_dict()
        }), 200

    waitlist_count = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).count()

    if waitlist_count >= MAX_WAITLIST:
        return jsonify({'error': f'候补名单已满（最多{MAX_WAITLIST}人）'}), 400

    _, error = validate_membership_for_booking(member)
    if error:
        return jsonify({'error': error}), 400

    waitlist = Waitlist(
        member_id=member_id,
        course_id=course_id,
        position=waitlist_count + 1,
        status='waiting'
    )
    db.session.add(waitlist)
    db.session.commit()

    return jsonify({
        'message': f'候补登记成功，您当前候补第{waitlist.position}位',
        'waitlist': waitlist.to_dict()
    }), 201


@waitlist_bp.route('/<int:course_id>/<int:member_id>', methods=['GET'])
def get_waitlist_position(course_id, member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    waitlist = Waitlist.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='waiting'
    ).first()

    if not waitlist:
        return jsonify({
            'in_waitlist': False,
            'message': '您未在候补名单中'
        }), 200

    waitlist_count = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).count()

    return jsonify({
        'in_waitlist': True,
        'message': f'您当前候补第{waitlist.position}位',
        'position': waitlist.position,
        'total_waiting': waitlist_count,
        'waitlist': waitlist.to_dict()
    }), 200


@waitlist_bp.route('/<int:course_id>/cancel', methods=['POST'])
def cancel_waitlist_route(course_id):
    data = request.get_json()
    if not data or 'member_id' not in data:
        return jsonify({'error': '缺少会员ID'}), 400

    member_id = data['member_id']

    waitlist = cancel_waitlist_entry(course_id, member_id)
    if not waitlist:
        return jsonify({'error': '您未在候补名单中'}), 404

    db.session.commit()

    return jsonify({
        'message': '候补取消成功',
        'waitlist': waitlist.to_dict()
    }), 200


@waitlist_bp.route('/<int:course_id>/list', methods=['GET'])
def get_course_waitlist(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    info = get_waitlist_info_for_course(course_id)

    return jsonify({
        'course_id': course_id,
        'course_name': course.name,
        'total_waiting': info['count'],
        'max_waitlist': info['max_waitlist'],
        'waitlist': info['members']
    }), 200


@waitlist_bp.route('/member/<int:member_id>', methods=['GET'])
def get_member_waitlist(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    waitlists = Waitlist.query.filter_by(
        member_id=member_id,
        status='waiting'
    ).order_by(Waitlist.created_at.desc()).all()

    result = []
    for wl in waitlists:
        course = Course.query.get(wl.course_id)
        wl_dict = wl.to_dict()
        if course:
            wl_dict['course'] = course.to_dict()
        result.append(wl_dict)

    return jsonify({
        'member_id': member_id,
        'member_name': member.name,
        'waitlist_count': len(result),
        'waitlist': result
    }), 200
