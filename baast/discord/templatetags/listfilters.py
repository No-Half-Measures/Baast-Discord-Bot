from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='has_value')
def has_value(dictionary: dict, val) -> bool:
    vals = dictionary.values() 
    return val in vals