# Python standard library imports
import csv
import io
import json
import logging
import os
import traceback
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Third-party imports (Django)
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models.fields.files import FileField, ImageField
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie, csrf_protect

from custom_tags_app.templatetags.permissionsacess import controle_acess
from django.views.decorators.http import require_GET, require_http_methods, require_POST

# Local application/library specific imports
from setup.utils import verificar_autenticacao
from .forms import *  # TODO: Considerar importações específicas em vez de '*'
from .models import *  # TODO: Considerar importações específicas em vez de '*'
from apps.siape.models import * # <<< ADICIONAR IMPORT
# Nota: O código original também importava especificamente Comissionamento, Empresa, Departamento, Setor, Equipe de .models.
# Usar 'from .models import *' cobre estes, mas importações específicas são geralmente preferidas para clareza.


# Configuração do logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# ----- Views de Renderização -----
from custom_tags_app.templatetags.permissionsacess import controle_acess


@login_required
@controle_acess('SCT15')   # 15 – RECURSOS HUMANOS | ADMINISTRATIVO
def render_administrativo(request):
    """Renderiza a página de cadastros administrativos."""
    logger.debug("Iniciando render_administrativo")
    return render(request, 'apps/funcionarios/forms/administrativo.html', {})

@login_required
@controle_acess('SCT13')   # 13 – RECURSOS HUMANOS | NOVO FUNCIONARIO
def render_novofuncionario(request):
    """Renderiza o formulário para criar um novo funcionário."""
    logger.debug("Iniciando render_novofuncionario")
    return render(request, 'apps/funcionarios/forms/novo_funcionario.html', {})

@login_required
@controle_acess('SCT14')   # 14 – RECURSOS HUMANOS | EDITAR FUNCIONARIO
@ensure_csrf_cookie
def render_editfuncionario(request):
    """Renderiza a página para editar funcionários."""
    logger.debug("Iniciando render_editfuncionario")
    return render(request, 'apps/funcionarios/forms/edit_funcionario.html', {})

@login_required
@controle_acess('SCT12')   # 12 – RECURSOS HUMANOS | DASHBOARD
def render_dashboard(request):
    """Renderiza a página do dashboard de funcionários."""
    logger.debug("Iniciando render_dashboard")
    return render(request, 'apps/funcionarios/forms/dashboard.html', {})



# ----- Views de API (JSON) -----

@require_GET
#@login_required # Ou seu decorador, APIs também devem ser protegidas
def api_get_infogeral(request):
    """Retorna informações gerais sobre entidades administrativas em JSON."""
    print("\n----- Iniciando api_get_infogeral -----")
    try:
        # Obtém os choices da hierarquia
        hierarquia_choices = [{'value': value, 'display': display} for value, display in Cargo.HierarquiaChoices.choices]

        # Obtém os cargos formatados
        cargos_formatados = []
        for cargo in Cargo.objects.filter(status=True).select_related('empresa'):
            cargos_formatados.append({
                'id': cargo.id,
                'nome': cargo.nome,
                'empresa_id': cargo.empresa_id,
                'empresa__nome': cargo.empresa.nome,
                'hierarquia': cargo.hierarquia,
                # Cria um campo combinado para exibição no select
                'nome_com_hierarquia': f"{cargo.nome} ({cargo.get_hierarquia_display()})"
            })

        # Obtém os horários formatados
        horarios_formatados = []
        for horario in HorarioTrabalho.objects.filter(status=True):
             horarios_formatados.append({
                 'id': horario.id,
                 'nome': horario.nome,
                 'entrada': horario.entrada.strftime('%H:%M') if horario.entrada else None,
                 'saida_almoco': horario.saida_almoco.strftime('%H:%M') if horario.saida_almoco else None,
                 'volta_almoco': horario.volta_almoco.strftime('%H:%M') if horario.volta_almoco else None,
                 'saida': horario.saida.strftime('%H:%M') if horario.saida else None,
                 # Adiciona texto pré-formatado para o select
                 'display_text': f"{horario.nome} ({horario.entrada.strftime('%H:%M') if horario.entrada else 'N/A'} - {horario.saida.strftime('%H:%M') if horario.saida else 'N/A'})"
             })


        data = {
            'empresas': list(Empresa.objects.filter(status=True).values('id', 'nome', 'cnpj', 'endereco')),
            'lojas': list(Loja.objects.filter(status=True).values('id', 'nome', 'empresa_id', 'empresa__nome', 'franquia', 'filial')),
            'departamentos': list(Departamento.objects.filter(status=True).values('id', 'nome', 'empresa_id', 'empresa__nome')),
            'setores': list(Setor.objects.filter(status=True).values('id', 'nome', 'departamento_id', 'departamento__nome')),
            # Usa a lista formatada de cargos
            'cargos': cargos_formatados,
            # Usa a lista formatada de horários
            'horarios': horarios_formatados,
            #'horarios': list(HorarioTrabalho.objects.filter(status=True).values('id', 'nome', 'entrada', 'saida_almoco', 'volta_almoco', 'saida')),
            'equipes': list(Equipe.objects.filter(status=True).values('id', 'nome')),
            'hierarquia_choices': hierarquia_choices, # Mantém para o form administrativo
        }
        print("Dados gerais (incluindo cargos e horários formatados) coletados para API.")
        return JsonResponse(data)
    except Exception as e:
        print(f"Erro em api_get_infogeral: {e}")
        return JsonResponse({'error': f'Erro ao buscar informações gerais: {e}'}, status=500)



@require_GET
def api_get_infocardsnovo(request):
    """
    API que retorna a quantidade de funcionários ativos e inativos para exibição nos cards.
    Retorna: JSON com 'qtd_ativos' e 'qtd_inativos'
    """
    print("\n----- Iniciando api_get_infocardsnovo -----")
    try:
        # Conta funcionários ativos
        qtd_ativos = Funcionario.objects.filter(status=True).count()
        print(f"Quantidade de funcionários ativos: {qtd_ativos}")
        
        # Conta funcionários inativos
        qtd_inativos = Funcionario.objects.filter(status=False).count()
        print(f"Quantidade de funcionários inativos: {qtd_inativos}")
        
        # Prepara os dados para retorno
        data = {
            'qtd_ativos': qtd_ativos,
            'qtd_inativos': qtd_inativos
        }
        
        print("Dados dos cards coletados com sucesso.")
        return JsonResponse(data)
    except Exception as e:
        print(f"Erro ao buscar dados para cards: {e}")
        return JsonResponse({'error': f'Erro ao buscar informações dos cards: {e}'}, status=500)




@require_GET
#@login_required
def api_get_infofuncionarios(request):
    """Retorna a lista de todos os funcionários em JSON."""
    print("\n----- Iniciando api_get_infofuncionarios -----")
    try:
        funcionarios = Funcionario.objects.select_related(
            'empresa', 'departamento', 'setor', 'cargo', 'horario', 'equipe', 'usuario'
        ).all()

        data = []
        for f in funcionarios:
            funcionario_data = {
                'id': f.id,
                'apelido': f.apelido,
                'nome_completo': f.nome_completo,
                'cpf': f.cpf,
                'data_nascimento': f.data_nascimento.strftime('%d/%m/%Y') if f.data_nascimento else None, # Exemplo de formatação
                'status': f.status,
                'empresa_id': f.empresa_id,
                'empresa_nome': f.empresa.nome if f.empresa else None,
                'departamento_id': f.departamento_id,
                'departamento_nome': f.departamento.nome if f.departamento else None,
                'setor_id': f.setor_id,
                'setor_nome': f.setor.nome if f.setor else None,
                'cargo_id': f.cargo_id,
                'cargo_nome': f.cargo.nome if f.cargo else None,
                'horario_id': f.horario_id,
                'horario_nome': f.horario.nome if f.horario else None,
                'equipe_id': f.equipe_id,
                'equipe_nome': f.equipe.nome if f.equipe else None,
                'matricula': f.matricula,
                'pis': f.pis,
                'data_admissao': f.data_admissao.strftime('%d/%m/%Y') if f.data_admissao else None,
                'data_demissao': f.data_demissao.strftime('%d/%m/%Y') if f.data_demissao else None,
                'foto_url': f.foto.url if f.foto else None,
                'usuario_id': f.usuario.id if f.usuario else None,
                'usuario_username': f.usuario.username if f.usuario else None,
                # Adicione outros campos conforme necessário
            }
            data.append(funcionario_data)

        print(f"{len(data)} funcionários coletados para API.")
        return JsonResponse(data, safe=False) # safe=False para permitir lista no JSON root
    except Exception as e:
        print(f"Erro em api_get_infofuncionarios: {e}")
        return JsonResponse({'error': f'Erro ao buscar lista de funcionários: {e}'}, status=500)

from django.http import FileResponse

@require_GET
def download_arquivo_funcionario(request, arquivo_id):
    """
    Força o download do arquivo do funcionário, enviando Content-Disposition: attachment.
    """
    from .models import ArquivoFuncionario
    arquivo_obj = get_object_or_404(ArquivoFuncionario, pk=arquivo_id, status=True)
    # abre o arquivo em modo binário
    fp = arquivo_obj.arquivo.open('rb')
    filename = os.path.basename(arquivo_obj.arquivo.name)
    response = FileResponse(fp, as_attachment=True, filename=filename)
    return response

@require_GET
def api_get_funcionario(request, funcionario_id):
    """Retorna dados detalhados de um funcionário específico em JSON, incluindo nomes relacionados."""
    print(f"\n----- Iniciando api_get_funcionario para ID: {funcionario_id} -----")
    try:
        funcionario = get_object_or_404(Funcionario.objects.select_related(
            'empresa', 'departamento', 'setor', 'cargo', 'horario', 'equipe', 'usuario', 'loja'
        ), pk=funcionario_id)
        print(f"Funcionário '{funcionario.nome_completo}' encontrado.")

        # Monta o dicionário com IDs e Nomes relacionados
        data = {
            'id': funcionario.id,
            'apelido': funcionario.apelido,
            'nome_completo': funcionario.nome_completo,
            'cpf': funcionario.cpf,
            'data_nascimento': funcionario.data_nascimento, # Formato YYYY-MM-DD
            'genero': funcionario.genero,
            'estado_civil': funcionario.estado_civil,
            'cep': funcionario.cep,
            'endereco': funcionario.endereco,
            'bairro': funcionario.bairro,
            'cidade': funcionario.cidade,
            'estado': funcionario.estado,
            'celular1': funcionario.celular1,
            'celular2': funcionario.celular2,
            'nome_mae': funcionario.nome_mae,
            'nome_pai': funcionario.nome_pai,
            'nacionalidade': funcionario.nacionalidade,
            'naturalidade': funcionario.naturalidade,
            'matricula': funcionario.matricula,
            'pis': funcionario.pis,
            'status': funcionario.status,
            'data_admissao': funcionario.data_admissao, # Formato YYYY-MM-DD
            'data_demissao': funcionario.data_demissao, # Formato YYYY-MM-DD
            'foto_url': funcionario.foto.url if funcionario.foto else None,
            'foto_nome': os.path.basename(funcionario.foto.name) if funcionario.foto else None,

            # IDs e Nomes/Textos relacionados
            'empresa_id': funcionario.empresa_id,
            'empresa_nome': funcionario.empresa.nome if funcionario.empresa else None,

            'loja_id': funcionario.loja_id,
            'loja_nome': funcionario.loja.nome if funcionario.loja else None,

            'departamento_id': funcionario.departamento_id,
            'departamento_nome': funcionario.departamento.nome if funcionario.departamento else None,

            'setor_id': funcionario.setor_id,
            'setor_nome': funcionario.setor.nome if funcionario.setor else None,

            'cargo_id': funcionario.cargo_id,
            'cargo_nome': f"{funcionario.cargo.nome} ({funcionario.cargo.get_hierarquia_display()})" if funcionario.cargo else None,

            'horario_id': funcionario.horario_id,
            'horario_nome': funcionario.horario.nome if funcionario.horario else None, # Nome base do horário
            'horario_display_text': f"{funcionario.horario.nome} ({funcionario.horario.entrada.strftime('%H:%M')} - {funcionario.horario.saida.strftime('%H:%M')})" if funcionario.horario and funcionario.horario.entrada and funcionario.horario.saida else None,

            'equipe_id': funcionario.equipe_id,
            'equipe_nome': funcionario.equipe.nome if funcionario.equipe else None,

            'usuario_id': funcionario.usuario.id if funcionario.usuario else None,
            'usuario_username': funcionario.usuario.username if funcionario.usuario else None,
        }
        from django.urls import reverse
        # Adicionar arquivos relacionados ao funcionário
        arquivos = []
        for arquivo in funcionario.arquivos.filter(status=True):
            download_url = request.build_absolute_uri(
                reverse('funcionarios:api_download_arquivo', args=[arquivo.id])
            )
            arquivos.append({
                'id': arquivo.id,
                'titulo': arquivo.titulo,
                'descricao': arquivo.descricao,
                'url': arquivo.arquivo.url,            # pode manter se quiser visualizar inline
                'download_url': download_url,          # novo
                'nome_arquivo': os.path.basename(arquivo.arquivo.name),
                'data_upload': arquivo.data_upload,
            })
        data['arquivos'] = arquivos
        
        # Adicionar IDs das regras de comissionamento associadas
        regras_comissionamento_ids = list(funcionario.regras_comissionamento.values_list('id', flat=True))
        data['regras_comissionamento_ids'] = regras_comissionamento_ids
        
        print(f"Dados do funcionário serializados com {len(arquivos)} arquivos e {len(regras_comissionamento_ids)} regras de comissão.")
        return JsonResponse(data)
    except Http404:
        print(f"Erro: Funcionário com ID {funcionario_id} não encontrado.")
        return JsonResponse({'error': 'Funcionário não encontrado'}, status=404)
    except Exception as e:
        print(f"Erro em api_get_funcionario: {e}")
        logger.exception("Erro detalhado em api_get_funcionario") # Log com traceback
        return JsonResponse({'error': f'Erro ao buscar dados do funcionário: {e}'}, status=500)

@require_GET
#@login_required
def api_get_userFuncionario(request, user_id):
    """Retorna dados do funcionário associado a um User ID específico em JSON."""
    print(f"\n----- Iniciando api_get_userFuncionario para User ID: {user_id} -----")
    try:
        # Busca o usuário
        user = get_object_or_404(User, pk=user_id)
        print(f"Usuário '{user.username}' encontrado.")

        # Tenta buscar o funcionário relacionado
        try:
            # Acessa via related_name 'funcionario_profile' definido no OneToOneField
            funcionario = Funcionario.objects.select_related(
                'empresa', 'departamento', 'setor', 'cargo', 'horario', 'equipe', 'usuario', 'loja'
            ).get(usuario=user)
            print(f"Funcionário associado '{funcionario.nome_completo}' encontrado.")

            # Serializa os dados do funcionário (similar a api_get_funcionario)
            data = {
                'id': funcionario.id,
                'apelido': funcionario.apelido,
                'nome_completo': funcionario.nome_completo,
                'cpf': funcionario.cpf,
                'data_nascimento': funcionario.data_nascimento,
                'genero': funcionario.genero,
                'estado_civil': funcionario.estado_civil,
                'cep': funcionario.cep,
                'endereco': funcionario.endereco,
                'bairro': funcionario.bairro,
                'cidade': funcionario.cidade,
                'estado': funcionario.estado,
                'celular1': funcionario.celular1,
                'celular2': funcionario.celular2,
                'nome_mae': funcionario.nome_mae,
                'nome_pai': funcionario.nome_pai,
                'nacionalidade': funcionario.nacionalidade,
                'naturalidade': funcionario.naturalidade,
                'matricula': funcionario.matricula,
                'pis': funcionario.pis,
                'empresa_id': funcionario.empresa_id,
                'loja_id': funcionario.loja_id,
                'departamento_id': funcionario.departamento_id,
                'setor_id': funcionario.setor_id,
                'cargo_id': funcionario.cargo_id,
                'horario_id': funcionario.horario_id,
                'equipe_id': funcionario.equipe_id,
                'status': funcionario.status,
                'data_admissao': funcionario.data_admissao,
                'data_demissao': funcionario.data_demissao,
                'foto_url': funcionario.foto.url if funcionario.foto else None,
                'usuario_id': funcionario.usuario_id, # Já temos o user_id
                 # Adicione nomes relacionados se necessário
            }
            print("Dados do funcionário associado serializados.")
            return JsonResponse(data)

        except Funcionario.DoesNotExist:
            print("Nenhum funcionário encontrado para este usuário.")
            return JsonResponse({'error': 'Nenhum funcionário associado a este usuário.'}, status=404)

    except Http404:
        print(f"Erro: Usuário com ID {user_id} não encontrado.")
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        print(f"Erro em api_get_userFuncionario: {e}")
        return JsonResponse({'error': f'Erro ao buscar funcionário pelo usuário: {e}'}, status=500)

# @csrf_exempt # Descomente APENAS se o AJAX não puder enviar o token CSRF
@require_POST
#@login_required # Proteja esta API se necessário
def api_post_userfuncionario(request):
    """
    API para criar um User e um Funcionario associado a partir de dados multipart/form-data.
    Espera campos normais em request.POST e o arquivo 'foto' em request.FILES.
    """
    print("\n----- Iniciando api_post_userfuncionario (multipart/form-data) -----")
    print("Dados POST:", request.POST)
    print("Arquivos FILES:", request.FILES)

    # 1. & 2. Extrair e preparar dados para User (agora de request.POST)
    apelido = request.POST.get('apelido')
    nome_completo = request.POST.get('nome_completo')

    if not apelido or not nome_completo:
        print("Erro: Apelido e Nome Completo são obrigatórios.")
        return JsonResponse({'error': 'Apelido e Nome Completo são obrigatórios'}, status=400)

    username = apelido.lower().replace(' ', '_')
    print(f"Username gerado: {username}")

    ano_atual = timezone.now().year
    password = f"Money@{ano_atual}"
    print(f"Senha padrão gerada: Money@{ano_atual}")

    partes_nome = nome_completo.split(' ', 1)
    first_name = partes_nome[0]
    last_name = partes_nome[1] if len(partes_nome) > 1 else ''

    # Verificar campos obrigatórios para Funcionário (de request.POST)
    required_fields = ['cpf', 'data_nascimento', 'empresa', 'departamento', 'setor', 'cargo']
    missing_fields = [field for field in required_fields if not request.POST.get(field)]
    if missing_fields:
        print(f"Erro: Campos obrigatórios faltando para funcionário: {', '.join(missing_fields)}")
        return JsonResponse({'error': f"Campos obrigatórios faltando: {', '.join(missing_fields)}"}, status=400)

    # Formatar CPF para remover caracteres especiais e espaços
    cpf_raw = request.POST.get('cpf', '')
    cpf_formatado = ''.join(filter(str.isdigit, cpf_raw))
    print(f"CPF original: {cpf_raw}")
    print(f"CPF formatado (apenas números): {cpf_formatado}")

    # Obter o arquivo da foto (de request.FILES)
    foto_file = request.FILES.get('foto') # A chave 'foto' deve corresponder à usada no FormData
    if foto_file:
         print(f"Arquivo de foto recebido: {foto_file.name}")
    else:
         print("Nenhum arquivo de foto recebido.")

    try:
        with transaction.atomic():
            print("Iniciando transação atômica.")
            # 3. Criar usuário
            try:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    # email=request.POST.get('email') # Obter de POST se enviado
                )
                print(f"User criado com sucesso. ID: {user.id}")
                user_id = user.id
            except IntegrityError:
                print(f"Erro: Username '{username}' já existe.")
                return JsonResponse({'error': f"Usuário com apelido/username '{username}' já existe."}, status=400)

            # 5. Criar funcionário
            try:
                # Validar e buscar ForeignKeys (de request.POST)
                empresa = get_object_or_404(Empresa, pk=request.POST.get('empresa'))
                departamento = get_object_or_404(Departamento, pk=request.POST.get('departamento'))
                setor = get_object_or_404(Setor, pk=request.POST.get('setor'))
                cargo = get_object_or_404(Cargo, pk=request.POST.get('cargo'))
                horario = HorarioTrabalho.objects.filter(pk=request.POST.get('horario')).first()
                equipe = Equipe.objects.filter(pk=request.POST.get('equipe')).first()
                loja = Loja.objects.filter(pk=request.POST.get('loja')).first()

                # Converter data de nascimento (de request.POST)
                try:
                    data_nascimento_obj = datetime.strptime(request.POST.get('data_nascimento'), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    raise ValidationError("Formato inválido para data_nascimento. Use YYYY-MM-DD.")

                funcionario = Funcionario.objects.create(
                    usuario=user,
                    apelido=apelido,
                    nome_completo=nome_completo,
                    cpf=cpf_formatado,  # Usa o CPF já formatado (somente números)
                    data_nascimento=data_nascimento_obj,
                    foto=foto_file, # Passa o arquivo para o campo ImageField/FileField
                    empresa=empresa,
                    departamento=departamento,
                    setor=setor,
                    cargo=cargo,
                    horario=horario,
                    equipe=equipe,
                    loja=loja,
                    genero=request.POST.get('genero'),
                    estado_civil=request.POST.get('estado_civil'),
                    cep=request.POST.get('cep'),
                    endereco=request.POST.get('endereco'),
                    bairro=request.POST.get('bairro'),
                    cidade=request.POST.get('cidade'),
                    estado=request.POST.get('estado'),
                    celular1=request.POST.get('celular1'),
                    celular2=request.POST.get('celular2'),
                    nome_mae=request.POST.get('nome_mae'),
                    nome_pai=request.POST.get('nome_pai'),
                    nacionalidade=request.POST.get('nacionalidade'),
                    naturalidade=request.POST.get('naturalidade'),
                    matricula=request.POST.get('matricula'),
                    pis=request.POST.get('pis'),
                    # status=request.POST.get('status') == 'true' # Exemplo se enviar status
                )
                print(f"Funcionário criado com sucesso. ID: {funcionario.id}")
                funcionario_id = funcionario.id

            except (Empresa.DoesNotExist, Departamento.DoesNotExist, Setor.DoesNotExist, Cargo.DoesNotExist):
                print("Erro: Empresa, Departamento, Setor ou Cargo não encontrado.")
                return JsonResponse({'error': 'Empresa, Departamento, Setor ou Cargo inválido.'}, status=400)
            except ValidationError as e:
                print(f"Erro de validação ao criar funcionário: {e}")
                return JsonResponse({'error': f'Erro de validação: {e.message if hasattr(e, "message") else e}'}, status=400) # Ajuste para diferentes versões do Django
            except Exception as e:
                print(f"Erro inesperado ao criar funcionário: {e}")
                print(traceback.format_exc())  # Adicione esta linha
                return JsonResponse({'error': f'Erro interno ao criar funcionário: {e}'}, status=500)

        # 6. Mensagem de retorno
        mensagem_sucesso = f"""
Usuario criado '{username}'!
Funcionario registrado com sucesso!
ID funcionario: {funcionario_id}
ID User: {user_id}
"""
        print("Operação concluída com sucesso.")
        return JsonResponse({'message': mensagem_sucesso.strip()}, status=201) # 201 Created

    except Exception as e:
        print(f"Erro geral na API (fora da transação): {e}")
        return JsonResponse({'error': f'Erro interno no servidor: {e}'}, status=500)

# ----- Views de API POST para Cadastros Administrativos -----

# @csrf_exempt # Usar com cautela
@require_POST
#@login_required # Adicione decoradores de permissão se necessário (ex: is_rh_or_superuser)
def api_post_empresa(request):
    """API para criar uma nova Empresa."""
    print("\n----- Iniciando api_post_empresa -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    cnpj = data.get('cnpj')
    endereco = data.get('endereco')
    status = data.get('status') == 'on' # Checkbox/Switch envia 'on' se marcado

    if not all([nome, cnpj, endereco]):
        return JsonResponse({'error': 'Nome, CNPJ e Endereço são obrigatórios.'}, status=400)

    try:
        empresa = Empresa.objects.create(
            nome=nome,
            cnpj=cnpj,
            endereco=endereco,
            status=status
        )
        print(f"Empresa '{empresa.nome}' criada com ID: {empresa.id}")
        return JsonResponse({'message': f'Empresa "{empresa.nome}" criada com sucesso!', 'id': empresa.id}, status=201)
    except IntegrityError as e:
         print(f"Erro de integridade: {e}")
         # Verificar se é erro de CNPJ único
         if 'cnpj' in str(e).lower():
             return JsonResponse({'error': 'Já existe uma empresa com este CNPJ.'}, status=400)
         return JsonResponse({'error': f'Erro de integridade ao criar empresa: {e}'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar empresa: {e}'}, status=500)

# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_loja(request):
    """API para criar uma nova Loja."""
    print("\n----- Iniciando api_post_loja -----")
    data = request.POST
    files = request.FILES
    print("Dados POST:", data)
    print("Arquivos FILES:", files)

    nome = data.get('nome')
    empresa_id = data.get('empresa')
    logo_file = files.get('logo')
    franquia = data.get('franquia') == 'on'
    filial = data.get('filial') == 'on'
    status = data.get('status') == 'on'

    if not nome or not empresa_id:
        return JsonResponse({'error': 'Nome da loja e Empresa são obrigatórios.'}, status=400)

    if franquia and filial:
        return JsonResponse({'error': 'Uma loja não pode ser Franquia e Filial ao mesmo tempo.'}, status=400)

    try:
        empresa = get_object_or_404(Empresa, pk=empresa_id)
        loja = Loja.objects.create(
            nome=nome,
            empresa=empresa,
            logo=logo_file, # Passa o arquivo diretamente
            franquia=franquia,
            filial=filial,
            status=status
        )
        print(f"Loja '{loja.nome}' criada com ID: {loja.id}")
        return JsonResponse({'message': f'Loja "{loja.nome}" criada com sucesso!', 'id': loja.id}, status=201)
    except Empresa.DoesNotExist:
         return JsonResponse({'error': 'Empresa selecionada não encontrada.'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar loja: {e}'}, status=500)

# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_departamento(request):
    """API para criar um novo Departamento."""
    print("\n----- Iniciando api_post_departamento -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    empresa_id = data.get('empresa')
    status = data.get('status') == 'on'

    if not nome or not empresa_id:
        return JsonResponse({'error': 'Nome do departamento e Empresa são obrigatórios.'}, status=400)

    try:
        empresa = get_object_or_404(Empresa, pk=empresa_id)
        departamento = Departamento.objects.create(
            nome=nome,
            empresa=empresa,
            status=status
        )
        print(f"Departamento '{departamento.nome}' criado com ID: {departamento.id}")
        return JsonResponse({'message': f'Departamento "{departamento.nome}" criado com sucesso!', 'id': departamento.id}, status=201)
    except Empresa.DoesNotExist:
         return JsonResponse({'error': 'Empresa selecionada não encontrada.'}, status=400)
    except IntegrityError:
         return JsonResponse({'error': f'Já existe um departamento com o nome "{nome}" nesta empresa.'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar departamento: {e}'}, status=500)

# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_setor(request):
    """API para criar um novo Setor."""
    print("\n----- Iniciando api_post_setor -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    departamento_id = data.get('departamento')
    status = data.get('status') == 'on'

    if not nome or not departamento_id:
        return JsonResponse({'error': 'Nome do setor e Departamento são obrigatórios.'}, status=400)

    try:
        departamento = get_object_or_404(Departamento, pk=departamento_id)
        setor = Setor.objects.create(
            nome=nome,
            departamento=departamento,
            status=status
        )
        print(f"Setor '{setor.nome}' criado com ID: {setor.id}")
        return JsonResponse({'message': f'Setor "{setor.nome}" criado com sucesso!', 'id': setor.id}, status=201)
    except Departamento.DoesNotExist:
         return JsonResponse({'error': 'Departamento selecionado não encontrado.'}, status=400)
    except IntegrityError:
         return JsonResponse({'error': f'Já existe um setor com o nome "{nome}" neste departamento.'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar setor: {e}'}, status=500)


# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_equipe(request):
    """API para criar uma nova Equipe."""
    print("\n----- Iniciando api_post_equipe -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    status = data.get('status') == 'on'
    participantes_ids = data.getlist('participantes') # Use getlist para campos multiple select

    if not nome:
        return JsonResponse({'error': 'Nome da equipe é obrigatório.'}, status=400)

    try:
        with transaction.atomic():
            equipe = Equipe.objects.create(
                nome=nome,
                status=status
            )
            print(f"Equipe '{equipe.nome}' criada com ID: {equipe.id}")

            if participantes_ids:
                participantes = User.objects.filter(pk__in=participantes_ids, is_active=True)
                equipe.participantes.set(participantes) # Usa set() para M2M
                print(f"Associados {participantes.count()} participantes.")

            return JsonResponse({'message': f'Equipe "{equipe.nome}" criada com sucesso!', 'id': equipe.id}, status=201)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar equipe: {e}'}, status=500)

# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_cargo(request):
    """API para criar um novo Cargo."""
    print("\n----- Iniciando api_post_cargo -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    empresa_id = data.get('empresa')
    hierarquia = data.get('hierarquia')
    status = data.get('status') == 'on'

    if not nome or not empresa_id or hierarquia is None: # Verifica se hierarquia foi enviado
        return JsonResponse({'error': 'Nome do cargo, Empresa e Nível Hierárquico são obrigatórios.'}, status=400)

    try:
        # Validar se hierarquia é um número válido e está nos choices
        hierarquia_int = int(hierarquia)
        if hierarquia_int not in Cargo.HierarquiaChoices.values:
             return JsonResponse({'error': 'Nível Hierárquico inválido.'}, status=400)

        empresa = get_object_or_404(Empresa, pk=empresa_id)
        cargo = Cargo.objects.create(
            nome=nome,
            empresa=empresa,
            hierarquia=hierarquia_int,
            status=status
        )
        print(f"Cargo '{cargo.nome}' criado com ID: {cargo.id}")
        return JsonResponse({'message': f'Cargo "{cargo.nome}" criado com sucesso!', 'id': cargo.id}, status=201)
    except Empresa.DoesNotExist:
         return JsonResponse({'error': 'Empresa selecionada não encontrada.'}, status=400)
    except ValueError:
        return JsonResponse({'error': 'Nível Hierárquico deve ser um número.'}, status=400)
    except IntegrityError:
         return JsonResponse({'error': f'Já existe um cargo com o nome "{nome}" nesta empresa.'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar cargo: {e}'}, status=500)

# @csrf_exempt
@require_POST
#@login_required # Adicione decoradores de permissão
def api_post_horario(request):
    """API para criar um novo HorarioTrabalho."""
    print("\n----- Iniciando api_post_horario -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    entrada = data.get('entrada')
    saida_almoco = data.get('saida_almoco')
    volta_almoco = data.get('volta_almoco')
    saida = data.get('saida')
    status = data.get('status') == 'on'

    if not all([nome, entrada, saida_almoco, volta_almoco, saida]):
        return JsonResponse({'error': 'Nome e todos os campos de horário (entrada, saída almoço, volta almoço, saída) são obrigatórios.'}, status=400)

    try:
        # Validação básica do formato do tempo (HH:MM) pode ser adicionada aqui se necessário
        horario = HorarioTrabalho.objects.create(
            nome=nome,
            entrada=entrada,
            saida_almoco=saida_almoco,
            volta_almoco=volta_almoco,
            saida=saida,
            status=status
        )
        print(f"Horário '{horario.nome}' criado com ID: {horario.id}")
        return JsonResponse({'message': f'Horário "{horario.nome}" criado com sucesso!', 'id': horario.id}, status=201)
    except IntegrityError:
         return JsonResponse({'error': f'Já existe um horário com o nome "{nome}".'}, status=400)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({'error': f'Erro interno ao criar horário: {e}'}, status=500)

# ----- API POST para Editar Funcionário -----

@csrf_exempt
@require_POST
@login_required
def api_edit_funcionario(request):
    """
    Edita um Funcionario existente, atualiza todos os campos (exceto CPF),
    faz parsing de datas YYYY-MM-DD, trata FKs e salva novos ArquivoFuncionario.
    """
    # 1) carrega dados JSON ou form-data
    if request.content_type.startswith('application/json'):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)
        files = {}
    else:
        data = request.POST
        files = request.FILES

    func_id = data.get('funcionario_id')
    if not func_id:
        return JsonResponse({'error': 'funcionario_id é obrigatório.'}, status=400)

    funcionario = get_object_or_404(Funcionario, pk=func_id)

    try:
        with transaction.atomic():
            # 2) campos simples (exceto cpf)
            simples = (
                'apelido','nome_completo','genero','estado_civil',
                'cep','endereco','bairro','cidade','estado',
                'celular1','celular2','nome_mae','nome_pai',
                'nacionalidade','naturalidade','matricula','pis'
            )
            for f in simples:
                if f in data:
                    val = data.get(f).strip()
                    setattr(funcionario, f, val or None)

            # status
            if 'status' in data:
                funcionario.status = data.get('status') in ('on','true',True,'True')

            # 3) datas
            for f in ('data_nascimento','data_admissao','data_demissao'):
                if f in data:
                    s = data.get(f).strip()
                    if s:
                        try:
                            setattr(funcionario, f, datetime.strptime(s, '%Y-%m-%d').date())
                        except ValueError:
                            return JsonResponse(
                                {'error': f'Formato inválido para {f}. Use YYYY-MM-DD.'},
                                status=400
                            )
                    else:
                        setattr(funcionario, f, None)

            # 4) FKs
            fk_map = {
                'empresa': Empresa, 'departamento': Departamento,
                'setor': Setor, 'cargo': Cargo,
                'horario': HorarioTrabalho, 'equipe': Equipe,
                'loja': Loja
            }
            for key, Model in fk_map.items():
                if key in data:
                    val = data.get(key).strip()
                    if val:
                        try:
                            obj = Model.objects.get(pk=int(val))
                        except (ValueError, Model.DoesNotExist):
                            return JsonResponse({'error': f'{key} inválido ({val}).'}, status=400)
                        setattr(funcionario, key, obj)
                    else:
                        setattr(funcionario, key, None)

            # 5) foto
            if 'foto' in files:
                novo = files['foto']
                if funcionario.foto:
                    funcionario.foto.delete(save=False)
                funcionario.foto = novo
            elif data.get('foto_clear') in ('on','true','True'):
                if funcionario.foto:
                    funcionario.foto.delete(save=False)
                    funcionario.foto = None

            # 6) validação e save principal
            funcionario.full_clean(exclude=['regras_comissionamento'])
            funcionario.save()

            # 7) upload de novos ArquivoFuncionario
            titulos = request.POST.getlist('arquivo_titulos[]')
            descrs  = request.POST.getlist('arquivo_descricoes[]')
            arquivos= request.FILES.getlist('arquivo_files[]')
            for titulo, arquivo_file, descricao in zip(titulos, arquivos, descrs):
                t = titulo.strip()
                if t and arquivo_file:
                    ArquivoFuncionario.objects.create(
                        funcionario=funcionario,
                        titulo=t,
                        descricao=descricao.strip() or '',
                        arquivo=arquivo_file
                    )

        return JsonResponse({'message': 'Funcionário e arquivos atualizados com sucesso.'})

    except IntegrityError as e:
        msg = str(e)
        if 'cpf' in msg.lower(): msg = 'CPF já em uso.'
        if 'matricula' in msg.lower(): msg = 'Matrícula já em uso.'
        return JsonResponse({'error': msg}, status=400)

    except ValidationError as e:
        return JsonResponse({'error': 'Erro de validação.', 'details': e.message_dict}, status=400)

    except Exception:
        import traceback; traceback.print_exc()
        return JsonResponse({'error': 'Erro interno no servidor.'}, status=500)

# ----- API POST para Desativar Funcionário (Soft Delete) -----



@require_GET
def api_get_comissao(request):
    """
    API para retornar dados necessários para formulários de comissionamento,
    incluindo regras de comissionamento ativas e listas de entidades
    (Empresas, Departamentos, Setores, Equipes) para seleção.
    """
    try:
        # Busca regras de comissionamento ativas (ID e Título)
        regras_comissionamento = list(Comissionamento.objects.filter(status=True).values('id', 'titulo').order_by('titulo'))

        # Busca Empresas ativas (ID e Nome)
        empresas = list(Empresa.objects.filter(status=True).values('id', 'nome').order_by('nome'))

        # Busca Departamentos ativos (ID, Nome, Empresa ID)
        departamentos = list(Departamento.objects.filter(status=True).values('id', 'nome', 'empresa_id').order_by('empresa__nome', 'nome'))

        # Busca Setores ativos (ID, Nome, Departamento ID)
        setores = list(Setor.objects.filter(status=True).values('id', 'nome', 'departamento_id').order_by('departamento__nome', 'nome'))

        # Busca Equipes ativas (ID e Nome)
        equipes = list(Equipe.objects.filter(status=True).values('id', 'nome').order_by('nome'))

        # Busca Lojas ativas (ID, Nome, Empresa ID)
        lojas = list(Loja.objects.filter(status=True).values('id', 'nome', 'empresa_id').order_by('empresa__nome', 'nome'))

        # Monta o dicionário de resposta
        data = {
            'regras_comissionamento': regras_comissionamento,
            'empresas': empresas,
            'departamentos': departamentos,
            'setores': setores,
            'equipes': equipes,
            'lojas': lojas,
        }

        return JsonResponse(data)

    except Exception as e:
        # Log do erro (substituir print por logger em produção)
        import traceback
        tb_str = traceback.format_exc()
        print(f"Erro ao buscar dados para formulário de comissionamento: {e}\n{tb_str}")
        # logger.exception("Erro ao buscar dados para formulário de comissionamento")
        return JsonResponse({'error': 'Erro interno ao buscar dados necessários.'}, status=500)


@csrf_exempt # Remover em produção se usar autenticação de sessão e AJAX configurado corretamente
@require_POST
@transaction.atomic # Garante que a criação e a adição de M2M sejam atômicas
def api_post_novaregracomissao(request):
    """
    API para criar uma nova regra de comissionamento via POST (JSON).
    Espera um corpo JSON com os dados da regra, incluindo listas de IDs para campos ManyToMany.
    Exemplo de JSON esperado:
    {
        "titulo": "Comissão Vendas Loja X",
        "escopo_base": "PESSOAL",
        "percentual": "5.50",
        "valor_fixo": null,
        "valor_de": null,
        "valor_ate": null,
        "data_inicio": "2024-01-01",
        "data_fim": null,
        "status": true,
        "empresas": [1, 2],
        "departamentos": [3],
        "setores": [],
        "equipes": [5],
        "lojas": [6]
    }
    """
    try:
        data = json.loads(request.body)

        # --- Extração e Validação de Dados ---
        titulo = data.get('titulo')
        escopo_base = data.get('escopo_base')
        percentual_str = data.get('percentual')
        valor_fixo_str = data.get('valor_fixo')
        valor_de_str = data.get('valor_de')
        valor_ate_str = data.get('valor_ate')
        data_inicio_str = data.get('data_inicio')
        data_fim_str = data.get('data_fim')
        status = data.get('status', True) # Default para True se não fornecido

        # Validações básicas de campos obrigatórios
        if not titulo:
            return JsonResponse({'error': 'O campo "titulo" é obrigatório.'}, status=400)
        if not escopo_base or escopo_base not in Comissionamento.EscopoBaseComissaoChoices.values:
             valid_choices = ", ".join(Comissionamento.EscopoBaseComissaoChoices.values)
             return JsonResponse({'error': f'O campo "escopo_base" é obrigatório e deve ser um dos seguintes: {valid_choices}.'}, status=400)

        # Conversão e validação de campos numéricos (Decimal)
        percentual = None
        if percentual_str is not None and percentual_str != '':
            try:
                percentual = Decimal(percentual_str)
            except InvalidOperation:
                return JsonResponse({'error': 'Valor inválido para "percentual". Use formato numérico (ex: 5.50).'}, status=400)

        valor_fixo = None
        if valor_fixo_str is not None and valor_fixo_str != '':
            try:
                valor_fixo = Decimal(valor_fixo_str)
            except InvalidOperation:
                return JsonResponse({'error': 'Valor inválido para "valor_fixo". Use formato numérico (ex: 100.00).'}, status=400)

        valor_de = None
        if valor_de_str is not None and valor_de_str != '':
            try:
                valor_de = Decimal(valor_de_str)
            except InvalidOperation:
                return JsonResponse({'error': 'Valor inválido para "valor_de". Use formato numérico.'}, status=400)

        valor_ate = None
        if valor_ate_str is not None and valor_ate_str != '':
            try:
                valor_ate = Decimal(valor_ate_str)
            except InvalidOperation:
                return JsonResponse({'error': 'Valor inválido para "valor_ate". Use formato numérico.'}, status=400)

        # Conversão e validação de datas
        data_inicio = None
        if data_inicio_str:
            data_inicio = parse_date(data_inicio_str)
            if not data_inicio:
                return JsonResponse({'error': 'Formato inválido para "data_inicio". Use AAAA-MM-DD.'}, status=400)

        data_fim = None
        if data_fim_str:
            data_fim = parse_date(data_fim_str)
            if not data_fim:
                return JsonResponse({'error': 'Formato inválido para "data_fim". Use AAAA-MM-DD.'}, status=400)

        # --- Criação da Instância ---
        nova_regra = Comissionamento(
            titulo=titulo,
            escopo_base=escopo_base,
            percentual=percentual,
            valor_fixo=valor_fixo,
            valor_de=valor_de,
            valor_ate=valor_ate,
            data_inicio=data_inicio,
            data_fim=data_fim,
            status=status
        )

        # Executa validações do modelo (método clean)
        try:
            nova_regra.full_clean(exclude=['empresas', 'departamentos', 'setores', 'equipes', 'lojas']) # Exclui M2M da validação inicial
        except ValidationError as e:
            print(f"Erro de validação ao criar regra de comissão: {e.message_dict}") # Substituído logger.warning por print
            return JsonResponse({'error': 'Erro de validação.', 'details': e.message_dict}, status=400)

        # Salva o objeto principal primeiro
        nova_regra.save()

        # --- Processamento dos Campos ManyToMany ---
        m2m_errors = {}

        # Empresas
        empresa_ids = data.get('empresas', [])
        if isinstance(empresa_ids, list):
            try:
                empresas_objs = Empresa.objects.filter(id__in=empresa_ids)
                if len(empresas_objs) != len(empresa_ids):
                     m2m_errors['empresas'] = 'Uma ou mais IDs de Empresa fornecidas são inválidas.'
                else:
                     nova_regra.empresas.set(empresas_objs)
            except Exception as e:
                 m2m_errors['empresas'] = f'Erro ao processar Empresas: {e}'
        elif empresa_ids:
             m2m_errors['empresas'] = 'O campo "empresas" deve ser uma lista de IDs.'

        # Departamentos
        departamento_ids = data.get('departamentos', [])
        if isinstance(departamento_ids, list):
            try:
                departamentos_objs = Departamento.objects.filter(id__in=departamento_ids)
                if len(departamentos_objs) != len(departamento_ids):
                    m2m_errors['departamentos'] = 'Uma ou mais IDs de Departamento fornecidas são inválidas.'
                else:
                    nova_regra.departamentos.set(departamentos_objs)
            except Exception as e:
                m2m_errors['departamentos'] = f'Erro ao processar Departamentos: {e}'
        elif departamento_ids:
            m2m_errors['departamentos'] = 'O campo "departamentos" deve ser uma lista de IDs.'

        # Setores
        setor_ids = data.get('setores', [])
        if isinstance(setor_ids, list):
            try:
                setores_objs = Setor.objects.filter(id__in=setor_ids)
                if len(setores_objs) != len(setor_ids):
                    m2m_errors['setores'] = 'Uma ou mais IDs de Setor fornecidas são inválidas.'
                else:
                    nova_regra.setores.set(setores_objs)
            except Exception as e:
                m2m_errors['setores'] = f'Erro ao processar Setores: {e}'
        elif setor_ids:
            m2m_errors['setores'] = 'O campo "setores" deve ser uma lista de IDs.'

        # Equipes
        equipe_ids = data.get('equipes', [])
        if isinstance(equipe_ids, list):
            try:
                equipes_objs = Equipe.objects.filter(id__in=equipe_ids)
                if len(equipes_objs) != len(equipe_ids):
                    m2m_errors['equipes'] = 'Uma ou mais IDs de Equipe fornecidas são inválidas.'
                else:
                    nova_regra.equipes.set(equipes_objs)
            except Exception as e:
                m2m_errors['equipes'] = f'Erro ao processar Equipes: {e}'
        elif equipe_ids:
            m2m_errors['equipes'] = 'O campo "equipes" deve ser uma lista de IDs.'

        # Lojas
        loja_ids = data.get('lojas', [])
        if isinstance(loja_ids, list):
            try:
                lojas_objs = Loja.objects.filter(id__in=loja_ids)
                if len(lojas_objs) != len(loja_ids):
                    m2m_errors['lojas'] = 'Uma ou mais IDs de Loja fornecidas são inválidas.'
                else:
                    nova_regra.lojas.set(lojas_objs)
            except Exception as e:
                m2m_errors['lojas'] = f'Erro ao processar Lojas: {e}'
        elif loja_ids:
            m2m_errors['lojas'] = 'O campo "lojas" deve ser uma lista de IDs.'

        # Se houve erros nos M2M, retorna o erro (a transação será revertida)
        if m2m_errors:
             print(f"Erro ao processar M2M para nova regra de comissão: {m2m_errors}") # Substituído logger.warning por print
             # A transação será revertida automaticamente ao levantar a exceção ou retornar erro
             return JsonResponse({'error': 'Erro ao processar relações ManyToMany.', 'details': m2m_errors}, status=400)

        # Executa validações novamente, agora incluindo M2M (se houver validações dependentes)
        try:
            nova_regra.full_clean()
        except ValidationError as e:
            print(f"Erro de validação final (com M2M) ao criar regra: {e.message_dict}") # Substituído logger.warning por print
            # A transação será revertida
            return JsonResponse({'error': 'Erro de validação final.', 'details': e.message_dict}, status=400)


        print(f"Nova regra de comissionamento '{nova_regra.titulo}' (ID: {nova_regra.id}) criada com sucesso.") # Substituído logger.info por print
        return JsonResponse({
            'message': 'Nova regra de comissionamento criada com sucesso!',
            'comissao_id': nova_regra.id
        }, status=201) # 201 Created

    except json.JSONDecodeError:
        print("Erro ao decodificar JSON na criação de regra de comissão.") # Substituído logger.error por print
        return JsonResponse({'error': 'JSON inválido no corpo da requisição.'}, status=400)
    except IntegrityError as e:
        print(f"Erro de integridade ao criar regra de comissão: {e}") # Substituído logger.error por print
        return JsonResponse({'error': f'Erro de integridade: {e}'}, status=400)
    except Exception as e:
        import traceback
        print(f"Erro inesperado ao criar nova regra de comissionamento: {e}\n{traceback.format_exc()}") # Substituído logger.exception por print com traceback
        return JsonResponse({'error': f'Erro interno no servidor: {e}'}, status=500)

# ----- API POST para Produto -----

# @csrf_exempt # Usar com cautela
@require_POST
#@login_required # Adicione decoradores de permissão se necessário (ex: is_rh_or_superuser)
def api_post_novoproduto(request):
    """API para criar um novo Produto."""
    print("\n----- Iniciando api_post_novoproduto -----")
    data = request.POST
    print("Dados recebidos:", data)

    nome = data.get('nome')
    descricao = data.get('descricao', '') # Descrição é opcional
    status = data.get('status') == 'on' # Checkbox/Switch envia 'on' se marcado

    if not nome:
        return JsonResponse({'error': 'Nome do Produto é obrigatório.'}, status=400)

    try:
        produto = Produto.objects.create(
            nome=nome.upper(), # Salvar nome em maiúsculas, por exemplo
            descricao=descricao,
            ativo=status # O nome do campo no modelo é 'ativo'
        )
        print(f"Produto '{produto.nome}' criado com ID: {produto.id}")
        return JsonResponse({'message': f'Produto "{produto.nome}" criado com sucesso!', 'id': produto.id}, status=201)
    except IntegrityError:
         # O modelo Produto tem unique=True no nome
         return JsonResponse({'error': f'Já existe um produto com o nome "{nome.upper()}".'}, status=400)
    except Exception as e:
        print(f"Erro inesperado ao criar produto: {e}")
        # logger.exception("Erro inesperado ao criar produto") # Se usar logger
        return JsonResponse({'error': f'Erro interno ao criar produto: {e}'}, status=500)


# ----- Views e API para o Dashboard de Funcionários -----



@require_GET
@login_required
def api_get_dashboard(request):
    """
    API que retorna dados agregados para o dashboard de funcionários,
    incluindo a lista de aniversariantes do mês.
    """
    try:
        hoje = timezone.now().date()
        mes_atual = hoje.month
        dia_atual = hoje.day

        # --- Dados Gerais de RH ---
        total_ativos = Funcionario.objects.filter(status=True).count()
        total_inativos = Funcionario.objects.filter(status=False).count()

        admin_counts = {
            'empresas': Empresa.objects.filter(status=True).count(),
            'lojas_sede': Loja.objects.filter(status=True, filial=False, franquia=False).count(),
            'lojas_filial': Loja.objects.filter(status=True, filial=True).count(),
            'lojas_franquia': Loja.objects.filter(status=True, franquia=True).count(),
            'departamentos': Departamento.objects.filter(status=True).count(),
            'setores': Setor.objects.filter(status=True).count(),
            'cargos': Cargo.objects.filter(status=True).count(),
            'equipes': Equipe.objects.filter(status=True).count(),
        }

        # --- Distribuição de Funcionários ---
        ativos_qs = Funcionario.objects.filter(status=True)
        from django.db.models import Count
        cargos_ativos = ativos_qs.values('cargo__nome').annotate(total=Count('id')).order_by('-total')
        funcionarios_distribuicao = {
            'geral': {
                'ativos': total_ativos,
                'inativos': total_inativos,
            },
            'por_empresa': list(ativos_qs.values('empresa__nome').annotate(total=Count('id')).order_by('empresa__nome')),
            'por_loja':    list(ativos_qs.exclude(loja__isnull=True)
                                   .values('loja__nome').annotate(total=Count('id')).order_by('loja__nome')),
            'por_departamento': list(ativos_qs.values('departamento__nome')
                                     .annotate(total=Count('id')).order_by('departamento__nome')),
            'por_setor': list(ativos_qs.values('setor__nome')
                              .annotate(total=Count('id')).order_by('setor__nome')),
            'por_cargo': list(cargos_ativos),
            'por_equipe': list(ativos_qs.exclude(equipe__isnull=True)
                               .values('equipe__nome').annotate(total=Count('id')).order_by('equipe__nome')),
        }

        # --- Aniversariantes do Mês ---
        # Removido filtro status=True para não excluir aniversariantes inativos
        aniversariantes_qs = Funcionario.objects.filter(
            data_nascimento__month=mes_atual
        ).select_related('departamento', 'setor').order_by('data_nascimento__day')

        aniversariantes_list = []
        for f in aniversariantes_qs:
            dia_aniv = f.data_nascimento.day
            if dia_aniv == dia_atual:
                status = "Dia de comemorar"
            elif dia_aniv > dia_atual:
                status = "Quase lá"
            else:
                status = "Já foi"

            aniversariantes_list.append({
                'nome': f.nome_completo,
                'departamento': f.departamento.nome if f.departamento else 'N/A',
                'setor': f.setor.nome if f.setor else 'N/A',
                'data': f.data_nascimento.strftime('%d/%m'),
                'status': status,
                'dia': dia_aniv,  # Mantemos o dia caso queira ordenar ou usar no frontend
            })

        # Log de depuração
        print(f"Aniversariantes mês {mes_atual}: {len(aniversariantes_list)} encontrado(s).")

        response = {
            'admin_rh': admin_counts,
            'funcionarios': funcionarios_distribuicao,
            'aniversariantes': aniversariantes_list,
            'timestamp': timezone.now().isoformat(),
        }
        return JsonResponse(response)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"Erro em api_get_dashboard: {e}\n{tb}")
        return JsonResponse({'error': f'Erro interno ao buscar dados do dashboard: {e}'}, status=500)

