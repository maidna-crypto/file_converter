from pathlib import Path
from pdf2docx import Converter
import subprocess
from celery import shared_task
from .models import FileUpload
from django.conf import settings
from django.urls import reverse
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)

@shared_task
def convert_file_task(file_upload_id, conversion_type=None):
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


def convert_docx_to_pdf(input_docx_path, output_pdf_path):
    try:
        # Get the directory for the output file
        output_dir = Path(output_pdf_path).parent

        # Run LibreOffice with the --outdir option
        subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pdf', input_docx_path, '--outdir', str(output_dir)],
            check=True
        )

        # Determine the original LibreOffice output file name
        original_pdf_path = output_dir / f"{Path(input_docx_path).stem}.pdf"

        # Rename the file to the desired output path if it exists
        if original_pdf_path.exists():
            original_pdf_path.rename(output_pdf_path)
        else:
            raise FileNotFoundError(f"Expected file not found: {original_pdf_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        raise

def redirect_to_download(request, file_name):
    download_url = reverse('download_file', kwargs={'file_name': file_name})
    return redirect(download_url)