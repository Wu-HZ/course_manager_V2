from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
import os

def serve_frontend_asset(request, path):
    """服务前端静态资源"""
    file_path = settings.FRONTEND_DIR / 'assets' / path
    if file_path.exists() and file_path.is_file():
        # 根据文件扩展名设置 Content-Type
        content_types = {
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject',
        }
        ext = file_path.suffix.lower()
        content_type = content_types.get(ext, 'application/octet-stream')
        return FileResponse(open(file_path, 'rb'), content_type=content_type)
    raise Http404()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/scheduler/', include('scheduler.urls')),
]

# 生产模式下服务前端 SPA
if not settings.DEBUG or os.environ.get('SERVE_FRONTEND') == 'true':
    urlpatterns += [
        # 服务前端静态资源
        re_path(r'^assets/(?P<path>.*)$', serve_frontend_asset),
        # 所有其他非 API 路由返回 index.html
        re_path(r'^(?!api/|admin/|assets/).*$', TemplateView.as_view(template_name='index.html')),
    ]
