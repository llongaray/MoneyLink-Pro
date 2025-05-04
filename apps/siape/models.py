from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from django.contrib.auth.models import User
from apps.funcionarios.models import Funcionario, Loja, Departamento, Equipe, Setor

class Campanha(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Campanha", blank=True, null=True)
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Criação", blank=True, null=True)
    setor = models.ForeignKey(
        Setor,
        on_delete=models.SET_NULL, # Usar SET_NULL para não deletar a campanha se o setor for excluído, ou PROTECT/CASCADE conforme regra
        related_name='campanhas_siape',
        verbose_name="Setor",
        blank=True,
        null=True
    )
    status = models.BooleanField(default=True, verbose_name="Status", blank=True, null=True)  # True para Ativo, False para Inativo

    def __str__(self):
        return f"{self.nome} - {self.setor.nome if self.setor else 'Sem Setor'} - {'Ativo' if self.status else 'Inativo'}"

class Cliente(models.Model):
    # Informações Pessoais
    nome = models.CharField(max_length=100, verbose_name="Nome", blank=True, null=True, db_index=True)
    cpf = models.CharField(
        max_length=11,
        unique=True,
        validators=[RegexValidator(r'^\d{11}$')],
        verbose_name="CPF",
        blank=True,
        null=True,
        db_index=True  # Adiciona índice no CPF para consultas mais rápidas
    )
    uf = models.CharField(max_length=2, verbose_name="UF", blank=True, null=True, db_index=True)
    rjur = models.CharField(max_length=50, verbose_name="RJur", blank=True, null=True)
    situacao_funcional = models.CharField(max_length=50, verbose_name="Situação Funcional", blank=True, null=True, db_index=True)

    # Dados Financeiros
    renda_bruta = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Renda Bruta")
    bruta_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Bruta 5")
    util_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Utilizado 5")
    saldo_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Saldo 5")
    brutaBeneficio_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Bruta Benefício 5")
    utilBeneficio_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Utilizado Benefício 5")
    saldoBeneficio_5 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Saldo Benefício 5")
    bruta_35 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Bruta 35")
    util_35 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Utilizado 35")
    saldo_35 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Saldo 35")
    total_util = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Total Utilizado")
    total_saldo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Total Saldo")

    class Meta:
        indexes = [
            models.Index(fields=['cpf']),
            models.Index(fields=['nome']),
            models.Index(fields=['uf', 'situacao_funcional']),
        ]

    def __str__(self):
        return f"{self.nome} - {self.cpf}"


class Debito(models.Model):
    # Relacionamento com o Cliente e com a Campanha
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='debitos', db_index=True)
    campanha = models.ForeignKey('Campanha', on_delete=models.CASCADE, related_name='debitos', db_index=True)
    
    # Campos do Débito (SIAPE)
    matricula = models.CharField(max_length=50, verbose_name="Matrícula", blank=True, null=True, db_index=True)
    banco = models.CharField(max_length=100, verbose_name="Banco", blank=True, null=True)
    orgao = models.CharField(max_length=50, verbose_name="Órgão", blank=True, null=True)
    rebrica = models.CharField(max_length=50, verbose_name="Rebrica", blank=True, null=True)
    parcela = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Parcela")
    prazo_restante = models.PositiveIntegerField(blank=True, null=True, verbose_name="Prazo Restante")
    tipo_contrato = models.CharField(max_length=50, verbose_name="Tipo de Contrato", blank=True, null=True)
    num_contrato = models.CharField(max_length=50, verbose_name="Número do Contrato", blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['cliente', 'campanha']),
            models.Index(fields=['matricula', 'parcela', 'prazo_restante']),
        ]

    def __str__(self):
        return f"{self.matricula} - {self.num_contrato or 'Sem Contrato'}"

class Produto(models.Model):
    """
    Modelo para representar os produtos oferecidos.
    """
    nome = models.CharField(max_length=100, verbose_name="Nome do Produto", unique=True)
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['nome']


class RegisterMoney(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    # Alterado on_delete para SET_NULL para preservar registros se a loja for excluída
    loja = models.ForeignKey(Loja, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Loja")
    cpf_cliente = models.CharField(max_length=14, blank=True, null=True, db_index=True) # Adicionado db_index
    produto = models.ForeignKey(
        Produto,
        on_delete=models.SET_NULL, # Mantém SET_NULL
        null=True,
        blank=True,
        verbose_name="Produto"
    )
    valor_est = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Valor Estimado/Registrado")
    status = models.BooleanField(default=True, blank=True, null=True, verbose_name="Status (Ativo)") # Considerar choices se houver mais status
    data = models.DateTimeField(default=timezone.now, blank=True, null=True, verbose_name="Data do Registro", db_index=True) # Adicionado db_index

    # Novos campos de associação organizacional
    empresa = models.ForeignKey(
        'funcionarios.Empresa', # Usando string para evitar import direto se preferir
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Empresa Associada",
        related_name='registros_financeiros'
    )
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Departamento Associado",
        related_name='registros_financeiros'
    )
    setor = models.ForeignKey(
        Setor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Setor Associado",
        related_name='registros_financeiros'
    )
    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Equipe Associada",
        related_name='registros_financeiros'
    )

    def __str__(self):
        display_name = f"User ID {self.user_id}" # Default
        try:
            # Tenta buscar o Funcionario associado ao User de forma otimizada
            # Evita import local repetido e usa select_related se possível (embora aqui seja get)
            # Nota: A lógica original com import local dentro do método é funcional, mas menos ideal.
            # Idealmente, a relação User -> Funcionario seria mais direta ou gerenciada de outra forma.
            funcionario = Funcionario.objects.select_related('usuario').get(usuario=self.user)
            # Usa apelido se existir, senão o primeiro nome
            display_name = funcionario.apelido or funcionario.nome_completo.split()[0]
        except Funcionario.DoesNotExist:
            # Se não encontrar Funcionario, usa o username do User (se user ainda existir)
            if self.user:
                display_name = self.user.username
        except Exception:
            # Fallback genérico para outros erros inesperados
            # Logar o erro seria bom em produção: logger.exception("Erro ao buscar funcionário em RegisterMoney.__str__")
            pass # Mantém o default "User ID X"

        valor_str = f"{self.valor_est:.2f}" if self.valor_est is not None else "N/A"
        produto_str = self.produto.nome if self.produto else "Sem Produto"

        # Adiciona informações organizacionais se disponíveis
        org_info = []
        if self.loja: org_info.append(f"Loja: {self.loja.nome}")
        if self.setor: org_info.append(f"Setor: {self.setor.nome}")
        if self.equipe: org_info.append(f"Equipe: {self.equipe.nome}")

        org_str = " | ".join(org_info) if org_info else "Sem Info Org."

        return f'{display_name} - {self.cpf_cliente or "Sem CPF"} - {produto_str} - R$ {valor_str} ({org_str})'

    class Meta:
        verbose_name = "Registro Financeiro"
        verbose_name_plural = "Registros Financeiros"
        ordering = ['-data']
        indexes = [
            models.Index(fields=['cpf_cliente']),
            models.Index(fields=['data']),
            models.Index(fields=['user']),
            models.Index(fields=['loja']),
            models.Index(fields=['empresa']),
            models.Index(fields=['departamento']),
            models.Index(fields=['setor']),
            models.Index(fields=['equipe']),
        ]

class RegisterMeta(models.Model):
    CATEGORIA_CHOICES = [
        ('GERAL', 'Geral - Todas as equipes'),
        ('EMPRESA', 'Empresa'),
        ('FRANQUIA', 'Franquia'),
        ('LOJAS', 'Lojas'),
        ('SETOR', 'Setor'),
        ('OUTROS', 'Outros')
    ]
    
    titulo = models.TextField(max_length=100, default="Ranking Geral", blank=True, null=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES, default='GERAL', blank=True, null=True)
    equipe = models.ManyToManyField(Equipe, blank=True, help_text="Selecione uma ou mais equipes quando a categoria for 'Outros'")
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, blank=True, null=True, help_text="Selecione o setor quando a categoria for 'Setor'")
    data_inicio = models.DateTimeField(blank=True, null=True, help_text="Data e hora de início (meia-noite AM)")
    data_fim = models.DateTimeField(blank=True, null=True, help_text="Data e hora de término (meia-noite PM)")
    status = models.BooleanField(default=False, blank=True, null=True, help_text="Ativo ou Inativo")
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.categoria == 'GERAL':
            return f'Meta Geral: {self.valor:.2f}'
        elif self.categoria == 'OUTROS':
            equipes = ', '.join([equipe.nome for equipe in self.equipe.all()])
            return f'Meta {equipes}: {self.valor:.2f}'
        elif self.categoria == 'SETOR':
            return f'Meta Setor {self.setor.nome if self.setor else "N/A"}: {self.valor:.2f}'
        return f'Meta {self.categoria}: {self.valor:.2f}'


class AgendamentoFichaCliente(models.Model):
    STATUS_CHOICES = [
        ('AGENDADO', 'Agendado'),
        ('CONFIRMADO', 'Confirmado'),
        ('FECHOU', 'Fechou negócio'),
        ('NAO_QUIS', 'Não quis')
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='agendamentos')
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, verbose_name="Usuário", related_name='agendamentos_criados')
    data = models.DateField(verbose_name="Data")
    hora = models.TimeField(verbose_name="Hora")
    observacao = models.TextField(verbose_name="Observação", blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='AGENDADO',
        verbose_name="Status",
        help_text="Status atual do agendamento"
    )

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        ordering = ['-data', '-hora']

    def __str__(self):
        return f"Agendamento - {self.cliente.nome} - {self.data} {self.hora}"


class Reembolso(models.Model):
    """
    Registra a ocorrência e a data de reembolso para um registro financeiro.
    Este modelo simplificado apenas marca se um RegisterMoney foi reembolsado.
    """
    # Relação um-para-um: Cada RegisterMoney pode ter no máximo um registro de reembolso.
    registermoney = models.OneToOneField(
        'RegisterMoney',
        on_delete=models.PROTECT,  # Impede a exclusão de RegisterMoney se houver reembolso associado
        related_name='reembolso_info', # Nome do relacionamento reverso
        verbose_name="Registro Financeiro",
        help_text="O registro financeiro que foi reembolsado.",
        primary_key=True, # Torna a chave estrangeira a chave primária da tabela Reembolso
    )
    data_reembolso = models.DateField(
        verbose_name="Data do Reembolso",
        help_text="Data em que o reembolso foi efetivado."
        # Considerar adicionar default=timezone.now se apropriado ao criar
    )
    # O status booleano confirma que o reembolso ocorreu.
    # Se a simples existência do registro já implica reembolso, este campo pode
    # ser redundante, mas foi explicitamente solicitado.
    status = models.BooleanField(
        default=True,
        verbose_name="Reembolsado",
        help_text="Indica que o reembolso foi efetivado (True)."
    )
    # data_criacao pode ser útil para rastreamento, adicionando opcionalmente:
    # data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação do Registro")

    class Meta:
        verbose_name = "Registro de Reembolso"
        verbose_name_plural = "Registros de Reembolso"
        # Ordena pela data de reembolso mais recente por padrão
        ordering = ['-data_reembolso']

    def __str__(self):
        """
        Representação em string do objeto Reembolso.
        """
        try:
            # Tenta obter uma representação mais descritiva do registro financeiro
            # Assumindo que RegisterMoney tem um __str__ útil
            register_info = str(self.registermoney)
        except Exception:
            # Fallback caso RegisterMoney não exista mais ou __str__ falhe
            register_info = f"ID Registro: {self.registermoney_id}"

        status_str = "Reembolsado" if self.status else "Status Pendente/Inválido"
        return f"{status_str} - {register_info} em {self.data_reembolso.strftime('%d/%m/%Y')}"
