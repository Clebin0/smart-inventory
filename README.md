<div align="center">

# Smart Inventory

**Gestão de ativos · QR Code · Auditoria · Risk Scoring**

<img src="https://img.shields.io/badge/Python-000000?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/FastAPI-000000?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/PostgreSQL-000000?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
<img src="https://img.shields.io/badge/Docker-000000?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />

</div>

---

Aplicação de portfólio para gestão de ativos de TI com rastreabilidade de movimentações e análise explicável de risco operacional.

## Recursos

- dashboard de ativos e status;
- cadastro, edição, pesquisa e filtros;
- patrimônio, serial, categoria, local e responsável;
- entrada, saída, transferência, manutenção e baixa;
- histórico de movimentações;
- QR Code individual;
- leitura por câmera quando suportado;
- exportação CSV;
- SQLite em desenvolvimento e PostgreSQL por <code>DATABASE_URL</code>;
- Docker / Docker Compose;
- score de risco por ciclo de vida.

## Lifecycle Risk

O endpoint <code>GET /risk</code> calcula um score de 0 a 100 usando regras explícitas, como:

- ativo em manutenção;
- ativo em uso sem responsável;
- serial ausente;
- frequência alta de movimentações;
- manutenção sem movimentação há mais de 14 dias.

O score é interpretável e não é apresentado como probabilidade de falha.

## Executar

~~~bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set APP_TOKEN=demo-token
uvicorn app:app --reload
~~~

## API

- <code>GET /dashboard</code>
- <code>GET /assets</code>
- <code>POST /assets</code>
- <code>PUT /assets/{id}</code>
- <code>POST /assets/{id}/movements</code>
- <code>GET /assets/{id}/movements</code>
- <code>GET /assets/{id}/qr</code>
- <code>GET /risk</code>
- <code>GET /insights</code>
- <code>GET /export.csv</code>

## Segurança

O token atual serve apenas para demonstração. Uso corporativo deve adotar identidade corporativa, RBAC, auditoria e gerenciamento seguro de segredos. Nenhum dado corporativo real deve ser versionado.

---

<div align="center">

Inventário técnico com foco em rastreabilidade antes de “planilha_final_v7_agora_vai.xlsx”.

</div>
