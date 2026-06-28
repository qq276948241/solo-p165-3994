import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from models import db, Member, Membership


member_bp = Blueprint('member', __name__)


def generate_qr_code():
    return f"GYM-{uuid.uuid4().hex[:12].upper()}"


@member_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or 'phone' not in data:
        return jsonify({'error': '手机号不能为空'}), 400

    phone = data['phone'].strip()
    name = data.get('name', '')

    existing_member = Member.query.filter_by(phone=phone).first()
    if existing_member:
        return jsonify({
            'message': '该手机号已注册',
            'member': existing_member.to_dict()
        }), 200

    qr_code = generate_qr_code()
    while Member.query.filter_by(qr_code=qr_code).first():
        qr_code = generate_qr_code()

    member = Member(
        phone=phone,
        name=name,
        qr_code=qr_code
    )
    db.session.add(member)
    db.session.flush()

    membership = Membership(
        member_id=member.id,
        card_type='experience',
        total_sessions=1,
        remaining_sessions=1,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(membership)
    db.session.commit()

    return jsonify({
        'message': '注册成功',
        'member': member.to_dict(),
        'membership': membership.to_dict()
    }), 201


@member_bp.route('/scan', methods=['POST'])
def scan_qr():
    data = request.get_json()

    if not data or 'qr_code' not in data:
        return jsonify({'error': '二维码不能为空'}), 400

    qr_code = data['qr_code'].strip()
    member = Member.query.filter_by(qr_code=qr_code).first()

    if not member:
        return jsonify({'error': '无效的二维码'}), 404

    active_membership = Membership.query.filter_by(
        member_id=member.id
    ).order_by(Membership.created_at.desc()).first()

    return jsonify({
        'message': '扫码成功',
        'member': member.to_dict(),
        'membership': active_membership.to_dict() if active_membership else None
    }), 200


@member_bp.route('/<int:member_id>/card', methods=['GET'])
def get_card_info(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    memberships = Membership.query.filter_by(member_id=member_id).all()

    active_membership = None
    for m in memberships:
        if m.is_active():
            if active_membership is None or m.remaining_sessions > active_membership.remaining_sessions:
                active_membership = m

    return jsonify({
        'member': member.to_dict(),
        'active_membership': active_membership.to_dict() if active_membership else None,
        'all_memberships': [m.to_dict() for m in memberships]
    }), 200


@member_bp.route('/<int:member_id>/bind-phone', methods=['PUT'])
def bind_phone(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    data = request.get_json()
    if not data or 'phone' not in data:
        return jsonify({'error': '手机号不能为空'}), 400

    new_phone = data['phone'].strip()

    existing_member = Member.query.filter_by(phone=new_phone).first()
    if existing_member and existing_member.id != member_id:
        return jsonify({'error': '该手机号已被其他用户绑定'}), 400

    member.phone = new_phone
    db.session.commit()

    return jsonify({
        'message': '手机号绑定成功',
        'member': member.to_dict()
    }), 200


@member_bp.route('/<int:member_id>/checkins', methods=['GET'])
def get_checkin_history(member_id):
    member = Member.query.get(member_id)
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    checkins = sorted(member.checkins, key=lambda c: c.checkin_time, reverse=True)
    total = len(checkins)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_checkins = checkins[start:end]

    result = []
    for checkin in paginated_checkins:
        checkin_dict = checkin.to_dict()
        checkin_dict['course_name'] = checkin.booking.course.name if checkin.booking and checkin.booking.course else None
        result.append(checkin_dict)

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'checkins': result
    }), 200


@member_bp.route('/by-phone', methods=['GET'])
def get_member_by_phone():
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'error': '手机号不能为空'}), 400

    member = Member.query.filter_by(phone=phone).first()
    if not member:
        return jsonify({'error': '会员不存在'}), 404

    return jsonify({
        'member': member.to_dict()
    }), 200
