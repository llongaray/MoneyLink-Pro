from django.urls import path
from .views import *

app_name = 'siape'

urlpatterns = [
    # Rotas da API (seguindo o padrão api/METHOD/...)
    path('api/get/cards/', api_cards, name='api_get_cards'), # Atualizado
    path('api/get/podium/', api_podium, name='api_get_podium'), # Atualizado
    path('api/get/ficha-cliente/', api_get_ficha_cliente, name='api_get_ficha_cliente'), # Atualizado
    path('api/post/importar-csv/', api_post_importar_csv, name='api_post_importar_csv'), # Já segue o padrão
    path('api/post/siape/campanha/', api_post_campanha, name='api_post_campanha'), # Atualizado
    path('api/post/agendamento-cliente/', api_post_agend_cliente, name='api_post_agend_cliente'), # Já segue o padrão
    path('api/get/agendamentos-cliente/', api_get_agendamentos_cliente, name='api_get_agendamentos_cliente'), # Já segue o padrão
    path('api/get/infocliente/', api_get_infocliente, name='api_get_infocliente'), # Já segue o padrão
    path('api/post/confirm-agendamento/', api_post_confirm_agend, name='api_post_confirm_agend'), # Já segue o padrão
    path('api/get/info-camp/', api_get_info_camp, name='api_get_info_camp'), # Atualizado

    # Novas Rotas da API (Financeiro - seguindo o padrão api/METHOD/...)
    path('api/get/info/', api_get_infosiape, name='api_get_infosiape'), # Atualizado
    path('api/get/registros-tac/', api_get_registrosTac, name='api_get_registrosTac'), # Atualizado
    path('api/get/cards-tac/', api_get_cardstac, name='api_get_cardstac'), # Atualizado
    path('api/post/novo-tac/', api_post_novotac, name='api_post_novotac'), # Atualizado
    path('api/get/nome-cliente/', api_get_nomecliente, name='api_get_nomecliente'), # Atualizado

    # Nova rota para excluir débitos de campanha
    path('api/post/excluir-debitos-campanha/', api_post_excluir_debitos_campanha, name='api_post_excluir_debitos_campanha'),
    
    # Rotas de páginas (não precisam seguir o padrão da API)
    path('ranking/', render_ranking, name='ranking'),
    path('consulta-cliente/', render_consulta_cliente, name='consulta_cliente'),
    path('export-register-money/', export_register_money, name='export_register_money'),
    path('campanhas-siape/', render_campanha_Siape, name='campanhas_siape'),
    path('financeiro/', render_financeiro, name='financeiro'), # Rota para a página Financeiro
]
