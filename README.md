# Smart Inventory

MVP de inventário de TI com API, movimentações auditáveis e geração de QR Code.

## Funcionalidades
- Cadastro de ativos e patrimônio
- Status e localização
- Entrada, saída, empréstimo, devolução e transferência
- Responsável por movimentação
- Histórico imutável de movimentações
- QR Code por ativo
- Dashboard resumido via API
- SQLite local, facilmente migrável para PostgreSQL

## Executar
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Abra `/docs` para a documentação interativa.

## Fluxo
1. Cadastre o ativo em `POST /assets`.
2. Gere/consulte o QR em `GET /assets/{id}/qr`.
3. Ao escanear, consulte o ativo e registre uma movimentação.
4. Consulte `/dashboard` e `/assets/{id}/movements`.

O repositório usa dados fictícios e não contém informações corporativas.