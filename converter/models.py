from django.db import models

class FileUpload(models.Model):
    file = models.FileField(upload_to='uploads/')
    converted_file = models.FileField(upload_to='converted/', null=True, blank=True)
    conversion_type = models.CharField(max_length=50)  # Example: 'docx_to_pdf', 'jpg_to_png'
    email = models.EmailField(null=True, blank=True)  # Optional email for notifications
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('COMPLETED', 'Completed')],
        default='PENDING'
    )
