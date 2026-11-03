# Smart Inventory

Controle de equipamentos de TI com histórico de movimentações, identificação por QR Code e regras para apontar ativos que merecem atenção.

![Tela principal do Smart Inventory](docs/screenshots/dashboard.png)

## O fluxo principal

O cadastro guarda os dados do equipamento. Entrega, devolução, transferência, manutenção e baixa são registradas como **movimentações**. Isso é importante porque alterar o status diretamente apagaria parte da história do ativo.

Por esse motivo, `PUT /assets/{id}` atualiza metadados, mas não aceita mudança de status ou responsável. Essas mudanças passam por `POST /assets/{id}/movements`, que valida o estado atual antes de gravar o evento.

Exemplo: um ativo disponível pode ser entregue a alguém; um ativo já em uso não pode receber uma segunda saída; um ativo baixado não pode voltar ao fluxo normal.

## O que já está implementado

- Cadastro, edição de metadados, busca e filtros por status, categoria e local.
- Movimentações de saída, entrada, transferência, manutenção e baixa.
- Histórico por equipamento, com responsável pela operação e destino.
- QR Code com identificador do ativo e leitura pela câmera quando o navegador oferece `BarcodeDetector`.
- Indicadores de inventário, exportação CSV e alertas operacionais.
- Uma pontuação de atenção baseada em regras legíveis, com os motivos exibidos por ativo.

## Como funciona a pontuação

O indicador não é um modelo de machine learning. Cada condição soma pontos; o total é limitado a 100.

| Condição | Pontos |
|---|---:|
| Ativo em manutenção | 35 |
| Em uso sem responsável | 30 |
| Sem número de série | 10 |
| Sem localização | 10 |
| Cadastro com mais de três anos | 15 |
| Doze ou mais movimentações | 10 |
| Mais de 14 dias em manutenção desde a última movimentação | 25 |

A classificação é baixa (0–29), média (30–59) ou alta (60–100). Os pesos são heurísticas de demonstração e precisam ser calibrados com a política patrimonial de cada organização. Não representam probabilidade de falha.

## Rodar localmente

Requisitos: Python 3.12 ou superior.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:APP_TOKEN = "token-local"
uvicorn app:app --reload
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000). Use na tela o mesmo valor definido em `APP_TOKEN`.

Por padrão, o banco é SQLite (`inventory.db`). Para usar PostgreSQL, configure `DATABASE_URL`. O Docker Compose do repositório sobe a aplicação e o banco.

## Rotas mais usadas

| Método | Rota | Uso |
|---|---|---|
| GET | `/assets` | Listar, pesquisar e filtrar ativos |
| POST | `/assets` | Cadastrar equipamento |
| GET / PUT | `/assets/{id}` | Consultar ou editar metadados |
| POST | `/assets/{id}/movements` | Registrar uma movimentação |
| GET | `/assets/{id}/movements` | Consultar o histórico |
| GET | `/assets/{id}/qr` | Gerar o QR Code |
| GET | `/dashboard` | Indicadores e movimentações recentes |
| GET | `/risk` | Pontuação e motivos por ativo |
| GET | `/export.csv` | Exportar o inventário |

As rotas de dados exigem o header `X-App-Token`. O QR Code identifica o ativo, mas não concede acesso aos dados protegidos.

## Testes

```bash
python -m pytest -q
```

A suíte cobre autenticação, cadastro, transições válidas e inválidas, preservação do histórico e cálculo de risco.

## Limites conhecidos

A autenticação atual usa um único token compartilhado. Ainda não há usuários individuais, permissões por função, isolamento por empresa nem migrações de banco. O `create_all` prepara as tabelas para a demonstração, mas não substitui uma estratégia de migração em uma implantação real. A pontuação também precisa ser revista antes de orientar decisões patrimoniais.
