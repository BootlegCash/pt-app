from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("", views.my_files, name="my_files"),
    path("excel/upload/", views.upload_excel, name="upload_excel"),
    path("excel/<uuid:job_uuid>/sheet/", views.select_sheet, name="select_sheet"),
    path("excel/<uuid:job_uuid>/mapping/", views.mapping, name="mapping"),
    path("excel/<uuid:job_uuid>/review/", views.review_parsed, name="review_parsed"),
    path("excel/<uuid:job_uuid>/", views.job_detail, name="job_detail"),
    path("excel/<uuid:job_uuid>/download/", views.download_import_file, name="download_import_file"),
    path("pdf/upload/", views.upload_pdf, name="upload_pdf"),
    path("pdf/<uuid:file_uuid>/", views.download_pdf, name="download_pdf"),
    path("client/<uuid:client_uuid>/", views.client_files, name="client_files"),
    path("pdf/<uuid:file_uuid>/edit/", views.pdf_edit, name="pdf_edit"),
    path("approvals/", views.approvals, name="approvals"),
    path("approvals/<uuid:job_uuid>/approve/", views.approve_job, name="approve_job"),
    path("approvals/<uuid:job_uuid>/reject/", views.reject_job, name="reject_job"),
]
