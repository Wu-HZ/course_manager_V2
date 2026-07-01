from rest_framework import serializers
from .models import ScheduleResult, ScheduleEntry


class ScheduleEntrySerializer(serializers.ModelSerializer):
    school_class_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleEntry
        fields = [
            'id', 'school_class', 'school_class_name',
            'subject', 'subject_name',
            'teacher', 'teacher_name',
            'day', 'period', 'is_locked'
        ]

    def get_school_class_name(self, obj):
        return obj.school_class.name if obj.school_class else None

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_teacher_name(self, obj):
        # 校本课程时 teacher 为 None
        return obj.teacher.name if obj.teacher else None


class ScheduleResultSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()
    display_name = serializers.ReadOnlyField()
    school = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ScheduleResult
        fields = [
            'id', 'name', 'display_name', 'created_at', 'is_active',
            'is_favorite', 'solve_status', 'solve_time_ms', 'notes',
            'entry_count', 'combined_class_assignments', 'school'
        ]

    def get_entry_count(self, obj):
        annotated = getattr(obj, 'entry_count', None)
        return annotated if annotated is not None else obj.entries.count()


class ScheduleResultListSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()
    display_name = serializers.ReadOnlyField()
    school = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ScheduleResult
        fields = [
            'id', 'name', 'display_name', 'created_at', 'is_active',
            'is_favorite', 'solve_status', 'solve_time_ms', 'notes',
            'entry_count', 'combined_class_assignments', 'school'
        ]

    def get_entry_count(self, obj):
        annotated = getattr(obj, 'entry_count', None)
        return annotated if annotated is not None else obj.entries.count()


class ScheduleResultUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleResult
        fields = ['name', 'is_favorite']
        extra_kwargs = {
            'name': {
                'allow_blank': True,
                'required': False,
                'trim_whitespace': True,
            },
            'is_favorite': {
                'required': False,
            },
        }
