{#- The source stores money as integer cents (the right call for an OLTP system).
    Marts expose euros because that is what a person reads; convert exactly once, here.

    The parentheses around the argument are load-bearing. Without them the macro expanded to
    `{{ column }} / 100`, and any caller passing a compound expression got operator precedence
    instead of the conversion it asked for: `a - b` became `a - b / 100`, dividing only the
    last term. That silently inflated fct_order_items.net_amount_eur by about 100x and
    dim_products.unit_margin_eur by about 500x, which is how a single coffee SKU came to show
    more revenue than the entire business. Pass an expression, get that expression converted.

    The result is DECIMAL, not DOUBLE, and no step of the conversion touches a float. This used
    to be `round((...) / 100, 2)`, which is a double: exact enough per row, and not exact at all
    once summed. `sum()` over doubles is not associative, so a total depends on the order the
    rows happen to be read in, and a total landing exactly on a half cent rounds either way.
    One did. Honduras medium roast beans total exactly 9313.50 euro of realised revenue, and the
    report showed 9,314 until an unrelated column was added to the mart, which changed the
    physical row order, which made the same sum come out as 9313.499999999998 and display 9,313.
    Nothing about the money had changed. Decimal addition is exact and order-independent, so the
    figure is now 9313.50 whatever order the rows arrive in. `dbt/tests/` fails the build if a
    mart money column goes back to being floating point. -#}
{% macro cents_to_eur(column) -%}
    cast(cast(({{ column }}) as decimal(18, 2)) * 0.01 as decimal(18, 2))
{%- endmacro %}
