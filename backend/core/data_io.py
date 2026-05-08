"""
数据导入导出功能
Excel格式，每个数据类型一个Sheet
"""
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from django.db import transaction
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import (
    TravelGroup, Subject, CombinedClassGroup, Teacher,
    SchoolClass, Location, ClassSubjectTeacher, TeacherQualification,
    ScheduleLock, TeacherBlockedTime, get_qualification_subject_queryset,
    is_subject_qualification_managed
)


# Sheet配置：名称 -> (模型, 字段列表, 表头)
SHEET_CONFIG = {
    '送教分组': {
        'model': TravelGroup,
        'fields': ['name', 'day_off'],
        'headers': ['分组名称', '禁排日(0周一~4周五)'],
    },
    '校本课程分组': {
        'model': CombinedClassGroup,
        'fields': ['name'],
        'headers': ['分组名称'],
    },
    '场地': {
        'model': Location,
        'fields': ['name', 'location_type', 'capacity'],
        'headers': ['场地名称', '类型(CLASSROOM/PLAYGROUND/LAB/HOME_EC)', '容量'],
    },
    '课程': {
        'model': Subject,
        'fields': ['name', 'weekly_hours', 'is_main_subject', 'max_teacher_classes', 'is_am_preferred', 'allow_consecutive',
                   'max_daily_limit', 'location_type', 'is_combined_class',
                   'applicable_grades', 'avoid_first_period'],
        'headers': ['课程名称', '周课时', '主课(TRUE/FALSE)', '单师班数(1-5)', '优先上午(TRUE/FALSE)', '允许连堂(TRUE/FALSE)',
                    '单日上限', '场地类型', '是否合班课(TRUE/FALSE)',
                    '适用年级(如1,2,3)', '避免第一节(TRUE/FALSE)'],
    },
    '教师': {
        'model': Teacher,
        'fields': ['name', 'travel_group__name', 'combined_class_group__name', 'exclude_from_combined', 'min_weekly_hours', 'max_weekly_hours'],
        'headers': ['姓名', '送教分组名称', '校本课程分组名称', '不参与校本课程(TRUE/FALSE)', '周课时下限(留空不限)', '周课时上限(留空不限)'],
        'fk_fields': {
            'travel_group__name': ('travel_group', TravelGroup, 'name'),
            'combined_class_group__name': ('combined_class_group', CombinedClassGroup, 'name'),
        },
    },
    '班级': {
        'model': SchoolClass,
        'fields': ['name', 'grade', 'homeroom_teacher__name'],
        'headers': ['班级名称', '年级', '班主任姓名'],
        'fk_fields': {
            'homeroom_teacher__name': ('homeroom_teacher', Teacher, 'name'),
        },
    },
    '教师资质': {
        'model': TeacherQualification,
        'fields': ['teacher__name', 'subject__name'],
        'headers': ['教师姓名', '课程名称'],
        'fk_fields': {
            'teacher__name': ('teacher', Teacher, 'name'),
            'subject__name': ('subject', Subject, 'name'),
        },
    },
    '授课分配': {
        'model': ClassSubjectTeacher,
        'fields': ['school_class__name', 'subject__name', 'teacher__name', 'is_manual'],
        'headers': ['班级名称', '课程名称', '教师姓名', '手动指定(TRUE/FALSE)'],
        'fk_fields': {
            'school_class__name': ('school_class', SchoolClass, 'name'),
            'subject__name': ('subject', Subject, 'name'),
            'teacher__name': ('teacher', Teacher, 'name'),
        },
    },
    '课表锁定': {
        'model': ScheduleLock,
        'fields': ['school_class__name', 'subject__name', 'teacher__name', 'day', 'period'],
        'headers': ['班级名称', '课程名称', '教师姓名(可空)', '星期(0-4)', '节次(0-5)'],
        'fk_fields': {
            'school_class__name': ('school_class', SchoolClass, 'name'),
            'subject__name': ('subject', Subject, 'name'),
            'teacher__name': ('teacher', Teacher, 'name'),
        },
    },
    '教师禁排日': {
        'model': TeacherBlockedTime,
        'fields': ['teacher__name', 'day', 'period_type'],
        'headers': ['教师姓名', '星期(0-4)', '时段(am/pm/all)'],
        'fk_fields': {
            'teacher__name': ('teacher', Teacher, 'name'),
        },
    },
}

# 导出顺序（按依赖关系排列）
EXPORT_ORDER = ['送教分组', '校本课程分组', '场地', '课程', '教师', '教师禁排日', '班级', '教师资质', '授课分配', '课表锁定']


def style_header(ws):
    """设置表头样式"""
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')


def build_import_response(results, errors, committed):
    """统一构造导入响应，便于前端区分是否已落库。"""
    response_results = results
    status_code = 200
    payload = {
        'results': response_results,
        'errors': errors[:20],
        'error_count': len(errors),
        'committed': committed,
    }

    if not committed:
        payload['error'] = '导入失败，已回滚，本次未写入任何数据。'
        payload['results'] = {
            sheet_name: {'created': 0, 'updated': 0}
            for sheet_name in results
        }
        status_code = 400

    return Response(payload, status=status_code)


@api_view(['GET'])
def export_data(request):
    """导出所有数据到Excel"""
    wb = Workbook()
    wb.remove(wb.active)  # 移除默认sheet

    for sheet_name in EXPORT_ORDER:
        config = SHEET_CONFIG[sheet_name]
        model = config['model']
        fields = config['fields']
        headers = config['headers']

        ws = wb.create_sheet(title=sheet_name)
        ws.append(headers)
        style_header(ws)

        # 获取数据
        queryset = model.objects.all()
        if model == TeacherQualification:
            queryset = queryset.filter(subject__in=get_qualification_subject_queryset())

        for obj in queryset:
            row = []
            for field in fields:
                if '__' in field:
                    # 外键字段
                    parts = field.split('__')
                    value = obj
                    for part in parts:
                        value = getattr(value, part, None) if value else None
                else:
                    value = getattr(obj, field, None)

                # 布尔值转换
                if isinstance(value, bool):
                    value = 'TRUE' if value else 'FALSE'
                row.append(value)
            ws.append(row)

        # 自动调整列宽
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

    # 保存到内存
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="course_manager_data.xlsx"'
    return response


@api_view(['POST'])
def import_data(request):
    """从Excel导入数据"""
    file = request.FILES.get('file')
    if not file:
        return Response({'error': '请上传文件'}, status=400)

    try:
        wb = load_workbook(file)
    except Exception as e:
        return Response({'error': f'无法读取Excel文件: {str(e)}'}, status=400)

    results = {}
    errors = []

    with transaction.atomic():
        # 按顺序导入（先导入被依赖的数据）
        for sheet_name in EXPORT_ORDER:
            if sheet_name not in wb.sheetnames:
                continue

            config = SHEET_CONFIG[sheet_name]
            model = config['model']
            fields = config['fields']
            fk_fields = config.get('fk_fields', {})

            ws = wb[sheet_name]
            rows = list(ws.iter_rows(min_row=2, values_only=True))  # 跳过表头

            created = 0
            updated = 0

            for row_idx, row in enumerate(rows, start=2):
                if not any(row):  # 跳过空行
                    continue

                try:
                    data = {}
                    lookup_field = None
                    lookup_value = None
                    row_has_error = False

                    for i, field in enumerate(fields):
                        value = row[i] if i < len(row) else None

                        # 处理布尔值
                        if isinstance(value, str) and value.upper() in ('TRUE', 'FALSE'):
                            value = value.upper() == 'TRUE'

                        if '__' in field:
                            # 外键字段
                            fk_info = fk_fields.get(field)
                            if fk_info and value:
                                fk_field_name, fk_model, fk_lookup = fk_info
                                try:
                                    fk_obj = fk_model.objects.get(**{fk_lookup: value})
                                    data[fk_field_name] = fk_obj
                                except fk_model.DoesNotExist:
                                    errors.append(f'{sheet_name} 第{row_idx}行: 找不到 {value}')
                                    row_has_error = True
                                    break
                            elif fk_info:
                                fk_field_name = fk_info[0]
                                data[fk_field_name] = None
                        else:
                            # 空值使用模型字段默认值
                            if value is None:
                                model_field = model._meta.get_field(field)
                                if model_field.has_default():
                                    value = model_field.default
                            data[field] = value
                            # 用第一个非外键字段作为查找字段
                            if lookup_field is None and value:
                                lookup_field = field
                                lookup_value = value

                    if row_has_error:
                        continue

                    if not data or not lookup_field:
                        continue

                    # 根据名称查找或创建
                    if model == TeacherQualification:
                        if not is_subject_qualification_managed(data.get('subject')):
                            continue
                        # 资质表用组合键查找
                        obj, is_created = model.objects.get_or_create(
                            teacher=data.get('teacher'),
                            subject=data.get('subject'),
                            defaults=data
                        )
                    elif model == ClassSubjectTeacher:
                        # 授课分配用组合键查找
                        obj, is_created = model.objects.get_or_create(
                            school_class=data.get('school_class'),
                            subject=data.get('subject'),
                            defaults=data
                        )
                        if not is_created:
                            for k, v in data.items():
                                setattr(obj, k, v)
                            obj.save()
                    elif model == ScheduleLock:
                        # 课表锁定用组合键查找
                        obj, is_created = model.objects.update_or_create(
                            school_class=data.get('school_class'),
                            day=data.get('day'),
                            period=data.get('period'),
                            defaults=data
                        )
                    elif model == TeacherBlockedTime:
                        # 教师禁排日用组合键查找
                        obj, is_created = model.objects.update_or_create(
                            teacher=data.get('teacher'),
                            day=data.get('day'),
                            period_type=data.get('period_type'),
                            defaults=data
                        )
                    else:
                        # 其他表用name字段查找
                        obj, is_created = model.objects.update_or_create(
                            **{lookup_field: lookup_value},
                            defaults=data
                        )

                    if is_created:
                        created += 1
                    else:
                        updated += 1

                except Exception as e:
                    errors.append(f'{sheet_name} 第{row_idx}行: {str(e)}')

            results[sheet_name] = {'created': created, 'updated': updated}

        if errors:
            transaction.set_rollback(True)
            return build_import_response(results, errors, committed=False)

    return build_import_response(results, errors, committed=True)
