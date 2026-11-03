"""
Empório da Música — Agente de Atendimento ao Cliente
Suporta Anthropic Claude e Google Gemini como provedores de LLM.
Configuração via arquivo .env na raiz do projeto.
"""

import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()  # lê o arquivo .env

# ---------------------------------------------------------------------------
# Configuração — lida do .env
# ---------------------------------------------------------------------------

PROVIDER = os.getenv("PROVIDER", "anthropic").lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"


def _load_data():
    def read(name):
        return pd.read_csv(DATA_DIR / f"desafio_tecnico_ai_eng - {name}.csv", encoding="latin1")

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

    order_items = order_items.merge(
        products[["product_id", "name", "price_brl"]], on="product_id", how="left"
    )
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
# Tool implementations (compartilhadas entre os dois provedores)
# ---------------------------------------------------------------------------


def search_products(
    query: str = "",
    category: str = "",
    max_price: float = None,
    min_price: float = None,
    in_stock_only: bool = True,
) -> dict:
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
    results = (
        df[["product_id", "name", "category", "price_brl", "stock_quantity", "description"]]
        .head(10)
        .to_dict("records")
    )
    return {"found": True, "count": len(df), "products": results}


def get_order_status(
    order_id: int = None, customer_name: str = "", customer_phone: str = ""
) -> dict:
    df = ORDERS.copy()
    if order_id:
        df = df[df["order_id"] == int(order_id)]
    elif customer_phone:
        digits = "".join(filter(str.isdigit, customer_phone))
        df = df[df["phone"].str.replace(r"\D", "", regex=True).str.contains(digits, na=False)]
    elif customer_name:
        df = df[df["customer_name"].str.lower().str.contains(customer_name.lower(), na=False)]
    if df.empty:
        return {"found": False, "message": "Nenhum pedido encontrado com essas informações."}
    records = df[
        [
            "order_id", "customer_name", "order_date", "status",
            "total_brl", "payment_method", "tracking_code", "estimated_delivery", "items",
        ]
    ].to_dict("records")
    return {"found": True, "orders": records}


def get_active_promotions() -> dict:
    active = PROMOTIONS[PROMOTIONS["is_active"] == 1].copy()
    if active.empty:
        return {"found": False, "message": "Não há promoções ativas no momento."}
    active = active.merge(
        PRODUCTS[["product_id", "name", "price_brl", "stock_quantity"]], on="product_id", how="left"
    )
    active["discounted_price"] = (
        active["price_brl"] * (1 - active["discount_percent"] / 100)
    ).round(2)
    records = active[
        ["product_id", "name", "description", "discount_percent", "price_brl", "discounted_price", "stock_quantity"]
    ].to_dict("records")
    return {"found": True, "promotions": records}


TOOL_HANDLERS = {
    "search_products": search_products,
    "get_order_status": get_order_status,
    "get_active_promotions": get_active_promotions,
}


def call_tool(name: str, args: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"Ferramenta '{name}' não encontrada."}
    return handler(**args)

# ---------------------------------------------------------------------------
# System prompt
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
Para perguntas fora do escopo da loja, informe educadamente que não podemos ajudar.

== FORMAS DE PAGAMENTO ==
- PIX: à vista, 5% de desconto (NÃO se aplica sobre preços já promocionais)
- Cartão de Débito: à vista, todas as bandeiras
- Cartão de Crédito: até 12x sem juros (mínimo R$100/parcela; 4–6x: mínimo R$80; até 3x: mínimo R$50)
- Boleto Bancário: à vista, compensação em até 3 dias úteis
- Combinação de formas: permitida para compras acima de R$2.000

== TROCAS E DEVOLUÇÕES ==
Arrependimento (compras online): até 7 dias corridos após recebimento, sem justificativa. Produto sem uso, embalagem original. Reembolso em até 10 dias úteis. Frete por conta da loja.
Troca por defeito: até 30 dias. Após 30 dias, acionar fabricante (podemos intermediar).
Troca por preferência: até 7 dias, produto em perfeito estado, diferenças de valor acertadas.
Não elegíveis: instrumentos personalizados, liquidação "venda final", boquilhas de sopro.

== FRETE E ENTREGAS ==
Campo Grande e região: grátis acima de R$500; R$35 abaixo disso. Prazo: 1–3 dias úteis.
Outras cidades: PAC (5–12 dias), SEDEX (2–5 dias), Jadlog (3–8 dias). Todos com rastreamento e seguro.

== GARANTIA ==
Garantia legal: 90 dias (CDC). Fabricante: 6 meses a 2 anos (ver certificado).
Não cobre: mau uso, quedas, condições climáticas, reparos não autorizados.

== PROMOÇÕES ==
Promoções não são cumulativas. Desconto PIX não se aplica sobre preços promocionais.

== INSTRUÇÕES ==
- SEMPRE use as ferramentas para consultar preços, estoque, pedidos e promoções. Nunca invente valores.
- Se o produto estiver indisponível, sugira alternativas similares.
- Para status de pedido, peça o número do pedido, nome ou telefone do cliente."""

# ---------------------------------------------------------------------------
# Anthropic tool schemas
# ---------------------------------------------------------------------------

ANTHROPIC_TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Busca produtos no catálogo. Use para consultas de preço, disponibilidade, "
            "comparação de modelos ou recomendações. Pode filtrar por texto, categoria, "
            "faixa de preço e estoque."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca livre (nome, marca, tipo)"},
                "category": {"type": "string", "description": "Ex: 'Guitarras', 'Violões', 'Baterias'"},
                "max_price": {"type": "number", "description": "Preço máximo em reais"},
                "min_price": {"type": "number", "description": "Preço mínimo em reais"},
                "in_stock_only": {"type": "boolean", "description": "Somente com estoque (padrão: true)"},
            },
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "Consulta status de pedido. Use quando o cliente perguntar sobre entrega ou "
            "rastreamento. Requer ao menos um: order_id, customer_name ou customer_phone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer", "description": "Número do pedido"},
                "customer_name": {"type": "string", "description": "Nome do cliente (busca parcial)"},
                "customer_phone": {"type": "string", "description": "Telefone (somente números)"},
            },
        },
    },
    {
        "name": "get_active_promotions",
        "description": "Retorna promoções ativas com preços originais, descontos e preços finais.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# ---------------------------------------------------------------------------
# Gemini tool schemas
# ---------------------------------------------------------------------------

GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_products",
                "description": (
                    "Busca produtos no catálogo. Use para consultas de preço, disponibilidade, "
                    "comparação de modelos ou recomendações."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Termo de busca livre"},
                        "category": {"type": "string", "description": "Ex: Guitarras, Violões, Baterias"},
                        "max_price": {"type": "number", "description": "Preço máximo em reais"},
                        "min_price": {"type": "number", "description": "Preço mínimo em reais"},
                        "in_stock_only": {"type": "boolean", "description": "Somente com estoque"},
                    },
                },
            },
            {
                "name": "get_order_status",
                "description": "Consulta status de pedido por order_id, nome ou telefone do cliente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "integer", "description": "Número do pedido"},
                        "customer_name": {"type": "string", "description": "Nome do cliente"},
                        "customer_phone": {"type": "string", "description": "Telefone (só números)"},
                    },
                },
            },
            {
                "name": "get_active_promotions",
                "description": "Retorna promoções ativas com preços originais, descontos e preços finais.",
                "parameters": {"type": "object", "properties": {}},
            },
        ]
    }
]

# ---------------------------------------------------------------------------
# Provider: Anthropic
# ---------------------------------------------------------------------------


def run_anthropic(history: list, user_input: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    history.append({"role": "user", "content": user_input})

    while True:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=ANTHROPIC_TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
            history.append({"role": "user", "content": tool_results})
        else:
            return next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )


# ---------------------------------------------------------------------------
# Provider: Google Gemini
# ---------------------------------------------------------------------------


def run_gemini(chat_session, user_input: str) -> str:
    import google.generativeai as genai

    response = chat_session.send_message(user_input)

    # Agentic loop: resolve tool calls until the model produces a text response
    while True:
        function_calls = [p for p in response.parts if p.function_call.name]
        if not function_calls:
            break

        # Execute all function calls and send results back in one turn
        tool_response_parts = []
        for part in function_calls:
            fc = part.function_call
            result = call_tool(fc.name, dict(fc.args))
            tool_response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result, ensure_ascii=False, default=str)},
                    )
                )
            )
        response = chat_session.send_message(tool_response_parts)

    return response.text


# ---------------------------------------------------------------------------
# CLI loop
# ---------------------------------------------------------------------------


def main():
    print("=" * 60)
    print("  Emporio da Musica — Assistente Virtual (Emi)")
    print(f"  Provedor: {PROVIDER.upper()}")
    print("=" * 60)
    print("  Digite sua mensagem ou 'sair' para encerrar.\n")

    if PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("sk-ant-..."):
            sys.exit("Erro: ANTHROPIC_API_KEY nao configurada no arquivo .env")
        history = []

        while True:
            try:
                user_input = input("Voce: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAte logo!")
                break
            if not user_input:
                continue
            if user_input.lower() in {"sair", "exit", "quit", "q"}:
                print("\nEmi: Ate logo! Se precisar de mais alguma coisa, e so chamar.")
                break
            reply = run_anthropic(history, user_input)
            print(f"\nEmi: {reply}\n")

    elif PROVIDER == "gemini":
        if not GOOGLE_API_KEY or GOOGLE_API_KEY.startswith("AIza..."):
            sys.exit("Erro: GOOGLE_API_KEY nao configurada no arquivo .env")

        import google.generativeai as genai

        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            tools=GEMINI_TOOLS,
            system_instruction=SYSTEM_PROMPT,
        )
        chat_session = model.start_chat()

        while True:
            try:
                user_input = input("Voce: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAte logo!")
                break
            if not user_input:
                continue
            if user_input.lower() in {"sair", "exit", "quit", "q"}:
                print("\nEmi: Ate logo! Se precisar de mais alguma coisa, e so chamar.")
                break
            reply = run_gemini(chat_session, user_input)
            print(f"\nEmi: {reply}\n")

    else:
        sys.exit(f"Erro: PROVIDER '{PROVIDER}' invalido. Use 'anthropic' ou 'gemini'.")


if __name__ == "__main__":
    main()
