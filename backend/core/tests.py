from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase, APIRequestFactory

from .data_io import SHEET_CONFIG, import_data
from .models import ScheduleLock, SchoolClass, Subject


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

    def test_import_skips_row_when_foreign_key_lookup_fails(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ScheduleLock.objects.count(), 0)
        self.assertEqual(response.data['results'][schedule_lock_sheet]['created'], 0)
        self.assertEqual(response.data['results'][schedule_lock_sheet]['updated'], 0)
        self.assertEqual(response.data['error_count'], 1)
