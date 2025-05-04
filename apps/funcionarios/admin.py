from django.contrib import admin
from .models import *

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'endereco', 'status')
    search_fields = ('nome', 'cnpj')
    list_filter = ('status',)
    list_editable = ('status',)
    ordering = ('nome',)

@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'franquia', 'filial', 'status')
    list_filter = ('empresa', 'franquia', 'filial', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status', 'franquia', 'filial')
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'nome')

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'status')
    list_filter = ('empresa', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status',)
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'nome')

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'departamento_nome', 'empresa_nome', 'status')
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
        # Otimiza a consulta buscando os relacionamentos necessários
        return super().get_queryset(request).select_related('departamento', 'departamento__empresa')


@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'status', 'listar_participantes')
    list_filter = ('status',)
    search_fields = ('nome',)
    list_editable = ('status',)
    filter_horizontal = ('participantes',)
    ordering = ('nome',)

    @admin.display(description='Participantes')
    def listar_participantes(self, obj):
        # Limita a quantidade de participantes exibidos para performance
        participantes = obj.participantes.all()[:10]
        nomes = ", ".join([p.get_full_name() or p.username for p in participantes])
        if obj.participantes.count() > 10:
            nomes += f" ... (e mais {obj.participantes.count() - 10})"
        return nomes

    def get_queryset(self, request):
        # Otimiza a consulta buscando os participantes
        return super().get_queryset(request).prefetch_related('participantes')

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'get_hierarquia_display', 'status')
    list_filter = ('empresa', 'hierarquia', 'status')
    search_fields = ('nome', 'empresa__nome')
    list_editable = ('status',)
    autocomplete_fields = ('empresa',)
    ordering = ('empresa__nome', 'hierarquia', 'nome')

    # get_hierarquia_display já existe no model, não precisa redefinir aqui
    # Apenas garantindo que ele seja usado corretamente
    @admin.display(description='Nível Hierárquico', ordering='hierarquia')
    def get_hierarquia_display(self, obj):
        return obj.get_hierarquia_display()

@admin.register(HorarioTrabalho)
class HorarioTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'entrada', 'saida_almoco', 'volta_almoco', 'saida', 'status')
    search_fields = ('nome',)
    list_filter = ('status',)
    list_editable = ('status',)
    ordering = ('nome',)

@admin.register(ArquivoFuncionario)
class ArquivoFuncionarioAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'funcionario_nome', 'get_arquivo_tamanho', 'data_upload', 'status')
    list_filter = (
        'status',
        'data_upload',
        ('funcionario__empresa', admin.RelatedOnlyFieldListFilter),
        ('funcionario__departamento', admin.RelatedOnlyFieldListFilter),
        ('funcionario__setor', admin.RelatedOnlyFieldListFilter),
        ('funcionario__cargo', admin.RelatedOnlyFieldListFilter),
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
            'classes': ('collapse',) # Mantém colapsado por padrão
        }),
    )

    @admin.display(description='Tamanho', ordering='arquivo') # Ordenar por tamanho pode ser pesado
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
        # Otimiza a consulta buscando o funcionário relacionado
        return super().get_queryset(request).select_related('funcionario')

# Novo Admin para Comissionamento
@admin.register(Comissionamento)
class RegraComissionamentoAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'escopo_base', 'percentual', 'valor_fixo',
        'status', 'data_inicio', 'data_fim', 'data_criacao'
    )
    list_filter = (
        'status', 'escopo_base', 'data_inicio', 'data_fim',
        ('empresas', admin.RelatedOnlyFieldListFilter),
        ('departamentos', admin.RelatedOnlyFieldListFilter),
        ('setores', admin.RelatedOnlyFieldListFilter),
        ('equipes', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ('titulo',)
    list_editable = ('status',)
    filter_horizontal = ('empresas', 'departamentos', 'setores', 'equipes')
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
            'fields': ('empresas', 'departamentos', 'setores', 'equipes')
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
    list_display = (
        'get_display_name', 'cpf_formatado', 'matricula', 'empresa', 'loja', 'departamento', 'setor', 'cargo', 'status'
    )
    search_fields = (
        'nome_completo', 'apelido', 'cpf', 'matricula', 'celular1', 'usuario__username',
        'empresa__nome', 'loja__nome', 'departamento__nome', 'setor__nome', 'cargo__nome' # Adicionado busca por campos relacionados
    )
    list_filter = (
        'status',
        ('empresa', admin.RelatedOnlyFieldListFilter),
        ('loja', admin.RelatedOnlyFieldListFilter),
        ('departamento', admin.RelatedOnlyFieldListFilter),
        ('setor', admin.RelatedOnlyFieldListFilter),
        ('cargo', admin.RelatedOnlyFieldListFilter),
        'genero', 'estado_civil'
    )
    list_editable = ('status',)
    ordering = ('empresa__nome', 'nome_completo')
    list_per_page = 25
    filter_horizontal = ('regras_comissionamento',)

    fieldsets = (
        (None, { # Campo sem título explícito para o vínculo principal
            'fields': ('usuario',)
        }),
        ('Informações Pessoais', {
            'fields': (('nome_completo', 'apelido'), ('foto', 'get_foto_preview'), ('cpf', 'data_nascimento'), ('genero', 'estado_civil'))
        }),
        ('Contato', {
            'fields': (('celular1', 'celular2'), 'cep', 'endereco', ('bairro', 'cidade', 'estado'))
        }),
        ('Filiação e Origem', {
            'classes': ('collapse',), # Mantém colapsado por padrão
            'fields': (('nome_mae', 'nome_pai'), ('nacionalidade', 'naturalidade'))
        }),
        ('Profissional', {
            'fields': (
                ('matricula', 'pis'),
                ('empresa', 'loja'),
                ('departamento', 'setor'),
                ('cargo', 'horario'),
                'equipe',
                ('status', 'data_admissao', 'data_demissao')
            )
        }),
        ('Comissionamento', {
             'classes': ('collapse',), # Pode começar colapsado se preferir
             'fields': ('regras_comissionamento',)
        })
    )
    autocomplete_fields = ('usuario', 'empresa', 'loja', 'departamento', 'setor', 'cargo', 'horario', 'equipe')
    readonly_fields = ('get_foto_preview',) # Adiciona preview da foto se houver

    # Adiciona um preview da foto no admin
    def get_foto_preview(self, obj):
        from django.utils.html import format_html
        if obj.foto:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.foto.url)
        return "(Sem foto)"
    get_foto_preview.short_description = 'Preview da Foto'

    # Inclui o preview no fieldset de Informações Pessoais
    fieldsets[1][1]['fields'] = (('nome_completo', 'apelido'), ('foto', 'get_foto_preview'), ('cpf', 'data_nascimento'), ('genero', 'estado_civil'))


    def get_queryset(self, request):
        # Otimiza a consulta buscando todos os relacionamentos ForeignKey de uma vez
        return super().get_queryset(request).select_related(
            'usuario', 'empresa', 'loja', 'departamento', 'setor', 'cargo', 'horario'
        ).prefetch_related('equipe', 'regras_comissionamento') # Adicionado prefetch_related para o M2M

    @admin.display(description='Nome', ordering='nome_completo')
    def get_display_name(self, obj):
        # Usa apelido se existir, senão nome completo
        return obj.apelido or obj.nome_completo

    @admin.display(description='CPF', ordering='cpf')
    def cpf_formatado(self, obj):
        # Exemplo de formatação simples (pode ser melhorada)
        if obj.cpf and len(obj.cpf) == 11:
            return f"{obj.cpf[:3]}.{obj.cpf[3:6]}.{obj.cpf[6:9]}-{obj.cpf[9:]}"
        return obj.cpf
