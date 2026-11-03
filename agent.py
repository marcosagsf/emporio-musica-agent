"""
Empório da Música — Agente de Atendimento ao Cliente
Usa Claude (function calling) + dados em pandas + políticas no system prompt.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
import pandas as pd

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"


def _load_data():
    def read(name):
        return pd.read_csv(DATA_DIR / f"desafio_tecnico_ai_eng - {name}.csv")

    products = read("products")
    categories = read("categories")
    orders = read("orders")
    customers = read("customers")
    promotions = read("promotions")
    order_items = read("order_items")

    products = products.merge(categories[["category_id", "name"]], on="category_id", how="left")
    products.rename(columns={"name_x": "name", "name_y": "category"}, inplace=True)

    orders = orders.merge(customers[["customer_id", "name", "phone"]], on="customer_id", how="left")
    orders.rename(columns={"name": "customer_name"}, inplace=True)

    # attach product names to order_items
    order_items = order_items.merge(
        products[["product_id", "name", "price_brl"]], on="product_id", how="left"
    )

    # attach items to orders
    items_grouped = (
        order_items.groupby("order_id")
        .apply(
            lambda df: df[["name", "quantity", "price_brl"]].to_dict("records"),
            include_groups=False,
        )
        .reset_index()
        .rename(columns={0: "items"})
    )
    orders = orders.merge(items_grouped, on="order_id", how="left")

    return products, orders, promotions


try:
    PRODUCTS, ORDERS, PROMOTIONS = _load_data()
except Exception as e:
    sys.exit(f"Erro ao carregar dados: {e}\nVerifique se a pasta 'data/' existe com os CSVs.")

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def search_products(
    query: str = "",
    category: str = "",
    max_price: float = None,
    min_price: float = None,
    in_stock_only: bool = True,
) -> dict:
    """Filter the products DataFrame and return matching items."""
    df = PRODUCTS.copy()

    if in_stock_only:
        df = df[df["stock_quantity"] > 0]

    df = df[df["status"] == "active"]

    if category:
        df = df[df["category"].str.lower().str.contains(category.lower(), na=False)]

    if max_price is not None:
        df = df[df["price_brl"] <= max_price]

    if min_price is not None:
        df = df[df["price_brl"] >= min_price]

    if query:
        mask = (
            df["name"].str.lower().str.contains(query.lower(), na=False)
            | df["description"].str.lower().str.contains(query.lower(), na=False)
            | df["category"].str.lower().str.contains(query.lower(), na=False)
        )
        df = df[mask]

    if df.empty:
        return {"found": False, "message": "Nenhum produto encontrado com esses critérios."}

    results = df[["product_id", "name", "category", "price_brl", "stock_quantity", "description"]].head(10).to_dict("records")
    return {"found": True, "count": len(df), "products": results}


def get_order_status(order_id: int = None, customer_name: str = "", customer_phone: str = "") -> dict:
    """Look up order status by order_id, customer name or phone."""
    df = ORDERS.copy()

    if order_id:
        df = df[df["order_id"] == int(order_id)]
    elif customer_phone:
        df = df[df["phone"].str.replace(r"\D", "", regex=True).str.contains(
            customer_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", ""), na=False
        )]
    elif customer_name:
        df = df[df["customer_name"].str.lower().str.contains(customer_name.lower(), na=False)]

    if df.empty:
        return {"found": False, "message": "Nenhum pedido encontrado com essas informações."}

    records = df[[
        "order_id", "customer_name", "order_date", "status",
        "total_brl", "payment_method", "tracking_code", "estimated_delivery", "items"
    ]].to_dict("records")

    return {"found": True, "orders": records}


def get_active_promotions() -> dict:
    """Return currently active promotions with product details."""
    active = PROMOTIONS[PROMOTIONS["is_active"] == 1].copy()

    if active.empty:
        return {"found": False, "message": "Não há promoções ativas no momento."}

    active = active.merge(
        PRODUCTS[["product_id", "name", "price_brl", "stock_quantity"]],
        on="product_id",
        how="left",
    )
    active["discounted_price"] = (
        active["price_brl"] * (1 - active["discount_percent"] / 100)
    ).round(2)

    records = active[[
        "product_id", "name", "description", "discount_percent",
        "price_brl", "discounted_price", "stock_quantity"
    ]].to_dict("records")

    return {"found": True, "promotions": records}


# ---------------------------------------------------------------------------
# Tool schemas for Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Busca produtos no catálogo da loja. Use para consultas de preço, "
            "disponibilidade, comparação de modelos ou recomendações. "
            "Pode filtrar por texto livre, categoria, faixa de preço e estoque."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca livre (nome, marca, tipo de instrumento)",
                },
                "category": {
                    "type": "string",
                    "description": "Categoria do instrumento, ex: 'Guitarras', 'Violões', 'Baterias'",
                },
                "max_price": {
                    "type": "number",
                    "description": "Preço máximo em reais",
                },
                "min_price": {
                    "type": "number",
                    "description": "Preço mínimo em reais",
                },
                "in_stock_only": {
                    "type": "boolean",
                    "description": "Se true (padrão), retorna apenas produtos com estoque disponível",
                },
            },
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "Consulta o status de um pedido. Use quando o cliente perguntar sobre "
            "entrega, rastreamento ou situação de uma compra. "
            "Requer ao menos um dos campos: order_id, customer_name ou customer_phone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "Número do pedido",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Nome do cliente (busca parcial)",
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Telefone do cliente (apenas números)",
                },
            },
        },
    },
    {
        "name": "get_active_promotions",
        "description": (
            "Retorna as promoções ativas no momento, com preços originais, "
            "descontos e preços promocionais."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ---------------------------------------------------------------------------
# System prompt (policies embedded)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é o assistente virtual da Empório da Música, uma loja especializada em instrumentos musicais localizada em Campo Grande/MS. Seu nome é "Emi".

Tom de voz: informal mas profissional — como um amigo que entende muito de música. Seja acolhedor, direto e prestativo. Evite linguagem robotizada ou excessivamente formal. Responda em português do Brasil.

== INFORMAÇÕES DA LOJA ==
- Nome: Empório da Música
- Endereço: Rua 14 de Maio, 3200 — Centro, Campo Grande – MS, CEP 79202-333
- Telefone/WhatsApp: (67) 3341-4444
- E-mail: contato@emporiodamusica.com.br
- Fundada em 2008. Mais de 15 anos no mercado.

== HORÁRIOS ==
- Segunda a Sexta: 09h às 18h
- Sábado: 09h às 13h
- Domingo e Feriados: Fechado
- Em datas especiais (Black Friday, Aniversário, Natal) o horário pode ser estendido.

== ESCOPO DA LOJA ==
Trabalhamos EXCLUSIVAMENTE com instrumentos musicais: guitarras, baixos, violões, baterias, teclados, sopros, cordas orquestrais e ukuleles.
NÃO vendemos acessórios como cordas avulsas, palhetas, cabos, cases, pedais ou amplificadores.
Para perguntas fora do escopo da loja (outros produtos, assuntos não relacionados), informe educadamente que não podemos ajudar com isso.

== FORMAS DE PAGAMENTO ==
- PIX: à vista, 5% de desconto (desconto NÃO se aplica sobre preços já promocionais)
- Cartão de Débito: à vista, todas as bandeiras
- Cartão de Crédito: até 12x sem juros (parcela mínima R$100)
  - Até 3x: sem juros, parcela mínima R$50
  - 4x a 6x: sem juros, parcela mínima R$80
  - 7x a 12x: sem juros, parcela mínima R$100
- Boleto Bancário: à vista, compensação em até 3 dias úteis
- Combinação de formas (ex: PIX + cartão): permitida para compras acima de R$2.000

== TROCAS E DEVOLUÇÕES ==
Direito de arrependimento (compras online):
- Até 7 dias corridos após recebimento, sem justificativa
- Produto deve estar na embalagem original, sem uso, com todos os acessórios
- Reembolso em até 10 dias úteis, na mesma forma de pagamento
- Frete de devolução por conta da loja

Troca por defeito:
- Até 30 dias corridos após a compra para defeito de fabricação
- Após 30 dias, acionar garantia diretamente com o fabricante (podemos intermediar)
- Danos por mau uso, quedas, umidade ou modificações NÃO são cobertos

Troca por preferência (cor, modelo, tamanho):
- Até 7 dias, produto em perfeito estado e embalagem original
- Diferenças de valor cobradas/reembolsadas conforme o caso

Itens NÃO elegíveis:
- Instrumentos com personalização/ajustes sob encomenda
- Produtos de liquidação com aviso explícito "venda final"
- Boquilhas de sopro (higiene)

== FRETE E ENTREGAS ==
Campo Grande e região metropolitana:
- Grátis para pedidos acima de R$500
- Taxa fixa de R$35 para pedidos abaixo de R$500
- Prazo: 1 a 3 dias úteis (motoboy próprio, cliente contactado antes)

Outras cidades:
- PAC (Correios): 5 a 12 dias úteis
- SEDEX (Correios): 2 a 5 dias úteis
- Jadlog: 3 a 8 dias úteis
- Todos com rastreamento e seguro incluídos
- Código de rastreamento enviado por e-mail/WhatsApp após despacho
- Instrumentos de grande porte (baterias, pianos, contrabaixos) podem ter frete especial

== GARANTIA ==
- Garantia legal: 90 dias contra defeitos de fabricação (CDC)
- Garantia do fabricante: varia de 6 meses a 2 anos (veja certificado do produto)
- Não cobre: desgaste natural, mau uso, quedas, condições climáticas extremas, reparos não autorizados

== PROMOÇÕES ==
- Promoções NÃO são cumulativas entre si
- Desconto PIX (5%) não se aplica sobre preços já promocionais
- Sujeitas à disponibilidade de estoque (sem rain check)

== INSTRUÇÕES PARA CONSULTAS ==
- SEMPRE use as ferramentas (search_products, get_order_status, get_active_promotions) para consultar preços, estoque, pedidos e promoções. Nunca invente ou assuma valores.
- Para status de pedido, peça ao cliente o número do pedido, nome ou telefone cadastrado.
- Se o produto não estiver disponível, sugira alternativas similares do catálogo.
"""

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    "search_products": search_products,
    "get_order_status": get_order_status,
    "get_active_promotions": get_active_promotions,
}


def run_agent():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "Erro: variável ANTHROPIC_API_KEY não definida.\n"
            "Execute: set ANTHROPIC_API_KEY=sua_chave_aqui"
        )

    client = anthropic.Anthropic(api_key=api_key)
    history = []

    print("=" * 60)
    print("  🎸 Empório da Música — Assistente Virtual (Emi)")
    print("=" * 60)
    print("  Digite sua mensagem ou 'sair' para encerrar.\n")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo! 🎵")
            break

        if not user_input:
            continue

        if user_input.lower() in {"sair", "exit", "quit", "q"}:
            print("\nEmi: Até logo! Se precisar de mais alguma coisa, é só chamar. 🎵")
            break

        history.append({"role": "user", "content": user_input})

        # Agentic loop: keep going until stop_reason is "end_turn"
        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=history,
            )

            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        handler = TOOL_HANDLERS.get(block.name)
                        if handler:
                            result = handler(**block.input)
                        else:
                            result = {"error": f"Ferramenta '{block.name}' não encontrada."}
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
                history.append({"role": "user", "content": tool_results})

            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        print(f"\nEmi: {block.text}\n")
                break


if __name__ == "__main__":
    run_agent()
