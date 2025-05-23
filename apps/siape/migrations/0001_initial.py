# Generated by Django 5.1 on 2025-04-23 17:50

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('funcionarios', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Campanha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=100, null=True, verbose_name='Nome da Campanha')),
                ('data_criacao', models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True, verbose_name='Data de Criação')),
                ('departamento', models.CharField(blank=True, max_length=100, null=True, verbose_name='Departamento')),
                ('status', models.BooleanField(blank=True, default=True, null=True, verbose_name='Status')),
            ],
        ),
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=100, null=True, verbose_name='Nome')),
                ('cpf', models.CharField(blank=True, max_length=11, null=True, unique=True, validators=[django.core.validators.RegexValidator('^\\d{11}$')], verbose_name='CPF')),
                ('uf', models.CharField(blank=True, max_length=2, null=True, verbose_name='UF')),
                ('rjur', models.CharField(blank=True, max_length=50, null=True, verbose_name='RJur')),
                ('situacao_funcional', models.CharField(blank=True, max_length=50, null=True, verbose_name='Situação Funcional')),
                ('renda_bruta', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Renda Bruta')),
                ('bruta_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Bruta 5')),
                ('util_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Utilizado 5')),
                ('saldo_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Saldo 5')),
                ('brutaBeneficio_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Bruta Benefício 5')),
                ('utilBeneficio_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Utilizado Benefício 5')),
                ('saldoBeneficio_5', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Saldo Benefício 5')),
                ('bruta_35', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Bruta 35')),
                ('util_35', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Utilizado 35')),
                ('saldo_35', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Saldo 35')),
                ('total_util', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Total Utilizado')),
                ('total_saldo', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Total Saldo')),
            ],
        ),
        migrations.CreateModel(
            name='AgendamentoFichaCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(verbose_name='Data')),
                ('hora', models.TimeField(verbose_name='Hora')),
                ('observacao', models.TextField(blank=True, null=True, verbose_name='Observação')),
                ('data_criacao', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('status', models.CharField(choices=[('AGENDADO', 'Agendado'), ('CONFIRMADO', 'Confirmado'), ('FECHOU', 'Fechou negócio'), ('NAO_QUIS', 'Não quis')], default='AGENDADO', help_text='Status atual do agendamento', max_length=10, verbose_name='Status')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agendamentos_criados', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agendamentos', to='siape.cliente')),
            ],
            options={
                'verbose_name': 'Agendamento',
                'verbose_name_plural': 'Agendamentos',
                'ordering': ['-data', '-hora'],
            },
        ),
        migrations.CreateModel(
            name='Debito',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('matricula', models.CharField(blank=True, max_length=50, null=True, verbose_name='Matrícula')),
                ('banco', models.CharField(blank=True, max_length=100, null=True, verbose_name='Banco')),
                ('orgao', models.CharField(blank=True, max_length=50, null=True, verbose_name='Órgão')),
                ('rebrica', models.CharField(blank=True, max_length=50, null=True, verbose_name='Rebrica')),
                ('parcela', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Parcela')),
                ('prazo_restante', models.PositiveIntegerField(blank=True, null=True, verbose_name='Prazo Restante')),
                ('tipo_contrato', models.CharField(blank=True, max_length=50, null=True, verbose_name='Tipo de Contrato')),
                ('num_contrato', models.CharField(blank=True, max_length=50, null=True, verbose_name='Número do Contrato')),
                ('campanha', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debitos', to='siape.campanha')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debitos', to='siape.cliente')),
            ],
        ),
        migrations.CreateModel(
            name='RegisterMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.TextField(blank=True, default='Ranking Geral', max_length=100, null=True)),
                ('valor', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('categoria', models.CharField(blank=True, choices=[('GERAL', 'Geral - Todas as equipes'), ('EMPRESA', 'Empresa'), ('FRANQUIA', 'Franquia'), ('LOJAS', 'Lojas'), ('SETOR', 'Setor'), ('OUTROS', 'Outros')], default='GERAL', max_length=10, null=True)),
                ('data_inicio', models.DateTimeField(blank=True, help_text='Data e hora de início (meia-noite AM)', null=True)),
                ('data_fim', models.DateTimeField(blank=True, help_text='Data e hora de término (meia-noite PM)', null=True)),
                ('status', models.BooleanField(blank=True, default=False, help_text='Ativo ou Inativo', null=True)),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
                ('equipe', models.ManyToManyField(blank=True, help_text="Selecione uma ou mais equipes quando a categoria for 'Outros'", to='funcionarios.equipe')),
                ('setor', models.ForeignKey(blank=True, help_text="Selecione o departamento quando a categoria for 'Setor'", null=True, on_delete=django.db.models.deletion.SET_NULL, to='funcionarios.departamento')),
            ],
        ),
        migrations.CreateModel(
            name='RegisterMoney',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cpf_cliente', models.CharField(blank=True, max_length=14, null=True)),
                ('valor_est', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.BooleanField(blank=True, default=True, null=True)),
                ('data', models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True)),
                ('loja', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='funcionarios.loja')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
        ),
    ]
