from django.contrib import admin
from .models import *
import os
from django.utils.safestring import mark_safe


# Filtro personalizado para funcionários MEI
class FuncionarioMEIFilter(admin.SimpleListFilter):
    title = 'Funcionários MEI Ativos'
    parameter_name = 'mei_ativo'

    def lookups(self, request, model_admin):
        return (
            ('sim', 'Apenas MEI Ativos'),
            ('nao', 'Não MEI ou Inativos'),
            ('todos_mei', 'Todos os MEI'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'sim':
            return queryset.filter(tipo_contrato='MEI', status=True)
        elif self.value() == 'nao':
            return queryset.exclude(tipo_contrato='MEI', status=True)
        elif self.value() == 'todos_mei':
            return queryset.filter(tipo_contrato='MEI')
        return queryset

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'cnpj', 'endereco', 'status')
    search_fields = ('nome', 'cnpj')
    list_filter = ('status',)
    list_editable = ('status',)
    ordering = ('nome',)

@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'empresa', 'franquia', 'filial', 'status')
    list_filter = ('empresa', 'franquia', 'filial', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status', 'franquia', 'filial')
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'nome')

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'empresa', 'status')
    list_filter = ('empresa', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status',)
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'nome')

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'departamento_nome', 'empresa_nome', 'status')
    list_filter = ('departamento__empresa', 'departamento', 'status')
    search_fields = ('nome', 'departamento__nome', 'departamento__empresa__nome')
    list_editable = ('status',)
    autocomplete_fields = ('departamento',)
    ordering = ('departamento__empresa__nome', 'departamento__nome', 'nome')

    @admin.display(description='Departamento', ordering='departamento__nome')
    def departamento_nome(self, obj):
        return obj.departamento.nome if obj.departamento else '-'

    @admin.display(description='Empresa', ordering='departamento__empresa__nome')
    def empresa_nome(self, obj):
        return obj.departamento.empresa.nome if obj.departamento and obj.departamento.empresa else '-'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('departamento', 'departamento__empresa')

@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'status', 'listar_participantes')
    list_filter = ('status',)
    search_fields = ('nome',)
    list_editable = ('status',)
    filter_horizontal = ('participantes',)
    ordering = ('nome',)

    @admin.display(description='Participantes')
    def listar_participantes(self, obj):
        participantes = obj.participantes.all()[:10]
        nomes = ", ".join([p.get_full_name() or p.username for p in participantes])
        if obj.participantes.count() > 10:
            nomes += f" ... (e mais {obj.participantes.count() - 10})"
        return nomes

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('participantes')

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'empresa', 'get_hierarquia_display', 'status')
    list_filter = ('empresa', 'hierarquia', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status',)
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'hierarquia', 'nome')

    @admin.display(description='Nível Hierárquico', ordering='hierarquia')
    def get_hierarquia_display(self, obj):
        return obj.get_hierarquia_display()

@admin.register(HorarioTrabalho)
class HorarioTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'entrada', 'saida_almoco', 'volta_almoco', 'saida', 'status')
    search_fields = ('nome',)
    list_filter = ('status',)
    list_editable = ('status',)
    ordering = ('nome',)

@admin.register(ArquivoFuncionario)
class ArquivoFuncionarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'funcionario_nome', 'get_arquivo_tamanho', 'data_upload', 'status')
    list_filter = (
        'status',
        'data_upload',
        'funcionario__tipo_contrato',
        ('funcionario__empresa', admin.RelatedOnlyFieldListFilter),
        ('funcionario__departamento', admin.RelatedOnlyFieldListFilter),
        ('funcionario__setor', admin.RelatedOnlyFieldListFilter),
        ('funcionario__cargo', admin.RelatedOnlyFieldListFilter),
        ('funcionario__equipe', admin.RelatedOnlyFieldListFilter),
        'funcionario__status',
    )
    search_fields = ('titulo', 'descricao', 'funcionario__nome_completo', 'funcionario__apelido', 'funcionario__cpf')
    list_editable = ('status',)
    autocomplete_fields = ('funcionario',)
    readonly_fields = ('data_upload', 'get_arquivo_tamanho')
    list_per_page = 25
    actions = ['mark_active', 'mark_inactive']
    ordering = ('-data_upload',)

    fieldsets = (
        ('Informações do Arquivo', {
            'fields': ('titulo', 'descricao', 'arquivo', 'status')
        }),
        ('Vinculação', {
            'fields': ('funcionario',)
        }),
        ('Metadados', {
            'fields': ('data_upload', 'get_arquivo_tamanho'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Tamanho', ordering='arquivo')
    def get_arquivo_tamanho(self, obj):
        return obj.get_tamanho_arquivo()

    @admin.display(description='Funcionário', ordering='funcionario__nome_completo')
    def funcionario_nome(self, obj):
        return obj.get_nome_funcionario()

    @admin.action(description="Marcar selecionados como Ativos")
    def mark_active(self, request, queryset):
        updated = queryset.update(status=True)
        self.message_user(request, f'{updated} arquivo(s) foram marcados como ativos.')

    @admin.action(description="Marcar selecionados como Inativos")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(status=False)
        self.message_user(request, f'{updated} arquivo(s) foram marcados como inativos.')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('funcionario')

@admin.register(Comissionamento)
class RegraComissionamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'titulo', 'escopo_base', 'percentual', 'valor_fixo',
        'status', 'data_inicio', 'data_fim', 'data_criacao'
    )
    list_filter = (
        'status', 'escopo_base', 'data_inicio', 'data_fim',
        ('empresas', admin.RelatedOnlyFieldListFilter),
        ('lojas', admin.RelatedOnlyFieldListFilter),
        ('departamentos', admin.RelatedOnlyFieldListFilter),
        ('setores', admin.RelatedOnlyFieldListFilter),
        ('equipes', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ('titulo',)
    list_editable = ('status',)
    filter_horizontal = ('empresas', 'lojas', 'departamentos', 'setores', 'equipes')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    ordering = ('-status', '-data_criacao', 'titulo')
    list_per_page = 20

    fieldsets = (
        ('Configuração da Regra', {
            'fields': ('titulo', 'escopo_base', 'status')
        }),
        ('Método de Cálculo', {
            'description': "Defina como a comissão será calculada. Preencha Percentual OU Valor Fixo. Use os campos 'Valor De/Até' para faixas.",
            'fields': ('percentual', 'valor_fixo', 'valor_de', 'valor_ate')
        }),
        ('Aplicabilidade (Filtros)', {
            'description': "Selecione onde esta regra se aplica. Deixar em branco significa que não há filtro nesse nível.",
            'fields': ('empresas', 'lojas', 'departamentos', 'setores', 'equipes')
        }),
        ('Vigência e Auditoria', {
            'fields': ('data_inicio', 'data_fim', ('data_criacao', 'data_atualizacao'))
        }),
    )

    def get_queryset(self, request):
        # Otimiza a consulta pré-buscando os relacionamentos M2M para os filtros
        # Isso pode ajudar na performance dos filtros, mas pode ser pesado se houver muitos relacionamentos
        # Avaliar a necessidade real com base no uso.
        # return super().get_queryset(request).prefetch_related('empresas', 'departamentos', 'setores', 'equipes')
        # Por enquanto, vamos manter simples:
        return super().get_queryset(request)


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('get_display_name', 'cpf_formatado', 'matricula', 'get_tipo_contrato_display', 'empresa', 'get_lojas', 'departamento', 'cargo', 'status')
    list_filter = (
        FuncionarioMEIFilter, 'tipo_contrato', 'empresa', 'departamento', 'setor', 'cargo', 'equipe', 
        'status', 'lojas', 'data_admissao', 'data_demissao'
    )
    search_fields = ('nome_completo', 'apelido', 'cpf', 'matricula', 'celular1', 'lojas__nome', 'pis')
    list_per_page = 25
    autocomplete_fields = ['empresa', 'departamento', 'setor', 'cargo', 'horario', 'equipe']
    filter_horizontal = ['lojas', 'regras_comissionamento']
    readonly_fields = ('get_foto_preview',)
    actions = ['marcar_como_mei', 'marcar_como_clt', 'marcar_como_estagio', 'ativar_funcionarios', 'desativar_funcionarios']

    def get_lojas(self, obj):
        return ", ".join([loja.nome for loja in obj.lojas.all()])
    get_lojas.short_description = 'Lojas'

    fieldsets = (
        (None, {
            'fields': ('usuario',)
        }),
        ('Informações Pessoais', {
            'fields': (
                ('nome_completo', 'apelido'),
                ('foto', 'get_foto_preview'),
                ('cpf', 'data_nascimento'),
                ('genero', 'estado_civil')
            )
        }),
        ('Contato', {
            'fields': (
                ('celular1', 'celular2'),
                'cep',
                'endereco',
                ('bairro', 'cidade', 'estado')
            )
        }),
        ('Filiação e Origem', {
            'classes': ('collapse',),
            'fields': (
                ('nome_mae', 'nome_pai'),
                ('nacionalidade', 'naturalidade')
            )
        }),
        ('Profissional', {
            'fields': (
                'tipo_contrato',
                ('matricula', 'pis'),
                ('empresa', 'lojas'),
                ('departamento', 'setor'),
                ('cargo', 'horario'),
                'equipe',
                ('status', 'data_admissao', 'data_demissao')
            )
        }),
        ('Comissionamento', {
            'classes': ('collapse',),
            'fields': ('regras_comissionamento',)
        })
    )

    def get_foto_preview(self, obj):
        if obj.foto:
            return mark_safe(f'<img src="{obj.foto.url}" width="150" height="150" style="object-fit: cover; border-radius: 50%;" />')
        return "Sem foto"
    get_foto_preview.short_description = 'Preview da Foto'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'empresa', 'departamento', 'setor', 'cargo', 'horario', 'equipe'
        ).prefetch_related('lojas', 'regras_comissionamento')

    @admin.display(description='Nome', ordering='nome_completo')
    def get_display_name(self, obj):
        return obj.apelido or obj.nome_completo

    @admin.display(description='CPF', ordering='cpf')
    def cpf_formatado(self, obj):
        if obj.cpf:
            return f"{obj.cpf[:3]}.{obj.cpf[3:6]}.{obj.cpf[6:9]}-{obj.cpf[9:]}"
        return "-"

    @admin.display(description='Tipo Contrato', ordering='tipo_contrato')
    def get_tipo_contrato_display(self, obj):
        if obj.tipo_contrato:
            # Adiciona cor baseada no tipo de contrato
            if obj.tipo_contrato == 'MEI':
                return mark_safe(f'<span style="color: #28a745; font-weight: bold;">{obj.get_tipo_contrato_display()}</span>')
            elif obj.tipo_contrato == 'CLT':
                return mark_safe(f'<span style="color: #007bff; font-weight: bold;">{obj.get_tipo_contrato_display()}</span>')
            elif obj.tipo_contrato == 'ESTAGIO':
                return mark_safe(f'<span style="color: #ffc107; font-weight: bold;">{obj.get_tipo_contrato_display()}</span>')
            return obj.get_tipo_contrato_display()
        return "-"

    # Actions personalizadas para tipo de contrato
    @admin.action(description="Alterar para MEI")
    def marcar_como_mei(self, request, queryset):
        updated = queryset.update(tipo_contrato='MEI')
        self.message_user(request, f'{updated} funcionário(s) alterado(s) para MEI.')

    @admin.action(description="Alterar para CLT")
    def marcar_como_clt(self, request, queryset):
        updated = queryset.update(tipo_contrato='CLT')
        self.message_user(request, f'{updated} funcionário(s) alterado(s) para CLT.')

    @admin.action(description="Alterar para Estágio")
    def marcar_como_estagio(self, request, queryset):
        updated = queryset.update(tipo_contrato='ESTAGIO')
        self.message_user(request, f'{updated} funcionário(s) alterado(s) para Estágio.')

    @admin.action(description="Ativar funcionários selecionados")
    def ativar_funcionarios(self, request, queryset):
        updated = queryset.update(status=True)
        # Também ativar os usuários Django associados
        for funcionario in queryset.filter(usuario__isnull=False):
            funcionario.usuario.is_active = True
            funcionario.usuario.save()
        self.message_user(request, f'{updated} funcionário(s) ativado(s).')

    @admin.action(description="Desativar funcionários selecionados")
    def desativar_funcionarios(self, request, queryset):
        updated = queryset.update(status=False)
        # Também desativar os usuários Django associados
        for funcionario in queryset.filter(usuario__isnull=False):
            funcionario.usuario.is_active = False
            funcionario.usuario.save()
        self.message_user(request, f'{updated} funcionário(s) desativado(s).')

@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = (
        'assunto', 'criado_por', 'data_criacao', 'status', 'get_destinatarios_count',
        'get_arquivos_count'
    )
    list_filter = (
        'status', 'data_criacao',
        ('criado_por', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'assunto', 'texto', 'criado_por__username',
        'criado_por__first_name', 'criado_por__last_name'
    )
    list_editable = ('status',)
    filter_horizontal = ('destinatarios',)
    readonly_fields = ('data_criacao', 'get_preview_banner')
    ordering = ('-data_criacao',)
    list_per_page = 20

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('assunto', 'status', 'criado_por')
        }),
        ('Conteúdo', {
            'description': "O comunicado deve ter texto OU banner, não ambos.",
            'fields': ('texto', ('banner', 'get_preview_banner'))
        }),
        ('Destinatários', {
            'fields': ('destinatarios',)
        }),
        ('Metadados', {
            'fields': ('data_criacao',),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Destinatários', ordering='destinatarios')
    def get_destinatarios_count(self, obj):
        return obj.destinatarios.count()
    get_destinatarios_count.short_description = 'Nº de Destinatários'

    @admin.display(description='Arquivos', ordering='arquivos')
    def get_arquivos_count(self, obj):
        return obj.arquivos.count()
    get_arquivos_count.short_description = 'Nº de Arquivos'

    @admin.display(description='Preview do Banner')
    def get_preview_banner(self, obj):
        from django.utils.html import format_html
        if obj.banner:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.banner.url
            )
        return "(Sem banner)"
    get_preview_banner.short_description = 'Preview'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('criado_por').prefetch_related(
            'destinatarios', 'arquivos'
        )

@admin.register(ControleComunicado)
class ControleComunicadoAdmin(admin.ModelAdmin):
    list_display = (
        'comunicado', 'usuario', 'lido', 'data_leitura'
    )
    list_filter = (
        'lido', 'data_leitura',
        ('comunicado', admin.RelatedOnlyFieldListFilter),
        ('usuario', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'comunicado__assunto', 'usuario__username',
        'usuario__first_name', 'usuario__last_name'
    )
    list_editable = ('lido',)
    readonly_fields = ('data_leitura',)
    ordering = ('-data_leitura',)
    list_per_page = 25

    fieldsets = (
        ('Informações do Controle', {
            'fields': ('comunicado', 'usuario', 'lido', 'data_leitura')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comunicado', 'usuario')

@admin.register(ArquivoComunicado)
class ArquivoComunicadoAdmin(admin.ModelAdmin):
    list_display = (
        'get_nome_arquivo', 'comunicado', 'get_tamanho_arquivo',
        'data_criacao', 'status'
    )
    list_filter = (
        'status', 'data_criacao',
        ('comunicado', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'arquivo', 'comunicado__assunto'
    )
    list_editable = ('status',)
    readonly_fields = ('data_criacao', 'get_tamanho_arquivo')
    ordering = ('-data_criacao',)
    list_per_page = 25

    fieldsets = (
        ('Informações do Arquivo', {
            'fields': ('arquivo', 'status')
        }),
        ('Vinculação', {
            'fields': ('comunicado',)
        }),
        ('Metadados', {
            'fields': ('data_criacao', 'get_tamanho_arquivo'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Arquivo', ordering='arquivo')
    def get_nome_arquivo(self, obj):
        return os.path.basename(obj.arquivo.name)
    get_nome_arquivo.short_description = 'Nome do Arquivo'

    @admin.display(description='Tamanho', ordering='arquivo')
    def get_tamanho_arquivo(self, obj):
        try:
            tamanho = obj.arquivo.size
            if tamanho < 1024:
                return f"{tamanho} bytes"
            elif tamanho < 1024 * 1024:
                return f"{tamanho/1024:.1f} KB"
            else:
                return f"{tamanho/(1024*1024):.1f} MB"
        except:
            return "N/A"
    get_tamanho_arquivo.short_description = 'Tamanho'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comunicado')

# --- Admins para Sistema de Presença ---

@admin.register(EntradaAuto)
class EntradaAutoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'data', 'datahora', 'ip_usado', 'get_funcionario_tipo_contrato')
    list_filter = (
        'data', 'datahora',
        ('usuario', admin.RelatedOnlyFieldListFilter),
        'usuario__funcionario_profile__tipo_contrato',
        ('usuario__funcionario_profile__empresa', admin.RelatedOnlyFieldListFilter),
        ('usuario__funcionario_profile__equipe', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name',
        'usuario__funcionario_profile__nome_completo', 'ip_usado'
    )
    readonly_fields = ('datahora', 'data')
    ordering = ('-datahora',)
    list_per_page = 50

    @admin.display(description='Tipo Contrato', ordering='usuario__funcionario_profile__tipo_contrato')
    def get_funcionario_tipo_contrato(self, obj):
        if hasattr(obj.usuario, 'funcionario_profile') and obj.usuario.funcionario_profile:
            tipo = obj.usuario.funcionario_profile.tipo_contrato
            if tipo == 'MEI':
                return mark_safe(f'<span style="color: #28a745; font-weight: bold;">{tipo}</span>')
            elif tipo == 'CLT':
                return mark_safe(f'<span style="color: #007bff; font-weight: bold;">{tipo}</span>')
            elif tipo == 'ESTAGIO':
                return mark_safe(f'<span style="color: #ffc107; font-weight: bold;">{tipo}</span>')
            return tipo
        return "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'usuario', 'usuario__funcionario_profile'
        )

@admin.register(RegistroPresenca)
class RegistroPresencaAdmin(admin.ModelAdmin):
    list_display = ('get_usuario_nome', 'data_entrada', 'tipo', 'datahora', 'get_funcionario_tipo_contrato')
    list_filter = (
        'tipo', 'datahora', 'entrada_auto__data',
        ('entrada_auto__usuario', admin.RelatedOnlyFieldListFilter),
        'entrada_auto__usuario__funcionario_profile__tipo_contrato',
        ('entrada_auto__usuario__funcionario_profile__empresa', admin.RelatedOnlyFieldListFilter),
        ('entrada_auto__usuario__funcionario_profile__equipe', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'entrada_auto__usuario__username', 'entrada_auto__usuario__first_name',
        'entrada_auto__usuario__last_name', 'entrada_auto__usuario__funcionario_profile__nome_completo'
    )
    readonly_fields = ('datahora',)
    ordering = ('-datahora',)
    list_per_page = 50

    @admin.display(description='Usuário', ordering='entrada_auto__usuario__username')
    def get_usuario_nome(self, obj):
        usuario = obj.entrada_auto.usuario
        if hasattr(usuario, 'funcionario_profile') and usuario.funcionario_profile:
            return usuario.funcionario_profile.nome_completo
        return f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username

    @admin.display(description='Data de Entrada', ordering='entrada_auto__data')
    def data_entrada(self, obj):
        return obj.entrada_auto.data.strftime('%d/%m/%Y')

    @admin.display(description='Tipo Contrato', ordering='entrada_auto__usuario__funcionario_profile__tipo_contrato')
    def get_funcionario_tipo_contrato(self, obj):
        usuario = obj.entrada_auto.usuario
        if hasattr(usuario, 'funcionario_profile') and usuario.funcionario_profile:
            tipo = usuario.funcionario_profile.tipo_contrato
            if tipo == 'MEI':
                return mark_safe(f'<span style="color: #28a745; font-weight: bold;">{tipo}</span>')
            elif tipo == 'CLT':
                return mark_safe(f'<span style="color: #007bff; font-weight: bold;">{tipo}</span>')
            elif tipo == 'ESTAGIO':
                return mark_safe(f'<span style="color: #ffc107; font-weight: bold;">{tipo}</span>')
            return tipo
        return "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'entrada_auto__usuario', 'entrada_auto__usuario__funcionario_profile'
        )

@admin.register(RelatorioSistemaPresenca)
class RelatorioSistemaPresencaAdmin(admin.ModelAdmin):
    list_display = ('get_usuario_nome', 'data', 'observacao_resumida', 'data_criacao', 'get_funcionario_tipo_contrato')
    list_filter = (
        'data', 'data_criacao',
        ('usuario', admin.RelatedOnlyFieldListFilter),
        'usuario__funcionario_profile__tipo_contrato',
        ('usuario__funcionario_profile__empresa', admin.RelatedOnlyFieldListFilter),
        ('usuario__funcionario_profile__equipe', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name',
        'usuario__funcionario_profile__nome_completo', 'observacao'
    )
    readonly_fields = ('data_criacao',)
    ordering = ('-data_criacao',)
    list_per_page = 50

    @admin.display(description='Usuário', ordering='usuario__username')
    def get_usuario_nome(self, obj):
        if hasattr(obj.usuario, 'funcionario_profile') and obj.usuario.funcionario_profile:
            return obj.usuario.funcionario_profile.nome_completo
        return f"{obj.usuario.first_name} {obj.usuario.last_name}".strip() or obj.usuario.username

    @admin.display(description='Observação', ordering='observacao')
    def observacao_resumida(self, obj):
        if len(obj.observacao) > 50:
            return obj.observacao[:50] + "..."
        return obj.observacao

    @admin.display(description='Tipo Contrato', ordering='usuario__funcionario_profile__tipo_contrato')
    def get_funcionario_tipo_contrato(self, obj):
        if hasattr(obj.usuario, 'funcionario_profile') and obj.usuario.funcionario_profile:
            tipo = obj.usuario.funcionario_profile.tipo_contrato
            if tipo == 'MEI':
                return mark_safe(f'<span style="color: #28a745; font-weight: bold;">{tipo}</span>')
            elif tipo == 'CLT':
                return mark_safe(f'<span style="color: #007bff; font-weight: bold;">{tipo}</span>')
            elif tipo == 'ESTAGIO':
                return mark_safe(f'<span style="color: #ffc107; font-weight: bold;">{tipo}</span>')
            return tipo
        return "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'usuario', 'usuario__funcionario_profile'
        )
