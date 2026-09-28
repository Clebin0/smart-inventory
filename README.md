# Smart Inventory

Aplicacao de portfolio para gestao de ativos de TI com rastreabilidade de movimentacoes.

## Principais recursos

- Dashboard com total de ativos e status
- Cadastro e edicao via API
- Patrimonio, numero de serie, categoria, local e responsavel
- Entrada, saida, transferencia, manutencao e baixa
- Historico de movimentacoes
- QR Code individual por ativo
- Leitura de QR/barcode pela camera quando o navegador oferece BarcodeDetector
- Busca e filtros
- Exportacao CSV
- Insights operacionais baseados em regras
- SQLite para desenvolvimento e PostgreSQL por variavel de ambiente
- Docker e Docker Compose
- Protecao simples por APP_TOKEN

## Rodar localmente

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
set APP_TOKEN=demo-token
uvicorn app:app --reload
```

Abra http://127.0.0.1:8000 e use o token configurado.

## Docker

```bash
docker compose up --build
```

## API

A documentacao interativa fica em `/docs`.

Endpoints principais:
- `GET /dashboard`
- `GET /assets`
- `POST /assets`
- `PUT /assets/{id}`
- `POST /assets/{id}/movements`
- `GET /assets/{id}/movements`
- `GET /assets/{id}/qr`
- `GET /insights`
- `GET /export.csv`

## Seguranca

Este projeto usa um token simples para demonstracao. Para uso corporativo real, a autenticacao deve ser substituida por identidade corporativa, RBAC, logs de auditoria e gerenciamento seguro de segredos.

Nenhum dado corporativo real e versionado neste repositorio.
