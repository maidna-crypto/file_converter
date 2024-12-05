from pathlib import Path
import uuid
from pdf2docx import Converter
import subprocess
from celery import shared_task
from .models import FileUpload
from django.conf import settings
from django.urls import reverse
from django.shortcuts import redirect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

@shared_task
def convert_file_task_api(file_upload_id, conversion_type=None):
    """
    Task to process file conversion (PDF to DOCX, DOCX to PDF, etc.).

    Args:
        file_upload_id: ID of the FileUpload instance.
        conversion_type: Type of conversion (e.g., 'pdf_to_docx', 'docx_to_pdf').
    """
    try:
        file_upload = FileUpload.objects.get(id=file_upload_id)
        file_upload.status = 'PROCESSING'
        file_upload.save()

        input_file = file_upload.file.path
        input_path = Path(input_file)

        # Define the output directory and ensure it exists
        output_dir = Path(settings.MEDIA_ROOT) / "converted"
        output_dir.mkdir(parents=True, exist_ok=True)
        print("output_dir", output_dir)

        # Define the output file based on conversion type
        output_file = output_dir / f"converted_{input_path.stem}"

        if conversion_type == 'pdf_to_docx':
            output_file = output_file.with_suffix('.docx')
            convert_pdf_to_docx(input_file, output_file)
        elif conversion_type == 'docx_to_pdf':
            output_file = output_file.with_suffix('.pdf')
            convert_docx_to_pdf(input_file, output_file)
        else:
            logger.info(f"No specific conversion type provided. Default mock conversion used.")
            # If no valid conversion type is specified, just copy the file
            output_file = output_file.with_suffix(input_path.suffix)
            with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                f_out.write(f_in.read())

        # Mark as completed and save the converted file path
        relative_output_path = str(output_file).replace(str(Path(settings.MEDIA_ROOT)) + '/', '')
        file_upload.converted_file.name = relative_output_path
        file_upload.status = 'COMPLETED'
        file_upload.save()

        return Path(relative_output_path).name  # Return just the file name for download

    except FileUpload.DoesNotExist:
        logger.error(f"FileUpload with ID {file_upload_id} does not exist.")
    except Exception as e:
        logger.error(f"Error during file conversion: {e}")
        if 'file_upload' in locals():
            file_upload.status = 'FAILED'
            file_upload.save()
        raise e


def convert_pdf_to_docx(input_pdf_path, output_docx_path):
    """
    Converts PDF to DOCX using the pdf2docx library.
    """
    cv = Converter(input_pdf_path)
    cv.convert(output_docx_path, start=0, end=None)
    cv.close()

import glob

def convert_docx_to_pdf(input_docx_path, output_pdf_path):
    try:
        output_dir = Path(output_pdf_path).parent
        result = subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pdf', input_docx_path, '--outdir', output_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            logging.error(f"Conversion failed with error: {result.stderr.decode()}")
            return False
        else:
            logging.info(f"Conversion successful: {result.stdout.decode()}")

        # Locate the actual output file
        possible_files = list(output_dir.glob(f"{Path(input_docx_path).stem}*.pdf"))
        if not possible_files:
            raise FileNotFoundError(f"No PDF file found in {output_dir} matching {Path(input_docx_path).stem}")
        
        # Rename the first match to the expected output path
        generated_pdf_path = possible_files[0]
        generated_pdf_path.rename(output_pdf_path)

    except subprocess.CalledProcessError as e:
        logging.error(f"Error during conversion: {e}")
        raise


def redirect_to_download(request, file_name):
    download_url = reverse('download_file', kwargs={'file_name': file_name})
    return redirect(download_url)


def generate_unique_filename(base_name, suffix):
    unique_id = uuid.uuid4().hex[:8]
    return f"{base_name}_{unique_id}{suffix}"



@shared_task
def convert_file_task(file_upload_id, conversion_type=None):
    print(f"Starting conversion task for file upload {file_upload_id}")
    channel_layer = get_channel_layer()
    
    try:
        file_upload = FileUpload.objects.get(id=file_upload_id)
        file_upload.status = 'PROCESSING'
        file_upload.save()

        async_to_sync(channel_layer.group_send)(
            "file_upload", 
            {
                "type": "task_update",
                "task_id": str(file_upload_id),
                "status": "PROCESSING"
            }
        )
        input_file = file_upload.file.path
        input_path = Path(input_file)

        # Define the output directory and ensure it exists
        output_dir = Path(settings.MEDIA_ROOT) / "converted"
        output_dir.mkdir(parents=True, exist_ok=True)
        print("output_dir", output_dir)

        output_file = output_dir / generate_unique_filename(input_path.stem, '.pdf')


        if conversion_type == 'pdf_to_docx':
            output_file = output_file.with_suffix('.docx')
            convert_pdf_to_docx(input_file, output_file)
        elif conversion_type == 'docx_to_pdf':
            output_file = output_file.with_suffix('.pdf')
            convert_docx_to_pdf(input_file, output_file)
        else:
            logger.info(f"No specific conversion type provided. Default mock conversion used.")
            output_file = output_file.with_suffix(input_path.suffix)
            with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
                f_out.write(f_in.read())

        relative_output_path = str(output_file).replace(str(Path(settings.MEDIA_ROOT)) + '/', '')
        file_upload.converted_file.name = relative_output_path
        file_upload.status = 'COMPLETED'
        file_upload.save()

        async_to_sync(channel_layer.group_send)(
            "file_upload", 
            {
                "type": "task_update",
                "task_id": str(file_upload_id),
                "status": "COMPLETED",
                "file_name": Path(relative_output_path).name
            }
        )
        print("Conversion completed successfully")
        return Path(relative_output_path).name
    
    except Exception as e:
        # Send error update
        async_to_sync(channel_layer.group_send)(
            "file_upload", 
            {
                "type": "task_update",
                "task_id": str(file_upload_id),
                "status": "FAILED",
                "message": str(e)
            }
        )
        raise