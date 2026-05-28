from django.urls import path

from .views import (
    ApproveRecordView,
    BulkApproveView,
    EmissionRecordDetailView,
    EmissionRecordListView,
    IngestionListView,
    IngestionUploadView,
    RejectRecordView,
    StatsView,
)

urlpatterns = [
    # Upload a new file for processing
    path('upload/<str:source_type>/', IngestionUploadView.as_view(), name='ingestion-upload'),

    # List all ingestion batches for the current company
    path('ingestions/', IngestionListView.as_view(), name='ingestion-list'),

    # Bulk operations — must come BEFORE the <int:pk> pattern
    path('records/bulk-approve/', BulkApproveView.as_view(), name='record-bulk-approve'),

    # Record list
    path('records/', EmissionRecordListView.as_view(), name='record-list'),

    # Single record detail + edit
    path('records/<int:pk>/', EmissionRecordDetailView.as_view(), name='record-detail'),

    # Workflow actions
    path('records/<int:pk>/approve/', ApproveRecordView.as_view(), name='record-approve'),
    path('records/<int:pk>/reject/', RejectRecordView.as_view(), name='record-reject'),

    # Dashboard statistics
    path('stats/', StatsView.as_view(), name='stats'),
]
