$(document).ready(function() {
    // Carrega os relatórios ao iniciar
    carregarRelatorios();

    // Configura o botão de filtrar
    $('#btn-filtrar').click(function() {
        carregarRelatorios();
    });

    // Carrega a lista de funcionários
    carregarFuncionarios();
});

function carregarRelatorios() {
    const dataInicio = $('#data-inicio').val();
    const dataFim = $('#data-fim').val();
    const usuarioId = $('#usuario').val();

    // Mostra loading
    $('#tabela-relatorios tbody').html('<tr><td colspan="4" class="text-center loading">Carregando relatórios...</td></tr>');

    // Faz a requisição
    $.ajax({
        url: '/rh/api/presenca/relatorio/',
        method: 'GET',
        data: {
            data_inicio: dataInicio,
            data_fim: dataFim,
            usuario_id: usuarioId
        },
        success: function(response) {
            atualizarTabelaRelatorio(response);
        },
        error: function(xhr) {
            mostrarErro('Erro ao carregar relatórios: ' + (xhr.responseJSON?.error || 'Erro desconhecido'));
            $('#tabela-relatorios tbody').html('<tr><td colspan="4" class="text-center text-danger">Erro ao carregar relatórios</td></tr>');
        }
    });
}

function carregarFuncionarios() {
    $.ajax({
        url: '/rh/api/presenca/funcionarios/',
        method: 'GET',
        success: function(response) {
            const select = $('#usuario');
            select.empty();
            select.append('<option value="">Todos</option>');
            
            response.forEach(function(funcionario) {
                select.append(`<option value="${funcionario.id}">${funcionario.nome}</option>`);
            });
        },
        error: function(xhr) {
            mostrarErro('Erro ao carregar lista de funcionários: ' + (xhr.responseJSON?.error || 'Erro desconhecido'));
        }
    });
}

function atualizarTabelaRelatorio(relatorios) {
    const tbody = $('#tabela-relatorios tbody');
    tbody.empty();

    if (relatorios.length === 0) {
        tbody.html('<tr><td colspan="4" class="text-center">Nenhum relatório encontrado</td></tr>');
        return;
    }

    relatorios.forEach(function(relatorio) {
        const tr = $('<tr>').addClass('fade-in');
        tr.append(`<td>${relatorio.data}</td>`);
        tr.append(`<td>${relatorio.usuario.nome}</td>`);
        tr.append(`<td>${relatorio.observacao}</td>`);
        tr.append(`<td>${relatorio.data_criacao}</td>`);
        tbody.append(tr);
    });
}

function mostrarErro(mensagem) {
    // Implementar de acordo com o sistema de notificações do projeto
    alert(mensagem);
} 