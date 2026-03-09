"""
测试数据生成脚本
运行: python manage.py shell < seed_data.py
或: venv\Scripts\python -c "exec(open('seed_data.py', encoding='utf-8').read())"
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import (
    TravelGroup, Subject, Teacher, SchoolClass,
    Location, ClassSubjectTeacher, TeacherQualification
)

print("清除现有数据...")
ClassSubjectTeacher.objects.all().delete()
TeacherQualification.objects.all().delete()
SchoolClass.objects.all().delete()
Teacher.objects.all().delete()
Subject.objects.all().delete()
TravelGroup.objects.all().delete()
Location.objects.all().delete()

print("创建送教分组...")
group_wed = TravelGroup.objects.create(name='周三组', day_off=2)
group_fri = TravelGroup.objects.create(name='周五组', day_off=4)

print("创建场地...")
Location.objects.create(name='操场', location_type='PLAYGROUND', capacity=2)
Location.objects.create(name='家政室', location_type='HOME_EC', capacity=1)

print("创建课程...")
chinese = Subject.objects.create(
    name='语文', weekly_hours=5, is_am_preferred=True,
    allow_consecutive=True, max_daily_limit=2
)
math = Subject.objects.create(
    name='数学', weekly_hours=5, is_am_preferred=True,
    max_daily_limit=1
)
english = Subject.objects.create(
    name='英语', weekly_hours=4, is_am_preferred=False,
    max_daily_limit=1
)
pe = Subject.objects.create(
    name='体育', weekly_hours=2, location_type='PLAYGROUND',
    max_daily_limit=1
)
music = Subject.objects.create(
    name='音乐', weekly_hours=2, max_daily_limit=1
)
art = Subject.objects.create(
    name='美术', weekly_hours=2, max_daily_limit=1
)
class_meeting = Subject.objects.create(
    name='班会', weekly_hours=1, max_daily_limit=1
)
# 校本课程: 每周4节(周二2+周四2), 是合班课
combined_subject = Subject.objects.create(
    name='校本课程', weekly_hours=4, is_combined_class=True, max_daily_limit=2
)

print("创建教师...")
# 注意: 校本课程教师不能有周二(1)或周四(3)的禁排日
teacher_zhang = Teacher.objects.create(name='张老师', travel_group=group_wed)  # 周三禁排 - 可教校本
teacher_li = Teacher.objects.create(name='李老师')  # 无禁排日 - 可教校本
teacher_wang = Teacher.objects.create(name='王老师', travel_group=group_wed)  # 周三禁排 - 可教校本
teacher_zhao = Teacher.objects.create(name='赵老师', travel_group=group_fri)  # 周五禁排 - 可教校本
teacher_chen = Teacher.objects.create(name='陈老师')  # 无禁排日 - 可教校本
teacher_liu = Teacher.objects.create(name='刘老师')  # 无禁排日 - 可教校本
teacher_sun = Teacher.objects.create(name='孙老师')  # 无禁排日 - 可教校本

print("创建班级...")
class_1 = SchoolClass.objects.create(name='一(1)班', grade=1, homeroom_teacher=teacher_zhang)
class_2 = SchoolClass.objects.create(name='一(2)班', grade=1, homeroom_teacher=teacher_wang)
class_3 = SchoolClass.objects.create(name='一(3)班', grade=1, homeroom_teacher=teacher_chen)

print("创建教师资质 (自动分配基础)...")
# 语文: 张老师、陈老师 可教
TeacherQualification.objects.create(teacher=teacher_zhang, subject=chinese)
TeacherQualification.objects.create(teacher=teacher_chen, subject=chinese)

# 数学: 李老师 专职
TeacherQualification.objects.create(teacher=teacher_li, subject=math)

# 英语: 王老师、张老师 可教
TeacherQualification.objects.create(teacher=teacher_wang, subject=english)
TeacherQualification.objects.create(teacher=teacher_zhang, subject=english)

# 体育: 赵老师 专职
TeacherQualification.objects.create(teacher=teacher_zhao, subject=pe)

# 音乐: 刘老师 专职
TeacherQualification.objects.create(teacher=teacher_liu, subject=music)

# 美术: 孙老师 专职
TeacherQualification.objects.create(teacher=teacher_sun, subject=art)

# 校本课程: 需要至少4位教师，且禁排日不在周二/周四
# 选择: 李老师、陈老师、刘老师、孙老师 (都没有周二/周四禁排)
print("设置校本课程教师资质 (需要4位，禁排日不在周二/周四)...")
TeacherQualification.objects.create(teacher=teacher_li, subject=combined_subject)
TeacherQualification.objects.create(teacher=teacher_chen, subject=combined_subject)
TeacherQualification.objects.create(teacher=teacher_liu, subject=combined_subject)
TeacherQualification.objects.create(teacher=teacher_sun, subject=combined_subject)

print("创建手动指定的授课分配 (示例: 一(3)班语文必须由张老师教)...")
# 手动指定: 一(3)班语文 -> 张老师 (虽然陈老师也有资质，但指定张老师)
ClassSubjectTeacher.objects.create(
    school_class=class_3, subject=chinese, teacher=teacher_zhang, is_manual=True
)

print("\n测试数据创建完成!")
print(f"- 送教分组: {TravelGroup.objects.count()}")
print(f"- 场地: {Location.objects.count()}")
print(f"- 课程: {Subject.objects.count()}")
print(f"- 教师: {Teacher.objects.count()}")
print(f"- 班级: {SchoolClass.objects.count()}")
print(f"- 教师资质: {TeacherQualification.objects.count()}")
print(f"- 手动授课分配: {ClassSubjectTeacher.objects.filter(is_manual=True).count()}")

print("\n校本课程教师资质:")
combined_quals = TeacherQualification.objects.filter(subject=combined_subject).select_related('teacher')
for q in combined_quals:
    teacher = q.teacher
    day_off_info = ""
    if teacher.travel_group:
        day_off_info = f" (禁排: {teacher.travel_group.get_day_off_display()})"
    print(f"  {teacher.name}{day_off_info}")

print("\n资质情况:")
for q in TeacherQualification.objects.select_related('teacher', 'subject').order_by('subject__name', 'teacher__name'):
    print(f"  {q.subject.name}: {q.teacher.name}")
