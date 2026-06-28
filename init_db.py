from datetime import datetime, timedelta, time
from app import create_app
from models import db, Member, Membership, Coach, Course, Booking, CheckIn


def init_database():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        print("数据库表创建成功！")

        coach1 = Coach(phone='13800138001', name='张教练')
        coach1.set_password('123456')

        coach2 = Coach(phone='13800138002', name='李教练')
        coach2.set_password('123456')

        coach3 = Coach(phone='13800138003', name='王教练')
        coach3.set_password('123456')

        db.session.add_all([coach1, coach2, coach3])
        db.session.flush()

        print(f"教练创建成功: {coach1.name}, {coach2.name}, {coach3.name}")

        members_data = [
            {'phone': '13900139001', 'name': '会员小明'},
            {'phone': '13900139002', 'name': '会员小红'},
            {'phone': '13900139003', 'name': '会员小刚'},
            {'phone': '13900139004', 'name': '会员小美'},
            {'phone': '13900139005', 'name': '会员小强'},
        ]

        members = []
        for idx, data in enumerate(members_data):
            member = Member(
                phone=data['phone'],
                name=data['name'],
                qr_code=f"GYM-TEST{idx+1:04d}"
            )
            db.session.add(member)
            members.append(member)

        db.session.flush()
        print(f"会员创建成功: {len(members)} 位")

        for idx, member in enumerate(members):
            if idx < 2:
                card_type = 'monthly'
                total_sessions = 30
                remaining_sessions = 30
                end_date = datetime.utcnow() + timedelta(days=30)
            elif idx < 4:
                card_type = 'prepaid_10'
                total_sessions = 10
                remaining_sessions = 10
                end_date = datetime.utcnow() + timedelta(days=90)
            else:
                card_type = 'experience'
                total_sessions = 1
                remaining_sessions = 1
                end_date = datetime.utcnow() + timedelta(days=7)

            membership = Membership(
                member_id=member.id,
                card_type=card_type,
                total_sessions=total_sessions,
                remaining_sessions=remaining_sessions,
                start_date=datetime.utcnow(),
                end_date=end_date
            )
            db.session.add(membership)

        print("会员卡创建成功")

        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())

        course_templates = [
            {'name': '瑜伽基础', 'coach_id': coach1.id, 'weekday': 0, 'start': '09:00', 'end': '10:00'},
            {'name': '动感单车', 'coach_id': coach2.id, 'weekday': 0, 'start': '18:00', 'end': '19:00'},
            {'name': '力量训练', 'coach_id': coach3.id, 'weekday': 1, 'start': '10:00', 'end': '11:00'},
            {'name': '普拉提', 'coach_id': coach1.id, 'weekday': 1, 'start': '19:00', 'end': '20:00'},
            {'name': '有氧舞蹈', 'coach_id': coach2.id, 'weekday': 2, 'start': '09:00', 'end': '10:00'},
            {'name': '核心训练', 'coach_id': coach3.id, 'weekday': 2, 'start': '18:00', 'end': '19:00'},
            {'name': '拉伸放松', 'coach_id': coach1.id, 'weekday': 3, 'start': '10:00', 'end': '11:00'},
            {'name': 'HIIT燃脂', 'coach_id': coach2.id, 'weekday': 3, 'start': '19:00', 'end': '20:00'},
            {'name': '拳击训练', 'coach_id': coach3.id, 'weekday': 4, 'start': '09:00', 'end': '10:00'},
            {'name': '形体塑造', 'coach_id': coach1.id, 'weekday': 4, 'start': '18:00', 'end': '19:00'},
            {'name': '动感单车', 'coach_id': coach2.id, 'weekday': 5, 'start': '10:00', 'end': '11:00'},
            {'name': '瑜伽进阶', 'coach_id': coach3.id, 'weekday': 6, 'start': '09:00', 'end': '10:30'},
        ]

        created_courses = []
        for week_offset in [0, 1]:
            for template in course_templates:
                course_date = monday + timedelta(weeks=week_offset, days=template['weekday'])
                start_time = datetime.strptime(template['start'], '%H:%M').time()
                end_time = datetime.strptime(template['end'], '%H:%M').time()

                course = Course(
                    name=template['name'],
                    description=f'{template["name"]}课程',
                    coach_id=template['coach_id'],
                    course_date=course_date,
                    start_time=start_time,
                    end_time=end_time,
                    capacity=12
                )
                db.session.add(course)
                created_courses.append(course)

        db.session.flush()
        print(f"课程创建成功: {len(created_courses)} 节")

        upcoming_courses = [c for c in created_courses if c.course_date >= today]
        if upcoming_courses:
            for i, member in enumerate(members):
                for j in range(min(3, len(upcoming_courses))):
                    course = upcoming_courses[(i + j) % len(upcoming_courses)]

                    existing = Booking.query.filter_by(
                        member_id=member.id,
                        course_id=course.id,
                        status='booked'
                    ).first()

                    if not existing and not course.is_full():
                        booking = Booking(
                            member_id=member.id,
                            course_id=course.id,
                            status='booked'
                        )
                        db.session.add(booking)

        print("预约记录创建成功")

        db.session.commit()

        print("\n=== 测试数据创建完成 ===")
        print(f"教练账号:")
        print(f"  张教练: 13800138001 / 123456")
        print(f"  李教练: 13800138002 / 123456")
        print(f"  王教练: 13800138003 / 123456")
        print(f"\n会员二维码:")
        for member in members:
            print(f"  {member.name}: {member.qr_code}")
        print(f"\n共创建:")
        print(f"  教练: {Coach.query.count()} 位")
        print(f"  会员: {Member.query.count()} 位")
        print(f"  会员卡: {Membership.query.count()} 张")
        print(f"  课程: {Course.query.count()} 节")
        print(f"  预约: {Booking.query.count()} 条")
        print(f"  签到: {CheckIn.query.count()} 条")


if __name__ == '__main__':
    init_database()
