"""Data migration: reassign TravelGroup IDs so id order = weekday order.

Before: id=5 Monday, 8 Tuesday, 1 Wednesday, 9 Thursday, 4 Friday
After:  id=1 Monday, 2 Tuesday, 3 Wednesday, 4 Thursday, 5 Friday

Teachers with travel_group FK are kept in sync via SET_NULL + restore.
"""

from django.db import migrations


def _reorder(apps, schema_editor):
    TravelGroup = apps.get_model('core', 'TravelGroup')
    Teacher = apps.get_model('core', 'Teacher')

    groups = list(TravelGroup.objects.all())
    if not groups:
        return

    # day_off 0=周一 → new_id=1,  1=周二→2,  2=周三→3,  3=周四→4,  4=周五→5
    old_to_new = {}
    new_to_data = {}
    for tg in groups:
        new_pk = tg.day_off + 1
        old_to_new[tg.pk] = new_pk
        new_to_data[new_pk] = {'name': tg.name, 'day_off': tg.day_off}

    # 1) 暂存当前 teacher FK 映射
    teachers_with_group = list(
        Teacher.objects.exclude(travel_group=None).values_list('id', 'travel_group_id')
    )
    old_id_to_teacher_ids = {}
    for teacher_id, group_id in teachers_with_group:
        old_id_to_teacher_ids.setdefault(group_id, []).append(teacher_id)

    # 2) 清空所有送教分组外键 (SET_NULL 行为模拟，在迁移中需要显式操作)
    for teacher_ids in old_id_to_teacher_ids.values():
        Teacher.objects.filter(id__in=teacher_ids).update(travel_group=None)

    # 3) 删除旧分组
    TravelGroup.objects.all().delete()

    # 4) 按新 ID 重建
    for new_pk in sorted(new_to_data.keys()):
        d = new_to_data[new_pk]
        TravelGroup.objects.create(pk=new_pk, name=d['name'], day_off=d['day_off'])

    # 5) 恢复教师外键到新 ID
    for old_pk, new_pk in old_to_new.items():
        teacher_ids = old_id_to_teacher_ids.get(old_pk, [])
        if teacher_ids:
            Teacher.objects.filter(id__in=teacher_ids).update(travel_group_id=new_pk)


def _reverse(apps, schema_editor):
    """Reverse is best-effort — restores groups but IDs may not match original."""
    TravelGroup = apps.get_model('core', 'TravelGroup')
    Teacher = apps.get_model('core', 'Teacher')

    groups = list(TravelGroup.objects.all())
    old_to_new = {}
    for tg in groups:
        old_to_new[tg.pk] = tg.day_off + 1  # same transform, idempotent in forward case

    teachers_with_group = list(
        Teacher.objects.exclude(travel_group=None).values_list('id', 'travel_group_id')
    )
    old_id_to_teacher_ids = {}
    for teacher_id, group_id in teachers_with_group:
        old_id_to_teacher_ids.setdefault(group_id, []).append(teacher_id)

    for teacher_ids in old_id_to_teacher_ids.values():
        Teacher.objects.filter(id__in=teacher_ids).update(travel_group=None)
    TravelGroup.objects.all().delete()

    for new_pk in sorted(old_to_new.keys()):
        d = {'name': groups[new_pk - 1].name if new_pk <= len(groups) else '分组', 'day_off': new_pk - 1}
        TravelGroup.objects.create(pk=new_pk, name=d['name'], day_off=d['day_off'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0027_schedulersettings_h15_teacher_max_main_subjects_and_more'),
    ]

    operations = [
        migrations.RunPython(_reorder, _reverse),
    ]
