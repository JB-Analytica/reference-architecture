{#- The source stores money as integer cents (the right call for an OLTP system).
    Marts expose euros because that is what a person reads; convert exactly once, here.

    The parentheses around the argument are load-bearing. Without them the macro expanded to
    `{{ column }} / 100`, and any caller passing a compound expression got operator precedence
    instead of the conversion it asked for: `a - b` became `a - b / 100`, dividing only the
    last term. That silently inflated fct_order_items.net_amount_eur by about 100x and
    dim_products.unit_margin_eur by about 500x, which is how a single coffee SKU came to show
    more revenue than the entire business. Pass an expression, get that expression converted. -#}
{% macro cents_to_eur(column) -%}
    round(({{ column }}) / 100, 2)
{%- endmacro %}
