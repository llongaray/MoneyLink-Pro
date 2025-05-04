$(document).ready(function() {
    // --- Configuração ---
    const apiUrlGeral = '/rh/api/get/infogeral/';          // Corrigido prefixo /rh/
    const apiUrlFuncionarios = '/rh/api/get/infofuncionarios/'; // Corrigido prefixo /rh/
    const apiUrlGetFuncionario = '/rh/api/get/funcionario/'; // Corrigido prefixo /rh/
    const apiUrlEditFuncionario = '/rh/api/edit/funcionario/'; // Corrigido prefixo /rh/
    const apiUrlDeactivateFuncionario = '/rh/api/deactivate/funcionario/'; // Nova API
    const apiUrlGetComissao = '/rh/api/get/comissao/'; // API para buscar regras de comissão
    const placeholderImg = '/static/img/profile_placeholder.png'; // Corrigido caminho da imagem

    // --- Elementos do DOM ---
    const $formFiltros = $('#form-filtros');
    const $filtroApelido = $('#filtro_apelido');
    const $filtroNome = $('#filtro_nome');
    const $filtroFuncao = $('#filtro_funcao');
    const $filtroStatus = $('#filtro_status');
    const $btnFiltrar = $('#btn-filtrar');
    const $tabelaResultadosBody = $('#tabelaResultadosBody');
    const $cardResultados = $('#card-resultados');
    const $cardEdicao = $('#card-edicao');
    const $formEdicao = $('#form-edicao');
    const $nomeFuncionarioEdicao = $('#nome-funcionario-edicao');
    const $btnCancelarEdicao = $('#btn-cancelar-edicao');
    const $fotoAtualPreview = $('#foto-atual-preview');
    const $fotoAtualNome = $('#foto-atual-nome');
    const $editFotoInput = $('#edit_foto');
    const $messageContainer = $('<div id="message-container" class="my-3"></div>');
    $cardResultados.before($messageContainer); // Insere container de msg antes dos resultados

    // Selects do Form Edição
    const $editEmpresaSelect = $('#edit_empresa');
    const $editLojaSelect = $('#edit_loja');
    const $editDepartamentoSelect = $('#edit_departamento');
    const $editSetorSelect = $('#edit_setor');
    const $editCargoSelect = $('#edit_cargo');
    const $editHorarioSelect = $('#edit_horario');
    const $editEquipeSelect = $('#edit_equipe');
    const $editRegrasComissionamentoContainer = $('#edit_regras_comissionamento_container'); // Novo Container

    // Novos elementos para a seção de arquivos
    const $containerNovosArquivos = $('#container-novos-arquivos');
    const $btnAdicionarMaisArquivos = $('#btn-adicionar-mais-arquivos');
    const $listaArquivosExistentes = $('#lista-arquivos-existentes');
    const $semArquivosMsg = $('#sem-arquivos-msg');

    // Contador para IDs únicos de formulários de arquivo
    let contadorFormArquivos = 1;

    // Arrays para controlar arquivos
    let arquivosParaEnviar = [];
    let arquivosExistentes = [];

    // --- Cache de Dados ---
    let todosFuncionarios = [];
    let todosEmpresas = [];
    let todasLojas = [];
    let todosDepartamentos = [];
    let todosSetores = [];
    let todosCargos = [];
    let todosHorarios = [];
    let todasEquipes = [];
    let todasRegrasComissao = []; // Cache para regras de comissão

    // --- Funções Auxiliares ---

    // Obtém o token CSRF
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

    // Exibe mensagens
    function showMessage(type, message, container = $messageContainer) {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        
        // Limpa timeout anterior se houver
        if (container.data('messageTimeout')) {
            clearTimeout(container.data('messageTimeout'));
        }
        
        container.html(`<div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                            ${message}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                         </div>`);
        
        // Auto-dismiss after 10 seconds (10000 ms)
        const timeoutId = setTimeout(() => {
            container.find('.alert').remove();
        }, 10000);
        
        // Armazena o ID do timeout no container
        container.data('messageTimeout', timeoutId);
    }

    // Limpa e reseta um select
    function resetSelect($select, defaultOptionText, disabled = true) {
        $select.empty().append(`<option value="">${defaultOptionText}</option>`).prop('disabled', disabled);
    }

    // Função genérica para popular um select
    function popularSelect($select, data, valueField, textField, defaultOptionText, selectedValue = null) {
        $select.empty().append(`<option value="">${defaultOptionText}</option>`);
        let hasOptions = false;
        // Converte selectedValue para string para comparação consistente, se não for nulo
        const selectedValueStr = selectedValue !== null ? String(selectedValue) : null;

        data.forEach(item => {
            const value = item[valueField];
            // Obtém o texto. Se textField for uma função, chama-a.
            const text = typeof textField === 'function' ? textField(item) : item[textField];
            const $option = $('<option></option>').val(value).text(text);

            // Compara os valores como strings (ou ambos null)
            if (selectedValueStr !== null && String(value) === selectedValueStr) {
                $option.prop('selected', true);
            }
            $select.append($option);
            hasOptions = true;
        });
        $select.prop('disabled', !hasOptions);
    }

    // Formato de tamanho de arquivo legível
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Truncar texto longo
    function truncateText(text, maxLength = 40) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    // Formatar data para exibição
    function formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'});
    }

    // Obter a extensão do arquivo
    function getFileExtension(filename) {
        return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2).toLowerCase();
    }

    // Obter ícone baseado na extensão do arquivo
    function getFileIcon(filename) {
        const ext = getFileExtension(filename);
        
        // Mapeamento de extensões para ícones do BoxIcons
        const iconMap = {
            'pdf': 'bxs-file-pdf',
            'doc': 'bxs-file-doc',
            'docx': 'bxs-file-doc',
            'xls': 'bxs-file-xls',
            'xlsx': 'bxs-file-xls',
            'ppt': 'bxs-file-ppt',
            'pptx': 'bxs-file-ppt',
            'jpg': 'bxs-file-image',
            'jpeg': 'bxs-file-image',
            'png': 'bxs-file-image',
            'gif': 'bxs-file-gif',
            'zip': 'bxs-file-archive',
            'rar': 'bxs-file-archive',
            'txt': 'bxs-file-txt'
        };
        
        return iconMap[ext] || 'bxs-file';
    }

    // Nova função para popular checkboxes
    function popularCheckboxes($container, data, name, valueField, textField, checkedValues = []) {
        $container.empty(); // Limpa o container (remove "Carregando...")
        let hasOptions = false;
        // Converte checkedValues para um array de strings para comparação consistente
        const checkedValuesStr = Array.isArray(checkedValues) ? checkedValues.map(String) : [];

        if (data.length === 0) {
             $container.html('<p class="text-muted small m-0">Nenhuma regra de comissionamento encontrada.</p>');
             return;
        }

        data.forEach(item => {
            const value = item[valueField];
            const text = typeof textField === 'function' ? textField(item) : item[textField];
            const id = `${name}-${value}`;
            const isChecked = checkedValuesStr.includes(String(value));

            const $checkboxDiv = $(`
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="${name}" value="${value}" id="${id}" ${isChecked ? 'checked' : ''}>
                    <label class="form-check-label" for="${id}">
                        ${text}
                    </label>
                </div>
            `);
            $container.append($checkboxDiv);
            hasOptions = true;
        });
    }

    // --- Funções de Carregamento e Filtragem ---

    function carregarDadosIniciais() {
        console.log("Carregando dados iniciais...");
        $tabelaResultadosBody.html('<tr><td colspan="6" class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Carregando dados...</td></tr>');

        Promise.all([
            $.getJSON(apiUrlGeral),
            $.getJSON(apiUrlFuncionarios),
            $.getJSON(apiUrlGetComissao) // Adiciona a chamada para buscar regras de comissão
        ]).then(([dataGeral, dataFuncionarios, dataComissao]) => {
            console.log("Dados gerais carregados:", dataGeral);
            console.log("Funcionários carregados:", dataFuncionarios);
            console.log("Regras de comissão carregadas:", dataComissao);

            // Armazena dados gerais em cache
            todosEmpresas = dataGeral.empresas || [];
            todasLojas = dataGeral.lojas || [];
            todosDepartamentos = dataGeral.departamentos || [];
            todosSetores = dataGeral.setores || [];
            todosCargos = dataGeral.cargos || [];
            todosHorarios = dataGeral.horarios || [];
            todasEquipes = dataGeral.equipes || [];
            todasRegrasComissao = dataComissao.regras_comissionamento || []; // Armazena regras no cache

            // Armazena funcionários em cache
            todosFuncionarios = dataFuncionarios || [];

            // Popula selects estáticos no formulário de edição (exceto comissão)
            popularSelect($editEmpresaSelect, todosEmpresas, 'id', 'nome', '--- Selecione ---');
            popularSelect($editHorarioSelect, todosHorarios, 'id', 'display_text', '--- Selecione ---');
            popularSelect($editEquipeSelect, todasEquipes, 'id', 'nome', '--- Nenhuma ---');

            // Popula o select de filtro de Cargo (Função no HTML)
            popularSelect($filtroFuncao, todosCargos, 'id', 'nome_com_hierarquia', 'Todas');

            // Popula a tabela inicial (sem filtros)
            filtrarEAtualizarTabela();

            $cardResultados.show();

        }).catch(error => {
            console.error("Erro ao carregar dados iniciais:", error);
            showMessage('error', 'Erro ao carregar dados necessários. Tente recarregar a página.');
            $tabelaResultadosBody.html('<tr><td colspan="6" class="text-center text-danger">Falha ao carregar dados.</td></tr>');
        });
    }

    function filtrarEAtualizarTabela() {
        const filtroApelidoVal = $filtroApelido.val().trim().toLowerCase();
        const filtroNomeVal = $filtroNome.val().trim().toLowerCase();
        const filtroCargoId = $filtroFuncao.val();
        const filtroStatusVal = $filtroStatus.val();

        const funcionariosFiltrados = todosFuncionarios.filter(f => {
            const apelidoMatch = !filtroApelidoVal || (f.apelido && f.apelido.toLowerCase().includes(filtroApelidoVal));
            const nomeMatch = !filtroNomeVal || (f.nome_completo && f.nome_completo.toLowerCase().includes(filtroNomeVal));
            const cargoMatch = !filtroCargoId || (f.cargo_id && f.cargo_id == filtroCargoId);
            const statusMatch = !filtroStatusVal || (filtroStatusVal === '1' && f.status) || (filtroStatusVal === '0' && !f.status);

            return apelidoMatch && nomeMatch && cargoMatch && statusMatch;
        });

        popularTabelaResultados(funcionariosFiltrados);
    }

    function popularTabelaResultados(funcionarios) {
        $tabelaResultadosBody.empty(); // Limpa a tabela

        if (funcionarios.length === 0) {
            $tabelaResultadosBody.html('<tr><td colspan="6" class="text-center text-muted">Nenhum funcionário encontrado com os filtros aplicados.</td></tr>');
            return;
        }

        const csrfToken = getCsrfToken(); // Obter o token CSRF uma vez para reutilizar

        funcionarios.forEach(f => {
            const statusBadge = f.status ? '<span class="badge bg-success">Ativo</span>' : '<span class="badge bg-danger">Inativo</span>';
            const row = `
                <tr>
                    <td>${f.apelido || '-'}</td>
                    <td>${f.nome_completo}</td>
                    <td>${f.cpf || '-'}</td>
                    <td>${f.cargo_nome || '-'} (${f.departamento_nome || '-'})</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-sm btn-info btn-editar" data-id="${f.id}" title="Editar">
                            <i class='bx bx-edit'></i>
                        </button>
                    </td>
                </tr>
            `;
            $tabelaResultadosBody.append(row);
        });
    }

    // --- Funções de Edição ---

    function handleEditarClick(funcionarioId) {
        console.log(`Editando funcionário ID: ${funcionarioId}`);
        showMessage('info', 'Carregando dados do funcionário...'); // Feedback visual
        $cardEdicao.hide(); // Esconde enquanto carrega

        $.getJSON(`${apiUrlGetFuncionario}${funcionarioId}/`)
            .done(function(data) {
                console.log("Dados do funcionário recebidos:", data);
                popularFormEdicao(data);
                $messageContainer.empty(); // Limpa msg de carregamento
                $('html, body').animate({ // Rola a página até o card de edição
                    scrollTop: $cardEdicao.offset().top - 20 // -20 para um pequeno espaço acima
                }, 500);
            })
            .fail(function(jqXHR, textStatus, errorThrown) {
                console.error("Erro ao buscar dados do funcionário:", textStatus, errorThrown, jqXHR.responseText);
                showMessage('error', `Erro ao buscar dados do funcionário: ${jqXHR.responseJSON?.error || errorThrown}`);
            });
    }

    function popularFormEdicao(data) {
        $formEdicao[0].reset(); // Limpa o form antes de popular
        $formEdicao.find('.is-invalid').removeClass('is-invalid'); // Limpa validação anterior
        $formEdicao.find('.is-valid').removeClass('is-valid');

        // Popula campos simples
        $('#edit_funcionario_id').val(data.id);
        $nomeFuncionarioEdicao.text(data.nome_completo || data.apelido || 'ID: ' + data.id);
        $('#edit_apelido').val(data.apelido);
        $('#edit_nome_completo').val(data.nome_completo);
        $('#edit_cpf').val(data.cpf);
        $('#edit_data_nascimento').val(data.data_nascimento); // Formato YYYY-MM-DD
        $('#edit_genero').val(data.genero);
        $('#edit_estado_civil').val(data.estado_civil);
        $('#edit_cep').val(data.cep);
        $('#edit_endereco').val(data.endereco);
        $('#edit_bairro').val(data.bairro);
        $('#edit_cidade').val(data.cidade);
        $('#edit_estado').val(data.estado);
        $('#edit_celular1').val(data.celular1);
        $('#edit_celular2').val(data.celular2);
        $('#edit_matricula').val(data.matricula);
        $('#edit_pis').val(data.pis);
        $('#edit_data_admissao').val(data.data_admissao); // Formato YYYY-MM-DD
        $('#edit_data_demissao').val(data.data_demissao); // Formato YYYY-MM-DD
        $('#edit_nome_mae').val(data.nome_mae);
        $('#edit_nome_pai').val(data.nome_pai);
        $('#edit_nacionalidade').val(data.nacionalidade);
        $('#edit_naturalidade').val(data.naturalidade);
        $('#edit_status').prop('checked', data.status);

        // Popula selects estáticos
        $editHorarioSelect.val(data.horario_id || '');
        $editEquipeSelect.val(data.equipe_id || '');

        // Popula e marca os checkboxes de regras de comissionamento
        popularCheckboxes($editRegrasComissionamentoContainer, todasRegrasComissao, 'comissionamento_ids[]', 'id', 'titulo', data.regras_comissionamento_ids || []);

        // Popula a foto
        $editFotoInput.val(''); // Limpa seleção de arquivo anterior
        if (data.foto_url) {
            $fotoAtualPreview.attr('src', data.foto_url);
            $fotoAtualNome.text(data.foto_nome || 'Arquivo existente');
        } else {
            $fotoAtualPreview.attr('src', placeholderImg);
            $fotoAtualNome.text('Nenhuma foto cadastrada');
        }

        // 1. Define valor da Empresa
        $editEmpresaSelect.val(data.empresa_id || '');

        // 2. Trigger para carregar dependentes da Empresa
        $editEmpresaSelect.trigger('editFormEmpresaChange');

        // 3. Espera e define valores dos dependentes
        setTimeout(() => {
            $editLojaSelect.val(data.loja_id || '');
            $editDepartamentoSelect.val(data.departamento_id || '');
            $editCargoSelect.val(data.cargo_id || '');

            if ($editDepartamentoSelect.val()) {
                $editDepartamentoSelect.trigger('editFormDepartamentoChange');
                setTimeout(() => {
                    $editSetorSelect.val(data.setor_id || '');
                    $cardEdicao.slideDown();
                }, 100);
            } else {
                 $cardEdicao.slideDown();
            }
        }, 250);

        // Carrega arquivos do funcionário
        if (data.arquivos && Array.isArray(data.arquivos)) {
            carregarArquivosExistentes(data.arquivos);
        } else {
            carregarArquivosExistentes([]);
        }

        // Limpa novos arquivos
        $containerNovosArquivos.empty();
        arquivosParaEnviar = [];
    }

    // Popula Lojas no form de edição
    function popularEditLojas(empresaId, selectedLojaId = null) {
        resetSelect($editLojaSelect, '--- Carregando Lojas ---', false);
        if (!empresaId) {
            resetSelect($editLojaSelect, '--- Selecione a Empresa Primeiro ---', true);
            return;
        }
        const lojasFiltradas = todasLojas.filter(l => l.empresa_id == empresaId);
        popularSelect($editLojaSelect, lojasFiltradas, 'id', 'nome', '--- Selecione a Loja (Opcional) ---', selectedLojaId);
    }

    // Popula Departamentos e Cargos no form de edição
    function popularEditDepartamentosCargos(empresaId, selectedDepartamentoId = null, selectedCargoId = null) {
        resetSelect($editDepartamentoSelect, '--- Carregando Departamentos ---', false);
        resetSelect($editCargoSelect, '--- Carregando Cargos ---', false);
        resetSelect($editSetorSelect, '--- Selecione o Departamento ---', true);

        if (!empresaId) {
            resetSelect($editDepartamentoSelect, '--- Selecione a Empresa ---', true);
            resetSelect($editCargoSelect, '--- Selecione a Empresa ---', true);
            return;
        }

        const deptsFiltrados = todosDepartamentos.filter(d => d.empresa_id == empresaId);
        popularSelect($editDepartamentoSelect, deptsFiltrados, 'id', 'nome', '--- Selecione o Departamento ---', selectedDepartamentoId);

        const cargosFiltrados = todosCargos.filter(c => c.empresa_id == empresaId);
        popularSelect($editCargoSelect, cargosFiltrados, 'id', 'nome_com_hierarquia', '--- Selecione o Cargo ---', selectedCargoId);

        // Se um departamento foi pré-selecionado, dispara o change dele também para carregar setores
         // O setor será pré-selecionado pelo trigger que é disparado em popularFormEdicao
         if (selectedDepartamentoId) {
             setTimeout(() => {
                 $editDepartamentoSelect.trigger('editFormDepartamentoChange');
             }, 50); // Delay menor, pois depende apenas do cache
         }
    }

    // Popula Setores no form de edição
    function popularEditSetores(departamentoId, selectedSetorId = null) {
        resetSelect($editSetorSelect, '--- Carregando Setores ---', false);
        if (!departamentoId) {
            resetSelect($editSetorSelect, '--- Selecione o Departamento ---', true);
            return;
        }
        const setoresFiltrados = todosSetores.filter(s => s.departamento_id == departamentoId);
        popularSelect($editSetorSelect, setoresFiltrados, 'id', 'nome', '--- Selecione o Setor ---', selectedSetorId);
    }

    // Submete o formulário de edição
    function submeterFormEdicao(event) {
        event.preventDefault();
        const $submitButton = $formEdicao.find('button[type="submit"]');
        const submitButtonText = $submitButton.html();

        // Validação HTML5 básica
        if (!$formEdicao[0].checkValidity()) {
            $formEdicao[0].reportValidity();
            return;
        }

        // Criar FormData com o formulário completo
        const formData = new FormData($formEdicao[0]);

        // Limpa quaisquer valores antigos de comissionamento do FormData
        formData.delete('comissionamento_ids[]');

        // Adiciona os IDs dos checkboxes de comissionamento marcados
        $editRegrasComissionamentoContainer.find('input[type="checkbox"]:checked').each(function() {
            formData.append('comissionamento_ids[]', $(this).val());
        });

        // Se o input de file estiver vazio, remove a chave 'foto' para não sobrescrever com vazio
        if ($editFotoInput[0].files.length === 0) {
            formData.delete('foto');
        }

        // Validação dos campos de arquivo
        let camposDeArquivoValidos = true;
        $containerNovosArquivos.find('.arquivo-form').each(function(index) {
            const $form = $(this);
            const temTitulo = $form.find('.input-arquivo-titulo').val().trim() !== '';
            const temArquivo = $form.find('.input-arquivo-file')[0].files.length > 0;
            if ((temTitulo && !temArquivo) || (!temTitulo && temArquivo)) {
                camposDeArquivoValidos = false;
                if (!temTitulo) $form.find('.input-arquivo-titulo').addClass('is-invalid');
                if (!temArquivo) $form.find('.input-arquivo-file').addClass('is-invalid');
            }
        });
        if (!camposDeArquivoValidos) {
            showMessage('error', 'Preencha todos os campos obrigatórios dos arquivos ou remova os formulários incompletos.');
            return;
        }

        console.log("Enviando dados de edição...");
        for (let [key, value] of formData.entries()) {
            console.log(`${key}: ${value}`);
        }

        $submitButton.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Salvando...');

        $.ajax({
            url: apiUrlEditFuncionario,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            success: function(response) {
                console.log("Edição bem-sucedida:", response);
                showMessage('success', response.message || 'Funcionário atualizado com sucesso!');
                $cardEdicao.slideUp();
                carregarDadosIniciais();
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Erro ao editar funcionário:", textStatus, errorThrown, jqXHR.responseText);
                let errorMessage = 'Erro ao salvar alterações.';
                if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
                    errorMessage = jqXHR.responseJSON.error;
                    if (jqXHR.responseJSON.details) {
                         let details = Object.entries(jqXHR.responseJSON.details)
                             .map(([field, errors]) => `<li>${field}: ${errors.join(', ')}</li>`)
                             .join('');
                         errorMessage += `<br><ul class="text-start small mt-2">${details}</ul>`;
                    }
                } else {
                    errorMessage += ` (${errorThrown || textStatus})`;
                }
                showMessage('error', errorMessage);
            },
            complete: function() {
                $submitButton.prop('disabled', false).html(submitButtonText);
            }
        });
    }

    function handleCancelarClick() {
        $cardEdicao.slideUp();
    }

    // --- Event Listeners ---

    // Filtragem em tempo real nos inputs de texto
    $filtroApelido.on('keyup input', filtrarEAtualizarTabela);
    $filtroNome.on('keyup input', filtrarEAtualizarTabela);

    // Filtragem ao mudar selects ou clicar no botão
    $filtroFuncao.on('change', filtrarEAtualizarTabela);
    $filtroStatus.on('change', filtrarEAtualizarTabela);
    $btnFiltrar.on('click', filtrarEAtualizarTabela);

    // Prevenir submit do form de filtros (ele só atualiza a tabela via JS)
    $formFiltros.submit(function(e) { e.preventDefault(); });

    // Delegação de evento para o botão Editar na tabela
    $tabelaResultadosBody.on('click', '.btn-editar', function() {
        const funcionarioId = $(this).data('id');
        handleEditarClick(funcionarioId);
    });

    // Listeners para selects dependentes NO FORMULÁRIO DE EDIÇÃO
    // Removidos parâmetros de pré-seleção, a seleção é feita diretamente em popularFormEdicao
    $editEmpresaSelect.on('change editFormEmpresaChange', function(event) {
        const empresaId = $(this).val();
        console.log("Event: Empresa Changed/Triggered. Loading dependents for Empresa ID:", empresaId);
        popularEditLojas(empresaId); // Popula Loja SEM pré-seleção aqui
        popularEditDepartamentosCargos(empresaId); // Popula Depto e Cargo SEM pré-seleção aqui
        resetSelect($editSetorSelect, '--- Selecione o Departamento ---', true); // Reseta setor ao mudar empresa
    });

    $editDepartamentoSelect.on('change editFormDepartamentoChange', function(event) {
        const departamentoId = $(this).val();
         console.log("Event: Departamento Changed/Triggered. Loading Setores for Depto ID:", departamentoId);
        popularEditSetores(departamentoId); // Popula Setor SEM pré-seleção aqui
    });

    // Submissão do formulário de edição
    $formEdicao.submit(submeterFormEdicao);

    // Botão Cancelar Edição
    $btnCancelarEdicao.click(handleCancelarClick);

    // Listeners para a seção de arquivos
    $btnAdicionarMaisArquivos.on('click', adicionarFormularioArquivo);
    
    // Remover validação quando o usuário corrige o campo
    $(document).on('input', '.input-arquivo-titulo, .input-arquivo-file', function() {
        $(this).removeClass('is-invalid');
    });

    // --- Inicialização ---
    carregarDadosIniciais();
    $cardEdicao.hide(); // Garante que o card de edição começa oculto
    $cardResultados.hide(); // Esconde resultados até carregar dados

    // Aplica máscaras (se usar jQuery Mask Plugin)
    if ($.fn.mask) {
        $('#edit_cpf').mask('000.000.000-00');
        $('#edit_cep').mask('00000-000');
        $('#edit_celular1').mask('(00) 00000-0000');
    } else {
        console.warn('jQuery Mask Plugin não encontrado. Máscaras não aplicadas.');
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

    // --- Funções para gerenciamento de arquivos ---

    // Carregar arquivos existentes do funcionário
    function carregarArquivosExistentes(arquivos) {
        $listaArquivosExistentes.empty();
        
        if (!arquivos || arquivos.length === 0) {
            $semArquivosMsg.show();
            return;
        }
        
        $semArquivosMsg.hide();
        
        arquivos.forEach(arquivo => {
            const iconClass = getFileIcon(arquivo.nome_arquivo);
            const $item = $(`
              <div class="arquivo-item">
                <div class="arquivo-info">
                  <div class="arquivo-titulo">${arquivo.titulo}</div>
                  <a href="${arquivo.download_url}" class="arquivo-nome-link" download>
                    <i class='bx ${iconClass} me-1'></i>
                    ${arquivo.nome_arquivo}
                  </a>
                  ${arquivo.descricao ? `<div class="arquivo-descricao">${arquivo.descricao}</div>` : ''}
                  <div class="arquivo-data">Enviado em: ${formatDate(arquivo.data_upload)}</div>
                </div>
              </div>
            `);
            $listaArquivosExistentes.append($item);
        });
    }

    // Adicionar novo formulário de arquivo
    function adicionarFormularioArquivo() {
        const novoId = contadorFormArquivos++;
        
        const $novoFormulario = $(`
            <div class="arquivo-form mb-3" id="arquivo-form-${novoId}">
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Título do Arquivo *</label>
                        <input type="text" class="form-control input-arquivo-titulo" name="arquivo_titulos[]" placeholder="Título do arquivo (obrigatório)" required>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Descrição</label>
                        <input type="text" class="form-control input-arquivo-descricao" name="arquivo_descricoes[]" placeholder="Descrição (opcional)">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Arquivo *</label>
                        <div class="input-group">
                            <input type="file" class="form-control input-arquivo-file" name="arquivo_files[]" required>
                            <button type="button" class="btn btn-danger btn-remover-arquivo" data-form-id="${novoId}">
                                <i class='bx bx-trash'></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        // Adicionar evento para o botão remover
        $novoFormulario.find('.btn-remover-arquivo').on('click', function() {
            const formId = $(this).data('form-id');
            $(`#arquivo-form-${formId}`).remove();
        });
        
        $containerNovosArquivos.append($novoFormulario);
        
        // Dar foco ao campo de título do novo formulário
        $novoFormulario.find('.input-arquivo-titulo').focus();
    }
});
