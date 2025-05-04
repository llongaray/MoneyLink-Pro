from django.contrib import admin
from django.utils.html import format_html
from .models import *
from django.utils import timezone
import calendar
from datetime import timedelta

class DataAgendamentoFilter(admin.SimpleListFilter):
    title = 'Data do Agendamento'
    parameter_name = 'dia_agendado_range'

    def lookups(self, request, model_admin):
        return (
            ('hoje', 'Hoje'),
            ('ontem', 'Ontem'),
            ('semana', 'Esta Semana'),
            ('mes', 'Este Mês'),
            ('mes_anterior', 'Mês Anterior'),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'hoje':
            return queryset.filter(dia_agendado__date=today)
        elif self.value() == 'ontem':
            yesterday = today - timedelta(days=1)
            return queryset.filter(dia_agendado__date=yesterday)
        elif self.value() == 'semana':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            return queryset.filter(dia_agendado__date__range=(start_week, end_week))
        elif self.value() == 'mes':
            start_month = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_month = today.replace(day=last_day)
            return queryset.filter(dia_agendado__date__range=(start_month, end_month))
        elif self.value() == 'mes_anterior':
            if today.month == 1:
                previous_month = 12
                year = today.year - 1
            else:
                previous_month = today.month - 1
                year = today.year
            start_previous = today.replace(year=year, month=previous_month, day=1)
            last_day_previous = calendar.monthrange(year, previous_month)[1]
            end_previous = today.replace(year=year, month=previous_month, day=last_day_previous)
            return queryset.filter(dia_agendado__date__range=(start_previous, end_previous))
        return queryset

class DataPresencaFilter(admin.SimpleListFilter):
    title = 'Data da Presença'
    parameter_name = 'data_presenca_range'

    def lookups(self, request, model_admin):
        return (
            ('hoje', 'Hoje'),
            ('ontem', 'Ontem'),
            ('semana', 'Esta Semana'),
            ('mes', 'Este Mês'),
            ('mes_anterior', 'Mês Anterior'),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'hoje':
            return queryset.filter(data_presenca__date=today)
        elif self.value() == 'ontem':
            yesterday = today - timedelta(days=1)
            return queryset.filter(data_presenca__date=yesterday)
        elif self.value() == 'semana':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            return queryset.filter(data_presenca__date__range=(start_week, end_week))
        elif self.value() == 'mes':
            start_month = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_month = today.replace(day=last_day)
            return queryset.filter(data_presenca__date__range=(start_month, end_month))
        elif self.value() == 'mes_anterior':
            if today.month == 1:
                previous_month = 12
                year = today.year - 1
            else:
                previous_month = today.month - 1
                year = today.year
            start_previous = today.replace(year=year, month=previous_month, day=1)
            last_day_previous = calendar.monthrange(year, previous_month)[1]
            end_previous = today.replace(year=year, month=previous_month, day=last_day_previous)
            return queryset.filter(data_presenca__date__range=(start_previous, end_previous))
        return queryset

@admin.register(ClienteAgendamento)
class ClienteAgendamentoAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf', 'numero', 'flg_whatsapp', 'status')
    list_filter = ('status', 'flg_whatsapp')
    search_fields = ('nome_completo', 'cpf', 'numero')
    list_editable = ('status',)

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'get_cliente_nome', 'get_cliente_cpf', 'dia_agendado', 
        'loja', 'get_atendente_username', 'tabulacao_agendamento',
        'data_criacao'
    )
    list_filter = (
        DataAgendamentoFilter,
        'loja',
        'atendente_agendou',
    )
    search_fields = (
        'cliente_agendamento__nome_completo', 
        'cliente_agendamento__cpf',
        'loja__nome',
        'atendente_agendou__username',
        'atendente_agendou__first_name',
        'atendente_agendou__last_name'
    )
    date_hierarchy = 'dia_agendado'
    autocomplete_fields = ('cliente_agendamento', 'loja', 'atendente_agendou')
    ordering = ('-dia_agendado',)
    
    fieldsets = (
        ('Cliente e Agendamento', {
            'fields': ('cliente_agendamento', 'dia_agendado', 'loja', 'atendente_agendou')
        }),
        ('Detalhes', {
            'fields': ('tabulacao_agendamento', 'data_criacao')
        }),
    )
    readonly_fields = ('data_criacao',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('cliente_agendamento', 'loja', 'atendente_agendou')

    @admin.display(description='Cliente', ordering='cliente_agendamento__nome_completo')
    def get_cliente_nome(self, obj):
        return obj.cliente_agendamento.nome_completo if obj.cliente_agendamento else '-'

    @admin.display(description='CPF Cliente', ordering='cliente_agendamento__cpf')
    def get_cliente_cpf(self, obj):
        return obj.cliente_agendamento.cpf if obj.cliente_agendamento else '-'

    @admin.display(description='Atendente', ordering='atendente_agendou__username')
    def get_atendente_username(self, obj):
        return obj.atendente_agendou.username if obj.atendente_agendou else '-'

@admin.register(PresencaLoja)
class PresencaLojaAdmin(admin.ModelAdmin):
    list_display = (
        'get_cliente_info', 'get_agendamento_info', 'loja_comp', 'vendedor', 
        'tabulacao_venda', 'status_pagamento', 'valor_tac', 
        'cliente_rua', 'data_presenca'
    )
    list_filter = (
        'tabulacao_venda', 
        'status_pagamento', 
        'cliente_rua',
        'loja_comp',
        'vendedor',
        DataPresencaFilter,
        'subsidio',
        'acao',
        'associacao',
        'aumento'
    )
    search_fields = (
        'agendamento__cliente_agendamento__nome_completo', 
        'agendamento__cliente_agendamento__cpf',
        'cliente_agendamento__nome_completo',
        'cliente_agendamento__cpf',
        'vendedor__username',
        'tipo_negociacao',
        'banco'
    )
    autocomplete_fields = ('agendamento', 'cliente_agendamento', 'loja_comp', 'vendedor')
    ordering = ('-data_presenca',)
    
    fieldsets = (
        ('Associação', {
            'fields': ('agendamento', 'cliente_agendamento', 'cliente_rua', 'loja_comp')
        }),
        ('Atendimento', {
            'fields': ('vendedor', 'tabulacao_venda', 'data_presenca')
        }),
        ('Detalhes da Negociação (se aplicável)', {
            'classes': ('collapse',),
            'fields': ('tipo_negociacao', 'banco', 'subsidio', 'valor_tac', 'acao', 'associacao', 'aumento')
        }),
        ('Pagamento TAC', {
            'fields': ('status_pagamento', 'data_pagamento')
        }),
    )
    readonly_fields = ('data_presenca', 'data_pagamento')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'agendamento__cliente_agendamento', 
            'cliente_agendamento', 
            'loja_comp',
            'vendedor'
        )

    @admin.display(description='Cliente')
    def get_cliente_info(self, obj):
        if obj.agendamento and obj.agendamento.cliente_agendamento:
            return obj.agendamento.cliente_agendamento
        elif obj.cliente_agendamento:
            return obj.cliente_agendamento
        return '-'

    @admin.display(description='Agendamento ID')
    def get_agendamento_info(self, obj):
        return obj.agendamento.id if obj.agendamento else 'N/A (Cliente Rua)'
