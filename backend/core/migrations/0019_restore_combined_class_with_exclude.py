# Generated manually - restore CombinedClassGroup and add exclude field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_remove_combined_class_group'),
    ]

    operations = [
        # 1. 重建 CombinedClassGroup 模型
        migrations.CreateModel(
            name='CombinedClassGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='分组名称')),
            ],
            options={
                'verbose_name': '校本课程分组',
                'verbose_name_plural': '校本课程分组',
            },
        ),
        # 2. 恢复 Teacher.combined_class_group 字段
        migrations.AddField(
            model_name='teacher',
            name='combined_class_group',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='core.combinedclassgroup',
                verbose_name='校本课程分组'
            ),
        ),
        # 3. 添加 Teacher.exclude_from_combined 字段
        migrations.AddField(
            model_name='teacher',
            name='exclude_from_combined',
            field=models.BooleanField(
                default=False,
                verbose_name='不参与校本课程',
                help_text='勾选后该教师不会被分配到校本课程'
            ),
        ),
    ]
