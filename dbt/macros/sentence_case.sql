{#- The source stores its enums lowercase and snake_cased (`light`, `beans`, `mobile_app`);
    marts expose labels a person reads.

    Sentence case, not title case: this site writes "Webshop performance" and "Average days to
    ship", so a channel is "Mobile app". Title-casing every word gave "Mobile App", which is the
    only Title Case string on the site and reads as a different voice. Every other label here is
    a single word, so this changes exactly one value -- but the rule is what matters, because
    the next two-word enum would have been wrong too.

    Underscores become spaces first, or `mobile_app` reads `Mobile_app`. DuckDB has no initcap,
    so the first character is uppercased explicitly and the rest left lower. Empty strings pass
    through unharmed: `upper(''[1]) || ''[2:]` is `''`, not an error. -#}
{% macro sentence_case(column) -%}
    {%- set text -%}replace(lower({{ column }}), '_', ' '){%- endset -%}
    upper(({{ text }})[1]) || ({{ text }})[2:]
{%- endmacro %}
