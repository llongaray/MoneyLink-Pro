from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, F, Case, When, Value, DecimalField, CharField
from django.db.models.functions import Coalesce, ExtractYear, ExtractMonth
from django.utils import timezone
import datetime
from decimal import Decimal
import datetime
import json
from django.forms.models import model_to_dict
from datetime import timedelta
import re

# Import models from other apps
from apps.funcionarios.models import *
from apps.siape.models import *
from apps.inss.models import Agendamento as INSS_Agendamento, PresencaLoja as INSS_PresencaLoja
from apps.inss.models import *



from django.shortcuts import render # Adicionar import se não existir no topo do arquivo
from django.contrib.auth.decorators import login_required # Import já presente no contexto
from django.views.decorators.http import require_GET # Adicionar import se não existir


import logging
logger = logging.getLogger(__name__)
# renderização de paginas

from custom_tags_app.templatetags.permissionsacess import controle_acess

@login_required
@controle_acess('SCT9')   #  9 – ADMINISTRATIVO | DASHBOARD
def render_dashboard(request):
    """
    Renderiza a página principal do dashboard administrativo.
    Os dados são carregados dinamicamente via API (api_get_dashboard).
    """
    logger.debug("Iniciando render_dashboard administrativo")
    return render(request, 'administrativo/dashboard.html')

@login_required
@controle_acess('SCT10')  # 10 – ADMINISTRATIVO | CONTROLE DE METAS
def render_controlemetas(request):
    """
    Renderiza a página HTML para o controle e cadastro de metas.
    """
    logger.debug("Iniciando render_controlemetas")
    return render(request, 'administrativo/controle_metas.html')

@login_required
@require_GET              # Garante que esta view só responda a requisições GET
@controle_acess('SCT11')  # 11 – ADMINISTRATIVO | REEMBOLSOS
def render_reembolso(request):
    """
    Renderiza a página principal de controle de reembolsos.

    Esta view simplesmente renderiza o template HTML base. Os dados
    dinâmicos (tabelas, estatísticas) são carregados de forma assíncrona
    pelo JavaScript no frontend, que faz chamadas para as API views
    (ex: api_get_inforeembolso).
    """
    logger.debug("Iniciando render_reembolso administrativo")
    return render(request, 'apps/administrativo/reembolso.html')

@login_required
@controle_acess('SCT52')
def render_importscsvs(request):
    """
    Renderiza a página de importação de CSVs do Administrativo.
    Não envia nenhum contexto adicional ao template.
    """
    logger.debug("Iniciando render_importscsvs")
    return render(request, 'administrativo/import_csvs.html')

# fim renderização de paginas


# Helper function for currency formatting (optional, frontend can also handle)
def format_currency(value):
    if value is None:
        return "R$ 0,00"
    try:
        # Ensure value is Decimal
        value = Decimal(value)
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"

# Helper function for percentage formatting (optional)
def format_percentage(value):
    if value is None:
        return "0.0%"
    try:
        value = Decimal(value)
        return f"{value:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


# -------------------------------------------
# INICIO API GET/POST DASHBOARD
# Funções relacionadas às requisições da dashboard administrativa
# -------------------------------------------

import traceback
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce

from django.utils import timezone


@login_required
@require_GET
def api_get_dashboard(request):
    """
    API endpoint para retornar todos os dados do Dashboard Administrativo.
    """
    try:
        now = timezone.now()

        # --- Intervalos de Data ---
        start_year  = now.replace(month=1, day=1,  hour=0, minute=0, second=0, microsecond=0)
        end_year    = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Primeiro dia do próximo mês
        next_month = start_month.replace(month=start_month.month % 12 + 1, day=1)
        if start_month.month == 12:
            next_month = next_month.replace(year=start_month.year + 1)

        # Último instante do mês atual
        end_month = next_month - timedelta(microseconds=1)

        # Base para dados financeiros ativos
        registros_financeiros = RegisterMoney.objects.filter(status=True)

        # Estrutura inicial de resposta
        data = {
            'financeiro': {
                'empresas_list': [],
                'interno': {'faturamento_ano': Decimal(0), 'faturamento_mes': Decimal(0)},
                'franquia': {'faturamento_ano': Decimal(0), 'faturamento_mes': Decimal(0)},
                'filial': {'faturamento_ano': Decimal(0), 'faturamento_mes': Decimal(0)},
            },
            'lojas': {
                'sede': {},
                'filiais_list': [],
                'franquias_list': [],
            },
            'rh': {
                'geral': {'ativos': 0, 'inativos': 0},
                'funcionarios_list': [],
                'desempenho': {},
            },
            'metas': {
                'ativas_list': [],
                'inativadas_list': [],
            },
            'timestamp': now.isoformat()
        }

        # ==========================================
        # FINANCEIRO
        # ==========================================
        empresas = Empresa.objects.filter(status=True).order_by('nome')
        for emp in empresas:
            fat_ano = registros_financeiros.filter(
                empresa=emp, data__range=(start_year, end_year)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
            fat_mes = registros_financeiros.filter(
                empresa=emp, data__range=(start_month, end_month)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
            data['financeiro']['empresas_list'].append({
                'id': emp.id,
                'nome': emp.nome,
                'faturamento_ano': fat_ano,
                'faturamento_mes': fat_mes
            })

        interno_ano = registros_financeiros.filter(
            Q(loja__isnull=True) | Q(loja__franquia=False),
            data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        interno_mes = registros_financeiros.filter(
            Q(loja__isnull=True) | Q(loja__franquia=False),
            data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['interno'] = {
            'faturamento_ano': interno_ano,
            'faturamento_mes': interno_mes
        }

        franq_ano = registros_financeiros.filter(
            loja__franquia=True, data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        franq_mes = registros_financeiros.filter(
            loja__franquia=True, data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['franquia'] = {
            'faturamento_ano': franq_ano,
            'faturamento_mes': franq_mes
        }

        filial_ano = registros_financeiros.filter(
            loja__filial=True, data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        filial_mes = registros_financeiros.filter(
            loja__filial=True, data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['filial'] = {
            'faturamento_ano': filial_ano,
            'faturamento_mes': filial_mes
        }

        # ==========================================
        # LOJAS
        # ==========================================
        lojas          = Loja.objects.filter(status=True).order_by('nome')
        sede_lojas     = lojas.filter(filial=False, franquia=False)
        filial_lojas   = lojas.filter(filial=True)
        franquia_lojas = lojas.filter(franquia=True)

        def get_loja_metrics(loja_inst):
            m = {
                'faturamento_ano': Decimal(0),
                'faturamento_mes': Decimal(0),
                'taxa_comparecimento': Decimal(0),
                'clientes_rua': 0,
                'negocios_fechados': 0,
                'agendamentos': 0,
                'sem_interesse': 0
            }
            m['faturamento_ano'] = registros_financeiros.filter(
                loja=loja_inst, data__range=(start_year, end_year)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
            m['faturamento_mes'] = registros_financeiros.filter(
                loja=loja_inst, data__range=(start_month, end_month)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']

            ag_m = INSS_Agendamento.objects.filter(
                loja=loja_inst, dia_agendado__range=(start_month, end_month)
            ).count()
            pr_qs = INSS_PresencaLoja.objects.filter(
                loja_comp=loja_inst, data_presenca__range=(start_month, end_month)
            )
            m['agendamentos'] = ag_m
            if ag_m > 0:
                comp = pr_qs.exclude(cliente_rua=True).count()
                m['taxa_comparecimento'] = (Decimal(comp) / Decimal(ag_m)) * 100
            m['clientes_rua']      = pr_qs.filter(cliente_rua=True).count()
            m['negocios_fechados'] = pr_qs.filter(
                tabulacao_venda=INSS_PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO
            ).count()
            m['sem_interesse']     = pr_qs.filter(
                tabulacao_venda__in=[
                    INSS_PresencaLoja.TabulacaoVendaChoices.NAO_ACEITOU,
                    INSS_PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR,
                    INSS_PresencaLoja.TabulacaoVendaChoices.INELEGIVEL
                ]
            ).count()
            return m

        # Sede agregado
        sede_tot = {
            'faturamento_ano': Decimal(0),
            'faturamento_mes': Decimal(0),
            'taxa_comparecimento': Decimal(0),
            'clientes_rua': 0,
            'negocios_fechados': 0,
            'agendamentos': 0,
            'sem_interesse': 0
        }
        sum_age = sum_comp = 0
        for s in sede_lojas:
            mt = get_loja_metrics(s)
            for k in sede_tot:
                sede_tot[k] += mt[k]
            ag_ct = INSS_Agendamento.objects.filter(
                loja=s, dia_agendado__range=(start_month, end_month)
            ).count()
            cp_ct = INSS_PresencaLoja.objects.filter(
                loja_comp=s, data_presenca__range=(start_month, end_month)
            ).exclude(cliente_rua=True).count()
            sum_age += ag_ct
            sum_comp += cp_ct
        sede_tot['taxa_comparecimento'] = (
            (Decimal(sum_comp) / Decimal(sum_age) * 100) if sum_age else Decimal(0)
        )
        data['lojas']['sede'] = sede_tot

        # Filiais e Franquias
        for f in filial_lojas:
            data['lojas']['filiais_list'].append({
                'id': f.id,
                'nome': f.nome,
                'metrics': get_loja_metrics(f)
            })
        for fq in franquia_lojas:
            data['lojas']['franquias_list'].append({
                'id': fq.id,
                'nome': fq.nome,
                'metrics': get_loja_metrics(fq)
            })

        # ==========================================
        # RH
        # ==========================================
        funcs = Funcionario.objects.select_related('usuario').prefetch_related('regras_comissionamento')
        data['rh']['geral']['ativos']   = funcs.filter(status=True).count()
        data['rh']['geral']['inativos'] = funcs.filter(status=False).count()

        for fn in funcs.filter(status=True).order_by('nome_completo'):
            # Lista para selector
            data['rh']['funcionarios_list'].append({
                'id': fn.id,
                'nome': fn.apelido or fn.nome_completo
            })
            # Desempenho
            desempenho = {
                'faturamento_ano': Decimal(0),
                'faturamento_mes': Decimal(0),
                'clientes_concluidos': 0,
                'comissao_total_mes': Decimal(0)
            }
            if fn.usuario:
                ur = registros_financeiros.filter(user=fn.usuario)
                desempenho['faturamento_ano'] = ur.filter(
                    data__range=(start_year, end_year)
                ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
                desempenho['faturamento_mes'] = ur.filter(
                    data__range=(start_month, end_month)
                ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
                desempenho['clientes_concluidos'] = ur.filter(
                    data__range=(start_month, end_month)
                ).values('cpf_cliente').distinct().count()

                # Cálculo de comissão simples
                total_com = Decimal(0)
                regras = fn.regras_comissionamento.filter(status=True)
                for rg in regras:
                    base = desempenho['faturamento_mes']
                    if rg.percentual is not None:
                        if ((rg.valor_de is None or base >= rg.valor_de) and
                            (rg.valor_ate is None or base <= rg.valor_ate)):
                            total_com += (base * rg.percentual) / Decimal(100)
                    elif rg.valor_fixo is not None:
                        if ((rg.valor_de is None or base >= rg.valor_de) and
                            (rg.valor_ate is None or base <= rg.valor_ate)):
                            total_com += rg.valor_fixo
                desempenho['comissao_total_mes'] = total_com

            data['rh']['desempenho'][fn.id] = desempenho

        # ==========================================
        # METAS
        # ==========================================
        def calcular_meta_atingida(meta):
            q = Q(status=True, data__range=(meta.data_inicio, meta.data_fim))
            if meta.categoria == 'GERAL':
                pass
            elif meta.categoria == 'EMPRESA':
                q &= Q(empresa__isnull=False)
            elif meta.categoria == 'FRANQUIA':
                q &= Q(loja__franquia=True)
            elif meta.categoria == 'LOJAS':
                q &= Q(loja__isnull=False)
            elif meta.categoria == 'SETOR' and meta.setor:
                q &= Q(setor=meta.setor)
            elif meta.categoria == 'OUTROS' and meta.equipe.exists():
                q &= Q(equipe__in=meta.equipe.all())
            else:
                return Decimal(0)
            return RegisterMoney.objects.filter(q).aggregate(
                total=Coalesce(Sum('valor_est'), Decimal(0))
            )['total']

        metas_ativas = RegisterMeta.objects.filter(
            status=True, data_inicio__lte=now, data_fim__gte=now
        )
        for m in metas_ativas:
            vm = m.valor or Decimal(0)
            va = calcular_meta_atingida(m)
            restante = max(Decimal(0), vm - va)
            pct = (va / vm * 100) if vm > 0 else Decimal(100)
            status = 'Concluída' if pct >= 100 else 'Quase lá' if pct >= 85 else 'Em andamento'
            data['metas']['ativas_list'].append({
                'id': m.id,
                'titulo': m.titulo,
                'valor_meta': vm,
                'valor_atingido': va,
                'valor_restante': restante,
                'percentual': pct,
                'status': status
            })

        metas_inativas = RegisterMeta.objects.filter(
            Q(status=False) | Q(data_fim__lt=now)
        ).exclude(pk__in=[m['id'] for m in data['metas']['ativas_list']])[:20]
        for m in metas_inativas:
            vm = m.valor or Decimal(0)
            va = calcular_meta_atingida(m)
            restante = max(Decimal(0), vm - va)
            st = 'Concluída' if va >= vm else 'Não atingida'
            if not m.status:
                st = 'Cancelada'
            data['metas']['inativadas_list'].append({
                'id': m.id,
                'titulo': m.titulo,
                'valor_meta': vm,
                'valor_atingido': va,
                'valor_restante': restante,
                'status': st
            })

        return JsonResponse(data)

    except Exception as e:
        print(f"Erro geral na API do Dashboard Administrativo: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': 'Erro interno ao processar dados do dashboard.',
            'details': str(e)
        }, status=500)



# -------------------------------------------
# FIM API GET/POST DASHBOARD
# -------------------------------------------



# -------------------------------------------
# INICIO Views Controle de Metas
# -------------------------------------------



@login_required
@require_GET
def api_get_metas(request):
    """
    API endpoint para listar todas as metas registradas (RegisterMeta).
    """
    try:
        # Otimização: Usar select_related e prefetch_related
        metas = RegisterMeta.objects.select_related('setor').prefetch_related('equipe').order_by('-data_criacao')

        metas_data = []
        for meta in metas:
            meta_dict = model_to_dict(meta, fields=[
                'id', 'titulo', 'valor', 'categoria', 'data_inicio',
                'data_fim', 'status', 'data_criacao'
            ])
            # Adicionar informações relacionadas manualmente
            meta_dict['setor_nome'] = meta.setor.nome if meta.setor else None
            meta_dict['equipes_nomes'] = list(meta.equipe.values_list('nome', flat=True))
            meta_dict['categoria_display'] = meta.get_categoria_display() # Nome legível da categoria

            # Formatar datas para JSON (ISO 8601)
            meta_dict['data_inicio'] = meta.data_inicio.isoformat() if meta.data_inicio else None
            meta_dict['data_fim'] = meta.data_fim.isoformat() if meta.data_fim else None
            meta_dict['data_criacao'] = meta.data_criacao.isoformat() if meta.data_criacao else None

            metas_data.append(meta_dict)

        # --- Buscar dados para os seletores ---
        setores = Setor.objects.filter(status=True).values('id', 'nome').order_by('nome')
        equipes = Equipe.objects.filter(status=True).values('id', 'nome').order_by('nome')
        categorias_meta = [{'value': choice[0], 'display': choice[1]} for choice in RegisterMeta.CATEGORIA_CHOICES]

        response_data = {
            'metas': metas_data,
            'seletores': {
                'setores': list(setores),
                'equipes': list(equipes),
                'categorias': categorias_meta
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        print(f"Erro em api_get_metas: {e}")
        # Em produção, logar o erro detalhado
        return JsonResponse({'error': 'Erro ao buscar metas.', 'details': str(e)}, status=500)


@login_required
@require_POST
@csrf_exempt
def api_post_attmeta(request):
    """
    API endpoint para atualizar o status de uma meta (RegisterMeta).
    Recebe o ID da meta via POST e inverte o status (True para False ou False para True).
    """
    try:
        # Tenta obter o ID da meta do corpo da requisição (JSON) ou formulário POST
        meta_id = None
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                meta_id = data.get('meta_id')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'JSON inválido no corpo da requisição.'}, status=400)
        else:
            # Fallback para dados de formulário
            meta_id = request.POST.get('meta_id')

        if not meta_id:
            return JsonResponse({'error': 'ID da meta (meta_id) não fornecido.'}, status=400)

        try:
            meta_id = int(meta_id)
        except ValueError:
            return JsonResponse({'error': 'ID da meta inválido.'}, status=400)

        # Busca a meta pelo ID
        try:
            meta = RegisterMeta.objects.get(pk=meta_id)
        except RegisterMeta.DoesNotExist:
            return JsonResponse({'error': f'Meta com ID {meta_id} não encontrada.'}, status=404)

        # Inverte o status da meta
        meta.status = not meta.status
        meta.save()

        # Retorna sucesso com o novo status
        return JsonResponse({
            'success': True,
            'message': f'Status da meta atualizado com sucesso para {"Ativo" if meta.status else "Inativo"}.',
            'meta_id': meta.id,
            'new_status': meta.status
        }, status=200)

    except Exception as e:
        # Logar o erro em produção seria ideal
        print(f"Erro em api_post_attmeta: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Erro interno ao atualizar o status da meta.', 'details': str(e)}, status=500)


@login_required
@require_POST
@csrf_exempt
def api_post_novameta(request):
    """
    API endpoint para criar uma nova meta (RegisterMeta).
    Recebe os dados via JSON no corpo da requisição POST.
    """
    try:
        data = json.loads(request.body)

        # Validação básica (campos obrigatórios) - Idealmente usar um Form
        required_fields = ['titulo', 'valor', 'categoria', 'data_inicio', 'data_fim']
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                 return JsonResponse({'error': f'Campo obrigatório ausente ou vazio: {field}'}, status=400)

        # Validação específica por categoria
        categoria = data.get('categoria')
        setor_id = data.get('setor_id')
        equipe_ids = data.get('equipe_ids', []) # Lista de IDs

        if categoria == 'SETOR' and not setor_id:
            return JsonResponse({'error': 'ID do setor é obrigatório para a categoria SETOR'}, status=400)
        if categoria == 'OUTROS' and not equipe_ids: # Assumindo que OUTROS = EQUIPE
            return JsonResponse({'error': 'Pelo menos um ID de equipe é obrigatório para a categoria OUTROS'}, status=400)

        # Criação da instância
        nova_meta = RegisterMeta.objects.create(
            titulo=data['titulo'],
            valor=Decimal(data['valor']), # Converter para Decimal
            categoria=categoria,
            data_inicio=data['data_inicio'], # Assumindo formato ISO 8601 vindo do frontend
            data_fim=data['data_fim'],       # Assumindo formato ISO 8601 vindo do frontend
            status=data.get('status', False) # Default para False se não enviado
        )

        # Associações
        if categoria == 'SETOR':
            try:
                setor = Setor.objects.get(pk=setor_id)
                nova_meta.setor = setor
            except Setor.DoesNotExist:
                nova_meta.delete() # Rollback da criação
                return JsonResponse({'error': f'Setor com ID {setor_id} não encontrado.'}, status=404)

        # Salva antes de adicionar M2M
        nova_meta.save()

        if categoria == 'OUTROS' and equipe_ids:
            try:
                equipes = Equipe.objects.filter(pk__in=equipe_ids)
                if len(equipes) != len(equipe_ids):
                     # Nem todas as equipes foram encontradas
                     raise ValueError("Uma ou mais equipes não encontradas.")
                nova_meta.equipe.set(equipes)
            except (Equipe.DoesNotExist, ValueError) as ve:
                 nova_meta.delete() # Rollback
                 return JsonResponse({'error': f'Erro ao associar equipes: {ve}'}, status=400)


        # Retorna a meta criada (opcional, mas útil para o frontend)
        # Exclui campos M2M e datas de model_to_dict para tratar manualmente
        meta_dict = model_to_dict(nova_meta, exclude=['equipe', 'data_inicio', 'data_fim', 'data_criacao'])
        meta_dict['setor_nome'] = nova_meta.setor.nome if nova_meta.setor else None
        meta_dict['equipes_nomes'] = list(nova_meta.equipe.values_list('nome', flat=True))
        meta_dict['categoria_display'] = nova_meta.get_categoria_display()
        # Formata as datas corretamente a partir do objeto datetime
        meta_dict['data_inicio'] = nova_meta.data_inicio.isoformat() if isinstance(nova_meta.data_inicio, (datetime.date, datetime.datetime)) else None
        meta_dict['data_fim'] = nova_meta.data_fim.isoformat() if isinstance(nova_meta.data_fim, (datetime.date, datetime.datetime)) else None
        meta_dict['data_criacao'] = nova_meta.data_criacao.isoformat() if isinstance(nova_meta.data_criacao, (datetime.date, datetime.datetime)) else None

        return JsonResponse({'message': 'Meta criada com sucesso!', 'meta': meta_dict}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido no corpo da requisição.'}, status=400)
    except (TypeError, ValueError) as ve:
        # Ex: Erro ao converter valor para Decimal ou data inválida
        print(f"Erro de tipo/valor em api_post_novameta: {ve}")
        return JsonResponse({'error': f'Erro nos dados enviados: {ve}'}, status=400)
    except Exception as e:
        print(f"Erro geral em api_post_novameta: {e}")
        # Em produção, logar o erro detalhado
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Erro interno ao criar a meta.', 'details': str(e)}, status=500)


# -------------------------------------------
# FIM Views Controle de Metas
# -------------------------------------------



# -------------------------------------------
# Views Reembolso
# -------------------------------------------
# (Outras views relacionadas a reembolso, como POST para criar/reverter, podem vir aqui)

from datetime import timedelta

@login_required
@require_GET
def api_get_inforeembolso(request):
    """
    Retorna:
    - registros_para_reembolsar: lista de RegisterMoney pendentes
    - registros_reembolsados:   lista de Reembolso já feitos
    - stats: contagens de Reembolso nos períodos 90d, 60d e mês atual
    """
    cpf     = request.GET.get('cpf_cliente', '').strip()
    produto = request.GET.get('produto_nome', '').strip()

    # — Registros ainda para reembolsar —
    qs_para = RegisterMoney.objects.filter(
        status=True,
        reembolso_info__isnull=True
    ).select_related('produto', 'setor')
    if cpf:
        qs_para = qs_para.filter(cpf_cliente__icontains=cpf)
    if produto:
        qs_para = qs_para.filter(produto__nome__icontains=produto)

    registros_para = []
    for reg in qs_para:
        nome_prod = reg.produto.nome if reg.produto else 'N/A'
        registros_para.append({
            'id':           reg.id,
            'cpf_cliente':  reg.cpf_cliente,
            'produto_nome': nome_prod,
            'valor':        f"{reg.valor_est:.2f}",
            'data_registro': reg.data.strftime('%d/%m/%Y %H:%M') if reg.data else 'N/A',
        })

    # — Registros já reembolsados —
    qs_remb = Reembolso.objects.filter(status=True).select_related(
        'registermoney__produto', 'registermoney__setor'
    )
    if cpf:
        qs_remb = qs_remb.filter(registermoney__cpf_cliente__icontains=cpf)

    registros_remb = []
    for remb in qs_remb:
        orig       = remb.registermoney
        nome_prod  = orig.produto.nome if orig.produto else 'N/A'
        nome_setor = orig.setor.nome   if orig.setor   else 'N/A'
        registros_remb.append({
            'reembolso_id':  remb.pk,
            'cpf_cliente':   orig.cpf_cliente,
            'produto_nome':  nome_prod,
            'valor':         f"{orig.valor_est:.2f}",
            'setor_nome':    nome_setor,
            'data_registro': orig.data.strftime('%d/%m/%Y %H:%M') if orig.data else 'N/A',
            'data_reembolso': remb.data_reembolso.strftime('%d/%m/%Y')
                               if remb.data_reembolso else 'N/A',
        })

    # — Estatísticas de Reembolso —
    hoje     = timezone.now().date()
    qs_todos = Reembolso.objects.filter(status=True)
    total_90d = qs_todos.filter(data_reembolso__gte=hoje - timedelta(days=90)).count()
    total_60d = qs_todos.filter(data_reembolso__gte=hoje - timedelta(days=60)).count()
    total_mes_atual = qs_todos.filter(
        data_reembolso__year=hoje.year,
        data_reembolso__month=hoje.month
    ).count()

    return JsonResponse({
        'registros_para_reembolsar': registros_para,
        'registros_reembolsados':   registros_remb,
        'stats': {
            'reembolsos_90d':       total_90d,
            'reembolsos_60d':       total_60d,
            'reembolsos_mes_atual': total_mes_atual,
        }
    })

# -------------------------------------------
# Views Reembolso
# -------------------------------------------
# (Outras views relacionadas a reembolso, como POST para criar/reverter, podem vir aqui)

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from apps.siape.models import RegisterMoney, Reembolso # Supondo que os modelos estão em .models
import json # Para decodificar o corpo da requisição se for JSON

@login_required
@require_POST
@transaction.atomic # Garante atomicidade da operação no banco
@csrf_exempt
def api_post_addreembolso(request):
    """
    API endpoint para registrar um novo reembolso para um RegisterMoney.
    Recebe o ID do RegisterMoney via POST.
    Cria um registro na tabela Reembolso associado ao RegisterMoney.
    """
    try:
        # Tenta obter o ID do corpo da requisição (JSON) ou formulário POST
        registermoney_id = None
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                registermoney_id = data.get('registermoney_id')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'JSON inválido no corpo da requisição.'}, status=400)
        else:
            # Fallback para dados de formulário
            registermoney_id = request.POST.get('registermoney_id')

        if not registermoney_id:
            return JsonResponse({'error': 'ID do registro financeiro (registermoney_id) não fornecido.'}, status=400)

        try:
            registermoney_id = int(registermoney_id)
        except ValueError:
            return JsonResponse({'error': 'ID do registro financeiro inválido.'}, status=400)

        # Verifica se o RegisterMoney existe
        try:
            registro_financeiro = RegisterMoney.objects.get(pk=registermoney_id)
        except RegisterMoney.DoesNotExist:
            return JsonResponse({'error': f'Registro Financeiro com ID {registermoney_id} não encontrado.'}, status=404)

        # Verifica se já existe um reembolso para este registro
        if Reembolso.objects.filter(registermoney=registro_financeiro).exists():
            return JsonResponse({'error': f'Já existe um reembolso registrado para o ID {registermoney_id}.'}, status=409) # 409 Conflict

        # Cria o novo registro de Reembolso
        novo_reembolso = Reembolso.objects.create(
            registermoney=registro_financeiro,
            data_reembolso=timezone.now().date(), # Usa a data atual
            status=True # Status padrão é True (reembolsado)
        )

        # Retorna sucesso com o ID do reembolso criado (que é o mesmo do registermoney)
        return JsonResponse({
            'success': True,
            'message': 'Reembolso registrado com sucesso.',
            'reembolso_id': novo_reembolso.pk
        }, status=201) # 201 Created

    except Exception as e:
        # Logar o erro em produção seria ideal
        print(f"Erro em api_post_addreembolso: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Erro interno ao registrar o reembolso.', 'details': str(e)}, status=500)


@login_required
@require_POST
@transaction.atomic # Garante atomicidade da operação no banco
@csrf_exempt
def api_post_reverterreembolso(request):
    """
    API endpoint para reverter (marcar como inativo) um registro de reembolso.
    Recebe o ID do Reembolso (que é o mesmo ID do RegisterMoney associado) via POST.
    Atualiza o status do Reembolso para False.
    """
    try:
        # Tenta obter o ID do corpo da requisição (JSON) ou formulário POST
        reembolso_id = None
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                reembolso_id = data.get('reembolso_id')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'JSON inválido no corpo da requisição.'}, status=400)
        else:
            # Fallback para dados de formulário
            reembolso_id = request.POST.get('reembolso_id')


        if not reembolso_id:
            return JsonResponse({'error': 'ID do reembolso (reembolso_id) não fornecido.'}, status=400)

        try:
            reembolso_id = int(reembolso_id)
        except ValueError:
            return JsonResponse({'error': 'ID do reembolso inválido.'}, status=400)

        # Busca o registro de Reembolso pelo ID (que é a PK e FK para RegisterMoney)
        try:
            reembolso = Reembolso.objects.get(pk=reembolso_id)
        except Reembolso.DoesNotExist:
            return JsonResponse({'error': f'Reembolso com ID {reembolso_id} não encontrado.'}, status=404)

        # Verifica se o reembolso já está inativo (status=False)
        if not reembolso.status:
             return JsonResponse({
                'success': False, # Ou True, dependendo se considera idempotente
                'message': f'Reembolso com ID {reembolso_id} já está marcado como revertido (inativo). Nenhuma ação realizada.'
            }, status=200) # Ou 400 Bad Request se não for idempotente

        # Atualiza o status para False
        reembolso.status = False
        reembolso.save()

        # Retorna sucesso
        return JsonResponse({
            'success': True,
            'message': f'Reembolso com ID {reembolso_id} revertido com sucesso (status alterado para False).'
        }, status=200)

    except Exception as e:
        # Logar o erro em produção seria ideal
        print(f"Erro em api_post_reverterreembolso: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Erro interno ao reverter o reembolso.', 'details': str(e)}, status=500)


import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date, parse_datetime
from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.utils import timezone
from apps.funcionarios.models import *
from apps.siape.models import *
from apps.inss.models import *
from django.shortcuts import get_object_or_404
import traceback
from datetime import datetime

@require_POST
@login_required
def api_post_csvfuncionarios(request):
    """
    Recebe JSON (UTF-8) com vários funcionários e cria User + Funcionario para cada um.
    Campos esperados por linha:
      apelido, nome_completo, cpf, data_nascimento (YYYY-MM-DD ou DD/MM/YYYY),
      empresa_id, departamento_id, setor_id, cargo_id,
      horario_id (opcional), equipe_id (opcional), loja_id (opcional)
    """
    print("\n----- Iniciando api_post_csvfuncionarios -----")
    try:
        body = request.body.decode('utf-8')     # explícito UTF-8
        rows = json.loads(body)
    except Exception as e:
        print("Erro ao decodificar JSON:", e)
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    total = len(rows)
    print(f"Total de linhas recebidas: {total}")
    created, errors = 0, []

    for i, row in enumerate(rows):
        print(f"\nProcessando linha {i}: {row}")
        try:
            apelido       = row.get('apelido', '').strip()
            nome_completo = row.get('nome_completo', '').strip()
            cpf           = ''.join(filter(str.isdigit, row.get('cpf', '')))
            data_str      = row.get('data_nascimento', '').strip()

            # parse de data
            nascimento = None
            for fmt in ('%Y-%m-%d','%d/%m/%Y'):
                try:
                    nascimento = datetime.strptime(data_str, fmt).date()
                    break
                except:
                    pass
            if not nascimento:
                raise ValueError("data_nascimento inválida")

            # credenciais
            username   = apelido.lower().replace(' ','_')
            password   = f"Money@{timezone.now().year}"
            fn, ln     = nome_completo.split(' ',1) if ' ' in nome_completo else (nome_completo,'')

            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, password=password,
                    first_name=fn, last_name=ln
                )
                print(f"  User criado ID={user.id}")

                empresa      = get_object_or_404(Empresa, pk=row['empresa_id'])
                departamento = get_object_or_404(Departamento, pk=row['departamento_id'])
                setor        = get_object_or_404(Setor, pk=row['setor_id'])
                cargo        = get_object_or_404(Cargo, pk=row['cargo_id'])
                horario      = HorarioTrabalho.objects.filter(pk=row.get('horario_id')).first()
                equipe       = Equipe.objects.filter(pk=row.get('equipe_id')).first()
                loja         = Loja.objects.filter(pk=row.get('loja_id')).first()

                Funcionario.objects.create(
                    usuario         = user,
                    apelido         = apelido,
                    nome_completo   = nome_completo,
                    cpf             = cpf,
                    data_nascimento = nascimento,
                    empresa         = empresa,
                    departamento    = departamento,
                    setor           = setor,
                    cargo           = cargo,
                    horario         = horario,
                    equipe          = equipe,
                    loja            = loja,
                )
                print("  Funcionario criado")
                created += 1

        except Exception as e:
            print(f"  Erro na linha {i}: {e}")
            traceback.print_exc()
            errors.append({'row': i, 'error': str(e)})

    print(f"\nConcluído. Criados: {created}, Erros: {len(errors)}")
    return JsonResponse({
        'success': True,
        'total': total,
        'created': created,
        'errors': errors,
    })

@require_POST
@login_required
def api_post_csvclientec2(request):
    """
    Recebe JSON com lista de clientes C2 e importa para ClienteAgendamento.
    Headers esperados por linha: nome_completo, cpf, numero_contato, flg_whatsapp.
    """
    print("Iniciando api_post_csvclientec2")
    try:
        rows = json.loads(request.body)
        print(f"Total de linhas recebidas: {len(rows)}")
    except json.JSONDecodeError:
        print("Erro ao decodificar JSON")
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    created, errors = 0, []
    for i, row in enumerate(rows):
        print(f"Processando linha {i}: {row}")
        try:
            cliente = ClienteAgendamento.objects.create(
                nome_completo = row['nome_completo'],
                cpf           = row['cpf'],
                numero        = row['numero_contato'],
                flg_whatsapp  = bool(row.get('flg_whatsapp', True)),
            )
            print(f"Cliente criado com ID: {cliente.id}")
            created += 1
        except Exception as e:
            print(f"Erro na linha {i}: {str(e)}")
            errors.append({'row': i, 'error': str(e)})

    print(f"Processamento concluído. Criados: {created}, Erros: {len(errors)}")
    return JsonResponse({'success': True, 'created': created, 'errors': errors})


@require_POST
@login_required
def api_post_csvagendamento(request):
    print("Iniciando api_post_csvagendamento")
    try:
        rows = json.loads(request.body)
        print(f"Total de linhas recebidas: {len(rows)}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    created, errors = 0, []
    for i, row in enumerate(rows):
        print(f"Processando linha {i}: {row}")
        try:
            # limpa o CPF recebido (remove . e -)
            raw_cpf = row['cpf_cliente']
            cleaned = re.sub(r'\D', '', raw_cpf)
            
            # primeiro, tenta achar exato
            try:
                cliente = ClienteAgendamento.objects.get(cpf=row['cpf_cliente'])
            except ClienteAgendamento.DoesNotExist:
                # senão, busca pelo CPF sem formatação
                cliente = None
                for c in ClienteAgendamento.objects.all():
                    if re.sub(r'\D', '', c.cpf) == cleaned:
                        cliente = c
                        break
                if not cliente:
                    raise ClienteAgendamento.DoesNotExist(f"CPF {raw_cpf} não encontrado")
            
            # continua com resto do processamento
            dia     = parse_datetime(row['dia_agendado'])
            loja    = Loja.objects.get(pk=row['loja_id'])
            user    = User.objects.get(pk=row['atendente_id'])

            Agendamento.objects.create(
                cliente_agendamento   = cliente,
                dia_agendado          = dia,
                loja                  = loja,
                atendente_agendou     = user,
                tabulacao_agendamento = row.get('tabulacao_agendamento', '')
            )
            created += 1
            print(f"Agendamento criado para cliente {cliente.id}")

        except Exception as e:
            print(f"Erro na linha {i}: {e}")
            errors.append({'row': i, 'error': str(e)})

    print(f"Processamento concluído. Criados: {created}, Erros: {len(errors)}")
    return JsonResponse({'success': True, 'created': created, 'errors': errors})


@require_POST
@login_required
def api_post_csvfinanceiro(request):
    """
    Recebe JSON com lista de registros financeiros e importa para RegisterMoney.
    Headers esperados por linha: user_id, loja_id, produto (nome), cpf_cliente,
    valor_estimado, empresa_id, departamento_id, setor_id, equipe_id, data_pagamento (ISO).
    """
    print("Iniciando api_post_csvfinanceiro")
    try:
        rows = json.loads(request.body)
        print(f"Total de linhas recebidas: {len(rows)}")
    except json.JSONDecodeError:
        print("Erro ao decodificar JSON")
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    created, errors = 0, []
    for i, row in enumerate(rows):
        try:
            user       = User.objects.get(pk=row['user_id'])
            loja       = Loja.objects.get(pk=row['loja_id'])
            produto, _= Produto.objects.get_or_create(nome=row['produto'])
            empresa    = Empresa.objects.get(pk=row['empresa_id'])
            departamento= Departamento.objects.get(pk=row['departamento_id'])
            setor      = Setor.objects.get(pk=row['setor_id'])
            equipe     = Equipe.objects.get(pk=row['equipe_id'])
            data_reg   = parse_datetime(row.get('data_pagamento'))

            RegisterMoney.objects.create(
                user         = user,
                loja         = loja,
                produto      = produto,
                cpf_cliente  = row.get('cpf_cliente', ''),
                valor_est    = row.get('valor_estimado') or None,
                empresa      = empresa,
                departamento = departamento,
                setor        = setor,
                equipe       = equipe,
                data         = data_reg
            )
            created += 1
        except Exception as e:
            errors.append({'row': i, 'error': str(e)})

    return JsonResponse({'success': True, 'created': created, 'errors': errors})
