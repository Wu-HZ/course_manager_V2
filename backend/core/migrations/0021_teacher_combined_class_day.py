# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_alter_schedulersettings_h9_consecutive_forbidden_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='combined_class_day',
            field=models.IntegerField(
                blank=True,
                choices=[(1, '周二'), (3, '周四')],
                help_text='手动指定该教师上校本课程的日期，留空则自动分配',
                null=True,
                verbose_name='校本课程日期'
            ),
        ),
    ]
