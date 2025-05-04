$(document).ready(function() {
    let dashboardData = {}; // Store fetched data globally within this scope

    // --- Helper Functions ---
    function formatCurrency(value) {
        if (value === null || value === undefined) return 'R$ 0,00';
        const number = Number(value);
        if (isNaN(number)) return 'R$ 0,00';
        return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function formatPercentage(value) {
        if (value === null || value === undefined) return '0.0%';
        const number = Number(value);
        if (isNaN(number)) return '0.0%';
        return number.toFixed(1) + '%';
    }

    function updateCardValue(cardId, value, formatter = formatCurrency) {
        const element = $(`#${cardId} .value`);
        if (element.length) {
            element.text(formatter(value));
            // Optional: Add a subtle animation on update
            element.addClass('updated');
            setTimeout(() => element.removeClass('updated'), 500);
        } else {
            console.warn(`Element not found for card value: ${cardId}`);
        }
    }

     function populateSelect(selectId, options, valueKey = 'id', textKey = 'nome', defaultOptionValue = "", defaultOptionText = 'Selecione...') {
        const select = $(`#${selectId}`);
        if (!select.length) {
            console.warn(`Select element not found: ${selectId}`);
            return;
        }
        select.empty(); // Clear existing options
        select.append($('<option>', { value: defaultOptionValue, text: defaultOptionText })); // Add default option
        options.forEach(option => {
            select.append($('<option>', {
                value: option[valueKey],
                text: option[textKey]
            }));
        });
    }

    // --- Data Fetching and Initial Population ---
    function fetchDataAndPopulate() {
        console.log("Fetching dashboard data...");
        $.ajax({
            url: '/api/dashboard/', // Use the correct URL (removed /administrativo prefix)
            method: 'GET',
            dataType: 'json',
            success: function(data) {
                console.log("Data received:", data);
                dashboardData = data; // Store data
                populateDashboard(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Error fetching dashboard data:", textStatus, errorThrown);
                $('#last-update-time').text('Erro ao carregar dados');
                // Display a user-friendly error message if needed
            }
        });
    }

    function populateDashboard(data) {
        if (!data) return;

        // === SESSÃO: FINANCEIRO ===
        console.log("Populating Financeiro...");
        if (data.financeiro) {
            // Populate Empresa Select
            populateSelect('select-empresa-financeiro', data.financeiro.empresas_list || [], 'id', 'nome', "", "Todas as Empresas");
            updateFinanceiroEmpresaCards(); // Initial state (Todas)

            // Interno Cards
            updateCardValue('card-interno-fat-ano', data.financeiro.interno?.faturamento_ano);
            updateCardValue('card-interno-fat-mes', data.financeiro.interno?.faturamento_mes);
            // Franquia Cards
            updateCardValue('card-franquia-fat-ano', data.financeiro.franquia?.faturamento_ano);
            updateCardValue('card-franquia-fat-mes', data.financeiro.franquia?.faturamento_mes);
            // Filial Cards
            updateCardValue('card-filial-fat-ano', data.financeiro.filial?.faturamento_ano);
            updateCardValue('card-filial-fat-mes', data.financeiro.filial?.faturamento_mes);
        }

        // === SESSÃO: LOJAS ===
        console.log("Populating Lojas...");
        if (data.lojas) {
            // Sede Cards
            const sede = data.lojas.sede || {};
            updateCardValue('card-sede-fat-ano', sede.faturamento_ano);
            updateCardValue('card-sede-fat-mes', sede.faturamento_mes);
            updateCardValue('card-sede-taxa-comp', sede.taxa_comparecimento, formatPercentage);
            updateCardValue('card-sede-cli-rua', sede.clientes_rua, val => val); // No formatting
            updateCardValue('card-sede-neg-fechados', sede.negocios_fechados, val => val);
            updateCardValue('card-sede-agendamentos', sede.agendamentos, val => val);
            updateCardValue('card-sede-sem-interesse', sede.sem_interesse, val => val);

            // Populate Filial Select
            populateSelect('select-filial-lojas', data.lojas.filiais_list || [], 'id', 'nome', "", "Todas as Filiais");
            updateLojasFilialCards(); // Initial state (Todas)

            // Populate Franquia Select
            populateSelect('select-franquia-lojas', data.lojas.franquias_list || [], 'id', 'nome', "", "Todas as Franquias");
            updateLojasFranquiaCards(); // Initial state (Todas)
        }

        // === SESSÃO: RH ===
        console.log("Populating RH...");
        if (data.rh) {
            // Geral Cards
            updateCardValue('card-rh-func-ativos', data.rh.geral?.ativos, val => val);
            updateCardValue('card-rh-func-inativos', data.rh.geral?.inativos, val => val);

            // Populate Funcionário Select
            populateSelect('select-funcionario-rh', data.rh.funcionarios_list || [], 'id', 'nome', "", "Selecione um funcionário");
            updateRhFuncionarioCards(); // Initial state (None selected)
        }

        // === SESSÃO: METAS ===
        console.log("Populating Metas...");
        if (data.metas) {
            // Populate Meta Ativa Select
            populateSelect('select-meta-ativa', data.metas.ativas_list || [], 'id', 'titulo', "", "Selecione uma meta ativa");
            updateMetaAtivaCards(); // Initial state (None selected)

            // Populate Meta Inativada Select
            populateSelect('select-meta-inativada', data.metas.inativadas_list || [], 'id', 'titulo', "", "Selecione uma meta inativa");
            updateMetaInativadaCards(); // Initial state (None selected)
        }

        // === TIMESTAMP ===
        if (data.timestamp) {
            try {
                const date = new Date(data.timestamp);
                $('#last-update-time').text(date.toLocaleString('pt-BR'));
            } catch (e) {
                $('#last-update-time').text('Data inválida');
            }
        } else {
            $('#last-update-time').text('Não disponível');
        }
         console.log("Dashboard populated.");
    }

    // --- Update Functions for Selectors ---

    // Financeiro - Empresa
    function updateFinanceiroEmpresaCards() {
        const selectedEmpresaId = $('#select-empresa-financeiro').val();
        let fatAno = 0;
        let fatMes = 0;

        if (selectedEmpresaId && dashboardData.financeiro?.empresas_list) {
            const empresa = dashboardData.financeiro.empresas_list.find(e => e.id == selectedEmpresaId);
            if (empresa) {
                fatAno = empresa.faturamento_ano;
                fatMes = empresa.faturamento_mes;
            }
        } else if (!selectedEmpresaId && dashboardData.financeiro?.empresas_list) {
            // "Todas as Empresas" - Sum all
            dashboardData.financeiro.empresas_list.forEach(empresa => {
                fatAno += Number(empresa.faturamento_ano || 0);
                fatMes += Number(empresa.faturamento_mes || 0);
            });
        }
        updateCardValue('card-empresa-fat-ano', fatAno);
        updateCardValue('card-empresa-fat-mes', fatMes);
    }

    // Lojas - Filial
    function updateLojasFilialCards() {
        const selectedFilialId = $('#select-filial-lojas').val();
        let metrics = {
            faturamento_ano: 0, faturamento_mes: 0, taxa_comparecimento: 0,
            clientes_rua: 0, negocios_fechados: 0, agendamentos: 0, sem_interesse: 0
        };
        let totalAgendamentos = 0;
        let totalComparecimentos = 0; // Needed for aggregated percentage

        if (selectedFilialId && dashboardData.lojas?.filiais_list) {
             const filial = dashboardData.lojas.filiais_list.find(f => f.id == selectedFilialId);
            if (filial && filial.metrics) {
                metrics = filial.metrics;
            }
        } else if (!selectedFilialId && dashboardData.lojas?.filiais_list) {
             // "Todas as Filiais" - Sum metrics
             dashboardData.lojas.filiais_list.forEach(filial => {
                 if (filial.metrics) {
                     metrics.faturamento_ano += Number(filial.metrics.faturamento_ano || 0);
                     metrics.faturamento_mes += Number(filial.metrics.faturamento_mes || 0);
                     metrics.clientes_rua += Number(filial.metrics.clientes_rua || 0);
                     metrics.negocios_fechados += Number(filial.metrics.negocios_fechados || 0);
                     metrics.agendamentos += Number(filial.metrics.agendamentos || 0);
                     metrics.sem_interesse += Number(filial.metrics.sem_interesse || 0);
                     // For aggregated percentage, we need sum of components
                     totalAgendamentos += Number(filial.metrics.agendamentos || 0); // Assuming 'agendamentos' is the base
                     // Assuming 'comparecimentos' can be derived or is provided. If derived from taxa:
                     // totalComparecimentos += (Number(filial.metrics.taxa_comparecimento || 0)/100) * Number(filial.metrics.agendamentos || 0);
                     // Using the taxa directly is simpler but less accurate for aggregation. Let's use the agendamentos count as provided.
                     // The backend should ideally provide summed comparecimentos if needed for accurate aggregated %.
                     // Using individual taxa for sum isn't mathematically correct. We'll display average/sum based on available data.
                     // Let's display the summed agendamentos and calculate an *average* taxa if needed, or rely on backend calculation if provided.
                     // For simplicity, we'll just sum the raw counts here. Taxa % will be inaccurate when summed.
                 }
             });
             // Calculate average taxa if needed (example - may not be required)
             // if(totalAgendamentos > 0) metrics.taxa_comparecimento = (totalComparecimentos / totalAgendamentos) * 100;
             // If the backend sends an aggregated taxa for "Todas", use that instead.
             // For now, we will just show the summed raw counts. Let's zero out the taxa for "Todas".
             metrics.taxa_comparecimento = 0; // Indicate taxa is not applicable/accurate for sum.
        }

        updateCardValue('card-filial-loja-fat-ano', metrics.faturamento_ano);
        updateCardValue('card-filial-loja-fat-mes', metrics.faturamento_mes);
        updateCardValue('card-filial-loja-taxa-comp', metrics.taxa_comparecimento, formatPercentage);
        updateCardValue('card-filial-loja-cli-rua', metrics.clientes_rua, val => val);
        updateCardValue('card-filial-loja-neg-fechados', metrics.negocios_fechados, val => val);
        updateCardValue('card-filial-loja-agendamentos', metrics.agendamentos, val => val);
        updateCardValue('card-filial-loja-sem-interesse', metrics.sem_interesse, val => val);
    }


    // Lojas - Franquia (Similar to Filial)
    function updateLojasFranquiaCards() {
        const selectedFranquiaId = $('#select-franquia-lojas').val();
        let metrics = {
            faturamento_ano: 0, faturamento_mes: 0, taxa_comparecimento: 0,
            clientes_rua: 0, negocios_fechados: 0, agendamentos: 0, sem_interesse: 0
        };
        // Add aggregation logic similar to updateLojasFilialCards if needed for "Todas as Franquias"

        if (selectedFranquiaId && dashboardData.lojas?.franquias_list) {
             const franquia = dashboardData.lojas.franquias_list.find(f => f.id == selectedFranquiaId);
            if (franquia && franquia.metrics) {
                metrics = franquia.metrics;
            }
        } else if (!selectedFranquiaId && dashboardData.lojas?.franquias_list) {
             // "Todas as Franquias" - Sum metrics
              dashboardData.lojas.franquias_list.forEach(franquia => {
                 if (franquia.metrics) {
                     metrics.faturamento_ano += Number(franquia.metrics.faturamento_ano || 0);
                     metrics.faturamento_mes += Number(franquia.metrics.faturamento_mes || 0);
                     metrics.clientes_rua += Number(franquia.metrics.clientes_rua || 0);
                     metrics.negocios_fechados += Number(franquia.metrics.negocios_fechados || 0);
                     metrics.agendamentos += Number(franquia.metrics.agendamentos || 0);
                     metrics.sem_interesse += Number(franquia.metrics.sem_interesse || 0);
                 }
             });
             metrics.taxa_comparecimento = 0; // Taxa aggregated isn't straightforward.
        }


        updateCardValue('card-franquia-loja-fat-ano', metrics.faturamento_ano);
        updateCardValue('card-franquia-loja-fat-mes', metrics.faturamento_mes);
        updateCardValue('card-franquia-loja-taxa-comp', metrics.taxa_comparecimento, formatPercentage);
        updateCardValue('card-franquia-loja-cli-rua', metrics.clientes_rua, val => val);
        updateCardValue('card-franquia-loja-neg-fechados', metrics.negocios_fechados, val => val);
        updateCardValue('card-franquia-loja-agendamentos', metrics.agendamentos, val => val);
        updateCardValue('card-franquia-loja-sem-interesse', metrics.sem_interesse, val => val);
    }

    // RH - Desempenho Funcionário
    function updateRhFuncionarioCards() {
        const selectedFuncId = $('#select-funcionario-rh').val();
        let desempenho = {
            faturamento_ano: 0, faturamento_mes: 0, clientes_concluidos: 0, comissao_total_mes: 0
        };

        if (selectedFuncId && dashboardData.rh?.desempenho) {
            desempenho = dashboardData.rh.desempenho[selectedFuncId] || desempenho;
        }
        // If no selection, keep default zero values

        updateCardValue('card-rh-func-fat-ano', desempenho.faturamento_ano);
        updateCardValue('card-rh-func-fat-mes', desempenho.faturamento_mes);
        updateCardValue('card-rh-func-clientes', desempenho.clientes_concluidos, val => val);
        updateCardValue('card-rh-func-comissao', desempenho.comissao_total_mes);
    }

    // Metas - Ativa
    function updateMetaAtivaCards() {
        const selectedMetaId = $('#select-meta-ativa').val();
        let meta = {
            valor_meta: 0, valor_atingido: 0, valor_restante: 0, status: '-', percentual: 0
        };

        if (selectedMetaId && dashboardData.metas?.ativas_list) {
            meta = dashboardData.metas.ativas_list.find(m => m.id == selectedMetaId) || meta;
        }
        // If no selection, keep default values

        updateCardValue('card-meta-ativa-valor', meta.valor_meta);
        updateCardValue('card-meta-ativa-atingido', meta.valor_atingido);
        updateCardValue('card-meta-ativa-restante', meta.valor_restante);
        updateCardValue('card-meta-ativa-status', meta.status, val => val); // No formatting
    }

    // Metas - Inativada
    function updateMetaInativadaCards() {
        const selectedMetaId = $('#select-meta-inativada').val();
        let meta = {
            valor_meta: 0, valor_atingido: 0, valor_restante: 0, status: '-'
        };

        if (selectedMetaId && dashboardData.metas?.inativadas_list) {
            meta = dashboardData.metas.inativadas_list.find(m => m.id == selectedMetaId) || meta;
        }
        // If no selection, keep default values

        updateCardValue('card-meta-inativa-valor', meta.valor_meta);
        updateCardValue('card-meta-inativa-atingido', meta.valor_atingido);
        updateCardValue('card-meta-inativa-restante', meta.valor_restante);
        updateCardValue('card-meta-inativa-status', meta.status, val => val); // No formatting
    }


    // --- Event Listeners ---
    $('#select-empresa-financeiro').on('change', updateFinanceiroEmpresaCards);
    $('#select-filial-lojas').on('change', updateLojasFilialCards);
    $('#select-franquia-lojas').on('change', updateLojasFranquiaCards);
    $('#select-funcionario-rh').on('change', updateRhFuncionarioCards);
    $('#select-meta-ativa').on('change', updateMetaAtivaCards);
    $('#select-meta-inativada').on('change', updateMetaInativadaCards);

    // --- Initial Load ---
    fetchDataAndPopulate();

});

// Adicione um pouco de CSS para a animação de atualização (opcional)
const style = document.createElement('style');
style.textContent = `
.value.updated {
  animation: pulse- nhẹ 0.5s ease-out;
}
@keyframes pulse- nhẹ {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); opacity: 0.8; }
  100% { transform: scale(1); opacity: 1; }
}
`;
document.head.append(style);
