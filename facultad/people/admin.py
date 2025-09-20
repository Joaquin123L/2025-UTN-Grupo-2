from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "rol", "legajo", "is_active", "is_staff")
    list_filter  = ("rol", "is_active", "is_staff", "is_superuser")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Rol y datos UTN", {"fields": ("rol", "legajo")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Rol y datos UTN", {"fields": ("rol", "legajo")}),
    )