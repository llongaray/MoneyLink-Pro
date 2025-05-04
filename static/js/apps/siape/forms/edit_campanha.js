$(document).ready(function() {

    // Função para carregar os dados de departamentos e campanhas nos selects
    function carregarInfoCamp() {
      $.ajax({
        url: "/siape/api/get/info-camp/",
        type: "GET",
        success: function(response) {
          // Preenche o seletor de setores
          var setorSelect = $("#setor_id");
          setorSelect.empty();
          setorSelect.append("<option value=''>Selecione um setor</option>");
          $.each(response.setores, function(index, setor) {
            setorSelect.append("<option value='" + setor.id + "'>" + setor.nome + "</option>");
          });
  
          // Preenche os seletores de campanhas: editar e importar CSV
          var campEditSelect = $("#filtro_campanha");
          var campImportSelect = $("#campanha_id");
          campEditSelect.empty();
          campImportSelect.empty();
          campEditSelect.append("<option value=''>Selecione uma campanha</option>");
          campImportSelect.append("<option value=''>Selecione uma campanha</option>");
          $.each(response.campanhas, function(index, campanha) {
            var option = "<option value='" + campanha.id + "'>" + campanha.nome + "</option>";
            campEditSelect.append(option);
            campImportSelect.append(option);
          });
        },
        error: function(xhr, status, error) {
          console.error("Erro ao carregar informações dos selects:", error);
        }
      });
    }
  
    // Carrega as informações assim que a página é carregada
    carregarInfoCamp();
  
    // 📝 Handler para criação de campanha
    $("#form-criar-campanha").on("submit", function(e) {
      e.preventDefault(); // Impede o envio tradicional do formulário
  
      // Coleta os dados dos inputs
      var formData = {
        nome_campanha: $("#nome_campanha").val(),
        setor_id: $("#setor_id").val()
      };
  
      $.ajax({
        url: "/siape/api/post/siape/campanha/",
        type: "POST",
        data: formData,
        success: function(response) {
          alert(response.texto);
          if(response.classe === 'success') {
            // Limpa o formulário se a criação for bem-sucedida
            $("#form-criar-campanha")[0].reset();
            // Atualiza os selects com a nova campanha criada
            carregarInfoCamp();
          }
        },
        error: function(xhr, status, error) {
          alert("Erro ao criar campanha: " + error);
          console.error("Erro ao criar campanha:", error);
        }
      });
    });
  
    // 📂 Handler para importação de CSV
    $("#form-importar-csv").on("submit", function(e) {
      e.preventDefault();
  
      // Prepara o FormData para envio de arquivos
      var formElement = document.getElementById("form-importar-csv");
      var formData = new FormData(formElement);
  
      $.ajax({
        url: "/siape/api/post/importar-csv/",
        type: "POST",
        data: formData,
        processData: false,  // Necessário para envio de FormData
        contentType: false,  // Necessário para envio de FormData
        success: function(response) {
            // Constrói a mensagem de sucesso baseada na resposta
            var successMsg = `Importação concluída!\n`;
            successMsg += `Clientes novos: ${response.clientes_novos}\n`;
            successMsg += `Clientes atualizados: ${response.clientes_atualizados}\n`;
            if (response.erros && response.erros.length > 0) {
                successMsg += `\n${response.erros.length} Linha(s) com erro:\n`;
                // Limita a exibição dos erros no alert para não ficar muito grande
                successMsg += response.erros.slice(0, 5).join('\n');
                if (response.erros.length > 5) {
                    successMsg += '\n(e mais...)';
                }
                alert(successMsg); // Mostra alerta com detalhes e erros
            } else {
                alert(successMsg + "Nenhuma linha com erro detectada."); // Mensagem de sucesso sem erros
            }
  
          // Limpa o formulário após importação
          $("#form-importar-csv")[0].reset();
          // Atualiza os selects, se necessário
          carregarInfoCamp();
  
        },
        error: function(xhr, status, error) {
          // Tenta pegar a mensagem de erro específica da API
          var errorMsg = "Erro ao importar CSV."; // Mensagem padrão
          if (xhr.responseJSON && xhr.responseJSON.mensagem) {
            errorMsg = xhr.responseJSON.mensagem; // Usa a mensagem da API se existir
          } else {
            // Se não houver mensagem específica, usa o erro padrão do AJAX
            errorMsg = `Erro ao importar CSV: ${status} - ${error}`;
          }
          alert(errorMsg); // Mostra a mensagem de erro
          console.error("Erro ao importar CSV:", xhr.responseText); // Loga a resposta completa para debug
        }
      });
    });
  
    // 📥 Handler para baixar o modelo CSV (Excel)
    $("#btn-baixar-modelo").on("click", function(e) {
      e.preventDefault();
  
      // Define o cabeçalho do CSV com separador ";" sem acentos e com underscores no lugar de espaços
      var csvHeader = [
        "Nome", "CPF", "UF", "RJur", "Situacao_Funcional",
        "Renda_Bruta", "Bruta_5", "Utilizado_5", "Saldo_5",
        "Bruta_Beneficio_5", "Utilizado_Beneficio_5", "Saldo_Beneficio_5",
        "Bruta_35", "Utilizado_35", "Saldo_35", "Total_Utilizado", "Total_Saldo",
        "Matricula", "Banco", "Orgao", "Rebrica", "Parcela", "Prazo_Restante",
        "Tipo_de_Contrato", "Numero_do_Contrato"
      ].join(";") + "\n";
  
      // Cria um blob com o conteúdo CSV
      var blob = new Blob([csvHeader], { type: "text/csv;charset=utf-8;" });
      var url = URL.createObjectURL(blob);
  
      // Cria um link temporário e dispara o download
      var a = document.createElement("a");
      a.href = url;
      a.download = "modelo_siape.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  });
  