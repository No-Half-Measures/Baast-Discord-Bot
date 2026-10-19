from django import template

register = template.Library()

@register.inclusion_tag('event.html')
def show_results(event):
    #event = events.choice_set.all()
    return {'event': event}