---
title: Products
sidebar_position: 2
description: The same revenue definition as the performance page, one grain down — per product, read off the same mart column rather than re-derived.
og:
  title: Products · JB Analytica Reference Architecture
  image: /og.png
---

Revenue per product. This is the same realised revenue the [performance page](/performance)
totals, read one grain down: `realised_net_amount_eur` on `fct_order_items` rather than on
`fct_orders`, summed by product instead of by month. The column is not re-derived here — a
cancelled line contributes €0 on this page for exactly the reason a cancelled order does on that
one, because it is the same definition in the same mart.

Origin, roast and category are mart columns too. `dim_products` composes both the display labels
and the product name from the source's lowercase enums, so a product reads the same way on every
page and no page has to know that the warehouse stores `light`.

```sql top_products
select
    p.product_name,
    p.origin_label,
    p.roast_label,
    sum(i.realised_net_amount_eur) as net_revenue_eur,
    sum(i.quantity) filter (where not i.is_cancelled) as units
from refarch.order_items i
join refarch.products p on i.product_id = p.product_id
group by 1, 2, 3
order by net_revenue_eur desc
limit 10
```

<DataTable data={top_products} rows=10>
    <Column id=product_name title="Product" />
    <Column id=origin_label title="Origin" />
    <Column id=roast_label title="Roast" />
    <Column id=units title="Units" fmt=num0 />
    <Column id=net_revenue_eur title="Net revenue" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>

The revenue column is a bar drawn inside the table cell rather than a chart beside it. Product
names run to nearly 40 characters, which a horizontal bar chart clips; `contentType=bar` puts the
bar where the label cannot collide with it.

What this ranking cannot tell you is which products are worth selling. Margin is a mart column
too — `unit_margin_eur` on `dim_products` — but the generator draws cost independently of demand,
so ranking by it would be ranking noise. [Architecture](/architecture) lists the other places the
generated data runs out.
