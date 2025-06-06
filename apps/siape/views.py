# Python built-in imports
import calendar
import csv
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

# Third party imports
import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery, Sum, Avg, Max, Min
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.core.exceptions import FieldError # <-- Import FieldError
from django.core.serializers.json import DjangoJSONEncoder

# Local imports
# É recomendado importar explicitamente os modelos necessários em vez de usar '*'
# Adicione outros modelos de .models, apps.inss.models e apps.funcionarios.models se forem usados neste arquivo.
from apps.funcionarios.models import *
from apps.inss.models import *
from custom_tags_app.permissions import *
from setup.utils import *
from .models import *
from apps.funcionarios.models import Setor # <-- Adiciona a importação do Setor

from custom_tags_app.templatetags.permissionsacess import controle_acess

# Configurando o logger para registrar atividades e erros no sistema
logger = logging.getLogger(__name__)


# renderização de páginas

@login_required
@controle_acess('SCT16')   # 16 – SIAPE | CONSULTA CLIENTE
def render_consulta_cliente(request):
    """
    Renderiza a página base de consulta de cliente.
    """
    logger.debug("Iniciando render_consulta_cliente")
    return render(request, 'siape/forms/consulta_cliente.html')

@login_required
@controle_acess('SCT17')   # 17 – SIAPE | CAMPANHAS
def render_campanha_Siape(request):
    logger.debug("Iniciando render_campanha_Siape")
    return render(request, 'apps/siape/forms/campanhas_consulta_siape.html')

@login_required
@controle_acess('SCT19')   # 19 – SIAPE | FINANCEIRO
def render_financeiro(request):
    """
    Renderiza a página de financeiro do SIAPE.
    """
    logger.debug("Iniciando render_financeiro")
    return render(request, 'apps/siape/forms/financeiro.html')

@login_required
@controle_acess('SCT18')   # 18 – SIAPE | RANKING
def render_ranking(request):
    # Apenas renderiza o template; os dados serão obtidos via API 🚀
    logger.debug("Iniciando render_ranking")
    return render(request, 'siape/ranking.html')

# fim renderização de paginas


def normalize_cpf(cpf):
    """Remove caracteres não numéricos do CPF e retorna apenas os 11 dígitos."""
    if cpf is None:
        return None
    
    if not isinstance(cpf, str):
        cpf = str(cpf)
    
    # Remove caracteres não numéricos (espaços, pontos, traços, etc)
    cpf_digits = ''.join(filter(str.isdigit, cpf))
    
    # Tenta preencher com zeros à esquerda se o CPF tiver menos de 11 dígitos
    if len(cpf_digits) > 0 and len(cpf_digits) < 11:
        cpf_digits = cpf_digits.zfill(11)
        print(f"CPF ajustado com zeros à esquerda: {cpf} -> {cpf_digits}")
    
    # Verifica se tem 11 dígitos
    if len(cpf_digits) == 11:
        return cpf_digits
    else:
        print(f"CPF inválido: {cpf}. Deve conter 11 dígitos.")
        return None

def clean_text_field(value, max_length=None):
    """Limpa campos de texto, removendo espaços extras e limitando tamanho."""
    if value is None:
        return value
    
    # Converte para string se não for
    if not isinstance(value, str):
        value = str(value)
    
    # Remove espaços em branco no início e fim
    value = value.strip()
    
    # Limita o tamanho se especificado
    if max_length and len(value) > max_length:
        value = value[:max_length]
        
    return value

def parse_float(value):
    """
    Converte um valor string para float, tratando diferentes formatos de número
    """
    try:
        # Se já for float, retorna o valor
        if isinstance(value, float):
            return value
            
        # Remove espaços em branco e verifica se está vazio
        if not value or str(value).strip() in ['', ' ', '-']:
            return 0.0
            
        # Converte para string e substitui vírgula por ponto
        value_str = str(value).strip().replace(',', '.')
        
        # Remove caracteres não numéricos (exceto ponto e sinal negativo)
        value_str = ''.join(c for c in value_str if c.isdigit() or c in '.-')
        
        return float(value_str)
    except (ValueError, TypeError) as e:
        print(f"Aviso: Valor inválido '{value}' convertido para 0.0: {str(e)}")
        return 0.0

def parse_int(value):
    """
    Converte um valor para inteiro puro
    """
    try:
        # Se for float, converte para inteiro
        if isinstance(value, float):
            return int(value)
            
        # Se for string vazia ou traço
        if not value or str(value).strip() in ['', '-']:
            return 0
            
        # Remove espaços e vírgulas
        value_clean = str(value).strip().replace(',', '')
        
        # Converte para inteiro
        return int(float(value_clean))
        
    except (ValueError, TypeError) as e:
        print(f"Aviso: Valor inválido '{value}' convertido para 0: {str(e)}")
        return 0

def parse_valor_br(value):
    """
    Converte um valor monetário em formato brasileiro para Decimal.
    
    Exemplos:
      "R$ 1.234,56" -> Decimal('1234.56')
      "4780,24"     -> Decimal('4780.24')
    """
    if value is None:
        return Decimal('0.00')

    # Se já for numérico, converte direto
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    s = str(value).strip()
    if not s or s.lower() in ('nan', 'none'):
        return Decimal('0.00')

    # Remove tudo que não é dígito, vírgula, ponto ou sinal de menos
    s = re.sub(r'[^\d,.-]', '', s)

    # Se houver vírgula, considera última vírgula como separador decimal
    if ',' in s:
        inteiro, frac = s.rsplit(',', 1)
        inteiro = inteiro.replace('.', '')  # remove pontos de milhar
        s = f"{inteiro}.{frac}"
    else:
        # sem vírgula, apenas remove pontos de milhar
        s = s.replace('.', '')

    # Garante formato "-1234.56" ou "1234.56"
    try:
        return Decimal(s)
    except InvalidOperation:
        print(f"⚠️ Erro ao converter valor '{value}' para Decimal.")
        return Decimal('0.00')

def parse_date(value):
    """Converte uma string de data para objeto datetime ou None se inválida."""
    if not value:
        return None
        
    try:
        # Primeiro tenta o formato DD/MM/YYYY
        if isinstance(value, str) and '/' in value:
            parts = value.split('/')
            if len(parts) == 3:
                day, month, year = parts
                return datetime(int(year), int(month), int(day))
                
        # Se não for possível, tenta dateutil parser
        return parse(value)
    except:
        return None  # Agora corretamente indentado

def format_currency(value):
    """Formata o valor para o padrão '1.000,00'."""
    if value is None:
        value = Decimal('0.00')
    value = Decimal(value)
    formatted_value = f'{value:,.2f}'.replace('.', 'X').replace(',', '.').replace('X', ',')
    print(f"Valor formatado: {formatted_value}")
    return formatted_value

# =============================================================================== v2

# ===== INICIO CONSULTA CLIENTE ==============================================


def api_get_ficha_cliente(request):
    """
    API que retorna os dados da ficha de um cliente em formato JSON,
    considerando apenas os débitos associados a campanhas ativas e com prazo_restante > 0.
    """
    print("🔍 [api_get_ficha_cliente] Iniciando busca de ficha do cliente")
    
    if request.method != 'GET':
        print("❌ [api_get_ficha_cliente] Método não permitido:", request.method)
        return JsonResponse({'erro': 'Método não permitido. Use GET.'}, status=405)

    cpf = request.GET.get('cpf')
    print(f"🔍 [api_get_ficha_cliente] CPF recebido: {cpf}")
    
    if not cpf:
        print("❌ [api_get_ficha_cliente] CPF não fornecido")
        return JsonResponse({'erro': 'CPF não fornecido.'}, status=400)

    # Normaliza o CPF (supondo que a função normalize_cpf já esteja implementada)
    cpf_normalizado = normalize_cpf(cpf)
    print(f"🔍 [api_get_ficha_cliente] CPF normalizado: {cpf_normalizado}")
    
    if not cpf_normalizado:
        print("❌ [api_get_ficha_cliente] CPF inválido após normalização")
        return JsonResponse({'erro': 'CPF inválido.'}, status=400)

    # Busca o cliente pelo CPF normalizado
    print(f"🔍 [api_get_ficha_cliente] Buscando cliente com CPF: {cpf_normalizado}")
    cliente = Cliente.objects.filter(cpf=cpf_normalizado).first()
    
    if not cliente:
        print("❌ [api_get_ficha_cliente] Cliente não encontrado")
        return JsonResponse({'erro': 'Cliente não encontrado.'}, status=404)

    print(f"✅ [api_get_ficha_cliente] Cliente encontrado: {cliente.nome}")
    
    # Dados do cliente (informações pessoais e financeiras)
    cliente_data = {
        'id': cliente.id,
        'nome': cliente.nome,
        'cpf': cliente.cpf,
        'uf': cliente.uf,
        'rjur': cliente.rjur,
        'situacao_funcional': cliente.situacao_funcional,
        'renda_bruta': str(cliente.renda_bruta) if cliente.renda_bruta is not None else None,
        'bruta_5': str(cliente.bruta_5) if cliente.bruta_5 is not None else None,
        'util_5': str(cliente.util_5) if cliente.util_5 is not None else None,
        'saldo_5': str(cliente.saldo_5) if cliente.saldo_5 is not None else None,
        'brutaBeneficio_5': str(cliente.brutaBeneficio_5) if cliente.brutaBeneficio_5 is not None else None,
        'utilBeneficio_5': str(cliente.utilBeneficio_5) if cliente.utilBeneficio_5 is not None else None,
        'saldoBeneficio_5': str(cliente.saldoBeneficio_5) if cliente.saldoBeneficio_5 is not None else None,
        'bruta_35': str(cliente.bruta_35) if cliente.bruta_35 is not None else None,
        'util_35': str(cliente.util_35) if cliente.util_35 is not None else None,
        'saldo_35': str(cliente.saldo_35) if cliente.saldo_35 is not None else None,
        'total_util': str(cliente.total_util) if cliente.total_util is not None else None,
        'total_saldo': str(cliente.total_saldo) if cliente.total_saldo is not None else None,
    }

    # Filtra os débitos do cliente associados a campanhas ativas e com prazo_restante > 0
    print(f"🔍 [api_get_ficha_cliente] Buscando débitos para o cliente ID: {cliente.id}")
    debitos = Debito.objects.filter(cliente=cliente, campanha__status=True, prazo_restante__gt=0).select_related('campanha')
    print(f"✅ [api_get_ficha_cliente] Encontrados {debitos.count()} débitos ativos")
    
    lista_debitos = []
    for d in debitos:
        print(f"📋 [api_get_ficha_cliente] Processando débito: {d.num_contrato} - Campanha: {d.campanha.nome if d.campanha else 'N/A'}")
        lista_debitos.append({
            'matricula': d.matricula,
            'banco': d.banco,
            'orgao': d.orgao,
            'rebrica': d.rebrica,
            'parcela': str(d.parcela) if d.parcela is not None else None,
            'prazo_restante': d.prazo_restante,
            'tipo_contrato': d.tipo_contrato,
            'num_contrato': d.num_contrato,
            # Incluindo dados da campanha associada ao débito para referência
            'campanha': {
                'nome': d.campanha.nome,
                'data_criacao': d.campanha.data_criacao.strftime("%Y-%m-%d %H:%M:%S") if d.campanha.data_criacao else None,
                'setor': d.campanha.setor.nome if d.campanha.setor else 'Sem Setor', # Alterado de departamento para setor
                'status': d.campanha.status,
            },
        })

    print("✅ [api_get_ficha_cliente] Retornando dados completos do cliente e débitos")
    return JsonResponse({
        'cliente': cliente_data,
        'debitos': lista_debitos
    })


# ======= FIM CONSULTA CLIENTE =======





























# =============================================================================== v2



# ===== INÍCIO DA SEÇÃO DE FICHA CLIENTE =====

# def get_ficha_cliente(request, cpf):
    """
    Obtém os dados da ficha do cliente com base no CPF fornecido e renderiza a página.
    """
    print(f"Iniciando get_ficha_cliente para CPF: {cpf}")
    
    # Normaliza o CPF
    cpf_normalizado = normalize_cpf(cpf)
    if not cpf_normalizado:
        return render(request, 'siape/error.html', {'message': 'CPF inválido.'})

    # Obtém o cliente pelo CPF, ou retorna um erro 404 se não encontrado
    cliente = get_object_or_404(Cliente, cpf=cpf_normalizado)
    print(f"Cliente encontrado: {cliente.nome}")

    # Dicionário com os dados do cliente
    cliente_data = {
        'nome': cliente.nome,
        'cpf': cliente.cpf,
        'uf': cliente.uf,
        'upag': cliente.upag,
        'situacao_funcional': cliente.situacao_funcional,
        'rjur': cliente.rjur,
        'data_nascimento': cliente.data_nascimento,
        'sexo': cliente.sexo,
        'rf_situacao': cliente.rf_situacao,
        'siape_tipo_siape': cliente.siape_tipo_siape,
        'siape_qtd_matriculas': cliente.siape_qtd_matriculas,
        'siape_qtd_contratos': cliente.siape_qtd_contratos,
    }
    print("Dados do cliente coletados")

    # Obtém as informações pessoais mais recentes do cliente
    try:
        info_pessoal = cliente.informacoes_pessoais.latest('data_envio')
        info_pessoal_data = {
            'fne_celular_1': info_pessoal.fne_celular_1,
            'fne_celular_2': info_pessoal.fne_celular_2,
            'end_cidade_1': info_pessoal.end_cidade_1,
            'email_1': info_pessoal.email_1,
            'email_2': info_pessoal.email_2,
            'email_3': info_pessoal.email_3,
        }
        print("Informações pessoais coletadas")
    except InformacoesPessoais.DoesNotExist:
        info_pessoal_data = {}
        print("Nenhuma informação pessoal encontrada")

    # Obtém o débito/margem mais recente para os cards (apenas de campanhas ativas)
    debito_recente = DebitoMargem.objects.filter(
        cliente=cliente,
        campanha__status=True
    ).first()
    
    cards_data = {
        'saldo_5': debito_recente.saldo_5 if debito_recente else Decimal('0.00'),
        'benef_saldo_5': debito_recente.benef_saldo_5 if debito_recente else Decimal('0.00')
    }
    print(f"Dados dos cards coletados: Saldo 5 = {cards_data['saldo_5']}, Benef Saldo 5 = {cards_data['benef_saldo_5']}")

    # Filtra os débitos e margens associados ao cliente com prazo maior que zero e campanha ativa
    debitos_margens = DebitoMargem.objects.filter(
        cliente=cliente, 
        prazo__gt=0,
        campanha__status=True
    )
    print(f"Total de débitos/margens encontrados (apenas campanhas ativas): {debitos_margens.count()}")

    debitos_margens_data = []
    for debito_margem in debitos_margens:
        # Cálculo do saldo devedor
        pmt = float(debito_margem.pmt)
        prazo = float(debito_margem.prazo)
        pr_pz = pmt * prazo
        
        if prazo < 10:
            porcentagem = 0
        elif 10 <= prazo <= 39:
            porcentagem = 0.1
        elif 40 <= prazo <= 59:
            porcentagem = 0.2
        elif 60 <= prazo <= 71:
            porcentagem = 0.25
        elif 72 <= prazo <= 83:
            porcentagem = 0.3
        elif 84 <= prazo <= 96:
            porcentagem = 0.35
        else:
            porcentagem = 0
        
        desconto = pr_pz * porcentagem
        saldo_devedor = round(pr_pz - desconto, 2)
        
        # Cálculo da margem
        margem = round(float(debito_margem.saldo_35), 2)  # Assumindo que saldo_35 representa a margem
        
        debitos_margens_data.append({
            'matricula': debito_margem.matricula,
            'banco': debito_margem.banco,
            'orgao': debito_margem.orgao,
            'pmt': debito_margem.pmt,
            'prazo': debito_margem.prazo,
            'contrato': debito_margem.contrato,
            'margem': margem,
            'saldo_devedor': saldo_devedor,
        })
    print(f"Processados {len(debitos_margens_data)} débitos/margens")

    context = {
        'cliente': cliente_data,
        'informacoes_pessoais': info_pessoal_data,
        'debitos_margens': debitos_margens_data,
        'cards_data': cards_data,  # Adiciona os dados dos cards ao contexto
        'debito_recente': debito_recente,  # Passa o objeto completo também
    }
    
    print("Contexto da ficha do cliente montado")
    print("Renderizando página da ficha do cliente")
    return render(request, 'siape/ficha_cliente.html', context)

# ===== FIM DA SEÇÃO DE FICHA CLIENTE =====

# ===== INÍCIO DA SEÇÃO DOS POSTS =====
def post_addMeta(form_data):
    """Processa a adição de uma nova meta em RegisterMeta."""
    print("\n\n----- Iniciando post_addMeta -----\n")
    mensagem = {'texto': '', 'classe': ''}

    try:
        valor = Decimal(str(form_data.get('valor')).replace(',', '.'))
        tipo = form_data.get('tipo')
        setor = form_data.get('setor') if tipo == 'EQUIPE' else None
        loja = form_data.get('loja') if setor == 'INSS' else None
        
        meta = RegisterMeta.objects.create(
            titulo=form_data.get('titulo'),
            valor=valor,
            tipo=tipo,
            setor=setor,
            loja=loja,
            range_data_inicio=form_data.get('range_data_inicio'),
            range_data_final=form_data.get('range_data_final'),
            status=form_data.get('status') == 'True',
            descricao=form_data.get('descricao')
        )
        
        mensagem['texto'] = f'Meta "{meta.titulo}" adicionada com sucesso!'
        mensagem['classe'] = 'success'
        print(f"Meta adicionada: {meta}")

    except ValueError as e:
        mensagem['texto'] = 'Erro: Valor inválido para a meta'
        mensagem['classe'] = 'error'
        print(f"Erro de valor: {str(e)}")
    except Exception as e:
        mensagem['texto'] = f'Erro ao adicionar meta: {str(e)}'
        mensagem['classe'] = 'error'
        print(f"Erro: {str(e)}")

    return mensagem

def post_addMoney(form_data):
    """Processa a adição de um novo registro em RegisterMoney."""
    print("\n\n----- Iniciando post_addMoney -----\n")
    mensagem = {'texto': '', 'classe': ''}

    try:
        funcionario_id = form_data.get('funcionario_id')
        cpf_cliente = form_data.get('cpf_cliente')
        valor_est = form_data.get('valor_est')
        status = form_data.get('status') == 'True'  # Converte o valor do status para booleano
        data_atual = timezone.now()  # Data e hora atuais

        # Cria um novo registro em RegisterMoney
        registro = RegisterMoney.objects.create(
            funcionario_id=funcionario_id,
            cpf_cliente=cpf_cliente,
            valor_est=valor_est,
            status=status, 
            data=data_atual  # Usando a data e hora atuais
        )
        mensagem['texto'] = 'Registro adicionado com sucesso!'
        mensagem['classe'] = 'success'
        print(f"Registro adicionado: {registro}")

    except Exception as e:
        mensagem['texto'] = f'Erro ao adicionar registro: {str(e)}'
        mensagem['classe'] = 'error'
        print(f"Erro: {str(e)}")

    print(f"Mensagem final: {mensagem}\n\n")
    print("\n----- Finalizando post_addMoney -----\n")
    return mensagem

@login_required
@csrf_exempt
@require_GET
def api_get_info_camp(request):
    """
    API endpoint que retorna a lista de setores e de campanhas já criadas.
    """
    logger.info("----- Iniciando api_get_info_camp -----")
    try:
        # Obter a lista de setores ativos
        setores_queryset = Setor.objects.filter(status=True).select_related('departamento') # Adiciona select_related se precisar do nome do departamento
        setores_list = [
            {
                "id": setor.pk,
                "nome": setor.nome
                # Adicionar nome do departamento se necessário: "nome_completo": f"{setor.nome} - {setor.departamento.nome}"
            }
            for setor in setores_queryset
        ]

        # Obter a lista de campanhas, ordenadas por data de criação (mais recentes primeiro)
        campanhas_queryset = Campanha.objects.all().select_related('setor').order_by('-data_criacao') # Adiciona select_related para setor
        campanhas_list = [
            {
                "id": campanha.pk,
                "nome": campanha.nome,
                "setor": campanha.setor.nome if campanha.setor else None, # Obtém o nome do setor
                "setor_id": campanha.setor.id if campanha.setor else None, # Obtém o ID do setor
                "status": campanha.status,
                "data_criacao": campanha.data_criacao.strftime("%Y-%m-%d %H:%M:%S") if campanha.data_criacao else None,
            }
            for campanha in campanhas_queryset
        ]

        data = {
            "setores": setores_list, # Alterado de "departamentos" para "setores"
            "campanhas": campanhas_list,
        }
        logger.info("Dados obtidos com sucesso para api_get_info_camp.")
        logger.info("----- Finalizando api_get_info_camp -----")
        return JsonResponse(data, status=200)
    except Exception as e:
        logger.error("Erro ao obter informações: " + str(e))
        data = {
            "texto": f"Erro ao obter informações: {str(e)}",
            "classe": "error"
        }
        logger.info("----- Finalizando api_get_info_camp com erro -----")
        return JsonResponse(data, status=500)

@csrf_exempt
@require_POST
@login_required
@transaction.atomic
def api_post_campanha(request):
    """
    API endpoint para criar uma nova campanha.

    Recebe os dados via POST (nome_campanha, setor_id) e retorna uma resposta JSON.
    """
    logger.info("----- Iniciando api_post_campanha -----")

    # Extração dos dados enviados pelo formulário
    nome_campanha = request.POST.get('nome_campanha')
    setor_id = request.POST.get('setor_id') # Alterado de 'departamento' para 'setor_id'

    # Validação dos campos obrigatórios
    if not nome_campanha or not setor_id:
        mensagem = {
            'texto': 'Por favor, preencha o nome da campanha e selecione o setor. ⚠️',
            'classe': 'error'
        }
        logger.error("Erro: Campos obrigatórios (nome_campanha, setor_id) não preenchidos.")
        logger.info("----- Finalizando api_post_campanha -----")
        return JsonResponse(mensagem, status=400)

    try:
        # Busca a instância do Setor
        try:
            setor_obj = Setor.objects.get(pk=int(setor_id))
        except (Setor.DoesNotExist, ValueError):
            mensagem = {
                'texto': 'Setor inválido ou não encontrado. 😞',
                'classe': 'error'
            }
            logger.error(f"Erro: Setor com ID '{setor_id}' inválido ou não encontrado.")
            logger.info("----- Finalizando api_post_campanha -----")
            return JsonResponse(mensagem, status=400)


        # Criação da nova campanha associada ao setor
        campanha = Campanha.objects.create(
            nome=nome_campanha,
            setor=setor_obj, # Associa a instância do Setor
            data_criacao=timezone.now(),
            status=True  # Status padrão: Ativo
        )
        mensagem = {
            'texto': f'Campanha "{campanha.nome}" criada com sucesso para o setor {setor_obj.nome}! 🎉',
            'classe': 'success'
        }
        logger.info(f"Campanha criada: {campanha.nome} para Setor ID: {setor_obj.id}")
        logger.info("----- Finalizando api_post_campanha -----")
        return JsonResponse(mensagem, status=201)

    except Exception as e:
        mensagem = {
            'texto': f'Erro ao criar a campanha: {str(e)} 😞',
            'classe': 'error'
        }
        logger.error(f"Erro ao criar a campanha: {str(e)}")
        logger.info("----- Finalizando api_post_campanha -----")
        return JsonResponse(mensagem, status=500)





def parse_json_post_file(request):
    if request.content_type.startswith('multipart/form-data'):
        return request.FILES.get('csv_file'), request.POST.get('campanha_id', '0')
    else:
        return None, None

import time


@csrf_exempt
@require_POST
def api_post_importar_csv(request):
    """
    Importa CSV/XLS via upload de arquivo (multipart/form-data).
    Produz:
      - clientes novos (bulk_create)
      - clientes atualizados (bulk_update)
      - débitos criados (bulk_create)
    """
    print("\n----- Iniciando importação de dados CSV via API -----")
    print(f"Request method: {request.method}")
    print(f"Content type: {request.content_type}")

    # 1) Extrai o arquivo e o ID da campanha do FormData
    csv_file = request.FILES.get('csv_file')
    campanha_id = request.POST.get('campanha_id')
    print(f"Arquivo recebido: {csv_file.name if csv_file else 'Nenhum'}")
    print(f"ID da campanha: {campanha_id}")

    if not csv_file or not campanha_id:
        print("Erro: csv_file ou campanha_id não fornecidos")
        return JsonResponse(
            {'status': 'erro', 'mensagem': 'csv_file e campanha_id são obrigatórios.'},
            status=400
        )

    # 2) Lê o DataFrame (decimal=',' e milhares='.')
    name = csv_file.name.lower()
    print(f"Processando arquivo: {name}")
    
    try:
        if name.endswith('.csv'):
            print("Processando arquivo CSV")
            df = pd.read_csv(
                csv_file,
                encoding='utf-8-sig',
                sep=';',
                decimal=',',
                thousands='.'
            )
        elif name.endswith(('.xls', '.xlsx')):
            print("Processando arquivo Excel")
            df = pd.read_excel(csv_file, dtype=str)
        else:
            raise ValueError("Formato inválido: use .csv, .xls ou .xlsx")
        
        print(f"DataFrame carregado com {len(df)} linhas")
        print("Colunas originais:", df.columns.tolist())
        
    except Exception as e:
        print(f"Erro ao processar arquivo: {str(e)}")
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)

    df.columns = df.columns.str.strip()
    rows = df.to_dict(orient='records')
    total_linhas = len(rows)
    print(f"Total de linhas para processar: {total_linhas}")

    # 3) Carrega a campanha
    try:
        print(f"Buscando campanha com ID: {campanha_id}")
        campanha = Campanha.objects.get(pk=int(campanha_id))
        print(f"Campanha encontrada: {campanha.nome}")
    except (Campanha.DoesNotExist, ValueError) as e:
        print(f"Erro ao buscar campanha: {str(e)}")
        return JsonResponse(
            {'status': 'erro', 'mensagem': f"Campanha {campanha_id} não encontrada."},
            status=404
        )

    # 4) Extrai CPFs únicos
    cpfs_unicos = {
        normalize_cpf(str(r.get('CPF', '')))
        for r in rows
        if normalize_cpf(str(r.get('CPF', '')))
    }
    print(f"CPFs únicos encontrados: {len(cpfs_unicos)}")

    # 5) Busca clientes existentes
    print("Buscando clientes existentes no banco de dados...")
    clientes_existentes = {
        c.cpf: c for c in Cliente.objects.filter(cpf__in=cpfs_unicos)
    }
    print(f"Clientes existentes encontrados: {len(clientes_existentes)}")
    
    criar, atualizar, novos_por_cpf, debitos_info = [], [], {}, []
    print("Iniciando processamento de linhas...")

    # 6) Processa cada linha
    for idx, row in enumerate(rows, start=1):
        try:
            print(f"\nProcessando linha {idx}")
            cpf = normalize_cpf(str(row.get('CPF', '')))
            print(f"CPF processado: {cpf}")
            
            if not cpf:
                raise ValueError(f"CPF inválido na linha {idx}")

            # Cliente
            if cpf in clientes_existentes:
                print(f"Cliente existente encontrado para CPF: {cpf}")
                cli = clientes_existentes[cpf]
            elif cpf in novos_por_cpf:
                print(f"Cliente novo já processado para CPF: {cpf}")
                cli = novos_por_cpf[cpf]
            else:
                print(f"Novo cliente detectado para CPF: {cpf}")
                cli = Cliente(cpf=cpf)
                criar.append(cli)
                novos_por_cpf[cpf] = cli

            # Campos numéricos do Cliente
            print("Atualizando campos do cliente...")
            cli.nome = clean_text_field(get_safe_value(row, 'Nome', ''), 100)
            cli.uf = clean_text_field(get_safe_value(row, 'UF', ''), 2)
            cli.rjur = clean_text_field(get_safe_value(row, 'RJur', ''), 50)
            cli.situacao_funcional = clean_text_field(get_safe_value(row, 'Situacao_Funcional', ''), 50)
            cli.renda_bruta = parse_valor_br(get_safe_value(row, 'Renda_Bruta', '0'))
            cli.bruta_5 = parse_valor_br(get_safe_value(row, 'Bruta_5', '0'))
            cli.util_5 = parse_valor_br(get_safe_value(row, 'Utilizado_5', '0'))
            cli.saldo_5 = parse_valor_br(get_safe_value(row, 'Saldo_5', '0'))
            cli.brutaBeneficio_5 = parse_valor_br(get_safe_value(row, 'Bruta_Beneficio_5', '0'))
            cli.utilBeneficio_5 = parse_valor_br(get_safe_value(row, 'Utilizado_Beneficio_5', '0'))
            cli.saldoBeneficio_5 = parse_valor_br(get_safe_value(row, 'Saldo_Beneficio_5', '0'))
            cli.bruta_35 = parse_valor_br(get_safe_value(row, 'Bruta_35', '0'))
            cli.util_35 = parse_valor_br(get_safe_value(row, 'Utilizado_35', '0'))
            cli.saldo_35 = parse_valor_br(get_safe_value(row, 'Saldo_35', '0'))
            cli.total_util = parse_valor_br(get_safe_value(row, 'Total_Utilizado', '0'))
            cli.total_saldo = parse_valor_br(get_safe_value(row, 'Total_Saldo', '0'))

            if getattr(cli, 'pk', None):
                print("Cliente marcado para atualização")
                atualizar.append(cli)

            # Débito
            print("Criando informações de débito...")
            debitos_info.append({
                'cpf': cpf,
                'banco': clean_text_field(get_safe_value(row, 'Banco', ''), 100),
                'matricula': clean_text_field(get_safe_value(row, 'Matricula', ''), 50),
                'orgao': clean_text_field(get_safe_value(row, 'Orgao', ''), 50),
                'rebrica': clean_text_field(get_safe_value(row, 'Rebrica', ''), 50), # Adicionado campo Rebrica
                'parcela': parse_valor_br(get_safe_value(row, 'Parcela', '0')),
                'prazo_restante': parse_int(get_safe_value(row, 'Prazo_Restante', '0')),
                'tipo_contrato': clean_text_field(get_safe_value(row, 'Tipo_de_Contrato', ''), 50),
                'num_contrato': clean_text_field(get_safe_value(row, 'Numero_do_Contrato', ''), 50),
            })
            
        except Exception as e:
            print(f"[Linha {idx}] erro: {e}")
            continue

    # 7) Salva tudo em transação
    print("\nIniciando transação no banco de dados...")
    with transaction.atomic():
        if criar:
            print(f"Criando {len(criar)} novos clientes...")
            Cliente.objects.bulk_create(criar, batch_size=100)
        
        if atualizar:
            print(f"Atualizando {len(atualizar)} clientes existentes...")
            Cliente.objects.bulk_update(
                atualizar,
                fields=[
                    'nome','uf','rjur','situacao_funcional',
                    'renda_bruta','bruta_5','util_5','saldo_5',
                    'brutaBeneficio_5','utilBeneficio_5','saldoBeneficio_5',
                    'bruta_35','util_35','saldo_35',
                    'total_util','total_saldo'
                ],
                batch_size=100
            )

        todos = Cliente.objects.filter(cpf__in=cpfs_unicos)
        mapa  = {c.cpf: c for c in todos}
        debs  = []
        for info in debitos_info:
            cli = mapa.get(info['cpf'])
            if cli:
                debs.append(Debito(
                    cliente=cli,
                    campanha=campanha,
                    banco=info['banco'],
                    matricula=info['matricula'],
                    orgao=info['orgao'],
                    rebrica=info['rebrica'], # Adicionado campo rebrica
                    parcela=info['parcela'],
                    prazo_restante=info['prazo_restante'],
                    tipo_contrato=info['tipo_contrato'],
                    num_contrato=info['num_contrato'],
                ))
        if debs:
            Debito.objects.bulk_create(debs, batch_size=100)

    print(f"----- Importação concluída -----")

    return JsonResponse({
        'status': 'sucesso',
        'linhas_processadas': total_linhas,
        'clientes_novos':      len(criar),
        'clientes_atualizados':len(atualizar),
        'debitos_criados':     len(debs),
    })


@csrf_exempt
@require_POST
@login_required
@transaction.atomic
def api_post_excluir_debitos_campanha(request):
    """
    API endpoint para excluir todos os débitos associados a uma campanha.
    Recebe o ID da campanha via POST.
    """
    logger.info("----- Iniciando api_post_excluir_debitos_campanha -----")
    mensagem = {'texto': '', 'classe': ''}

    try:
        campanha_id = request.POST.get('campanha_id')
        if not campanha_id:
            logger.error("Erro: ID da campanha não fornecido.")
            mensagem['texto'] = 'ID da campanha não fornecido.'
            mensagem['classe'] = 'error'
            return JsonResponse(mensagem, status=400)

        try:
            campanha_id_int = int(campanha_id)
            campanha = Campanha.objects.get(pk=campanha_id_int)
        except (ValueError, Campanha.DoesNotExist):
            logger.error(f"Erro: Campanha com ID '{campanha_id}' inválido ou não encontrado.")
            mensagem['texto'] = f'Campanha com ID \'{campanha_id}\' inválida ou não encontrada.'
            mensagem['classe'] = 'error'
            return JsonResponse(mensagem, status=404)

        # Excluir débitos associados à campanha
        debitos_excluidos, _ = Debito.objects.filter(campanha=campanha).delete()

        mensagem['texto'] = f'{debitos_excluidos} débitos da campanha "{campanha.nome}" foram excluídos com sucesso! ✅'
        mensagem['classe'] = 'success'
        logger.info(f"{debitos_excluidos} débitos da campanha '{campanha.nome}' (ID: {campanha_id}) excluídos.")
        status_code = 200

    except Exception as e:
        logger.error(f"Erro inesperado ao excluir débitos da campanha: {str(e)}")
        mensagem['texto'] = f'Erro inesperado ao excluir débitos: {str(e)}'
        mensagem['classe'] = 'error'
        status_code = 500

    logger.info("----- Finalizando api_post_excluir_debitos_campanha -----")
    return JsonResponse(mensagem, status=status_code)



# Antes de get_all_forms()
def post_deleteMoney(registro_id):
    """Processa a exclusão de um registro em RegisterMoney."""
    print("\n\n----- Iniciando post_deleteMoney -----\n")
    mensagem = {'texto': '', 'classe': ''}

    try:
        registro = RegisterMoney.objects.get(id=registro_id)
        registro.delete()
        mensagem['texto'] = 'Registro excluído com sucesso!'
        mensagem['classe'] = 'success'
        print(f"Registro excluído: {registro_id}")

    except RegisterMoney.DoesNotExist:
        mensagem['texto'] = 'Registro não encontrado.'
        mensagem['classe'] = 'error'
        print(f"Erro: Registro {registro_id} não encontrado")
    except Exception as e:
        mensagem['texto'] = f'Erro ao excluir registro: {str(e)}'
        mensagem['classe'] = 'error'
        print(f"Erro: {str(e)}")

    print(f"Mensagem final: {mensagem}\n\n")
    print("\n----- Finalizando post_deleteMoney -----\n")
    return mensagem

def post_csv_money(form_data):
    """Processa a importação de registros em RegisterMoney a partir de um arquivo CSV."""
    print("\n\n----- Iniciando post_csv_money -----\n")
    mensagem = {'texto': '', 'classe': ''}

    try:
        # Obtém o arquivo CSV do form_data
        csv_file = form_data.get('csv_file')
        if not csv_file:
            raise ValueError("Nenhum arquivo CSV fornecido.")

        # Lê o arquivo CSV
        df = pd.read_csv(csv_file, sep=';', encoding='utf-8-sig')

        for index, row in df.iterrows():
            funcionario_id = row['funcionario_id']
            cpf_cliente = row['cpf_cliente']
            valor_est = parse_float(row['valor_est'])
            data = parse_date(row['data'])

            # Cria um novo registro em RegisterMoney
            RegisterMoney.objects.create(
                funcionario_id=funcionario_id,
                cpf_cliente=cpf_cliente,
                valor_est=valor_est,
                status=True,
                data=data
            )
            print(f"Registro adicionado: Funcionario ID={funcionario_id}, CPF={cpf_cliente}, Valor={valor_est}")

        mensagem['texto'] = 'Registros importados com sucesso!'
        mensagem['classe'] = 'success'

    except Exception as e:
        mensagem['texto'] = f'Erro ao importar registros: {str(e)}'
        mensagem['classe'] = 'error'
        print(f"Erro: {str(e)}")

    return mensagem

def post_import_situacao(request):
    """
    Processa o arquivo CSV para atualizar a situação funcional dos clientes.
    Formato esperado do CSV:
    cpf_cliente;situacao_funcional
    03418758215;APOSENTADO
    24154571249;APOSENTADO
    """
    print("\n----- Iniciando post_import_situacao -----\n")
    mensagem = {'texto': '', 'classe': ''}
    
    if 'arquivo_situacao' not in request.FILES:
        mensagem['texto'] = 'Nenhum arquivo CSV foi enviado.'
        mensagem['classe'] = 'error'
        print(f"Aviso: {mensagem['texto']}")
        return mensagem

    arquivo = request.FILES['arquivo_situacao']
    print(f"Nome do arquivo: {arquivo.name}")
    print(f"Tamanho do arquivo: {arquivo.size} bytes")
    
    if not arquivo.name.endswith('.csv'):
        mensagem['texto'] = 'O arquivo deve ser um CSV.'
        mensagem['classe'] = 'error'
        print(f"Aviso: {mensagem['texto']}")
        return mensagem

    try:
        # Tenta diferentes encodings e separadores
        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'iso-8859-1']
        separators = [';', ',']
        df = None
        
        for encoding in encodings:
            for sep in separators:
                try:
                    print(f"Tentando ler com encoding {encoding} e separador '{sep}'")
                    df = pd.read_csv(
                        arquivo,
                        encoding=encoding,
                        sep=sep,
                        dtype=str  # Força todos os campos como string
                    )
                    # Verifica se as colunas esperadas existem
                    if 'cpf_cliente' in df.columns and 'situacao_funcional' in df.columns:
                        print(f"Arquivo lido com sucesso usando {encoding} e separador '{sep}'")
                        print(f"Colunas encontradas: {df.columns.tolist()}")
                        break
                    else:
                        print(f"Colunas esperadas não encontradas. Colunas presentes: {df.columns.tolist()}")
                        df = None
                except Exception as e:
                    print(f"Erro ao tentar {encoding} com separador '{sep}': {str(e)}")
                    continue
            if df is not None:
                break

        if df is None:
            raise Exception("Não foi possível ler o arquivo com nenhuma combinação de encoding e separador")

        print(f"Total de linhas no arquivo: {len(df)}")
        print("Primeiras linhas do arquivo:")
        print(df.head())
        
        # Remove espaços em branco
        df['cpf_cliente'] = df['cpf_cliente'].str.strip()
        df['situacao_funcional'] = df['situacao_funcional'].str.strip()
        
        atualizados = 0
        erros = 0
        erros_log = []

        for index, row in df.iterrows():
            try:
                # Normaliza o CPF
                cpf = ''.join(filter(str.isdigit, str(row['cpf_cliente'])))
                if len(cpf) != 11:
                    erro_msg = f"CPF inválido na linha {index + 1}: {row['cpf_cliente']}"
                    erros_log.append(erro_msg)
                    erros += 1
                    print(erro_msg)
                    continue

                situacao = row['situacao_funcional'].upper()
                
                # Atualiza o cliente
                cliente = Cliente.objects.filter(cpf=cpf).first()
                if cliente:
                    cliente.situacao_funcional = situacao
                    cliente.save()
                    atualizados += 1
                    print(f"Cliente {cpf} atualizado com situação: {situacao}")
                else:
                    erro_msg = f"CPF não encontrado: {cpf}"
                    erros_log.append(erro_msg)
                    erros += 1
                    print(erro_msg)
                    
            except Exception as e:
                erro_msg = f"Erro na linha {index + 1}: {str(e)}"
                erros_log.append(erro_msg)
                erros += 1
                print(erro_msg)

        mensagem['texto'] = f'Importação concluída. {atualizados} clientes atualizados, {erros} erros encontrados.'
        mensagem['classe'] = 'success'
        
        if erros_log:
            mensagem['texto'] += "\nErros encontrados:\n" + "\n".join(erros_log)
            mensagem['classe'] = 'warning' if atualizados > 0 else 'error'
            
    except Exception as e:
        mensagem['texto'] = f'Erro ao processar arquivo: {str(e)}'
        mensagem['classe'] = 'error'
        print(f"Erro: {mensagem['texto']}")

    print("\n----- Finalizando post_import_situacao -----\n")
    return mensagem

# ===== FIM DA SEÇÃO DOS POSTS =====


# ===== INÍCIO DA SEÇÃO DE FINANCEIRO =====

@login_required
def api_get_infosiape(request):
    """
    API para fornecer listas de produtos ativos e funcionários do setor SIAPE ativos.
    """
    try:
        # Lista de produtos ativos
        produtos = Produto.objects.filter(ativo=True).values('id', 'nome') # CORRIGIDO: Usar 'ativo' em vez de 'status'

        # Lista de funcionários ativos no setor SIAPE com user_id
        # Assumindo que o nome do setor é 'SIAPE'
        funcionarios_siape = Funcionario.objects.filter(
            status=True,
            setor__nome='SIAPE',
            usuario__isnull=False # Garante que há um usuário Django associado
        ).select_related('usuario', 'setor').values(
            'usuario_id',
            'nome_completo',
            'apelido'
        )

        # Formata a lista de funcionários para incluir nome preferencial e user_id
        funcionarios_list = [
            {
                'user_id': f['usuario_id'],
                'nome_funcionario': f['apelido'] if f['apelido'] else f['nome_completo'].split()[0] # Usa apelido ou primeiro nome
            }
            for f in funcionarios_siape
        ]

        data = {
            'produtos': list(produtos),
            'funcionarios': funcionarios_list,
        }
        return JsonResponse(data)

    except Exception as e:
        # Logar o erro para diagnóstico
        logger.error(f"Erro em api_get_infosiape: {type(e).__name__} - {e}")
        logger.exception("Detalhes do erro em api_get_infosiape:") # Loga o traceback completo
        return JsonResponse({'error': 'Ocorreu um erro ao buscar informações.'}, status=500)


@login_required
def api_get_registrosTac(request):
    """
    API para fornecer dados de registros de TAC (RegisterMoney) para uma tabela.
    Inclui nome do funcionário, nome do cliente, CPF, valor e tipo (baseado no setor).
    Aceita parâmetros GET para filtragem: vendedor_id, cpf, data_inicio, data_fim, tipo.
    """
    try:
        # Obter parâmetros de filtro
        vendedor_id = request.GET.get('vendedor_id')
        cpf_filtro = request.GET.get('cpf')
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        tipo_filtro = request.GET.get('tipo')

        # Query base
        registros_qs = RegisterMoney.objects.select_related('user', 'produto', 'loja').order_by('-data')

        # Aplicar filtros ao queryset
        if vendedor_id:
            registros_qs = registros_qs.filter(user_id=vendedor_id)
        if cpf_filtro:
            cpf_limpo = re.sub(r'\D', '', cpf_filtro)
            if len(cpf_limpo) == 11:
                registros_qs = registros_qs.filter(cpf_cliente=cpf_limpo)
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                registros_qs = registros_qs.filter(data__date__gte=data_inicio) # Filtrar pela parte da data
            except ValueError:
                logger.warning(f"Formato de data inválido para data_inicio: {data_inicio_str}")
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                registros_qs = registros_qs.filter(data__date__lte=data_fim) # Filtrar pela parte da data
            except ValueError:
                logger.warning(f"Formato de data inválido para data_fim: {data_fim_str}")

        # Obter todos os registros filtrados (exceto por tipo ainda)
        registros_filtrados = list(registros_qs)

        # Otimização: Buscar funcionários e clientes uma vez
        user_ids = [reg.user_id for reg in registros_filtrados if reg.user_id]
        cpfs_clientes = [reg.cpf_cliente for reg in registros_filtrados if reg.cpf_cliente]

        funcionarios = Funcionario.objects.filter(
            usuario_id__in=user_ids
        ).select_related('setor', 'usuario').in_bulk(field_name='usuario_id')

        clientes_siape = Cliente.objects.filter(cpf__in=cpfs_clientes).only('nome').in_bulk(field_name='cpf')
        # Assumindo que ClienteAgendamento é o modelo para clientes INSS
        clientes_inss = ClienteAgendamento.objects.filter(cpf__in=cpfs_clientes).only('nome_completo').in_bulk(field_name='cpf')


        data_list = []
        for reg in registros_filtrados:
            nome_funcionario = "Usuário não encontrado"
            tipo = "Outros" # Padrão
            funcionario = funcionarios.get(reg.user_id)

            if funcionario:
                nome_funcionario = funcionario.apelido if funcionario.apelido else funcionario.nome_completo
                if funcionario.setor:
                    # Define o tipo baseado no nome do setor do funcionário
                    setor_nome_upper = funcionario.setor.nome.upper()
                    if setor_nome_upper == 'SIAPE':
                        tipo = 'SIAPE'
                    elif setor_nome_upper == 'INSS':
                        tipo = 'INSS'

            # Aplicar filtro de TIPO aqui, após calcular o tipo
            if tipo_filtro and tipo_filtro != tipo:
                continue # Pula este registro se não corresponder ao tipo filtrado

            # Buscar nome do cliente
            nome_cliente = "Cliente não encontrado"
            cpf_cliente = reg.cpf_cliente
            if cpf_cliente:
                cliente_obj_siape = clientes_siape.get(cpf_cliente)
                if cliente_obj_siape:
                    nome_cliente = cliente_obj_siape.nome
                else:
                    cliente_obj_inss = clientes_inss.get(cpf_cliente)
                    if cliente_obj_inss:
                        nome_cliente = cliente_obj_inss.nome_completo

            data_list.append({
                'id': reg.id,
                'nome_funcionario': nome_funcionario,
                'nome_cliente': nome_cliente or 'Nome não disponível',
                'cpf_cliente': cpf_cliente,
                'valor_tac': reg.valor_est,
                'data': reg.data.strftime('%d/%m/%Y %H:%M:%S') if reg.data else None,
                'tipo': tipo,
                'produto': reg.produto.nome if reg.produto else 'N/A', # Adicionado produto
                'loja': reg.loja.nome if reg.loja else 'N/A', # Adicionado loja
            })

        return JsonResponse({'registros': data_list})

    except Exception as e:
        logger.error(f"Erro em api_get_registrosTac: {type(e).__name__} - {e}")
        logger.exception("Detalhes do erro em api_get_registrosTac:")
        return JsonResponse({'error': 'Ocorreu um erro ao buscar os registros de TAC.'}, status=500)

def api_get_cardstac(request):
    """
    API endpoint para buscar os valores agregados de TAC para os cards do dashboard financeiro.
    Retorna:
        - Total TAC no ano corrente.
        - Total TAC no mês corrente.
        - Total TAC no dia corrente.
        - Meta do mês para o setor SIAPE (se ativa).
    """
    try:
        hoje = timezone.now()
        ano_atual = hoje.year
        mes_atual = hoje.month
        dia_atual = hoje.day

        # 1. Calcular Total TAC Período (Ano)
        inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_ano = hoje.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        total_tac_ano = RegisterMoney.objects.filter(
            data__range=(inicio_ano, fim_ano),
            status=True # Considerando apenas registros ativos
        ).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.00')

        # 2. Calcular Total TAC Mês
        inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Calcula o último dia do mês
        ultimo_dia_mes = calendar.monthrange(ano_atual, mes_atual)[1]
        fim_mes = hoje.replace(day=ultimo_dia_mes, hour=23, minute=59, second=59, microsecond=999999)
        total_tac_mes = RegisterMoney.objects.filter(
            data__range=(inicio_mes, fim_mes),
            status=True
        ).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.00')

        # 3. Calcular Total TAC Dia
        inicio_dia = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_dia = hoje.replace(hour=23, minute=59, second=59, microsecond=999999)
        total_tac_dia = RegisterMoney.objects.filter(
            data__range=(inicio_dia, fim_dia),
            status=True
        ).aggregate(total=Sum('valor_est'))['total'] or Decimal('0.00')

        # 4. Buscar Meta do Mês para SIAPE (direto pelo nome do setor)
        meta_mes_obj = None
        meta_mes_valor = Decimal('0.00')
        try:
            logger.debug("Tentando buscar meta por setor__nome__iexact='SIAPE'")
            meta_mes_obj = RegisterMeta.objects.filter(
                categoria='SETOR',
                setor__nome__iexact='SIAPE', # Busca case-insensitive pelo nome do setor
                status=True,
                data_inicio__lte=hoje,
                data_fim__gte=hoje
            ).first()
            logger.debug(f"Meta encontrada (por nome): {meta_mes_obj}")

            if meta_mes_obj:
                meta_mes_valor = meta_mes_obj.valor if meta_mes_obj.valor else Decimal('0.00')

        except Exception as meta_error:
            logger.error(f"Erro inesperado ao buscar meta do mês para o setor SIAPE: {type(meta_error).__name__} - {meta_error}")
            logger.exception("Detalhes do erro ao buscar meta:")
            # Continua sem a meta, mas loga o erro

        data = {
            'total_tac_periodo': total_tac_ano, # Valor Decimal
            'total_tac_mes': total_tac_mes,     # Valor Decimal
            'total_tac_dia': total_tac_dia,     # Valor Decimal
            'meta_mes': meta_mes_valor,         # Valor Decimal
        }

        return JsonResponse(data)

    except Exception as e:
        # Logar o erro para diagnóstico
        logger.error(f"Erro em api_get_cardstac: {type(e).__name__} - {e}")
        logger.exception("Detalhes do erro em api_get_cardstac:") # Loga o traceback completo
        return JsonResponse({'error': 'Ocorreu um erro ao buscar os dados dos cards.'}, status=500)

@require_POST
@csrf_exempt # Considere remover se o token CSRF for enviado via AJAX para maior segurança.
def api_post_novotac(request):
    """
    API para criar um novo registro financeiro (RegisterMoney) via POST JSON.
    Espera JSON com: cpf_cliente, produto_id, valor_tac, data_pago (YYYY-MM-DD), user_id.
    Associa automaticamente a loja, empresa, departamento, setor e equipe do funcionário.
    """
    try:
        data = json.loads(request.body)
        cpf_cliente = data.get('cpf_cliente')
        produto_id = data.get('produto_id')
        valor_tac_str = data.get('valor_tac')
        data_pago_str = data.get('data_pago') # Formato esperado 'YYYY-MM-DD'
        user_id = data.get('user_id')

        # Validação básica de presença dos campos
        campos_obrigatorios = {
            'cpf_cliente': cpf_cliente,
            'produto_id': produto_id,
            'valor_tac': valor_tac_str,
            'data_pago': data_pago_str,
            'user_id': user_id
        }
        campos_ausentes = [nome for nome, valor in campos_obrigatorios.items() if not valor]
        if campos_ausentes:
            logger.warning(f"Tentativa de criar TAC com campos ausentes: {', '.join(campos_ausentes)}. Dados: {data}")
            return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(campos_ausentes)}'}, status=400)

        # Limpeza e validação do CPF
        cpf_cliente_cleaned = re.sub(r'\D', '', cpf_cliente)
        if len(cpf_cliente_cleaned) != 11:
             logger.warning(f"CPF inválido recebido: {cpf_cliente}")
             return JsonResponse({'error': 'Formato de CPF inválido. Deve conter 11 dígitos.'}, status=400)

        # Validação e conversão do valor_tac
        try:
            valor_tac = Decimal(valor_tac_str)
            if valor_tac < Decimal('0.00'):
                 raise ValueError("Valor TAC não pode ser negativo.")
        except (InvalidOperation, ValueError) as e:
            logger.error(f"Erro ao converter valor_tac '{valor_tac_str}': {e}")
            return JsonResponse({'error': f'Valor TAC inválido: {valor_tac_str}. Use formato numérico com ponto decimal.'}, status=400)

        # Validação e conversão da data_pago
        try:
            # API agora espera YYYY-MM-DD do input type="date"
            data_pago = datetime.strptime(data_pago_str, '%Y-%m-%d').date()
            data_registro = data_pago # Assumindo que o campo 'data' no modelo é DateField ou pode aceitar Date
        except ValueError:
             logger.error(f"Erro ao converter data_pago '{data_pago_str}': Formato inválido.")
             return JsonResponse({'error': "Formato de data inválido. Use 'YYYY-MM-DD'."}, status=400)

        # Busca objetos relacionados (Usuário, Produto, Funcionário e suas associações)
        try:
            user = User.objects.get(pk=user_id)
            produto = Produto.objects.get(pk=produto_id, ativo=True) # Garante que o produto está ativo

            # Busca o funcionário e suas associações organizacionais
            funcionario = None
            loja = None
            empresa = None
            departamento = None
            setor = None
            equipe = None

            try:
                # Busca o funcionário e suas associações organizacionais
                funcionario = Funcionario.objects.select_related(
                    'empresa', 'departamento', 'setor', 'equipe'
                ).filter(
                    usuario=user,
                    status=True  # Garante que o funcionário está ativo
                ).first()

                if not funcionario:
                    logger.warning(f"Usuário {user.username} (ID: {user_id}) não encontrado no cadastro de funcionários ativos.")
                    return JsonResponse({'error': 'Usuário não encontrado no cadastro de funcionários ativos.'}, status=404)

                # Extrai os dados organizacionais do funcionário
                empresa = funcionario.empresa
                departamento = funcionario.departamento
                setor = funcionario.setor
                equipe = funcionario.equipe

                # Log para verificar os dados encontrados
                logger.info(f"Funcionário {user.username} encontrado. Empresa: {empresa}, Depto: {departamento}, Setor: {setor}, Equipe: {equipe}")

            except Exception as func_error:
                logger.error(f"Erro ao buscar dados do funcionário: {type(func_error).__name__} - {func_error}")
                logger.exception("Detalhes do erro na busca de dados do funcionário:")
                return JsonResponse({'error': 'Erro ao buscar dados do funcionário.'}, status=500)

        except User.DoesNotExist:
            logger.error(f"Usuário com ID {user_id} não encontrado.")
            return JsonResponse({'error': f'Usuário com ID {user_id} não encontrado.'}, status=404)
        except Produto.DoesNotExist:
            logger.error(f"Produto com ID {produto_id} não encontrado ou inativo.")
            return JsonResponse({'error': f'Produto com ID {produto_id} não encontrado ou inativo.'}, status=404)
        except Exception as lookup_error:
            logger.error(f"Erro ao buscar User/Produto: {type(lookup_error).__name__} - {lookup_error}")
            logger.exception("Detalhes do erro na busca de objetos relacionados:")
            return JsonResponse({'error': 'Erro ao buscar dados relacionados.'}, status=500)

        # Criação da instância de RegisterMoney com os dados organizacionais
        try:
            novo_registro = RegisterMoney.objects.create(
                user=user,
                empresa=empresa,
                departamento=departamento,
                setor=setor,
                equipe=equipe,
                cpf_cliente=cpf_cliente_cleaned,
                produto=produto,
                valor_est=valor_tac,
                data=data_registro,
                status=True
            )
            logger.info(f"Registro TAC criado com sucesso: ID {novo_registro.id} para User {user.username}")

            return JsonResponse({
                'success': True,
                'message': 'Registro TAC criado com sucesso!',
                'registro_id': novo_registro.id
            }, status=201) # Status 201 Created

        except Exception as create_error:
            logger.error(f"Erro ao criar RegisterMoney: {type(create_error).__name__} - {create_error}")
            logger.exception("Detalhes do erro na criação do registro TAC:")
            return JsonResponse({'error': 'Erro ao salvar o registro no banco de dados.'}, status=500)

    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON da requisição.")
        return JsonResponse({'error': 'Formato JSON inválido no corpo da requisição.'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado em api_post_novotac: {type(e).__name__} - {e}")
        logger.exception("Detalhes do erro inesperado em api_post_novotac:")
        return JsonResponse({'error': 'Ocorreu um erro interno no servidor ao processar a solicitação.'}, status=500)


@require_GET
def api_get_nomecliente(request):
    """
    API para buscar o nome de um cliente pelo CPF.
    Busca primeiro no modelo Cliente (SIAPE) e depois em ClienteAgendamento (INSS).
    Recebe o parâmetro 'cpf' via GET.
    Retorna JSON {'nome': 'Nome Encontrado'} ou {'nome': 'Não registrado'}.
    """
    print("--- Iniciando api_get_nomecliente ---") # DEBUG
    cpf_param = request.GET.get('cpf')
    print(f"DEBUG: CPF recebido como parâmetro: {cpf_param}") # DEBUG

    if not cpf_param:
        print("DEBUG: Parâmetro CPF ausente.") # DEBUG
        return JsonResponse({'error': 'Parâmetro CPF ausente na requisição.'}, status=400)

    # Limpa o CPF para conter apenas dígitos
    cpf_limpo = re.sub(r'\D', '', cpf_param)
    print(f"DEBUG: CPF limpo: {cpf_limpo}") # DEBUG

    # Valida se o CPF limpo tem 11 dígitos
    if len(cpf_limpo) != 11:
        print(f"DEBUG: CPF limpo ({cpf_limpo}) não tem 11 dígitos. Retornando 'Não registrado'.") # DEBUG
        # Retorna 'Não registrado' para simplificar o tratamento no frontend
        # Alternativa: retornar erro 400
        return JsonResponse({'nome': 'Não registrado'})
        # return JsonResponse({'error': 'CPF inválido. Deve conter 11 dígitos.'}, status=400)

    nome_cliente = 'Não registrado' # Valor padrão
    print(f"DEBUG: Valor inicial de nome_cliente: {nome_cliente}") # DEBUG

    try:
        # 1. Busca no modelo Cliente (SIAPE)
        print(f"DEBUG: Buscando CPF {cpf_limpo} no modelo Cliente (SIAPE)...") # DEBUG
        # Usar first() para obter um objeto ou None, evitando exceção DoesNotExist
        cliente_siape = Cliente.objects.filter(cpf=cpf_limpo).only('nome').first()
        print(f"DEBUG: Resultado da busca no Cliente (SIAPE): {cliente_siape}") # DEBUG
        if cliente_siape:
            # Usa o nome se existir, senão mantém um placeholder ou o padrão
            nome_cliente = cliente_siape.nome if cliente_siape.nome else 'Nome não cadastrado (SIAPE)'
            print(f"DEBUG: Cliente encontrado no SIAPE. Nome: {nome_cliente}") # DEBUG
            return JsonResponse({'nome': nome_cliente})

        # 2. Se não encontrou no SIAPE, busca no modelo ClienteAgendamento (INSS)
        print(f"DEBUG: CPF {cpf_limpo} não encontrado no SIAPE. Buscando no ClienteAgendamento (INSS)...") # DEBUG
        cliente_inss = ClienteAgendamento.objects.filter(cpf=cpf_limpo).only('nome_completo').first()
        print(f"DEBUG: Resultado da busca no ClienteAgendamento (INSS): {cliente_inss}") # DEBUG
        if cliente_inss:
            nome_cliente = cliente_inss.nome_completo if cliente_inss.nome_completo else 'Nome não cadastrado (INSS)'
            print(f"DEBUG: Cliente encontrado no INSS. Nome: {nome_cliente}") # DEBUG
            return JsonResponse({'nome': nome_cliente})

        # 3. Se não encontrou em nenhum modelo, retorna o valor padrão 'Não registrado'
        print(f"DEBUG: CPF {cpf_limpo} não encontrado em nenhum modelo. Retornando '{nome_cliente}'.") # DEBUG
        return JsonResponse({'nome': nome_cliente})

    except Exception as e:
        # Logar o erro em produção
        print(f"!!! ERRO !!! Erro ao buscar nome do cliente por CPF ({cpf_limpo}): {e}") # DEBUG
        # Retorna 'Não registrado' para evitar quebrar o frontend em caso de erro inesperado
        print("DEBUG: Retornando 'Não registrado' devido a exceção.") # DEBUG
        return JsonResponse({'nome': 'Não registrado'})
        # Alternativa: retornar um erro 500 mais explícito
        # return JsonResponse({'error': 'Erro interno ao buscar nome do cliente.'}, status=500)





# ===== FIM DA SEÇÃO DE FINANCEIRO =====


# ===== INÍCIO DA SEÇÃO DE RANKING =====


from decimal import Decimal, InvalidOperation
from datetime import datetime, time, timedelta
import calendar
from django.utils import timezone
from django.db.models import Sum

# ===== INÍCIO DA SEÇÃO DE RANKING =====

def api_cards(request, periodo='mes'):
    hoje = timezone.now().date()

    # --- Carrega metas ---
    meta_geral = RegisterMeta.objects.filter(
        categoria='GERAL', status=True,
        data_inicio__lte=hoje, data_fim__gte=hoje
    ).first()
    meta_empresa = RegisterMeta.objects.filter(
        categoria='EMPRESA', status=True,
        data_inicio__lte=hoje, data_fim__gte=hoje
    ).first()
    meta_siape = RegisterMeta.objects.filter(
        categoria='SETOR', status=True,
        data_inicio__lte=hoje, data_fim__gte=hoje,
        setor__nome='SIAPE'
    ).first()

    # --- Define períodos ---
    def period_bounds(meta, default_month=True):
        if meta:
            start = datetime.combine(meta.data_inicio, time.min)
            end   = datetime.combine(meta.data_fim,    time.max)
        elif default_month:
            first = hoje.replace(day=1)
            last  = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])
            start = datetime.combine(first, time.min)
            end   = datetime.combine(last,  time.max)
        else:
            start = end = None
        return start, end

    p0_start, p0_end = period_bounds(meta_geral)
    p1_start, p1_end = period_bounds(meta_empresa)
    p2_start, p2_end = period_bounds(meta_siape)

    # --- Soma helper ---
    def sum_range(model_qs):
        tot = model_qs.aggregate(
            total=Sum('valor_est')
        )['total'] or Decimal('0')
        return tot

    # --- Meta Geral ---
    valores_geral = RegisterMoney.objects.filter(
        data__range=[p0_start, p0_end]
    )
    faturamento_total = sum((Decimal(str(v.valor_est)) for v in valores_geral if v.valor_est), Decimal('0'))
    percentual_geral = (
        round((faturamento_total / meta_geral.valor) * 100, 2)
        if meta_geral and meta_geral.valor and meta_geral.valor > 0 else 0
    )

    # --- Meta Empresa (exclui franquias) ---
    qs_emp_base = RegisterMoney.objects.filter(
        data__range=[p1_start, p1_end],
        status=True
    )
    total_emp = sum((Decimal(str(v.valor_est)) for v in qs_emp_base if v.valor_est), Decimal('0'))
    # subtrai o faturamento das franquias
    franquias_emp = sum((Decimal(str(v.valor_est)) for v in qs_emp_base.filter(loja__franquia=True) if v.valor_est), Decimal('0'))
    faturamento_empresa = total_emp - franquias_emp

    percentual_empresa = (
        round((faturamento_empresa / meta_empresa.valor) * 100, 2)
        if meta_empresa and meta_empresa.valor and meta_empresa.valor > 0 else 0
    )
    valor_meta_empresa = (
        format_currency(meta_empresa.valor) if meta_empresa and meta_empresa.valor else "R$ 0,00"
    )

    # --- Meta Siape ---
    qs_siape = RegisterMoney.objects.filter(
        data__range=[p2_start, p2_end],
        setor__nome='SIAPE'
    )
    faturamento_siape = sum((Decimal(str(v.valor_est)) for v in qs_siape if v.valor_est), Decimal('0'))
    percentual_siape = (
        round((faturamento_siape / meta_siape.valor) * 100, 2)
        if meta_siape and meta_siape.valor and meta_siape.valor > 0 else 0
    )

    # --- Monta resposta ---
    data = {
        'meta_geral': {
            'valor_total': format_currency(faturamento_total),
            'percentual': percentual_geral,
            'valor_meta': format_currency(meta_geral.valor) if meta_geral and meta_geral.valor else "R$ 0,00"
        },
        'meta_empresa': {
            'valor_total': format_currency(faturamento_empresa),
            'percentual': percentual_empresa,
            'valor_meta': valor_meta_empresa
        },
        'meta_siape': {
            'valor_total': format_currency(faturamento_siape),
            'percentual': percentual_siape,
            'valor_meta': format_currency(meta_siape.valor) if meta_siape and meta_siape.valor else "R$ 0,00"
        }
    }
    return JsonResponse(data)


def api_podium(request, periodo='mes'):
    hoje = timezone.now().date()

    meta_siape = RegisterMeta.objects.filter(
        status=True, categoria='SETOR',
        setor__nome='SIAPE',
        data_inicio__lte=hoje, data_fim__gte=hoje
    ).first()

    if meta_siape:
        primeiro_dia = meta_siape.data_inicio
        ultimo_dia   = meta_siape.data_fim
    else:
        primeiro_dia = hoje.replace(day=1)
        ultimo_mes   = calendar.monthrange(hoje.year, hoje.month)[1]
        ultimo_dia   = hoje.replace(day=ultimo_mes)

    podium_query = RegisterMoney.objects.filter(
        data__date__range=[primeiro_dia, ultimo_dia],
        setor__nome='SIAPE', user__isnull=False, status=True
    ).values('user_id').annotate(
        total_fechamentos=Sum('valor_est')
    ).filter(
        total_fechamentos__gt=Decimal('0.00')
    ).order_by('-total_fechamentos')[:5]

    user_ids = [x['user_id'] for x in podium_query]
    funcionarios_map = Funcionario.objects.filter(
        usuario_id__in=user_ids
    ).select_related('usuario').in_bulk(field_name='usuario_id')

    podium = []
    for pos, item in enumerate(podium_query, start=1):
        user_id = item['user_id']
        func = funcionarios_map.get(user_id)
        if func:
            nome = func.apelido or func.nome_completo.split()[0]
            logo = func.foto.url if func.foto else '/static/img/default-store.png'
            total = item['total_fechamentos']
        else:
            nome, logo, total = f'Usuário {user_id}', '/static/img/default-store.png', item['total_fechamentos']

        podium.append({
            'id': func.id if func else None,
            'user_id': user_id,
            'nome': nome,
            'logo': logo,
            'total_fechamentos': format_currency(total),
            'posicao': pos
        })

    return JsonResponse({
        'podium': podium,
        'periodo': {
            'inicio': primeiro_dia.strftime('%Y-%m-%d'),
            'fim':    ultimo_dia.strftime('%Y-%m-%d')
        }
    })




import io
import csv
import zipfile
from tqdm import tqdm
import sys

def export_register_money(request):
    """
    View que gera um arquivo ZIP contendo um CSV para o model RegisterMoney.
    O CSV utilizará ';' como delimitador.
    Durante a exportação, é exibida uma barra de progresso no terminal.
    """
    zip_buffer = io.BytesIO()
    filename = "registermoney.csv"
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter=';')
        
        # Escreve o cabeçalho com os nomes dos campos do model
        field_names = [field.name for field in RegisterMoney._meta.fields]
        writer.writerow(field_names)
        
        queryset = RegisterMoney.objects.all()
        # Barra de progresso para cada objeto do model
        for obj in tqdm(queryset, desc=f"Processando {filename}", file=sys.stdout):
            row = []
            for field in RegisterMoney._meta.fields:
                value = getattr(obj, field.name)
                row.append("" if value is None else str(value))
            writer.writerow(row)
        
        # Adiciona o conteúdo do CSV ao arquivo ZIP
        zip_file.writestr(filename, csv_buffer.getvalue())
        csv_buffer.close()
    
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename=export_registermoney.zip"
    return response

# ======= INÍCIO AGENDAMENTO CLIENTE =======

@csrf_exempt
@require_POST
def api_post_agend_cliente(request):
    """
    API endpoint para criar um novo agendamento para um cliente.
    Recebe os dados via POST e retorna uma resposta JSON.
    """
    logger.info("----- Iniciando api_post_agend_cliente -----")

    cliente_id = request.POST.get('cliente_id')
    data_str = request.POST.get('data')
    hora_str = request.POST.get('hora')
    observacao = request.POST.get('observacao', '') # Observação é opcional

    # Validação básica dos campos obrigatórios
    if not cliente_id or not data_str or not hora_str:
        logger.error("Erro: Campos obrigatórios (cliente_id, data, hora) não fornecidos.")
        return JsonResponse({'status': 'erro', 'mensagem': 'Campos obrigatórios não fornecidos.'}, status=400)

    try:
        # Busca o cliente
        cliente = Cliente.objects.get(id=int(cliente_id))
        logger.info(f"Cliente encontrado: {cliente.nome} (ID: {cliente_id})")

        # Tenta converter data e hora
        try:
            # Tenta formato DD-MM-YYYY primeiro
            data_agendamento = datetime.strptime(data_str, '%d-%m-%Y').date() 
            logger.info(f"Data parseada com formato DD-MM-YYYY: {data_agendamento}")
        except ValueError:
            try:
                 # Tenta formato YYYY-MM-DD como fallback
                data_agendamento = datetime.strptime(data_str, '%Y-%m-%d').date()
                logger.info(f"Data parseada com formato YYYY-MM-DD: {data_agendamento}")
            except ValueError:
                 logger.error(f"Erro: Formato inválido de data ({data_str}). Use DD-MM-YYYY ou YYYY-MM-DD.")
                 return JsonResponse({'status': 'erro', 'mensagem': 'Formato de data inválido. Use DD-MM-YYYY.'}, status=400)
        
        try:
            # Mantém o parse da hora como HH:MM
            hora_agendamento = datetime.strptime(hora_str, '%H:%M').time()
            logger.info(f"Hora parseada: {hora_agendamento}")
        except ValueError:
            logger.error(f"Erro: Formato inválido de hora ({hora_str}). Use HH:MM.")
            return JsonResponse({'status': 'erro', 'mensagem': 'Formato de hora inválido. Use HH:MM.'}, status=400)

        # Cria o agendamento usando objects.create com o nome correto do modelo
        try:
            # Usa AgendamentoFichaCliente.objects.create() para criar e salvar
            novo_agendamento = AgendamentoFichaCliente.objects.create(
                cliente=cliente,       # Passa a instância do cliente
                usuario=request.user,  # Adiciona o usuário logado
                data=data_agendamento, # Passa o objeto date
                hora=hora_agendamento, # Passa o objeto time
                observacao=observacao  # Passa a string de observação
            )
            logger.info(f"Agendamento (Ficha Cliente) criado com sucesso via objects.create: ID {novo_agendamento.id}")
        except Exception as creation_error:
            # Log detalhado do erro de criação
            logger.error(f"Erro ao criar AgendamentoFichaCliente via objects.create: {type(creation_error).__name__} - {str(creation_error)}")
            logger.exception("Detalhes do erro de criação do agendamento:") # Loga o traceback completo
            error_message = str(creation_error)
            # O erro TypeError original fazia sentido agora, remove a mensagem genérica
            return JsonResponse({'status': 'erro', 'mensagem': f'Erro ao criar registro no banco: {error_message}'}, status=500)

        return JsonResponse({
            'status': 'sucesso',
            'mensagem': 'Agendamento criado com sucesso!',
            'agendamento_id': novo_agendamento.id
        }, status=201)

    except Cliente.DoesNotExist:
        logger.error(f"Erro: Cliente com ID {cliente_id} não encontrado.")
        return JsonResponse({'status': 'erro', 'mensagem': 'Cliente não encontrado.'}, status=404)
    except ValueError as ve: # Captura especificamente ValueError de int(cliente_id)
        logger.error(f"Erro: ID do cliente inválido ({cliente_id}): {str(ve)}")
        return JsonResponse({'status': 'erro', 'mensagem': 'ID do cliente inválido.'}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado ao criar agendamento: {type(e).__name__} - {str(e)}")
        logger.exception("Detalhes do erro inesperado:") # Loga o traceback completo
        return JsonResponse({'status': 'erro', 'mensagem': f'Erro interno do servidor: {str(e)}'}, status=500)
    finally:
        logger.info("----- Finalizando api_post_agend_cliente -----")


@login_required
def api_get_agendamentos_cliente(request):
    """
    Retorna os agendamentos feitos pelo usuário logado que não estão confirmados.
    """
    try:
        # Obtém os agendamentos do usuário logado que não estão confirmados
        agendamentos = AgendamentoFichaCliente.objects.filter(
            usuario=request.user
        ).exclude(
            status='CONFIRMADO'  # Exclui agendamentos já confirmados
        ).select_related('cliente').order_by('-data', '-hora')

        # Prepara a lista de agendamentos para o JSON
        agendamentos_list = []
        for agend in agendamentos:
            agendamentos_list.append({
                'id': agend.id,
                'cliente_id': agend.cliente.id,
                'cliente_nome': agend.cliente.nome,
                'cliente_cpf': agend.cliente.cpf,
                'data': agend.data.strftime('%d/%m/%Y'),
                'hora': agend.hora.strftime('%H:%M'),
                'observacao': agend.observacao or '',
                'data_criacao': agend.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'status': agend.status  # Adicionar o status para referência no frontend
            })

        return JsonResponse({
            'status': 'sucesso',
            'agendamentos': agendamentos_list
        })

    except Exception as e:
        logger.error(f"Erro ao buscar agendamentos: {str(e)}")
        return JsonResponse({
            'status': 'erro',
            'mensagem': 'Erro ao buscar agendamentos.'
        }, status=500)

@require_GET
def api_get_infocliente(request):
    """
    API que retorna os dados da ficha de um cliente específico em formato JSON,
    recebendo o cliente_id via GET e opcionalmente o agendamento_id.
    Filtra os débitos apenas para campanhas ativas.
    """
    cliente_id      = request.GET.get('cliente_id')
    agendamento_id  = request.GET.get('agendamento_id')  # Parâmetro opcional

    if not cliente_id:
        return JsonResponse({'erro': 'ID do cliente não fornecido.'}, status=400)

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return JsonResponse({'erro': 'Cliente não encontrado.'}, status=404)
    except ValueError:
        return JsonResponse({'erro': 'ID do cliente inválido.'}, status=400)

    # Monta dados principais do cliente
    cliente_data = {
        'id': cliente.id,
        'nome': cliente.nome,
        'cpf': cliente.cpf,
        'uf': cliente.uf,
        'rjur': cliente.rjur,
        'situacao_funcional': cliente.situacao_funcional,
        'renda_bruta': str(cliente.renda_bruta) if cliente.renda_bruta is not None else None,
        'bruta_5': str(cliente.bruta_5) if cliente.bruta_5 is not None else None,
        'util_5': str(cliente.util_5) if cliente.util_5 is not None else None,
        'saldo_5': str(cliente.saldo_5) if cliente.saldo_5 is not None else None,
        'brutaBeneficio_5': str(cliente.brutaBeneficio_5) if cliente.brutaBeneficio_5 is not None else None,
        'utilBeneficio_5': str(cliente.utilBeneficio_5) if cliente.utilBeneficio_5 is not None else None,
        'saldoBeneficio_5': str(cliente.saldoBeneficio_5) if cliente.saldoBeneficio_5 is not None else None,
        'bruta_35': str(cliente.bruta_35) if cliente.bruta_35 is not None else None,
        'util_35': str(cliente.util_35) if cliente.util_35 is not None else None,
        'saldo_35': str(cliente.saldo_35) if cliente.saldo_35 is not None else None,
        'total_util': str(cliente.total_util) if cliente.total_util is not None else None,
        'total_saldo': str(cliente.total_saldo) if cliente.total_saldo is not None else None,
    }

    # Busca débitos apenas de campanhas ativas
    debitos = Debito.objects.filter(
        cliente=cliente,
        campanha__status=True
    ).select_related('campanha__setor')

    lista_debitos = []
    for d in debitos:
        lista_debitos.append({
            'id': d.id,
            'matricula': d.matricula,
            'banco': d.banco,
            'orgao': d.orgao,
            'rebrica': d.rebrica,
            'parcela': str(d.parcela) if d.parcela is not None else None,
            'prazo_restante': d.prazo_restante,
            'tipo_contrato': d.tipo_contrato,
            'num_contrato': d.num_contrato,
            'campanha': {
                'id': d.campanha.id,
                'nome': d.campanha.nome,
                # usa o campo correto 'setor' em vez de 'departamento'
                'setor': {
                    'id': d.campanha.setor.id,
                    'nome': d.campanha.setor.nome
                }
            }
        })

    # Se houver agendamento associado, busca também
    agendamento_data = None
    if agendamento_id:
        try:
            ag = AgendamentoFichaCliente.objects.get(id=agendamento_id, cliente=cliente)
            agendamento_data = {
                'id': ag.id,
                'data': ag.data.strftime('%d/%m/%Y'),
                'hora': ag.hora.strftime('%H:%M'),
                'observacao': ag.observacao or '',
                'data_criacao': ag.data_criacao.strftime('%d/%m/%Y %H:%M') if ag.data_criacao else None
            }
        except AgendamentoFichaCliente.DoesNotExist:
            # deixa agendamento_data como None
            pass

    return JsonResponse({
        'status': 'sucesso',
        'cliente': cliente_data,
        'debitos': lista_debitos,
        'agendamento': agendamento_data
    })

@csrf_exempt
@require_POST
def api_post_confirm_agend(request):
    """
    API para confirmar um agendamento existente
    Recebe: id do agendamento via POST
    Retorna: Mensagem de sucesso ou erro em JSON
    """
    try:
        # Simplificar a obtenção dos dados - usar apenas POST
        agendamento_id = request.POST.get('agendamento_id')
        
        # Verificar se o ID foi fornecido
        if not agendamento_id:
            return JsonResponse({
                'status': 'erro',
                'mensagem': 'ID de agendamento não fornecido'
            }, status=400)
        
        # Buscar o agendamento pelo ID
        try:
            agendamento = AgendamentoFichaCliente.objects.get(id=agendamento_id)
        except AgendamentoFichaCliente.DoesNotExist:
            return JsonResponse({
                'status': 'erro',
                'mensagem': f'Agendamento com ID {agendamento_id} não encontrado'
            }, status=404)
        
        # Atualizar o status para CONFIRMADO
        agendamento.status = 'CONFIRMADO'
        agendamento.save()
        
        # Registrar a confirmação no log
        logger.info(f'Agendamento {agendamento_id} confirmado com sucesso')
        
        # Retornar resposta de sucesso
        return JsonResponse({
            'status': 'sucesso',
            'mensagem': 'Agendamento confirmado com sucesso',
            'agendamento_id': agendamento_id
        })
        
    except Exception as e:
        # Registrar o erro
        logger.error(f'Erro ao confirmar agendamento: {str(e)}')
        
        # Retornar mensagem de erro
        return JsonResponse({
            'status': 'erro',
            'mensagem': f'Erro ao confirmar agendamento: {str(e)}'
        }, status=500)

def get_safe_value(row, column_name, default=''):
    """Obtém um valor de forma segura do DataFrame, lidando com colunas ausentes ou valores nulos."""
    try:
        if column_name not in row:
            print(f"Aviso: Coluna '{column_name}' não encontrada.")
            return default
        
        value = row.get(column_name)
        if value is None or (isinstance(value, str) and value.strip() == '') or pd.isna(value):
            return default
        return value
    except Exception as e:
        print(f"Erro ao obter valor da coluna '{column_name}': {e}")
        return default


