from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import *
from apps.inss.models import *
from apps.funcionarios.models import Funcionario, Empresa, Departamento, Setor, Cargo, Loja, Equipe
from apps.siape.models import Cliente as ClienteSiape
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from datetime import datetime
import re
from django.contrib.auth import get_user_model
from django.db import models
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from custom_tags_app.templatetags.permissionsacess import controle_acess
from django.db.models import Sum

# Create your views here.


@login_required(login_url='/')
@controle_acess('SCT60')
def render_acoes(request):
    """
    View para renderizar a página de listagem de ações.
    """
    print('[render_acoes] Renderizando página de listagem de ações')
    return render(request, 'apps/juridico/acoes.html')


@login_required(login_url='/')
@controle_acess('SCT59')
def render_addacao(request):
    """
    View para renderizar a página de adicionar nova ação.
    """
    print('[render_addacao] Renderizando página de adicionar nova ação')
    # Busca o funcionário associado ao usuário logado
    funcionario_logado = None
    hierarquia = None
    try:
        funcionario_logado = request.user.funcionario_profile
        hierarquia = funcionario_logado.cargo.hierarquia if funcionario_logado and funcionario_logado.cargo else None
    except Exception:
        pass
    return render(request, 'apps/juridico/adicionar_acao.html', {
        'usuario_logado_id': request.user.id,
        'hierarquia_logado': hierarquia,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_post_addacao(request):
    print('[ADDACAO] Iniciando api_post_addacao')
    if request.method == 'POST':
        try:
            # Campos obrigatórios básicos
            required_fields = [
                'nome_cliente', 'cpf_cliente', 'contato', 'funcionario', 
                'tipo_acao', 'tipo_pagamento'
            ]
            missing_fields = [field for field in required_fields if not request.POST.get(field)]
            if missing_fields:
                return JsonResponse({'status': 'error', 'message': f'Campos obrigatórios faltando: {", ".join(missing_fields)}'}, status=400)

            # Obter dados do cliente do formulário
            nome_cliente_form = request.POST.get('nome_cliente')
            cpf_cliente_form = request.POST.get('cpf_cliente', '').replace('.', '').replace('-', '') # Limpa máscara do CPF
            contato_form = request.POST.get('contato')

            # Verificar se o CPF é válido (simples verificação de tamanho)
            if not cpf_cliente_form or len(cpf_cliente_form) != 11:
                return JsonResponse({'status': 'error', 'message': 'CPF inválido ou não fornecido.'}, status=400)

            # Cria ou obtém o ClienteAcao
            cliente_acao, created = ClienteAcao.objects.get_or_create(
                cpf=cpf_cliente_form,
                defaults={
                    'nome': nome_cliente_form,
                    'contato': contato_form
                }
            )
            if created:
                print(f'[ADDACAO] Novo ClienteAcao criado: {cliente_acao}')
            else:
                # Opcional: Atualizar nome/contato se diferente do formulário
                if cliente_acao.nome != nome_cliente_form or cliente_acao.contato != contato_form:
                    cliente_acao.nome = nome_cliente_form
                    cliente_acao.contato = contato_form
                    cliente_acao.save()
                    print(f'[ADDACAO] ClienteAcao existente ({cliente_acao.cpf}) atualizado com novos dados do formulário.')
                else:
                    print(f'[ADDACAO] ClienteAcao existente encontrado: {cliente_acao}')

            # Funcionário e Tipo de Ação
            funcionario_id = request.POST.get('funcionario')
            try:
                funcionario = Funcionario.objects.get(id=funcionario_id)
            except Funcionario.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Funcionário não encontrado'}, status=400)

            tipo_acao = request.POST.get('tipo_acao')
            if tipo_acao not in [choice[0] for choice in Acoes.TipoAcaoChoices.choices]:
                return JsonResponse({'status': 'error', 'message': 'Tipo de ação inválido'}, status=400)

            # Verificar se há uma loja especificada
            loja_id = request.POST.get('loja')
            loja = None
            if loja_id:
                try:
                    loja = Loja.objects.get(id=loja_id)
                    print(f'[ADDACAO] Loja encontrada: {loja.nome}')
                except Loja.DoesNotExist:
                    print(f'[ADDACAO] Loja com ID {loja_id} não encontrada')
                    # Não retornamos erro para não interromper a criação da ação

            # Cria a Ação
            acao = Acoes.objects.create(
                cliente=cliente_acao,
                vendedor_responsavel=funcionario.usuario,
                tipo_acao=tipo_acao,
                status_emcaminhamento=Acoes.StatusChoices.EM_ESPERA,
                loja=loja
            )
            print(f'[ADDACAO] Ação criada com ID: {acao.id} para o cliente {cliente_acao.cpf}')

            # Processamento de Pagamento
            tipo_pagamento = request.POST.get('tipo_pagamento')
            if tipo_pagamento != 'SEM_PAGAMENTO':
                try:
                    valor_entrada = Decimal(request.POST.get('valor_entrada', '0').replace('.', '').replace(',', '.')) if request.POST.get('valor_entrada') else Decimal('0')
                    qtd_parcelas = int(request.POST.get('qtd_parcelas', 0)) if request.POST.get('qtd_parcelas') else 0
                    valor_parcela = Decimal(request.POST.get('valor_parcela', '0').replace('.', '').replace(',', '.')) if request.POST.get('valor_parcela') else Decimal('0')

                    # Mapeia o tipo de pagamento do formulário para o modelo
                    tipo_pagamento_model = {
                        'A_VISTA': RegistroPagamentos.TipoPagamentoChoices.A_VISTA,
                        'PARCELADO': RegistroPagamentos.TipoPagamentoChoices.PARCELADO
                    }.get(tipo_pagamento)

                    if not tipo_pagamento_model:
                        return JsonResponse({'status': 'error', 'message': 'Tipo de pagamento inválido'}, status=400)

                    if tipo_pagamento == 'PARCELADO':
                        valor_total = valor_entrada + (qtd_parcelas * valor_parcela)
                    else:  # A_VISTA
                        valor_total = Decimal(request.POST.get('valor_total', '0').replace('.', '').replace(',', '.')) if request.POST.get('valor_total') else Decimal('0')

                    RegistroPagamentos.objects.create(
                        acao_inss=acao,
                        tipo_pagamento=tipo_pagamento_model,
                        valor_total=valor_total,
                        valor_entrada=valor_entrada,
                        parcelas_totais=qtd_parcelas,
                        parcelas_restantes=qtd_parcelas,
                        parcelas_pagas=0,
                        status=RegistroPagamentos.StatusPagamentoChoices.EM_ANDAMENTO
                    )
                    print('[ADDACAO] Pagamento registrado')
                except (InvalidOperation, ValueError) as e:
                    return JsonResponse({'status': 'error', 'message': f'Erro ao processar pagamento: {str(e)}'}, status=400)

            # Processa os arquivos
            for key in request.FILES:
                if key.startswith('documento_'):
                    try:
                        file = request.FILES[key]
                        titulo = request.POST.get(f'titulo_{key}', 'Documento')
                        ArquivosAcoesINSS.objects.create(
                            acao_inss=acao,
                            titulo=titulo,
                            file=file
                        )
                        print(f'[ADDACAO] Arquivo processado: {key}')
                    except Exception as e:
                        return JsonResponse({'status': 'error', 'message': f'Erro ao processar arquivo {key}: {str(e)}'}, status=400)

            print(f'[ADDACAO] Documentos processados para ação {acao.id}')

            return JsonResponse({'status': 'success', 'message': 'Ação e pagamento adicionados com sucesso!', 'acao_id': acao.id})
        except Exception as e:
            print(f'[ADDACAO] Erro ao adicionar ação: {str(e)}')
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f'Erro interno do servidor: {str(e)}'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método não permitido'}, status=405)


@require_http_methods(["GET"])
def api_get_infogeral(request):
    """
    API para obter informações gerais do sistema.
    Retorna listas de funcionários, empresas, departamentos, setores, cargos, lojas e equipes.
    """
    print('[api_get_infogeral] Iniciando busca de informações gerais')
    try:
        # Busca o funcionário associado ao usuário logado
        funcionario_logado = None
        hierarquia = None
        try:
            funcionario_logado = request.user.funcionario_profile
            hierarquia = funcionario_logado.cargo.hierarquia if funcionario_logado and funcionario_logado.cargo else None
        except Exception:
            pass
        is_superuser = request.user.is_superuser
        HIERARQUIA_PADRAO = 2
        HIERARQUIA_ESTAGIO = 1

        # Lista de funcionários ativos
        if is_superuser or (hierarquia and hierarquia > HIERARQUIA_PADRAO):
            funcionarios = Funcionario.objects.filter(status=True).values('nome_completo', 'usuario__id')
        else:
            funcionarios = Funcionario.objects.filter(status=True, usuario=request.user).values('nome_completo', 'usuario__id')
        funcionarios_list = [
            {'nome': f['nome_completo'], 'value': f['usuario__id']}
            for f in funcionarios if f['usuario__id'] is not None
        ]

        # Lista de empresas ativas
        empresas = Empresa.objects.filter(status=True).values('id', 'nome')
        empresas_list = [
            {'id': e['id'], 'nome': e['nome']}
            for e in empresas
        ]

        # Lista de departamentos ativos
        departamentos = Departamento.objects.filter(status=True).values('id', 'nome', 'empresa__nome')
        departamentos_list = [
            {'id': d['id'], 'nome': d['nome'], 'empresa': d['empresa__nome']}
            for d in departamentos
        ]

        # Lista de setores ativos
        setores = Setor.objects.filter(status=True).values('id', 'nome', 'departamento__nome')
        setores_list = [
            {'id': s['id'], 'nome': s['nome'], 'departamento': s['departamento__nome']}
            for s in setores
        ]

        # Lista de cargos ativos
        cargos = Cargo.objects.filter(status=True).values('id', 'nome', 'empresa__nome')
        cargos_list = [
            {'id': c['id'], 'nome': c['nome'], 'empresa': c['empresa__nome']}
            for c in cargos
        ]

        # Lista de lojas ativas
        lojas = Loja.objects.filter(status=True).values('id', 'nome', 'empresa__nome')
        lojas_list = [
            {'id': l['id'], 'nome': l['nome'], 'empresa': l['empresa__nome']}
            for l in lojas
        ]

        # Lista de equipes ativas
        equipes = Equipe.objects.filter(status=True).values('id', 'nome')
        equipes_list = [
            {'id': e['id'], 'nome': e['nome']}
            for e in equipes
        ]

        print('[api_get_infogeral] Dados retornados com sucesso')
        return JsonResponse({
            'status': 'success',
            'data': {
                'funcionarios': funcionarios_list,
                'empresas': empresas_list,
                'departamentos': departamentos_list,
                'setores': setores_list,
                'cargos': cargos_list,
                'lojas': lojas_list,
                'equipes': equipes_list
            }
        })

    except Exception as e:
        print(f'[api_get_infogeral] Erro ao obter informações: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao obter informações: {str(e)}'
        }, status=500)


@login_required(login_url='/')
@require_http_methods(["GET"])
def api_get_vizualizararquivo(request, arquivo_id):
    """
    API para visualizar um arquivo de uma ação INSS.
    Recebe o ID do arquivo e retorna a URL para visualização.
    """
    print(f'[api_get_vizualizararquivo] Buscando arquivo com ID: {arquivo_id}')
    try:
        # Busca o arquivo pelo ID
        arquivo = ArquivosAcoesINSS.objects.get(id=arquivo_id)
        
        # Verifica se o arquivo existe
        if not arquivo.file:
            print(f'[api_get_vizualizararquivo] Arquivo não encontrado para o ID: {arquivo_id}')
            return JsonResponse({
                'status': 'error',
                'message': 'Arquivo não encontrado'
            }, status=404)
        
        # Obtém a URL do arquivo
        arquivo_url = arquivo.file.url
        
        print(f'[api_get_vizualizararquivo] Arquivo encontrado: {arquivo.titulo}, URL: {arquivo_url}')
        
        # Retorna os dados do arquivo
        return JsonResponse({
            'status': 'success',
            'data': {
                'id': arquivo.id,
                'titulo': arquivo.titulo,
                'url': arquivo_url,
                'data_import': arquivo.data_import.strftime('%d/%m/%Y %H:%M'),
                'acao_id': arquivo.acao_inss.id
            }
        })
        
    except ArquivosAcoesINSS.DoesNotExist:
        print(f'[api_get_vizualizararquivo] Arquivo com ID {arquivo_id} não existe')
        return JsonResponse({
            'status': 'error',
            'message': 'Arquivo não encontrado'
        }, status=404)
    except Exception as e:
        print(f'[api_get_vizualizararquivo] Erro ao buscar arquivo: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar arquivo: {str(e)}'
        }, status=500)



@require_http_methods(["GET"])
def api_get_cpfcliente(request):
    """
    API para buscar informações do cliente pelo CPF.
    Pesquisa em diferentes modelos do sistema.
    """
    print('[api_get_cpfcliente] Iniciando busca de cliente por CPF')
    try:
        cpf = request.GET.get('cpf', '')
        if not cpf:
            print('[api_get_cpfcliente] CPF não fornecido')
            return JsonResponse({
                'status': 'error',
                'message': 'CPF não fornecido'
            }, status=400)

        # Normaliza o CPF (remove caracteres não numéricos)
        cpf_normalizado = re.sub(r'\D', '', cpf)

        # Busca em diferentes modelos
        cliente_info = {}

        # Busca no modelo ClienteSiape
        try:
            cliente_siape = ClienteSiape.objects.get(cpf=cpf_normalizado)
            cliente_info['siape'] = {
                'nome': cliente_siape.nome,
                'modelo': 'ClienteSiape'
            }
        except ClienteSiape.DoesNotExist:
            pass

        # Busca no modelo ClienteAgendamento
        try:
            cliente_agendamento = ClienteAgendamento.objects.get(cpf=cpf_normalizado)
            cliente_info['agendamento'] = {
                'nome': cliente_agendamento.nome_completo,
                'modelo': 'ClienteAgendamento'
            }
        except ClienteAgendamento.DoesNotExist:
            pass

        if not cliente_info:
            return JsonResponse({
                'status': 'error',
                'message': 'Cliente não encontrado'
            }, status=404)

        print('[api_get_cpfcliente] Cliente encontrado:', cliente_info)
        return JsonResponse({
            'status': 'success',
            'data': cliente_info
        })

    except Exception as e:
        print(f'[api_get_cpfcliente] Erro ao buscar cliente: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar cliente: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_tabelaacoes(request):
    """
    API para obter dados das ações INSS para popular a tabela.
    Suporta filtros por nome, CPF, status e tipo de ação.
    Retorna todas as ações, incluindo as do tipo Limpa Nome.
    """
    try:
        print('[GET_TABELA] Iniciando busca de ações')
        query = Acoes.objects.select_related(
            'cliente',
            'loja'
        )
        # Filtro para mostrar apenas ações sem advogado_responsavel e excluir LIMPANOME
        query = query.filter(advogado_responsavel__isnull=True).exclude(
            tipo_acao=Acoes.TipoAcaoChoices.LIMPA_NOME.value  # Exclui ações do tipo LIMPANOME
        )
        print('[GET_TABELA] Total de ações iniciais (excluindo LIMPANOME):', query.count())

        # Obtém os parâmetros de filtro da requisição GET
        nome = request.GET.get('nome', '').strip()
        cpf = request.GET.get('cpf', '').strip()
        status = request.GET.get('status', '').strip()
        tipo_acao = request.GET.get('tipo_acao', '').strip()
        mostrar_inativas = request.GET.get('mostrar_inativas', 'false').lower() == 'true'

        print('[GET_TABELA] Filtros recebidos:', {
            'nome': nome,
            'cpf': cpf,
            'status': status,
            'tipo_acao': tipo_acao,
            'mostrar_inativas': mostrar_inativas
        })

        # Filtra por status ativo/inativo
        if not mostrar_inativas:
            query = query.filter(status=True)

        # Aplica filtros se fornecidos
        if nome:
            print('[GET_TABELA] Aplicando filtro por nome:', nome)
            query = query.filter(cliente__nome__icontains=nome)
            print('[GET_TABELA] Total após filtro por nome:', query.count())
        
        if cpf:
            # Remove caracteres não numéricos do CPF
            cpf_limpo = re.sub(r'\D', '', cpf)
            print('[GET_TABELA] Aplicando filtro por CPF:', cpf_limpo)
            query = query.filter(cliente__cpf__icontains=cpf_limpo)
            print('[GET_TABELA] Total após filtro por CPF:', query.count())
        
        if status:
            print('[GET_TABELA] Aplicando filtro por status:', status)
            query = query.filter(status_emcaminhamento=status)
            print('[GET_TABELA] Total após filtro por status:', query.count())
        
        if tipo_acao:
            print('[GET_TABELA] Aplicando filtro por tipo de ação:', tipo_acao)
            query = query.filter(tipo_acao=tipo_acao)
            print('[GET_TABELA] Total após filtro por tipo de ação:', query.count())

        # Ordena por data de criação (mais recente primeiro)
        query = query.order_by('-data_criacao')
        print('[GET_TABELA] Total final de ações:', query.count())

        # Prepara os dados para retorno
        acoes_list = []
        for acao in query:
            print(f'\n[GET_TABELA] Processando ação ID: {acao.id}')
            
            # Obtém informações do cliente
            cliente_nome = 'N/A'
            cliente_cpf = 'N/A'
            
            if acao.cliente:
                cliente_nome = acao.cliente.nome if acao.cliente.nome else 'N/A'
                cliente_cpf = acao.cliente.cpf if acao.cliente.cpf else 'N/A'
                print(f'[GET_TABELA] Cliente encontrado: {cliente_nome}, CPF: {cliente_cpf}')

            acao_data = {
                'id': acao.id,
                'cliente_nome': cliente_nome,
                'cliente_cpf': cliente_cpf,  
                'tipo_acao': acao.get_tipo_acao_display(),
                'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'status': acao.get_status_emcaminhamento_display(),
                'sentenca': acao.get_sentenca_display() if acao.sentenca else 'N/A',
                'loja': acao.loja.nome if acao.loja else 'N/A',
                'ativo': acao.status,
                'motivo_inatividade': acao.motivo_inatividade if not acao.status else None
            }
            print(f'[GET_TABELA] Dados da ação preparados:', acao_data)
            acoes_list.append(acao_data)

        print(f'\n[GET_TABELA] Total de ações retornadas: {len(acoes_list)}')
        return JsonResponse({
            'status': 'success',
            'data': acoes_list
        })

    except Exception as e:
        print(f'[GET_TABELA] Erro ao buscar ações: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar ações: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_tabelaacoes_limpanome(request):
    """
    API para obter dados das ações Limpa Nome para popular a tabela.
    Suporta filtros por nome, CPF e status.
    Retorna apenas ações do tipo Limpa Nome.
    """
    try:
        print('[GET_TABELA_LIMPANOME] Iniciando busca de ações Limpa Nome')
        query = Acoes.objects.select_related(
            'cliente',
            'vendedor_responsavel',
            'advogado_responsavel',
            'loja'
        ).filter(tipo_acao='LIMPANOME')
        print('[GET_TABELA_LIMPANOME] Total de ações iniciais:', query.count())

        # Obtém os parâmetros de filtro da requisição GET
        nome = request.GET.get('nome', '').strip()
        cpf = request.GET.get('cpf', '').strip()
        status = request.GET.get('status', '').strip()
        mostrar_inativas = request.GET.get('mostrar_inativas', 'false').lower() == 'true'

        print('[GET_TABELA_LIMPANOME] Filtros recebidos:', {
            'nome': nome,
            'cpf': cpf,
            'status': status,
            'mostrar_inativas': mostrar_inativas
        })

        # Filtra por status ativo/inativo
        if not mostrar_inativas:
            query = query.filter(status=True)

        # Aplica filtros se fornecidos
        if nome:
            print('[GET_TABELA_LIMPANOME] Aplicando filtro por nome:', nome)
            query = query.filter(cliente__nome__icontains=nome)
            print('[GET_TABELA_LIMPANOME] Total após filtro por nome:', query.count())
        
        if cpf:
            cpf_limpo = re.sub(r'\D', '', cpf)
            print('[GET_TABELA_LIMPANOME] Aplicando filtro por CPF:', cpf_limpo)
            query = query.filter(cliente__cpf__icontains=cpf_limpo)
            print('[GET_TABELA_LIMPANOME] Total após filtro por CPF:', query.count())
        
        if status:
            print('[GET_TABELA_LIMPANOME] Aplicando filtro por status:', status)
            query = query.filter(status_emcaminhamento=status)
            print('[GET_TABELA_LIMPANOME] Total após filtro por status:', query.count())

        # Ordena por data de criação (mais recente primeiro)
        query = query.order_by('-data_criacao')
        print('[GET_TABELA_LIMPANOME] Total final de ações:', query.count())

        # Prepara os dados para retorno
        acoes_list = []
        for acao in query:
            print(f'\n[GET_TABELA_LIMPANOME] Processando ação ID: {acao.id}')
            cliente_nome = acao.cliente.nome if acao.cliente and acao.cliente.nome else 'N/A'
            cliente_cpf = acao.cliente.cpf if acao.cliente and acao.cliente.cpf else 'N/A'
            print(f'[GET_TABELA_LIMPANOME] Cliente encontrado: {cliente_nome}, CPF: {cliente_cpf}')

            acao_data = {
                'id': acao.id,
                'cliente_nome': cliente_nome,
                'cliente_cpf': cliente_cpf,
                'tipo_acao': acao.get_tipo_acao_display(),
                'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'status': acao.get_status_emcaminhamento_display(),
                'sentenca': 'N/A',  # Removido pois não existe mais
                'loja': acao.loja.nome if acao.loja else 'N/A',
                'ativo': acao.status,
                'motivo_inatividade': acao.motivo_inatividade if not acao.status else None
            }
            print(f'[GET_TABELA_LIMPANOME] Dados da ação preparados:', acao_data)
            acoes_list.append(acao_data)

        print(f'\n[GET_TABELA_LIMPANOME] Total de ações retornadas: {len(acoes_list)}')
        return JsonResponse({
            'status': 'success',
            'data': acoes_list
        })

    except Exception as e:
        print(f'[GET_TABELA_LIMPANOME] Erro ao buscar ações Limpa Nome: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar ações Limpa Nome: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_acao(request, acao_id):
    """
    API para obter dados de uma ação específica.
    """
    print(f'[GET_ACAO] Buscando ação {acao_id}')
    try:
        acao = Acoes.objects.select_related('cliente', 'loja').get(id=acao_id)
        print(f'[GET_ACAO] Ação encontrada: {acao}')
        
        # Obtém o nome do cliente
        cliente_nome = acao.cliente.nome if acao.cliente else 'N/A'
        
        # Obtém os arquivos da ação (ArquivosAcoesINSS)
        arquivos_qs = ArquivosAcoesINSS.objects.filter(acao_inss=acao)
        arquivos_acao = []
        
        # Processa cada arquivo com tratamento de erros
        for arquivo_instance in arquivos_qs:
            try:
                arquivo_url = arquivo_instance.file.url if arquivo_instance.file else None
                arquivos_acao.append({
                    'id': arquivo_instance.id, 
                    'titulo': arquivo_instance.titulo, 
                    'url': arquivo_url, 
                    'data_import': arquivo_instance.data_import.isoformat() if arquivo_instance.data_import else None,
                    'tipo': 'arquivo'
                })
            except (AttributeError, ValueError) as e:
                print(f'[GET_ACAO] Erro ao processar arquivo {arquivo_instance.id if arquivo_instance else "N/A"}: {str(e)}')
                # Adiciona o arquivo sem a URL se houver erro
                arquivos_acao.append({
                    'id': arquivo_instance.id if arquivo_instance else None, 
                    'titulo': arquivo_instance.titulo if arquivo_instance else 'Erro', 
                    'url': None, 
                    'data_import': arquivo_instance.data_import.isoformat() if arquivo_instance and arquivo_instance.data_import else None,
                    'tipo': 'arquivo'
                })
        
        # Obtém os documentos da ação (DocsAcaoINSS)
        docs_qs = DocsAcaoINSS.objects.filter(acao_inss=acao)
        docs_acao = []
        
        # Processa cada documento com tratamento de erros
        for doc_instance in docs_qs:
            try:
                doc_url = doc_instance.file.url if doc_instance.file else None
                docs_acao.append({
                    'id': doc_instance.id, 
                    'titulo': doc_instance.titulo, 
                    'url': doc_url, 
                    'data_import': doc_instance.data_import.isoformat() if doc_instance.data_import else None,
                    'tipo': 'documento'
                })
            except (AttributeError, ValueError) as e:
                print(f'[GET_ACAO] Erro ao processar documento {doc_instance.id if doc_instance else "N/A"}: {str(e)}')
                # Adiciona o documento sem a URL se houver erro
                docs_acao.append({
                    'id': doc_instance.id if doc_instance else None, 
                    'titulo': doc_instance.titulo if doc_instance else 'Erro', 
                    'url': None, 
                    'data_import': doc_instance.data_import.isoformat() if doc_instance and doc_instance.data_import else None,
                    'tipo': 'documento'
                })
        
        # Combina arquivos e documentos em uma única lista
        documentos_acao = arquivos_acao + docs_acao
        
        # Obtém os pagamentos da ação
        pagamentos = RegistroPagamentosFeitos.objects.filter(registro_pagamento__acao_inss=acao).values('id', 'valor_pago', 'data_pagamento', 'parcela_paga')
        
        # Prepara os dados para retorno
        dados_acao = {
            'id': acao.id,
            'nome_cliente': cliente_nome,
            'cpf_cliente': acao.cliente.cpf if acao.cliente else 'N/A',  
            'tipo_acao': acao.tipo_acao,
            'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'status_emcaminhamento': acao.status_emcaminhamento,
            'sentenca': acao.sentenca,
            'grau_sentenca': acao.grau_sentenca,
            'valor_sentenca': str(acao.valor_sentenca) if acao.valor_sentenca else None,
            'data_sentenca': acao.data_sentenca.strftime('%Y-%m-%d') if acao.data_sentenca else None,
            'recurso_primeiro_grau': acao.recurso_primeiro_grau,
            'data_recurso_primeiro_grau': acao.data_recurso_primeiro_grau.strftime('%Y-%m-%d') if acao.data_recurso_primeiro_grau else None,
            'recurso_segundo_grau': acao.recurso_segundo_grau,
            'data_recurso_segundo_grau': acao.data_recurso_segundo_grau.strftime('%Y-%m-%d') if acao.data_recurso_segundo_grau else None,
            'senha_inss': acao.senha_inss,
            'status': acao.status,
            'motivo_inatividade': acao.motivo_inatividade,
            'documentos_acao': documentos_acao,
            'pagamentos': list(pagamentos),
            'responsavel': acao.vendedor_responsavel.id if acao.vendedor_responsavel else None,
            'responsavel_nome': acao.vendedor_responsavel.get_full_name() if acao.vendedor_responsavel else 'N/A',
            'loja': acao.loja.nome if acao.loja else 'N/A',
            'loja_id': acao.loja.id if acao.loja else None
        }

        print(f'[GET_ACAO] Dados encontrados para ação {acao_id}:', dados_acao)
        
        return JsonResponse({
            'success': True,
            'data': dados_acao
        })

    except Exception as e:
        print(f'[GET_ACAO] Erro ao buscar ação {acao_id}:', str(e))
        import traceback
        traceback.print_exc()  # Adiciona stack trace para debug
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar ação: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_documento(request, doc_id):
    """
    API para obter os dados de um documento específico.
    Retorna os dados do documento incluindo a URL do arquivo.
    """
    try:
        documento = ArquivosAcoesINSS.objects.get(id=doc_id)
        
        # Verifica se o documento tem um arquivo e se o arquivo tem uma URL
        try:
            arquivo_url = documento.file.url if documento.file else None
        except (AttributeError, ValueError):
            arquivo_url = None
            print(f'[DOCUMENTO] Erro ao obter URL do arquivo para documento {doc_id}')
        
        if not arquivo_url:
            return JsonResponse({
                'success': False,
                'message': 'Arquivo não encontrado ou inválido'
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': documento.id,
                'titulo': documento.titulo,
                'arquivo': arquivo_url,
                'data_import': documento.data_import.isoformat() if documento.data_import else None
            }
        })
        
    except ArquivosAcoesINSS.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Documento não encontrado'
        }, status=404)
    except Exception as e:
        print(f'[DOCUMENTO] Erro ao buscar documento {doc_id}:', str(e))
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar documento: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_documento_acao(request, doc_id):
    """
    API para obter os dados de um documento da ação (DocsAcaoINSS).
    Retorna os dados do documento incluindo a URL do arquivo.
    """
    try:
        documento = DocsAcaoINSS.objects.get(id=doc_id)
        
        # Verifica se o documento tem um arquivo e se o arquivo tem uma URL
        try:
            arquivo_url = documento.file.url if documento.file else None
        except (AttributeError, ValueError):
            arquivo_url = None
            print(f'[DOCUMENTO_ACAO] Erro ao obter URL do arquivo para documento {doc_id}')
        
        if not arquivo_url:
            return JsonResponse({
                'success': False,
                'message': 'Arquivo não encontrado ou inválido'
            }, status=404)

        return JsonResponse({
            'success': True,
            'data': {
                'id': documento.id,
                'titulo': documento.titulo,
                'arquivo': arquivo_url,
                'data_import': documento.data_import.isoformat() if documento.data_import else None
            }
        })

    except DocsAcaoINSS.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Documento não encontrado'
        }, status=404)
    except Exception as e:
        print(f'[DOCUMENTO_ACAO] Erro ao buscar documento {doc_id}:', str(e))
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar documento: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_post_attstatus(request):
    """
    API para atualizar o status de uma ação INSS.
    """
    print('\n[ATTSTATUS] ===== INÍCIO DA REQUISIÇÃO =====')
    print('[ATTSTATUS] Método:', request.method)
    print('[ATTSTATUS] Content-Type:', request.content_type)
    print('[ATTSTATUS] POST data:', request.POST.dict())
    
    try:
        # Obtém os dados do POST
        acao_id = request.POST.get('acao_id')
        novo_status = request.POST.get('status')  
        observacao = request.POST.get('observacao', '')
        numero_protocolo = request.POST.get('numero_protocolo')
        motivo_incompleto = request.POST.get('motivo_incompleto')

        print('[ATTSTATUS] Dados extraídos:')
        print('- acao_id:', acao_id)
        print('- novo_status:', novo_status)
        print('- observacao:', observacao)
        print('- numero_protocolo:', numero_protocolo)
        print('- motivo_incompleto:', motivo_incompleto)

        # Validação básica
        if not acao_id or not novo_status:
            print('[ATTSTATUS] Erro: Campos obrigatórios faltando')
            return JsonResponse({
                'status': 'error',
                'message': 'ID da ação e novo status são obrigatórios'
            }, status=400)
            
        # Validação para campos condicionais
        if novo_status == 'PROTOCOLADO' and not numero_protocolo:
            print('[ATTSTATUS] Erro: Número do protocolo obrigatório para status PROTOCOLADO')
            return JsonResponse({
                'status': 'error',
                'message': 'Número do protocolo é obrigatório quando o status é Protocolado'
            }, status=400)
            
        if novo_status == 'INCOMPLETO' and not motivo_incompleto:
            print('[ATTSTATUS] Erro: Motivo da incompletude obrigatório para status INCOMPLETO')
            return JsonResponse({
                'status': 'error',
                'message': 'Motivo da incompletude é obrigatório quando o status é Incompleto'
            }, status=400)

        # Busca a ação
        try:
            acao = Acoes.objects.get(id=acao_id)
            print(f'[ATTSTATUS] Ação encontrada: {acao.id} - Status atual: {acao.status_emcaminhamento}')
        except Acoes.DoesNotExist:
            print(f'[ATTSTATUS] Erro: Ação {acao_id} não encontrada')
            return JsonResponse({
                'status': 'error',
                'message': 'Ação não encontrada'
            }, status=404)

        # Valida se o status é válido
        status_validos = [choice[0] for choice in Acoes.StatusChoices.choices]
        print('[ATTSTATUS] Status válidos:', status_validos)
        if novo_status not in status_validos:
            print(f'[ATTSTATUS] Erro: Status inválido - {novo_status}')
            return JsonResponse({
                'status': 'error',
                'message': 'Status inválido'
            }, status=400)

        # Atualiza o status e campos relacionados
        acao.status_emcaminhamento = novo_status
        print(f'[ATTSTATUS] Status atualizado para: {novo_status}')
        
        # Se o status for PROTOCOLADO, atualiza o número do protocolo
        if novo_status == 'PROTOCOLADO' and numero_protocolo:
            acao.numero_protocolo = numero_protocolo
            print(f'[ATTSTATUS] Número de protocolo atualizado para: {numero_protocolo}')
            
        # Se o status for INCOMPLETO, atualiza o motivo da incompletude
        if novo_status == 'INCOMPLETO' and motivo_incompleto:
            acao.motivo_incompleto = motivo_incompleto
            print(f'[ATTSTATUS] Motivo da incompletude registrado')
            
        acao.save()
        print(f'[ATTSTATUS] Alterações salvas com sucesso')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Status atualizado com sucesso'
        })

    except Exception as e:
        print(f'[ATTSTATUS] Erro não tratado: {str(e)}')
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao atualizar status: {str(e)}'
        }, status=500)
    finally:
        print('[ATTSTATUS] ===== FIM DA REQUISIÇÃO =====\n')


@csrf_exempt
@require_http_methods(["POST"])
def api_post_inativaracao(request):
    """
    API para inativar uma ação INSS.
    """
    try:
        print('[INATIVAR] POST recebido:', request.POST.dict())
        
        # Obtém os dados do POST
        acao_id = request.POST.get('acao_id')
        motivo = request.POST.get('motivo', '')

        # Validação básica
        if not acao_id:
            return JsonResponse({
                'status': 'error',
                'message': 'ID da ação é obrigatório'
            }, status=400)

        # Busca a ação
        try:
            acao = Acoes.objects.get(id=acao_id)
        except Acoes.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Ação não encontrada'
            }, status=404)

        # Verifica se a ação já está inativa
        if not acao.status:
            return JsonResponse({
                'status': 'error',
                'message': 'Ação já está inativa'
            }, status=400)

        # Atualiza o status e o motivo da inativação
        acao.status = False
        acao.motivo_inatividade = motivo
        acao.save()

        print(f'[INATIVAR] Ação {acao_id} inativada. Motivo: {motivo}')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Ação inativada com sucesso'
        })

    except Exception as e:
        print(f'[INATIVAR] Erro ao inativar ação: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao inativar ação: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def api_post_reativaracao(request):
    """
    API para reativar uma ação INSS.
    """
    try:
        acao_id = request.POST.get('acao_id')
        if not acao_id:
            return JsonResponse({
                'status': 'error',
                'message': 'ID da ação não fornecido'
            }, status=400)

        try:
            acao = Acoes.objects.get(id=acao_id)
        except Acoes.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Ação não encontrada'
            }, status=404)

        if acao.status:
            return JsonResponse({
                'status': 'error',
                'message': 'Ação já está ativa'
            }, status=400)

        # Reativa a ação
        acao.status = True
        acao.motivo_inatividade = None
        acao.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Ação reativada com sucesso'
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao reativar ação: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_post_editaracao(request):
    """
    API para editar uma ação existente.
    """
    print('[EDITACAO] Iniciando edição de ação')
    try:
        print('[EDITACAO] POST recebido:', request.POST.dict())
        print('[EDITACAO] FILES recebidos:', request.FILES)
        
        # Obtém os dados do POST
        acao_id = request.POST.get('acao_id')
        cpf_cliente = request.POST.get('cpf_cliente')
        tipo_acao = request.POST.get('tipo_acao')
        status_emcaminhamento = request.POST.get('status_emcaminhamento')
        sentenca = request.POST.get('sentenca')
        senha_inss = request.POST.get('senha_inss')
        loja_id = request.POST.get('loja_id')
        
        # Campos da sentença
        grau_sentenca = request.POST.get('grau_sentenca')
        valor_sentenca = request.POST.get('valor_sentenca')
        data_sentenca = request.POST.get('data_sentenca')
        
        # Campos de recurso
        recurso_primeiro_grau = request.POST.get('recurso_primeiro_grau')
        data_recurso_primeiro_grau = request.POST.get('data_recurso_primeiro_grau')
        recurso_segundo_grau = request.POST.get('recurso_segundo_grau')
        data_recurso_segundo_grau = request.POST.get('data_recurso_segundo_grau')

        print('[EDITACAO] Dados recebidos:', {
            'acao_id': acao_id,
            'cpf_cliente': cpf_cliente,
            'tipo_acao': tipo_acao,
            'status_emcaminhamento': status_emcaminhamento,
            'sentenca': sentenca,
            'senha_inss': senha_inss,
            'loja_id': loja_id,
            'grau_sentenca': grau_sentenca,
            'valor_sentenca': valor_sentenca,
            'data_sentenca': data_sentenca,
            'recurso_primeiro_grau': recurso_primeiro_grau,
            'data_recurso_primeiro_grau': data_recurso_primeiro_grau,
            'recurso_segundo_grau': recurso_segundo_grau,
            'data_recurso_segundo_grau': data_recurso_segundo_grau
        })

        # Validação básica
        if not acao_id:
            print('[EDITACAO] Erro: ID da ação não fornecido')
            return JsonResponse({
                'status': 'error',
                'message': 'ID da ação é obrigatório'
            }, status=400)

        # Busca a ação
        try:
            acao = Acoes.objects.get(id=acao_id)
            print(f'[EDITACAO] Ação encontrada: {acao}')
        except Acoes.DoesNotExist:
            print(f'[EDITACAO] Erro: Ação {acao_id} não encontrada')
            return JsonResponse({
                'status': 'error',
                'message': 'Ação não encontrada'
            }, status=404)

        campos_atualizados = []
        
        # Atualiza os campos básicos
        if cpf_cliente:
            cliente_acao, created = ClienteAcao.objects.get_or_create(
                cpf=cpf_cliente,
                defaults={
                    'nome': acao.cliente.nome,
                    'contato': acao.cliente.contato
                }
            )
            acao.cliente = cliente_acao
            campos_atualizados.append('cpf_cliente')
            print(f'[EDITACAO] CPF atualizado para: {acao.cliente.cpf}')
        
        if tipo_acao:
            acao.tipo_acao = tipo_acao
            campos_atualizados.append('tipo_acao')
            print(f'[EDITACAO] Tipo de ação atualizado para: {acao.tipo_acao}')
        
        if status_emcaminhamento:
            acao.status_emcaminhamento = status_emcaminhamento
            campos_atualizados.append('status_emcaminhamento')
            print(f'[EDITACAO] Status atualizado para: {acao.status_emcaminhamento}')
        
        if sentenca:
            acao.sentenca = sentenca
            campos_atualizados.append('sentenca')
            print(f'[EDITACAO] Sentença atualizada para: {acao.sentenca}')
        
        if senha_inss:
            acao.senha_inss = senha_inss
            campos_atualizados.append('senha_inss')
            print(f'[EDITACAO] Senha INSS atualizada')
            
        # Atualiza a loja se fornecida
        if loja_id:
            try:
                loja = Loja.objects.get(id=loja_id)
                acao.loja = loja
                campos_atualizados.append('loja')
                print(f'[EDITACAO] Loja atualizada para: {loja.nome}')
            except Loja.DoesNotExist:
                print(f'[EDITACAO] Erro: Loja {loja_id} não encontrada')
                # Não retornamos erro para não interromper a edição dos outros campos
            
        # Atualiza os campos da sentença
        if grau_sentenca:
            acao.grau_sentenca = grau_sentenca
            campos_atualizados.append('grau_sentenca')
            print(f'[EDITACAO] Grau da sentença atualizado para: {acao.grau_sentenca}')
            
        if valor_sentenca:
            try:
                # Remove formatação e converte para decimal
                valor_limpo = valor_sentenca.replace('.', '').replace(',', '.')
                acao.valor_sentenca = Decimal(valor_limpo)
                campos_atualizados.append('valor_sentenca')
                print(f'[EDITACAO] Valor da sentença atualizado para: {acao.valor_sentenca}')
            except (InvalidOperation, ValueError) as e:
                print(f'[EDITACAO] Erro ao processar valor da sentença: {str(e)}')
                
        if data_sentenca:
            acao.data_sentenca = data_sentenca
            campos_atualizados.append('data_sentenca')
            print(f'[EDITACAO] Data da sentença atualizada para: {acao.data_sentenca}')
            
        # Atualiza os campos de recurso
        if recurso_primeiro_grau:
            acao.recurso_primeiro_grau = recurso_primeiro_grau
            campos_atualizados.append('recurso_primeiro_grau')
            print(f'[EDITACAO] Recurso 1º grau atualizado para: {acao.recurso_primeiro_grau}')
            
        if data_recurso_primeiro_grau:
            acao.data_recurso_primeiro_grau = data_recurso_primeiro_grau
            campos_atualizados.append('data_recurso_primeiro_grau')
            print(f'[EDITACAO] Data do recurso 1º grau atualizada para: {acao.data_recurso_primeiro_grau}')
            
        if recurso_segundo_grau:
            acao.recurso_segundo_grau = recurso_segundo_grau
            campos_atualizados.append('recurso_segundo_grau')
            print(f'[EDITACAO] Recurso 2º grau atualizado para: {acao.recurso_segundo_grau}')
            
        if data_recurso_segundo_grau:
            acao.data_recurso_segundo_grau = data_recurso_segundo_grau
            campos_atualizados.append('data_recurso_segundo_grau')
            print(f'[EDITACAO] Data do recurso 2º grau atualizada para: {acao.data_recurso_segundo_grau}')

        print('[EDITACAO] Campos atualizados:', campos_atualizados)

        # Salva as alterações
        acao.save()
        print('[EDITACAO] Alterações salvas com sucesso')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Ação atualizada com sucesso'
        })

    except Exception as e:
        print(f'[EDITACAO] Erro ao editar ação: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao editar ação: {str(e)}'
        }, status=500)


@csrf_exempt
@require_POST
def api_upload_documento_acao(request):
    """
    API para adicionar um novo documento à ação (DocsAcaoINSS).
    """
    try:
        acao_id = request.POST.get('acao_id')
        titulo = request.POST.get('titulo')
        file = request.FILES.get('file')

        if not acao_id or not file or not titulo:
            return JsonResponse({'status': 'error', 'message': 'Dados obrigatórios não enviados.'}, status=400)

        try:
            acao = Acoes.objects.get(id=acao_id)
        except Acoes.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Ação não encontrada.'}, status=404)

        doc = DocsAcaoINSS.objects.create(
            acao_inss=acao,
            titulo=titulo,
            file=file
        )

        return JsonResponse({'status': 'success', 'message': 'Documento adicionado com sucesso!', 'doc_id': doc.id})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Erro ao adicionar documento: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def api_get_pagamentosacoes(request):
    """
    API para obter dados dos registros de pagamento para popular a tabela de pagamentos.
    Calcula o valor restante para cada pagamento considerando os pagamentos já feitos.
    """
    print('[api_get_pagamentosacoes] Iniciando busca de registros de pagamento')
    try:
        # Filtra pagamentos que não estão cancelados e seleciona campos relacionados para otimizar a consulta
        pagamentos = RegistroPagamentos.objects.exclude(status=RegistroPagamentos.StatusPagamentoChoices.CANCELADO)\
                                           .select_related(
                                               'acao_inss',
                                               'acao_inss__cliente',
                                               'acao_inss__vendedor_responsavel',
                                               'acao_inss__loja'
                                           ).prefetch_related('pagamentos_feitos')\
                                           .order_by('-data_criacao')

        lista_pagamentos_data = []
        for rp in pagamentos:
            print(f'\n[api_get_pagamentosacoes] Processando pagamento ID: {rp.id}')
            acao = rp.acao_inss
            nome_cliente = "Não informado"
            cpf_cliente = "Não informado"
            contato_cliente = "Não informado"
            tipo_acao_display = acao.get_tipo_acao_display()
            responsavel_nome = acao.vendedor_responsavel.get_full_name() if acao.vendedor_responsavel else "Não informado"
            loja_nome = acao.loja.nome if acao.loja else "Não informado"

            if acao.cliente:
                nome_cliente = acao.cliente.nome if acao.cliente.nome else "Não informado"
                cpf_cliente = acao.cliente.cpf if acao.cliente.cpf else "Não informado"
                contato_cliente = acao.cliente.contato if acao.cliente.contato else "Não informado"
            
            # Fallback para nome_cliente se não estiver em acao.cliente e presenca_loja existir
            if nome_cliente == "Não informado" and acao.presenca_loja:
                presenca = acao.presenca_loja
                if presenca.agendamento and presenca.agendamento.cliente_agendamento:
                    cliente_ref = presenca.agendamento.cliente_agendamento
                    nome_cliente = cliente_ref.nome_completo
                elif presenca.cliente_agendamento:
                    cliente_ref = presenca.cliente_agendamento
                    nome_cliente = cliente_ref.nome_completo

            # Cálculo do valor total e restante
            valor_total = rp.valor_total if rp.valor_total is not None else Decimal('0.00')
            valor_entrada = rp.valor_entrada if rp.valor_entrada is not None else Decimal('0.00')
            
            # Soma todos os pagamentos já feitos
            valor_pago = Decimal('0.00')
            for pagamento_feito in rp.pagamentos_feitos.all():
                if pagamento_feito.valor_pago is not None:
                    valor_pago += pagamento_feito.valor_pago
            
            print(f'[api_get_pagamentosacoes] Valores para pagamento {rp.id}:')
            print(f'Valor total: {valor_total}')
            print(f'Valor entrada: {valor_entrada}')
            print(f'Valor pago: {valor_pago}')

            # Calcula o valor restante
            valor_restante = valor_total - valor_entrada - valor_pago

            # Garante que o valor restante não seja negativo
            if valor_restante < Decimal('0.00'):
                valor_restante = Decimal('0.00')
            
            print(f'Valor restante calculado: {valor_restante}')
            
            lista_pagamentos_data.append({
                'id_pagamento': rp.id,
                'id_acao': acao.id,
                'nome_cliente': nome_cliente,
                'cpf_cliente': cpf_cliente,
                'contato_cliente': contato_cliente,
                'tipo_acao': tipo_acao_display,
                'tipo_pagamento': rp.get_tipo_pagamento_display(),
                'valor_total': str(valor_total.quantize(Decimal('0.01'))),
                'valor_restante': str(valor_restante.quantize(Decimal('0.01'))),
                'status_pagamento': rp.get_status_display(),
                'responsavel_nome': responsavel_nome,
                'loja_nome': loja_nome
            })
        
        print(f'\n[api_get_pagamentosacoes] {len(lista_pagamentos_data)} registros de pagamento encontrados')
        return JsonResponse({'status': 'success', 'pagamentos': lista_pagamentos_data})

    except Exception as e:
        print(f'[api_get_pagamentosacoes] Erro ao buscar registros de pagamento: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def api_get_lista_acoes(request):
    """
    API para obter dados das ações em aberto (sem advogado responsável).
    Exclui ações do tipo LIMPANOME.
    """
    print('[GET_LISTA_ACOES] Iniciando busca de ações')
    try:
        # Busca todas as ações ativas, excluindo as do tipo LIMPANOME
        acoes = Acoes.objects.select_related('cliente', 'loja').filter(
            status=True
        ).exclude(
            tipo_acao=Acoes.TipoAcaoChoices.LIMPA_NOME.value  # Exclui ações do tipo LIMPANOME usando o valor da constante
        ).order_by('-data_criacao')
        print(f'[GET_LISTA_ACOES] {acoes.count()} ações encontradas (excluindo LIMPANOME)')
        
        acoes_list = []
        for acao in acoes:
            try:
                cliente_nome = acao.cliente.nome if acao.cliente and acao.cliente.nome else 'N/A'
                cliente_cpf = acao.cliente.cpf if acao.cliente and acao.cliente.cpf else 'N/A'

                acao_data = {
                    'id': acao.id,
                    'cliente_nome': cliente_nome,
                    'cliente_cpf': cliente_cpf,
                    'tipo_acao': acao.get_tipo_acao_display(),
                    'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
                    'status': acao.get_status_emcaminhamento_display(),
                    'sentenca': acao.get_sentenca_display() if acao.sentenca else 'N/A',
                    'loja': acao.loja.nome if acao.loja else 'N/A',
                    'ativo': acao.status
                }
                acoes_list.append(acao_data)
                print(f'[GET_LISTA_ACOES] Ação {acao.id} processada')

            except Exception as e:
                print(f'[GET_LISTA_ACOES] Erro ao processar ação {acao.id}:', str(e))
                continue

        print('[GET_LISTA_ACOES] Lista de ações preparada com sucesso')
        return JsonResponse({
            'status': 'success',
            'data': acoes_list
        })

    except Exception as e:
        print(f'[GET_LISTA_ACOES] Erro ao buscar ações: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar ações: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_minhas_acoes(request):
    """
    API para obter dados das ações do advogado logado.
    Suporta filtros por nome, CPF e status.
    """
    try:
        print('[GET_MINHAS_ACOES] Iniciando busca de ações do advogado')
        query = Acoes.objects.select_related(
            'cliente',
            'vendedor_responsavel',
            'advogado_responsavel',
            'loja'
        ).filter(
            advogado_responsavel=request.user,
            status=True
        )
        print('[GET_MINHAS_ACOES] Total de ações iniciais:', query.count())

        # Obtém os parâmetros de filtro da requisição GET
        nome = request.GET.get('nome', '').strip()
        cpf = request.GET.get('cpf', '').strip()
        status = request.GET.get('status', '').strip()

        # Aplica filtros se fornecidos
        if nome:
            query = query.filter(cliente__nome__icontains=nome)
        
        if cpf:
            cpf_limpo = re.sub(r'\D', '', cpf)
            query = query.filter(cliente__cpf__icontains=cpf_limpo)
        
        if status:
            query = query.filter(status_emcaminhamento=status)

        # Ordena por data de criação (mais recente primeiro)
        query = query.order_by('-data_criacao')

        # Prepara os dados para retorno
        acoes_list = []
        for acao in query:
            cliente_nome = acao.cliente.nome if acao.cliente and acao.cliente.nome else 'N/A'
            cliente_cpf = acao.cliente.cpf if acao.cliente and acao.cliente.cpf else 'N/A'

            acao_data = {
                'id': acao.id,
                'cliente_nome': cliente_nome,
                'cliente_cpf': cliente_cpf,
                'tipo_acao': acao.get_tipo_acao_display(),
                'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'status': acao.get_status_emcaminhamento_display(),
                'sentenca': acao.get_sentenca_display() if acao.sentenca else 'N/A',
                'loja': acao.loja.nome if acao.loja else 'N/A',
                'ativo': acao.status
            }
            acoes_list.append(acao_data)

        return JsonResponse({
            'status': 'success',
            'data': acoes_list
        })

    except Exception as e:
        print(f'[GET_MINHAS_ACOES] Erro ao buscar ações: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar ações: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_acoes_com_advogado(request):
    """
    API para obter dados das ações com advogado responsável (para gestor).
    Suporta filtros por nome, CPF, status e advogado.
    """
    try:
        print('[GET_ACOES_COM_ADVOGADO] Iniciando busca de ações com advogado')
        query = Acoes.objects.select_related(
            'cliente',
            'vendedor_responsavel',
            'advogado_responsavel',
            'loja'
        ).filter(
            advogado_responsavel__isnull=False,
            status=True
        )
        print('[GET_ACOES_COM_ADVOGADO] Total de ações iniciais:', query.count())

        # Obtém os parâmetros de filtro da requisição GET
        nome = request.GET.get('nome', '').strip()
        cpf = request.GET.get('cpf', '').strip()
        status = request.GET.get('status', '').strip()
        advogado = request.GET.get('advogado', '').strip()

        # Aplica filtros se fornecidos
        if nome:
            query = query.filter(cliente__nome__icontains=nome)
        
        if cpf:
            cpf_limpo = re.sub(r'\D', '', cpf)
            query = query.filter(cliente__cpf__icontains=cpf_limpo)
        
        if status:
            query = query.filter(status_emcaminhamento=status)
            
        if advogado:
            query = query.filter(advogado_responsavel__username__icontains=advogado)

        # Ordena por data de criação (mais recente primeiro)
        query = query.order_by('-data_criacao')

        # Prepara os dados para retorno
        acoes_list = []
        for acao in query:
            cliente_nome = acao.cliente.nome if acao.cliente and acao.cliente.nome else 'N/A'
            cliente_cpf = acao.cliente.cpf if acao.cliente and acao.cliente.cpf else 'N/A'

            acao_data = {
                'id': acao.id,
                'cliente_nome': cliente_nome,
                'cliente_cpf': cliente_cpf,
                'tipo_acao': acao.get_tipo_acao_display(),
                'data_criacao': acao.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'status': acao.get_status_emcaminhamento_display(),
                'sentenca': acao.get_sentenca_display() if acao.sentenca else 'N/A',
                'loja': acao.loja.nome if acao.loja else 'N/A',
                'ativo': acao.status,
                'advogado': acao.advogado_responsavel.get_full_name() if acao.advogado_responsavel else 'N/A'
            }
            acoes_list.append(acao_data)

        return JsonResponse({
            'status': 'success',
            'data': acoes_list
        })

    except Exception as e:
        print(f'[GET_ACOES_COM_ADVOGADO] Erro ao buscar ações: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar ações: {str(e)}'
        }, status=500)


@require_POST
@login_required
@csrf_exempt
def api_post_assumir_acao(request):
    acao_id = request.POST.get('acao_id')
    if not acao_id:
        return JsonResponse({'status': 'error', 'message': 'ID da ação não informado.'}, status=400)
    try:
        acao = Acoes.objects.get(id=acao_id)
        if acao.advogado_responsavel is not None:
            return JsonResponse({'status': 'error', 'message': 'Ação já possui advogado responsável.'}, status=400)
        acao.advogado_responsavel = request.user
        acao.save()
        return JsonResponse({'status': 'success', 'message': 'Ação assumida com sucesso!'})
    except Acoes.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Ação não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required(login_url='/')
@controle_acess('SCT61')
def render_limpa_nome(request):
    """
    View para renderizar a página de listagem de ações Limpa Nome.
    """
    print('[render_limpa_nome] Renderizando página de Limpa Nome')
    return render(request, 'apps/juridico/limpa_nome.html')


@login_required(login_url='/')
@controle_acess('SCT62')
def render_pagamentos(request):
    """
    View para renderizar a tela de pagamentos do INSS.
    Requer permissão SCT58 (mesma da tela de ações).
    """
    return render(request, 'apps/juridico/pagamentos.html')


@login_required
@csrf_exempt
def api_post_registrar_pagamento(request):
    try:
        data = json.loads(request.body)
        print('[api_post_registrar_pagamento] Dados recebidos:', data)
        
        # Validação dos campos obrigatórios
        if not all(key in data for key in ['pagamento_id', 'valor_pago', 'data_pagamento']):
            return JsonResponse({
                'status': 'error',
                'message': 'Campos obrigatórios não preenchidos'
            }, status=400)

        # Busca o registro de pagamento
        try:
            registro_pagamento = RegistroPagamentos.objects.get(id=data['pagamento_id'])
            print(f'[api_post_registrar_pagamento] Registro encontrado: {registro_pagamento.id}')
        except RegistroPagamentos.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Registro de pagamento não encontrado'
            }, status=404)

        # Processa o valor pago
        try:
            # Se o valor já vier com ponto decimal, não precisa fazer replace
            valor_str = data['valor_pago']
            if ',' in valor_str:
                # Se tiver vírgula, converte para o formato com ponto
                valor_str = valor_str.replace('.', '').replace(',', '.')
            print(f'[api_post_registrar_pagamento] Valor string processado: {valor_str}')
            valor_pago = Decimal(valor_str)
            print(f'[api_post_registrar_pagamento] Valor pago processado: {valor_pago}')
        except (ValueError, AttributeError) as e:
            print(f'[api_post_registrar_pagamento] Erro ao processar valor: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': 'Valor do pagamento inválido'
            }, status=400)

        # Processa a data do pagamento
        try:
            data_pagamento = datetime.strptime(data['data_pagamento'], '%Y-%m-%d')
            print(f'[api_post_registrar_pagamento] Data processada: {data_pagamento}')
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Data do pagamento inválida'
            }, status=400)

        # Processa o número da parcela (opcional)
        parcela_paga = data.get('parcela_paga')
        if parcela_paga:
            try:
                parcela_paga = int(parcela_paga)
                print(f'[api_post_registrar_pagamento] Parcela processada: {parcela_paga}')
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Número da parcela inválido'
                }, status=400)

        # Processa os campos de atraso
        flg_atrasado = data.get('flg_atrasado', False)
        juros_atrasado = Decimal('0.00')
        if flg_atrasado:
            try:
                juros_str = data.get('juros_atrasado', '0').replace(',', '.')
                print(f'[api_post_registrar_pagamento] Juros string processado: {juros_str}')
                juros_atrasado = Decimal(juros_str)
                print(f'[api_post_registrar_pagamento] Juros processados: {juros_atrasado}')
            except (ValueError, AttributeError) as e:
                print(f'[api_post_registrar_pagamento] Erro ao processar juros: {str(e)}')
                return JsonResponse({
                    'status': 'error',
                    'message': 'Valor dos juros inválido'
                }, status=400)

        # Processa os campos de acordo
        flg_acordo = data.get('flg_acordo', False)
        tipo_acordo = 'NENHUM'
        if flg_acordo:
            tipo_acordo = data.get('tipo_acordo', 'NENHUM')
            if tipo_acordo not in ['NENHUM', 'DESCONTO', 'PARCELAMENTO', 'QUITACAO']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Tipo de acordo inválido'
                }, status=400)
            print(f'[api_post_registrar_pagamento] Tipo de acordo: {tipo_acordo}')

        # Cria o registro do pagamento
        pagamento = RegistroPagamentosFeitos.objects.create(
            registro_pagamento=registro_pagamento,
            valor_pago=valor_pago,
            data_pagamento=data_pagamento,
            parcela_paga=parcela_paga,
            flg_atrasado=flg_atrasado,
            flg_acordo=flg_acordo,
            tipo_acordo=tipo_acordo,
            juros_atrasado_mensal=juros_atrasado,
            observacao=data.get('observacao', '')
        )
        print(f'[api_post_registrar_pagamento] Pagamento registrado: {pagamento.id}')

        # Atualiza o status do registro de pagamento
        valor_total_pago = RegistroPagamentosFeitos.objects.filter(
            registro_pagamento=registro_pagamento
        ).aggregate(total=Sum('valor_pago'))['total'] or Decimal('0.00')
        
        print(f'[api_post_registrar_pagamento] Valor total pago: {valor_total_pago}')
        print(f'[api_post_registrar_pagamento] Valor total do registro: {registro_pagamento.valor_total}')

        # Atualiza o status baseado no tipo de pagamento
        if registro_pagamento.tipo_pagamento in ['PARCELADO', 'ENTRADA_PARCELAS']:
            # Para pagamentos parcelados, verifica se todas as parcelas foram pagas
            parcelas_pagas = RegistroPagamentosFeitos.objects.filter(
                registro_pagamento=registro_pagamento,
                parcela_paga__isnull=False
            ).count()
            
            print(f'[api_post_registrar_pagamento] Parcelas pagas: {parcelas_pagas}')
            print(f'[api_post_registrar_pagamento] Total de parcelas: {registro_pagamento.parcelas_totais}')
            
            if parcelas_pagas >= registro_pagamento.parcelas_totais:
                registro_pagamento.status = RegistroPagamentos.StatusPagamentoChoices.QUITADO
                print(f'[api_post_registrar_pagamento] Status atualizado para QUITADO (todas parcelas pagas)')
            else:
                registro_pagamento.status = RegistroPagamentos.StatusPagamentoChoices.EM_ANDAMENTO
                print(f'[api_post_registrar_pagamento] Status mantido como EM_ANDAMENTO (parcelas pendentes)')
        else:
            # Para pagamentos à vista, verifica se o valor total foi pago
            if valor_total_pago >= registro_pagamento.valor_total:
                registro_pagamento.status = RegistroPagamentos.StatusPagamentoChoices.QUITADO
                print(f'[api_post_registrar_pagamento] Status atualizado para QUITADO (valor total pago)')
            else:
                registro_pagamento.status = RegistroPagamentos.StatusPagamentoChoices.EM_ANDAMENTO
                print(f'[api_post_registrar_pagamento] Status mantido como EM_ANDAMENTO (valor pendente)')

        registro_pagamento.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Pagamento registrado com sucesso',
            'data': {
                'id': pagamento.id,
                'valor_pago': str(pagamento.valor_pago),
                'data_pagamento': pagamento.data_pagamento.strftime('%Y-%m-%d'),
                'status': registro_pagamento.status
            }
        })

    except json.JSONDecodeError:
        print('[api_post_registrar_pagamento] Erro ao decodificar JSON')
        return JsonResponse({
            'status': 'error',
            'message': 'Erro ao processar os dados do formulário'
        }, status=400)
    except Exception as e:
        print(f'[api_post_registrar_pagamento] Erro: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao registrar pagamento: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_get_detalhes_pagamento(request, registro_pagamento_id):
    """
    API para obter detalhes de um registro de pagamento específico.
    Retorna informações do registro, pagamentos feitos e parcelas disponíveis.
    """
    print(f'[api_get_detalhes_pagamento] Buscando detalhes do registro {registro_pagamento_id}')
    try:
        # Busca o registro de pagamento
        try:
            registro = RegistroPagamentos.objects.select_related(
                'acao_inss',
                'acao_inss__cliente',
                'acao_inss__vendedor_responsavel',
                'acao_inss__loja'
            ).get(id=registro_pagamento_id)
        except RegistroPagamentos.DoesNotExist:
            print(f'[api_get_detalhes_pagamento] Registro {registro_pagamento_id} não encontrado')
            return JsonResponse({
                'status': 'error',
                'message': 'Registro de pagamento não encontrado'
            }, status=404)

        # Busca os pagamentos feitos para este registro
        pagamentos_feitos = RegistroPagamentosFeitos.objects.filter(
            registro_pagamento=registro
        ).order_by('data_pagamento')

        # Lista de parcelas já pagas
        parcelas_pagas = [p.parcela_paga for p in pagamentos_feitos if p.parcela_paga is not None]
        
        # Prepara a lista de parcelas disponíveis
        parcelas_disponiveis = []
        if registro.tipo_pagamento in ['PARCELADO', 'ENTRADA_PARCELAS']:
            total_parcelas = registro.parcelas_totais
            parcelas_disponiveis = [
                {'value': i, 'label': f'Parcela {i}'}
                for i in range(1, total_parcelas + 1)
                if i not in parcelas_pagas
            ]

        # Prepara os dados dos pagamentos feitos
        pagamentos_data = []
        for pagamento in pagamentos_feitos:
            pagamentos_data.append({
                'id': pagamento.id,
                'valor_pago': str(pagamento.valor_pago),
                'data_pagamento': pagamento.data_pagamento.strftime('%d/%m/%Y'),
                'parcela_paga': pagamento.parcela_paga,
                'flg_atrasado': pagamento.flg_atrasado,
                'flg_acordo': pagamento.flg_acordo,
                'tipo_acordo': pagamento.tipo_acordo,
                'juros_atrasado': str(pagamento.juros_atrasado_mensal),
                'observacao': pagamento.observacao
            })

        # Obtém o contato do cliente
        contato_cliente = "Não informado"
        if registro.acao_inss.cliente and registro.acao_inss.cliente.contato:
            contato_cliente = registro.acao_inss.cliente.contato

        # Obtém o nome do responsável
        responsavel_nome = "Não informado"
        if registro.acao_inss.vendedor_responsavel:
            try:
                # Tenta obter o nome completo do funcionário associado
                funcionario = Funcionario.objects.get(usuario=registro.acao_inss.vendedor_responsavel)
                responsavel_nome = funcionario.nome_completo
            except Funcionario.DoesNotExist:
                # Se não encontrar o funcionário, usa o username do usuário
                responsavel_nome = registro.acao_inss.vendedor_responsavel.username

        # Obtém o nome da loja
        loja_nome = "Não informado"
        if registro.acao_inss.loja:
            loja_nome = registro.acao_inss.loja.nome

        # Prepara os dados do registro
        dados_registro = {
            'id_registro': registro.id,
            'id_acao': registro.acao_inss.id,
            'tipo_pagamento': registro.tipo_pagamento,
            'valor_total': str(registro.valor_total),
            'valor_entrada': str(registro.valor_entrada),
            'parcelas_totais': registro.parcelas_totais,
            'parcelas_pagas': registro.parcelas_pagas,
            'parcelas_restantes': registro.parcelas_restantes,
            'status': registro.status,
            'parcelas_disponiveis': parcelas_disponiveis,
            'pagamentos_feitos': pagamentos_data,
            'responsavel_nome': responsavel_nome,
            'contato_cliente': contato_cliente,
            'loja_nome': loja_nome
        }

        print(f'[api_get_detalhes_pagamento] Dados encontrados para registro {registro_pagamento_id}')
        return JsonResponse({
            'status': 'success',
            'data': dados_registro
        })

    except Exception as e:
        print(f'[api_get_detalhes_pagamento] Erro ao buscar detalhes do registro {registro_pagamento_id}: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao buscar detalhes do registro: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_post_atualizar_sentenca(request):
    """
    API para atualizar a sentença de uma ação.
    Aceita tanto envio simplificado (apenas ID e tipo de sentença) quanto completo (todos os campos).
    """
    print('[ATUALIZAR_SENTENCA] Iniciando atualização de sentença')
    try:
        print('[ATUALIZAR_SENTENCA] POST recebido:', request.POST.dict())
        
        # Obtém os dados do POST
        acao_id = request.POST.get('acao_id')
        sentenca = request.POST.get('sentenca')

        print('[ATUALIZAR_SENTENCA] Dados recebidos:', {
            'acao_id': acao_id,
            'sentenca': sentenca
        })

        # Validação básica - apenas ID e tipo de sentença são obrigatórios
        if not acao_id or not sentenca:
            print('[ATUALIZAR_SENTENCA] Erro: Campos obrigatórios faltando')
            return JsonResponse({
                'status': 'error',
                'message': 'ID da ação e tipo de sentença são obrigatórios'
            }, status=400)

        # Busca a ação
        try:
            acao = Acoes.objects.get(id=acao_id)
            print(f'[ATUALIZAR_SENTENCA] Ação encontrada: {acao}')
        except Acoes.DoesNotExist:
            print(f'[ATUALIZAR_SENTENCA] Erro: Ação {acao_id} não encontrada')
            return JsonResponse({
                'status': 'error',
                'message': 'Ação não encontrada'
            }, status=404)

        # Atualiza o tipo de sentença
        acao.sentenca = sentenca
        
        # Se for sentença não favorável ou pendente, limpa os outros campos
        if sentenca in ['NAO_FAVORAVEL', 'PENDENTE']:
            acao.grau_sentenca = None
            acao.valor_sentenca = None
            acao.data_sentenca = None
            acao.recurso_primeiro_grau = 'NENHUM'
            acao.data_recurso_primeiro_grau = None
            acao.resultado_recurso_primeiro_grau = None
            acao.recurso_segundo_grau = 'NENHUM'
            acao.data_recurso_segundo_grau = None
            acao.resultado_recurso_segundo_grau = None
        else:
            # Se for favorável, atualiza os outros campos se fornecidos
            grau_sentenca = request.POST.get('grau_sentenca')
            valor_sentenca = request.POST.get('valor_sentenca')
            data_sentenca = request.POST.get('data_sentenca')
            recurso_primeiro_grau = request.POST.get('recurso_primeiro_grau')
            data_recurso_primeiro_grau_str = request.POST.get('data_recurso_primeiro_grau')
            resultado_recurso_primeiro_grau = request.POST.get('resultado_recurso_primeiro_grau')
            recurso_segundo_grau = request.POST.get('recurso_segundo_grau')
            data_recurso_segundo_grau_str = request.POST.get('data_recurso_segundo_grau')
            resultado_recurso_segundo_grau = request.POST.get('resultado_recurso_segundo_grau')

            # Atualiza apenas os campos que foram fornecidos
            if grau_sentenca:
                acao.grau_sentenca = grau_sentenca
            if valor_sentenca:
                try:
                    valor_limpo = valor_sentenca.replace('.', '').replace(',', '.')
                    acao.valor_sentenca = Decimal(valor_limpo)
                except (InvalidOperation, ValueError) as e:
                    print(f'[ATUALIZAR_SENTENCA] Erro ao processar valor da sentença: {str(e)}')
            if data_sentenca:
                acao.data_sentenca = data_sentenca
            if recurso_primeiro_grau:
                acao.recurso_primeiro_grau = recurso_primeiro_grau
            
            if data_recurso_primeiro_grau_str is not None: # Verifica se a chave existe no POST
                acao.data_recurso_primeiro_grau = data_recurso_primeiro_grau_str if data_recurso_primeiro_grau_str else None
            
            if resultado_recurso_primeiro_grau:
                acao.resultado_recurso_primeiro_grau = resultado_recurso_primeiro_grau
            if recurso_segundo_grau:
                acao.recurso_segundo_grau = recurso_segundo_grau
            
            if data_recurso_segundo_grau_str is not None: # Verifica se a chave existe no POST
                acao.data_recurso_segundo_grau = data_recurso_segundo_grau_str if data_recurso_segundo_grau_str else None
            
            if resultado_recurso_segundo_grau:
                acao.resultado_recurso_segundo_grau = resultado_recurso_segundo_grau

            # Se sentença for favorável e recurso_primeiro_grau for NENHUM, finaliza a ação
            # Também considerar se o resultado do recurso de 1o grau for FAVORAVEL e não houver recurso de 2o grau
            if acao.sentenca == 'FAVORAVEL':
                if acao.recurso_primeiro_grau == 'NENHUM':
                    acao.status_emcaminhamento = 'FINALIZADO'
                elif acao.resultado_recurso_primeiro_grau == 'FAVORAVEL' and acao.recurso_segundo_grau == 'NENHUM':
                    acao.status_emcaminhamento = 'FINALIZADO'
                # Adicionar lógica para resultado de 2o grau se necessário
                elif acao.resultado_recurso_segundo_grau == 'FAVORAVEL':
                     acao.status_emcaminhamento = 'FINALIZADO'

        # Salva as alterações
        acao.save()
        print('[ATUALIZAR_SENTENCA] Alterações salvas com sucesso')
        
        return JsonResponse({
            'status': 'success',
            'message': 'Sentença atualizada com sucesso'
        })

    except Exception as e:
        print(f'[ATUALIZAR_SENTENCA] Erro ao atualizar sentença: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao atualizar sentença: {str(e)}'
        }, status=500)

from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


@login_required(login_url='/')
@ensure_csrf_cookie
@controle_acess('SCT57')
def render_dashboardacoes(request):
    """
    Renderiza a página do dashboard de ações para advogados e gestores
    """
    context = {}
    return render(request, 'apps/juridico/dashboard_acoes.html', context)


@login_required(login_url='/')
@require_GET
def api_get_dashboardacoes(request):
    """
    API para obter dados do dashboard de ações jurídicas do usuário logado
    """
    print('[DASHBOARD_ACOES] ===== INÍCIO DA REQUISIÇÃO =====')
    
    try:
        usuario = request.user
        mostrar_todos_dados = False

        if usuario.is_superuser:
            mostrar_todos_dados = True
        else:
            try:
                # Tenta obter o perfil de funcionário do usuário
                # As importações são feitas aqui para evitar importação circular se não forem necessárias
                from apps.funcionarios.models import Funcionario, Cargo 
                funcionario_profile = Funcionario.objects.filter(usuario=usuario).first()
                if funcionario_profile and funcionario_profile.cargo:
                    # Verifica se o nível hierárquico do cargo é GESTOR (valor 7 conforme Cargo.HierarquiaChoices)
                    if funcionario_profile.cargo.hierarquia == Cargo.HierarquiaChoices.GESTOR:
                        mostrar_todos_dados = True
            except Funcionario.DoesNotExist:
                # Usuário não tem perfil de funcionário, não é gestor
                pass
            except Exception as e:
                # Logar outros possíveis erros ao acessar o perfil do funcionário
                print(f"[DASHBOARD_ACOES] Erro ao verificar perfil de gestor para {usuario.username}: {str(e)}")

        if mostrar_todos_dados:
            print(f"[DASHBOARD_ACOES] Usuário {usuario.username} (Superuser ou Gestor) - Mostrando todos os dados.")
            acoes_qs = Acoes.objects.all() # Queryset base para todos os dados
        else:
            print(f"[DASHBOARD_ACOES] Usuário {usuario.username} - Mostrando dados como advogado responsável.")
            acoes_qs = Acoes.objects.filter(advogado_responsavel=usuario) # Queryset base filtrado
        
        # Quantidade total de ações
        total_acoes = acoes_qs.count()
        
        # Sentenças
        sentencas_favoraveis = acoes_qs.filter(sentenca='FAVORAVEL').count()
        sentencas_nao_favoraveis = acoes_qs.filter(sentenca='NAO_FAVORAVEL').count()
        sentencas_pendentes = acoes_qs.filter(sentenca='PENDENTE').count()
        
        # Recursos
        # A lógica original para acoes_com_recursos estava contando apenas NENHUM em recurso_primeiro_grau
        # Para ser mais abrangente (qualquer recurso em qualquer grau), podemos fazer:
        acoes_com_recursos = acoes_qs.exclude(
            recurso_primeiro_grau=Acoes.RecursoChoices.NENHUM,
            recurso_segundo_grau=Acoes.RecursoChoices.NENHUM
        ).count()
        
        # Recursos de primeiro grau
        recursos_primeiro_grau = {
            'apelacao': acoes_qs.filter(recurso_primeiro_grau='APELACAO').count(),
            'agravo': acoes_qs.filter(recurso_primeiro_grau='AGRAVO').count(),
            'embargos': acoes_qs.filter(recurso_primeiro_grau='EMBARGOS').count(),
        }
        
        # Recursos de segundo grau
        recursos_segundo_grau = {
            'apelacao': acoes_qs.filter(recurso_segundo_grau='APELACAO').count(),
            'agravo': acoes_qs.filter(recurso_segundo_grau='AGRAVO').count(),
            'embargos': acoes_qs.filter(recurso_segundo_grau='EMBARGOS').count(),
        }
        
        # Status atual das ações
        status_acoes = {
            'em_espera': acoes_qs.filter(status_emcaminhamento='EM_ESPERA').count(),
            'incompleto': acoes_qs.filter(status_emcaminhamento='INCOMPLETO').count(),
            'em_despacho': acoes_qs.filter(status_emcaminhamento='EM_DESPACHO').count(),
            'protocolado': acoes_qs.filter(status_emcaminhamento='PROTOCOLADO').count(),
            'finalizado': acoes_qs.filter(status_emcaminhamento='FINALIZADO').count(),
        }
        
        # Tipos de ações
        tipos_acoes = {
            'associacao': acoes_qs.filter(tipo_acao='ASSOCIACAO').count(),
            'cartao': acoes_qs.filter(tipo_acao='CARTAO').count(),
            'debito_conta': acoes_qs.filter(tipo_acao='DEBITO_CONTA').count(),
            'limpa_nome': acoes_qs.filter(tipo_acao='LIMPANOME').count(),
            'revisional': acoes_qs.filter(tipo_acao='REVISIONAL').count(),
        }
        
        # Acões por mês nos últimos 6 meses
        from django.db.models import Count
        from django.db.models.functions import TruncMonth
        import datetime
        
        # Obter data atual e data 6 meses atrás
        data_atual = datetime.datetime.now()
        seis_meses_atras = data_atual - datetime.timedelta(days=180)
        
        # Agrupar ações por mês
        acoes_por_mes = acoes_qs.filter(
            data_criacao__gte=seis_meses_atras
        ).annotate(
            mes=TruncMonth('data_criacao')
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')
        
        # Formatar o resultado
        historico_acoes = [
            {
                'mes': item['mes'].strftime('%m/%Y'),
                'total': item['total']
            } for item in acoes_por_mes
        ]
        
        return JsonResponse({
            'success': True,
            'dados_dashboard': {
                'total_acoes': total_acoes,
                'sentencas': {
                    'favoraveis': sentencas_favoraveis,
                    'nao_favoraveis': sentencas_nao_favoraveis,
                    'pendentes': sentencas_pendentes
                },
                'recursos': {
                    'total_com_recursos': acoes_com_recursos,
                    'primeiro_grau': recursos_primeiro_grau,
                    'segundo_grau': recursos_segundo_grau
                },
                'status_acoes': status_acoes,
                'tipos_acoes': tipos_acoes,
                'historico_acoes': historico_acoes
            }
        })
        
    except Exception as e:
        import traceback
        print(f"[DASHBOARD_ACOES] Erro: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': f'Erro ao obter dados do dashboard: {str(e)}'
        }, status=500)
    finally:
        print('[DASHBOARD_ACOES] ===== FIM DA REQUISIÇÃO =====\n')
