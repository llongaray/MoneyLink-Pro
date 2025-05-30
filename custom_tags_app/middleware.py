from django.shortcuts import redirect
from django.urls import reverse

class SetorRedirectMiddleware:
    """
    Middleware para redirecionar usuários com base em seu departamento.
    Redireciona funcionários do departamento jurídico para o dashboard jurídico.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Processa apenas se o usuário estiver autenticado e a URL for a raiz
        if request.user.is_authenticated and request.path == '/':
            try:
                # Tenta obter o funcionário associado ao usuário
                funcionario = request.user.funcionario_profile
                
                # Verifica se o funcionário existe e tem um departamento
                if funcionario and funcionario.departamento:
                    # Se o departamento for "JURIDICO", redireciona para o dashboard jurídico
                    if funcionario.departamento.nome.upper() == 'JURIDICO':
                        return redirect(reverse('juridico:dashboard_acoes'))
            except Exception as e:
                # Se ocorrer algum erro, apenas continua o fluxo normal
                pass

        # Continua o processamento normal para outros casos
        return self.get_response(request)
