# Conversa 4 — Status de pedido + promoções ativas (consulta a dados em tempo real)

**Cenário:** Cliente quer rastrear o pedido e aproveitar promoções. Demonstra consulta a múltiplas fontes de dados.

---

**Você:** Oi, queria saber o status do meu pedido. Sou o Lucas Mendes.

**Emi:** Olá, Lucas! Deixa eu verificar aqui pra você! 🔍

*(consultou get_order_status: customer_name="Lucas Mendes")*

Encontrei seu pedido! Veja os detalhes:

| Campo | Informação |
|---|---|
| **Pedido nº** | 4 |
| **Status** | ✅ Entregue |
| **Data do pedido** | 10/12/2025 |
| **Total** | R$ 799,90 |
| **Pagamento** | Boleto bancário |
| **Produto** | Yamaha C40 Nylon Natural (1x) |
| **Código de rastreamento** | BRQM7890123BR |
| **Entrega prevista** | 22/12/2025 |

Pedido já consta como entregue! Se você não recebeu ou teve algum problema, pode me contar que a gente resolve. 😊

---

**Você:** Tá ótimo, obrigado! Vocês têm alguma promoção rolando agora?

**Emi:** Que bom! Agora deixa eu ver o que está em promoção no momento 🎉

*(consultou get_active_promotions)*

Temos **4 produtos em promoção** agora:

| Produto | De | Por | Desconto |
|---|---|---|---|
| Ibanez RG421 Azul Metálico | R$ 2.299,00 | **R$ 1.954,15** | 15% OFF |
| Pearl Roadshow RS525SC Fusion Preto | R$ 3.799,00 | **R$ 3.229,15** | 15% OFF |
| Fender Player Stratocaster Sunburst | R$ 5.499,00 | **R$ 4.399,20** | 20% OFF |
| Korg B2 Piano Digital Preto | R$ 2.199,00 | **R$ 1.869,15** | 15% OFF |

Vale lembrar: o desconto de **PIX (5%)** não se aplica sobre preços já promocionais — o preço que você vê aí já é o final da promoção.

Tem interesse em algum desses? Posso dar mais detalhes! 🎸
