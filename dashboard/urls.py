from django.urls import path
from .views_api import DashboardMetricsView, DashboardMainView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardMainView.as_view(), name='dashboard-main'),
    path('metricas/', DashboardMetricsView.as_view(), name='dashboard-metrics'),
]
