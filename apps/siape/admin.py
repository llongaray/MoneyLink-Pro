from django.contrib import admin
from .models import (
    Campanha, Cliente, Debito, Produto, RegisterMoney, RegisterMeta,
    AgendamentoFichaCliente, Reembolso # Importa o novo modelo Reembolso
)
# Import relativo para acessar o modelo Funcionario da app funcionarios
# Certifique-se que a estrutura do projeto permite isso (apps no mesmo nível)
try:
    from ..funcionarios.models import Funcionario
except ImportError:
    # Fallback caso a estrutura seja diferente ou a app não exista
    # Você pode querer logar um aviso aqui ou lidar de outra forma
    Funcionario = None

@admin.register(Campanha)
class CampanhaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'get_setor_nome', 'data_criacao', 'status')
    list_filter = ('status', 'setor')
    search_fields = ('nome', 'setor__nome')
    list_editable = ('status',)
    date_hierarchy = 'data_criacao'
    ordering = ('-data_criacao', 'nome')
    autocomplete_fields = ('setor',)
    list_select_related = ('setor',)

    @admin.display(description='Setor', ordering='setor__nome')
    def get_setor_nome(self, obj):
        return obj.setor.nome if obj.setor else 'N/A'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'uf', 'situacao_funcional', 'renda_bruta', 'total_saldo')
    list_filter = ('uf', 'situacao_funcional', 'rjur')
    search_fields = ('nome', 'cpf')
    readonly_fields = ('total_util', 'total_saldo') # Campos calculados podem ser readonly
    fieldsets = (
        ('Informações Pessoais', {
            'fields': ('nome', 'cpf', 'uf', 'rjur', 'situacao_funcional')
        }),
        ('Dados Financeiros (Margem)', {
            'fields': (
                'renda_bruta',
                ('bruta_5', 'util_5', 'saldo_5'),
                ('brutaBeneficio_5', 'utilBeneficio_5', 'saldoBeneficio_5'),
                ('bruta_35', 'util_35', 'saldo_35'),
                ('total_util', 'total_saldo')
            ),
            'classes': ('collapse',) # Opcional: recolher seção por padrão
        })
    )
    ordering = ('nome',)

@admin.register(Debito)
class DebitoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'campanha', 'matricula', 'banco', 'orgao', 'parcela', 'prazo_restante', 'tipo_contrato', 'num_contrato')
    list_filter = ('banco', 'tipo_contrato', 'campanha', 'orgao')
    search_fields = ('matricula', 'num_contrato', 'cliente__nome', 'cliente__cpf', 'banco', 'orgao')
    autocomplete_fields = ('cliente', 'campanha') # Usar autocomplete para FKs com muitos registros
    list_select_related = ('cliente', 'campanha') # Otimiza a busca dos nomes
    ordering = ('cliente__nome', '-campanha__data_criacao')

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'ativo', 'data_criacao')
    list_filter = ('ativo',)
    search_fields = ('nome', 'descricao')
    list_editable = ('ativo',)
    ordering = ('nome',)

@admin.register(RegisterMoney)
class RegisterMoneyAdmin(admin.ModelAdmin):
    list_display = ('get_user_display', 'loja', 'produto', 'cpf_cliente', 'valor_est', 'status', 'data')
    list_filter = ('status', 'loja', 'produto', 'data')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        # Assumindo que Funcionario tem um campo 'usuario' (ForeignKey ou OneToOne) para User
        # e um campo 'apelido'
        'user__funcionario__apelido',
        'cpf_cliente',
        'produto__nome',
        'loja__nome'
    )
    date_hierarchy = 'data'
    autocomplete_fields = ('user', 'loja', 'produto')
    list_select_related = ('user', 'loja', 'produto') # Otimiza a busca
    list_editable = ('status',)
    readonly_fields = ('data',)
    ordering = ('-data',)

    @admin.display(description='Usuário', ordering='user__username')
    def get_user_display(self, obj):
        # Tenta buscar o funcionário associado para exibir nome/apelido
        if Funcionario: # Verifica se o import funcionou
            try:
                # Acessa o funcionário relacionado ao usuário.
                # Ajuste 'funcionario' se o related_name/field name for diferente.
                # Ex: Se Funcionario tem OneToOneField 'user', use obj.user.funcionario
                # Ex: Se User tem OneToOneField 'funcionario_profile', use obj.user.funcionario_profile
                # Baseado no __str__ do modelo, parece ser Funcionario.objects.get(usuario=obj.user)
                # então o acesso reverso seria obj.user.funcionario (se related_name não for definido ou for 'funcionario')
                funcionario = getattr(obj.user, 'funcionario', None) # Acesso seguro
                if funcionario:
                     # Usa apelido, senão nome completo, senão username
                    return funcionario.apelido or funcionario.nome_completo or obj.user.username
                else: # Se não houver funcionário ligado ao user
                    return obj.user.username
            except AttributeError: # Caso o related name/field não exista
                 return obj.user.username
            except Exception: # Captura genérica para outros erros inesperados
                return f"Erro ao buscar funcionário (User ID: {obj.user_id})"
        else: # Se Funcionario não pôde ser importado
            return obj.user.username


@admin.register(RegisterMeta)
class RegisterMetaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'valor', 'categoria', 'get_target_display', 'data_inicio', 'data_fim', 'status')
    list_filter = ('categoria', 'status', 'setor', 'equipe') # Adicionado equipe ao filtro
    search_fields = ('titulo', 'setor__nome', 'equipe__nome') # Adicionado equipe à busca
    filter_horizontal = ('equipe',) # Mantém para M2M
    date_hierarchy = 'data_inicio'
    autocomplete_fields = ('setor', 'equipe') # Mantém autocomplete
    list_editable = ('status',)
    ordering = ('-data_inicio', 'categoria')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'valor', 'categoria')
        }),
        ('Período da Meta', {
            'fields': ('data_inicio', 'data_fim')
        }),
        ('Alvo da Meta (Configuração)', {
            'description': "Selecione Setor OU Equipe(s) conforme a Categoria.",
            'fields': ('setor', 'equipe', 'status') # Agrupados
        }),
         ('Datas de Controle', {
            'fields': ('data_criacao',),
            'classes': ('collapse',) # Oculta por padrão
        })
    )
    readonly_fields = ('data_criacao',)

    @admin.display(description='Alvo (Setor/Equipe)', ordering='categoria')
    def get_target_display(self, obj):
        if obj.categoria == 'SETOR' and obj.setor:
            return f"Setor: {obj.setor.nome}"
        elif obj.categoria == 'OUTROS' and obj.equipe.exists():
            return f"Equipe(s): {', '.join([e.nome for e in obj.equipe.all()])}"
        elif obj.categoria == 'GERAL':
             return "Geral"
        # Adicionar lógica para outras categorias se necessário (EMPRESA, FRANQUIA, LOJAS)
        return obj.get_categoria_display() # Fallback para o nome da categoria

@admin.register(AgendamentoFichaCliente)
class AgendamentoFichaClienteAdmin(admin.ModelAdmin):
    list_display = ('get_cliente_nome', 'get_usuario_display', 'data', 'hora', 'status', 'data_criacao')
    list_filter = ('status', 'data', 'usuario') # Adicionado usuário ao filtro
    search_fields = ('cliente__nome', 'cliente__cpf', 'usuario__username', 'usuario__first_name', 'usuario__last_name')
    date_hierarchy = 'data'
    autocomplete_fields = ('cliente', 'usuario')
    readonly_fields = ('data_criacao',)
    list_select_related = ('cliente', 'usuario') # Otimiza busca
    ordering = ('-data', '-hora')
    fieldsets = (
        ('Agendamento', {
            'fields': ('cliente', 'usuario', ('data', 'hora')) # Data e hora na mesma linha
        }),
        ('Status e Observações', {
            'fields': ('status', 'observacao')
        }),
        ('Informações do Sistema', {
            'fields': ('data_criacao',),
            'classes': ('collapse',)
        })
    )

    @admin.display(description='Cliente', ordering='cliente__nome')
    def get_cliente_nome(self, obj):
        return obj.cliente.nome if obj.cliente else 'N/A'

    @admin.display(description='Usuário Agendou', ordering='usuario__username')
    def get_usuario_display(self, obj):
        # Similar ao RegisterMoneyAdmin, tenta mostrar nome/apelido se possível
        if Funcionario:
             try:
                funcionario = getattr(obj.usuario, 'funcionario', None)
                if funcionario:
                    return funcionario.apelido or funcionario.nome_completo or obj.usuario.username
                else:
                    return obj.usuario.username
             except Exception:
                 return obj.usuario.username # Fallback
        return obj.usuario.username

# Adiciona a classe Admin para o modelo Reembolso
@admin.register(Reembolso)
class ReembolsoAdmin(admin.ModelAdmin):
    list_display = ('registermoney', 'data_reembolso', 'status')
    list_filter = ('status', 'data_reembolso')
    search_fields = (
        'registermoney__cpf_cliente', # Busca pelo CPF do cliente no RegisterMoney
        'registermoney__produto__nome', # Busca pelo nome do produto
        'registermoney__user__username', # Busca pelo username do usuário
        'registermoney__user__first_name',
        'registermoney__user__last_name',
    )
    date_hierarchy = 'data_reembolso'
    autocomplete_fields = ('registermoney',) # Permite autocompletar o campo RegisterMoney
    list_select_related = ('registermoney',) # Otimiza a busca do objeto RegisterMoney relacionado
    ordering = ('-data_reembolso',)
    # O campo registermoney é a PK e OneToOne, geralmente não é editável após a criação
    # Mas como é OneToOne, a criação é feita *a partir* de um RegisterMoney existente
    # readonly_fields = ('registermoney',) # Pode ser útil tornar readonly após a criação

    # Opcional: Adicionar um método para exibir informações mais detalhadas do RegisterMoney
    # @admin.display(description='Registro Financeiro')
    # def get_registermoney_info(self, obj):
    #     if obj.registermoney:
    #         return f"ID: {obj.registermoney.id} - Cliente: {obj.registermoney.cpf_cliente} - Valor: {obj.registermoney.valor_est}"
    #     return "N/A"
    # Se usar este método, adicione 'get_registermoney_info' ao list_display
