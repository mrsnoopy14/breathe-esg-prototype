from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Extends the built-in UserAdmin to expose company and role fields."""

    # Columns shown in the changelist
    list_display = ('username', 'email', 'company', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'company', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'company__name')

    # Add company and role to the edit form via an extra fieldset
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ESG Platform', {
            'fields': ('company', 'role'),
        }),
    )

    # Also show them in the "add user" form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('ESG Platform', {
            'fields': ('company', 'role'),
        }),
    )
