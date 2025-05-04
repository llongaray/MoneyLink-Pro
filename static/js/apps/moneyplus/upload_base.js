$(document).ready(function(){
    $("#form-importar-base").submit(function(e){
      e.preventDefault();
      
      var produto       = $("#select-produto").val();
      var campanha      = $("#select-campanha").val();
      var arquivoInput  = $("#input-arquivo-import")[0];
  
      if (!campanha) {
        alert("Por favor, selecione uma campanha.");
        return;
      }
      if (!produto) {
        alert("Por favor, selecione um produto.");
        return;
      }
      if (arquivoInput.files.length === 0) {
        alert("Por favor, selecione um arquivo.");
        return;
      }
      
      var arquivo  = arquivoInput.files[0];
      var formData = new FormData();
      formData.append("produto", produto);
      formData.append("campanha_id", campanha);
      formData.append("arquivo", arquivo);
      
      console.log("Enviando CSV:", { produto, campanha_id: campanha, arquivo: arquivo.name });
      
      $.ajax({
        url: "/moneyplus/api/post/csv-clientes/",
        method: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function(response){
          alert(
            "Upload processado com sucesso.\n" +
            "Clientes importados: " + response.clientes_importados + "\n" +
            "Débitos importados: " + response.debitos_importados
          );
          $("#form-importar-base")[0].reset();
          populateSelectorsFromAPI();
        },
        error: function(xhr, status, error){
            console.error("Erro no upload:", xhr.responseText);
            let msg = "Erro no upload.";
            try {
              let json = JSON.parse(xhr.responseText);
              msg += "\n" + (json.error || xhr.responseText);
            } catch(e) {
              msg += "\n" + xhr.responseText;
            }
            alert(msg);
          }
      });
    });
  });
  