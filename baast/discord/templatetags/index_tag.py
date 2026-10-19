from django import template

register = template.Library()

@register.filter
def index(sequence, i):
    try:
        return sequence[int(i)]
    except (IndexError, TypeError):
        return None
    
@register.filter
def nested_index(sequence, indices):
    try:
        result = sequence
        for index in indices:
            result = result[int(index)]
        return result
    except (IndexError, TypeError):
        return None