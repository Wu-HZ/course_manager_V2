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
    Location, ClassSubjectTeacher, TeacherQualification, School
)

# 获取或创建默认学校
school, _ = School.objects.get_or_create(
    import_key='default00000000000000000000000000',
    defaults={'name': '默认学校', 'short_name': '默认'}
)

print(f"使用学校: {school.name}")
print("清除该校现有数据...")
ClassSubjectTeacher.objects.filter(school=school).delete()
TeacherQualification.objects.filter(school=school).delete()
SchoolClass.objects.filter(school=school).delete()
Teacher.objects.filter(school=school).delete()
Subject.objects.filter(school=school).delete()
TravelGroup.objects.filter(school=school).delete()
Location.objects.filter(school=school).delete()

print("创建送教分组...")
group_wed = TravelGroup.objects.create(school=school, name='周三组', day_off=2)
group_fri = TravelGroup.objects.create(school=school, name='周五组', day_off=4)

print("创建场地...")
Location.objects.create(school=school, name='操场', location_type='PLAYGROUND', capacity=2)
Location.objects.create(school=school, name='家政室', location_type='HOME_EC', capacity=1)

print("创建课程...")
chinese = Subject.objects.create(
    school=school, name='语文', weekly_hours=5, is_am_preferred=True,
    allow_consecutive=True, max_daily_limit=2
)
math = Subject.objects.create(
    school=school, name='数学', weekly_hours=5, is_am_preferred=True,
    max_daily_limit=1
)
english = Subject.objects.create(
    school=school, name='英语', weekly_hours=4, is_am_preferred=False,
    max_daily_limit=1
)
pe = Subject.objects.create(
    school=school, name='体育', weekly_hours=2, location_type='PLAYGROUND',
    max_daily_limit=1
)
music = Subject.objects.create(
    school=school, name='音乐', weekly_hours=2, max_daily_limit=1
)
art = Subject.objects.create(
    school=school, name='美术', weekly_hours=2, max_daily_limit=1
)
class_meeting = Subject.objects.create(
    school=school, name='班会', weekly_hours=1, max_daily_limit=1
)
# 校本课程: 每周4节(周二2+周四2), 是合班课
combined_subject = Subject.objects.create(
    school=school, name='校本课程', weekly_hours=4, is_combined_class=True, max_daily_limit=2
)

print("创建教师...")
teacher_zhang = Teacher.objects.create(school=school, name='张老师', travel_group=group_wed)
teacher_li = Teacher.objects.create(school=school, name='李老师')
teacher_wang = Teacher.objects.create(school=school, name='王老师', travel_group=group_wed)
teacher_zhao = Teacher.objects.create(school=school, name='赵老师', travel_group=group_fri)
teacher_chen = Teacher.objects.create(school=school, name='陈老师')
teacher_liu = Teacher.objects.create(school=school, name='刘老师')
teacher_sun = Teacher.objects.create(school=school, name='孙老师')

print("创建班级...")
class_1 = SchoolClass.objects.create(school=school, name='一(1)班', grade=1, homeroom_teacher=teacher_zhang)
class_2 = SchoolClass.objects.create(school=school, name='一(2)班', grade=1, homeroom_teacher=teacher_wang)
class_3 = SchoolClass.objects.create(school=school, name='一(3)班', grade=1, homeroom_teacher=teacher_chen)

print("创建教师资质 (自动分配基础)...")
TeacherQualification.objects.create(school=school, teacher=teacher_zhang, subject=chinese)
TeacherQualification.objects.create(school=school, teacher=teacher_chen, subject=chinese)

TeacherQualification.objects.create(school=school, teacher=teacher_li, subject=math)

TeacherQualification.objects.create(school=school, teacher=teacher_wang, subject=english)
TeacherQualification.objects.create(school=school, teacher=teacher_zhang, subject=english)

TeacherQualification.objects.create(school=school, teacher=teacher_zhao, subject=pe)

TeacherQualification.objects.create(school=school, teacher=teacher_liu, subject=music)

TeacherQualification.objects.create(school=school, teacher=teacher_sun, subject=art)

print("创建手动指定的授课分配...")
ClassSubjectTeacher.objects.create(
    school=school, school_class=class_3, subject=chinese, teacher=teacher_zhang, is_manual=True
)

print(f"\n测试数据创建完成! (学校: {school.name})")
print(f"- 送教分组: {TravelGroup.objects.filter(school=school).count()}")
print(f"- 场地: {Location.objects.filter(school=school).count()}")
print(f"- 课程: {Subject.objects.filter(school=school).count()}")
print(f"- 教师: {Teacher.objects.filter(school=school).count()}")
print(f"- 班级: {SchoolClass.objects.filter(school=school).count()}")
print(f"- 教师资质: {TeacherQualification.objects.filter(school=school).count()}")
print(f"- 手动授课分配: {ClassSubjectTeacher.objects.filter(school=school, is_manual=True).count()}")

print("\n资质情况:")
for q in TeacherQualification.objects.filter(school=school).select_related('teacher', 'subject').order_by('subject__name', 'teacher__name'):
    print(f"  {q.subject.name}: {q.teacher.name}")
