// static/js/apps/usuarios/permissionacess.js

$(function() {
    console.log('Script de Permissões iniciado.');
  
    // --- Pega o CSRF token ---
    function getCookie(name) {
      let cookieValue = null;
      document.cookie.split(';').forEach(c => {
        c = c.trim();
        if (c.startsWith(name + '=')) {
          cookieValue = decodeURIComponent(c.slice(name.length + 1));
        }
      });
      return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');
  
    // --- Genérico AJAX POST ---
    function sendPost(url, data, onSuccess) {
      $.ajax({
        url,
        method: 'POST',
        contentType: 'application/json',
        headers: { 'X-CSRFToken': csrftoken },
        data: JSON.stringify(data),
        success(resp) {
          alert('✅ Operação bem-sucedida!');
          if (onSuccess) onSuccess(resp);
          loadAll();
        },
        error(xhr) {
          console.error(xhr.responseText);
          alert('❌ Erro ao salvar. Veja console.');
        }
      });
    }
  
    // --- Carrega todos os dados ---
    function loadAcessos() {
      $.getJSON('/autenticacao/api/acessos/')
        .done(res => {
          const grp = $('#grupo_acesso_acessos_container').empty();
          const mnl = $('#controle_acesso_acessos_container').empty();
          if (!res.acessos.length) {
            grp.html('<p class="text-muted text-center">Nenhum acesso.</p>');
            mnl.html('<p class="text-muted text-center">Nenhum acesso.</p>');
            return;
          }
          res.acessos.forEach(a => {
            const item = `
              <div class="form-check">
                <input class="form-check-input" type="checkbox" id="acesso_${a.id}" value="${a.id}">
                <label class="form-check-label" for="acesso_${a.id}">
                  ${a.nome} <small class="text-muted">(${a.tipo})</small>
                </label>
              </div>`;
            grp.append(item);
            mnl.append(item);
          });
        })
        .fail(() => {
          $('#grupo_acesso_acessos_container, #controle_acesso_acessos_container')
            .html('<p class="text-danger text-center">Erro ao carregar acessos.</p>');
        });
    }
  
    function loadGroups() {
      const sel = $('#controle_acesso_grupo_favorito')
        .empty()
        .append('<option value="">--- Selecione um Grupo ---</option>');
      $.getJSON('/autenticacao/api/grupos-acessos/')
        .done(res => {
          res.groups_acessos.forEach(g => {
            sel.append(
              `<option value="${g.id}" data-acessos='${JSON.stringify(g.acessos)}'>
                 ${g.titulo}
               </option>`
            );
          });
        })
        .fail(() => {
          sel.html('<option value="">Erro ao carregar grupos</option>');
        });
    }
  
    // --- Atualizado: Carrega e popula o select de Usuários via nova API ---
    function loadUsers() {
      const sel = $('#controle_acesso_usuario')
        .empty()
        .append('<option value="">--- Selecione o Usuário ---</option>');
      $.getJSON('/autenticacao/api/users-info/')  // <— nova rota
        .done(res => {
          // res.infousers: [{ user_id, nome_completo }, ...]
          res.infousers.forEach(u => {
            sel.append(
              `<option value="${u.user_id}">
                 ${u.nome_completo}
               </option>`
            );
          });
        })
        .fail(() => {
          sel.html('<option value="">Erro ao carregar usuários</option>');
        });
    }
  
    function loadAll() {
      loadAcessos();
      loadGroups();
      loadUsers();
    }
  
    // --- Oculta/Exibe containers conforme método ---
    function toggleContainers() {
      const metodo = $('#controle_acesso_metodo').val();
      $('#controle_acesso_manual_container, #controle_acesso_favoritos_container').hide();
      if (metodo === 'manual') {
        $('#controle_acesso_manual_container').show();
      } else if (metodo === 'favoritos') {
        $('#controle_acesso_favoritos_container').show();
      }
    }
  
    // --- Submissões de formulários ---
    $('#form-acesso').submit(function(e) {
      e.preventDefault();
      const nome   = $('#acesso_nome').val().trim();
      const tipo   = $('#acesso_tipo').val();
      const status = $('#acesso_status').is(':checked');
      if (!nome || !tipo) return alert('Preencha nome e tipo.');
      sendPost('/autenticacao/api/acessos/new/', { titulo: nome, tipo, status }, () => this.reset());
    });
  
    $('#form-grupo-acesso').submit(function(e) {
      e.preventDefault();
      const titulo = $('#grupo_acesso_titulo').val().trim();
      const status = $('#grupo_acesso_status').is(':checked');
      const acessos = $('#grupo_acesso_acessos_container input:checked').map((_,c) => c.value).get();
      if (!titulo || !acessos.length) return alert('Título e ao menos 1 acesso.');
      sendPost('/autenticacao/api/grupos-acessos/new/', { titulo, acessos, status }, () => this.reset());
    });
  
    $('#form-controle-acesso').submit(function(e) {
      e.preventDefault();
      const userId = $('#controle_acesso_usuario').val();
      const metodo = $('#controle_acesso_metodo').val();
      const status = $('#controle_acesso_status').is(':checked');
      if (!userId || !metodo) return alert('Selecione usuário e método.');
      let acessos = [];
      if (metodo === 'manual') {
        acessos = $('#controle_acesso_acessos_container input:checked').map((_,c) => c.value).get();
      } else {
        acessos = $('#controle_acesso_favoritos_acessos_container input:checked').map((_,c) => c.value).get();
      }
      sendPost('/autenticacao/api/users-acessos/register/', { user_id: userId, acessos, status }, () => {
        this.reset();
        toggleContainers();
        $('#controle_acesso_favoritos_acessos_container')
          .html('<p class="text-muted text-center">Selecione um grupo para ver os acessos.</p>');
      });
    });
  
    // --- Eventos ---
    $('#controle_acesso_metodo').on('change', toggleContainers);
  
    $('#controle_acesso_grupo_favorito').on('change', function() {
      const ids = $(this).find(':selected').data('acessos') || [];
      const box = $('#controle_acesso_favoritos_acessos_container').empty();
      if (!ids.length) {
        return box.html('<p class="text-muted text-center">Este grupo não possui acessos.</p>');
      }
      $.getJSON('/autenticacao/api/acessos/')
        .done(res => {
          res.acessos.forEach(a => {
            const checked = ids.includes(a.id) ? 'checked' : '';
            box.append(`
              <div class="form-check">
                <input class="form-check-input" type="checkbox"
                       id="fav_acesso_${a.id}" value="${a.id}" disabled ${checked}>
                <label class="form-check-label" for="fav_acesso_${a.id}">
                  ${a.nome} <small class="text-muted">(${a.tipo})</small>
                </label>
              </div>`);
          });
        })
        .fail(() => {
          box.html('<p class="text-danger text-center">Erro ao carregar acessos do grupo.</p>');
        });
    });
  
    // --- Inicialização ---
    loadAll();
    toggleContainers();
    console.log('Script de Permissões carregado.');
  });
  