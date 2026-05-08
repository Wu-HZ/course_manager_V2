from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase, APIRequestFactory

from .data_io import SHEET_CONFIG, import_data
from .models import ScheduleLock, SchoolClass, Subject, Teacher


class ImportDataTests(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def build_workbook(self, sheet_rows):
        wb = Workbook()
        wb.remove(wb.active)

        for sheet_name, rows in sheet_rows.items():
            ws = wb.create_sheet(title=sheet_name)
            ws.append(SHEET_CONFIG[sheet_name]['headers'])
            for row in rows:
                ws.append(row)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def test_import_rejects_row_when_foreign_key_lookup_fails(self):
        school_class = SchoolClass.objects.create(name='一1班', grade=1)
        subject = Subject.objects.create(name='语文')
        schedule_lock_sheet = next(
            name for name, config in SHEET_CONFIG.items()
            if config['model'] is ScheduleLock
        )

        workbook_bytes = self.build_workbook({
            schedule_lock_sheet: [
                [school_class.name, subject.name, '不存在的教师', 1, 2],
            ]
        })
        upload = SimpleUploadedFile(
            'import.xlsx',
            workbook_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        request = self.factory.post('/api/data/import/', {'file': upload}, format='multipart')
        response = import_data(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ScheduleLock.objects.count(), 0)
        self.assertFalse(response.data['committed'])
        self.assertEqual(response.data['results'][schedule_lock_sheet]['created'], 0)
        self.assertEqual(response.data['results'][schedule_lock_sheet]['updated'], 0)
        self.assertEqual(response.data['error_count'], 1)

    def test_import_rolls_back_all_rows_when_any_error_occurs(self):
        school_class = SchoolClass.objects.create(name='二1班', grade=2)
        subject = Subject.objects.create(name='数学')
        teacher = Teacher.objects.create(name='张老师')
        schedule_lock_sheet = next(
            name for name, config in SHEET_CONFIG.items()
            if config['model'] is ScheduleLock
        )

        workbook_bytes = self.build_workbook({
            schedule_lock_sheet: [
                [school_class.name, subject.name, teacher.name, 1, 2],
                [school_class.name, subject.name, '不存在的教师', 1, 3],
            ]
        })
        upload = SimpleUploadedFile(
            'import.xlsx',
            workbook_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        request = self.factory.post('/api/data/import/', {'file': upload}, format='multipart')
        response = import_data(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['committed'])
        self.assertEqual(ScheduleLock.objects.count(), 0)
        self.assertEqual(response.data['results'][schedule_lock_sheet]['created'], 0)
        self.assertEqual(response.data['results'][schedule_lock_sheet]['updated'], 0)
        self.assertEqual(response.data['error_count'], 1)
