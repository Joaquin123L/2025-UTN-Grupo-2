from django.contrib import admin
from .models import Department
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "created_at")
    search_fields = ("nombre",)

# Register your models here.
