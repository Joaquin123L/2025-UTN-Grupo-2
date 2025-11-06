from django.contrib import admin
from .models import Department, CensoredWord
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "created_at")
    search_fields = ("nombre",)

@admin.register(CensoredWord)
class CensoredWordAdmin(admin.ModelAdmin):
    list_display = ("palabra",)
    search_fields = ("palabra",)
