$(document).ready(function() {
    // --- Configuração ---
    const apiUrlGeral = '/rh/api/get/infogeral/'; // Corrigido prefixo
    const apiUrlFuncionarios = '/rh/api/get/infofuncionarios/'; // Corrigido prefixo
    const apiUrlNovoFuncionario = '/rh/api/post/userfuncionario/'; // Corrigido prefixo
    const $form = $('form'); // Seleciona o formulário principal da página
    const $messageContainer = $('#message-container'); // <<< ADICIONADO AQUI

    // --- Elementos do DOM ---
    const $empresaSelect = $('#empresa');
    const $departamentoSelect = $('#departamento');
    const $setorSelect = $('#setor');
    const $cargoSelect = $('#cargo');
    const $horarioSelect = $('#horario');
    const $equipeSelect = $('#equipe');
    const $cpfInput = $('#cpf');
    const $dataNascimentoInput = $('#data_nascimento'); // Adicionado para o campo de data
    const $submitButton = $form.find('button[type="submit"]');

    // --- Cache de Dados ---
    let todosDepartamentos = [];
    let todosSetores = [];
    let todosCargos = [];
    let todosEmpresas = [];
    let todosHorarios = [];
    let todosEquipes = [];
    let listaCpfsExistentes = []; // Armazena CPFs para validação rápida

    // --- Funções Auxiliares ---

    // Obtém o token CSRF do cookie
    function getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 'csrftoken'.length + 1) === ('csrftoken' + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Exibe mensagens como Toasts (ATUALIZADO)
    function showMessage(type, message, duration = 5000) {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const iconClass = type === 'success' ? 'bxs-check-circle' : 'bxs-x-circle';

        // Cria o elemento de alerta (toast)
        const $alert = $(`
            <div class="alert ${alertClass} alert-dismissible fade" role="alert" style="display: flex; align-items: center; gap: 0.75rem;">
                <i class='bx ${iconClass}' style="font-size: 1.3rem; flex-shrink: 0;"></i>
                <div style="flex-grow: 1;">${message}</div>
                <button type="button" class="btn-close" aria-label="Close" style="padding: 0.8rem; opacity: 0.8; background: none; border: none; font-size: 1.2rem; line-height: 1; color: inherit;"></button>
            </div>
        `);

        // Cria o container de toasts se ainda não existir
        let $toastContainer = $('#message-container'); // Usa o ID do CSS
        if ($toastContainer.length === 0) {
            // Cria o container com os estilos corretos
            $toastContainer = $('<div id="message-container" style="position: fixed; top: 20px; right: 20px; z-index: 1056; width: auto; max-width: 400px;"></div>');
            $('body').append($toastContainer);
        }

        // Adiciona o novo toast ao container
        $toastContainer.append($alert);

        // Força reflow para garantir que a animação funcione
        $alert.width();

        // Adiciona a classe 'show' para iniciar a animação de entrada
        $alert.addClass('show');

        // Define timeout para remover o toast
        const timer = setTimeout(() => {
            $alert.removeClass('show'); // Inicia animação de saída
            $alert.on('transitionend webkitTransitionEnd oTransitionEnd', function () {
                $(this).remove();
            });
            setTimeout(() => $alert.remove(), 600); // Fallback
        }, duration);

        // Permite fechar manualmente
        $alert.find('.btn-close').on('click', function() {
            clearTimeout(timer);
             const $thisAlert = $(this).closest('.alert');
             $thisAlert.removeClass('show');
             $thisAlert.on('transitionend webkitTransitionEnd oTransitionEnd', function () {
                 $(this).remove();
             });
             setTimeout(() => $thisAlert.remove(), 600);
        });
    }

    // Limpa e reseta um select
    function resetSelect($select, defaultOptionText) {
        $select.empty().append(`<option value="">${defaultOptionText}</option>`).prop('disabled', true);
    }

    // Validação básica de CPF (algoritmo)
    function validarCPF(cpf) {
        cpf = cpf.replace(/[^\d]+/g, ''); // Remove caracteres não numéricos
        if (cpf == '') return false;
        if (cpf.length != 11 ||
            cpf == "00000000000" ||
            cpf == "11111111111" ||
            cpf == "22222222222" ||
            cpf == "33333333333" ||
            cpf == "44444444444" ||
            cpf == "55555555555" ||
            cpf == "66666666666" ||
            cpf == "77777777777" ||
            cpf == "88888888888" ||
            cpf == "99999999999")
            return false;
        // Valida DVs
        let add = 0;
        for (let i = 0; i < 9; i++) add += parseInt(cpf.charAt(i)) * (10 - i);
        let rev = 11 - (add % 11);
        if (rev == 10 || rev == 11) rev = 0;
        if (rev != parseInt(cpf.charAt(9))) return false;
        add = 0;
        for (let i = 0; i < 10; i++) add += parseInt(cpf.charAt(i)) * (11 - i);
        rev = 11 - (add % 11);
        if (rev == 10 || rev == 11) rev = 0;
        if (rev != parseInt(cpf.charAt(10))) return false;
        return true;
    }

    // --- Funções de Carregamento e População ---

    // Carrega dados gerais e de funcionários
    function carregarDadosIniciais() {
        console.log("Iniciando carregamento de dados...");
        // Usar Promise.all para carregar ambos em paralelo
        Promise.all([
            $.getJSON(apiUrlGeral).fail(function() { console.error("Falha ao carregar dados gerais."); return $.Deferred().resolve(null); }), // Continua mesmo se falhar
            $.getJSON(apiUrlFuncionarios).fail(function() { console.error("Falha ao carregar funcionários."); return $.Deferred().resolve(null); }) // Continua mesmo se falhar
        ]).then(([dataGeral, dataFuncionarios]) => {

            if (dataGeral) {
                console.log("Dados gerais carregados:", dataGeral);
                // Armazena dados em cache
                todosEmpresas = dataGeral.empresas || [];
                todosDepartamentos = dataGeral.departamentos || [];
                todosSetores = dataGeral.setores || [];
                todosCargos = dataGeral.cargos || [];
                todosHorarios = dataGeral.horarios || [];
                todosEquipes = dataGeral.equipes || [];

                // Popula selects principais
                popularSelect($empresaSelect, todosEmpresas, 'id', 'nome', '--- Selecione a Empresa ---');
                popularSelect($horarioSelect, todosHorarios, 'id', 'nome', '--- Selecione o Horário ---'); // Usar 'nome' para exibição
                popularSelect($equipeSelect, todosEquipes, 'id', 'nome', '--- Nenhuma Equipe ---');

                // Habilita selects principais se tiverem opções
                $empresaSelect.prop('disabled', todosEmpresas.length === 0);
                $horarioSelect.prop('disabled', todosHorarios.length === 0);
                $equipeSelect.prop('disabled', todosEquipes.length === 0);
            } else {
                showMessage('error', 'Não foi possível carregar os dados básicos do formulário.');
                // Desabilita selects que dependem dos dados gerais
                $empresaSelect.prop('disabled', true);
                $horarioSelect.prop('disabled', true);
                $equipeSelect.prop('disabled', true);
            }

            if (dataFuncionarios) {
                console.log("Funcionários carregados:", dataFuncionarios);
                listaCpfsExistentes = (dataFuncionarios || []).map(f => f.cpf.replace(/[\D]/g, '')); // Garante limpeza correta
            } else {
                 showMessage('warning', 'Não foi possível carregar a lista de funcionários para validação de CPF.');
            }

        }).catch(error => {
            // Este catch pode não ser atingido devido aos .fail() individuais, mas é bom ter
            console.error("Erro GERAL ao carregar dados iniciais:", error);
            showMessage('error', 'Erro crítico ao carregar dados. Tente recarregar a página.');
        });
    }

    // Popula Departamentos e Cargos com base na Empresa
    function popularSelectsDependentes(empresaId) {
        resetSelect($departamentoSelect, '--- Selecione a Empresa Primeiro ---');
        resetSelect($setorSelect, '--- Selecione o Departamento Primeiro ---');
        resetSelect($cargoSelect, '--- Selecione a Empresa Primeiro ---');

        if (!empresaId) {
            return; // Já estão resetados e desabilitados
        }

        // Filtra Departamentos
        const departamentosFiltrados = todosDepartamentos.filter(d => String(d.empresa_id) === String(empresaId));
        popularSelect($departamentoSelect, departamentosFiltrados, 'id', 'nome', '--- Selecione o Departamento ---');
        $departamentoSelect.prop('disabled', departamentosFiltrados.length === 0);

        // Filtra Cargos
        const cargosFiltrados = todosCargos.filter(c => String(c.empresa_id) === String(empresaId));
        popularSelect($cargoSelect, cargosFiltrados, 'id', 'nome_com_hierarquia', '--- Selecione o Cargo ---');
        $cargoSelect.prop('disabled', cargosFiltrados.length === 0);
    }

    // Popula Setores com base no Departamento
    function popularSetores(departamentoId) {
        resetSelect($setorSelect, '--- Selecione o Departamento Primeiro ---');

        if (!departamentoId) {
            return; // Já está resetado e desabilitado
        }

        const setoresFiltrados = todosSetores.filter(s => String(s.departamento_id) === String(departamentoId));
        popularSelect($setorSelect, setoresFiltrados, 'id', 'nome', '--- Selecione o Setor ---');
        $setorSelect.prop('disabled', setoresFiltrados.length === 0);
    }

    // Função genérica para popular um select
    function popularSelect($select, data, valueField, textField, defaultOptionText) {
        $select.empty().append(`<option value="">${defaultOptionText}</option>`);
        if (data && data.length > 0) {
             data.forEach(item => {
                // Para Horário, usa a representação __str__ que já vem formatada (assumindo que a API retorna)
                // Se a API retornar campos separados, ajuste aqui para formatar como quiser.
                // Ex: const displayText = textField === 'horario_formatado' ? item.horario_formatado : item[textField];
                const displayText = item[textField];
                $select.append(`<option value="${item[valueField]}">${displayText}</option>`);
            });
            // Habilita o select SE ele foi populado com opções válidas
             $select.prop('disabled', false);
        } else {
            // Mantém desabilitado se não houver dados
            $select.prop('disabled', true);
        }
    }

    // Função para carregar dados dos cards (funcionários ativos e inativos)
    function carregarDadosCards() {
        console.log("Carregando dados dos cards de funcionários...");
        
        // URL da API que retorna as quantidades
        const apiUrlCards = '/rh/api/get/infocardsnovo/';
        
        // Requisição AJAX para obter os dados
        $.ajax({
            url: apiUrlCards,
            type: 'GET',
            success: function(response) {
                console.log("Dados dos cards recebidos:", response);
                
                // Atualiza o card de funcionários ativos
                const $cardAtivos = $('.dashboard-card.border-success .card-body p');
                $cardAtivos.text(response.qtd_ativos || 0);
                
                // Atualiza o card de funcionários inativos
                const $cardInativos = $('.dashboard-card.border-danger .card-body p');
                $cardInativos.text(response.qtd_inativos || 0);
                
                console.log("Cards atualizados com sucesso.");
            },
            error: function(xhr, status, error) {
                console.error("Erro ao carregar dados dos cards:", error);
                // Não exibe mensagem de erro para o usuário para não interromper a experiência
            }
        });
    }

    // --- Funções de Validação e Submissão ---

    // Verifica se CPF é válido e se já existe
    function handleCPFChange() {
        const cpf = $cpfInput.val();
        const cpfLimpo = cpf.replace(/[^\d]+/g, '');
        $cpfInput.removeClass('is-invalid is-valid'); // Limpa classes de validação

        if (cpfLimpo.length === 11) {
            if (!validarCPF(cpf)) {
                $cpfInput.addClass('is-invalid');
                showMessage('error', 'CPF inválido.');
                return false; // Inválido
            } else if (listaCpfsExistentes.includes(cpfLimpo)) {
                $cpfInput.addClass('is-invalid'); // Ou 'is-warning' se preferir
                showMessage('error', 'Este CPF já está cadastrado.');
                return false; // Já existe
            } else {
                $cpfInput.addClass('is-valid');
                $messageContainer.empty(); // Limpa mensagens anteriores
                return true; // Válido e não existe
            }
        } else if (cpfLimpo.length > 0) {
            // Se não tem 11 dígitos mas não está vazio, marca como inválido
             $cpfInput.addClass('is-invalid');
             return false; // Incompleto/Inválido
        }
         return true; // Vazio ou incompleto, mas não necessariamente inválido ainda
    }

    // Submete o formulário via AJAX
    function submeterFormulario(event) {
        event.preventDefault(); // Impede o envio tradicional
        $messageContainer.empty(); // Limpa mensagens anteriores

        // Valida CPF antes de enviar
        if (!handleCPFChange()) {
            $cpfInput.focus();
            return;
        }

        // Validação de campos obrigatórios do HTML5 (boa prática adicional)
        if (!$form[0].checkValidity()) {
            $form[0].reportValidity(); // Mostra mensagens de validação nativas do browser
            return;
        }

        // Formatação dos dados
        const cpf = $cpfInput.val().replace(/[^\d]+/g, ''); // Formata CPF
        const dataNascimento = $dataNascimentoInput.val(); // Obtém a data de nascimento

        // Log dos dados antes de enviar
        console.log("Dados a serem enviados:", {
            apelido: $('#apelido').val(),
            nome_completo: $('#nome_completo').val(),
            cpf: cpf,
            data_nascimento: dataNascimento,
            empresa: $empresaSelect.val(),
            departamento: $departamentoSelect.val(),
            setor: $setorSelect.val(),
            cargo: $cargoSelect.val(),
            horario: $horarioSelect.val(),
            equipe: $equipeSelect.val(),
            // Adicione outros campos conforme necessário
        });

        // Log da foto
        const fotoFile = $('#foto')[0].files[0]; // Obtém o arquivo da foto
        if (fotoFile) {
            console.log("Arquivo de foto a ser enviado:", fotoFile.name);
        } else {
            console.log("Nenhum arquivo de foto selecionado.");
        }

        // Envia a requisição POST diretamente
        const formData = new FormData($form[0]); // Cria FormData a partir do formulário
        const submitButtonText = $submitButton.html();
        $submitButton.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Salvando...');

        $.ajax({
            url: apiUrlNovoFuncionario,
            type: 'POST',
            data: formData,
            processData: false, // Necessário para FormData
            contentType: false, // Necessário para FormData
            headers: {
                'X-CSRFToken': getCsrfToken() // Inclui o token CSRF
            },
            success: function(response) {
                if (response && response.message) {
                    console.log("Sucesso:", response);
                    showMessage('success', response.message); // Exibe a mensagem de sucesso recebida da API
                    $form[0].reset(); // Limpa o formulário
                    // Reseta selects dependentes e validação de CPF
                    resetSelect($departamentoSelect, '--- Selecione a Empresa Primeiro ---');
                    resetSelect($setorSelect, '--- Selecione o Departamento Primeiro ---');
                    resetSelect($cargoSelect, '--- Selecione a Empresa Primeiro ---');
                    $cpfInput.removeClass('is-valid is-invalid');
                    // Recarrega a lista de CPFs para incluir o novo
                    carregarDadosIniciais();
                    carregarDadosCards();
                } else {
                    showMessage('error', 'Erro ao adicionar funcionário. Tente novamente.');
                }
            },
            error: function(xhr, status, error) {
                showMessage('error', 'Erro ao adicionar funcionário: ' + error);
            },
            complete: function() {
                $submitButton.prop('disabled', false).html(submitButtonText); // Restaura o botão
            }
        });
    }

    // --- Event Listeners ---

    // Ao mudar a Empresa, popula os selects dependentes
    $empresaSelect.change(function() {
        const empresaId = $(this).val();
        popularSelectsDependentes(empresaId);
    });

    // Ao mudar o Departamento, popula os Setores
    $departamentoSelect.change(function() {
        const departamentoId = $(this).val();
        popularSetores(departamentoId);
    });

    // Ao sair do campo CPF ou mudar seu valor, valida
    $cpfInput.on('blur change', handleCPFChange);

    // Intercepta o envio do formulário
    $form.submit(submeterFormulario);

    // --- Inicialização ---
    carregarDadosIniciais(); // Carrega dados quando a página estiver pronta
    carregarDadosCards(); // Carrega dados dos cards de quantidade de funcionários

    // Aplica máscara ao CPF (Exemplo usando jQuery Mask Plugin - inclua a lib no seu base.html)
    // Se você não usa essa lib, remova ou adapte esta linha.
    if ($.fn.mask) {
        $cpfInput.mask('000.000.000-00');
    } else {
        console.warn('jQuery Mask Plugin não encontrado. Máscara de CPF não aplicada.');
    }

}); 