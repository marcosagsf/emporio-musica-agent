# Empório da Música — Agente de Atendimento

Agente de atendimento ao cliente via CLI para a loja fictícia **Empório da Música**, desenvolvido como desafio técnico para a vaga de AI Engineer na Artefact.

## Como rodar

### 1. Pré-requisitos

- Python 3.9+
- Chave de API da Anthropic ([console.anthropic.com](https://console.anthropic.com))

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar a chave de API

**Windows:**
```cmd
set ANTHROPIC_API_KEY=sua_chave_aqui
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY=sua_chave_aqui
```

### 4. Executar

```bash
python agent.py
```

O agente inicia um chat interativo no terminal. Digite `sair` para encerrar.

---

## Decisões Técnicas

### Framework / Abordagem

**Function calling (tool use) com Claude.**

O agente usa a API de tool use da Anthropic: o LLM decide, a cada turno, se precisa consultar dados ou se pode responder direto com base nas políticas. Isso elimina a necessidade de um orquestrador externo (LangChain, LlamaIndex etc.) e mantém o código simples e auditável.

Alternativas consideradas e descartadas:
- **RAG com embeddings**: seria mais adequado se as políticas fossem extensas ou frequentemente atualizadas. Com 8 páginas de PDF, é mais simples e confiável embedar o texto diretamente no system prompt.
- **Agente de SQL**: adiciona complexidade sem benefício real para ~65 produtos e 20 pedidos. Pandas em memória é mais rápido e suficiente.
- **ReAct com scratchpad explícito**: o model já raciocina internamente antes de chamar tools; não há ganho visível em externalizar isso no protótipo.

### Modelo e Provedor

**Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) via API Anthropic.

Justificativa: Haiku tem latência baixa e custo reduzido — ideal para atendimento em tempo real onde o cliente espera uma resposta rápida. Para um protótipo de atendimento (não análise complexa), a qualidade do Haiku é suficiente. Em produção, seria fácil trocar para Sonnet sem alterar nenhuma outra linha de código.

### Interface

**CLI interativa.**

O foco é validar o comportamento do agente, não a interface. CLI é a forma mais rápida de iterar e demonstrar conversas. Uma API REST (FastAPI) ou UI (Streamlit) seriam camadas adicionais simples de construir sobre esse mesmo core.

### Persistência do histórico

**Em memória durante a sessão.**

O histórico completo de mensagens é mantido na lista `history` e enviado ao LLM a cada turno, o que garante contexto conversacional (o agente lembra do que foi dito antes). Para persistência entre sessões, bastaria serializar `history` para JSON/SQLite — optei por não implementar pois o enunciado não requer e adicionaria complexidade sem demonstrar nada novo.

### Tratamento dos dados

- CSVs carregados em DataFrames pandas na inicialização.
- Joins feitos no carregamento: products ← categories, orders ← customers ← order_items.
- Busca textual com `str.contains` (case-insensitive) — adequado para o volume de dados.
- A política da loja está embutida diretamente no system prompt (8 páginas = ~2k tokens), evitando uma pipeline RAG desnecessária.

### Ferramentas disponíveis para o agente

| Ferramenta | Quando usar |
|---|---|
| `search_products` | Preço, disponibilidade, recomendação de instrumentos |
| `get_order_status` | Status de pedido, rastreamento |
| `get_active_promotions` | Promoções em vigor |

Perguntas sobre horários, endereço, formas de pagamento, trocas e garantia são respondidas diretamente pelo LLM com base nas políticas no system prompt.

---

## Estrutura do projeto

```
emporio-musica-agent/
├── agent.py              # Agente completo (carregamento de dados + tools + loop CLI)
├── requirements.txt
├── README.md
├── data/
│   ├── desafio_tecnico_ai_eng - products.csv
│   ├── desafio_tecnico_ai_eng - orders.csv
│   ├── desafio_tecnico_ai_eng - customers.csv
│   ├── desafio_tecnico_ai_eng - promotions.csv
│   ├── desafio_tecnico_ai_eng - order_items.csv
│   ├── desafio_tecnico_ai_eng - categories.csv
│   └── políticas_da_loja.pdf
└── conversations/
    ├── 01_catalogo_violoes.md
    ├── 02_info_loja.md
    ├── 03_politica_devolucao.md
    ├── 04_status_pedido_e_promocoes.md
    └── 05_fora_escopo.md
```

---

## Limitações conhecidas

- **Busca textual simples**: `str.contains` não lida bem com erros de digitação (ex: "viulão"). Em produção, fuzzy matching (rapidfuzz) ou busca semântica com embeddings resolveriam isso.
- **Sem autenticação do cliente**: o agente consulta pedidos pelo nome/telefone sem verificação de identidade. Em produção, seria necessário um fluxo de autenticação.
- **Frete para outras cidades**: a política menciona que o valor é calculado com base no CEP, mas os dados não incluem essa informação. O agente informa as modalidades disponíveis e orienta o cliente a entrar em contato para cotação.
- **Sem persistência entre sessões**: histórico de conversa é perdido ao encerrar. Solução simples: serializar `history` para arquivo JSON.
- **Interface CLI apenas**: sem integração real com WhatsApp. A camada de integração (Twilio, Evolution API, Meta Cloud API) seria o próximo passo natural.

## Com mais tempo, eu faria:

1. Integração real com WhatsApp via webhook (FastAPI + Evolution API)
2. Fuzzy search para produtos (tolerância a erros de digitação)
3. Autenticação básica do cliente antes de exibir dados de pedido
4. Testes automatizados das funções de tool

---

## Uso de assistentes de código

Este projeto foi desenvolvido com apoio do **Claude Code** (CLI da Anthropic) como pair programmer. O assistente foi usado para:
- Explorar e entender a estrutura dos dados (CSVs e PDF)
- Gerar o scaffold inicial do código (`agent.py`)
- Revisar e ajustar o system prompt e os schemas das ferramentas
- Gerar os exemplos de conversa

Todo o raciocínio arquitetural (escolha de abordagem, modelo, estrutura de dados) foi meu — o Claude Code acelerou a execução. Considero esse workflow transparente e alinhado com como times de engenharia modernos trabalham com ferramentas de IA.
