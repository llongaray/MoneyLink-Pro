/**
 * Funções para gerenciamento de TACs na página financeira do INSS
 * 
 * Este módulo contém funções para:
 * 1. Carregar TACs pendentes da API
 * 2. Exibir os TACs na tabela
 * 3. Processar o pagamento de TACs
 * 4. Atualizar o valor do TAC
 */

$(document).ready(function() {
    console.log('Documento pronto, inicializando módulo financeiro INSS');
    // Carrega os TACs pendentes ao iniciar a página
    carregarTACs();
    
    // Configura a atualização automática a cada 5 minutos
    console.log('Configurando atualização automática a cada 5 minutos');
    setInterval(carregarTACs, 300000);

    // Carrega os dados dos cards financeiros
    carregarCardsFinanceiro();

    // Carrega o histórico de pagamentos
    carregarHistoricoPagamentos();

    // Inicializa os tooltips
    console.log('Inicializando tooltips');
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Adiciona evento de submit ao formulário de filtro
    $('#formFiltroFinanceiro').on('submit', function(e) {
        e.preventDefault(); // Impede o envio do formulário
        aplicarFiltros();
    });
    
    // Preenchimento do select de lojas
    carregarLojas();
});

/**
 * Carrega os TACs pendentes da API e atualiza a tabela
 */
function carregarTACs() {
    console.log('Iniciando carregamento de TACs pendentes');
    $.ajax({
        url: '/inss/api/get/tac/',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            console.log('Resposta da API recebida:', response);
            if (response.success) {
                console.log('Sucesso ao carregar TACs, atualizando tabela com', response.presencas.length, 'registros');
                atualizarTabelaTACs(response.presencas);
            } else {
                console.error('Erro retornado pela API:', response.error);
                exibirMensagemErro('Erro ao carregar TACs: ' + response.error);
            }
        },
        error: function(xhr, status, error) {
            console.error('Erro na requisição AJAX:', status, error);
            console.error('Detalhes do XHR:', xhr);
            exibirMensagemErro('Erro na requisição: ' + error);
        }
    });
}

/**
 * Atualiza a tabela de TACs com os dados recebidos da API
 * 
 * @param {Array} presencas - Lista de presenças com TACs pendentes
 */
function atualizarTabelaTACs(presencas) {
    console.log('Iniciando atualização da tabela de TACs');
    const tabela = $('#tabelaAgendamentosTAC tbody');
    tabela.empty();
    console.log('Tabela limpa, preparando para inserir novos dados');
    
    if (presencas && presencas.length > 0) {
        console.log('Processando', presencas.length, 'presenças para exibição');
        // Oculta a mensagem de nenhum resultado
        $('#nenhumResultadoTAC').hide();
        console.log('Mensagem "nenhum resultado" ocultada');
        
        // Adiciona cada presença à tabela
        presencas.forEach(function(presenca, index) {
            console.log('Adicionando presença', index + 1, ':', presenca);
            
            // Extrai o valor numérico do valor_tac formatado (remove R$ e converte vírgula para ponto)
            const valorTacNumerico = presenca.valor_tac.replace('R$', '').replace('.', '').replace(',', '.').trim();
            
            tabela.append(`
                <tr>
                    <td>${presenca.nome_cliente}</td>
                    <td>${presenca.cpf_cliente}</td>
                    <td>${presenca.loja}</td>
                    <td>${presenca.data}</td>
                    <td class="text-end">
                        <form class="form-valor-tac">
                            <input type="hidden" name="presenca_id" value="${presenca.id}">
                            <input type="text" class="form-control form-control-sm input-valor-tac" 
                                   name="valor_tac" value="${valorTacNumerico}" 
                                   data-valor-original="${valorTacNumerico}">
                        </form>
                    </td>
                    <td class="text-center">
                        <button class="btn btn-sm btn-success btn-confirmar-tac" 
                                data-id="${presenca.id}" 
                                data-bs-toggle="tooltip" 
                                title="Confirmar Pagamento">
                            <i class="bx bx-check"></i> Confirmar
                        </button>
                    </td>
                </tr>
            `);
        });
        
        // Adiciona evento de clique aos botões de confirmação
        console.log('Adicionando eventos de clique aos botões de confirmação');
        $('.btn-confirmar-tac').on('click', function() {
            const presencaId = $(this).data('id');
            console.log('Botão de confirmação clicado para presença ID:', presencaId);
            confirmarPagamentoTAC(presencaId);
        });
        
        // Adiciona evento de blur (quando o campo perde o foco) aos inputs de valor TAC
        console.log('Adicionando eventos de blur aos inputs de valor TAC');
        $('.input-valor-tac').on('blur', function() {
            const form = $(this).closest('form');
            const presencaId = form.find('input[name="presenca_id"]').val();
            const novoValor = $(this).val();
            const valorOriginal = $(this).data('valor-original');
            
            // Só atualiza se o valor foi alterado
            if (novoValor !== valorOriginal) {
                console.log(`Valor TAC alterado para presença ID ${presencaId}: ${valorOriginal} -> ${novoValor}`);
                atualizarValorTAC(presencaId, novoValor, $(this));
            }
        });
    } else {
        // Exibe mensagem de nenhum resultado
        console.log('Nenhuma presença encontrada, exibindo mensagem');
        $('#nenhumResultadoTAC').show();
    }
}

/**
 * Atualiza o valor do TAC de uma presença
 * 
 * @param {number} presencaId - ID da presença
 * @param {string} novoValor - Novo valor do TAC
 * @param {Object} inputElement - Elemento jQuery do input que foi alterado
 */
function atualizarValorTAC(presencaId, novoValor, inputElement) {
    console.log('Iniciando atualização de valor TAC para presença ID:', presencaId);
    
    // Obtém o token CSRF do cookie
    const csrftoken = getCookie('csrftoken');
    console.log('Token CSRF obtido:', csrftoken);
    
    if (!csrftoken) {
        console.error('Token CSRF não encontrado no cookie.');
        exibirMensagemErro('Erro: Token CSRF não encontrado. Por favor, recarregue a página.');
        return;
    }
    
    // Desabilita o input durante a atualização
    inputElement.prop('disabled', true);
    
    $.ajax({
        url: '/inss/api/post/attvalortac/',
        type: 'POST',
        dataType: 'json',
        data: {
            id: presencaId,
            valor_tac: novoValor
        },
        headers: {
            'X-CSRFToken': csrftoken
        },
        success: function(response) {
            console.log('Resposta da API recebida:', response);
            if (response.success) {
                // Atualiza o valor original no data-attribute
                inputElement.data('valor-original', novoValor);
                
                // Exibe mensagem de sucesso
                console.log('Valor TAC atualizado com sucesso');
                exibirMensagemSucesso(response.message);
            } else {
                console.error('Erro retornado pela API:', response.message);
                exibirMensagemErro(response.message);
                
                // Restaura o valor original em caso de erro
                inputElement.val(inputElement.data('valor-original'));
            }
        },
        error: function(xhr, status, error) {
            console.error('Erro na requisição AJAX:', status, error);
            console.error('Detalhes do XHR:', xhr);
            
            let mensagemErro = 'Erro ao atualizar valor TAC';
            
            try {
                const resposta = JSON.parse(xhr.responseText);
                console.log('Resposta de erro parseada:', resposta);
                if (resposta.message) {
                    mensagemErro = resposta.message;
                }
            } catch (e) {
                console.error('Erro ao parsear resposta:', e);
                mensagemErro += ': ' + error;
            }
            
            console.error('Mensagem de erro final:', mensagemErro);
            exibirMensagemErro(mensagemErro);
            
            // Restaura o valor original em caso de erro
            inputElement.val(inputElement.data('valor-original'));
        },
        complete: function() {
            // Reabilita o input após a conclusão da requisição
            inputElement.prop('disabled', false);
        }
    });
}

/**
 * Envia requisição para confirmar o pagamento de um TAC
 * 
 * @param {number} presencaId - ID da presença a ser confirmada
 */
function confirmarPagamentoTAC(presencaId) {
    console.log('Iniciando confirmação de pagamento para presença ID:', presencaId);
    // Confirmação antes de processar
    if (!confirm('Confirmar o pagamento deste TAC?')) {
        console.log('Confirmação cancelada pelo usuário');
        return;
    }
    
    console.log('Confirmação aceita pelo usuário, obtendo token CSRF do cookie');
    // Obtém o token CSRF do cookie (método padrão Django para AJAX)
    const csrftoken = getCookie('csrftoken');
    console.log('Valor do cookie csrftoken obtido:', csrftoken); // Log para verificar o token
    
    if (!csrftoken) {
        console.error('Token CSRF não encontrado no cookie.');
        exibirMensagemErro('Erro: Token CSRF não encontrado. Por favor, recarregue a página.');
        return;
    }
    
    console.log('Token CSRF obtido, enviando requisição para API');
    $.ajax({
        url: '/inss/api/post/tac/',
        type: 'POST',
        dataType: 'json',
        data: {
            presenca_id: presencaId
        },
        headers: {
            'X-CSRFToken': csrftoken
        },
        success: function(response) {
            console.log('Resposta da API recebida:', response);
            if (response.success) {
                // Exibe mensagem de sucesso
                console.log('Pagamento confirmado com sucesso');
                exibirMensagemSucesso(response.message);
                
                // Recarrega a tabela
                console.log('Recarregando tabela após confirmação');
                carregarTACs();
            } else {
                console.error('Erro retornado pela API:', response.message);
                exibirMensagemErro(response.message);
            }
        },
        error: function(xhr, status, error) {
            console.error('Erro na requisição AJAX:', status, error);
            console.error('Detalhes do XHR:', xhr);
            
            let mensagemErro = 'Erro ao processar pagamento';
            
            try {
                const resposta = JSON.parse(xhr.responseText);
                console.log('Resposta de erro parseada:', resposta);
                if (resposta.message) {
                    mensagemErro = resposta.message;
                }
            } catch (e) {
                console.error('Erro ao parsear resposta:', e);
                mensagemErro += ': ' + error;
            }
            
            console.error('Mensagem de erro final:', mensagemErro);
            exibirMensagemErro(mensagemErro);
        }
    });
}

/**
 * Exibe uma mensagem de sucesso temporária
 * 
 * @param {string} mensagem - Mensagem a ser exibida
 */
function exibirMensagemSucesso(mensagem) {
    console.log('Exibindo mensagem de sucesso:', mensagem);
    alert('Sucesso!\n' + mensagem);
}

/**
 * Exibe uma mensagem de erro usando alert
 * 
 * @param {string} mensagem - Mensagem de erro a ser exibida
 */
function exibirMensagemErro(mensagem) {
    console.error('Exibindo mensagem de erro:', mensagem);
    alert('Erro:\n' + mensagem);
}

/**
 * Obtém o valor de um cookie pelo nome
 * 
 * @param {string} name - Nome do cookie
 * @return {string} Valor do cookie ou string vazia
 */
function getCookie(name) {
    console.log('Buscando cookie com nome:', name);
    let cookieValue = '';
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        console.log('Cookies encontrados:', cookies.length);
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                console.log('Cookie encontrado, valor:', cookieValue);
                break;
            }
        }
    }
    if (!cookieValue) {
        console.log('Cookie não encontrado');
    }
    return cookieValue;
}

function carregarCardsFinanceiro() {
    $.ajax({
        url: '/inss/api/get/cardsfinanceiro/',
        type: 'GET',
        dataType: 'json',
        beforeSend: function(xhr) {
            xhr.setRequestHeader("X-CSRFToken", getCookie("csrftoken"));
        },
        success: function(response) {
            console.log('Resposta da API cardsfinanceiro:', response);
            
            // Verificamos se a resposta existe e não tem erro
            if (response && !response.error) {
                // Atualizamos com os dados retornados pela API usando os IDs corretos do HTML
                $('#totalTCAno').text(response.totalTCAno || 'R$ 0,00');
                $('#totalTCAnoPendente').text(response.totalTCAnoPendente || 'R$ 0,00');
                $('#totalTCMes').text(response.totalTCMes || 'R$ 0,00');
                $('#totalTCMesPendente').text(response.totalTCMesPendente || 'R$ 0,00');
                $('#qtdTCAno').text(response.qtdTCAno || '0');
                $('#qtdTCMes').text(response.qtdTCMes || '0');
            } else {
                let errorMsg = 'Erro ao processar dados dos cards financeiros';
                if (response && response.error) {
                    errorMsg += ': ' + response.error;
                }
                exibirMensagemErro(errorMsg);
                console.error('Resposta da API inválida:', response);
            }
        },
        error: function(xhr, status, error) {
            exibirMensagemErro('Erro ao carregar dados dos cards financeiros');
            console.error('Erro na requisição AJAX:', status, error);
            console.error('Resposta do servidor:', xhr.responseText);
        }
    });
}

function carregarHistoricoPagamentos() {
    console.log('Iniciando carregamento do histórico de pagamentos');
    $.ajax({
        url: '/inss/api/get/historicopagamentos/',
        type: 'GET',
        dataType: 'json',
        beforeSend: function(xhr) {
            xhr.setRequestHeader("X-CSRFToken", getCookie("csrftoken"));
        },
        success: function(response) {
            console.log('Resposta da API de histórico recebida:', response);
            
            if (response && response.historico) {
                atualizarTabelaHistorico(response.historico);
            } else if (response && response.error) {
                console.error('Erro retornado pela API de histórico:', response.error);
                exibirMensagemErro('Erro ao carregar histórico: ' + response.error);
            } else {
                console.error('Resposta da API de histórico inválida:', response);
                exibirMensagemErro('Erro: Resposta inválida da API de histórico');
            }
        },
        error: function(xhr, status, error) {
            console.error('Erro na requisição AJAX de histórico:', status, error);
            console.error('Detalhes do XHR:', xhr);
            exibirMensagemErro('Erro ao carregar histórico: ' + error);
        }
    });
}

function atualizarTabelaHistorico(historico) {
    console.log('Atualizando tabela de histórico com', historico.length, 'registros');
    const tabela = $('#tabelaHistoricoPagamentos tbody');
    tabela.empty();
    
    if (historico && historico.length > 0) {
        $('#nenhumResultadoHistorico').hide();
        
        historico.forEach(function(pagamento) {
            const btnAcao = pagamento.status_pagamento === 'PAGO' 
                ? `<button class="btn btn-sm btn-info" disabled>Pago</button>`
                : `<button class="btn btn-sm btn-success btn-confirmar-tac" 
                          data-id="${pagamento.id}" 
                          data-bs-toggle="tooltip" 
                          title="Confirmar Pagamento">
                       <i class="bx bx-check"></i> Confirmar
                   </button>`;
            
            tabela.append(`
                <tr>
                    <td>${pagamento.cliente_nome}</td>
                    <td>${pagamento.cliente_cpf}</td>
                    <td>${pagamento.loja_nome}</td>
                    <td>${pagamento.data_pagamento}</td>
                    <td class="text-end">${pagamento.valor_tac}</td>
                    <td class="text-center">
                        <span class="badge ${pagamento.status_pagamento === 'PAGO' ? 'bg-success' : 'bg-warning'}">
                            ${pagamento.status_pagamento}
                        </span>
                    </td>
                    <td class="text-center">
                        ${btnAcao}
                    </td>
                </tr>
            `);
        });
        
        // Inicializa tooltips para novos botões
        $('[data-bs-toggle="tooltip"]').tooltip();
        
        // Adiciona evento aos botões de confirmação
        $('.btn-confirmar-tac').on('click', function() {
            const presencaId = $(this).data('id');
            console.log('Botão de confirmação clicado no histórico para ID:', presencaId);
            confirmarPagamentoTAC(presencaId);
        });
    } else {
        console.log('Nenhum histórico de pagamento encontrado');
        $('#nenhumResultadoHistorico').show();
    }
}

// Função para carregar lojas no select de filtro
function carregarLojas() {
    $.ajax({
        url: '/inss/api/get/info-loja-funcionario/',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response && response.lojas) {
                const selectLoja = $('#filtro_loja');
                response.lojas.forEach(function(loja) {
                    selectLoja.append(`<option value="${loja.nome}">${loja.nome}</option>`);
                });
            }
        },
        error: function(xhr, status, error) {
            console.error('Erro ao carregar lojas:', error);
        }
    });
}

// Função para aplicar filtros na tabela
function aplicarFiltros() {
    const periodo = $('#filtro_periodo').val();
    const dataEspecifica = $('#filtro_data_especifica').val();
    const loja = $('#filtro_loja').val();
    const status = $('#filtro_status').val();
    
    console.log('Aplicando filtros:', { periodo, dataEspecifica, loja, status });
    
    // --- Funções auxiliares para validação de datas ---
    
    // Verifica se uma data está no período selecionado
    function estaNoPerioido(dataStr, periodo) {
        if (!periodo || periodo === '') return true;
        if (!dataStr || dataStr === '-') return false;
        
        // Converte data formato DD/MM/YYYY para Date
        const partes = dataStr.split('/');
        if (partes.length !== 3) return false;
        
        const data = new Date(partes[2], partes[1] - 1, partes[0]);
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        
        if (periodo === 'HOJE') {
            return data.getDate() === hoje.getDate() && 
                   data.getMonth() === hoje.getMonth() && 
                   data.getFullYear() === hoje.getFullYear();
        }
        
        if (periodo === 'SEMANA') {
            const inicioSemana = new Date(hoje);
            inicioSemana.setDate(hoje.getDate() - hoje.getDay()); // Domingo
            
            const fimSemana = new Date(inicioSemana);
            fimSemana.setDate(inicioSemana.getDate() + 6); // Sábado
            
            return data >= inicioSemana && data <= fimSemana;
        }
        
        if (periodo === 'MES') {
            return data.getMonth() === hoje.getMonth() && 
                   data.getFullYear() === hoje.getFullYear();
        }
        
        return true;
    }
    
    // Verifica se bate com a data específica
    function correspondeDataEspecifica(dataStr, dataEspecifica) {
        if (!dataEspecifica || dataEspecifica === '') return true;
        if (!dataStr || dataStr === '-') return false;
        
        // Converte data formato DD/MM/YYYY para comparar com dataEspecifica (YYYY-MM-DD)
        const partes = dataStr.split('/');
        if (partes.length !== 3) return false;
        
        const dataFormatada = `${partes[2]}-${partes[1]}-${partes[0]}`;
        return dataFormatada === dataEspecifica;
    }
    
    // --- Filtro da Tabela de Histórico de Pagamentos ---
    let totalHistoricoVisiveis = 0;
    
    $('#tabelaHistoricoPagamentos tbody tr').each(function() {
        const $row = $(this);
        const rowLoja = $row.find('td:eq(2)').text().trim();
        const rowData = $row.find('td:eq(3)').text().trim();
        const rowStatus = $row.find('td:eq(5)').text().trim();
        
        // Verifica se a linha atende a todos os critérios
        const atendeLoja = !loja || loja === '' || rowLoja === loja;
        const atendePeriodo = estaNoPerioido(rowData, periodo);
        const atendeDataEspecifica = correspondeDataEspecifica(rowData, dataEspecifica);
        const atendeStatus = !status || status === '' || rowStatus.includes(status);
        
        const deveExibir = atendeLoja && atendePeriodo && atendeDataEspecifica && atendeStatus;
        
        if (deveExibir) {
            $row.show();
            totalHistoricoVisiveis++;
        } else {
            $row.hide();
        }
    });
    
    // Exibe mensagem se não houver resultados na tabela de histórico
    if (totalHistoricoVisiveis === 0) {
        $('#nenhumResultadoHistorico').show();
    } else {
        $('#nenhumResultadoHistorico').hide();
    }
    
    // --- Filtro da Tabela de TACs Pendentes ---
    let totalTacVisiveis = 0;
    
    $('#tabelaAgendamentosTAC tbody tr').each(function() {
        const $row = $(this);
        const rowNome = $row.find('td:eq(0)').text().trim();
        const rowCpf = $row.find('td:eq(1)').text().trim();
        const rowLoja = $row.find('td:eq(2)').text().trim();
        const rowData = $row.find('td:eq(3)').text().trim();
        
        // Verifica se a linha atende aos critérios aplicáveis (TACs não têm status)
        const atendeLoja = !loja || loja === '' || rowLoja === loja;
        const atendePeriodo = estaNoPerioido(rowData, periodo);
        const atendeDataEspecifica = correspondeDataEspecifica(rowData, dataEspecifica);
        // O filtro de status não se aplica à tabela de TACs pendentes, pois eles ainda não foram pagos
        
        const deveExibir = atendeLoja && atendePeriodo && atendeDataEspecifica;
        
        if (deveExibir) {
            $row.show();
            totalTacVisiveis++;
        } else {
            $row.hide();
        }
    });
    
    // Exibe mensagem se não houver resultados na tabela de TACs
    if (totalTacVisiveis === 0) {
        $('#nenhumResultadoTAC').show();
    } else {
        $('#nenhumResultadoTAC').hide();
    }
    
    // Exibe uma mensagem no console
    console.log(`Filtros aplicados. Exibindo ${totalHistoricoVisiveis} registros de histórico e ${totalTacVisiveis} TACs pendentes.`);
}

