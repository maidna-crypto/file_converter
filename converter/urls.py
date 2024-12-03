from django.urls import path
from .views import FileUploadView, FileDownloadView, upload_form, download_file, TaskStatusView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('upload/', upload_form, name='upload_form'),
    path('api/upload/', FileUploadView.as_view(), name='file-upload'),
    #path('download/<int:pk>/', FileDownloadView.as_view(), name='file-download'),
    path('download/<str:file_name>/', download_file, name='download_file'),
    path('api/task-status/', TaskStatusView.as_view(), name='task-status')

]  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
