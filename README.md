# Smart Inventory

Aplicação de portfólio para gestão de ativos de TI com rastreabilidade de movimentações e análise de risco operacional explicável.

## Recursos

- dashboard de ativos e status
- cadastro, edição, pesquisa e filtros
- patrimônio, serial, categoria, local e responsável
- entrada, saída, transferência, manutenção e baixa
- histórico de movimentações
- QR Code individual e leitura por câmera quando suportado
- exportação CSV
- SQLite para desenvolvimento e PostgreSQL por `DATABASE_URL`
- Docker / Docker Compose
- proteção simples por `APP_TOKEN`
- **lifecycle risk score** por ativo

## Lifecycle Risk

O endpoint `GET /risk` calcula um score de 0 a 100 usando regras explícitas, como:

- ativo em manutenção
- ativo em uso sem responsável
- serial ausente
- frequência alta de movimentações
- manutenção sem movimentação há mais de 14 dias

O score é deliberadamente **interpretável** e não é apresentado como probabilidade de falha. Um modelo preditivo real exigiria histórico suficiente, rótulos confiáveis e validação.

## Executar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set APP_TOKEN=demo-token
uvicorn app:app --reload
```

Abra `http://127.0.0.1:8000`.

## API

- `GET /dashboard`
- `GET /assets`
- `POST /assets`
- `PUT /assets/{id}`
- `POST /assets/{id}/movements`
- `GET /assets/{id}/movements`
- `GET /assets/{id}/qr`
- `GET /risk`
- `GET /insights`
- `GET /export.csv`

## Segurança

O token atual é adequado apenas para demonstração. Uso corporativo real deve adotar identidade corporativa, RBAC, auditoria e gerenciamento seguro de segredos. Nenhum dado corporativo real é versionado.
