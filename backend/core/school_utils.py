"""跨模块使用的学校相关工具。"""
from __future__ import annotations

from core.models import School


def get_request_school(request):
    """从请求中获取当前学校。

    优先级：header ``X-School-ID`` > query param ``school_id`` > 第一所学校。
    不存在任何学校时返回 None。
    """
    school_id = request.headers.get('X-School-ID') or request.query_params.get('school_id')
    if school_id:
        try:
            return School.objects.get(pk=int(school_id))
        except (ValueError, School.DoesNotExist):
            pass
    return School.objects.first()
