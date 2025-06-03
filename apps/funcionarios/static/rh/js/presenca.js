// Sistema de Presença - JavaScript

$(document).ready(function() {
    let dataAtual = new Date();
    let mesAtual = dataAtual.getMonth();
    let anoAtual = dataAtual.getFullYear();

    // Carregar calendário inicial
    carregarCalendario(mesAtual, anoAtual);

    // Configurar botões de navegação
    $('#btn-mes-anterior').click(function() {
        mesAtual--;
        if (mesAtual < 0) {
            mesAtual = 11;
            anoAtual--;
        }
        carregarCalendario(mesAtual, anoAtual);
    });

    $('#btn-mes-proximo').click(function() {
        mesAtual++;
        if (mesAtual > 11) {
            mesAtual = 0;
            anoAtual++;
        }
        carregarCalendario(mesAtual, anoAtual);
    });

    // Configurar botão de registro
    $('#btn-registrar-presenca').click(function() {
        registrarPresenca();
    });
});

// Função para carregar o calendário
function carregarCalendario(mes, ano) {
    const grid = document.getElementById('grid-calendario');
    grid.innerHTML = '';
    
    const primeiroDia = new Date(ano, mes, 1);
    const ultimoDia = new Date(ano, mes + 1, 0);
    const diasNoMes = ultimoDia.getDate();
    const primeiroDiaSemana = primeiroDia.getDay();
    
    // Atualiza o título do mês
    const meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    document.getElementById('mes-atual').textContent = `${meses[mes]} ${ano}`;
    
    // Adiciona espaços vazios para os dias antes do primeiro dia do mês
    for (let i = 0; i < primeiroDiaSemana; i++) {
        const diaVazio = document.createElement('div');
        diaVazio.className = 'dia-card dia-vazio';
        grid.appendChild(diaVazio);
    }
    
    // Adiciona os dias do mês
    const hoje = new Date();
    const dataAtual = hoje.getDate();
    const mesAtual = hoje.getMonth();
    const anoAtual = hoje.getFullYear();
    
    for (let dia = 1; dia <= diasNoMes; dia++) {
        const diaCard = document.createElement('div');
        diaCard.className = 'dia-card';
        
        // Adiciona classes específicas baseadas na data
        if (dia === dataAtual && mes === mesAtual && ano === anoAtual) {
            diaCard.classList.add('dia-atual');
        } else if (dia < dataAtual && mes === mesAtual && ano === anoAtual) {
            diaCard.classList.add('dia-passado');
        } else if (dia > dataAtual && mes === mesAtual && ano === anoAtual) {
            diaCard.classList.add('dia-futuro');
        }
        
        // Número do dia
        const numeroDia = document.createElement('div');
        numeroDia.className = 'numero-dia';
        numeroDia.textContent = dia;
        diaCard.appendChild(numeroDia);
        
        // Status do registro
        const statusRegistro = document.createElement('div');
        statusRegistro.className = 'status-registro';
        diaCard.appendChild(statusRegistro);
        
        // Botão de registro (apenas para o dia atual)
        if (dia === dataAtual && mes === mesAtual && ano === anoAtual) {
            const btnRegistrar = document.createElement('button');
            btnRegistrar.className = 'btn btn-registrar btn-primary';
            btnRegistrar.innerHTML = '<i class="bx bx-log-in-circle me-2"></i> Registrar Entrada';
            btnRegistrar.onclick = function() {
                registrarPresenca();
            };
            diaCard.appendChild(btnRegistrar);
        }
        
        // Adiciona evento de clique para mostrar registros
        diaCard.onclick = function() {
            const data = `${ano}-${String(mes + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
            carregarRegistrosDia(data, diaCard);
        };
        
        grid.appendChild(diaCard);
    }
}

// Função para carregar registros do dia
function carregarRegistrosDia(data, card) {
    console.log(`[PRESENCA] Carregando registros para data: ${data}`);
    const url = `/rh/api/presenca/registros/?data=${data}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('[PRESENCA] Registros recebidos:', data);
            const registros = data.hoje.registros;
            const statusDiv = card.querySelector('.status-registro');
            const btnRegistrar = card.querySelector('.btn-registrar');
            
            if (registros && registros.length > 0) {
                statusDiv.innerHTML = `
                    <div class="badge bg-success">
                        <i class="bx bx-check-circle me-1"></i> Presente
                    </div>
                `;
                if (btnRegistrar) {
                    btnRegistrar.style.display = 'none';
                }
            } else {
                statusDiv.innerHTML = `
                    <div class="badge bg-danger">
                        <i class="bx bx-x-circle me-1"></i> Ausente
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('[PRESENCA] Erro ao carregar registros:', error);
            mostrarErro('Erro ao carregar registros do dia');
        });
}

// Função para registrar presença
function registrarPresenca() {
    console.log('[PRESENCA] Iniciando registro de presença');
    const url = `/rh/api/presenca/registrar/`;
    
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            tipo: 'ENTRADA'
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('[PRESENCA] Resposta do registro:', data);
        if (data.success) {
            mostrarSucesso(data.message);
            // Recarregar calendário para atualizar status
            const dataAtual = new Date();
            carregarCalendario(dataAtual.getMonth(), dataAtual.getFullYear());
        } else {
            mostrarErro(data.error || 'Erro ao registrar presença');
        }
    })
    .catch(error => {
        console.error('[PRESENCA] Erro ao registrar presença:', error);
        mostrarErro('Erro ao registrar presença');
    });
}

// Função para mostrar mensagem de sucesso
function mostrarSucesso(mensagem) {
    // Implementar usando o sistema de notificações do seu template
    console.log('[PRESENCA] Sucesso:', mensagem);
}

// Função para mostrar mensagem de erro
function mostrarErro(mensagem) {
    // Implementar usando o sistema de notificações do seu template
    console.error('[PRESENCA] Erro:', mensagem);
}

// Função para obter o token CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    console.log('[PRESENCA] Inicializando módulo de presença');
    const dataAtual = new Date();
    carregarCalendario(dataAtual.getMonth(), dataAtual.getFullYear());
    
    // Eventos dos botões de navegação
    document.getElementById('btn-mes-anterior').addEventListener('click', function() {
        const mesAtual = parseInt(document.getElementById('mes-atual').textContent.split(' ')[0]);
        const anoAtual = parseInt(document.getElementById('mes-atual').textContent.split(' ')[1]);
        const novaData = new Date(anoAtual, mesAtual - 1, 1);
        carregarCalendario(novaData.getMonth(), novaData.getFullYear());
    });
    
    document.getElementById('btn-mes-proximo').addEventListener('click', function() {
        const mesAtual = parseInt(document.getElementById('mes-atual').textContent.split(' ')[0]);
        const anoAtual = parseInt(document.getElementById('mes-atual').textContent.split(' ')[1]);
        const novaData = new Date(anoAtual, mesAtual + 1, 1);
        carregarCalendario(novaData.getMonth(), novaData.getFullYear());
    });
}); 