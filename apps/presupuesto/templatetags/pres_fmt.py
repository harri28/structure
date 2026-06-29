from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def miles(value, decimales=2):
    """
    Formatea un número con separador de miles y decimal español.
    Ejemplo: 200669.58  →  200.669,58
    """
    try:
        n = float(value)
        decimales = int(decimales)
        # Formato US: 200,669.58
        us = f'{n:,.{decimales}f}'
        # Invertir separadores: coma→punto, punto→coma
        return us.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return value
