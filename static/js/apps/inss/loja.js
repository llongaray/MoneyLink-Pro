document.addEventListener('DOMContentLoaded', function() {
    // --- INICIALIZAÇÃO DE MODAIS ---
    // Verificar se estamos usando Bootstrap 5
    if (typeof bootstrap !== 'undefined') {
        // Inicializar modais do Bootstrap
        const modais = document.querySelectorAll('.modal-sec');
        modais.forEach(modalEl => {
            // Impedir fechamento ao clicar fora (opcional)
            const modalOptions = {
                backdrop: 'static',
                keyboard: false
            };
            new bootstrap.Modal(modalEl, modalOptions);
        });
        
        console.log('Modais inicializados com Bootstrap');
    } else {
        // Inicialização manual para sistemas sem Bootstrap
        console.log('Bootstrap não detectado, usando inicialização manual para modais');
        
        // Adicionar eventos de fechamento ao clicar fora (opcional)
        document.querySelectorAll('.modal-sec').forEach(modal => {
            modal.addEventListener('click', function(e) {
                if (e.target === this) {
                    window.fecharModal('#' + this.id);
                }
            });
        });
    }

    // --- MÁSCARAS (Exemplo - Adapte conforme necessário) ---
    $('#cpf_cliente_rua_inline').mask('000.000.000-00');
    $('#numero_cliente_rua_inline').mask('(00) 0 0000-0000');
    // A máscara para .money será aplicada dinamicamente abaixo

    // --- FUNÇÃO AUXILIAR PARA FORMATAR NÚMERO DE TELEFONE ---
    function formatarNumeroTelefone(numero) {
        if (!numero) return ''; // Retorna vazio se nulo ou vazio
        const numeroLimpo = numero.toString().replace(/\D/g, ''); // Remove não dígitos
        const tamanho = numeroLimpo.length;

        if (tamanho === 11) {
            // Formato (00) 0 0000-0000
            return `(${numeroLimpo.substring(0, 2)}) ${numeroLimpo.substring(2, 3)} ${numeroLimpo.substring(3, 7)}-${numeroLimpo.substring(7)}`;
        } else if (tamanho === 10) {
            // Formato (00) 0000-0000
            return `(${numeroLimpo.substring(0, 2)}) ${numeroLimpo.substring(2, 6)}-${numeroLimpo.substring(6)}`;
        } else {
            return numero; // Retorna o número original se não tiver 10 ou 11 dígitos
        }
    }

    // --- LÓGICA PARA ADICIONAR/REMOVER PRODUTOS - FORMULÁRIO INLINE ---
    const tabulacaoSelect = document.getElementById('tabulacao_vendedor_rua_inline');
    const addProdutoBtnContainer = document.getElementById('addProdutoBtnContainerInline');
    const btnAddProduto = document.getElementById('btnAddProdutoInline');
    const produtosContainer = document.getElementById('produtosContainerInline');
    const produtoTemplate = document.getElementById('produtoTemplateInline');
    let produtoIndex = 0; // Contador para indexar os produtos

    // --- LÓGICA PARA ADICIONAR/REMOVER PRODUTOS - MODAL EDIÇÃO ---
    const tabulacaoEdicaoSelect = document.getElementById('tabulacaoVendedorEdicao');
    const addProdutoBtnContainerEdicao = document.getElementById('addProdutoBtnContainerEdicao');
    const btnAddProdutoEdicao = document.getElementById('btnAddProdutoEdicao');
    const produtosContainerEdicao = document.getElementById('produtosContainerEdicao');
    const produtoTemplateEdicao = document.getElementById('produtoTemplateEdicao');
    let produtoEdicaoIndex = 0; // Contador para indexar os produtos no modal de edição

    // Função para aplicar máscara de dinheiro a um elemento específico
    function aplicarMascaraDinheiro(elemento) {
        $(elemento).mask('#.##0,00', { reverse: true });
    }

    // Função para adicionar um novo bloco de produto (formulário inline)
    function adicionarProduto() {
        console.log('[CLIENTE RUA] Adicionando novo produto, índice:', produtoIndex);
        const clone = produtoTemplate.content.cloneNode(true);
        const blocoProduto = clone.querySelector('.produto-bloco');

        // Atualiza IDs e Names com o índice correto
        blocoProduto.innerHTML = blocoProduto.innerHTML.replace(/__INDEX__/g, produtoIndex);

        // Adiciona evento de remoção ao botão do novo bloco
        const btnRemove = blocoProduto.querySelector('.btn-remove-produto');
        btnRemove.addEventListener('click', function() {
            console.log('[CLIENTE RUA] Removendo produto');
            blocoProduto.remove();
            // Opcional: reajustar índices se necessário após remover um item do meio
            // (para simplificação, não faremos isso aqui inicialmente)
            verificarVisibilidadeBotaoAdd(); // Verifica se o botão add ainda deve aparecer
        });

        // Aplica máscara de dinheiro ao campo valor_tac do novo bloco
        const valorTacInput = blocoProduto.querySelector('.money');
        if (valorTacInput) {
            aplicarMascaraDinheiro(valorTacInput);
        }
        
        // Preenche o select de produtos
        const produtoSelect = blocoProduto.querySelector(`[name='produtos[${produtoIndex}][produto_id]']`);
        if (produtoSelect) {
            preencherSelectProdutos($(produtoSelect));
        }

        produtosContainer.appendChild(blocoProduto);
        produtoIndex++;
        verificarVisibilidadeBotaoAdd();
        console.log('[CLIENTE RUA] Produto adicionado, novo contador de produtos:', produtoIndex);
    }

    // Função para adicionar um novo bloco de produto no modal de edição
    function adicionarProdutoEdicao() {
        const clone = produtoTemplateEdicao.content.cloneNode(true);
        const blocoProduto = clone.querySelector('.produto-bloco');

        // Atualiza IDs e Names com o índice correto
        blocoProduto.innerHTML = blocoProduto.innerHTML.replace(/__INDEX__/g, produtoEdicaoIndex);

        // Adiciona evento de remoção ao botão do novo bloco
        const btnRemove = blocoProduto.querySelector('.btn-remove-produto');
        btnRemove.addEventListener('click', function() {
            blocoProduto.remove();
            // Opcional: reajustar índices se necessário após remover um item do meio
            verificarVisibilidadeBotaoAddEdicao(); // Verifica se o botão add ainda deve aparecer
        });

        // Aplica máscara de dinheiro ao campo valor_tac do novo bloco
        const valorTacInput = blocoProduto.querySelector('.money');
        if (valorTacInput) {
            aplicarMascaraDinheiro(valorTacInput);
        }
        
        // Preenche o select de produtos
        const produtoSelect = blocoProduto.querySelector(`[name='produtos[${produtoEdicaoIndex}][produto_id]']`);
        if (produtoSelect) {
            preencherSelectProdutos($(produtoSelect));
        }

        produtosContainerEdicao.appendChild(blocoProduto);
        produtoEdicaoIndex++;
        verificarVisibilidadeBotaoAddEdicao();
    }

    // Função para remover todos os produtos (formulário inline)
    function removerTodosProdutos() {
        produtosContainer.innerHTML = '';
        produtoIndex = 0; // Reseta o índice
        addProdutoBtnContainer.style.display = 'none'; // Esconde o botão de adicionar
    }

    // Função para remover todos os produtos no modal de edição
    function removerTodosProdutosEdicao() {
        produtosContainerEdicao.innerHTML = '';
        produtoEdicaoIndex = 0; // Reseta o índice
        // Não escondemos o botão aqui, pois isso é tratado no handler de tabulação
    }

    // Função para verificar e ajustar a visibilidade do botão "Adicionar Produto" (formulário inline)
    function verificarVisibilidadeBotaoAdd() {
         if (tabulacaoSelect && tabulacaoSelect.value === 'NEGOCIO FECHADO') {
             addProdutoBtnContainer.style.display = 'block';
         } else {
             addProdutoBtnContainer.style.display = 'none';
         }
    }

    // Função para verificar e ajustar a visibilidade do botão "Adicionar Produto" (modal edição)
    function verificarVisibilidadeBotaoAddEdicao() {
         if (tabulacaoEdicaoSelect && tabulacaoEdicaoSelect.value === 'NEGOCIO FECHADO') {
             addProdutoBtnContainerEdicao.style.display = 'block';
         } else {
             addProdutoBtnContainerEdicao.style.display = 'none';
         }
    }

    // Event listener para a seleção da tabulação (formulário inline)
    window.handleTabulacaoVendedorInline = function() {
        if (tabulacaoSelect && tabulacaoSelect.value === 'NEGOCIO FECHADO') {
            addProdutoBtnContainer.style.display = 'block';
            // Adiciona o primeiro produto automaticamente se não houver nenhum
            if (produtosContainer.children.length === 0) {
                adicionarProduto();
            }
        } else {
            removerTodosProdutos(); // Remove produtos se não for "NEGOCIO FECHADO"
        }
    }

    /**
     * Handler para a alteração de tabulação do vendedor no modal de edição
     */
    function handleTabulacaoVendedorChange() {
        const tabulacaoValue = $(this).val();
        
        if (tabulacaoValue === 'NEGOCIO FECHADO') {
            $('#fechouNegocioContainerEdicao').slideDown();
            // Mostrar o botão para adicionar produtos
            addProdutoBtnContainerEdicao.style.display = 'block';
            
            // Adiciona o primeiro produto automaticamente se não houver nenhum
            if (produtosContainerEdicao && produtosContainerEdicao.children.length === 0) {
                adicionarProdutoEdicao();
            }
        } else {
            $('#fechouNegocioContainerEdicao').slideUp();
            // Remover todos os produtos se não for "NEGOCIO FECHADO"
            removerTodosProdutosEdicao();
        }
    }

    // Expor funções necessárias para o escopo global
    window.handleTabulacaoVendedorChange = handleTabulacaoVendedorChange;

    // Event listener para o botão "Adicionar Produto" (formulário inline)
    if(btnAddProduto) {
        btnAddProduto.addEventListener('click', adicionarProduto);
    }

    // Event listener para o botão "Adicionar Produto" no modal de edição
    if(btnAddProdutoEdicao) {
        btnAddProdutoEdicao.addEventListener('click', adicionarProdutoEdicao);
    }

    // --- VALIDAÇÃO CONDICIONAL (Simplificado - pode precisar de mais lógica) ---
    const formClienteRua = document.getElementById('formClienteRuaInline');
    if(formClienteRua) {
        formClienteRua.addEventListener('submit', function(event) {
            if (tabulacaoSelect.value === 'NEGOCIO FECHADO') {
                const produtos = produtosContainer.querySelectorAll('.produto-bloco');
                if (produtos.length === 0) {
                     alert('Se a tabulação for "NEGOCIO FECHADO", ao menos um produto deve ser adicionado.');
                     event.preventDefault(); // Impede o envio
                     return;
                }
                // Adicionar validação para campos obrigatórios dentro de cada produto, se necessário
                let formValido = true;
                produtos.forEach((produto, index) => {
                    // Exemplo: Tornar tipo_negociação obrigatório
                    const tipoNegInput = produto.querySelector(`[name='produtos[${index}][tipo_negociacao]']`);
                    if (tipoNegInput && !tipoNegInput.value) {
                        alert(`Por favor, preencha o Tipo de Negociação para o Produto ${index + 1}.`);
                        tipoNegInput.focus();
                        formValido = false;
                        return; // Sai do forEach
                    }
                    // Adicione mais validações aqui para outros campos...
                });

                if (!formValido) {
                    event.preventDefault(); // Impede o envio se a validação falhar
                }
            }
        });
    }


    // Inicializa o estado do botão ao carregar a página (caso o formulário já tenha um valor)
    verificarVisibilidadeBotaoAdd();
     // Define data de comparecimento padrão como hoje
     const dataComparecimentoInput = document.getElementById('data_comparecimento_rua_inline');
     if (dataComparecimentoInput && !dataComparecimentoInput.value) {
         const hoje = new Date().toISOString().split('T')[0];
         dataComparecimentoInput.value = hoje;
     }

    // --- FUNÇÃO PARA CARREGAR LOJAS E FUNCIONÁRIOS (Adaptada de agendamento.js) ---
    function carregarLojasEFuncionarios() {
        console.log("Carregando lojas, funcionários e produtos para o formulário de cliente rua..."); // Log específico

        $.ajax({
            url: '/inss/api/get/info-loja-funcionario/',
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log("Dados de lojas, funcionários e produtos recebidos (cliente rua):", response); // Log específico
                
                // Preenche o select de lojas do formulário inline
                const selectLojaInline = $('#loja_rua_inline');
                selectLojaInline.empty().append('<option value="">Selecione uma loja</option>');
                
                const lojasArray = Object.values(response.lojas || {});
                lojasArray.sort((a, b) => a.nome.localeCompare(b.nome));
                
                lojasArray.forEach(function(loja) {
                    selectLojaInline.append(`<option value="${loja.id}">${loja.nome}</option>`);
                });
                
                // Preenche o select de funcionários (vendedores) do formulário inline
                const selectFuncionarioInline = $('#vendedor_rua_inline');
                selectFuncionarioInline.empty().append('<option value="">Selecione um vendedor</option>');
                
                const funcionariosArray = Object.values(response.funcionarios || {});
                funcionariosArray.sort((a, b) => a.nome.localeCompare(b.nome));
                
                funcionariosArray.forEach(function(funcionario) {
                    selectFuncionarioInline.append(`<option value="${funcionario.id}">${funcionario.nome}</option>`);
                });
                
                // Armazena a lista de produtos para uso posterior
                window.listaProdutos = response.produtos || {};
                
                // Se existir o select de produto do modal
                const selectProdutoModal = $('#tipo_negociacao_rua');
                if (selectProdutoModal.length > 0) {
                    preencherSelectProdutos(selectProdutoModal);
                }
                
                console.log("Selects de lojas, vendedores e produtos preenchidos com sucesso.");
            },
            error: function(xhr, status, error) {
                console.error("Erro ao carregar lojas, funcionários e produtos (cliente rua):", status, error, xhr); // Log específico
                // Considerar adicionar uma mensagem de erro visual para o usuário, se apropriado
                // Por exemplo, desabilitar os selects ou mostrar um alerta
            }
        });
    }
    
    // Função auxiliar para preencher um select de produtos
    function preencherSelectProdutos(selectElement) {
        selectElement.empty().append('<option value="">Selecione um produto</option>');
        
        const produtosArray = Object.values(window.listaProdutos || {});
        produtosArray.sort((a, b) => a.nome.localeCompare(b.nome));
        
        produtosArray.forEach(function(produto) {
            selectElement.append(`<option value="${produto.id}">${produto.nome}</option>`);
        });
    }

    // --- FUNÇÕES PARA POPULAR TABELAS DE AGENDAMENTOS ---
    
    /**
     * Função para carregar e exibir agendamentos para hoje
     * @param {Object} filtros - Objeto com filtros opcionais (nomeCliente, cpfCliente, atendente, status)
     */
    function carregarAgendadosHoje(filtros = {}) {
        // Construir URL com filtros
        let url = '/inss/api/get/agendadosHoje/';
        const params = new URLSearchParams();
        
        if (filtros.nomeCliente) params.append('nomeCliente', filtros.nomeCliente);
        if (filtros.cpfCliente) params.append('cpfCliente', filtros.cpfCliente);
        if (filtros.atendente) params.append('atendente', filtros.atendente);
        if (filtros.status) params.append('status', filtros.status);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        console.log('Carregando agendados hoje - URL:', url);
        console.log('Filtros aplicados:', filtros);
        
        // Exibir indicador de carregamento
        $('#tabelaClientesHoje tbody').html('<tr><td colspan="8" class="text-center"><i class="bx bx-loader-alt bx-spin"></i> Carregando agendamentos...</td></tr>');
        
        // Fazer requisição AJAX
        $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log('Resposta da API agendadosHoje:', response);
                
                // Limpar tabela
                $('#tabelaClientesHoje tbody').empty();
                
                // Verificar se há agendamentos
                if (response.agendamentos && response.agendamentos.length > 0) {
                    console.log(`Encontrados ${response.agendamentos.length} agendamentos para hoje`);
                    
                    // Preencher tabela com os dados
                    $.each(response.agendamentos, function(index, agendamento) {
                        let statusClass = '';
                        let statusTexto = agendamento.status; // Novo nome de campo
                        if (statusTexto === 'Atendido') {
                            statusClass = 'text-success';
                        } else if (statusTexto === 'Aguardando') {
                            statusClass = 'text-warning';
                        }
                        
                        let row = `
                            <tr data-id="${agendamento.id_agendamento}">
                                <td>${agendamento.nome}</td>
                                <td>${agendamento.cpf}</td>
                                <td>${formatarNumeroTelefone(agendamento.numero)}</td>
                                <td>${agendamento.dia_agendado.split(' ')[0]}</td>
                                <td>${agendamento.atendente}</td>
                                <td class="${statusClass}">${statusTexto}</td>
                                <td>${agendamento.loja}</td>
                                <td>
                                    <button class="btn btn-sm btn-primary btn-atender" data-id="${agendamento.id_agendamento}" 
                                        ${statusTexto === 'Atendido' ? 'disabled' : ''}>
                                        <i class="bx bx-check-circle"></i> ${statusTexto === 'Atendido' ? 'Atendido' : 'Atender'}
                                    </button>
                                </td>
                            </tr>
                        `;
                        $('#tabelaClientesHoje tbody').append(row);
                    });
                    
                    // Atualizar contador
                    $('#totalAgendadosHoje').text(response.total);
                    
                    // Adicionar eventos aos botões de ação
                    $('.btn-atender').on('click', function() {
                        const agendamentoId = $(this).data('id');
                        abrirModalAtendimento(agendamentoId);
                    });
                } else {
                    console.log('Nenhum agendamento encontrado para hoje');
                    // Exibir mensagem se não houver agendamentos
                    $('#tabelaClientesHoje tbody').html('<tr><td colspan="8" class="text-center">Nenhum agendamento encontrado para hoje.</td></tr>');
                    $('#totalAgendadosHoje').text('0');
                }
            },
            error: function(xhr, status, error) {
                console.error('Erro ao carregar agendamentos:', error);
                console.error('Status:', status);
                console.error('Resposta do servidor:', xhr.responseText);
                $('#tabelaClientesHoje tbody').html(`<tr><td colspan="8" class="text-center text-danger">Erro ao carregar agendamentos: ${xhr.responseJSON?.error || error}</td></tr>`);
            }
        });
    }
    
    /**
     * Função para carregar e exibir agendamentos pendentes
     * @param {Object} filtros - Objeto com filtros opcionais (nomeCliente, cpfCliente, atendente, status)
     */
    function carregarAgendamentosPendentes(filtros = {}) {
        // Construir URL com filtros
        let url = '/inss/api/get/agendPendentes/';
        const params = new URLSearchParams();
        
        if (filtros.nomeCliente) params.append('nomeCliente', filtros.nomeCliente);
        if (filtros.cpfCliente) params.append('cpfCliente', filtros.cpfCliente);
        if (filtros.atendente) params.append('atendente', filtros.atendente);
        if (filtros.status) params.append('status', filtros.status);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        console.log('Carregando agendamentos pendentes - URL:', url);
        console.log('Filtros aplicados:', filtros);
        
        // Exibir indicador de carregamento
        $('#tabelaAgendamentosPendentes tbody').html('<tr><td colspan="8" class="text-center"><i class="bx bx-loader-alt bx-spin"></i> Carregando agendamentos pendentes...</td></tr>');
        
        // Fazer requisição AJAX
        $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log('Resposta da API agendPendentes:', response);
                
                // Limpar tabela
                $('#tabelaAgendamentosPendentes tbody').empty();
                
                // Verificar se há agendamentos
                if (response.agendamentos && response.agendamentos.length > 0) {
                    console.log(`Encontrados ${response.agendamentos.length} agendamentos pendentes`);
                    
                    // Preencher tabela com os dados
                    $.each(response.agendamentos, function(index, agendamento) {
                        let statusClass = '';
                        let statusTexto = agendamento.agendamento_tabulacao; // Usa a nova chave

                        // Lógica de classes de status (mantida, mas usando a nova chave)
                        if (statusTexto === 'CONFIRMADO') {
                            statusClass = 'text-success';
                        } else if (statusTexto === 'REAGENDADO') {
                            statusClass = 'text-warning';
                        } else if (statusTexto === 'CANCELADO' || statusTexto === 'DESISTIU') {
                            statusClass = 'text-danger';
                        } else {
                            statusClass = 'text-secondary'; // Outros (Pendente, Em Espera, etc)
                        }
                        
                        // Formata a data para DD/MM/YYYY
                        let diaFormatado = '';
                        if (agendamento.agendamento_dia) {
                            const partesData = agendamento.agendamento_dia.split('-'); // Divide YYYY-MM-DD
                            if (partesData.length === 3) {
                                diaFormatado = `${partesData[2]}/${partesData[1]}/${partesData[0]}`; // Monta DD/MM/YYYY
                            }
                        }

                        // Constrói a linha da tabela usando as novas chaves e a data formatada
                        let row = `
                            <tr data-id="${agendamento.agendamento_id}">
                                <td>${agendamento.cliente_agendamento_nome}</td>
                                <td>${agendamento.cliente_agendamento_cpf}</td>
                                <td>${formatarNumeroTelefone(agendamento.cliente_agendamento_numero)}</td>
                                <td>${diaFormatado}</td>
                                <td>${agendamento.agendamento_atendente_nome}</td>
                                <td class="${statusClass}">${statusTexto}</td>
                                <td>${agendamento.agendamento_loja_nome}</td>
                                <td>
                                    <button class="btn btn-sm btn-primary btn-atender" data-id="${agendamento.agendamento_id}">
                                        <i class="bx bx-check-circle"></i> Atender
                                    </button>
                                </td>
                            </tr>
                        `;
                        $('#tabelaAgendamentosPendentes tbody').append(row);
                    });
                    
                    // Atualizar contador
                    $('#totalAgendamentosPendentes').text(response.total);
                    
                    // Adicionar eventos aos botões de ação
                    $('#tabelaAgendamentosPendentes .btn-atender').off('click').on('click', function() {
                        const agendamentoId = $(this).data('id');
                        abrirModalAtendimento(agendamentoId);
                    });
                } else {
                    console.log('Nenhum agendamento pendente encontrado');
                    // Exibir mensagem se não houver agendamentos
                    $('#tabelaAgendamentosPendentes tbody').html('<tr><td colspan="8" class="text-center">Nenhum agendamento pendente encontrado.</td></tr>');
                    $('#totalAgendamentosPendentes').text('0');
                }
            },
            error: function(xhr, status, error) {
                console.error('Erro ao carregar agendamentos pendentes:', error);
                console.error('Status:', status);
                console.error('Resposta do servidor:', xhr.responseText);
                $('#tabelaAgendamentosPendentes tbody').html(`<tr><td colspan="8" class="text-center text-danger">Erro ao carregar agendamentos pendentes: ${xhr.responseJSON?.error || error}</td></tr>`);
            }
        });
    }
    
    /**
     * Função para abrir o modal de atendimento e carregar os dados do agendamento/cliente
     * @param {number} agendamentoId - ID do agendamento a ser exibido no modal
     */
    function abrirModalAtendimento(agendamentoId) {
        if (!agendamentoId) {
            console.error("ID do agendamento não fornecido para abrir o modal");
            return;
        }
        
        console.log(`Abrindo modal de atendimento para o agendamento ID: ${agendamentoId}`);
        
        // Limpar qualquer conteúdo de erro anterior
        $('#modalEdicaoCliente .alert').remove();
        
        // Armazenar o HTML original do formulário - vamos escondê-lo durante o carregamento
        const $formOriginal = $('#formEdicaoCliente');
        
        // Mostrar o loader e esconder o formulário
        $formOriginal.hide();
        $('#modalEdicaoCliente .modal-body').append('<div id="formLoader" class="text-center py-4"><i class="bx bx-loader-alt bx-spin fs-1"></i><p class="mt-2">Carregando informações...</p></div>');
        
        // Abrir o modal de forma híbrida (compatível com Bootstrap e classe manual)
        const $modal = $('#modalEdicaoCliente');
        
        // Garantir que aria-hidden não seja usado quando o modal estiver visível
        $modal.removeAttr('aria-hidden');
        
        // Tenta usar o método do Bootstrap primeiro
        if (typeof $modal.modal === 'function') {
            $modal.modal('show');
        } else {
            // Fallback para a abordagem de classe .active
            $modal.addClass('active');
            $('body').addClass('modal-open');
        }
        
        // Limpar produtos existentes antes de carregar novos dados
        removerTodosProdutosEdicao();
        
        // Buscar dados do agendamento via API
        $.ajax({
            url: `/inss/api/get/infocliente/?agendamento_id=${agendamentoId}`,
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                console.log('Dados do cliente/agendamento recebidos:', response);
                
                // Remover o loader
                $('#formLoader').remove();
                
                // Mostrar o formulário original novamente
                $formOriginal.show();
                
                // Preencher os campos do formulário com os dados recebidos
                $('#agendamentoIdEdicao').val(response.agendamento.id);
                $('#nomeClienteEdicao').val(response.cliente.nome_completo);
                $('#cpfClienteEdicao').val(response.cliente.cpf);
                $('#numeroClienteEdicao').val(response.cliente.numero_contato);
                $('#lojaAgendadaEdicao').val(response.loja.nome);
                // Adicionar campo oculto com o ID da loja agendada
                if (!$('#lojaAgendadaId').length) {
                    $('<input>').attr({
                        type: 'hidden',
                        id: 'lojaAgendadaId',
                        name: 'loja_id',
                        value: response.loja.id
                    }).appendTo('#formEdicaoCliente');
                } else {
                    $('#lojaAgendadaId').val(response.loja.id);
                }
                $('#atendenteAgendouEdicao').val(response.atendente.nome);
                $('#diaAgendadoEdicao').val(`${response.agendamento.dia_agendado} ${response.agendamento.hora_agendada}`);
                
                // Se já existe presença, buscar e preencher esses dados também
                if (response.agendamento.tem_presenca && response.presenca) {
                    // Preencher o select do vendedor
                    if (response.presenca.vendedor_id) {
                        $('#vendedorLojaEdicao').val(response.presenca.vendedor_id);
                    }
                    
                    // Preencher a tabulação do vendedor
                    if (response.presenca.tabulacao_venda) {
                        $('#tabulacaoVendedorEdicao').val(response.presenca.tabulacao_venda);
                        
                        // Se for NEGOCIO FECHADO, mostrar o container e carregar produtos
                        if (response.presenca.tabulacao_venda === 'NEGOCIO FECHADO') {
                            $('#fechouNegocioContainerEdicao').show();
                            
                            // Se tiver produtos na resposta, carregá-los
                            if (response.presenca.produtos && response.presenca.produtos.length > 0) {
                                response.presenca.produtos.forEach(produto => {
                                    const clone = produtoTemplateEdicao.content.cloneNode(true);
                                    const blocoProduto = clone.querySelector('.produto-bloco');
                                    
                                    // Atualiza IDs e Names com o índice correto
                                    blocoProduto.innerHTML = blocoProduto.innerHTML.replace(/__INDEX__/g, produtoEdicaoIndex);
                                    
                                    // Preencher o select de produtos
                                    const produtoSelect = blocoProduto.querySelector(`[name='produtos[${produtoEdicaoIndex}][produto_id]']`);
                                    if (produtoSelect) {
                                        preencherSelectProdutos($(produtoSelect));
                                        
                                        // Tentar definir o produto selecionado (se tivermos ID do produto)
                                        // Ou se tivermos apenas o nome, tentar encontrar o produto pelo nome
                                        if (produto.produto_id) {
                                            $(produtoSelect).val(produto.produto_id);
                                        } else if (produto.tipo_negociacao) {
                                            // Buscar produto pelo nome
                                            const produtosArray = Object.values(window.listaProdutos || {});
                                            const produtoEncontrado = produtosArray.find(
                                                p => p.nome.toUpperCase() === produto.tipo_negociacao.toUpperCase()
                                            );
                                            if (produtoEncontrado) {
                                                $(produtoSelect).val(produtoEncontrado.id);
                                            }
                                        }
                                    }
                                    
                                    // Preencher os campos com os dados do produto
                                    const campos = blocoProduto.querySelectorAll('input, select');
                                    campos.forEach(campo => {
                                        // Pular o campo produto_id que já foi tratado acima
                                        if (campo.name.includes('produto_id')) return;
                                        
                                        const nomeCampo = campo.name.match(/\[([^\]]+)\]$/);
                                        if (nomeCampo && nomeCampo[1] && produto[nomeCampo[1]] !== undefined) {
                                            if (campo.type === 'select-one') {
                                                campo.value = produto[nomeCampo[1]].toString();
                                            } else {
                                                campo.value = produto[nomeCampo[1]];
                                            }
                                        }
                                    });
                                    
                                    // Adiciona evento de remoção
                                    const btnRemove = blocoProduto.querySelector('.btn-remove-produto');
                                    btnRemove.addEventListener('click', function() {
                                        blocoProduto.remove();
                                    });
                                    
                                    // Aplica máscara de dinheiro ao campo valor_tac
                                    const valorTacInput = blocoProduto.querySelector('.money');
                                    if (valorTacInput) {
                                        aplicarMascaraDinheiro(valorTacInput);
                                    }
                                    
                                    produtosContainerEdicao.appendChild(blocoProduto);
                                    produtoEdicaoIndex++;
                                });
                            } else {
                                // Adiciona um produto em branco se não houver produtos
                                adicionarProdutoEdicao();
                            }
                        }
                    }
                    
                    // Preencher campos de TAC geral (se aplicável)
                    if (response.presenca.status_pagamento) {
                        $('#statusTacEdicao').val(response.presenca.status_pagamento);
                    }
                    
                    if (response.presenca.data_pagamento) {
                        $('#dataPagamentoTacEdicao').val(response.presenca.data_pagamento);
                    }
                }
                
                // Carregar vendedores disponíveis para o select
                carregarVendedoresSelect('#vendedorLojaEdicao');
                
                // Definir action do formulário 
                $('#formEdicaoCliente').attr('action', '/inss/api/post/atendimento/');
                
                // Atualizar título do modal
                $('.modal-title').html(`<i class='bx bx-edit me-2'></i>Atendimento do Cliente`);
                
                // Adicionar listeners específicos, se necessário
                $('#tabulacaoVendedorEdicao').on('change', handleTabulacaoVendedorChange);
                
                // Aplicar máscaras (para inputs como TAC e Número)
                $('#modalEdicaoCliente .money').mask('#.##0,00', { reverse: true });
                $('#numeroClienteEdicao').mask('(00) 0 0000-0000'); // Máscara aplicada aqui
                
                // Verificar visibilidade do botão de adicionar produto
                verificarVisibilidadeBotaoAddEdicao();
            },
            error: function(xhr, status, error) {
                console.error('Erro ao carregar dados do agendamento:', error);
                // Remover o loader
                $('#formLoader').remove();
                
                // Mostrar mensagem de erro
                $('#modalEdicaoCliente .modal-body').append(`
                    <div class="alert alert-danger">
                        <i class='bx bx-error-circle me-2'></i>
                        Erro ao carregar dados: ${xhr.responseJSON?.error || error}
                    </div>
                    <button type="button" class="btn btn-secondary w-100" onclick="fecharModal('#modalEdicaoCliente')">
                        <i class='bx bx-x me-2'></i>Fechar
                    </button>
                `);
            }
        });
    }
    
    /**
     * Função auxiliar para carregar os vendedores disponíveis em um select
     * @param {string} selectorId - Seletor do elemento select a ser preenchido
     */
    function carregarVendedoresSelect(selectorId) {
        const select = $(selectorId);
        select.empty().append('<option value="">Carregando vendedores...</option>');
        
        $.ajax({
            url: '/inss/api/get/info-loja-funcionario/',
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                select.empty().append('<option value="">Selecione um vendedor</option>');
                
                const funcionariosArray = Object.values(response.funcionarios || {});
                funcionariosArray.sort((a, b) => a.nome.localeCompare(b.nome));
                
                funcionariosArray.forEach(function(funcionario) {
                    select.append(`<option value="${funcionario.id}">${funcionario.nome}</option>`);
                });
            },
            error: function(xhr, status, error) {
                console.error("Erro ao carregar vendedores:", error);
                select.empty().append('<option value="">Erro ao carregar vendedores</option>');
            }
        });
    }
    
    /**
     * Função para fechar qualquer modal
     * @param {string} modalSelector - Seletor CSS do modal para fechar
     */
    function fecharModal(modalSelector) {
        const $modal = $(modalSelector);
        
        // Tenta usar o método do Bootstrap primeiro
        if (typeof $modal.modal === 'function') {
            $modal.modal('hide');
        } else {
            // Fallback para remover apenas a classe
            $modal.removeClass('active');
            $('body').removeClass('modal-open');
        }
        
        // Limpar erros imediatamente
        $(modalSelector + ' .alert').remove();
        $('#formLoader').remove();
        
        // Após um curto atraso, garantir que o formulário esteja visível e o modal corretamente fechado
        setTimeout(function() {
            $modal.attr('aria-hidden', 'true');
            
            // Garantir que o formulário esteja visível
            if (modalSelector === '#modalEdicaoCliente') {
                $('#formEdicaoCliente').show();
            }
        }, 300);
    }
    
    // Expor a função fecharModal globalmente para que o onclick nos botões de fechamento funcione
    window.fecharModal = fecharModal;
    
    // Carregar dados iniciais
    console.log('Iniciando carregamento de dados iniciais...');
    carregarAgendadosHoje();
    carregarAgendamentosPendentes();
    carregarLojasEFuncionarios(); // Chama a função para popular os selects do form cliente rua
    
    // Adicionar eventos para filtros (se existirem)
    $('#formFiltroClientesHoje').on('submit', function(e) { e.preventDefault(); });
    
    $('#formFiltroClientesHoje input').on('keyup change', function() {
        const filtros = {
            nomeCliente: $('#filtroNomeClientesHoje').val(),
            cpfCliente: $('#filtroCPFClientesHoje').val(),
            atendente: $('#filtroAtendenteClientesHoje').val(),
            status: $('#filtroStatusClientesHoje').val()
        };
        console.log('Aplicando filtros para agendados hoje:', filtros);
        carregarAgendadosHoje(filtros);
    });
    
    $('#formFiltroAgendamentosPendentes').on('submit', function(e) { e.preventDefault(); });
    
    $('#formFiltroAgendamentosPendentes input').on('keyup change', function() {
        const filtros = {
            nomeCliente: $('#filtroNomeAgendPendentes').val(),
            cpfCliente: $('#filtroCPFAgendPendentes').val(),
            atendente: $('#filtroAtendenteAgendPendentes').val(),
            status: $('#filtroStatusAgendPendentes').val()
        };
        console.log('Aplicando filtros para agendamentos pendentes:', filtros);
        carregarAgendamentosPendentes(filtros);
    });
    
    // Manipulador de envio do formulário de atendimento
    $('#formEdicaoCliente').on('submit', function(e) {
        e.preventDefault();
        
        console.log('[ADDVENDA] Início do processamento do formulário de atendimento');
        
        const $form = $(this);
        const $submitButton = $form.find('.btn-submit');
        const originalButtonText = $submitButton.html();
        
        // Desabilitar o botão para evitar múltiplos envios
        $submitButton.prop('disabled', true).html('<i class="bx bx-loader-alt bx-spin me-1"></i> Salvando...');
        console.log('[ADDVENDA] Botão de submit desabilitado');
        
        // Obter o ID do agendamento
        const agendamentoId = $('#agendamentoIdEdicao').val();
        if (!agendamentoId) {
            console.log('[ADDVENDA] Erro: ID do agendamento não encontrado');
            alertaErro('ID do agendamento não encontrado');
            $submitButton.prop('disabled', false).html(originalButtonText);
            return;
        }
        console.log('[ADDVENDA] ID do agendamento:', agendamentoId);
        
        // Verificar se o vendedor foi selecionado
        const vendedorId = $('#vendedorLojaEdicao').val();
        if (!vendedorId) {
            console.log('[ADDVENDA] Erro: Vendedor não selecionado');
            alertaErro('Por favor, selecione um vendedor.');
            $submitButton.prop('disabled', false).html(originalButtonText);
            return;
        }
        console.log('[ADDVENDA] ID do vendedor:', vendedorId);
        
        // Obter o ID da loja - Se houver um campo específico para loja de comparecimento
        const lojaId = $('#lojaComparecimentoEdicao').val() || $('#lojaAgendadaId').val();
        console.log('[ADDVENDA] ID da loja de comparecimento:', lojaId);
        
        // Verificar se a tabulação foi selecionada
        const tabulacaoVendedor = $('#tabulacaoVendedorEdicao').val();
        if (!tabulacaoVendedor) {
            console.log('[ADDVENDA] Erro: Tabulação não selecionada');
            alertaErro('Por favor, selecione uma tabulação.');
            $submitButton.prop('disabled', false).html(originalButtonText);
            return;
        }
        console.log('[ADDVENDA] Tabulação do vendedor:', tabulacaoVendedor);
        
        // Criar FormData para envio
        const formData = new FormData();
        formData.append('agendamento_id', agendamentoId);
        formData.append('vendedor_id', vendedorId);
        formData.append('tabulacao_vendedor', tabulacaoVendedor);
        
        // Adicionar o ID da loja se estiver disponível
        if (lojaId) {
            formData.append('loja_id', lojaId);
        }
        
        // Se a tabulação for NEGOCIO FECHADO, verificar produtos
        if (tabulacaoVendedor === 'NEGOCIO FECHADO') {
            console.log('[ADDVENDA] Tabulação é NEGOCIO FECHADO, verificando produtos...');
            
            // Verificar se existe pelo menos um produto
            const produtos = $('#produtosContainerEdicao .produto-bloco');
            if (produtos.length === 0) {
                console.log('[ADDVENDA] Erro: Nenhum produto encontrado para NEGOCIO FECHADO');
                alertaErro('Para tabulação "NEGOCIO FECHADO", é necessário adicionar pelo menos um produto.');
                $submitButton.prop('disabled', false).html(originalButtonText);
                return;
            }
            console.log('[ADDVENDA] Número de produtos encontrados:', produtos.length);
            
            // Criar um array de produtos para enviar como JSON
            const produtosArray = [];
            
            // Para cada produto, adiciona ao array de produtos
            console.log('[ADDVENDA] Processando cada produto para o array');
            produtos.each(function(index) {
                console.log('[ADDVENDA] Processando produto #', index);
                const produto = {};
                const camposProduto = $(this).find('input, select');
                
                camposProduto.each(function() {
                    const campo = $(this);
                    // Extrair apenas o nome do campo sem o índice
                    const nomeCampoCompleto = campo.attr('name');
                    const match = nomeCampoCompleto.match(/\[([^\]]+)\]$/);
                    if (match && match[1]) {
                        const nomeCampo = match[1]; // Ex: tipo_negociacao, banco, etc.
                        const valorCampo = campo.val();
                        produto[nomeCampo] = valorCampo;
                        console.log('[ADDVENDA] Campo adicionado ao produto:', nomeCampo, '=', valorCampo);
                    }
                });
                
                // Verificar campos obrigatórios do produto
                if (!produto.produto_id || !produto.banco) {
                    console.log('[ADDVENDA] Erro: Campos obrigatórios do produto não preenchidos');
                    alertaErro(`Por favor, selecione um produto e informe o banco para o Produto ${index + 1}.`);
                    $submitButton.prop('disabled', false).html(originalButtonText);
                    return false; // interrompe o loop each
                }
                
                produtosArray.push(produto);
            });
            
            // Se a validação falhou no each, sair da função
            if (produtosArray.length !== produtos.length) {
                return;
            }
            
            console.log('[ADDVENDA] Array de produtos criado:', produtosArray);
            
            // Adicionar o array de produtos como um único campo JSON
            formData.append('produtos_json', JSON.stringify(produtosArray));
        }
        
        // Adicionar token CSRF
        const csrftoken = $('input[name="csrfmiddlewaretoken"]').val();
        formData.append('csrfmiddlewaretoken', csrftoken);
        
        // Debugar todos os campos do FormData
        console.log('[ADDVENDA] Dados completos a serem enviados:');
        for (let pair of formData.entries()) {
            console.log('[ADDVENDA] FormData -', pair[0], ':', pair[1]);
        }
        
        // Fazer requisição AJAX
        console.log('[ADDVENDA] Iniciando envio AJAX para /inss/api/post/addvenda/');
        $.ajax({
            url: '/inss/api/post/addvenda/',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                console.log('[ADDVENDA] Sucesso na requisição AJAX!', response);
                if (response.status === 'success') {
                    console.log('[ADDVENDA] Status success, exibindo mensagem de sucesso');
                    // Exibe mensagem de sucesso
                    alertaSucesso(response.message);
                    
                    // Fecha o modal
                    console.log('[ADDVENDA] Fechando modal');
                    fecharModal('#modalEdicaoCliente');
                    
                    console.log('[ADDVENDA] Recarregando tabelas');
                    // Recarrega as tabelas para mostrar novos dados
                    carregarAgendadosHoje();
                    carregarAgendamentosPendentes();
                } else {
                    console.log('[ADDVENDA] Status não é success:', response.status);
                    alertaErro(response.message || 'Erro ao processar a solicitação.');
                }
            },
            error: function(xhr) {
                console.log('[ADDVENDA] Erro na requisição AJAX:', xhr);
                console.log('[ADDVENDA] Status:', xhr.status);
                console.log('[ADDVENDA] StatusText:', xhr.statusText);
                console.log('[ADDVENDA] ResponseText:', xhr.responseText);
                
                let mensagemErro = 'Erro ao processar a solicitação.';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    mensagemErro = xhr.responseJSON.message;
                    console.log('[ADDVENDA] Mensagem de erro encontrada na resposta:', mensagemErro);
                }
                alertaErro(mensagemErro);
            },
            complete: function() {
                console.log('[ADDVENDA] Requisição AJAX completada (sucesso ou erro)');
                // Restaura o botão de envio
                $submitButton.prop('disabled', false).html(originalButtonText);
                console.log('[ADDVENDA] Botão de submit restaurado');
            }
        });
        console.log('[ADDVENDA] Requisição AJAX iniciada, aguardando resposta...');
    });
    
    // Manipulador de envio do formulário de cliente rua
    $('#formClienteRuaInline').on('submit', function(e) {
        console.log('[CLIENTE RUA] Início do processamento do formulário');
        e.preventDefault(); // Impede o envio padrão do formulário

        console.log('[CLIENTE RUA] Validando formulário...');
        // Verifica se a validação do formulário passa
        if (!validarFormularioClienteRua()) {
            console.log('[CLIENTE RUA] Validação falhou! Abortando envio.');
            return false;
        }
        console.log('[CLIENTE RUA] Formulário validado com sucesso');

        // Exibe um indicador de carregamento
        const btnSubmit = $(this).find('.btn-submit');
        const textoOriginal = btnSubmit.html();
        btnSubmit.html('<i class="bx bx-loader-alt bx-spin me-2"></i> Processando...');
        btnSubmit.prop('disabled', true);
        console.log('[CLIENTE RUA] Botão de submit desabilitado');

        // Obtém dados do formulário
        const formData = new FormData(this);
        console.log('[CLIENTE RUA] FormData criado a partir do formulário');
        
        // Verifica se há produtos a serem adicionados
        const tabulacaoVendedor = $('#tabulacao_vendedor_rua_inline').val();
        console.log('[CLIENTE RUA] Tabulação do vendedor:', tabulacaoVendedor);
        
        if (tabulacaoVendedor === 'NEGOCIO FECHADO') {
            console.log('[CLIENTE RUA] Tabulação é NEGOCIO FECHADO, verificando produtos...');
            // Obtém todos os produtos do container
            const produtosContainer = $('#produtosContainerInline');
            const produtoBlocos = produtosContainer.find('.produto-bloco');
            console.log('[CLIENTE RUA] Número de produtos encontrados:', produtoBlocos.length);
            
            if (produtoBlocos.length === 0) {
                console.log('[CLIENTE RUA] Erro: Nenhum produto encontrado para NEGOCIO FECHADO');
                alertaErro('Para tabulação NEGOCIO FECHADO é necessário adicionar pelo menos um produto.');
                btnSubmit.html(textoOriginal);
                btnSubmit.prop('disabled', false);
                return false;
            }
            
            // MODIFICAÇÃO: Criar um array de produtos para enviar como JSON
            const produtosArray = [];
            
            // Para cada produto, adiciona ao array de produtos
            console.log('[CLIENTE RUA] Processando cada produto para o array');
            produtoBlocos.each(function(index) {
                console.log('[CLIENTE RUA] Processando produto #', index);
                const produto = {};
                const camposProduto = $(this).find('input, select');
                
                camposProduto.each(function() {
                    const campo = $(this);
                    // Extrair apenas o nome do campo sem o índice
                    const nomeCampoCompleto = campo.attr('name');
                    const match = nomeCampoCompleto.match(/\[([^\]]+)\]$/);
                    if (match && match[1]) {
                        const nomeCampo = match[1]; // Ex: tipo_negociacao, banco, etc.
                        const valorCampo = campo.val();
                        produto[nomeCampo] = valorCampo;
                        console.log('[CLIENTE RUA] Campo adicionado ao produto:', nomeCampo, '=', valorCampo);
                    }
                });
                
                produtosArray.push(produto);
            });
            
            console.log('[CLIENTE RUA] Array de produtos criado:', produtosArray);
            
            // Remover quaisquer campos de produtos individuais que possam existir no FormData
            for (const pair of formData.entries()) {
                if (pair[0].startsWith('produtos[')) {
                    formData.delete(pair[0]);
                }
            }
            
            // Adicionar o array de produtos como um único campo JSON
            formData.append('produtos_json', JSON.stringify(produtosArray));
            console.log('[CLIENTE RUA] Produtos JSON adicionados ao FormData:', JSON.stringify(produtosArray));
        }
        
        // Debugar todos os campos do FormData
        console.log('[CLIENTE RUA] Dados completos a serem enviados:');
        for (let pair of formData.entries()) {
            console.log('[CLIENTE RUA] FormData -', pair[0], ':', pair[1]);
        }
        
        console.log('[CLIENTE RUA] Iniciando envio AJAX para /inss/api/post/novavenda/');
        // Faz a requisição AJAX para a API
        $.ajax({
            url: '/inss/api/post/novavenda/',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                console.log('[CLIENTE RUA] Sucesso na requisição AJAX!', response);
                if (response.status === 'success') {
                    console.log('[CLIENTE RUA] Status success, exibindo mensagem de sucesso');
                    // Exibe mensagem de sucesso
                    alertaSucesso(response.message);
                    
                    console.log('[CLIENTE RUA] Limpando formulário');
                    // Limpa o formulário
                    $('#formClienteRuaInline')[0].reset();
                    
                    console.log('[CLIENTE RUA] Limpando produtos adicionados');
                    // Limpa os produtos adicionados
                    $('#produtosContainerInline').empty();
                    
                    console.log('[CLIENTE RUA] Escondendo botão de adicionar produto');
                    // Esconde o botão de adicionar produto
                    $('#addProdutoBtnContainerInline').hide();
                    
                    console.log('[CLIENTE RUA] Recarregando tabelas');
                    // Recarrega as tabelas para mostrar novos dados
                    carregarAgendadosHoje();
                    carregarAgendamentosPendentes();
                } else {
                    console.log('[CLIENTE RUA] Status não é success:', response.status);
                    alertaErro(response.message || 'Erro ao processar a solicitação.');
                }
            },
            error: function(xhr) {
                console.log('[CLIENTE RUA] Erro na requisição AJAX:', xhr);
                console.log('[CLIENTE RUA] Status:', xhr.status);
                console.log('[CLIENTE RUA] StatusText:', xhr.statusText);
                console.log('[CLIENTE RUA] ResponseText:', xhr.responseText);
                
                let mensagemErro = 'Erro ao processar a solicitação.';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    mensagemErro = xhr.responseJSON.message;
                    console.log('[CLIENTE RUA] Mensagem de erro encontrada na resposta:', mensagemErro);
                }
                alertaErro(mensagemErro);
            },
            complete: function() {
                console.log('[CLIENTE RUA] Requisição AJAX completada (sucesso ou erro)');
                // Restaura o botão de envio
                btnSubmit.html(textoOriginal);
                btnSubmit.prop('disabled', false);
                console.log('[CLIENTE RUA] Botão de submit restaurado');
            }
        });
        console.log('[CLIENTE RUA] Requisição AJAX iniciada, aguardando resposta...');
    });

    /**
     * Valida o formulário de cliente rua antes do envio
     */
    function validarFormularioClienteRua() {
        // Campos obrigatórios
        const camposObrigatorios = [
            { id: 'nome_cliente_rua_inline', mensagem: 'O nome do cliente é obrigatório.' },
            { id: 'cpf_cliente_rua_inline', mensagem: 'O CPF do cliente é obrigatório.' },
            { id: 'numero_cliente_rua_inline', mensagem: 'O número de contato é obrigatório.' },
            { id: 'data_comparecimento_rua_inline', mensagem: 'A data de comparecimento é obrigatória.' },
            { id: 'loja_rua_inline', mensagem: 'A loja é obrigatória.' },
            { id: 'vendedor_rua_inline', mensagem: 'O vendedor é obrigatório.' },
            { id: 'tabulacao_vendedor_rua_inline', mensagem: 'A tabulação do vendedor é obrigatória.' }
        ];
        
        for (const campo of camposObrigatorios) {
            const valor = $(`#${campo.id}`).val();
            if (!valor || valor.trim() === '') {
                alertaErro(campo.mensagem);
                $(`#${campo.id}`).focus();
                return false;
            }
        }
        
        // Validar CPF
        const cpf = $('#cpf_cliente_rua_inline').val().replace(/\D/g, '');
        if (cpf.length !== 11) {
            alertaErro('CPF inválido. Deve conter 11 dígitos.');
            $('#cpf_cliente_rua_inline').focus();
            return false;
        }
        
        // Validar produtos se a tabulação for NEGOCIO FECHADO
        const tabulacao = $('#tabulacao_vendedor_rua_inline').val();
        if (tabulacao === 'NEGOCIO FECHADO') {
            const produtosContainer = $('#produtosContainerInline');
            const produtoBlocos = produtosContainer.find('.produto-bloco');
            
            if (produtoBlocos.length === 0) {
                alertaErro('Para tabulação NEGOCIO FECHADO é necessário adicionar pelo menos um produto.');
                return false;
            }
            
            // Verificar se cada produto tem um produto_id selecionado
            let produtosValidos = true;
            produtoBlocos.each(function(index) {
                const produtoId = $(this).find('select[name^="produtos"][name$="[produto_id]"]').val();
                if (!produtoId) {
                    alertaErro(`Por favor, selecione um produto para o Produto ${index + 1}.`);
                    produtosValidos = false;
                    return false; // Sai do loop each
                }
                
                const banco = $(this).find('input[name^="produtos"][name$="[banco]"]').val();
                if (!banco) {
                    alertaErro(`Por favor, informe o banco para o Produto ${index + 1}.`);
                    produtosValidos = false;
                    return false; // Sai do loop each
                }
            });
            
            if (!produtosValidos) {
                return false;
            }
        }
        
        
        return true;
    }

    /**
     * Exibe um alerta de erro
     */
    function alertaErro(mensagem) {
        alert('ERRO: ' + mensagem);
    }

    /**
     * Exibe um alerta de sucesso
     */
    function alertaSucesso(mensagem) {
        alert('SUCESSO: ' + mensagem);
    }

    /**
     * Função para tratamento da mudança de tabulação do vendedor no formulário inline
     */
    function handleTabulacaoVendedorInline() {
        const tabulacao = $('#tabulacao_vendedor_rua_inline').val();
        
        // Mostrar ou esconder o botão de adicionar produto com base na tabulação
        if (tabulacao === 'NEGOCIO FECHADO') {
            $('#addProdutoBtnContainerInline').show();
        } else {
            $('#addProdutoBtnContainerInline').hide();
            // Limpar container de produtos se a tabulação não for NEGOCIO FECHADO
            $('#produtosContainerInline').empty();
        }
    }

    // Inicialização das máscaras para os campos
    $(document).ready(function() {
        $('#cpf_cliente_rua_inline').mask('000.000.000-00');
        $('#numero_cliente_rua_inline').mask('(00) 0 0000-0000');
        
        // Associando evento de clique ao botão de adicionar produto
        $('#btnAddProdutoInline').on('click', function() {
            adicionarProduto();
        });
        
        // Delegando evento para remover produtos
        $('#produtosContainerInline').on('click', '.btn-remove-produto', function() {
            $(this).closest('.produto-bloco').remove();
        });
        
        // Delegando evento para aplicar máscara nos campos de valor TAC
        $('#produtosContainerInline').on('focus', '.money', function() {
            $(this).mask('#.##0,00', {reverse: true});
        });
        
        // Adicionar manipulador de evento change para o select de tabulação no modal de edição
        $('#tabulacaoVendedorEdicao').on('change', handleTabulacaoVendedorChange);
        
        // Carregar lojas, funcionários e produtos
        carregarLojasEFuncionarios();
    });
});
