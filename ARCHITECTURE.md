# 社区健身工作室后端 — 架构说明

> 读本文档大约需要 10 分钟。不需要有 Flask/SQLAlchemy 背景，看懂业务流程就行。

---

## 一、这项目是干嘛的

给社区健身工作室用的小程序后端。会员可以扫码注册、绑手机号、查自己卡上还剩几次、约课；课满了可以排队候补，有人取消就自动顶上；上课前教练拿手机扫会员码签到，系统根据卡类型自动扣次（次卡扣 1 次，月卡不扣）；教练端能看自己今天带了几节课、每节课有哪些人报名、谁没来。

一句话：**会员注册 → 办卡 → 约课 → 签到扣次 → 教练看数据**，这一整条链路的后端 API。

**技术栈**：Python Flask + SQLite（通过 SQLAlchemy ORM 操作），纯 API 服务，没有前端页面。

---

## 二、代码结构：每个文件是干嘛的

### 入口和配置

| 文件 | 作用 |
|------|------|
| [app.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/app.py) | 程序入口。创建 Flask 应用，把下面 5 个 API 模块的 Blueprint 挂上去，启动后监听 5000 端口 |
| [config.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/config.py) | 配置项，见本文第五节 |
| [models.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/models.py) | 数据库表结构定义（7 张表），见本文第三节 |
| [requirements.txt](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/requirements.txt) | 依赖清单：Flask、Flask-SQLAlchemy、Werkzeug |
| [init_db.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/init_db.py) | 建表 + 灌测试数据（3 个教练、5 个会员、两周课程），演示用 |
| [test_api.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/test_api.py) | 自动化测试脚本，15 个用例覆盖全流程，跑完没问题就是没坏 |

### API 模块（5 个，都在 `api/` 目录下）

按业务领域拆分，一个 Blueprint 管一块 URL 前缀：

| 文件 | URL 前缀 | 管什么事 | 主要接口 |
|------|----------|----------|----------|
| [member.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/member.py) | `/api/member` | 会员相关 | 扫码注册、手机号查询、绑卡/换手机号、查会员卡余额、查打卡历史 |
| [course.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/course.py) | `/api/course` | 课程和预约 | 创建课程、按周查排期、预约课程、取消预约、更新/删除课程、批量排课 |
| [waitlist.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/waitlist.py) | `/api/waitlist` | 候补排队 | 加入候补、查自己排第几、取消候补、查看某节课候补名单、查看会员所有候补 |
| [checkin.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/checkin.py) | `/api/checkin` | 签到扣次 | 教练扫会员码签到（自动按卡类型扣次）、查某节课签到情况、查会员打卡记录、签到统计 |
| [coach.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/coach.py) | `/api/coach` | 教练端 | 教练注册/登录、看自己带的课、看某节课学员名单、学员签到明细、教学统计 |

### 业务逻辑层

| 文件 | 作用 |
|------|------|
| [services.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo165/project165/api/services.py) | **共享业务函数**，不对外暴露 HTTP 接口，被上面 5 个模块内部调用。比如：判断会员卡是否有效、有人取消预约时自动从候补名单顶人、候补位置重排。目的是让路由文件薄一点，别把几十行业务逻辑塞在 `@app.route` 下面 |

> 设计原则：**路由函数只做三件事**——收参数、调 service、拼返回值。真正的"该不该扣次""候补能不能顶上"这种判断，全写在 services.py 里。

---

## 三、数据长什么样（数据库表 + 关系）

一共 7 张表，用 SQLAlchemy ORM 定义在 `models.py` 里，数据库是单个文件 `gym.db`（SQLite）。

### 表清单

| 表名 | 中文名 | 关键字段 | 说明 |
|------|--------|----------|------|
| `members` | 会员 | id、phone（唯一）、name、qr_code（唯一） | 一个会员一条记录 |
| `memberships` | 会员卡 | id、member_id、card_type、total_sessions、remaining_sessions、start_date、end_date | 一个会员可以有多张卡（比如先用完一张 10 次卡再买一张月卡） |
| `coaches` | 教练 | id、phone（唯一）、name、password_hash | 教练需要密码登录看自己的数据 |
| `courses` | 课程 | id、name、coach_id、course_date、start_time、end_time、capacity | 一节课一条记录，某教练在某天上某节课 |
| `bookings` | 预约 | id、member_id、course_id、status（booked/cancelled）、cancelled_at | 会员约了哪节课 |
| `waitlists` | 候补 | id、member_id、course_id、position、status（waiting/converted/cancelled）、converted_to_booking_at | 课程满员后会员排队，position 是排队位置 |
| `checkins` | 签到 | id、member_id、course_id、booking_id、checkin_time、sessions_deducted、card_type_used | 教练扫码后产生一条签到记录，记录扣了几次、用的什么卡 |

### 关系（大白话版）

```
会员 1 ──── * 会员卡         （一个人可以有多张卡，用完一张买下一张）
会员 1 ──── * 预约           （一个人可以约多节课）
会员 1 ──── * 候补           （一个人可以在多节课排队）
会员 1 ──── * 签到           （一个人可以有多次打卡记录）

教练 1 ──── * 课程           （一个教练带多节课）

课程 1 ──── * 预约           （一节课有多人报名）
课程 1 ──── * 候补           （一节课满了之后有多人排队）
课程 1 ──── * 签到           （一节课有多人签到）

预约 1 ──── 0/1 签到         （预约了不一定来，来了才有签到记录）
候补 1 ──── 0/1 预约         （候补被顶上之后会生成一条对应预约记录）
```

两张关键关联表的设计意图：
- **预约和候补分开存**：候补不是"特殊的预约"，两者是不同业务状态。候补成功了再生成一条真正的 Booking，候补记录自己更新 status=converted 保留历史。
- **签到挂在预约下面**：签到必须有预约做前提（防止没约课直接来签到蹭课），扣次记录存在签到表里方便对账。

---

## 四、数据怎么流转：会员从进门到上课的完整链路

从一个新会员走进健身房开始，按时间顺序讲：

### 步骤 1：扫码注册

```
前台/自助机扫码
    ↓
POST /api/member/scan  { qr_code: "GYM-XXX" }
    ↓  第一次扫：没这个会员
POST /api/member/register  { phone: "138xxxx", name: "小明" }
    ↓
系统自动生成：
  ├── members 表插一条（phone、name、自动生成唯一 qr_code）
  └── memberships 表插一张「体验卡」（1 次、7 天有效，送新用户的）
```

### 步骤 2：查自己卡

```
会员小程序
    ↓
GET /api/member/<id>/card
    ↓
返回：
  ├── 卡类型（monthly 月卡 / prepaid_10 十次卡 / experience 体验卡）
  ├── 剩余次数（月卡显示 30/30，实际不扣）
  └── 有效期起止
```

### 步骤 3：查课 + 约课

```
会员看排期 → GET /api/course/next-week      （下周课表）
           → GET /api/course/schedule?week_offset=0  （本周课表）
    ↓
挑一节课约 → POST /api/course/<course_id>/book { member_id: 123 }
    ↓
系统校验（全在 services.py 里）：
  ✓ 课程没开始
  ✓ 课程没满员（capacity 默认 12 人）
  ✓ 会员有有效会员卡且次数足够
  ✓ 没重复约这节课
    ↓
bookings 表插一条 status='booked'
```

### 步骤 3.5：课满了 → 候补排队

```
POST /api/course/<id>/book → 返回 400 "课程已满，可加入候补排队"
    ↓
POST /api/waitlist/<id> { member_id: 123 }
    ↓
校验：课程确实满了 + 会员卡有效 + 没排过队
    ↓
waitlists 表插一条 status='waiting', position=N（当前排队第 N 位）
    ↓
会员端显示："候补登记成功，您当前候补第 2 位"
```

**自动补位逻辑（关键）**：当有别人取消预约时：

```
会员A 取消 → POST /api/course/<id>/cancel
    ↓
booking.status = 'cancelled'  →  flush
    ↓
process_waitlist(course_id) 被调用（services.py）：
  1. 查课程是否还有空位
  2. 按 position 取第一个 waiting 的候补记录
  3. 检查这个候补会员的卡是否还有效、次数是否够（可能排了 3 天卡过期了）
  4. 有效 → 生成一条新 Booking + 候补 status 改成 converted + 后面所有人 position 减 1
  5. 无效 → 把这个候补踢掉 status=cancelled + 递归找下一个
    ↓
返回值里带 waitlist_converted 字段："已自动为候补会员 XX 补上名额"
```

### 步骤 4：签到 + 扣次

```
上课当天，教练拿手机扫会员二维码
    ↓
POST /api/checkin/scan { qr_code: "GYM-XXX", course_id: 42, coach_id: 7 }
    ↓
校验：
  ✓ 二维码是有效会员
  ✓ 扫的教练确实是这节课的教练（防止乱扫）
  ✓ 课前 1 小时内 ~ 课后 2 小时内（时间窗口）
  ✓ 会员确实预约了这节课
  ✓ 没重复签到过
    ↓
扣次逻辑（services.validate_membership_for_booking）：
  - 月卡 → sessions_deducted = 0，不扣
  - 次卡/体验卡 → membership.remaining_sessions -= 1，sessions_deducted = 1
    ↓
checkins 表插一条（记录扣了几次、用的什么卡，方便对账）
    ↓
返回：签到成功 + 扣了几次 + 卡上还剩几次
```

### 步骤 5：教练端看数据

```
教练登录 → POST /api/coach/login { phone, password }
看自己课 → GET /api/coach/<id>/courses/today
           返回每节课的：课程名、时间、报名人数、实到人数、学员名单（谁签到了谁没签）
看学员   → GET /api/coach/<id>/students
           所有带过课的学员，按签到次数排序
```

---

## 五、关键配置项（config.py）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask 加密用的 key，部署到线上一定要改成环境变量，别写死在代码里 |
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///gym.db` | 数据库连接串。现在用的是 SQLite 文件，要换 MySQL/PostgreSQL 只改这一行 |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | `False` | 关掉 SQLAlchemy 的修改跟踪通知，省内存。一般都设 False |
| `MAX_COURSE_CAPACITY` | `12` | 每节课默认上限人数，创建课程时不传 capacity 就用这个值 |
| `CANCELLATION_WINDOW_HOURS` | `2` | 免费取消窗口，开课前 2 小时内取消就扣课时。目前代码里只用在 Booking.can_cancel() 判断里 |

---

## 六、已知小问题 + 后续可以优化的方向

不是 bug，是目前实现简单、后续真要上线得补的东西：

### 已知问题 / 技术债

1. **没做认证鉴权**：现在所有接口都是裸的，拿到 member_id 就能操作任意会员的数据。上线至少得加个 JWT 或 Token 校验，教练端和会员端分开权限。
2. **SQLite 够用但扛不住并发**：SQLite 单文件锁粒度粗，真有几十个教练同时扫码签到可能会卡。上生产建议换 PostgreSQL。
3. **手机号不做验证**：注册时随便填 11 位数字就行，没发短信验证码。
4. **SECRET_KEY 写死在代码里**：`config.py` 里默认值是明文，部署时必须通过环境变量覆盖。
5. **没有分页**：打卡记录、签到列表之类的接口只做了简单分页参数，数据量大了会慢。
6. **候补最多 5 人是硬编码**：`services.py` 里 `MAX_WAITLIST = 5`，没有放到 config.py 也没有给课程单独设置。
7. **UTC 时间 vs 本地时间**：全用 `datetime.utcnow()`，中国用户看到的时间差 8 小时。签到时间窗口、课程显示都得转成本地时区。

### 可以继续加的功能

- **消息通知**：候补被顶上、课程改时间、签到成功，推微信小程序模板消息或短信。
- **会员卡充值/续费**：现在卡只能注册时送一张或 init_db.py 手动插，得做购买接口。
- **数据统计面板**：工作室老板看的维度——月出勤率、热门课程排行、教练课时统计。
- **请假/补课**：会员请假系统自动留位置，补课安排到其他班。
- **二维码安全性**：现在 qr_code 是固定字符串，容易被截图伪造。可以做成每次刷新的动态码或者加上时间戳签名。
- **并发扣次加锁**：现在扣次是读 remaining_sessions → 减 1 → 写回，两个教练同时扫同一个会员可能超扣。要加数据库行级锁或乐观锁。

---

## 七、怎么跑起来

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 建表 + 灌测试数据（可选，会生成 3 个教练账号）
python init_db.py

# 3. 启动服务
python app.py
# → 监听 http://localhost:5000

# 4. 跑测试（确保没坏）
python test_api.py
```

测试账号（init_db.py 生成的）：
- 教练：`13800138001` / `123456`（张教练）
- 会员二维码：`GYM-TEST0001` ~ `GYM-TEST0005`

健康检查：`GET http://localhost:5000/api/health` → 返回 `{"status":"ok"}`
