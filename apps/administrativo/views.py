from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, F, Case, When, Value, DecimalField, CharField
from django.db.models.functions import Coalesce, ExtractYear, ExtractMonth
from django.utils import timezone
from decimal import Decimal
import datetime
import json
from django.forms.models import model_to_dict

# Import models from other apps
from apps.funcionarios.models import Empresa, Loja, Funcionario, Comissionamento, Setor, Equipe
from apps.siape.models import RegisterMoney, RegisterMeta, Produto
from apps.inss.models import Agendamento as INSS_Agendamento, PresencaLoja as INSS_PresencaLoja



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

@login_required # Ensure user is logged in
@require_GET
def api_get_dashboard(request):
    """
    API endpoint to fetch all necessary data for the administrative dashboard.
    """
    try:
        now = timezone.now()
        current_year = now.year
        current_month = now.month

        # --- Date Ranges ---
        start_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_year = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Find the last day of the current month
        next_month = start_month.replace(month=start_month.month % 12 + 1, day=1)
        if start_month.month == 12:
             next_month = next_month.replace(year=start_month.year + 1)
        end_month = next_month - datetime.timedelta(microseconds=1)


        # --- Base QuerySet for Financial Data ---
        registros_financeiros = RegisterMoney.objects.filter(status=True)

        # --- Estrutura de Dados de Retorno ---
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
                'desempenho': {}, # Keyed by funcionario.id
            },
            'metas': {
                'ativas_list': [],
                'inativadas_list': [],
            },
            'timestamp': now.isoformat()
        }

        # ==========================================
        # SESSÃO: FINANCEIRO
        # ==========================================
        print("Calculando seção Financeiro...")

        # 1. Categoria: Empresa
        empresas = Empresa.objects.filter(status=True).order_by('nome')
        empresas_data = []
        for empresa in empresas:
            fat_ano = registros_financeiros.filter(
                empresa=empresa, data__range=(start_year, end_year)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']

            fat_mes = registros_financeiros.filter(
                empresa=empresa, data__range=(start_month, end_month)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']

            empresas_data.append({
                'id': empresa.id,
                'nome': empresa.nome,
                'faturamento_ano': fat_ano,
                'faturamento_mes': fat_mes
            })
        data['financeiro']['empresas_list'] = empresas_data

        # 2. Categoria: Interno (Sedes) - Faturamento NÃO associado a Lojas Franquia
        # Inclui faturamento sem loja OU faturamento de lojas não-franquia (sede ou filial)
        interno_ano = registros_financeiros.filter(
            Q(loja__isnull=True) | Q(loja__franquia=False),
            data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        interno_mes = registros_financeiros.filter(
            Q(loja__isnull=True) | Q(loja__franquia=False),
            data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['interno'] = {'faturamento_ano': interno_ano, 'faturamento_mes': interno_mes}

        # 3. Categoria: Franquia - Faturamento de Lojas Franquia
        franquia_ano = registros_financeiros.filter(
            loja__franquia=True, data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        franquia_mes = registros_financeiros.filter(
            loja__franquia=True, data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['franquia'] = {'faturamento_ano': franquia_ano, 'faturamento_mes': franquia_mes}

        # 4. Categoria: Filial - Faturamento de Lojas Filial
        filial_ano = registros_financeiros.filter(
            loja__filial=True, data__range=(start_year, end_year)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        filial_mes = registros_financeiros.filter(
            loja__filial=True, data__range=(start_month, end_month)
        ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
        data['financeiro']['filial'] = {'faturamento_ano': filial_ano, 'faturamento_mes': filial_mes}
        print("Seção Financeiro OK.")

        # ==========================================
        # SESSÃO: LOJAS
        # ==========================================
        print("Calculando seção Lojas...")
        lojas = Loja.objects.filter(status=True).select_related('empresa').order_by('nome')
        sede_lojas = lojas.filter(filial=False, franquia=False)
        filial_lojas = lojas.filter(filial=True)
        franquia_lojas = lojas.filter(franquia=True)

        # --- Helper function for Loja Metrics ---
        def get_loja_metrics(loja_instance):
            metrics = {
                'faturamento_ano': Decimal(0), 'faturamento_mes': Decimal(0),
                'taxa_comparecimento': Decimal(0), 'clientes_rua': 0,
                'negocios_fechados': 0, 'agendamentos': 0, 'sem_interesse': 0
            }

            # Faturamento (RegisterMoney)
            metrics['faturamento_ano'] = registros_financeiros.filter(
                loja=loja_instance, data__range=(start_year, end_year)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
            metrics['faturamento_mes'] = registros_financeiros.filter(
                loja=loja_instance, data__range=(start_month, end_month)
            ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']

            # Métricas INSS (Agendamento, PresencaLoja) - Filtrar por mês atual
            agendamentos_mes = INSS_Agendamento.objects.filter(
                loja=loja_instance, dia_agendado__range=(start_month, end_month)
            )
            presencas_mes = INSS_PresencaLoja.objects.filter(
                loja_comp=loja_instance, data_presenca__range=(start_month, end_month)
            )

            total_agendamentos_mes = agendamentos_mes.count()
            total_presencas_mes = presencas_mes.count() # Presenças registradas no mês

            metrics['agendamentos'] = total_agendamentos_mes # Total agendado para o mês

            # Calcula comparecimentos do mês (presenças não de rua vinculadas a agendamentos do mês OU presenças de agend. anteriores que ocorreram no mes)
            # Simplificação: Considerando presenças registradas no mês como base para taxa
            comparecimentos_mes = presencas_mes.exclude(cliente_rua=True).count()

            if total_agendamentos_mes > 0:
                # Taxa pode ser baseada em comparecimentos/agendados OU comparecimentos/(agendados que deveriam ter vindo)
                # Usando a contagem de presenças do mês como base simplificada:
                 metrics['taxa_comparecimento'] = (Decimal(comparecimentos_mes) / Decimal(total_agendamentos_mes)) * 100
            else:
                 metrics['taxa_comparecimento'] = Decimal(0)


            metrics['clientes_rua'] = presencas_mes.filter(cliente_rua=True).count()
            metrics['negocios_fechados'] = presencas_mes.filter(
                tabulacao_venda=INSS_PresencaLoja.TabulacaoVendaChoices.NEGOCIO_FECHADO
            ).count()
            metrics['sem_interesse'] = presencas_mes.filter(
                tabulacao_venda__in=[
                    INSS_PresencaLoja.TabulacaoVendaChoices.NAO_ACEITOU,
                    INSS_PresencaLoja.TabulacaoVendaChoices.NAO_QUIS_OUVIR,
                    INSS_PresencaLoja.TabulacaoVendaChoices.INELEGIVEL
                ]
            ).count()

            return metrics

        # 1. Categoria: Sede
        # Assumindo que pode haver mais de uma sede, somamos as métricas
        sede_metrics_total = {
            'faturamento_ano': Decimal(0), 'faturamento_mes': Decimal(0),
            'taxa_comparecimento': Decimal(0), 'clientes_rua': 0,
            'negocios_fechados': 0, 'agendamentos': 0, 'sem_interesse': 0
        }
        total_agendamentos_sede_mes = 0
        total_comparecimentos_sede_mes = 0

        for sede in sede_lojas:
            metrics = get_loja_metrics(sede)
            sede_metrics_total['faturamento_ano'] += metrics['faturamento_ano']
            sede_metrics_total['faturamento_mes'] += metrics['faturamento_mes']
            sede_metrics_total['clientes_rua'] += metrics['clientes_rua']
            sede_metrics_total['negocios_fechados'] += metrics['negocios_fechados']
            sede_metrics_total['agendamentos'] += metrics['agendamentos']
            sede_metrics_total['sem_interesse'] += metrics['sem_interesse']

            # Para taxa de comparecimento agregada:
            agendamentos_mes_sede = INSS_Agendamento.objects.filter(loja=sede, dia_agendado__range=(start_month, end_month)).count()
            presencas_mes_sede = INSS_PresencaLoja.objects.filter(loja_comp=sede, data_presenca__range=(start_month, end_month))
            comparecimentos_mes_sede = presencas_mes_sede.exclude(cliente_rua=True).count()

            total_agendamentos_sede_mes += agendamentos_mes_sede
            total_comparecimentos_sede_mes += comparecimentos_mes_sede

        if total_agendamentos_sede_mes > 0:
            sede_metrics_total['taxa_comparecimento'] = (Decimal(total_comparecimentos_sede_mes) / Decimal(total_agendamentos_sede_mes)) * 100
        else:
            sede_metrics_total['taxa_comparecimento'] = Decimal(0)

        data['lojas']['sede'] = sede_metrics_total


        # 2. Categoria: Filial
        filiais_data = []
        for filial in filial_lojas:
            metrics = get_loja_metrics(filial)
            filiais_data.append({
                'id': filial.id,
                'nome': filial.nome,
                'metrics': metrics
            })
        data['lojas']['filiais_list'] = filiais_data

        # 3. Categoria: Franquia
        franquias_data = []
        for franquia in franquia_lojas:
            metrics = get_loja_metrics(franquia)
            franquias_data.append({
                'id': franquia.id,
                'nome': franquia.nome,
                'metrics': metrics
            })
        data['lojas']['franquias_list'] = franquias_data
        print("Seção Lojas OK.")

        # ==========================================
        # SESSÃO: RECURSOS HUMANOS
        # ==========================================
        print("Calculando seção RH...")
        funcionarios = Funcionario.objects.select_related(
            'usuario', 'cargo', 'empresa', 'departamento', 'setor', 'equipe'
        ).prefetch_related('regras_comissionamento') # Prefetch M2M

        # 1. Categoria: Funcionários (Geral)
        data['rh']['geral']['ativos'] = funcionarios.filter(status=True).count()
        data['rh']['geral']['inativos'] = funcionarios.filter(status=False).count()

        # 2. Categoria: Desempenho por Funcionário
        rh_funcionarios_list = []
        rh_desempenho = {}

        funcionarios_ativos = funcionarios.filter(status=True).order_by('nome_completo')

        for func in funcionarios_ativos:
             # Lista para o selector
             rh_funcionarios_list.append({
                 'id': func.id,
                 'nome': func.apelido or func.nome_completo # Usar apelido se disponível
             })

             # Dados de Desempenho
             desempenho_func = {
                 'faturamento_ano': Decimal(0),
                 'faturamento_mes': Decimal(0),
                 'clientes_concluidos': 0,
                 'comissao_total_mes': Decimal(0),
             }

             if func.usuario:
                 user_registros = registros_financeiros.filter(user=func.usuario)

                 # Faturamento Ano/Mês
                 desempenho_func['faturamento_ano'] = user_registros.filter(
                     data__range=(start_year, end_year)
                 ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']

                 fat_mes_func = user_registros.filter(
                     data__range=(start_month, end_month)
                 ).aggregate(total=Coalesce(Sum('valor_est'), Decimal(0)))['total']
                 desempenho_func['faturamento_mes'] = fat_mes_func

                 # Clientes Concluídos (CPFs únicos no mês)
                 desempenho_func['clientes_concluidos'] = user_registros.filter(
                     data__range=(start_month, end_month)
                 ).values('cpf_cliente').distinct().count()

                 # Calcular Comissão Total do Mês
                 total_comissao_mes = Decimal(0)
                 regras_aplicaveis = func.regras_comissionamento.filter(
                     status=True
                     # Adicionar filtro de data_inicio/data_fim se necessário:
                     # Q(data_inicio__lte=now.date()) | Q(data_inicio__isnull=True),
                     # Q(data_fim__gte=now.date()) | Q(data_fim__isnull=True)
                 )

                 for regra in regras_aplicaveis:
                     # Aplicar a lógica da regra baseada no faturamento do mês
                     # Simplificação: Apenas percentual sobre fat_mes_func ou valor fixo
                     # A lógica de faixas (valor_de, valor_ate) e escopo (escopo_base) precisaria
                     # de implementação mais detalhada aqui se fosse o caso.
                     comissao_regra = Decimal(0)
                     if regra.percentual is not None:
                         # Verificar faixas (exemplo simples)
                         if (regra.valor_de is None or fat_mes_func >= regra.valor_de) and \
                            (regra.valor_ate is None or fat_mes_func <= regra.valor_ate):
                            comissao_regra = (fat_mes_func * regra.percentual) / 100
                     elif regra.valor_fixo is not None:
                         # Verificar faixas (exemplo simples)
                         if (regra.valor_de is None or fat_mes_func >= regra.valor_de) and \
                            (regra.valor_ate is None or fat_mes_func <= regra.valor_ate):
                             comissao_regra = regra.valor_fixo

                     total_comissao_mes += comissao_regra

                 desempenho_func['comissao_total_mes'] = total_comissao_mes

             rh_desempenho[func.id] = desempenho_func

        data['rh']['funcionarios_list'] = rh_funcionarios_list
        data['rh']['desempenho'] = rh_desempenho
        print("Seção RH OK.")

        # ==========================================
        # SESSÃO: METAS
        # ==========================================
        print("Calculando seção Metas...")

        # --- Helper function for Meta Calculation ---
        def calcular_meta_atingida(meta_instance):
            atingido = Decimal(0)
            q_filter = Q(status=True, data__range=(meta_instance.data_inicio, meta_instance.data_fim))

            # Aplicar filtros com base na categoria da meta
            if meta_instance.categoria == 'GERAL':
                # Sem filtro adicional além da data
                 pass
            elif meta_instance.categoria == 'EMPRESA':
                 # Soma faturamento de qualquer registro associado a uma empresa
                 q_filter &= Q(empresa__isnull=False)
            elif meta_instance.categoria == 'FRANQUIA':
                 q_filter &= Q(loja__franquia=True)
            elif meta_instance.categoria == 'LOJAS':
                 # Soma faturamento de qualquer registro associado a uma loja
                 q_filter &= Q(loja__isnull=False)
            elif meta_instance.categoria == 'SETOR' and meta_instance.setor:
                 q_filter &= Q(setor=meta_instance.setor)
            elif meta_instance.categoria == 'OUTROS' and meta_instance.equipe.exists(): # 'Outros' é interpretado como 'Equipe'
                 q_filter &= Q(equipe__in=meta_instance.equipe.all())
            else:
                 # Categoria não tratada ou sem filtro específico, retorna 0
                 return Decimal(0)

            # Executa a agregação
            result = RegisterMoney.objects.filter(q_filter).aggregate(
                total=Coalesce(Sum('valor_est'), Decimal(0))
            )
            atingido = result['total']
            return atingido

        # 1. Categoria: Metas Ativas
        metas_ativas = RegisterMeta.objects.filter(
            status=True,
            data_inicio__lte=now,
            data_fim__gte=now
        ).select_related('setor').prefetch_related('equipe').order_by('titulo')

        metas_ativas_data = []
        for meta in metas_ativas:
            valor_meta = meta.valor or Decimal(0)
            valor_atingido = calcular_meta_atingida(meta)
            valor_restante = max(Decimal(0), valor_meta - valor_atingido)
            percentual_atingido = (valor_atingido / valor_meta * 100) if valor_meta > 0 else Decimal(100) # Se meta é 0, considera 100%

            status_str = "Em andamento"
            if percentual_atingido >= 100:
                status_str = "Concluída"
            elif percentual_atingido >= 85: # Exemplo: Quase lá >= 85%
                status_str = "Quase lá"

            metas_ativas_data.append({
                'id': meta.id,
                'titulo': meta.titulo,
                'valor_meta': valor_meta,
                'valor_atingido': valor_atingido,
                'valor_restante': valor_restante,
                'status': status_str,
                'percentual': percentual_atingido # Adiciona o percentual
            })
        data['metas']['ativas_list'] = metas_ativas_data

        # 2. Categoria: Metas Inativadas (ou Concluídas/Expiradas)
        metas_inativadas = RegisterMeta.objects.filter(
             Q(status=False) | Q(data_fim__lt=now) # Inativas OU que já terminaram
        ).exclude(
            pk__in=[m['id'] for m in metas_ativas_data] # Exclui as ativas já listadas
        ).select_related('setor').prefetch_related('equipe').order_by('-data_fim', 'titulo')[:20] # Limita a 20 mais recentes

        metas_inativadas_data = []
        for meta in metas_inativadas:
            valor_meta = meta.valor or Decimal(0)
            valor_atingido = calcular_meta_atingida(meta) # Recalcula o atingido final
            valor_restante = max(Decimal(0), valor_meta - valor_atingido)
            status_str = "Concluída" if valor_atingido >= valor_meta else "Não atingida"
            if not meta.status:
                 status_str = "Cancelada" # Ou outro termo se status=False tiver outro significado

            metas_inativadas_data.append({
                'id': meta.id,
                'titulo': meta.titulo,
                'valor_meta': valor_meta,
                'valor_atingido': valor_atingido,
                'valor_restante': valor_restante,
                'status': status_str
            })
        data['metas']['inativadas_list'] = metas_inativadas_data
        print("Seção Metas OK.")

        # --- Resposta Final ---
        return JsonResponse(data)

    except Exception as e:
        # Log detailed error in production
        import traceback
        print(f"Erro geral na API do Dashboard Administrativo: {e}")
        print(traceback.format_exc())
        return JsonResponse({'error': 'Erro interno ao processar dados do dashboard.', 'details': str(e)}, status=500)


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

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from apps.siape.models import Reembolso # Importar o modelo Reembolso

@login_required
@require_GET
def api_get_inforeembolso(request):
    """
    API endpoint para buscar informações sobre registros financeiros
    elegíveis para reembolso e registros já reembolsados.

    Retorna dados paginados para popular as tabelas no template reembolso.html.
    Suporta filtros básicos via GET parameters.
    """
    try:
        # --- Parâmetros de Paginação e Filtro ---
        page_registrar_param = request.GET.get('page_registrar', '1')
        page_reverter_param = request.GET.get('page_reverter', '1')
        per_page_param = request.GET.get('per_page', '10')

        # Validar parâmetros de paginação
        try:
            page_registrar = int(page_registrar_param)
            page_reverter = int(page_reverter_param)
            per_page = int(per_page_param)
            if per_page <= 0:
                per_page = 10 # Default seguro
        except ValueError:
            # Se não for um número válido, usar defaults
            page_registrar = 1
            page_reverter = 1
            per_page = 10

        # Filtros para a tabela de registros a reembolsar (baseado no form do template)
        filtro_cpf = request.GET.get('cpf_cliente', '').strip()
        filtro_produto = request.GET.get('produto_nome', '').strip()
        # Adicionar mais filtros conforme necessário (data, setor, etc.)

        # --- Query para Registros Elegíveis para Reembolso ---
        registros_qs = RegisterMoney.objects.filter(
            status=True, # Apenas registros ativos (considerar se status=False pode ser reembolsado)
            reembolso_info__isnull=True # Filtra apenas os que NÃO têm um Reembolso associado
        ).select_related(
            'user', 'produto', 'setor', 'loja' # Otimiza acesso a campos relacionados
        ).order_by('-data') # Ordena pelos mais recentes primeiro

        # Aplicar filtros da busca
        if filtro_cpf:
            # Usar __icontains para busca case-insensitive que contenha o CPF
            registros_qs = registros_qs.filter(cpf_cliente__icontains=filtro_cpf)
        if filtro_produto:
            registros_qs = registros_qs.filter(produto__nome__icontains=filtro_produto)
        # Adicionar lógica para outros filtros aqui...
        # Ex: filtro_setor_id = request.GET.get('setor_id')
        # if filtro_setor_id:
        #     registros_qs = registros_qs.filter(setor_id=filtro_setor_id)

        # Paginação para Registros Elegíveis
        paginator_registrar = Paginator(registros_qs, per_page)
        try:
            registros_paginados = paginator_registrar.page(page_registrar)
        except PageNotAnInteger:
            # Se page não for um inteiro, entrega a primeira página.
            registros_paginados = paginator_registrar.page(1)
            page_registrar = 1
        except EmptyPage:
            # Se page estiver fora do range (e.g. 9999), entrega a última página.
            registros_paginados = paginator_registrar.page(paginator_registrar.num_pages)
            page_registrar = paginator_registrar.num_pages

        # Formatar dados dos registros elegíveis para JSON
        registros_data = []
        for reg in registros_paginados:
            # Tenta obter nome do funcionário associado ao usuário que registrou
            usuario_nome = "Desconhecido" # Default
            try:
                # Assume que existe um Funcionario ligado ao User.
                # Se a relação for opcional ou puder falhar, o try/except é importante.
                funcionario = Funcionario.objects.select_related('usuario').get(usuario=reg.user)
                # Usa apelido se disponível, senão o primeiro nome
                usuario_nome = funcionario.apelido or funcionario.nome_completo.split()[0]
            except Funcionario.DoesNotExist:
                 # Se não há funcionário, usa o username do Django User
                 if reg.user:
                     usuario_nome = reg.user.username
            except Exception as e_func:
                 # Logar erro em produção seria ideal aqui
                 print(f"Aviso: Erro ao buscar funcionário para User ID {reg.user_id}: {e_func}")
                 usuario_nome = f"Erro ({reg.user.username})" if reg.user else "Erro"

            registros_data.append({
                'id': reg.id, # ID do RegisterMoney, usado para a ação de reembolsar
                'cpf_cliente': reg.cpf_cliente or "N/Informado",
                'produto_nome': reg.produto.nome if reg.produto else "N/A",
                'valor': f"{reg.valor_est:.2f}" if reg.valor_est is not None else "0.00",
                'data_registro': reg.data.strftime('%d/%m/%Y %H:%M') if reg.data else "N/A",
                'usuario_nome': usuario_nome,
                'setor_nome': reg.setor.nome if reg.setor else "N/A",
                # Adicionar outros campos se forem necessários no template
                # 'loja_nome': reg.loja.nome if reg.loja else "N/A",
            })

        # --- Query para Registros Já Reembolsados ---
        reembolsados_qs = Reembolso.objects.select_related(
            'registermoney', # Acessa o registro financeiro original via OneToOneField
            'registermoney__produto',
            'registermoney__setor',
            # 'registermoney__user' # Descomentar se precisar do usuário original
        ).filter(
            status=True # Assume que status=True em Reembolso significa que foi efetivado
        ).order_by('-data_reembolso') # Ordena pelos reembolsos mais recentes

        # Aplicar filtros (se houver filtros específicos para esta tabela no futuro)
        # Exemplo: Filtrar reembolsos por CPF do cliente original
        # if filtro_cpf: # Reutilizando o filtro da outra tabela, se aplicável
        #     reembolsados_qs = reembolsados_qs.filter(registermoney__cpf_cliente__icontains=filtro_cpf)

        # Paginação para Registros Reembolsados
        paginator_reverter = Paginator(reembolsados_qs, per_page)
        try:
            reembolsados_paginados = paginator_reverter.page(page_reverter)
        except PageNotAnInteger:
            reembolsados_paginados = paginator_reverter.page(1)
            page_reverter = 1
        except EmptyPage:
            reembolsados_paginados = paginator_reverter.page(paginator_reverter.num_pages)
            page_reverter = paginator_reverter.num_pages

        # Formatar dados dos registros reembolsados para JSON
        reembolsados_data = []
        for remb in reembolsados_paginados:
            reg_orig = remb.registermoney # Acessa o RegisterMoney associado
            reembolsados_data.append({
                # O ID do reembolso é a PK, que é a FK para RegisterMoney
                'reembolso_id': remb.pk,
                'cpf_cliente': reg_orig.cpf_cliente or "N/Informado",
                'produto_nome': reg_orig.produto.nome if reg_orig.produto else "N/A",
                'valor': f"{reg_orig.valor_est:.2f}" if reg_orig.valor_est is not None else "0.00",
                'data_registro': reg_orig.data.strftime('%d/%m/%Y %H:%M') if reg_orig.data else "N/A",
                'data_reembolso': remb.data_reembolso.strftime('%d/%m/%Y') if remb.data_reembolso else "N/A",
                'setor_nome': reg_orig.setor.nome if reg_orig.setor else "N/A",
                # Adicionar outros campos se forem necessários no template
            })

        # --- Estrutura de Resposta JSON ---
        response_data = {
            'registros_para_reembolsar': {
                'items': registros_data,
                'pagination': {
                    'total_items': paginator_registrar.count,
                    'total_pages': paginator_registrar.num_pages,
                    'current_page': page_registrar,
                    'per_page': per_page,
                    'has_previous': registros_paginados.has_previous(),
                    'has_next': registros_paginados.has_next(),
                    'previous_page_number': registros_paginados.previous_page_number() if registros_paginados.has_previous() else None,
                    'next_page_number': registros_paginados.next_page_number() if registros_paginados.has_next() else None,
                }
            },
            'registros_reembolsados': {
                'items': reembolsados_data,
                'pagination': {
                    'total_items': paginator_reverter.count,
                    'total_pages': paginator_reverter.num_pages,
                    'current_page': page_reverter,
                    'per_page': per_page,
                    'has_previous': reembolsados_paginados.has_previous(),
                    'has_next': reembolsados_paginados.has_next(),
                    'previous_page_number': reembolsados_paginados.previous_page_number() if reembolsados_paginados.has_previous() else None,
                    'next_page_number': reembolsados_paginados.next_page_number() if reembolsados_paginados.has_next() else None,
                }
            },
            # Adicionar estatísticas gerais se necessário (ex: contagens totais)
            'stats': {
                 'total_elegiveis': paginator_registrar.count,
                 'total_reembolsados': paginator_reverter.count,
                 # Poderia adicionar totais por período aqui se calculado no backend
                 # Ex: total_reembolsado_mes = Reembolso.objects.filter(data_reembolso__month=timezone.now().month, data_reembolso__year=timezone.now().year).aggregate(Sum('registermoney__valor_est'))['registermoney__valor_est__sum'] or 0
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        # É crucial logar o erro em um ambiente de produção
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.error(f"Erro em api_get_inforeembolso: {e}", exc_info=True)
        print(f"Erro em api_get_inforeembolso: {e}")
        import traceback
        traceback.print_exc() # Imprime o traceback no console do servidor para debug
        return JsonResponse({'error': 'Erro interno ao buscar informações de reembolso.', 'details': str(e)}, status=500)

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
    - registros_reembolsados: lista de Reembolso já feitos (com dados extras)
    - stats: contagens de Reembolso nos períodos 90d, 60d e mês atual
    """

    cpf = request.GET.get('cpf_cliente', '').strip()
    produto = request.GET.get('produto_nome', '').strip()

    # — Registros ainda para reembolsar —
    qs_para = RegisterMoney.objects.filter(
        status=True,
        reembolso_info__isnull=True
    ).select_related('produto')
    if cpf:
        qs_para = qs_para.filter(cpf_cliente__icontains=cpf)
    if produto:
        qs_para = qs_para.filter(produto__nome__icontains=produto)

    registros_para = [
        {
            'id': reg.id,
            'cpf_cliente': reg.cpf_cliente,
            'produto_nome': reg.produto.nome,
            'valor': f"{reg.valor_est:.2f}",
            'data_registro': reg.data.strftime('%d/%m/%Y %H:%M'),
        }
        for reg in qs_para
    ]

    # — Registros já reembolsados —
    qs_remb = Reembolso.objects.filter(status=True).select_related(
        'registermoney__produto', 'registermoney__setor'
    )
    if cpf:
        qs_remb = qs_remb.filter(registermoney__cpf_cliente__icontains=cpf)

    registros_remb = []
    for remb in qs_remb:
        orig = remb.registermoney
        registros_remb.append({
            'reembolso_id': remb.pk,
            'cpf_cliente': orig.cpf_cliente,
            'produto_nome': orig.produto.nome if orig.produto else 'N/A',
            'valor': f"{orig.valor_est:.2f}",
            'setor_nome': orig.setor.nome if orig.setor else 'N/A',
            'data_registro': orig.data.strftime('%d/%m/%Y %H:%M'),
            'data_reembolso': remb.data_reembolso.strftime('%d/%m/%Y'),
        })

    # — Estatísticas de Reembolso —
    hoje = timezone.now().date()
    qs_todos = Reembolso.objects.filter(status=True)

    total_90d = qs_todos.filter(data_reembolso__gte=hoje - timedelta(days=90)).count()
    total_60d = qs_todos.filter(data_reembolso__gte=hoje - timedelta(days=60)).count()
    total_mes_atual = qs_todos.filter(
        data_reembolso__year=hoje.year,
        data_reembolso__month=hoje.month
    ).count()

    return JsonResponse({
        'registros_para_reembolsar': registros_para,
        'registros_reembolsados': registros_remb,
        'stats': {
            'reembolsos_90d': total_90d,
            'reembolsos_60d': total_60d,
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
    """
    Recebe JSON com lista de agendamentos e importa para Agendamento.
    Headers esperados por linha: cpf_cliente, dia_agendado (ISO), loja_id,
    atendente_id, tabulacao_agendamento.
    """
    print("Iniciando api_post_csvagendamento")
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
            cliente = ClienteAgendamento.objects.get(cpf=row['cpf_cliente'])
            dia     = parse_datetime(row['dia_agendado'])
            loja    = Loja.objects.get(pk=row['loja_id'])
            user    = User.objects.get(pk=row['atendente_id'])
            print(f"Objetos relacionados obtidos: Cliente({cliente.id}), Loja({loja.id}), User({user.id})")

            agendamento = Agendamento.objects.create(
                cliente_agendamento  = cliente,
                dia_agendado         = dia,
                loja                 = loja,
                atendente_agendou    = user,
                tabulacao_agendamento= row.get('tabulacao_agendamento', '')
            )
            print(f"Agendamento criado com ID: {agendamento.id}")
            created += 1
        except Exception as e:
            print(f"Erro na linha {i}: {str(e)}")
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
