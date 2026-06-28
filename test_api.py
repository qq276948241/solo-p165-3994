import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from app import create_app
from models import db, Member, Membership, Coach, Course, Booking, CheckIn


def run_tests():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        print("=" * 60)
        print("开始 API 功能测试")
        print("=" * 60)

        client = app.test_client()

        print("\n[1/8] 测试教练注册...")
        resp = client.post('/api/coach/register', json={
            'phone': '13800138001',
            'name': '张教练',
            'password': '123456'
        })
        assert resp.status_code == 201, f"教练注册失败: {resp.get_json()}"
        coach_data = resp.get_json()
        coach_id = coach_data['coach']['id']
        print(f"  ✓ 教练注册成功: {coach_data['coach']['name']} (ID: {coach_id})")

        print("\n[2/8] 测试教练登录...")
        resp = client.post('/api/coach/login', json={
            'phone': '13800138001',
            'password': '123456'
        })
        assert resp.status_code == 200, f"教练登录失败: {resp.get_json()}"
        print(f"  ✓ 教练登录成功")

        print("\n[3/8] 测试会员注册...")
        resp = client.post('/api/member/register', json={
            'phone': '13900139001',
            'name': '测试会员'
        })
        assert resp.status_code == 201, f"会员注册失败: {resp.get_json()}"
        member_data = resp.get_json()
        member_id = member_data['member']['id']
        qr_code = member_data['member']['qr_code']
        print(f"  ✓ 会员注册成功: {member_data['member']['name']} (ID: {member_id}, QR: {qr_code})")

        print("\n[4/8] 测试会员卡信息查询...")
        resp = client.get(f'/api/member/{member_id}/card')
        assert resp.status_code == 200, f"查询会员卡失败: {resp.get_json()}"
        card_data = resp.get_json()
        print(f"  ✓ 会员卡查询成功: 卡类型={card_data['active_membership']['card_type']}, 剩余次数={card_data['active_membership']['remaining_sessions']}")

        print("\n[5/8] 测试创建课程...")
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        resp = client.post('/api/course', json={
            'name': '瑜伽测试课',
            'description': '测试用瑜伽课程',
            'coach_id': coach_id,
            'course_date': tomorrow.isoformat(),
            'start_time': '10:00',
            'end_time': '11:00',
            'capacity': 12
        })
        assert resp.status_code == 201, f"创建课程失败: {resp.get_json()}"
        course_data = resp.get_json()
        course_id = course_data['course']['id']
        print(f"  ✓ 课程创建成功: {course_data['course']['name']} (ID: {course_id})")

        print("\n[6/8] 测试课程预约...")
        resp = client.post(f'/api/course/{course_id}/book', json={
            'member_id': member_id
        })
        assert resp.status_code == 201, f"课程预约失败: {resp.get_json()}"
        booking_data = resp.get_json()
        booking_id = booking_data['booking']['id']
        print(f"  ✓ 课程预约成功 (预约ID: {booking_id})")

        print("\n[7/8] 测试下周排期查询...")
        resp = client.get('/api/course/next-week')
        assert resp.status_code == 200, f"查询下周排期失败: {resp.get_json()}"
        schedule_data = resp.get_json()
        print(f"  ✓ 下周排期查询成功: 共 {len(schedule_data['courses'])} 节课, 时间范围 {schedule_data['week_start']} ~ {schedule_data['week_end']}")

        print("\n[8/8] 测试取消预约...")
        resp = client.post(f'/api/course/{course_id}/cancel', json={
            'member_id': member_id
        })
        assert resp.status_code == 200, f"取消预约失败: {resp.get_json()}"
        print(f"  ✓ 预约取消成功")

        print("\n" + "=" * 60)
        print("✓ 所有基础功能测试通过！")
        print("=" * 60)

        print("\n=== 额外业务逻辑测试 ===")

        print("\n[9/10] 测试会员扫码...")
        resp = client.post('/api/member/scan', json={
            'qr_code': qr_code
        })
        assert resp.status_code == 200, f"扫码失败: {resp.get_json()}"
        print(f"  ✓ 扫码成功: {resp.get_json()['member']['name']}")

        print("\n[10/10] 测试教练查看自己的课程...")
        resp = client.get(f'/api/coach/{coach_id}/courses')
        assert resp.status_code == 200, f"查询教练课程失败: {resp.get_json()}"
        coach_courses = resp.get_json()
        print(f"  ✓ 教练课程查询成功: 本周共 {len(coach_courses['courses'])} 节课")

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！API 功能正常！")
        print("=" * 60)

        print("\n项目结构说明:")
        print("  app.py           - 主应用入口")
        print("  config.py        - 配置文件")
        print("  models.py        - 数据模型 (Member, Membership, Coach, Course, Booking, CheckIn)")
        print("  api/member.py    - 会员模块 (注册、扫码、卡信息、打卡记录)")
        print("  api/course.py    - 课程模块 (排课、查询、预约、取消)")
        print("  api/checkin.py   - 签到模块 (扫码签到、扣次、打卡记录)")
        print("  api/coach.py     - 教练模块 (登录、课程、学员、统计)")
        print("  init_db.py       - 数据库初始化和测试数据")
        print("  requirements.txt - 依赖包")

        print("\n启动命令:")
        print("  python app.py")
        print("\n初始化数据:")
        print("  python init_db.py")


if __name__ == '__main__':
    run_tests()
