$(document).ready(function() {
    // Função para criar e baixar um CSV modelo
    function downloadCSV(filename, headers) {
        const csvContent = "data:text/csv;charset=ISO-8859-1," + headers.join(";");
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Botões de modelo...
    $('#csv_funcionarios').before(`
        <button type="button" class="btn btn-outline-primary w-100 mb-3" id="btn-download-funcionarios">
            <i class='bx bx-download me-2'></i> Baixar Modelo Funcionários
        </button>
    `);
    $('#btn-download-funcionarios').click(function() {
        downloadCSV('modelo_funcionarios.csv', [
            'apelido','nome_completo','cpf','data_nascimento',
            'empresa_id','departamento_id','setor_id','cargo_id',
            'equipe_id','loja_id'
        ]);
    });

    $('#csv_c2').before(`
        <button type="button" class="btn btn-outline-success w-100 mb-3" id="btn-download-c2">
            <i class='bx bx-download me-2'></i> Baixar Modelo Cliente C2
        </button>
    `);
    $('#btn-download-c2').click(function() {
        downloadCSV('modelo_cliente_c2.csv', [
            'nome_completo','cpf','numero_contato','flg_whatsapp'
        ]);
    });

    $('#csv_agendamentos').before(`
        <button type="button" class="btn btn-outline-success w-100 mb-3" id="btn-download-agendamentos">
            <i class='bx bx-download me-2'></i> Baixar Modelo Agendamentos
        </button>
    `);
    $('#btn-download-agendamentos').click(function() {
        downloadCSV('modelo_agendamentos.csv', [
            'cpf_cliente','dia_agendado','loja_id',
            'atendente_id','tabulacao_agendamento'
        ]);
    });

    $('#csv_registermoney').before(`
        <button type="button" class="btn btn-outline-warning w-100 mb-3" id="btn-download-registermoney">
            <i class='bx bx-download me-2'></i> Baixar Modelo RegisterMoney
        </button>
    `);
    $('#btn-download-registermoney').click(function() {
        downloadCSV('modelo_registermoney.csv', [
            'user_id','loja_id','produto','cpf_cliente',
            'valor_estimado','empresa_id','departamento_id',
            'setor_id','equipe_id','data_pagamento'
        ]);
    });
});

// Função para processar o CSV e enviar para a API
function processarCSV(formId, apiUrl) {
    const form = $(formId);
    const fileInput = form.find('input[type="file"]')[0];
    const file = fileInput.files[0];

    if (!file) {
        mostrarMensagem('Por favor, selecione um arquivo CSV.', 'danger');
        return;
    }

    const submitBtn = form.find('button[type="submit"]');
    submitBtn.prop('disabled', true)
             .html(`<i class='bx bx-loader bx-spin me-2'></i> Processando...`);

    const reader = new FileReader();
    // forçar ISO-8859-1 (ABNT2) na leitura
    reader.readAsText(file, 'ISO-8859-1');
    reader.onload = function(e) {
        try {
            const csvData = e.target.result;
            const rows = csvData.split('\n').filter(r => r.trim());
            const headers = rows[0].split(';').map(h => h.trim());
            const jsonData = [];

            for (let i = 1; i < rows.length; i++) {
                const row = rows[i].split(';');
                if (row.length === headers.length) {
                    const obj = {};
                    headers.forEach((header, idx) => {
                        obj[header] = row[idx] ? row[idx].trim() : null;
                    });
                    jsonData.push(obj);
                }
            }

            $.ajax({
                url: apiUrl,
                method: 'POST',
                contentType: 'application/json; charset=utf-8',
                data: JSON.stringify(jsonData),
                headers: {
                    'X-CSRFToken': form.find('input[name="csrfmiddlewaretoken"]').val()
                },
                success(response) {
                    if (response.success) {
                        mostrarMensagem(`Importação concluída! ${response.created} registros criados.`, 'success');
                    } else {
                        mostrarMensagem(`Erro na importação: ${response.error || 'desconhecido'}`, 'danger');
                    }
                },
                error() {
                    mostrarMensagem('Erro ao enviar dados para o servidor.', 'danger');
                },
                complete() {
                    submitBtn.prop('disabled', false)
                             .html(`<i class='bx bx-upload me-2'></i> Importar`);
                }
            });

        } catch (err) {
            mostrarMensagem(`Erro ao processar o arquivo: ${err.message}`, 'danger');
            submitBtn.prop('disabled', false)
                     .html(`<i class='bx bx-upload me-2'></i> Importar`);
        }
    };

    reader.onerror = function() {
        mostrarMensagem('Falha ao ler o arquivo CSV.', 'danger');
        submitBtn.prop('disabled', false)
                 .html(`<i class='bx bx-upload me-2'></i> Importar`);
    };
}

// Mensagens de feedback
function mostrarMensagem(mensagem, tipo) {
    $('#message-container').html(`
        <div class="alert alert-${tipo} alert-dismissible fade show" role="alert">
            ${mensagem}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
}

// Associa submit dos formulários
$('#form-importar-funcionarios').submit(e => {
    e.preventDefault();
    processarCSV('#form-importar-funcionarios', '/api/csv/funcionarios/');
});
$('#form-importar-c2').submit(e => {
    e.preventDefault();
    processarCSV('#form-importar-c2', '/api/csv/clientec2/');
});
$('#form-importar-agendamentos').submit(e => {
    e.preventDefault();
    processarCSV('#form-importar-agendamentos', '/api/csv/agendamento/');
});
$('#form-importar-registermoney').submit(e => {
    e.preventDefault();
    processarCSV('#form-importar-registermoney', '/api/csv/financeiro/');
});
