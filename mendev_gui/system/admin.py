from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.forms import ModelForm

from .models import SysSetting, SysProfile, SysMenu


class SysSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'parent', 'value']
    list_filter = ['parent']
    search_fields = ['key', 'value']
    save_as = True


class SysMenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'sequence', 'url']
    list_filter = ['parent']


class AlwaysChangedModelForm(ModelForm):
    def has_changed(self):
        """ Should return True if data differs from initial.
            By always returning true even unchanged inlines will get   validated and saved."""
        return True


class ProfileInline(admin.TabularInline):
    model = SysProfile
    can_delete = False
    form = AlwaysChangedModelForm


class MyUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name')
    inlines = [ProfileInline]

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.add_fieldsets

        if request.user.is_superuser:
            if request.user.pk == obj.pk:
                perm_fields = ('groups', 'user_permissions')
            else:
                perm_fields = ('is_active', 'is_staff', 'is_superuser',
                               'groups', 'user_permissions')
        else:
            perm_fields = ('is_active', 'is_staff', 'groups')

        return [(None, {'fields': ('username', 'password')}),
                (('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
                (('Permissions'), {'fields': perm_fields}),
                (('Important dates'), {'fields': ('last_login', 'date_joined')})]

    def has_delete_permission(self, request, obj=None):

        if obj is None:
            return True
        elif obj.pk == request.user.pk:
            return False
        elif obj.is_superuser and not request.user.is_superuser:
            return False
        else:
            return True

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        elif obj.is_superuser and not request.user.is_superuser:
            return False
        else:
            return True


user = get_user_model()
admin.site.unregister(user)
admin.site.register(user, MyUserAdmin)

admin.site.register(SysSetting, SysSettingAdmin)
admin.site.register(SysMenu, SysMenuAdmin)
