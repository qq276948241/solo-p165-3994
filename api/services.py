from datetime import datetime
from models import db, Member, Membership, Course, Booking, Waitlist


MAX_WAITLIST = 5


def get_active_membership(member_id):
    memberships = Membership.query.filter_by(member_id=member_id).all()
    active_membership = None
    for m in memberships:
        if m.is_active():
            if active_membership is None or m.remaining_sessions > active_membership.remaining_sessions:
                active_membership = m
    return active_membership


def validate_membership_for_booking(member):
    active_membership = get_active_membership(member.id)
    if not active_membership:
        return None, '没有有效的会员卡'
    if active_membership.card_type != 'monthly' and active_membership.remaining_sessions <= 0:
        return None, '会员卡次数不足'
    return active_membership, None


def reindex_waitlist_positions(course_id):
    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()
    for idx, wl in enumerate(waitlists):
        wl.position = idx + 1


def convert_waitlist_entry(waitlist_entry):
    waitlist_entry.status = 'converted'
    waitlist_entry.converted_to_booking_at = datetime.utcnow()
    reindex_waitlist_positions(waitlist_entry.course_id)


def process_waitlist(course_id):
    try:
        course = Course.query.get(course_id)
        if not course:
            return None

        if course.is_full():
            return None

        next_entry = Waitlist.query.filter_by(
            course_id=course_id,
            status='waiting'
        ).order_by(Waitlist.position).first()

        if not next_entry:
            return None

        member = Member.query.get(next_entry.member_id)
        if not member:
            next_entry.status = 'cancelled'
            db.session.flush()
            return process_waitlist(course_id)

        existing_booking = Booking.query.filter_by(
            member_id=member.id,
            course_id=course_id,
            status='booked'
        ).first()
        if existing_booking:
            next_entry.status = 'cancelled'
            db.session.flush()
            return process_waitlist(course_id)

        active_membership, error = validate_membership_for_booking(member)
        if error:
            next_entry.status = 'cancelled'
            db.session.flush()
            return process_waitlist(course_id)

        booking = Booking(
            member_id=member.id,
            course_id=course_id,
            status='booked'
        )
        db.session.add(booking)
        db.session.flush()

        if booking.id is None:
            return None

        next_entry.status = 'converted'
        next_entry.converted_to_booking_at = datetime.utcnow()

        reindex_waitlist_positions(course_id)

        db.session.flush()

        return {
            'member_id': member.id,
            'member_name': member.name,
            'member_phone': member.phone,
            'booking': booking.to_dict()
        }
    except Exception:
        db.session.rollback()
        return None


def get_waitlist_info_for_course(course_id):
    waitlists = Waitlist.query.filter_by(
        course_id=course_id,
        status='waiting'
    ).order_by(Waitlist.position).all()

    members = []
    for wl in waitlists:
        member = Member.query.get(wl.member_id)
        if member:
            members.append({
                'waitlist_id': wl.id,
                'member_id': member.id,
                'name': member.name,
                'phone': member.phone,
                'position': wl.position
            })

    return {
        'count': len(members),
        'max_waitlist': MAX_WAITLIST,
        'members': members
    }


def cancel_waitlist_entry(course_id, member_id):
    waitlist = Waitlist.query.filter_by(
        member_id=member_id,
        course_id=course_id,
        status='waiting'
    ).first()

    if not waitlist:
        return None

    waitlist.status = 'cancelled'
    db.session.flush()

    reindex_waitlist_positions(course_id)

    return waitlist
