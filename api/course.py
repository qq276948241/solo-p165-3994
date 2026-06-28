from datetime import datetime, timedelta, time
from flask import Blueprint, request, jsonify, current_app
from models import db, Course, Booking, Member, Membership, Coach, Waitlist


course_bp = Blueprint('course', __name__)


def get_week_range(week_offset=0):
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    start_date = monday + timedelta(weeks=week_offset)
    end_date = start_date + timedelta(days=6)
    return start_date, end_date


@course_bp.route('', methods=['POST'])
def create_course():
    data = request.get_json()

    required_fields = ['name', 'coach_id', 'course_date', 'start_time', 'end_time']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'缺少必要字段: {field}'}), 400

    coach = Coach.query.get(data['coach_id'])
    if not coach:
        return jsonify({'error': '教练不存在'}), 404

    try:
        course_date = datetime.strptime(data['course_date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        end_time = datetime.strptime(data['end_time'], '%H:%M').time()
    except ValueError:
        return jsonify({'error': '日期或时间格式错误'}), 400

    if start_time >= end_time:
        return jsonify({'error': '开始时间必须早于结束时间'}), 400

    capacity = data.get('capacity', current_app.config['MAX_COURSE_CAPACITY'])

    course = Course(
        name=data['name'],
        description=data.get('description', ''),
        coach_id=data['coach_id'],
        course_date=course_date,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity
    )
    db.session.add(course)
    db.session.commit()

    return jsonify({
        'message': '课程创建成功',
        'course': course.to_dict()
    }), 201


@course_bp.route('/schedule', methods=['GET'])
def get_schedule(week_offset=None, coach_id=None):
    if week_offset is None:
        week_offset = request.args.get('week_offset', 0, type=int)
    if coach_id is None:
        coach_id = request.args.get('coach_id', type=int)

    start_date, end_date = get_week_range(week_offset)

    query = Course.query.filter(
        Course.course_date >= start_date,
        Course.course_date <= end_date
    )

    if coach_id:
        query = query.filter_by(coach_id=coach_id)

    courses = query.order_by(Course.course_date, Course.start_time).all()

    return jsonify({
        'week_start': start_date.isoformat(),
        'week_end': end_date.isoformat(),
        'week_offset': week_offset,
        'courses': [course.to_dict() for course in courses]
    }), 200


@course_bp.route('/next-week', methods=['GET'])
def get_next_week_schedule():
    return get_schedule(week_offset=1)


@course_bp.route('/<int:course_id>', methods=['GET'])
def get_course_detail(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    bookings = Booking.query.filter_by(course_id=course_id, status='booked').all()
    members = []
    for booking in bookings:
        member = Member.query.get(booking.member_id)
        if member:
            members.append({
                'booking_id': booking.id,
                'member_id': member.id,
                'name': member.name,
                'phone': member.phone
            })

    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()

    waitlist_members = []
    for wl in waitlists:
        member = Member.query.get(wl.member_id)
        if member:
            waitlist_members.append({
                'waitlist_id': wl.id,
                'member_id': member.id,
                'name': member.name,
                'phone': member.phone,
                'position': wl.position
            })

    course_dict = course.to_dict()
    course_dict['booked_members'] = members
    course_dict['waitlist'] = {
        'count': len(waitlist_members),
        'max_waitlist': 5,
        'members': waitlist_members
    }

    return jsonify(course_dict), 200


@course_bp.route('/<int:course_id>/book', methods=['POST'])
def book_course(course_id):
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

    if course.is_full():
        return jsonify({'error': '课程已满，可加入候补排队'}), 400

    course_datetime = datetime.combine(course.course_date, course.start_time)
    if course_datetime < datetime.utcnow():
        return jsonify({'error': '课程已开始，无法预约'}), 400

    active_membership = None
    for m in member.memberships:
        if m.is_active():
            if active_membership is None or m.remaining_sessions > active_membership.remaining_sessions:
                active_membership = m

    if not active_membership:
        return jsonify({'error': '没有有效的会员卡'}), 400

    if active_membership.card_type != 'monthly' and active_membership.remaining_sessions <= 0:
        return jsonify({'error': '会员卡次数不足'}), 400

    existing_booking = Booking.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='booked'
    ).first()
    if existing_booking:
        return jsonify({'error': '您已预约该课程'}), 400

    existing_waitlist = Waitlist.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='waiting'
    ).first()

    booking = Booking(
        member_id=member_id,
        course_id=course_id,
        status='booked'
    )
    db.session.add(booking)
    db.session.flush()

    if existing_waitlist:
        existing_waitlist.status = 'converted'
        existing_waitlist.converted_to_booking_at = datetime.utcnow()

        waitlists = Waitlist.query.filter_by(
            course_id=course_id,
            status='waiting'
        ).order_by(Waitlist.position).all()

        for idx, wl in enumerate(waitlists):
            wl.position = idx + 1

    db.session.commit()

    response_data = {
        'message': '预约成功',
        'booking': booking.to_dict(),
        'course': course.to_dict()
    }

    if existing_waitlist:
        response_data['from_waitlist'] = True
        response_data['message'] = '已从候补名单转为正式预约'

    return jsonify(response_data), 201


def process_waitlist(course_id):
    max_waitlist = 5

    course = Course.query.get(course_id)
    if not course or course.is_full():
        return None

    next_waitlist = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).first()

    if not next_waitlist:
        return None

    member = Member.query.get(next_waitlist.member_id)
    if not member:
        next_waitlist.status = 'cancelled'
        db.session.commit()
        return process_waitlist(course_id)

    active_membership = None
    for m in member.memberships:
        if m.is_active():
            if active_membership is None or m.remaining_sessions > active_membership.remaining_sessions:
                active_membership = m

    if not active_membership:
        next_waitlist.status = 'cancelled'
        db.session.commit()
        return process_waitlist(course_id)

    if active_membership.card_type != 'monthly' and active_membership.remaining_sessions <= 0:
        next_waitlist.status = 'cancelled'
        db.session.commit()
        return process_waitlist(course_id)

    booking = Booking(
        member_id=member.id,
        course_id=course_id,
        status='booked'
    )
    db.session.add(booking)

    next_waitlist.status = 'converted'
    next_waitlist.converted_to_booking_at = datetime.utcnow()

    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()

    for idx, wl in enumerate(waitlists):
        wl.position = idx + 1

    db.session.commit()

    return {
        'member_id': member.id,
        'member_name': member.name,
        'member_phone': member.phone,
        'booking': booking.to_dict()
    }


@course_bp.route('/<int:course_id>/cancel', methods=['POST'])
def cancel_booking(course_id):
    data = request.get_json()

    if not data or 'member_id' not in data:
        return jsonify({'error': '缺少会员ID'}), 400

    member_id = data['member_id']

    booking = Booking.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='booked'
    ).first()

    if not booking:
        return jsonify({'error': '未找到预约记录'}), 404

    course = Course.query.get(course_id)
    if not course.can_cancel():
        return jsonify({'error': '开课前2小时内无法取消，将扣除课时'}), 400

    booking.status = 'cancelled'
    booking.cancelled_at = datetime.utcnow()
    db.session.flush()

    converted_member = process_waitlist(course_id)

    db.session.commit()

    response_data = {
        'message': '取消成功，不扣除课时',
        'booking': booking.to_dict()
    }

    if converted_member:
        response_data['waitlist_converted'] = {
            'message': f'已自动为候补会员 {converted_member["member_name"]} 补上名额',
            'member': converted_member
        }

    return jsonify(response_data), 200


@course_bp.route('/<int:course_id>/waitlist', methods=['POST'])
def join_waitlist(course_id):
    data = request.get_json()

    if not data or 'member_id' not in data:
        return jsonify({'error': '缺少会员ID'}), 400

    member_id = data['member_id']
    max_waitlist = 5

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

    if waitlist_count >= max_waitlist:
        return jsonify({'error': '候补名单已满（最多5人）'}), 400

    active_membership = None
    for m in member.memberships:
        if m.is_active():
            if active_membership is None or m.remaining_sessions > active_membership.remaining_sessions:
                active_membership = m

    if not active_membership:
        return jsonify({'error': '没有有效的会员卡'}), 400

    if active_membership.card_type != 'monthly' and active_membership.remaining_sessions <= 0:
        return jsonify({'error': '会员卡次数不足'}), 400

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


@course_bp.route('/<int:course_id>/waitlist/<int:member_id>', methods=['GET'])
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


@course_bp.route('/<int:course_id>/waitlist/cancel', methods=['POST'])
def cancel_waitlist(course_id):
    data = request.get_json()

    if not data or 'member_id' not in data:
        return jsonify({'error': '缺少会员ID'}), 400

    member_id = data['member_id']

    waitlist = Waitlist.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='waiting'
    ).first()

    if not waitlist:
        return jsonify({'error': '您未在候补名单中'}), 404

    waitlist.status = 'cancelled'
    db.session.flush()

    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()

    for idx, wl in enumerate(waitlists):
        wl.position = idx + 1

    db.session.commit()

    return jsonify({
        'message': '候补取消成功',
        'waitlist': waitlist.to_dict()
    }), 200


@course_bp.route('/<int:course_id>/waitlist', methods=['GET'])
def get_course_waitlist(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()

    result = []
    for wl in waitlists:
        member = Member.query.get(wl.member_id)
        wl_dict = wl.to_dict()
        if member:
            wl_dict['member_name'] = member.name
            wl_dict['member_phone'] = member.phone
        result.append(wl_dict)

    return jsonify({
        'course_id': course_id,
        'course_name': course.name,
        'total_waiting': len(result),
        'max_waitlist': 5,
        'waitlist': result
    }), 200


@course_bp.route('/member/<int:member_id>/waitlist', methods=['GET'])
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


@course_bp.route('/<int:course_id>', methods=['PUT'])
def update_course(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    data = request.get_json()

    if 'name' in data:
        course.name = data['name']
    if 'description' in data:
        course.description = data['description']
    if 'coach_id' in data:
        coach = Coach.query.get(data['coach_id'])
        if not coach:
            return jsonify({'error': '教练不存在'}), 404
        course.coach_id = data['coach_id']
    if 'course_date' in data:
        try:
            course.course_date = datetime.strptime(data['course_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': '日期格式错误'}), 400
    if 'start_time' in data:
        try:
            course.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        except ValueError:
            return jsonify({'error': '时间格式错误'}), 400
    if 'end_time' in data:
        try:
            course.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        except ValueError:
            return jsonify({'error': '时间格式错误'}), 400
    if 'capacity' in data:
        course.capacity = data['capacity']

    db.session.commit()

    return jsonify({
        'message': '课程更新成功',
        'course': course.to_dict()
    }), 200


@course_bp.route('/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '课程不存在'}), 404

    bookings = Booking.query.filter_by(course_id=course_id, status='booked').all()
    for booking in bookings:
        booking.status = 'cancelled'
        booking.cancelled_at = datetime.utcnow()

    db.session.delete(course)
    db.session.commit()

    return jsonify({
        'message': '课程删除成功，所有预约已取消'
    }), 200


@course_bp.route('/member/<int:member_id>/bookings', methods=['GET'])
def get_member_bookings(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    status = request.args.get('status', 'booked')

    query = Booking.query.filter_by(member_id=member_id)
    if status != 'all':
        query = query.filter_by(status=status)

    bookings = query.order_by(Booking.created_at.desc()).all()

    result = []
    for booking in bookings:
        booking_dict = booking.to_dict()
        course = Course.query.get(booking.course_id)
        if course:
            booking_dict['course'] = course.to_dict()
        result.append(booking_dict)

    return jsonify({
        'bookings': result
    }), 200


@course_bp.route('/batch-create', methods=['POST'])
def batch_create_courses():
    data = request.get_json()

    if not data or 'courses' not in data:
        return jsonify({'error': '缺少课程列表'}), 400

    created_courses = []
    errors = []

    for idx, course_data in enumerate(data['courses']):
        try:
            required_fields = ['name', 'coach_id', 'course_date', 'start_time', 'end_time']
            for field in required_fields:
                if field not in course_data:
                    errors.append(f'第{idx+1}个课程缺少字段: {field}')
                    continue

            coach = Coach.query.get(course_data['coach_id'])
            if not coach:
                errors.append(f'第{idx+1}个课程教练不存在')
                continue

            course_date = datetime.strptime(course_data['course_date'], '%Y-%m-%d').date()
            start_time = datetime.strptime(course_data['start_time'], '%H:%M').time()
            end_time = datetime.strptime(course_data['end_time'], '%H:%M').time()

            if start_time >= end_time:
                errors.append(f'第{idx+1}个课程时间设置错误')
                continue

            capacity = course_data.get('capacity', current_app.config['MAX_COURSE_CAPACITY'])

            course = Course(
                name=course_data['name'],
                description=course_data.get('description', ''),
                coach_id=course_data['coach_id'],
                course_date=course_date,
                start_time=start_time,
                end_time=end_time,
                capacity=capacity
            )
            db.session.add(course)
            db.session.flush()
            created_courses.append(course.to_dict())
        except Exception as e:
            errors.append(f'第{idx+1}个课程创建失败: {str(e)}')

    db.session.commit()

    return jsonify({
        'message': f'成功创建{len(created_courses)}个课程',
        'created_courses': created_courses,
        'errors': errors
    }), 201


@course_bp.route('/generate-weekly', methods=['POST'])
def generate_weekly_schedule():
    data = request.get_json()

    if not data or 'template' not in data or 'week_offset' not in data:
        return jsonify({'error': '缺少必要参数'}), 400

    week_offset = data['week_offset']
    template = data['template']

    start_date, end_date = get_week_range(week_offset)

    created_courses = []
    errors = []

    for item in template:
        try:
            weekday = item['weekday']
            if weekday < 0 or weekday > 6:
                errors.append(f'星期值{weekday}无效，应为0-6')
                continue

            course_date = start_date + timedelta(days=weekday)

            coach = Coach.query.get(item['coach_id'])
            if not coach:
                errors.append(f'教练ID{item["coach_id"]}不存在')
                continue

            start_time = datetime.strptime(item['start_time'], '%H:%M').time()
            end_time = datetime.strptime(item['end_time'], '%H:%M').time()

            capacity = item.get('capacity', current_app.config['MAX_COURSE_CAPACITY'])

            course = Course(
                name=item['name'],
                description=item.get('description', ''),
                coach_id=item['coach_id'],
                course_date=course_date,
                start_time=start_time,
                end_time=end_time,
                capacity=capacity
            )
            db.session.add(course)
            db.session.flush()
            created_courses.append(course.to_dict())
        except Exception as e:
            errors.append(f'创建课程失败: {str(e)}')

    db.session.commit()

    return jsonify({
        'message': f'成功生成{len(created_courses)}个课程',
        'week_start': start_date.isoformat(),
        'week_end': end_date.isoformat(),
        'created_courses': created_courses,
        'errors': errors
    }), 201
