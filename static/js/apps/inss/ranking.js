$(document).ready(function() {
    // Período fixo para as chamadas da API
    var periodoAtual = 'meta';

    // FUNÇÃO: Atualiza os dados dos cards
    function updateCards() {
        $.getJSON("/inss/api/inss/cards/" + periodoAtual + "/", function(data) {
            console.log("Dados da API cards:", data);

            // Atualiza o card "Meta Geral"
            if (data.meta_geral) {
                $(".dashboard-card.meta-geral .card-value").text(data.meta_geral.valor || 'R$ 0,00');
                $(".dashboard-card.meta-geral .percentage-value").text((data.meta_geral.percentual || 0) + "%");
            }

            // Atualiza o card "Meta Empresa"
            if (data.meta_empresa) { 
                $(".dashboard-card.meta-empresa .card-value").text(data.meta_empresa.valor || 'R$ 0,00');
                $(".dashboard-card.meta-empresa .percentage-value").text((data.meta_empresa.percentual || 0) + "%");
            }

            // Atualiza o card "Meta Setor"
            if (data.meta_setor) {
                $(".dashboard-card.meta-setor .card-value").text(data.meta_setor.valor || 'R$ 0,00');
                $(".dashboard-card.meta-setor .percentage-value").text((data.meta_setor.percentual || 0) + "%");
            }

            // Atualiza o card "Qtd Em Loja"
            if (data.quantidade) {
                $(".dashboard-card.quantidade .card-value").text(data.quantidade.valor || 0);
            }

            // Atualiza o card "Qtd Confirmados"
            if (data.agendamentos) {
                $(".dashboard-card.agendamentos .card-value").text(data.agendamentos.valor || 0);
            }

            // Removido: Atualiza informações do período

        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Erro ao carregar dados dos cards:", textStatus, errorThrown);
        });
    }

    // FUNÇÃO: Atualiza os dados do pódium (top 3 lojas)
    function updatePodium() {
        $.getJSON("/inss/api/inss/podium/" + periodoAtual + "/", function(data) {
            console.log("Dados do pódio:", data);
            var podium = data.podium;
            // Atualiza Top 2 (índice 1)
            if (podium[1]) {
                var top2 = podium[1];
                // Verifica se a loja tem um logo válido e acessível
                var logoUrl = "/static/img/default-store.png";
                if (top2.logo && top2.logo.startsWith("/")) {
                    logoUrl = top2.logo;
                }
                $(".top2.box__ranking .foto__pos img").attr("src", logoUrl);
                $(".top2.box__ranking .foto__pos img").attr("alt", top2.nome);
                $(".top2.box__ranking .circle__position").text("2");
                $(".top2.box__ranking .valor").text(top2.valor);
                $(".top2.box__ranking .bar .nome").text(top2.nome);
            } else {
                $(".top2.box__ranking .foto__pos img").attr("src", "/static/img/default-store.png");
                $(".top2.box__ranking .foto__pos img").attr("alt", "Posição Disponível");
                $(".top2.box__ranking .circle__position").text("2");
                $(".top2.box__ranking .valor").text("R$ 0,00");
                $(".top2.box__ranking .bar .nome").text("Posição Disponível");
            }
            // Atualiza Top 1 (índice 0)
            if (podium[0]) {
                var top1 = podium[0];
                // Verifica se a loja tem um logo válido e acessível
                var logoUrl = "/static/img/default-store.png";
                if (top1.logo && top1.logo.startsWith("/")) {
                    logoUrl = top1.logo;
                }
                $(".top1.box__ranking .foto__pos img").attr("src", logoUrl);
                $(".top1.box__ranking .foto__pos img").attr("alt", top1.nome);
                $(".top1.box__ranking .circle__position").text("1");
                $(".top1.box__ranking .valor").text(top1.valor);
                $(".top1.box__ranking .bar .nome").text(top1.nome);
            } else {
                $(".top1.box__ranking .foto__pos img").attr("src", "/static/img/default-store.png");
                $(".top1.box__ranking .foto__pos img").attr("alt", "Posição Disponível");
                $(".top1.box__ranking .circle__position").text("1");
                $(".top1.box__ranking .valor").text("R$ 0,00");
                $(".top1.box__ranking .bar .nome").text("Posição Disponível");
            }
            // Atualiza Top 3 (índice 2)
            if (podium[2]) {
                var top3 = podium[2];
                // Verifica se a loja tem um logo válido e acessível
                var logoUrl = "/static/img/default-store.png";
                if (top3.logo && top3.logo.startsWith("/")) {
                    logoUrl = top3.logo;
                }
                $(".top3.box__ranking .foto__pos img").attr("src", logoUrl);
                $(".top3.box__ranking .foto__pos img").attr("alt", top3.nome);
                $(".top3.box__ranking .circle__position").text("3");
                $(".top3.box__ranking .valor").text(top3.valor);
                $(".top3.box__ranking .bar .nome").text(top3.nome);
            } else {
                $(".top3.box__ranking .foto__pos img").attr("src", "/static/img/default-store.png");
                $(".top3.box__ranking .foto__pos img").attr("alt", "Posição Disponível");
                $(".top3.box__ranking .circle__position").text("3");
                $(".top3.box__ranking .valor").text("R$ 0,00");
                $(".top3.box__ranking .bar .nome").text("Posição Disponível");
            }

            // Removido: Atualiza informações do período

        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Erro ao carregar dados do pódium:", textStatus, errorThrown);
        });
    }

    // Variável global para armazenar a ordem anterior (usando o nome dos atendentes)
    var previousOrder = [];

    function updateTabela() {
        $.getJSON("/inss/api/inss/tabela/" + periodoAtual + "/", function(data) {
            var ranking = data.ranking_data;
            var tbody = $("table tbody");
            var newOrder = [];
            var newRows = [];

            // Cria as novas linhas e armazena a nova ordem (usando o atributo data-nome)
            if (ranking && ranking.length > 0) {
                $.each(ranking, function(i, item) {
                    newOrder.push(item.nome);
                    var row = $("<tr></tr>").attr("data-nome", item.nome);
                    row.append("<td>" + item.posicao + "</td>");
                    if (item.foto) {
                        row.append("<td><img src='" + item.foto + "' alt='" + item.nome + "' class='ranking-foto'></td>");
                    } else {
                        row.append("<td><img src='/static/img/geral/default_image.png' alt='" + item.nome + "' class='ranking-foto'></td>");
                    }
                    row.append("<td>" + item.nome + "</td>");
                    row.append("<td>" + item.qtd_agendados + "</td>");
                    row.append("<td>" + item.qtd_emloja + "</td>");
                    newRows.push(row);
                });
            } else {
                var row = $("<tr></tr>");
                row.append("<td colspan='5' class='text-center'>Nenhum dado disponível para o período</td>");
                newRows.push(row);
                newOrder = [];
            }

            // Define a altura de uma linha (pode ser ajustada conforme necessário)
            var rowHeight = $("table tbody tr").outerHeight() || 50;

            // Se já houver uma ordem anterior, compara e anima as linhas que mudaram de posição
            if (previousOrder.length > 0) {
                newRows.forEach(function(newRow, index) {
                    var nome = newRow.attr("data-nome");
                    var oldIndex = previousOrder.indexOf(nome);
                    // Se o atendente existia anteriormente e sua posição mudou
                    if (oldIndex !== -1 && oldIndex !== index) {
                        var diff = (oldIndex - index) * rowHeight;
                        // Aplica posição relativa e anima a mudança do valor de 'top'
                        newRow.css({ position: "relative", top: diff + "px" });
                        newRow.animate({ top: "0px" }, 500);
                    }
                });
            }

            // Atualiza o conteúdo da tabela com as novas linhas
            tbody.empty();
            $.each(newRows, function(i, row) {
                tbody.append(row);
            });

            // Atualiza a ordem anterior
            previousOrder = newOrder;

            // Removido: Atualiza informações do período

        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error("Erro ao carregar dados da tabela:", textStatus, errorThrown);
            // Exibe mensagem de erro na tabela
            $("table tbody").html("<tr><td colspan='5' class='text-center text-danger'>Erro ao carregar dados. Tente novamente mais tarde.</td></tr>");
        });
    }

    // Removido: FUNÇÃO: Atualiza as informações do período (updatePeriodoInfo)

    // FUNÇÃO: Atualiza todas as informações (cards, pódium e tabela)
    function updateAll() {
        updateCards();
        updatePodium();
        updateTabela();
    }

    // Removido: Criação dinâmica dos botões de seleção de período (criarBotoesPeriodo)

    // Atualiza os handlers de ordenação para todas as colunas
    function atualizarHandlersOrdenacao() {
        // Remove handlers existentes para evitar duplicação
        $('.sort-icon').off('click');
        
        // Adiciona os handlers para todos os ícones de ordenação
        $('.sort-icon').on('click', function() {
            var column = $(this).data('column');
            var tbody = $('table tbody');
            var rows = Array.from(tbody.find('tr'));
            var currentIcon = $(this).find('i');
            
            // Alterna entre ascendente e descendente
            var isAscending = currentIcon.hasClass('fa-sort') || currentIcon.hasClass('fa-sort-down');
            
            // Reseta todos os ícones para o estado padrão
            $('.sort-icon i').removeClass('fa-sort-up fa-sort-down').addClass('fa-sort');
            
            // Atualiza apenas o ícone clicado
            currentIcon.removeClass('fa-sort');
            currentIcon.addClass(isAscending ? 'fa-sort-up' : 'fa-sort-down');
            
            // Ordena as linhas
            rows.sort(function(a, b) {
                var valueA, valueB;
                
                if (column === 'rank') {
                    valueA = parseInt($(a).find('td').eq(0).text(), 10);
                    valueB = parseInt($(b).find('td').eq(0).text(), 10);
                } else if (column === 'nome') {
                    valueA = $(a).find('td').eq(2).text().toLowerCase();
                    valueB = $(b).find('td').eq(2).text().toLowerCase();
                } else if (column === 'agendados') {
                    valueA = parseInt($(a).find('td').eq(3).text(), 10);
                    valueB = parseInt($(b).find('td').eq(3).text(), 10);
                } else if (column === 'taxa') { // "taxa" corresponde à coluna "Em Loja"
                    valueA = parseInt($(a).find('td').eq(4).text(), 10);
                    valueB = parseInt($(b).find('td').eq(4).text(), 10);
                }
                
                if (isNaN(valueA)) valueA = 0;
                if (isNaN(valueB)) valueB = 0;
                
                return isAscending ? 
                    (valueA > valueB ? 1 : valueA < valueB ? -1 : 0) : 
                    (valueA < valueB ? 1 : valueA > valueB ? -1 : 0);
            });
            
            // Reinsere as linhas ordenadas
            $.each(rows, function(index, row) {
                tbody.append(row);
            });
        });
    }

    // Função de inicialização
    function inicializar() {
        console.log("Inicializando ranking INSS...");
        
        // Removido: Cria os botões de seleção de período
        
        // Atualiza os handlers de ordenação
        atualizarHandlersOrdenacao();
        
        // Atualiza os dados inicialmente
        updateAll();
        
        // Atualiza os dados a cada 30 segundos
        setInterval(updateAll, 30000);
    }

    // Inicializa a página
    inicializar();
});
