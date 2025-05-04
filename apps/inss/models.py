from django.db import models
from django.contrib.auth.models import User
from apps.funcionarios.models import Loja # Importa Loja do app funcionarios
from django.utils import timezone

# Modelo para dados do cliente que será agendado
class ClienteAgendamento(models.Model):
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF") # Considerar validação/máscara
    numero = models.CharField(max_length=20, verbose_name="Número de Contato") # Celular/Telefone
    flg_whatsapp = models.BooleanField(default=True, verbose_name="Possui WhatsApp")
    status = models.BooleanField(default=True, verbose_name="Ativo")

    def __str__(self):
        return f"{self.nome_completo} ({self.cpf})"

    class Meta:
        verbose_name = "Cliente para Agendamento"
        verbose_name_plural = "Clientes para Agendamento"
        ordering = ['nome_completo']

# Modelo para o agendamento em si
class Agendamento(models.Model):
    cliente_agendamento = models.ForeignKey(
        ClienteAgendamento, 
        on_delete=models.CASCADE, # Se excluir o cliente, exclui o agendamento
        related_name='agendamentos',
        verbose_name="Cliente"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    dia_agendado = models.DateTimeField(verbose_name="Data e Hora Agendada")
    loja = models.ForeignKey(
        Loja, 
        on_delete=models.PROTECT, # Protege contra exclusão da Loja se houver agendamentos
        related_name='agendamentos_loja',
        verbose_name="Loja Agendada"
    )
    atendente_agendou = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='inss_agendamentos_criados', 
        verbose_name="Atendente que Agendou"
    )
    tabulacao_agendamento = models.TextField(blank=True, null=True, verbose_name="Tabulação do Agendamento")

    def __str__(self):
        return f"Agendamento de {self.cliente_agendamento.nome_completo} para {self.dia_agendado.strftime('%d/%m/%Y %H:%M')} na loja {self.loja.nome}"

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        ordering = ['-dia_agendado']

# Modelo para registrar a presença/resultado da visita na loja
class PresencaLoja(models.Model):
    
    # Choices para Tabulação da Venda
    class TabulacaoVendaChoices(models.TextChoices):
        NEGOCIO_FECHADO = 'NEGOCIO FECHADO', 'NEGÓCIO FECHADO'
        INELEGIVEL = 'INELEGIVEL', 'INELEGÍVEL'
        NAO_ACEITOU = 'NAO ACEITOU', 'NÃO ACEITOU'
        NAO_QUIS_OUVIR = 'NAO QUIS OUVIR', 'NÃO QUIS OUVIR'
        PENDENTE = 'PENDENTE', 'PENDENTE' # Adicionado PENDENTE como opção

    # Choices para Status do Pagamento
    class StatusPagamentoChoices(models.TextChoices):
        EM_ESPERA = 'EM_ESPERA', 'EM ESPERA'
        NAO_PAGO  = 'NAO_PAGO',  'NÃO PAGO'
        PAGO      = 'PAGO',      'PAGO'

    agendamento = models.OneToOneField( # Mudado para OneToOneField para linkar diretamente ao agendamento se existir
        Agendamento, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='presenca',
        verbose_name="Agendamento Associado"
    )
    cliente_agendamento = models.ForeignKey( # Mantido como ForeignKey para clientes de rua
        ClienteAgendamento, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='presencas', 
        verbose_name="Cliente (Rua / Sem Agendamento)"
    )
    loja_comp = models.ForeignKey(
        Loja,
        on_delete=models.PROTECT,  # Protege contra exclusão da Loja
        related_name='presencas_loja',
        verbose_name="Loja de Comparecimento"
    )
    vendedor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vendas_realizadas', 
        verbose_name="Vendedor"
    )
    tabulacao_venda = models.CharField(
        max_length=50, 
        choices=TabulacaoVendaChoices.choices,
        blank=True, null=True, # Permitir nulo inicialmente
        verbose_name="Tabulação da Venda"
    )
    
    # Campos preenchidos principalmente se tabulacao_venda == 'NEGOCIO FECHADO'
    tipo_negociacao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Negociação")
    banco = models.CharField(max_length=100, blank=True, null=True, verbose_name="Banco")
    subsidio = models.BooleanField(default=False, verbose_name="Subsídio")
    valor_tac = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Valor TAC")
    acao = models.BooleanField(default=False, verbose_name="Com Ação Judicial")
    associacao = models.BooleanField(default=False, verbose_name="Com Associação")
    aumento = models.BooleanField(default=False, verbose_name="Com Aumento de Margem")
    
    status_pagamento = models.CharField(
        max_length=20, 
        choices=StatusPagamentoChoices.choices, 
        default=StatusPagamentoChoices.EM_ESPERA, 
        verbose_name="Status Pagamento TAC"
    )
    data_pagamento = models.DateTimeField(null=True, blank=True, verbose_name="Data Pagamento TAC")
    
    cliente_rua = models.BooleanField(default=False, verbose_name="Cliente Veio Direto da Rua")
    data_presenca = models.DateTimeField(default=timezone.now, verbose_name="Data/Hora da Presença/Registro")

    def __str__(self):
        cliente_nome = "Cliente Desconhecido"
        if self.agendamento and self.agendamento.cliente_agendamento:
            cliente_nome = self.agendamento.cliente_agendamento.nome_completo
        elif self.cliente_agendamento:
            cliente_nome = self.cliente_agendamento.nome_completo
        
        loja_nome = self.loja_comp.nome if self.loja_comp else "Loja não especificada"
        
        return f"Presença/Resultado de {cliente_nome} em {self.data_presenca.strftime('%d/%m/%Y %H:%M')} na loja {loja_nome}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Garante que ou agendamento ou cliente_agendamento (para cliente de rua) esteja preenchido
        if not self.agendamento and not self.cliente_agendamento:
            raise ValidationError('É necessário associar a um Agendamento ou a um Cliente (para clientes de rua).')
        # Garante que cliente_rua seja True se não houver agendamento
        if not self.agendamento and self.cliente_agendamento and not self.cliente_rua:
             raise ValidationError('Marque "Cliente Veio Direto da Rua" se não houver um agendamento associado.')
        # Garante que se houver agendamento, cliente_rua seja False
        if self.agendamento and self.cliente_rua:
            raise ValidationError('Não marque "Cliente Veio Direto da Rua" se houver um agendamento associado.')
        # Garante que se houver agendamento, o cliente_agendamento não seja preenchido manualmente
        if self.agendamento and self.cliente_agendamento:
            raise ValidationError('Não preencha o campo "Cliente (Rua / Sem Agendamento)" se um Agendamento já foi selecionado.')
        # Garante que a loja de comparecimento esteja preenchida
        if not self.loja_comp:
            raise ValidationError('A loja de comparecimento é obrigatória.')

    def save(self, *args, **kwargs):
        # Se associado a um agendamento, preenche cliente_rua = False automaticamente
        if self.agendamento:
            self.cliente_rua = False
            # Se não foi especificada uma loja de comparecimento e existe agendamento,
            # define a loja do agendamento como loja de comparecimento por padrão
            if not self.loja_comp and self.agendamento.loja:
                self.loja_comp = self.agendamento.loja
        # Se não associado a um agendamento e cliente_agendamento preenchido, marca como cliente_rua = True
        elif self.cliente_agendamento:
             self.cliente_rua = True
        
        # Se o status do pagamento for PAGO e data_pagamento não estiver definida, define agora
        if self.status_pagamento == self.StatusPagamentoChoices.PAGO and not self.data_pagamento:
            self.data_pagamento = timezone.now()
        # Se o status for alterado de PAGO para outro, limpa a data_pagamento
        elif self.status_pagamento != self.StatusPagamentoChoices.PAGO:
            self.data_pagamento = None

        self.full_clean() # Executa validações do clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Presença/Resultado em Loja"
        verbose_name_plural = "Presenças/Resultados em Loja"
        ordering = ['-data_presenca']
