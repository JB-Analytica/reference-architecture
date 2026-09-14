{#- The source stores its enums lowercase (`light`, `beans`, `ethiopia`); marts expose labels
    a person reads. DuckDB has no initcap, so capitalise each word explicitly: split on spaces,
    upper the first character of each part, keep the rest. Empty strings pass through unharmed. -#}
{% macro title_case(column) -%}
    array_to_string(
        list_transform(string_split(lower({{ column }}), ' '), w -> upper(w[1]) || w[2:]), ' '
    )
{%- endmacro %}
