# apps/usuarios/admin.py

from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import Acesso, GroupsAcessos, ControleAcessos

# -------------------------
# Custom UserAdmin
# -------------------------
class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter  = ('is_staff', 'is_active', 'is_superuser', 'groups')
    fieldsets    = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'),    {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'),      {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'),  {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username','email','password1','password2','first_name','last_name'),
        }),
    )
    search_fields     = ('username','email','first_name','last_name')
    ordering          = ('id','username')
    filter_horizontal = ('groups','user_permissions')

# -------------------------
# Custom GroupAdmin
# -------------------------
class CustomGroupAdmin(BaseGroupAdmin):
    list_display   = ('id','name')
    search_fields  = ('name',)
    ordering       = ('id','name')

# Desregistrando e registrando User e Group
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)

# -------------------------
# AcessoAdmin
# -------------------------
@admin.register(Acesso)
class AcessoAdmin(admin.ModelAdmin):
    list_display   = ('id','nome','tipo','data_criacao','status')
    list_filter    = ('tipo','status')
    search_fields  = ('nome',)
    ordering       = ('tipo','nome')  # agrupa por tipo e ordena alfabeticamente

# -------------------------
# GroupsAcessosAdmin
# -------------------------
@admin.register(GroupsAcessos)
class GroupsAcessosAdmin(admin.ModelAdmin):
    list_display       = ('id','titulo','data_criacao','status')
    list_filter        = ('status',)
    search_fields      = ('titulo',)
    ordering           = ('titulo',)
    filter_horizontal  = ('acessos',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'acessos':
            kwargs['queryset'] = Acesso.objects.filter(status=True).order_by('tipo','nome')
            kwargs['widget']   = FilteredSelectMultiple('Acessos', is_stacked=False)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

# -------------------------
# ControleAcessosAdmin
# -------------------------
@admin.register(ControleAcessos)
class ControleAcessosAdmin(admin.ModelAdmin):
    list_display       = ('id','user','data_criacao','status')
    list_filter        = ('status',)
    search_fields      = ('user__username',)
    ordering           = ('user__username',)
    filter_horizontal  = ('acessos',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'acessos':
            kwargs['queryset'] = Acesso.objects.filter(status=True).order_by('tipo','nome')
            kwargs['widget']   = FilteredSelectMultiple('Acessos', is_stacked=False)
        return super().formfield_for_manytomany(db_field, request, **kwargs)
