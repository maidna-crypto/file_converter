import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status

from django.shortcuts import redirect
from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from celery.result import AsyncResult
from .models import FileUpload
from .serializers import FileUploadSerializer
from .tasks import convert_file_task


def upload_form(request):
    return render(request, 'converter/upload_form.html')


# def download_file(request, file_name):
#     file_path = os.path.join(settings.MEDIA_ROOT, 'converted', file_name)  # Adjust this path as per your file storage
#     if os.path.exists(file_path):
#         return FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
#     return Response({'message': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

def download_file(request, file_name):
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, 'converted', file_name)
        print(f"File path: {file_path}")

        if not os.path.exists(file_path):
            raise Http404("File not found")

        # Return the file with the correct content type
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response

    except Exception as e:
        # Handle any errors and return a custom error message
        raise Http404(f"Error: {str(e)}")


@method_decorator(csrf_exempt, name='dispatch')
class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            file_obj = serializer.save()
            # Trigger Celery task for conversion
            task = convert_file_task.delay(file_obj.id, serializer.validated_data['conversion_type'])
            return Response({'message': 'File uploaded successfully and queued for conversion',
                              'task_id': task.id,}, status=status.HTTP_202_ACCEPTED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, *args, **kwargs):
        task_id = request.query_params.get('task_id')

        if not task_id:
            return Response({'message': 'Task ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        task_result = AsyncResult(task_id)


        if task_result.state == 'SUCCESS':

            file_name = task_result.result 
            converted_file_path = os.path.join(settings.MEDIA_ROOT, 'converted', file_name)
            if os.path.exists(converted_file_path):
                download_url = reverse('download_file', kwargs={'file_name': file_name})
                return redirect(download_url)
            else:
                return Response({'message': 'File not found after conversion.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        elif task_result.state == 'PENDING':
            return Response({'message': 'Conversion in progress.'}, status=status.HTTP_202_ACCEPTED)
        
        else:
            return Response({'message': 'Conversion failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class FileDownloadView(APIView):
    def get(self, request, pk):
        file_upload = get_object_or_404(FileUpload, pk=pk, status='COMPLETED')
        return FileResponse(open(file_upload.converted_file.path, 'rb'), as_attachment=True)


class TaskStatusView(APIView):
    def get(self, request):
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'message': 'Task ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        task_result = AsyncResult(task_id)

        if task_result.state == 'SUCCESS':
            return Response({
                'status': 'COMPLETED',
                'file_name': task_result.result  # This should be the file name for download
            })
        elif task_result.state == 'PENDING':
            return Response({'status': 'PENDING'}, status=status.HTTP_202_ACCEPTED)
        else:
            return Response({'status': 'FAILED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)