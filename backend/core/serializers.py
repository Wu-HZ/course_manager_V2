from rest_framework import serializers
from .models import (
    TravelGroup, Subject, CombinedClassGroup, Teacher,
    SchoolClass, Location, ClassSubjectTeacher,
    TeacherQualification, ScheduleLock, SchedulerSettings,
    TeacherBlockedTime, is_subject_qualification_managed
)


class TravelGroupSerializer(serializers.ModelSerializer):
    day_off_display = serializers.CharField(source='get_day_off_display', read_only=True)

    class Meta:
        model = TravelGroup
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    location_type_display = serializers.CharField(
        source='get_location_type_display', read_only=True
    )

    class Meta:
        model = Subject
        fields = '__all__'


class CombinedClassGroupSerializer(serializers.ModelSerializer):
    teacher_count = serializers.SerializerMethodField()

    class Meta:
        model = CombinedClassGroup
        fields = '__all__'

    def get_teacher_count(self, obj):
        return obj.teacher_set.count()


class TeacherSerializer(serializers.ModelSerializer):
    travel_group_name = serializers.CharField(
        source='travel_group.name', read_only=True, allow_null=True
    )
    combined_class_group_name = serializers.CharField(
        source='combined_class_group.name', read_only=True, allow_null=True
    )
    combined_class_day_display = serializers.CharField(
        source='get_combined_class_day_display', read_only=True, allow_null=True
    )
    homeroom_class_name = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = '__all__'

    def get_homeroom_class_name(self, obj):
        if hasattr(obj, 'homeroom_class') and obj.homeroom_class:
            return obj.homeroom_class.name
        return None


class SchoolClassSerializer(serializers.ModelSerializer):
    homeroom_teacher_name = serializers.CharField(
        source='homeroom_teacher.name', read_only=True, allow_null=True
    )

    class Meta:
        model = SchoolClass
        fields = '__all__'


class LocationSerializer(serializers.ModelSerializer):
    location_type_display = serializers.CharField(
        source='get_location_type_display', read_only=True
    )

    class Meta:
        model = Location
        fields = '__all__'


class ClassSubjectTeacherSerializer(serializers.ModelSerializer):
    school_class_name = serializers.CharField(
        source='school_class.name', read_only=True
    )
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = ClassSubjectTeacher
        fields = '__all__'


class TeacherQualificationSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    def validate_subject(self, subject):
        if not is_subject_qualification_managed(subject):
            raise serializers.ValidationError('班会和校本课程不通过教师资质管理。')
        return subject

    class Meta:
        model = TeacherQualification
        fields = ['id', 'teacher', 'teacher_name', 'subject', 'subject_name']


class ScheduleLockSerializer(serializers.ModelSerializer):
    school_class_name = serializers.CharField(source='school_class.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True, allow_null=True)
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = ScheduleLock
        fields = '__all__'


class SchedulerSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulerSettings
        fields = '__all__'


class TeacherBlockedTimeSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)
    day_display = serializers.CharField(source='get_day_display', read_only=True)
    period_type_display = serializers.CharField(source='get_period_type_display', read_only=True)

    class Meta:
        model = TeacherBlockedTime
        fields = '__all__'
