$(document).ready(function() {
  console.log("Documento pronto, inicializando scripts...");

  // 📥 Carrega dados de setores e campanhas
  function carregarInfoCamp() {
    console.log("Iniciando carregamento de informações de campanhas e setores...");
    $.ajax({
      url: "/siape/api/get/info-camp/",
      type: "GET",
      success: function(response) {
        console.log("Dados recebidos com sucesso:", response);

        // Setores
        var setorSelect = $("#setor_id").empty()
          .append("<option value=''>Selecione um setor</option>");
        response.setores.forEach(function(setor) {
          setorSelect.append(
            $("<option>").val(setor.id).text(setor.nome)
          );
        });

        // Campanhas
        var campEdit   = $("#filtro_campanha").empty()
                            .append("<option value=''>Selecione uma campanha</option>"),
            campImport = $("#campanha_id").empty()
                            .append("<option value=''>Selecione uma campanha</option>");
        response.campanhas.forEach(function(camp) {
          var opt = $("<option>").val(camp.id).text(camp.nome);
          campEdit.append(opt.clone());
          campImport.append(opt);
        });
      },
      error: function(xhr, status, err) {
        console.error("Erro ao carregar selects:", err);
      }
    });
  }

  // Chamada inicial
  carregarInfoCamp();

  // 🆕 Criar campanha
  $("#form-criar-campanha").on("submit", function(e) {
    e.preventDefault();
    var dados = {
      nome_campanha: $("#nome_campanha").val(),
      setor_id:      $("#setor_id").val()
    };
    $.post("/siape/api/post/siape/campanha/", dados)
      .done(function(resp) {
        alert(resp.texto);
        if (resp.classe === "success") {
          $("#form-criar-campanha")[0].reset();
          carregarInfoCamp();
        }
      })
      .fail(function(xhr, status, err) {
        alert("Erro ao criar campanha: " + err);
        console.error("Erro criar campanha:", err);
      });
  });

  // 📂 Importar CSV via FormData (sem JSON gigante)
  $("#form-importar-csv").on("submit", function(e) {
    e.preventDefault();

    var fileInput = $("#form-importar-csv input[type=file]")[0];
    if (!fileInput.files.length) {
      return alert("Selecione um arquivo CSV antes de enviar.");
    }
    var file = fileInput.files[0];

    // Exibe tamanho
    var mb = (file.size / 1024 / 1024).toFixed(2);
    $("#upload-size").text("Tamanho do arquivo: " + mb + " MB");

    var $prog = $("#conversion-progress"),
        $txt  = $("#conversion-text");
    $prog.attr({ max: 100, value: 0 });
    $txt.text("Preparando upload…");

    // Prepara FormData
    var formData = new FormData();
    formData.append("csv_file", file);
    formData.append("campanha_id", $("#campanha_id").val());

    $.ajax({
      url: "/siape/api/post/importar-csv/",
      type: "POST",
      data: formData,
      processData: false,  // importante para FormData
      contentType: false,  // importante para FormData
      xhr: function() {
        var xhr = $.ajaxSettings.xhr();
        if (xhr.upload) {
          xhr.upload.onprogress = function(evt) {
            if (evt.lengthComputable) {
              var pct = (evt.loaded / evt.total * 100).toFixed(1);
              $prog.val(pct);
              $txt.text("Enviando arquivo: " + pct + "%");
            }
          };
        }
        return xhr;
      },
      beforeSend: function() {
        $txt.text("Iniciando upload…");
        $prog.val(0);
      },
      success: function(resp) {
        var msg = 
          "Importação concluída!\n" +
          "Linhas processadas: "   + resp.linhas_processadas + "\n" +
          "Clientes novos: "       + resp.clientes_novos       + "\n" +
          "Clientes atualizados: " + resp.clientes_atualizados + "\n" +
          "Débitos criados: "      + resp.debitos_criados;
        alert(msg);

        // Reset UI
        $("#form-importar-csv")[0].reset();
        $prog.val(0);
        $txt.text("");
        $("#upload-size").text("");
        carregarInfoCamp();
      },
      error: function(xhr, status, err) {
        var em = (xhr.responseJSON && xhr.responseJSON.mensagem)
                 ? xhr.responseJSON.mensagem
                 : ("Erro: " + status + " - " + err);
        alert(em);
        console.error("Erro na importação:", xhr.responseText);
        $txt.text("");
      }
    });
  });

  // 📥 Baixar modelo CSV
  $("#btn-baixar-modelo").on("click", function(e) {
    e.preventDefault();
    var header = [
      "Nome","CPF","UF","RJur","Situacao_Funcional",
      "Renda_Bruta","Bruta_5","Utilizado_5","Saldo_5",
      "Bruta_Beneficio_5","Utilizado_Beneficio_5","Saldo_Beneficio_5",
      "Bruta_35","Utilizado_35","Saldo_35","Total_Utilizado","Total_Saldo",
      "Matricula","Banco","Orgao","Rebrica","Parcela","Prazo_Restante",
      "Tipo_de_Contrato","Numero_do_Contrato"
    ].join(";") + "\n";
    var blob = new Blob([header], { type: "text/csv;charset=utf-8;" });
    var url  = URL.createObjectURL(blob);
    var a    = document.createElement("a");
    a.href      = url;
    a.download  = "modelo_siape.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

});
