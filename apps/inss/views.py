# Importações da biblioteca padrão Python
import json
import re
import json
import traceback
import os
from datetime import *
import calendar
import csv
import io
from django.http import JsonResponse, HttpResponse
from django.shortcuts import *
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Count, F, Max, Q, Sum, DecimalField
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import FieldError
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

# Importações de terceiros
import pytz

# Importações locais
from custom_tags_app.permissions import check_access
from setup.utils import verificar_autenticacao

# Importações de apps
from .forms import *
from .models import *
from apps.funcionarios.models import *
from apps.siape.models import *
import re
from django.views.decorators.csrf import ensure_csrf_cookie


# renderização de paginas


from custom_tags_app.templatetags.permissionsacess import controle_acess

@login_required(login_url='/')
@controle_acess('SCT20')   # 20 – INSS | RANKING LOJAS
def render_ranking(request):
    """
    Renderiza a página de ranking do INSS.
    """
    return render(request, 'inss/ranking.html')


@login_required(login_url='/')
@controle_acess('SCT21')   # 21 – INSS | DASHBOARD INSS
def render_dashboard(request):
    """
    Renderiza a página principal do Dashboard INSS.
    """
    return render(request, 'inss/dashboard.html')


@login_required(login_url='/')
@controle_acess('SCT22')   # 22 – INSS | AGENDAMENTO
def render_agendamento(request):
    """
    Renderiza a página de gerenciamento de agendamentos do INSS.
    """
    return render(request, 'inss/agendamento.html')


@login_required(login_url='/')
@controle_acess('SCT23')   # 23 – INSS | LOJA
def render_loja(request):
    """
    Renderiza a página com a visão da loja/vendas do INSS.
    """
    return render(request, 'inss/loja.html')


@login_required(login_url='/')
@controle_acess('SCT24')   # 24 – INSS | FINANCEIRO
@ensure_csrf_cookie
def render_financeiro(request):
    """
    Renderiza a página de acompanhamento financeiro do INSS.
    """
    return render(request, 'inss/financeiro.html')


@login_required(login_url='/')
@controle_acess('CT6')     #  6 – INSS (Categoria)
def render_inss_forms(request):
    """
    Renderiza a página que centraliza o acesso aos formulários do INSS.
    (Ex: listagem de todos os formulários/agendamentos.)
    """
    return render(request, 'inss/all_forms.html')

# fim renderização de paginas



def format_cpf(cpf):
    """
    Formata o CPF para o padrão 000.000.000-00.
    Remove caracteres não numéricos e, se o CPF tiver 11 dígitos, aplica a formatação.
    """
    if cpf is None:
        return ""
    cpf = re.sub(r'\D', '', cpf)  # Remove todos os caracteres não numéricos
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf

# Função auxiliar para obter a data/hora atual em SP
def get_current_sp_time():
    """
    Retorna a hora atual de SP:
     - se USE_TZ=True, converte now() (UTC-aware) para SP-aware
     - se USE_TZ=False, retorna agora naïve no fuso local do servidor
    """
    now = timezone.now()  # aware se USE_TZ=True, naïve caso contrário
    if settings.USE_TZ:
        # já é aware em UTC, basta converter para SP
        return timezone.localtime(now, SP_TZ)
    # sem fuso, devolve o naïve original
    return now

def make_aware_sp(dt_naive):
    """
    Torna um datetime naïve "aware" em SP, se USE_TZ=True.
    Se USE_TZ=False, retorna o datetime sem modificações.
    """
    if settings.USE_TZ:
        # dt_naive é naïve → atribui fuso São Paulo
        return SP_TZ.localize(dt_naive)
    return dt_naive

def calcular_status_dias(agendamento, hoje, presenca=None):
    """Calcula o status baseado nos dias entre hoje e o agendamento, considerando a presença."""

    # Verifica se já tem presença com tabulação do vendedor
    # (presenca pode ser None se não houver registro PresencaLoja associado)
    tabulacao_venda = getattr(presenca, 'tabulacao_venda', None) if presenca else None

    if tabulacao_venda: # Se vendedor já tabulou na PresencaLoja
        return 'FINALIZADO'

    # Se não finalizado, calcula baseado na data do agendamento
    # Verifica se é um dicionário ou objeto Agendamento
    if isinstance(agendamento, dict):
        dia_agendado_val = agendamento.get('dia_agendado')
    else:
        dia_agendado_val = agendamento.dia_agendado

    # Converte a data do agendamento para date se for string ou datetime
    if isinstance(dia_agendado_val, str):
        try:
            dia_agendado = datetime.strptime(dia_agendado_val, '%Y-%m-%d').date()
        except ValueError:
             # Tenta formato com hora se o primeiro falhar (vindo do DB)
             try:
                 dia_agendado = datetime.strptime(dia_agendado_val, '%Y-%m-%d %H:%M:%S%z').date()
             except (ValueError, TypeError):
                 return 'ERRO_DATA' # Retorna um status indicando erro na data
    elif isinstance(dia_agendado_val, datetime):
        dia_agendado = timezone.localtime(dia_agendado_val).date() # Converte para data local
    elif isinstance(dia_agendado_val, date):
        dia_agendado = dia_agendado_val
    else:
        return 'ERRO_DATA' # Não foi possível determinar a data

    # Calcula a diferença de dias
    try:
        dias_diferenca = (dia_agendado - hoje).days
    except TypeError:
        return 'ERRO_DATA' # Se 'hoje' não for compatível

    # Retorna o status baseado na diferença de dias
    if dias_diferenca > 0:
        return 'FUTURO'
    elif dias_diferenca == 0:
        return 'HOJE'
    else: # dias_diferenca < 0
        return 'ATRASADO'

def format_percentage(value):
    """Formata um valor Decimal ou float como porcentagem com uma casa decimal."""
    if value is None or not isinstance(value, (Decimal, float, int)):
        return "0.0%"
    try:
        return f"{Decimal(value):.1f}%"
    except:
        return "0.0%"

def format_currency(value):
    """Formata um valor Decimal como moeda brasileira (R$)."""
    if value is None or not isinstance(value, Decimal):
        # Tenta converter se for numérico, senão retorna 0
        try:
            value = Decimal(value)
        except:
            value = Decimal('0.0')

    try:
        # Formatação básica para R$
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"
    

def _filter_por_hierarquia(qs, user):
    """
    Filtra o queryset de Agendamento conforme o cargo do usuário:
    - superuser: todos
    - estágio/padrão: apenas próprios
    - coordenador/gerente: própria loja + próprios
    - demais: todos
    """
    if user.is_superuser:
        return qs

    try:
        func = Funcionario.objects.select_related('cargo', 'loja').get(usuario=user)
    except Funcionario.DoesNotExist:
        return Agendamento.objects.none()

    nivel = func.cargo.hierarquia if func.cargo else None
    loja = func.loja

    if nivel in [Cargo.HierarquiaChoices.ESTAGIO, Cargo.HierarquiaChoices.PADRAO]:
        return qs.filter(atendente_agendou=user)
    if nivel in [Cargo.HierarquiaChoices.COORDENADOR, Cargo.HierarquiaChoices.GERENTE]:
        return qs.filter(Q(loja=loja) | Q(atendente_agendou=user))
    return qs  # outros níveis sem filtro adicional


def _serialize_agendamento(a):
    """
    Converte um Agendamento em dict simples para JSON.
    """
    cliente = a.cliente_agendamento
    usuario = a.atendente_agendou

    # tenta pegar nome do funcionário, senão user.username
    try:
        atendente = Funcionario.objects.get(usuario=usuario).nome_completo
    except:
        atendente = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username

    # data do agendamento no formato YYYY-MM-DD
    if settings.USE_TZ:
        dt = timezone.localtime(a.dia_agendado)
    else:
        dt = a.dia_agendado
    dia_str = dt.strftime('%Y-%m-%d') if dt else ''

    return {
        'id': a.id,
        'nome_cliente': cliente.nome_completo if cliente else 'N/A',
        'cliente_agendamento_id': cliente.id if cliente else None,
        'cpf_cliente': getattr(cliente, 'cpf', 'N/A'),
        'numero_cliente': getattr(cliente, 'numero', 'N/A'),
        'dia_agendado': dia_str,
        'atendente_agendou': atendente,
        'loja_agendada': a.loja.nome if a.loja else 'N/A',
        'loja_id': a.loja.id if a.loja else None,
    }


# -------------------------------------------
# INICIO TEMPLATE FINANCEIRO.HTML
# -------------------------------------------

@login_required
@require_GET
@ensure_csrf_cookie
def api_get_historicopagamentos(request):
    try:
        base_query = PresencaLoja.objects.filter(
            valor_tac__isnull=False,
            valor_tac__gt=0,
            data_pagamento__isnull=False,
            status_pagamento=PresencaLoja.StatusPagamentoChoices.PAGO
        )

        try:
            historico_qs = (
                base_query
                .filter(vendedor__isnull=False)
                .select_related(
                    'loja_comp',
                    'vendedor',
                    'agendamento__cliente_agendamento',
                    'cliente_agendamento'
                )
                .order_by('-data_pagamento')
            )
            print(f"Consulta histórico de pagamentos executada com sucesso. "
                  f"Registros pagos encontrados: {historico_qs.count()}")
        except FieldError as fe:
            print(f"Erro de campo no filtro: {fe}")
            return JsonResponse({
                'error': 'Erro na configuração do filtro. Verifique os modelos relacionados ao vendedor.',
                'details': str(fe)
            }, status=500)

        data_list = []
        for pl in historico_qs:
            # Determina dados do cliente
            if pl.agendamento and pl.agendamento.cliente_agendamento:
                cli = pl.agendamento.cliente_agendamento
            else:
                cli = pl.cliente_agendamento
            data_list.append({
                'id': pl.id,
                'cliente_nome': getattr(cli, 'nome_completo', 'N/A'),
                'cliente_cpf': getattr(cli, 'cpf', 'N/A'),
                'loja_nome': pl.loja_comp.nome if pl.loja_comp else 'N/A',
                'data_pagamento': pl.data_pagamento.strftime('%d/%m/%Y') if pl.data_pagamento else '-',
                'valor_tac': format_currency(pl.valor_tac),
                'status_pagamento': pl.get_status_pagamento_display(),
            })

        return JsonResponse({'historico': data_list})

    except Exception as e:
        print(f"Erro inesperado em api_get_historicopagamentos: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': 'Ocorreu um erro interno ao processar a solicitação.',
            'details': str(e)
        }, status=500)


@login_required
@require_GET
@ensure_csrf_cookie
def api_get_cardsfinanceiro(request):
    try:
        hoje = timezone.now().date()
        print(f"Iniciando api_get_cardsfinanceiro. Data atual: {hoje}")

        # --- Período Ano Atual ---
        inicio_ano = hoje.replace(month=1, day=1)
        fim_ano    = hoje.replace(month=12, day=31)
        dt1 = datetime.combine(inicio_ano, time.min)
        dt2 = datetime.combine(fim_ano,    time.max)
        if settings.USE_TZ:
            start_dt_ano = timezone.make_aware(dt1)
            end_dt_ano   = timezone.make_aware(dt2)
        else:
            start_dt_ano = dt1
            end_dt_ano   = dt2
        print(f"Período ano: {start_dt_ano} a {end_dt_ano}")

        # --- Período Mês Atual ---
        inicio_mes = hoje.replace(day=1)
        try:
            proximo_mes = inicio_mes.replace(month=inicio_mes.month + 1)
        except ValueError:
            proximo_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
        fim_mes = proximo_mes - timedelta(days=1)

        dt3 = datetime.combine(inicio_mes, time.min)
        dt4 = datetime.combine(fim_mes,    time.max)
        if settings.USE_TZ:
            start_dt_mes = timezone.make_aware(dt3)
            end_dt_mes   = timezone.make_aware(dt4)
        else:
            start_dt_mes = dt3
            end_dt_mes   = dt4
        print(f"Período mês: {start_dt_mes} a {end_dt_mes}")

        # --- Consultas e Agregações ---
        base_tac_query = PresencaLoja.objects.filter(
            valor_tac__isnull=False,
            valor_tac__gt=0
        )
        print(f"Quantidade de TACs válidos no sistema: {base_tac_query.count()}")

        agregados_ano = base_tac_query.filter(
            data_presenca__gte=start_dt_ano,
            data_presenca__lte=end_dt_ano
        ).aggregate(
            total_pago_ano=Sum(
                'valor_tac',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.PAGO),
                output_field=DecimalField()
            ),
            total_pendente_ano=Sum(
                'valor_tac',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.EM_ESPERA),
                output_field=DecimalField()
            ),
            qtd_pago_ano=Count(
                'id',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.PAGO)
            )
        )
        print(f"Agregados ano: {agregados_ano}")

        agregados_mes = base_tac_query.filter(
            data_presenca__gte=start_dt_mes,
            data_presenca__lte=end_dt_mes
        ).aggregate(
            total_pago_mes=Sum(
                'valor_tac',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.PAGO),
                output_field=DecimalField()
            ),
            total_pendente_mes=Sum(
                'valor_tac',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.EM_ESPERA),
                output_field=DecimalField()
            ),
            qtd_pago_mes=Count(
                'id',
                filter=Q(status_pagamento=PresencaLoja.StatusPagamentoChoices.PAGO)
            )
        )
        print(f"Agregados mês: {agregados_mes}")

        total_tc_ano           = agregados_ano.get('total_pago_ano') or Decimal('0.0')
        total_tc_ano_pendente  = agregados_ano.get('total_pendente_ano') or Decimal('0.0')
        qtd_tc_ano             = agregados_ano.get('qtd_pago_ano') or 0

        total_tc_mes           = agregados_mes.get('total_pago_mes') or Decimal('0.0')
        total_tc_mes_pendente  = agregados_mes.get('total_pendente_mes') or Decimal('0.0')
        qtd_tc_mes             = agregados_mes.get('qtd_pago_mes') or 0

        data = {
            'totalTCAno':            format_currency(total_tc_ano),
            'totalTCAnoPendente':    format_currency(total_tc_ano_pendente),
            'totalTCMes':            format_currency(total_tc_mes),
            'totalTCMesPendente':    format_currency(total_tc_mes_pendente),
            'qtdTCAno':              qtd_tc_ano,
            'qtdTCMes':              qtd_tc_mes,
        }
        print(f"Dados formatados para retorno: {data}")

        return JsonResponse(data)

    except Exception as e:
        print(f"Erro em api_get_cardsfinanceiro: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro interno ao calcular dados financeiros: {str(e)}'
        }, status=500)

# -------------------------------------------
# FIM TEMPLATE FINANCEIRO.HTML
# -------------------------------------------

@login_required
@require_GET
@ensure_csrf_cookie
def api_get_tac(request):
    """
    API para buscar presenças em loja com valor TAC pendente.
    
    Retorna um JSON com todas as presenças que possuem valor_tac diferente de vazio ou 0,
    e com status de pagamento 'EM ESPERA'.
    
    Retorna para cada presença:
    - id: ID da presença
    - nome_cliente: Nome do cliente
    - cpf_cliente: CPF do cliente
    - loja: Nome da loja onde ocorreu o atendimento
    - data: Data do atendimento
    - valor_tac: Valor do TAC formatado como moeda
    """
    try:
        # Filtra presenças com valor_tac preenchido e diferente de zero, com status 'EM ESPERA'
        presencas = PresencaLoja.objects.filter(
            valor_tac__isnull=False,
            valor_tac__gt=0,
            status_pagamento=PresencaLoja.StatusPagamentoChoices.EM_ESPERA
        ).select_related(
            'agendamento__cliente_agendamento',
            'cliente_agendamento',
            'loja_comp',
            'vendedor'
        )
        
        # Prepara os dados para retorno
        presencas_data = []
        
        for presenca in presencas:
            # Determina o cliente (pode vir do agendamento ou diretamente da presença)
            cliente_obj = None
            if presenca.agendamento and presenca.agendamento.cliente_agendamento:
                cliente_obj = presenca.agendamento.cliente_agendamento
            elif presenca.cliente_agendamento:
                cliente_obj = presenca.cliente_agendamento
                
            # Só adiciona se tiver cliente identificado
            if cliente_obj:
                presencas_data.append({
                    'id': presenca.id,
                    'nome_cliente': cliente_obj.nome_completo,
                    'cpf_cliente': cliente_obj.cpf,
                    'loja': presenca.loja_comp.nome if presenca.loja_comp else 'N/A',
                    'data': presenca.data_presenca.strftime('%d/%m/%Y %H:%M'),
                    'valor_tac': format_currency(presenca.valor_tac)
                })
        
        return JsonResponse({
            'success': True,
            'presencas': presencas_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erro ao buscar TACs pendentes: {str(e)}'
        }, status=500)

@login_required
@require_POST
@csrf_exempt # << TEMPORÁRIO PARA DIAGNÓSTICO
def api_post_tac(request):
    """
    API para registrar um TAC no sistema financeiro (RegisterMoney).

    Recebe o ID da presença em loja (PresencaLoja) e cria um novo RegisterMoney
    no app SIAPE utilizando os dados do cliente, loja, valor TAC da presença,
    e as informações organizacionais (empresa, departamento, setor, equipe)
    do funcionário associado ao vendedor no momento do registro.

    Parâmetros esperados no corpo da requisição POST:
    - presenca_id: ID da PresencaLoja

    Retorna:
    - success: True/False
    - message: Mensagem de sucesso ou erro
    - register_money_id: ID do registro financeiro criado (em caso de sucesso)
    """
    try:
        # Obtém o ID da presença do corpo da requisição POST
        presenca_id = request.POST.get('presenca_id')

        if not presenca_id:
            return JsonResponse({
                'success': False,
                'message': 'ID da presença não fornecido.'
            }, status=400)

        # Busca a presença pelo ID, otimizando com select_related
        try:
            presenca = PresencaLoja.objects.select_related(
                'agendamento__cliente_agendamento',
                'cliente_agendamento',
                'loja_comp',
                'vendedor' # Garante que o User vendedor seja carregado
            ).get(id=presenca_id)
        except PresencaLoja.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Presença com ID {presenca_id} não encontrada.'
            }, status=404)
        except ValueError: # Caso presenca_id não seja um número válido
             return JsonResponse({
                'success': False,
                'message': 'ID da presença inválido.'
            }, status=400)

        # Verifica se a presença tem valor_tac válido
        if not presenca.valor_tac or presenca.valor_tac <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Presença não possui valor TAC válido para registro.'
            }, status=400)

        # Verifica se o status já é PAGO para evitar duplicidade
        if presenca.status_pagamento == PresencaLoja.StatusPagamentoChoices.PAGO:
             return JsonResponse({
                'success': False,
                'message': 'Este TAC já foi registrado anteriormente.'
            }, status=409) # Conflict

        # Determina o cliente (pode vir do agendamento ou diretamente da presença)
        cliente_obj = None
        if presenca.agendamento and presenca.agendamento.cliente_agendamento:
            cliente_obj = presenca.agendamento.cliente_agendamento
        elif presenca.cliente_agendamento:
            cliente_obj = presenca.cliente_agendamento

        if not cliente_obj:
            return JsonResponse({
                'success': False,
                'message': 'Cliente não identificado na presença.'
            }, status=400)

        # Verifica se há um vendedor associado à presença
        if not presenca.vendedor:
             return JsonResponse({
                'success': False,
                'message': 'Vendedor não associado a esta presença.'
            }, status=400)

        # Importa os modelos necessários
        from apps.siape.models import RegisterMoney
        from apps.funcionarios.models import Funcionario

        # Busca o Funcionario associado ao User vendedor para obter dados organizacionais
        funcionario = None
        try:
            # Otimiza buscando os campos relacionados necessários
            funcionario = Funcionario.objects.select_related(
                'empresa', 'departamento', 'setor', 'equipe'
            ).get(usuario=presenca.vendedor)
        except Funcionario.DoesNotExist:
            # Se não encontrar o funcionário, os campos organizacionais ficarão nulos
            # Pode ser útil logar um aviso aqui, dependendo da regra de negócio
            # logger.warning(f"Funcionário não encontrado para o usuário {presenca.vendedor.id} ao registrar TAC da presença {presenca.id}")
            pass # Continua a execução, os campos serão None

        # Prepara os dados para criar o RegisterMoney
        register_data = {
            'user': presenca.vendedor,
            'loja': presenca.loja_comp,
            'cpf_cliente': cliente_obj.cpf,
            'valor_est': presenca.valor_tac,
            'status': True,  # Status ativo por padrão
            'data': timezone.now(), # Data/Hora do registro financeiro
            # Associa os dados organizacionais do funcionário no momento do registro
            'empresa': funcionario.empresa if funcionario else None,
            'departamento': funcionario.departamento if funcionario else None,
            'setor': funcionario.setor if funcionario else None,
            'equipe': funcionario.equipe if funcionario else None,
        }

        # Cria o novo registro no RegisterMoney
        # Idealmente, envolver a criação e a atualização da presença em uma transação
        # from django.db import transaction
        # with transaction.atomic():
        register_money = RegisterMoney.objects.create(**register_data)

        # Atualiza o status da presença para PAGO e define a data de pagamento
        presenca.status_pagamento = PresencaLoja.StatusPagamentoChoices.PAGO
        presenca.data_pagamento = timezone.now().date() # Grava apenas a data do pagamento
        presenca.save(update_fields=['status_pagamento', 'data_pagamento']) # Otimiza o save

        return JsonResponse({
            'success': True,
            'message': 'TAC registrado com sucesso no sistema financeiro.',
            'register_money_id': register_money.id
        })

    except Exception as e:
        # Logar o erro seria importante em produção
        # logger.error(f"Erro inesperado em api_post_tac para presenca_id {request.POST.get('presenca_id')}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Erro interno ao registrar TAC: {str(e)}'
        }, status=500)

@login_required
@require_POST
@csrf_exempt # << TEMPORÁRIO PARA DIAGNÓSTICO
@ensure_csrf_cookie
def api_post_attvalortac(request):
    """
    API para atualizar o valor TAC de uma presença em loja.
    
    Recebe:
    - id: ID da PresencaLoja
    - valor_tac: Novo valor TAC
    
    Retorna:
    - success: True/False
    - valor_antigo: Valor TAC anterior
    - valor_novo: Novo valor TAC
    - message: Mensagem de sucesso ou erro
    """
    try:
        # Obtém os parâmetros da requisição
        presenca_id = request.POST.get('id')
        novo_valor_tac = request.POST.get('valor_tac')
        
        # Validação básica
        if not presenca_id or not novo_valor_tac:
            return JsonResponse({
                'success': False,
                'message': 'Parâmetros incompletos. ID e valor_tac são obrigatórios.'
            }, status=400)
            
        # Converte o valor para decimal
        try:
            novo_valor_tac = Decimal(novo_valor_tac)
        except:
            return JsonResponse({
                'success': False,
                'message': 'Valor TAC inválido. Informe um valor numérico.'
            }, status=400)
            
        # Busca a presença pelo ID
        try:
            presenca = PresencaLoja.objects.get(id=presenca_id)
        except PresencaLoja.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Presença com ID {presenca_id} não encontrada.'
            }, status=404)
            
        # Armazena o valor antigo para retornar na resposta
        valor_antigo = presenca.valor_tac
        
        # Atualiza o valor TAC
        presenca.valor_tac = novo_valor_tac
        presenca.save()
        
        # Retorna resposta de sucesso
        return JsonResponse({
            'success': True,
            'message': 'Valor TAC atualizado com sucesso',
            'valor_antigo': float(valor_antigo) if valor_antigo else 0,
            'valor_novo': float(novo_valor_tac)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao atualizar valor TAC: {str(e)}'
        }, status=500)


# -------------------------------------------
# FIM TEMPLATE FINANCEIRO.HTML
# Funções relacionadas à página financeira (financeiro.html)
# -------------------------------------------

# -------------------------------------------
# INICIO TEMPLATE LOJA.HTML
# Funções relacionadas à página de lojas (loja.html)
# -------------------------------------------

def _local(dt):
    """Garante que dt seja aware antes de chamar localtime."""
    if not dt:
        return None
    if settings.USE_TZ:
        # torna aware se for naive
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_default_timezone())
        return timezone.localtime(dt)
    return dt

@login_required
@require_GET
@ensure_csrf_cookie
@controle_acess('SCT23')
def api_get_agendadosHoje(request):
    print(f"[DEBUG] Iniciando api_get_agendadosHoje para usuário: {request.user}")
    
    user  = request.user
    hoje  = _local(timezone.now()).date()
    print(f"[DEBUG] Data de hoje: {hoje}")

    # 1️⃣ Base: agendamentos de hoje sem presença
    base_qs = Agendamento.objects.filter(
        dia_agendado__date=hoje,
        presencas__isnull=True
    ).select_related('cliente_agendamento', 'loja', 'atendente_agendou')
    print(f"[DEBUG] Total de agendamentos base: {base_qs.count()}")

    # 2️⃣ Se for superuser, libera tudo
    if user.is_superuser:
        qs = base_qs
        print("[DEBUG] Acesso total - superuser")
    else:
        # 3️⃣ Perfil do funcionário
        func = Funcionario.objects.filter(
            usuario=user, status=True
        ).select_related('cargo', 'loja').first()
        if not func or not func.loja:
            print("[DEBUG] Funcionário não encontrado ou sem loja")
            return JsonResponse({'agendamentos': [], 'message': 'Sem permissão'}, status=200)

        hier = func.cargo.hierarquia if func.cargo else Cargo.HierarquiaChoices.PADRAO
        print(f"[DEBUG] Hierarquia do usuário: {hier}")

        # 4️⃣ Filtro de acesso por hierarquia
        if hier == Cargo.HierarquiaChoices.SUPERVISOR_GERAL:
            qs = base_qs
            print("[DEBUG] Acesso total - supervisor(a) geral")
        elif hier >= Cargo.HierarquiaChoices.GERENTE:
            qs = base_qs.exclude(loja__is_franquia=True)
            print("[DEBUG] Filtro gerente - excluindo franquias")
        else:
            qs = base_qs.filter(loja=func.loja)
            print(f"[DEBUG] Filtro loja específica: {func.loja}")

    # 5️⃣ Filtros opcionais por querystring
    nome = request.GET.get('nomeCliente','').strip()
    cpf  = ''.join(c for c in request.GET.get('cpfCliente','') if c.isdigit())
    aten = request.GET.get('atendente','').strip()
    
    print(f"[DEBUG] Filtros recebidos - Nome: {nome}, CPF: {cpf}, Atendente: {aten}")
    
    if nome:
        qs = qs.filter(cliente_agendamento__nome_completo__icontains=nome)
        print(f"[DEBUG] Aplicando filtro por nome: {nome}")
    if cpf:
        qs = qs.filter(cliente_agendamento__cpf__icontains=cpf)
        print(f"[DEBUG] Aplicando filtro por CPF: {cpf}")
    if aten:
        qs = qs.filter(
            Q(atendente_agendou__first_name__icontains=aten) |
            Q(atendente_agendou__last_name__icontains=aten)   |
            Q(atendente_agendou__username__icontains=aten)
        )
        print(f"[DEBUG] Aplicando filtro por atendente: {aten}")

    # 6️⃣ Monta resultado
    resultado = []
    for a in qs:
        dt = _local(a.dia_agendado)
        data_hora = dt.strftime('%d/%m/%Y %H:%M') if dt else ''
        usr = a.atendente_agendou
        nome_at = (usr.get_full_name() or usr.username) if usr else ''
        resultado.append({
            'id_agendamento': a.id,
            'nome':           a.cliente_agendamento.nome_completo,
            'cpf':            a.cliente_agendamento.cpf,
            'numero':         a.cliente_agendamento.numero,
            'dia_agendado':   data_hora,
            'atendente':      nome_at,
            'status':         'Aguardando',
            'loja':           a.loja.nome if a.loja else 'Sem loja'
        })

    print(f"[DEBUG] Total de agendamentos retornados: {len(resultado)}")
    return JsonResponse({'agendamentos': resultado, 'total': len(resultado)}, status=200)



@login_required
@require_GET
@ensure_csrf_cookie
@controle_acess('SCT23')
def api_get_agendPendentes(request):
    user = request.user
    hoje = _local(timezone.now()).date()

    # 1️⃣ Base: apenas pendentes (não 'CONFIRMADO') a partir de hoje
    base_qs = (
        Agendamento.objects
        .exclude(tabulacao_agendamento='CONFIRMADO')
        .filter(dia_agendado__date__gte=hoje)
        .select_related('cliente_agendamento', 'loja', 'atendente_agendou')
    )

    # 2️⃣ Acesso irrestrito para superuser
    if user.is_superuser:
        qs = base_qs
    else:
        # 3️⃣ Perfil do funcionário
        func = (
            Funcionario.objects
            .filter(usuario=user, status=True)
            .select_related('cargo', 'loja')
            .first()
        )
        if not func or not func.loja:
            return JsonResponse({'agendamentos': [], 'message': 'Sem permissão'}, status=200)

        hier = func.cargo.hierarquia if func.cargo else Cargo.HierarquiaChoices.PADRAO

        # 4️⃣ Supervisor(a) Geral sem filtro
        if hier == Cargo.HierarquiaChoices.SUPERVISOR_GERAL:
            qs = base_qs
        # 5️⃣ Gerentes e acima (exceto superuser) veem todas as não-franquias
        elif hier >= Cargo.HierarquiaChoices.GERENTE:
            qs = base_qs.exclude(loja__is_franquia=True)
        # 6️⃣ Demais veem apenas a própria loja
        else:
            qs = base_qs.filter(loja=func.loja)

    # 7️⃣ Filtros opcionais via querystring
    nome = request.GET.get('nomeCliente', '').strip()
    cpf  = ''.join(c for c in request.GET.get('cpfCliente', '') if c.isdigit())
    aten = request.GET.get('atendente', '').strip()
    stat = request.GET.get('status', '').strip()

    if nome:
        qs = qs.filter(cliente_agendamento__nome_completo__icontains=nome)
    if cpf:
        qs = qs.filter(cliente_agendamento__cpf__icontains=cpf)
    if aten:
        qs = qs.filter(
            Q(atendente_agendou__first_name__icontains=aten) |
            Q(atendente_agendou__last_name__icontains=aten)   |
            Q(atendente_agendou__username__icontains=aten)
        )
    if stat:
        qs = qs.filter(tabulacao_agendamento__icontains=stat)

    # 8️⃣ Monta array de resultado
    resultado = []
    for a in qs:
        dt = _local(a.dia_agendado)
        dia = dt.strftime('%Y-%m-%d') if dt else ''
        usr = a.atendente_agendou
        nome_at = (usr.get_full_name() or usr.username) if usr else ''
        resultado.append({
            'agendamento_id':             a.id,
            'cliente_agendamento_nome':   a.cliente_agendamento.nome_completo,
            'cliente_agendamento_cpf':    a.cliente_agendamento.cpf,
            'cliente_agendamento_numero': a.cliente_agendamento.numero,
            'agendamento_dia':            dia,
            'agendamento_atendente_nome': nome_at,
            'agendamento_tabulacao':      a.tabulacao_agendamento or '',
            'agendamento_loja_id':        a.loja.id if a.loja else None,
            'agendamento_loja_nome':      a.loja.nome if a.loja else 'Sem loja',
            'tem_presenca':               hasattr(a, 'presenca'),
        })

    return JsonResponse({'agendamentos': resultado, 'total': len(resultado)}, status=200)

@login_required
@require_GET
@ensure_csrf_cookie
@controle_acess('SCT23')
def api_get_clientesAtrasadoLoja(request):
    """
    Lista clientes com dia_agendado < hoje, tabulacao != 'CONFIRMADO'
    e sem PresencaLoja registrada.
    Superuser e Supervisor(a) Geral veem todos sem filtro de loja.
    """
    print(f"[DEBUG] Iniciando api_get_clientesAtrasadoLoja. User: {request.user}")
    user = request.user
    hoje = _local(timezone.now()).date()
    print(f"[DEBUG] Data de hoje: {hoje}")

    # base: agendamentos passados não confirmados e sem presença
    base_qs = (
        Agendamento.objects
        .filter(dia_agendado__date__lt=hoje)
        .exclude(tabulacao_agendamento='CONFIRMADO')
        .filter(presencas__isnull=True)
        .select_related('cliente_agendamento', 'loja', 'atendente_agendou')
    )
    print(f"[DEBUG] Total de agendamentos base: {base_qs.count()}")

    # 1️⃣ Se for superuser, acesso total
    if user.is_superuser:
        qs = base_qs
        print("[DEBUG] Superuser – acesso total")
    else:
        # 2️⃣ Busca perfil do funcionário
        func = (
            Funcionario.objects
            .filter(usuario=user, status=True)
            .select_related('cargo', 'loja')
            .first()
        )
        if not func:
            print("[DEBUG] Sem perfil de funcionário")
            return JsonResponse({'agendamentos': [], 'message': 'Sem permissão'}, status=200)

        hier = func.cargo.hierarquia if func.cargo else Cargo.HierarquiaChoices.PADRAO
        print(f"[DEBUG] Hierarquia do usuário: {hier}")

        # 3️⃣ Supervisor(a) Geral sem filtro de loja
        if hier == Cargo.HierarquiaChoices.SUPERVISOR_GERAL:
            qs = base_qs
            print("[DEBUG] Supervisor(a) Geral – acesso total")
        # 4️⃣ Gerentes veem todas as lojas, exceto franquias
        elif hier >= Cargo.HierarquiaChoices.GERENTE:
            qs = base_qs.exclude(loja__is_franquia=True)
            print("[DEBUG] Gerente – excluindo franquias")
        # 5️⃣ Demais: apenas a própria loja
        else:
            if not func.loja:
                print("[DEBUG] Funcionário sem loja associada")
                return JsonResponse({'agendamentos': [], 'message': 'Sem permissão'}, status=200)
            qs = base_qs.filter(loja=func.loja)
            print(f"[DEBUG] Filtrando pela loja: {func.loja.nome}")

    # 6️⃣ Filtros opcionais
    nome = request.GET.get('nomeCliente', '').strip()
    cpf  = ''.join(c for c in request.GET.get('cpfCliente', '') if c.isdigit())
    aten = request.GET.get('atendente', '').strip()
    stat = request.GET.get('status', '').strip()
    print(f"[DEBUG] Filtros recebidos – Nome: {nome}, CPF: {cpf}, Atendente: {aten}, Status: {stat}")

    if nome:
        qs = qs.filter(cliente_agendamento__nome_completo__icontains=nome)
        print(f"[DEBUG] Aplicando filtro por nome: {nome}")
    if cpf:
        qs = qs.filter(cliente_agendamento__cpf__icontains=cpf)
        print(f"[DEBUG] Aplicando filtro por CPF: {cpf}")
    if aten:
        qs = qs.filter(
            Q(atendente_agendou__first_name__icontains=aten) |
            Q(atendente_agendou__last_name__icontains=aten)   |
            Q(atendente_agendou__username__icontains=aten)
        )
        print(f"[DEBUG] Aplicando filtro por atendente: {aten}")
    if stat:
        qs = qs.filter(tabulacao_agendamento__icontains=stat)
        print(f"[DEBUG] Aplicando filtro por status: {stat}")

    print(f"[DEBUG] Total após filtros: {qs.count()}")

    # 7️⃣ Monta resultado
    resultado = []
    for a in qs.order_by('dia_agendado'):
        dt = _local(a.dia_agendado)
        data_hora = dt.strftime('%d/%m/%Y %H:%M') if dt else ''
        usr = a.atendente_agendou
        nome_at = (usr.get_full_name() or usr.username) if usr else ''
        resultado.append({
            'id_agendamento': a.id,
            'nome':            a.cliente_agendamento.nome_completo,
            'cpf':             a.cliente_agendamento.cpf,
            'numero':          a.cliente_agendamento.numero,
            'dia_agendado':    data_hora,
            'atendente':       nome_at,
            'status':          a.tabulacao_agendamento,
            'loja':            a.loja.nome if a.loja else 'Sem loja'
        })

    print(f"[DEBUG] Total de resultados encontrados: {len(resultado)}")
    return JsonResponse({'agendamentos': resultado, 'total': len(resultado)}, status=200)

@login_required
@require_GET
@ensure_csrf_cookie
def api_get_infocliente(request):
    ag_id = request.GET.get('agendamento_id')
    if not ag_id:
        return JsonResponse({'error': 'ID não fornecido'}, status=400)
    a = Agendamento.objects.select_related('cliente_agendamento', 'loja', 'atendente_agendou') \
        .filter(id=ag_id).first()
    if not a:
        return JsonResponse({'error': 'Agendamento não encontrado'}, status=404)

    dt_cr = _local(a.data_criacao)
    dt_ag = _local(a.dia_agendado)
    data_fmt = dt_ag.strftime('%d/%m/%Y') if dt_ag else ''
    hora_fmt = dt_ag.strftime('%H:%M') if dt_ag else ''

    usr = a.atendente_agendou
    nome_at = (usr.get_full_name() or usr.username) if usr else ''
    # busca cargo
    cargo_at = Funcionario.objects.filter(usuario=usr, status=True).select_related('cargo') \
        .first()
    cargo_nome = cargo_at.cargo.nome if cargo_at and cargo_at.cargo else None

    tem = hasattr(a, 'presenca')
    resposta = {
        'agendamento': {
            'id': a.id,
            'data_criacao': dt_cr.strftime('%d/%m/%Y %H:%M') if dt_cr else '',
            'dia_agendado': data_fmt,
            'hora_agendada': hora_fmt,
            'tabulacao': a.tabulacao_agendamento or '',
            'tem_presenca': tem
        },
        'cliente': {
            'id': a.cliente_agendamento.id,
            'nome_completo': a.cliente_agendamento.nome_completo,
            'cpf': a.cliente_agendamento.cpf,
            'numero_contato': a.cliente_agendamento.numero,
            'possui_whatsapp': a.cliente_agendamento.flg_whatsapp,
            'status': a.cliente_agendamento.status
        },
        'loja': {
            'id': a.loja.id if a.loja else None,
            'nome': a.loja.nome if a.loja else 'Sem loja'
        },
        'atendente': {
            'id': usr.id if usr else None,
            'nome': nome_at,
            'cargo': cargo_nome
        }
    }
    return JsonResponse(resposta, status=200)


@login_required
@require_POST
def api_post_novavenda(request):
    import logging
    logger = logging.getLogger(__name__)

    # 1️⃣ Extrai campos do POST
    nome      = request.POST.get('nome_cliente', '').strip()
    cpf       = request.POST.get('cpf_cliente', '').strip().replace('.', '').replace('-', '')
    num       = request.POST.get('numero_cliente', '').strip()
    dt_s      = request.POST.get('data_comparecimento', '')
    loja_id   = request.POST.get('loja', '')
    vend_id   = request.POST.get('vendedor_id', '')
    tab_v_raw = request.POST.get('tabulacao_vendedor', '').strip()

    # 2️⃣ Mapeamento das tabulações para as chaves válidas em TextChoices
    TAB_MAP = {
        'NEGÓCIO FECHADO':  'NEGOCIO_FECHADO',
        'FECHOU NEGÓCIO':   'NEGOCIO_FECHADO',
        'FECHOU NEGOCIO':   'NEGOCIO_FECHADO',
        'INELEGÍVEL':       'INELEGIVEL',
        'NAO ACEITOU':      'NAO_ACEITOU',
        'NÃO ACEITOU':      'NAO_ACEITOU',
        'NAO QUIS OUVIR':   'NAO_QUIS_OUVIR',
        'NÃO QUIS OUVIR':   'NAO_QUIS_OUVIR',
        'PENDENTE':         'PENDENTE',
    }
    tab_v = TAB_MAP.get(tab_v_raw.upper(), tab_v_raw.upper())

    # 3️⃣ Validações básicas
    if not all([nome, cpf, num, dt_s, loja_id, vend_id, tab_v]):
        return JsonResponse({'status':'error','message':'Campos obrigatórios faltando'}, status=400)

    try:
        dt_naive = timezone.datetime.strptime(dt_s, '%Y-%m-%d')
        dt_cmp = timezone.make_aware(dt_naive) if settings.USE_TZ else dt_naive
    except ValueError:
        return JsonResponse({'status':'error','message':'Data inválida'}, status=400)

    # 4️⃣ Cria ou atualiza ClienteAgendamento
    cliente, created = ClienteAgendamento.objects.get_or_create(
        cpf=cpf,
        defaults={
            'nome_completo': nome.upper(),
            'numero': num,
            'flg_whatsapp': True,
            'status': True
        }
    )
    if not created:
        cliente.nome_completo = nome.upper()
        cliente.numero = num
        cliente.save()

    # 5️⃣ Busca loja e vendedor
    try:
        loja = Loja.objects.get(id=loja_id)
        vend = User.objects.get(id=vend_id)
    except (Loja.DoesNotExist, User.DoesNotExist):
        return JsonResponse({'status':'error','message':'Loja ou vendedor não encontrado'}, status=400)

    # 6️⃣ Processa produtos, se for NEGÓCIO_FECHADO
    produtos_json = request.POST.get('produtos_json') or request.POST.get('produtos','{}')
    produtos = []
    valor_total = Decimal('0')
    if tab_v == 'NEGOCIO_FECHADO':
        try:
            parsed = json.loads(produtos_json)
            # converte lista em dict de índices
            produtos = {str(i): p for i, p in enumerate(parsed)} if isinstance(parsed, list) else parsed
        except json.JSONDecodeError:
            return JsonResponse({'status':'error','message':'Produtos inválidos'}, status=400)
        if not produtos:
            return JsonResponse({'status':'error','message':'Pelo menos um produto é obrigatório'}, status=400)

    # 7️⃣ Cria as PresencaLoja
    pres_ids = []
    if produtos:
        for info in produtos.values():
            sub   = str(info.get('subsidio')).lower() in ['true', '1', 'sim']
            acao  = str(info.get('acao')).lower()     in ['true', '1', 'sim']
            asso  = str(info.get('associacao')).lower() in ['true', '1', 'sim']
            aum   = str(info.get('aumento')).lower()  in ['true', '1', 'sim']
            vt    = info.get('valor_tac','0').replace('R$','').replace('.','').replace(',','.')
            try:
                vt_dec = Decimal(vt)
            except:
                vt_dec = Decimal('0')
            valor_total += vt_dec

            tipo = info.get('tipo_negociacao','').upper()
            pid  = info.get('produto_id')
            if pid:
                try:
                    prod = Produto.objects.get(id=pid)
                    tipo = prod.nome.upper()
                except Produto.DoesNotExist:
                    pass

            p = PresencaLoja.objects.create(
                cliente_agendamento=cliente,
                loja_comp=loja,
                vendedor=vend,
                tabulacao_venda=tab_v,
                tipo_negociacao=tipo,
                banco=info.get('banco','').upper(),
                subsidio=sub,
                valor_tac=vt_dec,
                acao=acao,
                associacao=asso,
                aumento=aum,
                status_pagamento=PresencaLoja.StatusPagamentoChoices.EM_ESPERA,
                cliente_rua=True,
                data_presenca=dt_cmp
            )
            pres_ids.append(p.id)

    else:
        # sem produto
        p = PresencaLoja.objects.create(
            cliente_agendamento=cliente,
            loja_comp=loja,
            vendedor=vend,
            tabulacao_venda=tab_v,
            cliente_rua=True,
            data_presenca=dt_cmp
        )
        pres_ids.append(p.id)

    # 8️⃣ Monta resposta
    resp = {
        'status': 'success',
        'message': f'Cliente {cliente.nome_completo} registrado',
        'cliente_id': cliente.id,
        'presencas_ids': pres_ids
    }
    if valor_total > 0:
        resp['valor_total_tac'] = f'R$ {valor_total:.2f}'.replace('.', ',')

    return JsonResponse(resp, status=201)

@login_required
@require_POST
def api_post_addvenda(request):
    ag_id   = request.POST.get('agendamento_id','').strip()
    vend_id = request.POST.get('vendedor_id','').strip()
    raw_tab = request.POST.get('tabulacao_vendedor','').strip()
    loja_id = request.POST.get('loja_id','').strip()

    # 1️⃣ Campos obrigatórios
    if not all([ag_id, vend_id, raw_tab]):
        return JsonResponse({'status':'error','message':'Campos obrigatórios faltando'}, status=400)

    # 2️⃣ Normaliza tabulação
    TAB_MAP = {
        'NEGÓCIO FECHADO':  PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO,
        'FECHOU NEGOCIO':   PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO,
        'INELEGÍVEL':       PresencaLoja.TabulacaoVendaChoices.INELEGIVEL,
        'INELEGIVEL':       PresencaLoja.TabulacaoVendaChoices.INELEGIVEL,
        'NÃO ACEITOU':      PresencaLoja.TabulacaoVendaChoices.NAO_ACEITOU,
        'NAO ACEITOU':      PresencaLoja.TabulacaoVendaChoices.NAO_ACEITOU,
        'NÃO QUIS OUVIR':   PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR,
        'NAO QUIS OUVIR':   PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR,
        'PENDENTE':         PresencaLoja.TabulacaoVendaChoices.PENDENTE,
    }
    tab_v = TAB_MAP.get(raw_tab, raw_tab.replace(' ', '_').upper())
    if tab_v not in PresencaLoja.TabulacaoVendaChoices.values:
        return JsonResponse({
            'status':'error','message':f"Tabulação inválida: '{raw_tab}'."
        }, status=400)

    # 3️⃣ Carrega agendamento
    try:
        ag = Agendamento.objects.get(id=ag_id)
    except Agendamento.DoesNotExist:
        return JsonResponse({'status':'error','message':'Agendamento não encontrado'}, status=404)

    # Carrega vendedor
    try:
        vend = User.objects.get(id=vend_id)
    except User.DoesNotExist:
        return JsonResponse({'status':'error','message':'Vendedor não encontrado'}, status=404)

    # Carrega loja (ou usa a do agendamento)
    if loja_id:
        try:
            loja = Loja.objects.get(id=loja_id)
        except Loja.DoesNotExist:
            return JsonResponse({'status':'error','message':'Loja não encontrada'}, status=404)
    else:
        loja = ag.loja

    pres_ids = []

    # 4️⃣ NEGÓCIO FECHADO → itera sobre produtos JSON
    if tab_v == PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO:
        raw = request.POST.get('produtos_json','[]')
        try:
            produtos = json.loads(raw)
        except json.JSONDecodeError:
            return JsonResponse({'status':'error','message':'JSON de produtos inválido'}, status=400)

        if not isinstance(produtos, list) or not produtos:
            return JsonResponse({
                'status':'error',
                'message':'Ao menos um produto é obrigatório para NEGÓCIO FECHADO'
            }, status=400)

        total_tac = Decimal('0')
        for info in produtos:
            # parsing...
            vt_str = info.get('valor_tac','0').replace('R$','').replace('.','').replace(',','.')
            try: vt_dec = Decimal(vt_str)
            except: vt_dec = Decimal('0')
            total_tac += vt_dec

            # monta PresencaLoja
            p = PresencaLoja(
                agendamento       = ag,
                loja_comp         = loja,
                vendedor          = vend,
                tabulacao_venda   = tab_v,
                tipo_negociacao   = info.get('tipo_negociacao','').upper(),
                banco             = info.get('banco','').upper(),
                subsidio          = str(info.get('subsidio')).lower() in ('true','1','sim'),
                valor_tac         = vt_dec,
                acao              = str(info.get('acao')).lower() in ('true','1','sim'),
                associacao        = str(info.get('associacao')).lower() in ('true','1','sim'),
                aumento           = str(info.get('aumento')).lower() in ('true','1','sim'),
                status_pagamento  = PresencaLoja.StatusPagamentoChoices.EM_ESPERA,
                data_presenca     = timezone.now(),  # Adiciona data da presença
            )
            # Salva sem validar unicidade de agendamento
            p.save()
            pres_ids.append(p.id)

        # marca confirmado
        if ag.tabulacao_agendamento != 'CONFIRMADO':
            ag.tabulacao_agendamento = 'CONFIRMADO'
            ag.save()

        return JsonResponse({
            'status':'success',
            'message':f'{len(pres_ids)} produto(s) registrado(s)',
            'presencas_ids': pres_ids,
            'valor_total_tac': f'R$ {total_tac:.2f}'.replace('.',',')
        })

    # 5️⃣ Fluxo padrão (sem produtos)
    p = PresencaLoja(
        agendamento     = ag,
        loja_comp       = loja,
        vendedor        = vend,
        tabulacao_venda = tab_v,
        data_presenca   = timezone.now()  # Adiciona data da presença
    )
    p.save()
    pres_ids.append(p.id)

    if ag.tabulacao_agendamento != 'CONFIRMADO':
        ag.tabulacao_agendamento = 'CONFIRMADO'
        ag.save()

    return JsonResponse({
        'status':'success',
        'message':'Presença registrada',
        'presenca_id': p.id
    })


@login_required
@require_GET
def api_get_infolojaefuncionario(request):
    """
    API para buscar informações de lojas ativas e funcionários permitidos.

    Retorna um JSON contendo:
    - 'lojas': Um dicionário com ID da loja como chave e {'id', 'nome'} como valor.
    - 'funcionarios': Um dicionário com ID do usuário como chave e {'id', 'nome'} como valor.
    - 'produtos': Um dicionário com ID do produto como chave e {'id', 'nome'} como valor.

    A lista de funcionários e de lojas depende do nível hierárquico do usuário logado:
    - Superusuários ou cargos SUPERVISOR_GERAL e GESTOR veem todas as lojas ativas e todos os funcionários dessas lojas.
    - Cargos de nível superior a PADRAO (COORDENADOR, GERENTE, FRANQUEADO) veem apenas a própria loja e todos os funcionários dessa loja.
    - Cargos ESTAGIO ou PADRAO veem apenas a própria loja e apenas a si mesmos.
    - Usuários sem perfil de funcionário ou sem cargo definido (e não superusuários) veem apenas a si mesmos, sem nenhuma loja adicional.
    """
    try:
        user = request.user

        # 1. Produtos ativos
        produtos_qs = Produto.objects.filter(ativo=True).order_by('nome')
        produtos_dict = {
            p.id: {'id': p.id, 'nome': p.nome}
            for p in produtos_qs
        }

        # 2. Determinar perfil do funcionário logado (se existir)
        func_logado = Funcionario.objects.select_related('cargo', 'loja').filter(
            usuario=user, status=True
        ).first()

        # 3. Inicialização
        lojas_qs = Loja.objects.filter(status=True)  # base de todas as lojas ativas
        funcionarios_qs = Funcionario.objects.none()  # vazio por padrão

        # 4. Superuser -> todas as lojas e todos os funcionários dessas lojas
        if user.is_superuser:
            # lojistas
            lojas_permitidas = lojas_qs
            # funcionários de todas essas lojas
            funcionarios_qs = Funcionario.objects.filter(
                status=True,
                loja__in=lojas_permitidas,
                usuario__isnull=False
            ).select_related('usuario').order_by('nome_completo')

        else:
            # 5. Se não superuser, mas tem perfil de funcionário
            if func_logado and func_logado.cargo:
                hier = func_logado.cargo.hierarquia
                minha_loja = func_logado.loja

                # SUPERVISOR_GERAL ou GESTOR veem tudo também
                if hier in [Cargo.HierarquiaChoices.SUPERVISOR_GERAL,
                            Cargo.HierarquiaChoices.GESTOR]:
                    lojas_permitidas = lojas_qs
                    funcionarios_qs = Funcionario.objects.filter(
                        status=True,
                        loja__in=lojas_permitidas,
                        usuario__isnull=False
                    ).select_related('usuario').order_by('nome_completo')

                # cargos superiores a PADRAO (COORDENADOR, GERENTE, FRANQUEADO)
                elif hier not in [Cargo.HierarquiaChoices.ESTAGIO,
                                  Cargo.HierarquiaChoices.PADRAO]:
                    # vê apenas a própria loja, mas todos os funcionários dela
                    lojas_permitidas = Loja.objects.filter(id=minha_loja.id, status=True)
                    funcionarios_qs = Funcionario.objects.filter(
                        status=True,
                        loja=minha_loja,
                        usuario__isnull=False
                    ).select_related('usuario').order_by('nome_completo')

                else:
                    # ESTAGIO ou PADRAO: vê apenas a própria loja e somente a si mesmo
                    lojas_permitidas = Loja.objects.filter(id=minha_loja.id, status=True)
                    funcionarios_qs = Funcionario.objects.filter(
                        usuario=user,
                        status=True,
                        loja=minha_loja,
                        usuario__isnull=False
                    ).select_related('usuario')

            else:
                # 6. Sem perfil de funcionário associado: só ele mesmo, sem loja
                lojas_permitidas = Loja.objects.none()
                funcionarios_qs = Funcionario.objects.filter(
                    usuario=user, status=True, usuario__isnull=False
                ).select_related('usuario')

        # 7. Formatar dicionários de saída
        lojas_dict = {
            loja.id: {'id': loja.id, 'nome': loja.nome}
            for loja in lojas_permitidas.order_by('nome')
        }
        funcionarios_dict = {
            f.usuario.id: {'id': f.usuario.id, 'nome': f.nome_completo}
            for f in funcionarios_qs if f.usuario
        }

        return JsonResponse({
            'lojas': lojas_dict,
            'funcionarios': funcionarios_dict,
            'produtos': produtos_dict
        })

    except Exception as e:
        # Em produção, substituir print por logger.error(...)
        print(f"Erro em api_get_infolojaefuncionario: {e}")
        return JsonResponse(
            {'erro': 'Ocorreu um erro interno ao buscar dados.'},
            status=500
        )


@csrf_exempt
@require_POST
def api_post_agendamento(request):
    print(">>> Iniciando processamento do agendamento")
    try:
        payload = json.loads(request.body)
        print("Dados recebidos:", payload)
    except json.JSONDecodeError:
        return JsonResponse({'texto': 'Dados inválidos', 'classe': 'error'}, status=400)

    try:
        # 1️⃣ Extrai campos do JSON
        nome_cliente          = payload.get('nome_cliente')
        cpf_cliente_raw       = payload.get('cpf_cliente')
        numero_cliente        = payload.get('numero_cliente')
        dia_agendado_str      = payload.get('dia_agendado')        # precisa existir no JSON
        loja_agendada_id      = payload.get('loja_agendada')
        usuario_atendente_id  = payload.get('funcionario_atendente')

        # Validação básica
        faltam = []
        if not nome_cliente:      faltam.append('Nome')
        if not cpf_cliente_raw:   faltam.append('CPF')
        if not numero_cliente:    faltam.append('Número')
        if not dia_agendado_str:  faltam.append('Dia Agendado')
        if not loja_agendada_id:  faltam.append('Loja')
        if not usuario_atendente_id: faltam.append('Funcionário')
        if faltam:
            return JsonResponse({
                'texto': f"Campos obrigatórios faltando: {', '.join(faltam)}",
                'classe': 'error'
            }, status=400)

        # 2️⃣ Processa CPF
        cpf_limpo = re.sub(r'\D', '', cpf_cliente_raw)
        if len(cpf_limpo) != 11:
            raise ValueError("CPF inválido.")

        # 3️⃣ Converte dia_agendado para datetime
        #    Espera que dia_agendado_str venha no formato 'YYYY-MM-DD'
        try:
            dia_naive = datetime.strptime(dia_agendado_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Formato de data inválido. Use YYYY-MM-DD.")

        # Se sua aplicação usa TZ, torne aware; senão, mantenha naive
        if settings.USE_TZ:
            dia_agendado = timezone.make_aware(
                datetime.combine(dia_naive.date(), timezone.now().time()),
                timezone.get_default_timezone()
            )
        else:
            # Garante que esse datetime não tenha tzinfo
            dia_agendado = dia_naive.replace(
                hour=timezone.now().hour,
                minute=timezone.now().minute,
                second=timezone.now().second,
                microsecond=0
            )

        # 4️⃣ ClienteAgendamento
        cliente, created = ClienteAgendamento.objects.get_or_create(
            cpf=cpf_limpo,
            defaults={
                'nome_completo': nome_cliente.upper(),
                'numero': numero_cliente,
                'status': True
            }
        )
        msg_cliente = "Cliente Cadastrado!" if created else "Cliente Já existe, contato atualizado!"
        if not created:
            updated = False
            if cliente.numero != numero_cliente:
                cliente.numero = numero_cliente; updated = True
            if cliente.nome_completo != nome_cliente.upper():
                cliente.nome_completo = nome_cliente.upper(); updated = True
            if not cliente.status:
                cliente.status = True; updated = True
            if updated:
                cliente.save()

        # 5️⃣ Recupera atendente e loja
        try:
            atendente = User.objects.get(pk=int(usuario_atendente_id))
        except User.DoesNotExist:
            raise ValueError("Funcionário selecionado não existe.")

        try:
            loja_obj = Loja.objects.get(pk=int(loja_agendada_id))
        except Loja.DoesNotExist:
            raise ValueError("Loja selecionada não existe.")

        # 6️⃣ Cria o Agendamento
        agendamento = Agendamento.objects.create(
            cliente_agendamento=cliente,
            dia_agendado=dia_agendado,
            loja=loja_obj,
            atendente_agendou=atendente,
            tabulacao_agendamento='EM ESPERA'
        )
        msg_agendamento = f"Agendamento {agendamento.id} registrado com sucesso!"

        # 7️⃣ Resposta
        texto = f"{msg_cliente} {msg_agendamento}".strip()
        return JsonResponse({'texto': texto, 'classe': 'success'}, status=201)

    except ValueError as ve:
        print("Erro de validação:", ve)
        return JsonResponse({'texto': str(ve), 'classe': 'error'}, status=400)
    except Exception as e:
        import traceback
        print("Exception inesperada:", e)
        traceback.print_exc()
        return JsonResponse({'texto': 'Erro interno.', 'classe': 'error'}, status=500)

@csrf_exempt
@require_POST
def api_post_confirmagem(request):
    """
    Confirma ou reagenda um Agendamento:
      - tabulacao_agendamento é sempre obrigatória
      - se for REAGENDADO, nova_dia_agendado (YYYY-MM-DD) é obrigatória
      - DESISTIU apenas atualiza a tabulação
    Retorna JSON com 'texto' e 'classe' ('success' ou 'error').
    """
    # 1️⃣ Parse dos dados (JSON ou form-encoded)
    if request.content_type.startswith('application/json'):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'texto': 'JSON mal formatado', 'classe': 'error'}, status=400)
    else:
        data = request.POST

    # 2️⃣ Validação do ID do agendamento
    ag_id = data.get('agendamento_id')
    if not ag_id:
        return JsonResponse({'texto': 'ID do agendamento não fornecido', 'classe': 'error'}, status=400)
    try:
        ag_id = int(ag_id)
    except ValueError:
        return JsonResponse({'texto': 'ID do agendamento inválido', 'classe': 'error'}, status=400)

    # 3️⃣ Busca do Agendamento
    try:
        ag = Agendamento.objects.get(pk=ag_id)
    except Agendamento.DoesNotExist:
        return JsonResponse({'texto': 'Agendamento não encontrado', 'classe': 'error'}, status=404)

    # 4️⃣ Tabulação do atendente/agendamento
    nova_tab = data.get('tabulacao_agendamento') or data.get('tabulacao_atendente')
    if not nova_tab:
        return JsonResponse({'texto': 'Tabulação não fornecida', 'classe': 'error'}, status=400)
    ag.tabulacao_agendamento = nova_tab

    # 5️⃣ Se for REAGENDADO, valida e atualiza data
    if nova_tab.upper() == 'REAGENDADO':
        nova_data = data.get('nova_dia_agendado')
        if not nova_data:
            return JsonResponse({'texto': 'Nova data obrigatória para reagendamento', 'classe': 'error'}, status=400)
        try:
            d = datetime.strptime(nova_data, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'texto': 'Formato de data inválido. Use YYYY-MM-DD', 'classe': 'error'}, status=400)

        # une com hora atual de SP e torna aware
        hora_sp = get_current_sp_time().time()
        dt_comb = datetime.combine(d, hora_sp)
        ag.dia_agendado = make_aware_sp(dt_comb)

    # 6️⃣ Se for DESISTIU, apenas tabulação é atualizada (sem campo extra)

    # 7️⃣ Salva e retorna sucesso
    ag.save()
    return JsonResponse({'texto': 'Agendamento atualizado com sucesso 😊', 'classe': 'success'}, status=200)

@csrf_exempt
@require_GET
def api_get_submodal_cliente(request):
    """
    API que recebe 'agendamento_id' ou 'cpf_cliente' e retorna:
    - dados do agendamento
    - dados da presença (PresencaLoja), se houver
    """
    try:
        agendamento_id    = request.GET.get('agendamento_id')
        cpf_cliente_param = request.GET.get('cpf_cliente')

        # 1) busca o Agendamento
        qs = Agendamento.objects.select_related(
            'cliente_agendamento', 'loja', 'atendente_agendou'
        )
        if agendamento_id:
            ag = qs.filter(pk=agendamento_id).first()
            if not ag:
                return JsonResponse(
                    {'texto': 'Agendamento não encontrado pelo ID', 'classe': 'error'},
                    status=404
                )
        elif cpf_cliente_param:
            cpf_limpo = re.sub(r'\D', '', cpf_cliente_param)
            if len(cpf_limpo) != 11:
                return JsonResponse(
                    {'texto': 'CPF inválido fornecido', 'classe': 'error'},
                    status=400
                )
            ag = qs.filter(
                cliente_agendamento__cpf=cpf_limpo
            ).order_by('-dia_agendado').first()
            if not ag:
                # se cliente existe mas sem agendamento...
                cliente = ClienteAgendamento.objects.filter(cpf=cpf_limpo).first()
                if cliente:
                    return JsonResponse({
                        'texto': 'Cliente sem agendamentos registrados.',
                        'cliente_info': {
                            'nome': cliente.nome_completo,
                            'cpf': cliente.cpf,
                            'numero': cliente.numero
                        }
                    }, status=404)
                return JsonResponse(
                    {'texto': 'Nenhum cliente ou agendamento encontrado', 'classe': 'error'},
                    status=404
                )
        else:
            return JsonResponse(
                {'texto': 'agendamento_id ou cpf_cliente não fornecido', 'classe': 'error'},
                status=400
            )

        # 2) Serializa dados do cliente
        cli = ag.cliente_agendamento
        cliente_data = {
            'nome_cliente':   cli.nome_completo if cli else 'N/A',
            'cpf_cliente':    getattr(cli, 'cpf', 'N/A'),
            'numero_cliente': getattr(cli, 'numero', 'N/A'),
        }

        # formata dia_agendado
        dt = ag.dia_agendado
        if dt and settings.USE_TZ:
            dt = timezone.localtime(dt)
        dia_ag = dt.strftime('%Y-%m-%d %H:%M') if dt else ''

        # nome do atendente que agendou
        atend = ag.atendente_agendou
        if atend:
            fn = Funcionario.objects.filter(usuario=atend).first()
            atend_nome = fn.apelido.split()[0] if fn and fn.apelido else (atend.get_full_name() or atend.username)
        else:
            atend_nome = 'N/A'

        agendamento_data = {
            'id': ag.id,
            'dia_agendado': dia_ag,
            'atendente_agendou': atend_nome,
            'loja_agendada': ag.loja.nome if ag.loja else 'N/A',
            'tabulacao_agendamento': ag.tabulacao_agendamento or '',
        }

        # 3) Pega a primeira PresencaLoja, se existir
        pres = ag.presencas.first()
        if pres:
            # nome do vendedor
            vend_fn = Funcionario.objects.filter(usuario=pres.vendedor).first()
            vendedor_nome = (
                vend_fn.apelido.split()[0] if vend_fn and vend_fn.apelido
                else (pres.vendedor.get_full_name() or pres.vendedor.username)
            ) if pres.vendedor else 'N/A'

            presenca_data = {
                'tabulacao_vendedor':    pres.tabulacao_venda or '',
                'tipo_negociacao':       pres.tipo_negociacao or '',
                'banco':                 pres.banco or '',
                'subsidio':              bool(pres.subsidio),
                'tac':                   str(pres.valor_tac or ''),
                'acao':                  bool(pres.acao),
                'associacao':            bool(pres.associacao),
                'aumento':               bool(pres.aumento),
                'status_tac':            pres.get_status_pagamento_display() or '',
                'data_pagamento_tac':    pres.data_pagamento.strftime('%Y-%m-%d') if pres.data_pagamento else '',
                'cliente_rua':           bool(pres.cliente_rua),
                'vendedor_loja':         vendedor_nome,
            }
        else:
            presenca_data = {
                'tabulacao_vendedor': '', 'tipo_negociacao': '', 'banco': '',
                'subsidio': False,       'tac': '',              'acao': False,
                'associacao': False,     'aumento': False,       'status_tac': '',
                'data_pagamento_tac': '', 'cliente_rua': False,  'vendedor_loja': 'N/A',
            }

        # 4) combina tudo
        resultado = {**cliente_data, **agendamento_data, **presenca_data}
        return JsonResponse(resultado, status=200)

    except Exception:
        traceback.print_exc()
        return JsonResponse(
            {'texto': 'Erro interno ao obter submodal do cliente', 'classe': 'error'},
            status=500
        )


@csrf_exempt
@require_GET
@login_required
def api_get_agendados(request):
    """
    Retorna agendamentos com tabulação 'EM ESPERA'.
    """
    try:
        qs = Agendamento.objects.filter(
            tabulacao_agendamento='EM ESPERA'
        ).select_related('cliente_agendamento', 'loja', 'atendente_agendou')
        qs = _filter_por_hierarquia(qs, request.user)
        resultados = [_serialize_agendamento(a) for a in qs.order_by('-dia_agendado')]
        return JsonResponse({'agendamentos': resultados}, status=200)
    except Exception as e:
        return JsonResponse({'texto': f'Erro: {str(e)}', 'classe': 'error'}, status=500)


@csrf_exempt
@require_GET
@login_required
def api_get_reagendados(request):
    """
    Retorna agendamentos com tabulação 'REAGENDADO'.
    """
    try:
        qs = Agendamento.objects.filter(
            tabulacao_agendamento='REAGENDADO'
        ).select_related('cliente_agendamento', 'loja', 'atendente_agendou')
        qs = _filter_por_hierarquia(qs, request.user)
        resultados = [_serialize_agendamento(a) for a in qs.order_by('-dia_agendado')]
        return JsonResponse({'agendamentos': resultados}, status=200)
    except Exception as e:
        return JsonResponse({'texto': f'Erro: {str(e)}', 'classe': 'error'}, status=500)


@csrf_exempt
@require_GET
@login_required
def api_get_atrasados(request):
    """
    Retorna agendamentos 'EM ESPERA' ou 'REAGENDADO' cujo dia_agendado < hoje.
    Mantém apenas o mais recente por CPF.
    """
    try:
        agora = timezone.now()
        qs = Agendamento.objects.filter(
            tabulacao_agendamento__in=['EM ESPERA', 'REAGENDADO'],
            dia_agendado__lt=agora
        ).select_related('cliente_agendamento', 'loja', 'atendente_agendou')
        qs = _filter_por_hierarquia(qs, request.user)

        # mantém só o mais recente por CPF
        por_cpf = {}
        for a in qs:
            cliente = a.cliente_agendamento
            if not cliente or not cliente.cpf:
                continue
            cpf = cliente.cpf
            if cpf not in por_cpf or a.dia_agendado > por_cpf[cpf].dia_agendado:
                por_cpf[cpf] = a

        resultados = [
            _serialize_agendamento(a)
            for a in sorted(por_cpf.values(), key=lambda x: x.dia_agendado, reverse=True)
        ]
        return JsonResponse({'agendamentos': resultados}, status=200)
    except Exception as e:
        return JsonResponse({'texto': f'Erro: {str(e)}', 'classe': 'error'}, status=500)
@csrf_exempt
@require_GET
@login_required
def api_get_atrasados(request):
    """
    Agendamentos 'EM ESPERA' ou 'REAGENDADO' com dia_agendado < hoje.
    Retorna apenas o mais recente por CPF.
    """
    try:
        hoje = timezone.now()
        qs = Agendamento.objects.filter(
            tabulacao_agendamento__in=['EM ESPERA', 'REAGENDADO'],
            dia_agendado__lt=hoje
        ).select_related('cliente_agendamento', 'loja', 'atendente_agendou')
        qs = _filter_por_hierarquia(qs, request.user)

        # pega o mais recente por CPF
        por_cpf = {}
        for a in qs:
            cliente = a.cliente_agendamento
            if not cliente or not cliente.cpf:
                continue
            cpf = cliente.cpf
            if cpf not in por_cpf or a.dia_agendado > por_cpf[cpf].dia_agendado:
                por_cpf[cpf] = a

        data = [_serialize_agendamento(a) for a in sorted(
            por_cpf.values(),
            key=lambda x: x.dia_agendado,
            reverse=True
        )]
        return JsonResponse({'agendamentos': data}, status=200)
    except Exception as e:
        return JsonResponse({'texto': str(e), 'classe': 'error'}, status=500)

@csrf_exempt
@require_GET
def api_get_emloja(request):
    """
    Agendamentos que tiveram presença registrada (PresencaLoja):
    - Superuser: filtra apenas pela semana atual (domingo→sábado)
    - ESTAGIO/PADRAO: filtra pela loja do funcionário
    - Demais: vê todos que têm presença.
    """
    try:
        user = request.user

        # Query base: todos com presença não-nula
        qs = Agendamento.objects.filter(
            presenca__isnull=False
        ).select_related(
            'cliente_agendamento',
            'loja',
            'presenca'  # Inclui o relacionamento presenca
        )

        # 1) Filtrar por data de agendamento (superuser) ou por loja (estágio/padrão)
        if user.is_superuser:
            hoje = timezone.now().date()
            domingo = hoje - timedelta(days=(hoje.weekday() + 1) % 7)
            sabado  = domingo + timedelta(days=6)

            # Monta datetimes de início e fim
            dt_start = datetime.combine(domingo, time.min)
            dt_end   = datetime.combine(sabado,  time.max)

            # Se o projeto usa TZ, torna aware; senão, mantém naive
            if settings.USE_TZ:
                dt_start = timezone.make_aware(dt_start, timezone.get_default_timezone())
                dt_end   = timezone.make_aware(dt_end,   timezone.get_default_timezone())

            qs = qs.filter(dia_agendado__range=(dt_start, dt_end))

        else:
            # Tenta obter o funcionário para ver qual loja filtrar
            try:
                func = Funcionario.objects.select_related('cargo', 'loja').get(usuario=user)
                nivel = func.cargo.hierarquia if func.cargo else None

                if nivel in [Cargo.HierarquiaChoices.ESTAGIO, Cargo.HierarquiaChoices.PADRAO] and func.loja:
                    qs = qs.filter(loja=func.loja)
                # coordenador/gerente e demais níveis não fazem filtro adicional aqui

            except Funcionario.DoesNotExist:
                # usuário sem funcionário não vê nada
                return JsonResponse({'clientes_em_loja': []}, status=200)

        # 2) Serializa resultados
        clientes = []
        for ag in qs.order_by('-dia_agendado'):
            # Usa o relacionamento presenca diretamente
            pres = ag.presenca
            tab_venda = pres.tabulacao_venda if pres and pres.tabulacao_venda else 'PENDENTE'

            cliente = ag.cliente_agendamento
            clientes.append({
                'nome_cliente': cliente.nome_completo if cliente else 'N/A',
                'cpf_cliente': cliente.cpf if cliente else 'N/A',
                'loja_agendada': ag.loja.nome if ag.loja else 'N/A',
                # ao exibir, se USE_TZ=True usamos localtime, senão apenas strftime do naive
                'dia_agendado': (
                    timezone.localtime(ag.dia_agendado).strftime('%Y-%m-%d')
                    if settings.USE_TZ else ag.dia_agendado.strftime('%Y-%m-%d')
                ),
                'tabulacao_venda': tab_venda,
            })

        return JsonResponse({'clientes_em_loja': clientes}, status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'texto': 'Erro interno ao obter clientes em loja.', 'classe': 'error'}, status=500)

@login_required
@require_GET
@ensure_csrf_cookie
def api_get_cpfclientenome(request):
    """
    Recebe ?cpf=000.000.000-00 (ou sem formatação),
    busca em ClienteAgendamento.cpf (armazenado sem máscara)
    e retorna {'nome': 'Fulano da Silva'} ou 404 com {'mensagem': 'Cliente não encontrado'}.
    """
    cpf = request.GET.get('cpf', '')
    print(f"[DEBUG] CPF recebido: {cpf}")
    
    # remove tudo que não for dígito
    cpf_digits = re.sub(r'\D', '', cpf)
    print(f"[DEBUG] CPF formatado: {cpf_digits}")
    
    try:
        # Remove caracteres especiais de todos os CPFs no banco antes de comparar
        clientes = ClienteAgendamento.objects.all()
        for cliente in clientes:
            cpf_banco = re.sub(r'\D', '', cliente.cpf)
            if cpf_banco == cpf_digits:
                print(f"[DEBUG] Cliente encontrado: {cliente.nome_completo}")
                return JsonResponse({'nome': cliente.nome_completo})
        
        print("[DEBUG] Cliente não encontrado")
        return JsonResponse(
            {'mensagem': 'Cliente não encontrado'},
            status=404
        )
    except Exception as e:
        print(f"[ERROR] Erro ao buscar cliente: {str(e)}")
        return JsonResponse(
            {'mensagem': 'Erro interno ao buscar cliente'},
            status=500
        )

# -------------------------------------------
# FIM TEMPLATE AGENDAMENTO.HTML
# -------------------------------------------



# -------------------------------------------
# INICIO RANKING : inss/ranking.html
# Funções relacionadas ao Ranking
# -------------------------------------------

def _to_range(dt_date, start=True):
    """
    Return a datetime (aware if USE_TZ) at start or end of dt_date.
    """
    t = time.min if start else time.max
    dt = datetime.combine(dt_date, t)
    if settings.USE_TZ:
        return timezone.make_aware(dt)
    return dt


def api_get_cards(request, periodo='meta'):
    print(f"[DEBUG] api_get_cards called with periodo='{periodo}'")
    hoje = timezone.now().date()
    print(f"[DEBUG] Hoje: {hoje}")

    # helpers
    fmt = lambda v: f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    pct = lambda f, m: round((f / m) * 100, 2) if m > 0 else 0

    # ====================================================
    # Carrega a meta INSS (usada por vários cards)
    # ====================================================
    meta_set_qs = RegisterMeta.objects.filter(
        categoria='SETOR',
        status=True,
        data_inicio__date__lte=hoje,
        data_fim__date__gte=hoje,
        setor__nome='INSS'
    )
    if meta_set_qs.exists():
        m_set = meta_set_qs.first()
        si_set = datetime.combine(m_set.data_inicio.date(), time.min)
        sf_set = datetime.combine(m_set.data_fim.date(),     time.max)
        mv_set = m_set.valor or Decimal('0.0')
        print(f"[DEBUG] Meta INSS interval: {si_set} → {sf_set}, valor_meta={mv_set}")
    else:
        si_set = sf_set = None
        mv_set = Decimal('0.0')
        print("[DEBUG] Sem meta SETOR INSS ativa")

    # função para somar reembolsos no intervalo, opcionalmente filtrado
    def sum_refunds(start, end, **rq_kwargs):
        qs = Reembolso.objects.filter(
            status=True,
            data_reembolso__range=[start, end],
            registermoney__status=True,
            **{f"registermoney__{k}": v for k, v in rq_kwargs.items()}
        )
        total = qs.aggregate(t=Sum('registermoney__valor_est'))['t'] or Decimal('0.0')
        print(f"[DEBUG] Refunds filter={rq_kwargs}: {total}")
        return total

    # ====================================================
    # Card 1: Meta Geral
    # ====================================================
    print("[DEBUG] Calculating Meta Geral...")
    meta_geral = RegisterMeta.objects.filter(
        categoria='GERAL',
        status=True,
        data_inicio__date__lte=hoje,
        data_fim__date__gte=hoje
    ).first()
    if meta_geral:
        si = datetime.combine(meta_geral.data_inicio.date(), time.min)
        sf = datetime.combine(meta_geral.data_fim.date(),     time.max)
        mv_geral = meta_geral.valor or Decimal('0.0')
        fat_geral = RegisterMoney.objects.filter(
            data__range=[si, sf],
            status=True
        ).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.0')
        ref_geral = sum_refunds(si, sf)
        fat_geral -= ref_geral
        print(f"[DEBUG] Meta Geral bruto={fat_geral + ref_geral}, refunds={ref_geral}, líquid o={fat_geral}")
    else:
        fat_geral = mv_geral = Decimal('0.0')
        print("[DEBUG] Nenhuma meta GERAL ativa")

    # ====================================================
    # Card 2: Meta Empresa (não franquia)
    # ====================================================
    print("[DEBUG] Calculating Meta Empresa...")
    meta_emp = RegisterMeta.objects.filter(
        categoria='EMPRESA',
        status=True,
        data_inicio__date__lte=hoje,
        data_fim__date__gte=hoje
    ).first()
    if meta_emp:
        si = datetime.combine(meta_emp.data_inicio.date(), time.min)
        sf = datetime.combine(meta_emp.data_fim.date(),     time.max)
        mv_emp = meta_emp.valor or Decimal('0.0')
        fat_emp = RegisterMoney.objects.filter(
            data__range=[si, sf],
            status=True,
            loja__franquia=False
        ).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.0')
        ref_emp = sum_refunds(si, sf, loja__franquia=False)
        fat_emp -= ref_emp
        print(f"[DEBUG] Meta Empresa bruto={fat_emp + ref_emp}, refunds={ref_emp}, líquid o={fat_emp}")
    else:
        fat_emp = mv_emp = Decimal('0.0')
        print("[DEBUG] Nenhuma meta EMPRESA ativa")

    # ====================================================
    # Card 3: Meta Setor INSS
    # ====================================================
    print("[DEBUG] Calculating Meta Setor INSS...")
    if si_set and sf_set:
        fat_set = RegisterMoney.objects.filter(
            data__range=[si_set, sf_set],
            status=True
        ).exclude(loja__isnull=True).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.0')
        ref_set = sum_refunds(si_set, sf_set)  # sem filtro extra, pois setor já é INSS
        fat_set -= ref_set
        print(f"[DEBUG] Meta Setor INSS bruto={fat_set + ref_set}, refunds={ref_set}, líquid o={fat_set}")
    else:
        fat_set = Decimal('0.0')
        ref_set = Decimal('0.0')

    # ====================================================
    # Card 4: Quantidade em Loja (únicos)
    # ====================================================
    print("[DEBUG] Calculating Quantidade em Loja...")
    if si_set and sf_set:
        qtd_pres = PresencaLoja.objects.filter(
            data_presenca__range=[si_set, sf_set]
        ).values('cliente_agendamento__cpf').distinct().count()
        print(f"[DEBUG] Presenças únicas: {qtd_pres}")
    else:
        qtd_pres = 0

    # ====================================================
    # Card 5: Quantidade Confirmados
    # ====================================================
    print("[DEBUG] Calculating Quantidade Confirmados...")
    if si_set and sf_set:
        qtd_conf = Agendamento.objects.filter(
            dia_agendado__range=[si_set, sf_set],
            tabulacao_agendamento='CONFIRMADO'
        ).count()
        print(f"[DEBUG] Confirmados: {qtd_conf}")
    else:
        qtd_conf = 0

    # ====================================================
    # Montagem da resposta
    # ====================================================
    response_data = {
        'meta_geral': {
            'valor':      fmt(fat_geral),
            'percentual': pct(fat_geral, mv_geral),
            'valor_meta': fmt(mv_geral)
        },
        'meta_empresa': {
            'valor':      fmt(fat_emp),
            'percentual': pct(fat_emp, mv_emp),
            'valor_meta': fmt(mv_emp)
        },
        'meta_setor': {
            'valor':      fmt(fat_set),
            'percentual': pct(fat_set, mv_set),
            'valor_meta': fmt(mv_set)
        },
        'quantidade': {
            'valor': qtd_pres,
            'label': 'Presenças Únicas (Meta INSS)'
        },
        'agendamentos': {
            'valor': qtd_conf,
            'label': 'Confirmados (Meta INSS)'
        },
        'periodo': {
            'inicio': si_set.date().isoformat() if si_set else hoje.replace(day=1).isoformat(),
            'fim':    sf_set.date().isoformat() if sf_set else hoje.isoformat(),
            'tipo':   periodo
        }
    }
    print(f"[DEBUG] Response data: {response_data}")
    return JsonResponse(response_data)


def api_get_podium(request, periodo='meta'):
    hoje = timezone.now().date()

    # define di, df
    if periodo == 'dia':
        di, df = hoje, hoje
    elif periodo == 'semana':
        di = hoje - timedelta(days=hoje.weekday())
        df = di + timedelta(days=6)
    elif periodo == 'mes':
        di = hoje.replace(day=1)
        try:
            df = hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1)
        except ValueError:
            df = hoje.replace(day=31, month=12)
    else:
        m = RegisterMeta.objects.filter(
            categoria='SETOR', status=True,
            data_inicio__date__lte=hoje, data_fim__date__gte=hoje,
            setor__nome='INSS'
        ).first()
        if m and m.data_inicio and m.data_fim:
            di = m.data_inicio.date()
            df = m.data_fim.date()
        else:
            di = hoje.replace(day=1)
            try:
                df = hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1)
            except ValueError:
                df = hoje.replace(day=31, month=12)
            periodo = 'mes'

    si = datetime.combine(di, time.min)
    sf = datetime.combine(df, time.max)

    users_inss = Funcionario.objects.filter(
        setor__nome='INSS', status=True, usuario__isnull=False
    ).values_list('usuario_id', flat=True)

    vendas = RegisterMoney.objects.filter(
        data__range=[si, sf],
        status=True,
        loja__isnull=False,
        user_id__in=users_inss
    ).values('loja__id', 'loja__nome', 'loja__logo')\
     .annotate(total=Sum('valor_est'))\
     .order_by('-total')

    top3 = list(vendas[:3])
    default_logo = '/static/img/default-store.png'
    podium = []
    for idx, itm in enumerate(top3):
        tot = itm['total'] or Decimal('0.0')
        vf  = f"R$ {tot:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        logo = f"/media/{itm['loja__logo']}" if itm['loja__logo'] else default_logo
        podium.append({'nome': itm['loja__nome'], 'valor': vf, 'pos': idx+1, 'logo': logo})
    while len(podium) < 3:
        podium.append({'nome':'','valor':'R$ 0,00','pos':len(podium)+1,'logo':default_logo})

    return JsonResponse({
        'podium': podium,
        'periodo': {
            'inicio': di.strftime("%Y-%m-%d"),
            'fim':    df.strftime("%Y-%m-%d"),
            'tipo':   periodo
        }
    })


def api_get_tabela(request, periodo='semana'):
    hoje = timezone.now().date()

    # define di, df
    if periodo == 'dia':
        di, df = hoje, hoje
    elif periodo == 'semana':
        di = hoje - timedelta(days=hoje.weekday())
        df = di + timedelta(days=6)
    elif periodo == 'mes':
        di = hoje.replace(day=1)
        try:
            df = hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1)
        except ValueError:
            df = hoje.replace(day=31, month=12)
    else:
        m = RegisterMeta.objects.filter(
            categoria='SETOR', status=True,
            data_inicio__date__lte=hoje, data_fim__date__gte=hoje,
            setor__nome='INSS'
        ).first()
        if m and m.data_inicio and m.data_fim:
            di = m.data_inicio.date()
            df = m.data_fim.date()
        else:
            di = hoje.replace(day=1)
            try:
                df = hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1)
            except ValueError:
                df = hoje.replace(day=31, month=12)
            periodo = 'mes'

    si = datetime.combine(di, time.min)
    sf = datetime.combine(df, time.max)

    # 1) todos os INSS ativos
    users_all = User.objects.filter(
        funcionario_profile__setor__nome='INSS',
        funcionario_profile__status=True
    )
    user_ids = list(users_all.values_list('id', flat=True))

    # 2) quem confirmou
    conf_qs = Agendamento.objects.filter(
        dia_agendado__range=[si, sf],
        atendente_agendou_id__in=user_ids,
        tabulacao_agendamento='CONFIRMADO'
    )
    eleg_ids = set(conf_qs.values_list('atendente_agendou_id', flat=True))

    # 3) mapa base
    default_foto = '/static/img/user.png'
    perfil_map = {}
    for u in users_all:
        if u.id in eleg_ids:
            prof = getattr(u, 'funcionario_profile', None)
            foto = prof.foto.url if prof and prof.foto else default_foto
            nome = prof.apelido or (prof.nome_completo.split()[0] if prof else u.username)
            perfil_map[u.id] = {'foto': foto, 'nome': nome, 'qtd_ag':0, 'qtd_el':0, 'val_v':Decimal('0.0')}

    if not eleg_ids:
        return JsonResponse({
            'ranking_data': [],
            'periodo': {'inicio': di.strftime("%Y-%m-%d"), 'fim': df.strftime("%Y-%m-%d"), 'tipo': periodo},
            'total_agendamentos': 0
        })

    # 4) conta agendados
    ag_ct = Agendamento.objects.filter(
        dia_agendado__range=[si, sf],
        atendente_agendou_id__in=eleg_ids
    ).values('atendente_agendou_id').annotate(cnt=Count('id'))
    for itm in ag_ct:
        perfil_map[itm['atendente_agendou_id']]['qtd_ag'] = itm['cnt']

    # 5) conta presenças válidas
    pres_ct = PresencaLoja.objects.filter(
        data_presenca__range=[si, sf],
        agendamento__atendente_agendou_id__in=eleg_ids
    ).exclude(tabulacao_venda=PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR)\
     .values('agendamento__atendente_agendou_id').annotate(cnt=Count('id'))
    for itm in pres_ct:
        perfil_map[itm['agendamento__atendente_agendou_id']]['qtd_el'] = itm['cnt']

    # 6) soma vendas
    vend_ct = RegisterMoney.objects.filter(
        data__range=[si, sf],
        status=True,
        user_id__in=eleg_ids
    ).values('user_id').annotate(total=Sum('valor_est'))
    for itm in vend_ct:
        perfil_map[itm['user_id']]['val_v'] = itm['total'] or Decimal('0.0')

    # 7) formata e ordena
    ranking = []
    for uid, d in perfil_map.items():
        vf = f"R$ {d['val_v']:,.2f}".replace(',', '_').replace('.', ',').replace('_','.')
        ranking.append({
            'foto':         d['foto'],
            'nome':         d['nome'],
            'qtd_agendados':d['qtd_ag'],
            'qtd_emloja':   d['qtd_el'],
            'valor_vendas': vf
        })
    ranking.sort(key=lambda x: (
        -float(x['valor_vendas'].replace('R$ ','').replace('.','').replace(',','.')),
        -x['qtd_emloja'],
        -x['qtd_agendados'],
        x['nome']
    ))
    for i, itm in enumerate(ranking, 1):
        itm['posicao'] = i

    return JsonResponse({
        'ranking_data': ranking,
        'periodo': {'inicio': di.strftime("%Y-%m-%d"), 'fim': df.strftime("%Y-%m-%d"), 'tipo': periodo},
        'total_agendamentos': len(ag_ct)
    })
# -------------------------------------------
# FIM RANKING
# -------------------------------------------


# -------------------------------------------
# GERAL
# -------------------------------------------


@require_GET
def api_get_infogeral(request):
    print('iniciando api get!')
    user = request.user
    # Se for superuser, retorna todas as lojas e todos os funcionários
    if user.is_superuser:
        lojas = Loja.objects.all()
        funcionarios = Funcionario.objects.all()
    else:
        # Procura o funcionário associado ao usuário logado
        try:
            funcionario = Funcionario.objects.get(usuario_id=user.id)
        except Funcionario.DoesNotExist:
            return JsonResponse({"erro": "Funcionário não encontrado"}, status=404)
        # Exibe apenas a loja do funcionário e o próprio funcionário
        lojas = Loja.objects.filter(id=funcionario.loja.id) if funcionario.loja else []
        funcionarios = [funcionario]

    lojas_data = [{"id": loja.id, "nome": loja.nome} for loja in lojas]
    funcionarios_data = [{"id": func.id, "apelido": func.apelido} for func in funcionarios]

    return JsonResponse({"lojas": lojas_data, "funcionarios": funcionarios_data}, status=200)

# Nova View para Exportar CSV
@login_required # Opcional: Adicione autenticação se necessário
def export_agendamentos_csv(request):
    """
    Gera e retorna um arquivo CSV com todos os dados de Agendamento e sua PresencaLoja associada (se houver).
    Substitui IDs por nomes/apelidos e formata os dados adequadamente, conforme os novos modelos.
    """
    # Define o nome do arquivo CSV, incluindo a data atual
    filename = f"agendamentos_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Cria a resposta HTTP com os headers apropriados para CSV
    response = HttpResponse(
        content_type='text/csv; charset=utf-8-sig', # utf-8-sig inclui BOM para melhor compatibilidade com Excel
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )

    # Utiliza StringIO para escrever o CSV em memória
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL) # Usando ';' como delimitador

    # --- Cabeçalho do CSV (Ajustado) ---
    header = [
        'ID Agendamento',
        'Nome Cliente',
        'CPF Cliente',
        'Numero Cliente',
        'Cliente Possui WhatsApp', # Nome da coluna atualizado
        'Dia Agendado',
        'Loja Agendada', # Nome da loja vindo de agendamento.loja
        'Atendente Agendou (Apelido)', # Obtido do User -> Funcionario
        'Atendente Agendou (Nome Completo)', # Obtido do User -> Funcionario
        'Tabulacao Agendamento', # Campo do Agendamento
        'Observacao Atendente', # Campo não existe mais, será vazio
        'Vendedor Loja (Apelido)', # Obtido da PresencaLoja.vendedor (User -> Funcionario)
        'Vendedor Loja (Nome Completo)', # Obtido da PresencaLoja.vendedor (User -> Funcionario)
        'Tabulacao Venda (Presença)', # Campo da PresencaLoja
        'Observacao Vendedor', # Campo não existe mais, será vazio
        'Tipo Negociacao (Presença)', # Campo da PresencaLoja
        'Banco (Presença)', # Campo da PresencaLoja
        'Subsidio (Presença)', # Campo da PresencaLoja
        'TAC Valor (Presença)', # Campo da PresencaLoja
        'Acao (Presença)', # Campo da PresencaLoja
        'Associacao (Presença)', # Campo da PresencaLoja
        'Aumento (Presença)', # Campo da PresencaLoja
        'Status TAC (Presença)', # Campo da PresencaLoja (status_pagamento)
        'Data Pagamento TAC (Presença)', # Campo da PresencaLoja (data_pagamento)
        'Cliente Rua (Presença)', # Campo da PresencaLoja
        'Mensagem Update TAC', # Campo não existe mais, será vazio
    ]
    writer.writerow(header)

    # --- Dados dos Agendamentos ---
    # Otimização: Pré-carregar dados relacionados
    agendamentos = Agendamento.objects.select_related(
        'cliente_agendamento',
        'loja',
        'atendente_agendou', # Relação com User
        'presenca', # Relação OneToOne reversa com PresencaLoja
        'presenca__vendedor' # Relação com User a partir da PresencaLoja
    ).all().order_by('-dia_agendado') # Ordena do mais recente para o mais antigo

    # Otimização: Buscar todos os funcionários relevantes de uma vez
    user_ids = set()
    for ag in agendamentos:
        if ag.atendente_agendou:
            user_ids.add(ag.atendente_agendou.id)
        # Verifica se 'presenca' existe e não é None antes de acessar seus atributos
        presenca_obj = getattr(ag, 'presenca', None)
        if presenca_obj and presenca_obj.vendedor:
            user_ids.add(presenca_obj.vendedor.id)
            
    # Garante que Funcionario seja importado (pode precisar ajustar o caminho)
    try:
        from apps.funcionarios.models import Funcionario 
        funcionarios_map = {
            func.usuario_id: func
            for func in Funcionario.objects.filter(usuario_id__in=list(user_ids)).select_related('usuario')
        }
    except ImportError:
        print("Erro: Não foi possível importar o modelo Funcionario. Verifique o caminho.")
        funcionarios_map = {}
        # Considerar retornar um erro ou continuar com dados limitados

    # Função auxiliar para formatar datas e horas
    def format_datetime(dt):
        if dt:
            # Converte para o fuso horário local (se necessário) e formata
            return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M:%S')
        return ''

    # Função auxiliar para obter nome/apelido de um User via Funcionario mapeado
    def get_funcionario_info_from_user(user, info_type='apelido'):
        if not user:
            return 'N/A'
        
        funcionario = funcionarios_map.get(user.id)
        if not funcionario:
            # Se não encontrar o funcionário mapeado, tenta retornar o username do User
            # Ou primeiro/último nome se disponíveis
            display_name = f"{user.first_name} {user.last_name}".strip()
            return display_name or user.username or 'N/A'

        if info_type == 'apelido':
            # Usa apelido do funcionário, senão primeiro nome do user, senão username
            return funcionario.apelido or user.first_name or user.username or 'N/A' 
        elif info_type == 'nome_completo':
             # Usa nome e sobrenome do User (padrão Django)
             full_name = f"{user.first_name} {user.last_name}".strip()
             # Alternativa: Usar nome_completo do Funcionario se existir:
             # full_name = getattr(funcionario, 'nome_completo', f"{user.first_name} {user.last_name}".strip())
             return full_name if full_name else user.username or 'N/A' # Fallback para username
        return 'N/A'

    # Função auxiliar para formatar booleano
    def format_boolean(value):
        if value is None:
            return '' # Retorna vazio em vez de 'N/A' para consistência
        return 'Sim' if value else 'Não'

     # Função auxiliar para formatar decimal para CSV (com vírgula decimal)
    def format_decimal(value):
        if value is None:
            return ''
        try:
            # Tenta formatar como decimal com 2 casas, usando vírgula
            return f"{Decimal(value):.2f}".replace('.', ',')
        except (TypeError, ValueError, InvalidOperation):
             # Retorna vazio se a conversão falhar
             return ''


    for agendamento in agendamentos:
        presenca = getattr(agendamento, 'presenca', None) # Acessa a presença relacionada (pode ser None)

        # Dados do ClienteAgendamento
        cliente_nome = 'N/A'
        cliente_cpf = 'N/A'
        cliente_numero = 'N/A'
        cliente_whatsapp = 'Não'
        if agendamento.cliente_agendamento:
            cliente_nome = agendamento.cliente_agendamento.nome_completo or 'N/A'
            cliente_cpf = agendamento.cliente_agendamento.cpf or 'N/A'
            cliente_numero = agendamento.cliente_agendamento.numero or 'N/A'
            cliente_whatsapp = format_boolean(agendamento.cliente_agendamento.flg_whatsapp)

        # Dados do Agendamento
        dia_agendado_fmt = format_datetime(agendamento.dia_agendado)
        loja_nome = agendamento.loja.nome if agendamento.loja else 'N/A'
        atendente_apelido = get_funcionario_info_from_user(agendamento.atendente_agendou, 'apelido')
        atendente_nome_completo = get_funcionario_info_from_user(agendamento.atendente_agendou, 'nome_completo')
        tabulacao_agendamento = agendamento.tabulacao_agendamento or ''
        obs_atendente = '' # Campo não existe mais

        # Dados da PresencaLoja (se existir) - Valores padrão
        vendedor_apelido = 'N/A'
        vendedor_nome_completo = 'N/A'
        tabulacao_venda = ''
        obs_vendedor = '' # Campo não existe mais
        tipo_negociacao = ''
        banco = ''
        subsidio = 'Não'
        tac_valor = ''
        acao = 'Não'
        associacao = 'Não'
        aumento = 'Não'
        status_tac = ''
        data_pagamento_tac = ''
        cliente_rua = 'Não'
        msg_update_tac = '' # Campo não existe mais

        if presenca: # Se existe um registro de PresencaLoja associado
            vendedor_apelido = get_funcionario_info_from_user(presenca.vendedor, 'apelido')
            vendedor_nome_completo = get_funcionario_info_from_user(presenca.vendedor, 'nome_completo')
            tabulacao_venda = presenca.tabulacao_venda or ''
            # obs_vendedor = '' # Ainda vazio
            tipo_negociacao = presenca.tipo_negociacao or ''
            banco = presenca.banco or ''
            subsidio = format_boolean(presenca.subsidio)
            tac_valor = format_decimal(presenca.valor_tac)
            acao = format_boolean(presenca.acao)
            associacao = format_boolean(presenca.associacao)
            aumento = format_boolean(presenca.aumento)
            status_tac = presenca.get_status_pagamento_display() # Usa o método display se disponível
            data_pagamento_tac = format_datetime(presenca.data_pagamento)
            cliente_rua = format_boolean(presenca.cliente_rua)
            # msg_update_tac = '' # Ainda vazio

        row = [
            agendamento.id,
            cliente_nome,
            cliente_cpf,
            cliente_numero,
            cliente_whatsapp,
            dia_agendado_fmt,
            loja_nome,
            atendente_apelido,
            atendente_nome_completo,
            tabulacao_agendamento,
            obs_atendente,
            vendedor_apelido,
            vendedor_nome_completo,
            tabulacao_venda,
            obs_vendedor,
            tipo_negociacao,
            banco,
            subsidio,
            tac_valor,
            acao,
            associacao,
            aumento,
            status_tac,
            data_pagamento_tac,
            cliente_rua,
            msg_update_tac,
        ]
        writer.writerow(row)

    # Escreve o conteúdo do buffer na resposta HTTP, codificado corretamente
    response.write(buffer.getvalue().encode('utf-8-sig')) # Usar encode aqui garante a codificação
    buffer.close() # Fecha o buffer
    return response







# ==============================================================================
# API VIEW - DASHBOARD DATA
# ==============================================================================
# Esta view fornece os dados agregados necessários para popular o dashboard do INSS.


@verificar_autenticacao
@check_access(departamento='INSS', nivel_minimo='ESTAGIO')
def api_get_dashboard(request, periodo='mes'):
    """
    Fornece dados agregados para popular o dashboard do INSS.
    Parâmetro 'periodo': 'dia', 'semana', 'mes' ou 'meta'.
    """
    try:
        print(f"----- api_get_dashboard chamado por {request.user.username}, periodo={periodo} -----")
        hoje = timezone.now().date()
        now_dt = timezone.now()
        print(f"Data de hoje: {hoje}, now_dt: {now_dt}")

        # 1) DETERMINAR intervalo [data_inicio, data_fim]
        if periodo == 'dia':
            di = df = hoje
        elif periodo == 'semana':
            di = hoje - timedelta(days=hoje.weekday())
            df = di + timedelta(days=6)
        elif periodo == 'mes':
            di = hoje.replace(day=1)
            try:
                df = (hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1))
            except ValueError:
                df = hoje.replace(day=31, month=12)
        elif periodo == 'meta':
            meta = RegisterMeta.objects.filter(
                categoria='SETOR', status=True,
                data_inicio__date__lte=hoje, data_fim__date__gte=hoje,
                setor__nome='INSS'
            ).order_by('-data_inicio').first()
            if meta:
                di = meta.data_inicio.date()
                df = meta.data_fim.date()
            else:
                print("Nenhuma meta INSS ativa — caindo para 'mes'")
                periodo = 'mes'
                di = hoje.replace(day=1)
                try:
                    df = (hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1))
                except ValueError:
                    df = hoje.replace(day=31, month=12)
        else:
            print(f"Período inválido '{periodo}' — usando 'mes'")
            periodo = 'mes'
            di = hoje.replace(day=1)
            try:
                df = (hoje.replace(day=1, month=hoje.month + 1) - timedelta(days=1))
            except ValueError:
                df = hoje.replace(day=31, month=12)

        # 2) CONVERTER para datetimes
        def to_dt(d, start=True):
            t = time.min if start else time.max
            dt = datetime.combine(d, t)
            return timezone.make_aware(dt) if settings.USE_TZ else dt

        start_dt = to_dt(di, start=True)
        end_dt   = to_dt(df, start=False)
        print(f"Intervalo usado: {start_dt} — {end_dt} ({periodo})")

        # 3) AGENDAMENTOS
        qs_ag = Agendamento.objects.filter(dia_agendado__range=[start_dt, end_dt])
        total_ag = qs_ag.count()
        confirmados = qs_ag.filter(tabulacao_agendamento='CONFIRMADO').count()
        print(f"Total agendamentos: {total_ag}, Confirmados: {confirmados}")

        # 4) PRESENÇAS / FINALIZADOS
        qs_pres = PresencaLoja.objects.filter(
            data_presenca__range=[start_dt, end_dt],
            agendamento__dia_agendado__range=[start_dt, end_dt]
        )
        finalizados = qs_pres.exclude(
            Q(tabulacao_venda=PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR) |
            Q(tabulacao_venda=PresencaLoja.TabulacaoVendaChoices.PENDENTE) |
            Q(tabulacao_venda__isnull=True)
        ).count()
        atrasados = qs_ag.filter(
            dia_agendado__lt=now_dt,
            presenca__isnull=True
        ).count()
        print(f"Finalizados: {finalizados}, Atrasados: {atrasados}")

        # 5) EFETIVIDADE POR LOJA
        lojas_ids = qs_ag.values_list('loja_id', flat=True).distinct()
        lojas = {loja.id: loja for loja in Loja.objects.filter(id__in=lojas_ids)}

        ag_por_loja = qs_ag.values('loja_id').annotate(total=Count('id'))
        pres_por_loja = qs_pres.values('agendamento__loja_id').annotate(total=Count('id'))
        fech_por_loja = qs_pres.filter(
            tabulacao_venda=PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO
        ).values('agendamento__loja_id').annotate(total=Count('id'))

        ag_map = {i['loja_id']: i['total'] for i in ag_por_loja}
        pres_map = {i['agendamento__loja_id']: i['total'] for i in pres_por_loja}
        fech_map = {i['agendamento__loja_id']: i['total'] for i in fech_por_loja}

        efetividade_lojas = []
        tot_pres, tot_fech = 0, 0
        for loja_id, tot_ag in ag_map.items():
            loj = lojas.get(loja_id)
            if not loj: continue
            p = pres_map.get(loja_id, 0)
            f = fech_map.get(loja_id, 0)
            tot_pres += p
            tot_fech += f
            cmp = (Decimal(p) / tot_ag * 100) if tot_ag else Decimal(0)
            fe = (Decimal(f) / p * 100) if p else Decimal(0)
            nome = loj.nome.split(' - ')[-1] if ' - ' in loj.nome else loj.nome
            efetividade_lojas.append({
                'loja_nome': nome,
                'comparecimento': f"{cmp:.2f}%",
                'fechamento':      f"{fe:.2f}%"
            })
        efetividade_lojas.sort(key=lambda x: x['loja_nome'])
        efetividade_geral = (tot_fech / tot_pres * 100) if tot_pres else Decimal(0)

        # 6) SITUAÇÃO TAC
        qs_tac = PresencaLoja.objects.filter(
            data_presenca__range=[start_dt, end_dt],
            valor_tac__isnull=False, valor_tac__gt=0
        )
        vals = list(qs_tac.values_list('valor_tac', flat=True))
        tac_m = (sum(vals) / len(vals)) if vals else Decimal(0)
        tac_min = min(vals) if vals else Decimal(0)
        tac_max = max(vals) if vals else Decimal(0)

        ultimas = qs_tac.select_related(
            'agendamento__cliente_agendamento',
            'agendamento__loja',
            'cliente_agendamento',
            'loja_comp'
        ).order_by('-data_presenca')[:50]
        situacao = []
        for pres in ultimas:
            # compor loja, tipo e cliente
            loja_nome, tipo = 'N/A', 'N/A'
            if pres.agendamento and pres.agendamento.cliente_agendamento:
                tipo = 'Agendado'
                loja_at = pres.loja_comp or pres.agendamento.loja
                loja_nome = loja_at.nome.split(' - ')[-1] if loja_at and ' - ' in loja_at.nome else (loja_at.nome if loja_at else 'N/A')
            elif pres.cliente_agendamento:
                tipo = 'Rua'
                loja_nome = pres.loja_comp.nome.split(' - ')[-1] if pres.loja_comp and ' - ' in pres.loja_comp.nome else (pres.loja_comp.nome if pres.loja_comp else 'N/A')
            situacao.append({
                'loja': loja_nome,
                'tipo': tipo,
                'valor': f"R$ {pres.valor_tac:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'),
                'status': pres.get_status_pagamento_display()
            })

        # 7) MONTAR E RETORNAR
        data = {
            'periodo': {
                'inicio': di.strftime("%d/%m/%Y"),
                'fim':    df.strftime("%d/%m/%Y"),
                'tipo':   periodo
            },
            'metricas_agendamentos': {
                'total': total_ag,
                'confirmados': confirmados,
                'finalizados': finalizados,
                'atrasados': atrasados
            },
            'metricas_financeiras': {
                'tac_medio':    f"R$ {tac_m:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'),
                'tac_menor':    f"R$ {tac_min:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'),
                'tac_maior':    f"R$ {tac_max:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'),
                'efetividade_geral': f"{efetividade_geral:.2f}%"
            },
            'efetividade_loja': efetividade_lojas,
            'situacao_tac':    situacao
        }
        print("api_get_dashboard retornando com sucesso.")
        return JsonResponse(data)

    except Exception as e:
        print(f"Erro em api_get_dashboard: {e}")
        print(traceback.format_exc())
        # Retorna estrutura padrão de erro para o frontend
        return JsonResponse({
            'error': f"Erro ao processar dashboard: {str(e)}",
            'periodo': {'inicio': '', 'fim': '', 'tipo': periodo},
            'metricas_agendamentos': {'total': 0, 'confirmados': 0, 'finalizados': 0, 'atrasados': 0},
            'metricas_financeiras': {'tac_medio': 'R$ 0,00', 'tac_menor': 'R$ 0,00', 'tac_maior': 'R$ 0,00', 'efetividade_geral': '0%'},
            'efetividade_loja': [],
            'situacao_tac': []
        }, status=500)



# -------------------------------------------
# FIM TEMPLATE DASHBOARD
# -------------------------------------------



# ==============================================================================
# VIEWS DE RENDERIZAÇÃO DE PÁGINAS HTML (Templates)
# ==============================================================================
# Nota: Manter esta seção conforme estrutura atual para renderização de templates.

# Acesso permitido para usuários logados que são superusuários ou pertencem ao departamento INSS.
# O nível 'ESTAGIO' é o mais baixo, garantindo que qualquer membro do INSS possa acessar.




