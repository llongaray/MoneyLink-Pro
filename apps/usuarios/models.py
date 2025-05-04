from django.db import models
from django.contrib.auth.models import User

class Acesso(models.Model):
    CATEGORIA_APP      = 'CT'
    SUBCATEGORIA_RENDER = 'SCT'
    SESSAO_SECTION     = 'SS'
    SUBSESSAO_DIV      = 'SSS'
    CAIXA_BOX          = 'CX'
    TIPO_CHOICES = [
        (CATEGORIA_APP,       'Categoria - APP'),
        (SUBCATEGORIA_RENDER,  'SubCategoria - Render/Template'),
        (SESSAO_SECTION,       'Sessão - Section/Container'),
        (SUBSESSAO_DIV,        'SubSessão - Div/Content'),
        (CAIXA_BOX,            'Caixa - div/span/box/card'),
    ]

    nome          = models.CharField(max_length=100)
    tipo          = models.CharField(max_length=20, choices=TIPO_CHOICES)
    data_criacao  = models.DateTimeField(auto_now_add=True)
    status        = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    def gerar_codigo(self):
        return f"COD_{self.tipo}{self.id}"

class GroupsAcessos(models.Model):
    titulo        = models.CharField(max_length=100)
    acessos       = models.ManyToManyField(Acesso, related_name='groups_acessos')
    data_criacao  = models.DateTimeField(auto_now_add=True)
    status        = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo

class ControleAcessos(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='controle_acessos')
    acessos       = models.ManyToManyField(Acesso, related_name='usuarios_controle')
    data_criacao  = models.DateTimeField(auto_now_add=True)
    status        = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} – {self.acessos.count()} acessos"
